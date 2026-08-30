from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
import logging
import os
import threading
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import ChunkEmbedding, Document, DocumentChunk
from .embedding_service import BaseEmbeddingService
from .search_service import SearchService


logger = logging.getLogger(__name__)


class HaystackUnavailableError(RuntimeError):
    pass


class HaystackRetrievalError(RuntimeError):
    pass


@dataclass(frozen=True)
class _HaystackApi:
    version: str
    document_class: Any
    pipeline_class: Any
    document_store_class: Any
    bm25_retriever_class: Any
    embedding_retriever_class: Any
    document_joiner_class: Any


@dataclass
class _IndexSnapshot:
    signature: tuple[int, int, int, int]
    pipelines: dict[str, Any]
    chunk_count: int
    embedding_count: int
    embedding_dimension: int | None
    run_lock: threading.Lock = field(default_factory=threading.Lock)


@lru_cache(maxsize=1)
def _load_haystack_api() -> _HaystackApi:
    os.environ.setdefault("HAYSTACK_TELEMETRY_ENABLED", "False")
    os.environ.setdefault("HAYSTACK_CONTENT_TRACING_ENABLED", "false")
    try:
        import haystack
        from haystack import Document as HaystackDocument
        from haystack import Pipeline
        from haystack.components.joiners import DocumentJoiner
        from haystack.components.retrievers.in_memory import (
            InMemoryBM25Retriever,
            InMemoryEmbeddingRetriever,
        )
        from haystack.document_stores.in_memory import InMemoryDocumentStore
    except ImportError as exc:
        raise HaystackUnavailableError(
            "RAG v3 icin haystack-ai kurulu degil. 'pip install haystack-ai>=3,<4' komutunu calistir."
        ) from exc

    return _HaystackApi(
        version=str(getattr(haystack, "__version__", "unknown")),
        document_class=HaystackDocument,
        pipeline_class=Pipeline,
        document_store_class=InMemoryDocumentStore,
        bm25_retriever_class=InMemoryBM25Retriever,
        embedding_retriever_class=InMemoryEmbeddingRetriever,
        document_joiner_class=DocumentJoiner,
    )


