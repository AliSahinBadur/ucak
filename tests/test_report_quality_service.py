from __future__ import annotations

import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import Base, Document, DocumentPage
from app.services.document_intelligence_service import DocumentIntelligenceService
from app.services.report_quality_service import ReportQualityService


class ReportQualityServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def _add_document(self, title: str, page_texts: list[str]) -> int:
        document = Document(
            title=title,
            file_name=f"{title}.pdf",
            file_type="pdf",
            file_hash=(title.lower().replace("-", "") + "0" * 64)[:64],
            file_path=f"C:/{title}.pdf",
        )
        self.session.add(document)
        self.session.flush()
        for page_number, text in enumerate(page_texts, start=1):
            self.session.add(
                DocumentPage(
                    document_id=document.id,
                    page_number=page_number,
                    raw_text=text,
                    clean_text=text,
                    section_title=None,
                )
            )
        self.session.commit()
        return int(document.id)

    def test_reports_complete_table_and_figure_sequences(self) -> None:
        document_id = self._add_document(
            "SYN-001",
            [
                "Tablo 1 - Ilk tablo\nSekil 1 - Ilk model",
                "Tablo 2 - Ikinci tablo\nSekil 2 - Ikinci model",
                "Tablo 3 - Son tablo\nSekil 3 - Son model",
            ],
        )

        result = ReportQualityService(self.session).answer_question(
            "SYN-001 raporunda tablo ve sekil numaralandirmasi dogru mu?",
            [document_id],
        )

        self.assertTrue(result["answer_found"])
        self.assertIn("numaralandirmasi dogru gorunuyor", result["answer"])
        self.assertIn("Tablolar: 1, 2, 3", result["answer"])
        self.assertIn("Sekiller: 1, 2, 3", result["answer"])

    def test_reports_missing_duplicate_and_out_of_order_numbers(self) -> None:
        document_id = self._add_document(
            "SYN-002",
            [
                "Tablo 1 - Ilk tablo",
                "Tablo 3 - Ucuncu tablo",
                "Tablo 3 - Tekrarlanan tablo",
                "Tablo 5 - Besinci tablo",
                "Tablo 2 - Ikinci tablo",
            ],
        )

        result = ReportQualityService(self.session).answer_question(
            "SYN-002 tablo numaralandirmasi dogru mu?",
            [document_id],
        )

        self.assertIn("sorun bulundu", result["answer"])
        self.assertIn("tekrar eden: 3", result["answer"])
        self.assertIn("eksik: 4", result["answer"])
        self.assertIn("gecis sirasi bozuk", result["answer"])

    def test_ignores_inline_table_references(self) -> None:
        document_id = self._add_document(
            "SYN-003",
            ["Tablo 1 - Sonuclar\nTablo 1'de sonuclar verilmistir."],
        )
        page = self.session.scalar(select(DocumentPage).where(DocumentPage.document_id == document_id))

        captions = ReportQualityService.extract_captions([page])

        self.assertEqual(["1"], [caption.number_text for caption in captions])

    def test_detects_quality_question_intent(self) -> None:
        question = "2025-BIG-E-DUR-01 bu rapordaki tablo isimlendirmesi dogru mu yapilmis?"
        self.assertEqual("quality", DocumentIntelligenceService._detect_intent(question))


if __name__ == "__main__":
    unittest.main()
