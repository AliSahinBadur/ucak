from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Document
from .catalog_service import CatalogService
from .qa_service import QAService
from .search_service import SearchService


class MultiDocumentQAService:
    COMPARISON_TERMS = ("karsilastir", "kiyasla", "fark", "farki", "ayni", "farkli")

    def __init__(self, session: Session) -> None:
        self.session = session
        self.catalog_service = CatalogService(session)
        self.qa_service = QAService(session)
        self.search_service = self.qa_service.search_service

    def answer_question(
        self,
        question: str,
        mode: str = "hybrid",
        limit: int = 6,
        document_ids: list[int] | None = None,
        catalog_question: str | None = None,
    ) -> dict:
        cleaned_question = " ".join(question.split())
        resolved_document_ids = SearchService._normalize_document_ids(document_ids)
        catalog_matches: list[dict] = []

        if catalog_question and catalog_question.strip():
            catalog_result = self.catalog_service.answer_catalog_question(catalog_question.strip(), limit=max(limit * 8, 40))
            catalog_matches = catalog_result.get("catalog_matches", [])
            resolved_document_ids = SearchService._normalize_document_ids(
                resolved_document_ids
                + [
                    int(item["matched_document_id"])
                    for item in catalog_matches
                    if item.get("matched_document_id")
                ]
            )

        if not resolved_document_ids:
            return self._empty_response(
                question=cleaned_question,
                mode=mode,
                catalog_question=catalog_question,
                matched_catalog_count=len(catalog_matches),
                answer=(
                    "Bu kapsam icin yuklenmis eslesen rapor bulunamadi. "
                    "Once ilgili PDF veya DOCX raporlarini yukleyip tekrar dene."
                ),
            )

        documents = self._load_documents(resolved_document_ids)
        if not documents:
            return self._empty_response(
                question=cleaned_question,
                mode=mode,
                catalog_question=catalog_question,
                matched_catalog_count=len(catalog_matches),
                answer="Secilen belge grubuna ait yuklenmis rapor bulunamadi.",
            )

        if self._is_comparison_question(cleaned_question) and len(documents) > 1:
            return self._comparison_response(
                question=cleaned_question,
                mode=mode,
                limit=limit,
                catalog_question=catalog_question,
                catalog_matches=catalog_matches,
                documents=documents,
            )

        qa_result = self.qa_service.answer_question(
            cleaned_question,
            mode=mode,
            limit=limit,
            document_ids=[document.id for document in documents],
        )
        answer = qa_result["answer"]
        if qa_result["answer_found"] and len(documents) > 1:
            answer = f"{len(documents)} yuklu rapor icinden bulunan cevap:\n{answer}"

        return {
            "question": cleaned_question,
            "catalog_question": catalog_question.strip() if catalog_question else None,
            "mode": mode,
            "answer": answer,
            "answer_found": qa_result["answer_found"],
            "confidence": qa_result["confidence"],
            "embedding_provider": qa_result["embedding_provider"],
            "matched_catalog_count": len(catalog_matches),
            "matched_document_count": len(documents),
            "documents": [self._document_payload(document) for document in documents],
            "comparison_rows": [],
            "sources": qa_result["sources"],
        }

    def _comparison_response(
        self,
        question: str,
        mode: str,
        limit: int,
        catalog_question: str | None,
        catalog_matches: list[dict],
        documents: list[Document],
    ) -> dict:
        comparison_rows: list[dict] = []
        pooled_sources: list[dict] = []
        answer_lines = ["Belge bazli karsilastirma:"]

        for document in documents[:8]:
            qa_result = self.qa_service.answer_question(
                question,
                mode=mode,
                limit=max(2, min(limit, 4)),
                document_id=document.id,
            )
            if qa_result["sources"]:
                pooled_sources.extend(qa_result["sources"][:2])
            if not qa_result["answer_found"]:
                comparison_rows.append(
                    {
                        "document_id": document.id,
                        "document_title": document.title,
                        "answer": "Bu belgede guvenilir cevap secilemedi.",
                        "confidence": qa_result["confidence"],
                        "source_count": len(qa_result["sources"]),
                    }
                )
                answer_lines.append(f"- {document.title}: guvenilir cevap secilemedi.")
                continue

            comparison_rows.append(
                {
                    "document_id": document.id,
                    "document_title": document.title,
                    "answer": qa_result["answer"],
                    "confidence": qa_result["confidence"],
                    "source_count": len(qa_result["sources"]),
                }
            )
            answer_lines.append(f"- {document.title}: {qa_result['answer']}")

        answer_found = any(row["source_count"] > 0 for row in comparison_rows)
        confidence = max((row["confidence"] for row in comparison_rows), default=0.0)
        deduped_sources = self._dedupe_sources(pooled_sources)[:8]
        return {
            "question": question,
            "catalog_question": catalog_question.strip() if catalog_question else None,
            "mode": mode,
            "answer": "\n".join(answer_lines),
            "answer_found": answer_found,
            "confidence": round(confidence, 3),
            "embedding_provider": self.search_service.embedding_provider_name(),
            "matched_catalog_count": len(catalog_matches),
            "matched_document_count": len(documents),
            "documents": [self._document_payload(document) for document in documents],
            "comparison_rows": comparison_rows,
            "sources": deduped_sources,
        }

    def _load_documents(self, document_ids: list[int]) -> list[Document]:
        rows = self.session.execute(
            select(Document)
            .where(Document.id.in_(document_ids))
            .order_by(Document.title.asc())
        ).scalars().all()
        rows_by_id = {document.id: document for document in rows}
        return [rows_by_id[document_id] for document_id in document_ids if document_id in rows_by_id]

    @staticmethod
    def _document_payload(document: Document) -> dict:
        return {
            "document_id": document.id,
            "document_title": document.title,
            "file_name": document.file_name,
        }

    @classmethod
    def _is_comparison_question(cls, question: str) -> bool:
        lowered = question.casefold()
        normalized = lowered.translate(str.maketrans({"ı": "i", "ğ": "g", "ü": "u", "ş": "s", "ö": "o", "ç": "c"}))
        if any(term in normalized for term in cls.COMPARISON_TERMS):
            return True
        return len(re.findall(r"\bve\b", normalized)) >= 1 and "?" not in normalized

    @staticmethod
    def _dedupe_sources(sources: list[dict]) -> list[dict]:
        deduped: list[dict] = []
        seen: set[tuple[int, int, int]] = set()
        for source in sources:
            key = (
                int(source.get("document_id", 0) or 0),
                int(source.get("page_start", 0) or 0),
                int(source.get("page_end", 0) or 0),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(source)
        return deduped

    def _empty_response(
        self,
        question: str,
        mode: str,
        catalog_question: str | None,
        matched_catalog_count: int,
        answer: str,
    ) -> dict:
        return {
            "question": question,
            "catalog_question": catalog_question.strip() if catalog_question else None,
            "mode": mode,
            "answer": answer,
            "answer_found": False,
            "confidence": 0.0,
            "embedding_provider": self.search_service.embedding_provider_name(),
            "matched_catalog_count": matched_catalog_count,
            "matched_document_count": 0,
            "documents": [],
            "comparison_rows": [],
            "sources": [],
        }
