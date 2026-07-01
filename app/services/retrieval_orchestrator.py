from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from .catalog_service import CatalogService
from .query_understanding_service import QueryUnderstanding, QueryUnderstandingService
from .reranker_service import Reranker, build_reranker
from .search_service import SearchService


logger = logging.getLogger(__name__)


class RetrievalOrchestrator:
    """Phase-1 orchestration shell; preserves existing SearchService behavior by default."""

    def __init__(
        self,
        session: Session,
        search_service: SearchService | None = None,
        query_understanding_service: QueryUnderstandingService | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        self.session = session
        self.search_service = search_service or SearchService(session)
        self.query_understanding_service = query_understanding_service or QueryUnderstandingService()
        self.reranker = reranker or build_reranker()

    def retrieve(
        self,
        query: str,
        *,
        mode: str = "hybrid",
        limit: int = 5,
        document_ids: list[int] | None = None,
        use_query_enhancement: bool = False,
        use_reranking: bool = False,
    ) -> dict:
        fallback_reason = None
        catalog_scope: dict = {"matched_document_ids": [], "match_count": 0}
        try:
            understanding = self.query_understanding_service.understand(query) if use_query_enhancement else None
            queries = self._retrieval_queries(query, understanding)
            scoped_document_ids, catalog_scope = self._catalog_scoped_document_ids(
                query,
                requested_document_ids=document_ids,
                enabled=bool(use_query_enhancement),
            )
            if catalog_scope.get("scope_status") == "catalog_matches_not_ingested":
                results = self._strict_catalog_fallback_results(catalog_scope, mode=mode, limit=limit)
                if results:
                    catalog_scope["scope_status"] = "strict_catalog_title_fallback"
                    fallback_reason = "catalog_link_missing_strict_title_fallback"
                else:
                    fallback_reason = "catalog_matches_not_ingested"
            else:
                merged = self._run_queries(queries, mode=mode, limit=limit, document_ids=scoped_document_ids)
                results = self.reranker.rerank(query, merged, limit) if use_reranking else merged[:limit]
        except Exception as exc:
            logger.exception("Enhanced retrieval failed; falling back to original query only.")
            fallback_reason = exc.__class__.__name__
            understanding = None
            queries = [query]
            results = self._search_once(query, mode=mode, limit=limit, document_ids=document_ids)

        try:
            similar_documents = self.search_service.similar_documents_for_results(results)
        except Exception as exc:
            logger.exception("Similar-document generation failed during orchestrated retrieval.")
            fallback_reason = fallback_reason or f"similar_documents:{exc.__class__.__name__}"
            similar_documents = []

        return {
            "results": results,
            "similar_documents": similar_documents,
            "retrieval": {
                "original_query": query,
                "expanded_queries": queries[1:],
                "applied_filters": understanding.metadata_filters.model_dump() if understanding else {},
                "query_enhancement_used": bool(understanding and understanding.enhancement_used),
                "reranker_used": bool(use_reranking),
                "reranker": self.reranker.provider_name if use_reranking else "disabled",
                "catalog_scope": catalog_scope,
                "fallback_reason": fallback_reason,
            },
        }

    @staticmethod
    def _retrieval_queries(query: str, understanding: QueryUnderstanding | None) -> list[str]:
        queries = [query]
        if understanding:
            queries.extend(understanding.expanded_queries)
            queries.extend(understanding.subqueries)
        deduped: list[str] = []
        seen: set[str] = set()
        for item in queries:
            cleaned = " ".join(str(item or "").split())
            key = cleaned.casefold()
            if cleaned and key not in seen:
                seen.add(key)
                deduped.append(cleaned)
        return deduped[:4]

    def _run_queries(
        self,
        queries: list[str],
        *,
        mode: str,
        limit: int,
        document_ids: list[int] | None,
    ) -> list[dict]:
        merged: dict[int, dict] = {}
        for query in queries:
            results = self._search_once(query, mode=mode, limit=max(limit * 2, limit), document_ids=document_ids)
            for rank, item in enumerate(results):
                key = int(item["id"])
                score = float(item.get("combined_score", 0.0) or 0.0) + 1.0 / (rank + 60)
                if key not in merged or score > float(merged[key].get("_orchestrator_score", 0.0)):
                    merged[key] = {**item, "_orchestrator_score": score}
        return sorted(merged.values(), key=lambda item: item["_orchestrator_score"], reverse=True)

    def _search_once(
        self,
        query: str,
        *,
        mode: str,
        limit: int,
        document_ids: list[int] | None,
    ) -> list[dict]:
        if mode == "keyword":
            return self.search_service.keyword_search(query, limit=limit, document_ids=document_ids)
        if mode == "semantic":
            return self.search_service.semantic_search(query, limit=limit, document_ids=document_ids)
        return self.search_service.hybrid_search(query, limit=limit, document_ids=document_ids)

    def _catalog_scoped_document_ids(
        self,
        query: str,
        *,
        requested_document_ids: list[int] | None,
        enabled: bool,
    ) -> tuple[list[int] | None, dict]:
        requested = self.search_service._normalize_document_ids(requested_document_ids)
        if not enabled:
            return (requested if requested_document_ids is not None else None), {
                "matched_document_ids": [],
                "match_count": 0,
            }

        catalog_answer = CatalogService(self.session).answer_catalog_question(query, limit=80)
        catalog_matches = catalog_answer.get("catalog_matches", [])
        matched_ids = [
            int(item["matched_document_id"])
            for item in catalog_matches
            if item.get("matched_document_id")
        ]
        matched_ids = list(dict.fromkeys(matched_ids))
        if requested:
            requested_set = set(requested)
            matched_ids = [document_id for document_id in matched_ids if document_id in requested_set]

        match_count = int(catalog_answer.get("match_count", 0) or 0)
        scope_status = "unscoped"
        if matched_ids:
            scope_status = "scoped_to_ingested_catalog_documents"
        elif match_count > 0 and requested_document_ids is None:
            scope_status = "catalog_matches_not_ingested"

        scoped_ids = matched_ids or (requested if requested_document_ids is not None else None)
        return scoped_ids, {
            "matched_document_ids": matched_ids[:20],
            "match_count": match_count,
            "scope_status": scope_status,
            "filters": catalog_answer.get("filters", {}),
            "report_codes": [
                str(item.get("report_code", ""))
                for item in catalog_matches[:8]
                if item.get("report_code")
            ],
        }

    def _strict_catalog_fallback_results(self, catalog_scope: dict, *, mode: str, limit: int) -> list[dict]:
        filters = catalog_scope.get("filters", {})
        vehicle = str(filters.get("vehicle") or "").strip()
        year = str(filters.get("year") or "").strip()
        discipline = str(filters.get("discipline") or "").strip()
        if not vehicle:
            return []

        candidates = self._search_once(vehicle, mode="keyword", limit=max(limit * 4, 12), document_ids=None)
        filtered = []
        compact_vehicle = self._compact_text(vehicle)
        for item in candidates:
            document_text = f"{item.get('document_title', '')} {item.get('file_name', '')}"
            compact_document = self._compact_text(document_text)
            if compact_vehicle and compact_vehicle not in compact_document:
                continue
            if year and year not in document_text:
                continue
            if discipline and discipline.casefold() not in document_text.casefold():
                continue
            filtered.append(item)
            if len(filtered) >= limit:
                break
        return filtered

    @staticmethod
    def _compact_text(value: str) -> str:
        return "".join(char for char in value.casefold() if char.isalnum())
