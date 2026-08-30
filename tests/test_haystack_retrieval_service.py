from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, ChunkEmbedding, Document, DocumentChunk
from app.services.document_intelligence_service import DocumentIntelligenceService
from app.services.embedding_service import TokenHashEmbeddingService
from app.services.haystack_retrieval_service import HaystackRetrievalService
from app.services.search_service import SearchService


class HaystackRetrievalServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        HaystackRetrievalService.clear_cache()
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.embedding_service = TokenHashEmbeddingService(dimensions=64)
        search_service = SearchService(self.session, embedding_service=self.embedding_service)
        self.service = HaystackRetrievalService(self.session, search_service=search_service)

        self.alternator_id = self._add_document(
            "2025-BIG-E-NVH-01",
            "Alternator braket dogal frekans degeri 42 Hz olarak olculdu.",
        )
        self.thermal_id = self._add_document(
            "2025-BIG-E-TASE-02",
            "Motor sogutma testinde maksimum sicaklik 80 C olarak olculdu.",
        )

    def tearDown(self) -> None:
        HaystackRetrievalService.clear_cache()
        self.session.close()
        self.engine.dispose()

    def _add_document(self, title: str, chunk_text: str) -> int:
        document = Document(
            title=title,
            file_name=f"{title}.pdf",
            file_type="pdf",
            file_hash=(title.replace("-", "").lower() + "0" * 64)[:64],
            file_path=f"C:/{title}.pdf",
        )
        self.session.add(document)
        self.session.flush()
        chunk = DocumentChunk(
            document_id=document.id,
            page_start=1,
            page_end=1,
            section_title="SONUCLAR",
            chunk_text=chunk_text,
            chunk_order=0,
        )
        self.session.add(chunk)
        self.session.flush()
        self.session.add(
            ChunkEmbedding(
                chunk_id=chunk.id,
                embedding=self.embedding_service.serialize(
                    self.embedding_service.embed_document(chunk_text)
                ),
            )
        )
        self.session.commit()
        return int(document.id)

    def test_hybrid_pipeline_returns_relevant_chunk(self) -> None:
        results = self.service.retrieve(
            "alternator braket dogal frekans",
            mode="hybrid",
            limit=2,
        )

        self.assertTrue(results)
        self.assertEqual(self.alternator_id, results[0]["document_id"])
        self.assertTrue(results[0]["retrieval_engine"].startswith("haystack:"))

    def test_document_filter_is_applied_inside_haystack(self) -> None:
        results = self.service.retrieve(
            "sicaklik",
            mode="keyword",
            limit=2,
            document_ids=[self.thermal_id],
        )

        self.assertTrue(results)
        self.assertEqual({self.thermal_id}, {item["document_id"] for item in results})

    def test_strict_missing_report_identity_returns_no_result(self) -> None:
        results = self.service.retrieve(
            "2026 CITIBUS raporlari",
            mode="hybrid",
            limit=5,
        )

        self.assertEqual([], results)

    def test_clear_keyword_lead_focuses_single_report_questions(self) -> None:
        focused = DocumentIntelligenceService._focus_v3_single_document_results(
            [
                {"document_id": 11, "keyword_score": 12.0},
                {"document_id": 22, "keyword_score": 1.0},
                {"document_id": 11, "keyword_score": 4.0},
            ]
        )

        self.assertEqual({11}, {item["document_id"] for item in focused})

    def test_close_keyword_scores_keep_multi_report_candidates(self) -> None:
        focused = DocumentIntelligenceService._focus_v3_single_document_results(
            [
                {"document_id": 11, "keyword_score": 4.0},
                {"document_id": 22, "keyword_score": 2.5},
            ]
        )

        self.assertEqual(2, len(focused))


if __name__ == "__main__":
    unittest.main()
