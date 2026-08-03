from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.models import Base, ChunkEmbedding, Document, DocumentChunk
from app.services.document_intelligence_service import DocumentIntelligenceService
from app.services.embedding_service import BaseEmbeddingService
from app.services.search_service import SearchService


class RecordingEmbeddingService(BaseEmbeddingService):
    provider_name = "recording-rag-v2"

    def __init__(self) -> None:
        self.query_calls: list[str] = []
        self.document_calls: list[str] = []
        self.legacy_calls: list[str] = []

    def embed_text(self, text: str) -> list[float]:
        self.legacy_calls.append(text)
        return [1.0, 0.0]

    def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return [1.0, 0.0]

    def embed_document(self, text: str) -> list[float]:
        self.document_calls.append(text)
        return [1.0, 0.0]


class DisabledLLM:
    provider_name = "disabled-test"

    @staticmethod
    def is_available() -> bool:
        return False


def add_document(session: Session, title: str, vectors_and_texts: list[tuple[list[float], str]]) -> int:
    document = Document(
        title=title,
        file_name=f"{title}.pdf",
        file_type="pdf",
        file_hash=f"hash-{title}",
        file_path=f"C:/{title}.pdf",
    )
    session.add(document)
    session.flush()
    for index, (vector, text) in enumerate(vectors_and_texts, start=1):
        chunk = DocumentChunk(
            document_id=document.id,
            page_start=index,
            page_end=index,
            section_title="SONUCLAR",
            chunk_text=text,
            chunk_order=index,
        )
        session.add(chunk)
        session.flush()
        session.add(
            ChunkEmbedding(
                chunk_id=chunk.id,
                embedding=BaseEmbeddingService.serialize(vector),
            )
        )
    session.flush()
    return int(document.id)


def main() -> int:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    embedding_service = RecordingEmbeddingService()

    with Session(engine) as session:
        search = SearchService(session, embedding_service=embedding_service)
        empty_document = Document(
            title="EMPTY",
            file_name="EMPTY.pdf",
            file_type="pdf",
            file_hash="hash-empty",
            file_path="C:/EMPTY.pdf",
        )
        session.add(empty_document)
        session.flush()
        session.add(
            DocumentChunk(
                document_id=empty_document.id,
                page_start=1,
                page_end=1,
                section_title=None,
                chunk_text="Embedding kaydi olmayan parca.",
                chunk_order=1,
            )
        )
        session.flush()
        assert search.semantic_available() is False

        primary_id = add_document(
            session,
            "RAPOR-A",
            [
                ([1.0, 0.0], "Tasarim-1 maksimum 120 MPa ile guvenli bulunmustur."),
                ([0.98, 0.2], "Tasarim-2 maksimum 145 MPa sonuc vermistir."),
                ([0.0, 1.0], "Kurum adresi ve kapak bilgileri."),
            ],
        )
        secondary_id = add_document(
            session,
            "RAPOR-B",
            [([0.8, 0.6], "Alternatif tasarim dayanimi incelenmistir.")],
        )
        session.commit()

        assert search.semantic_available() is True
        results = search.semantic_search(
            "hangi tasarim daha dayanikli",
            limit=3,
            max_results_per_document=2,
        )
        result_document_ids = [int(item["document_id"]) for item in results]
        assert embedding_service.query_calls == ["hangi tasarim daha dayanikli"]
        assert result_document_ids.count(primary_id) == 2
        assert secondary_id in result_document_ids
        search.semantic_search(
            "klasik sorgu",
            limit=2,
            retrieval_version="v1",
        )
        assert embedding_service.legacy_calls == ["klasik sorgu"]

        intelligence = DocumentIntelligenceService(session, llm_provider=DisabledLLM())
        intelligence.search_service = search
        sources = intelligence._collect_evidence(
            [primary_id],
            "hangi tasarim daha dayanikli",
            intent="ranking",
            per_document_limit=2,
        )
        assert sources
        assert any(float(source["semantic_score"]) > 0.0 for source in sources)
        classic_sources = intelligence._collect_evidence(
            [primary_id],
            "hangi tasarim daha dayanikli",
            intent="ranking",
            per_document_limit=2,
            retrieval_version="v1",
        )
        assert classic_sources
        assert all(float(source["semantic_score"]) == 0.0 for source in classic_sources)
        assert intelligence._citation_coverage(
            "Tasarim guvenli bulunmustur [K1].",
            source_count=2,
        ) == 1.0
        assert intelligence._citation_coverage(
            "Gecersiz kaynak [K9].",
            source_count=2,
        ) == 0.0

    print("RAG v2 checks: all pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
