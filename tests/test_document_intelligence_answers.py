from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import (
    Base,
    CatalogDocumentLink,
    Document,
    DocumentChunk,
    ReportCatalogEntry,
)
from app.services.document_intelligence_service import DocumentIntelligenceService
from app.services.llm_provider import DisabledLLMProvider


class ThinkingLLMProvider:
    provider_name = "test-thinking"

    def __init__(self) -> None:
        self.prompt = ""

    def is_available(self) -> bool:
        return True

    def generate_json(self, prompt, schema):
        self.prompt = prompt
        return schema(
            route="document",
            is_follow_up=True,
            use_previous_documents=True,
            standalone_question="2025-BIG-E-DUR-01 raporunda kullanılan profil malzemesi nedir?",
            confidence=0.97,
            rationale="Kullanıcı önceki teknik soruyu sürdürüyor.",
        )

    def generate(self, prompt, *, max_tokens=None, temperature=0.0) -> str:
        return ""


class DocumentIntelligenceAnswerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_report_heading_focuses_attribute_answer_and_follow_up(self) -> None:
        document = Document(
            title="2025-BIG-E-DUR-01",
            file_name="2025-BIG-E-DUR-01.pdf",
            file_type="pdf",
            file_hash="a" * 64,
            file_path="C:/2025-BIG-E-DUR-01.pdf",
        )
        self.session.add(document)
        self.session.flush()
        self.session.add_all(
            [
                DocumentChunk(
                    document_id=document.id,
                    page_start=1,
                    page_end=1,
                    section_title="KAPSAM",
                    chunk_text=(
                        r"V:\RAPORLAR\BIG-E\2025-BIG-e-DUR-01 Page 1 / 10 "
                        "BIG-E DETAY STOK REGALLERI STATİK ANALİZ RAPORU KAPSAM: "
                        "Stok regallerinin statik analizleri gerçekleştirilmiştir."
                    ),
                    chunk_order=0,
                ),
                DocumentChunk(
                    document_id=document.id,
                    page_start=3,
                    page_end=3,
                    section_title="MALZEME ÖZELLİKLERİ",
                    chunk_text=(
                        "Tasarımda, profil malzemeleri için çelik S235 malzemesi kullanılmıştır. "
                        "S235 çeliğinin akma mukavemeti 235 MPa'dır."
                    ),
                    chunk_order=1,
                ),
            ]
        )
        catalog = ReportCatalogEntry(
            report_code="2025-BIG-E-DUR-01",
            vehicle_name="BIG-E",
            report_title="Taşıyıcı Statik Analizleri",
            discipline="DURABILITY",
            report_date="2025-01-01",
            authors="TEST",
            source_path=r"V:\RAPORLAR\BIG-E\2025-BIG-e-DUR-01",
            row_hash="b" * 64,
        )
        self.session.add(catalog)
        self.session.flush()
        self.session.add(
            CatalogDocumentLink(
                catalog_entry_id=catalog.id,
                document_id=document.id,
                source_path=catalog.source_path,
                match_method="test",
            )
        )
        self.session.commit()

        service = DocumentIntelligenceService(
            self.session,
            llm_provider=DisabledLLMProvider(),
        )
        question = "BIG-E DETAY STOK REGALLERI STATİK ANALİZ RAPORU profil malzemesi nedir"

        self.assertEqual([document.id], service._resolve_document_mentions(question))
        result = service.answer_question(question, mode="keyword", retrieval_version="v2")

        self.assertTrue(result["answer_found"])
        self.assertIn("S235", result["answer"])
        self.assertNotIn(r"V:\RAPORLAR", result["answer"])
        self.assertLess(result["confidence"], 1.0)
        self.assertEqual({document.id}, {source["document_id"] for source in result["sources"]})

        follow_up = service.answer_question(
            "Başka hangi malzemeler vardı o raporda?",
            history=[
                {"role": "user", "content": question},
                {"role": "assistant", "content": result["answer"]},
            ],
            context_document_ids=[document.id],
            mode="keyword",
            retrieval_version="v2",
        )

        self.assertTrue(service._uses_context_reference("Başka hangi malzemeler vardı o raporda?"))
        self.assertTrue(follow_up["answer_found"])
        self.assertIn("farklı bir malzeme belirtilmemiş", follow_up["answer"])
        self.assertIn("S235", follow_up["answer"])
        self.assertEqual({document.id}, {source["document_id"] for source in follow_up["sources"]})

    def test_thinking_mode_resolves_unlisted_follow_up_with_llm(self) -> None:
        document = Document(
            title="2025-BIG-E-DUR-01",
            file_name="2025-BIG-E-DUR-01.pdf",
            file_type="pdf",
            file_hash="c" * 64,
            file_path="C:/2025-BIG-E-DUR-01.pdf",
        )
        self.session.add(document)
        self.session.flush()
        self.session.add(
            DocumentChunk(
                document_id=document.id,
                page_start=3,
                page_end=3,
                section_title="MALZEME ÖZELLİKLERİ",
                chunk_text="Profil malzemesi olarak S235 çelik kullanılmıştır.",
                chunk_order=0,
            )
        )
        self.session.commit()

        provider = ThinkingLLMProvider()
        service = DocumentIntelligenceService(self.session, llm_provider=provider)
        follow_up_question = "Devamındaki teknik ayrıntıyı da söyler misin?"
        self.assertFalse(service._uses_context_reference(follow_up_question))

        result = service.answer_question(
            follow_up_question,
            history=[
                {"role": "user", "content": "Bu çalışmada hangi profil malzemesi kullanılmış?"},
                {"role": "assistant", "content": "Profil malzemesi S235 çeliktir."},
            ],
            context_document_ids=[document.id],
            mode="keyword",
            retrieval_version="v2",
            thinking_mode=True,
        )

        self.assertTrue(service.last_thinking_used)
        self.assertEqual("document", service.last_thinking_route)
        self.assertEqual(
            "2025-BIG-E-DUR-01 raporunda kullanılan profil malzemesi nedir?",
            service.last_resolved_question,
        )
        self.assertIn("AKTIF KAYNAK BELGELER", provider.prompt)
        self.assertIn("document_id=1", provider.prompt)
        self.assertTrue(result["answer_found"])
        self.assertIn("S235", result["answer"])
        self.assertEqual({document.id}, {source["document_id"] for source in result["sources"]})


if __name__ == "__main__":
    unittest.main()