class HaystackRetrievalService:
    """Isolated Haystack retrieval path used only by RAG v3."""

    _cache_lock = threading.RLock()
    _index_cache: dict[str, _IndexSnapshot] = {}

    def __init__(self, session: Session, search_service: SearchService | None = None) -> None:
        self.session = session
        self.search_service = search_service or SearchService(session)

    @classmethod
    def clear_cache(cls) -> None:
        with cls._cache_lock:
            cls._index_cache.clear()

    @staticmethod
    def ensure_available() -> None:
        _load_haystack_api()

    @property
    def provider_name(self) -> str:
        try:
            return f"haystack:{_load_haystack_api().version}"
        except HaystackUnavailableError:
            return "haystack:unavailable"

    def retrieve(
        self,
        query: str,
        *,
        mode: str = "hybrid",
        limit: int = 5,
        document_ids: list[int] | None = None,
        max_results_per_document: int | None = None,
    ) -> list[dict]:
        cleaned_query = " ".join(str(query or "").split())
        if not cleaned_query:
            return []
        normalized_mode = mode if mode in {"keyword", "semantic", "hybrid"} else "hybrid"
        normalized_document_ids = SearchService._normalize_document_ids(document_ids)
        if document_ids is not None and not normalized_document_ids:
            return []

        snapshot = self._index_snapshot()
        if snapshot.chunk_count <= 0:
            return []

        filters = None
        if normalized_document_ids:
            filters = {
                "field": "meta.document_id",
                "operator": "in",
                "value": normalized_document_ids,
            }
        candidate_limit = min(max(limit * 6, 24), snapshot.chunk_count)

        try:
            with snapshot.run_lock:
                pipeline_result = self._run_pipeline(
                    snapshot,
                    cleaned_query,
                    mode=normalized_mode,
                    filters=filters,
                    top_k=candidate_limit,
                )
        except HaystackRetrievalError:
            raise
        except Exception as exc:
            raise HaystackRetrievalError(f"Haystack RAG v3 retrieval calistirilamadi: {exc}") from exc

        return self._map_pipeline_results(
            cleaned_query,
            pipeline_result,
            mode=normalized_mode,
            limit=limit,
            max_results_per_document=max_results_per_document,
        )

    def _run_pipeline(
        self,
        snapshot: _IndexSnapshot,
        query: str,
        *,
        mode: str,
        filters: dict | None,
        top_k: int,
    ) -> dict[str, Any]:
        if mode == "keyword":
            payload = {"query": query, "top_k": top_k, "scale_score": False}
            if filters:
                payload["filters"] = filters
            output = snapshot.pipelines["keyword"].run({"retriever": payload})
            documents = output.get("retriever", {}).get("documents", [])
            return {"joined": documents, "keyword": documents, "semantic": []}

        query_vector = self.search_service.embedding_service.embed_query(query)
        if not self.search_service.embedding_service.has_signal(query_vector):
            if mode == "hybrid":
                return self._run_pipeline(snapshot, query, mode="keyword", filters=filters, top_k=top_k)
            return {"joined": [], "keyword": [], "semantic": []}
        if snapshot.embedding_dimension is None:
            if mode == "hybrid":
                return self._run_pipeline(snapshot, query, mode="keyword", filters=filters, top_k=top_k)
            return {"joined": [], "keyword": [], "semantic": []}
        if len(query_vector) != snapshot.embedding_dimension:
            raise HaystackRetrievalError(
                "RAG v3 embedding boyutu mevcut indeksle uyusmuyor; embeddingleri yeniden indeksle."
            )

        dense_payload: dict[str, Any] = {
            "query_embedding": query_vector,
            "top_k": top_k,
            "scale_score": False,
            "return_embedding": False,
        }
        if filters:
            dense_payload["filters"] = filters

        if mode == "semantic":
            output = snapshot.pipelines["semantic"].run({"retriever": dense_payload})
            documents = output.get("retriever", {}).get("documents", [])
            return {"joined": documents, "keyword": [], "semantic": documents}

        keyword_payload: dict[str, Any] = {
            "query": query,
            "top_k": top_k,
            "scale_score": False,
        }
        if filters:
            keyword_payload["filters"] = filters
        output = snapshot.pipelines["hybrid"].run(
            {
                "bm25": keyword_payload,
                "dense": dense_payload,
                "joiner": {"top_k": top_k},
            },
            include_outputs_from={"bm25", "dense"},
        )
        return {
            "joined": output.get("joiner", {}).get("documents", []),
            "keyword": output.get("bm25", {}).get("documents", []),
            "semantic": output.get("dense", {}).get("documents", []),
        }

    def _map_pipeline_results(
        self,
        query: str,
        pipeline_result: dict[str, Any],
        *,
        mode: str,
        limit: int,
        max_results_per_document: int | None,
    ) -> list[dict]:
        keyword_scores = self._scores_by_id(pipeline_result.get("keyword", []))
        semantic_scores = self._scores_by_id(pipeline_result.get("semantic", []))
        query_tokens = SearchService._tokenize(query)
        profile = SearchService._query_profile(query, query_tokens)
        results: list[dict] = []

        for document in pipeline_result.get("joined", []):
            meta = dict(getattr(document, "meta", {}) or {})
            chunk_id = int(meta.get("chunk_id", 0) or 0)
            document_id = int(meta.get("document_id", 0) or 0)
            if chunk_id <= 0 or document_id <= 0:
                continue

            chunk_text = str(meta.get("chunk_text") or "")
            document_title = str(meta.get("document_title") or "")
            file_name = str(meta.get("file_name") or "")
            section_title = meta.get("section_title")
            searchable_text = " ".join(
                value for value in (document_title, file_name, str(section_title or ""), chunk_text) if value
            )
            if profile["strict_identity"] and not SearchService._passes_required_token_gate(
                query_tokens,
                searchable_text,
            ):
                continue

            document_key = str(getattr(document, "id", ""))
            lexical_signal = SearchService._keyword_score(
                query=query,
                tokens=query_tokens,
                chunk_text=chunk_text,
                document_title=document_title,
                file_name=file_name,
                section_title=section_title,
            )
            keyword_score = keyword_scores.get(document_key, 0.0) if lexical_signal > 0.0 else 0.0
            semantic_score = semantic_scores.get(document_key, 0.0)

            if mode == "keyword" and keyword_score <= 0.0:
                continue
            if mode == "semantic" and semantic_score < SearchService.MIN_SEMANTIC_SCORE:
                continue
            if (
                mode == "hybrid"
                and keyword_score <= 0.0
                and semantic_score < SearchService.MIN_SEMANTIC_NO_OVERLAP_SCORE
            ):
                continue

            if keyword_score > 0.0 and semantic_score >= SearchService.MIN_SEMANTIC_SCORE:
                match_type = "hybrid"
            elif semantic_score >= SearchService.MIN_SEMANTIC_SCORE:
                match_type = "semantic"
            else:
                match_type = "keyword"
            combined_score = float(getattr(document, "score", 0.0) or 0.0)
            results.append(
                {
                    "id": chunk_id,
                    "document_id": document_id,
                    "document_title": document_title,
                    "file_name": file_name,
                    "page_start": int(meta.get("page_start", 1) or 1),
                    "page_end": int(meta.get("page_end", 1) or 1),
                    "section_title": section_title,
                    "chunk_text": chunk_text,
                    "match_type": match_type,
                    "keyword_score": max(keyword_score, 0.0),
                    "semantic_score": semantic_score,
                    "combined_score": max(combined_score, 0.0),
                    "retrieval_engine": self.provider_name,
                }
            )

        results.sort(key=lambda item: item["combined_score"], reverse=True)
        return self.search_service._metadata_rerank_results(
            query,
            query_tokens,
            results,
            limit,
            max_results_per_document=max_results_per_document,
        )

    def _index_snapshot(self) -> _IndexSnapshot:
        api = _load_haystack_api()
        signature = self._database_signature()
        namespace = self._cache_namespace()
        with self._cache_lock:
            cached = self._index_cache.get(namespace)
            if cached is not None and cached.signature == signature:
                return cached
            snapshot = self._build_index(api, signature)
            self._index_cache[namespace] = snapshot
            return snapshot

    def _build_index(self, api: _HaystackApi, signature: tuple[int, int, int, int]) -> _IndexSnapshot:
        rows = self.session.execute(
            select(
                DocumentChunk.id,
                DocumentChunk.document_id,
                Document.title.label("document_title"),
                Document.file_name,
                DocumentChunk.page_start,
                DocumentChunk.page_end,
                DocumentChunk.section_title,
                DocumentChunk.chunk_text,
                DocumentChunk.chunk_order,
                ChunkEmbedding.embedding,
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .outerjoin(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
            .order_by(DocumentChunk.id.asc())
        ).all()

        prepared_rows: list[tuple[Any, list[float]]] = []
        dimensions: Counter[int] = Counter()
        for row in rows:
            vector = self._deserialize_embedding(row.embedding)
            if vector:
                dimensions[len(vector)] += 1
            prepared_rows.append((row, vector))
        embedding_dimension = dimensions.most_common(1)[0][0] if dimensions else None

        documents = []
        indexed_embedding_count = 0
        for row, vector in prepared_rows:
            embedding = vector if embedding_dimension and len(vector) == embedding_dimension else None
            if embedding is not None:
                indexed_embedding_count += 1
            search_content = "\n".join(
                value
                for value in (
                    str(row.document_title or ""),
                    str(row.file_name or ""),
                    str(row.section_title or ""),
                    str(row.chunk_text or ""),
                )
                if value
            )
            documents.append(
                api.document_class(
                    id=f"chunk-{int(row.id)}",
                    content=search_content,
                    embedding=embedding,
                    meta={
                        "chunk_id": int(row.id),
                        "document_id": int(row.document_id),
                        "document_title": str(row.document_title or ""),
                        "file_name": str(row.file_name or ""),
                        "page_start": int(row.page_start),
                        "page_end": int(row.page_end),
                        "section_title": row.section_title,
                        "chunk_order": int(row.chunk_order),
                        "chunk_text": str(row.chunk_text or ""),
                    },
                )
            )

        document_store = api.document_store_class(
            embedding_similarity_function="cosine",
            shared=False,
            return_embedding=False,
        )
        if documents:
            document_store.write_documents(documents)

        keyword_pipeline = api.pipeline_class()
        keyword_pipeline.add_component(
            "retriever",
            api.bm25_retriever_class(document_store=document_store),
        )

        semantic_pipeline = api.pipeline_class()
        semantic_pipeline.add_component(
            "retriever",
            api.embedding_retriever_class(document_store=document_store),
        )

        hybrid_pipeline = api.pipeline_class()
        hybrid_pipeline.add_component(
            "bm25",
            api.bm25_retriever_class(document_store=document_store),
        )
        hybrid_pipeline.add_component(
            "dense",
            api.embedding_retriever_class(document_store=document_store),
        )
        hybrid_pipeline.add_component(
            "joiner",
            api.document_joiner_class(join_mode="reciprocal_rank_fusion"),
        )
        hybrid_pipeline.connect("bm25.documents", "joiner.documents")
        hybrid_pipeline.connect("dense.documents", "joiner.documents")

        logger.info(
            "Haystack RAG v3 index ready: %s chunks, %s embeddings, dimension=%s.",
            len(documents),
            indexed_embedding_count,
            embedding_dimension or "none",
        )
        return _IndexSnapshot(
            signature=signature,
            pipelines={
                "keyword": keyword_pipeline,
                "semantic": semantic_pipeline,
                "hybrid": hybrid_pipeline,
            },
            chunk_count=len(documents),
            embedding_count=indexed_embedding_count,
            embedding_dimension=embedding_dimension,
        )

    def _database_signature(self) -> tuple[int, int, int, int]:
        chunk_count, max_chunk_id = self.session.execute(
            select(func.count(DocumentChunk.id), func.max(DocumentChunk.id))
        ).one()
        embedding_count, embedding_payload_size = self.session.execute(
            select(
                func.count(ChunkEmbedding.chunk_id),
                func.coalesce(func.sum(func.length(ChunkEmbedding.embedding)), 0),
            )
        ).one()
        return (
            int(chunk_count or 0),
            int(max_chunk_id or 0),
            int(embedding_count or 0),
            int(embedding_payload_size or 0),
        )

    def _cache_namespace(self) -> str:
        bind = self.session.get_bind()
        url = str(bind.url)
        return f"{url}:{id(bind)}" if ":memory:" in url else url

    @staticmethod
    def _deserialize_embedding(payload: bytes | str | None) -> list[float]:
        # Delegates to the embedding service so packed float32 BLOBs and
        # legacy JSON-text payloads both deserialize.
        if not payload:
            return []
        try:
            return BaseEmbeddingService.deserialize(payload)
        except (TypeError, ValueError):
            return []

    @staticmethod
    def _scores_by_id(documents: list[Any]) -> dict[str, float]:
        return {
            str(getattr(document, "id", "")): float(getattr(document, "score", 0.0) or 0.0)
            for document in documents
        }
