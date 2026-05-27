from __future__ import annotations

import unicodedata
import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db.models import ChunkEmbedding, Document, DocumentChunk
from .embedding_service import EmbeddingService, build_embedding_service


class SearchService:
    KEYWORD_WEIGHT = 0.45
    SEMANTIC_WEIGHT = 0.55
    MIN_SEMANTIC_SCORE = 0.22
    MIN_SEMANTIC_NO_OVERLAP_SCORE = 0.27
    MIN_SIMILAR_DOCUMENT_SCORE = 0.24
    MAX_RESULTS_PER_DOCUMENT = 2
    MAX_FUZZY_SCAN_ROWS = 1500
    GENERIC_QUERY_TOKENS = {
        "analiz",
        "analizi",
        "rapor",
        "raporu",
        "test",
        "testi",
        "degerlendirme",
        "degerlendirmesi",
        "sonuc",
        "sonuclari",
    }

    def __init__(
        self,
        session: Session,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.session = session
        self.embedding_service = embedding_service or build_embedding_service()

    def keyword_search(self, query: str, limit: int = 5) -> list[dict]:
        raw_query = query.strip()
        tokens = self.embedding_service.tokenize(raw_query)
        if not raw_query:
            return []

        candidate_limit = max(limit * 12, 30)
        searchable_terms = self._expand_search_terms(tokens)
        conditions = [DocumentChunk.chunk_text.ilike(f"%{raw_query}%")]
        for term in searchable_terms:
            conditions.extend(
                (
                    DocumentChunk.chunk_text.ilike(f"%{term}%"),
                    DocumentChunk.section_title.ilike(f"%{term}%"),
                    Document.title.ilike(f"%{term}%"),
                    Document.file_name.ilike(f"%{term}%"),
                )
            )
        exact_rows = self.session.execute(
            self._base_chunk_query().where(or_(*conditions)).limit(candidate_limit)
        ).all()
        fuzzy_rows = self.session.execute(
            self._base_chunk_query().limit(self.MAX_FUZZY_SCAN_ROWS)
        ).all()

        rows_by_id = {int(row.id): row for row in exact_rows}
        for row in fuzzy_rows:
            rows_by_id.setdefault(int(row.id), row)

        results: list[dict] = []
        for row in rows_by_id.values():
            score = self._keyword_score(
                query=raw_query,
                tokens=tokens,
                chunk_text=row.chunk_text,
                document_title=row.document_title,
                file_name=row.file_name,
                section_title=row.section_title,
            )
            if score <= 0.0:
                continue
            results.append(
                {
                    "id": row.id,
                    "document_id": row.document_id,
                    "document_title": row.document_title,
                    "file_name": row.file_name,
                    "page_start": row.page_start,
                    "page_end": row.page_end,
                    "section_title": row.section_title,
                    "chunk_text": row.chunk_text,
                    "match_type": "keyword",
                    "keyword_score": score,
                    "semantic_score": 0.0,
                    "combined_score": score,
                }
            )

        results.sort(key=lambda item: item["keyword_score"], reverse=True)
        return results[:limit]

    def semantic_search(self, query: str, limit: int = 5) -> list[dict]:
        query_tokens = self.embedding_service.tokenize(query.strip())
        query_vector = self.embedding_service.embed_text(query)
        if not self.embedding_service.has_signal(query_vector):
            return []

        statement = (
            select(
                DocumentChunk.id,
                DocumentChunk.document_id,
                Document.title.label("document_title"),
                Document.file_name,
                DocumentChunk.page_start,
                DocumentChunk.page_end,
                DocumentChunk.section_title,
                DocumentChunk.chunk_text,
                ChunkEmbedding.embedding,
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .outerjoin(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
        )
        rows = self.session.execute(statement).all()

        results: list[dict] = []
        expected_dimensions = len(query_vector)
        for row in rows:
            chunk_vector = self._resolve_chunk_vector(row.embedding, expected_dimensions=expected_dimensions)
            if not self.embedding_service.has_signal(chunk_vector):
                continue
            score = self.embedding_service.cosine_similarity(query_vector, chunk_vector)
            token_overlap = self._token_overlap_ratio(query_tokens, row.chunk_text)
            minimum_score = (
                self.MIN_SEMANTIC_SCORE
                if token_overlap > 0.0
                else self.MIN_SEMANTIC_NO_OVERLAP_SCORE
            )
            if score < minimum_score:
                continue
            results.append(
                {
                    "id": row.id,
                    "document_id": row.document_id,
                    "document_title": row.document_title,
                    "file_name": row.file_name,
                    "page_start": row.page_start,
                    "page_end": row.page_end,
                    "section_title": row.section_title,
                    "chunk_text": row.chunk_text,
                    "match_type": "semantic",
                    "keyword_score": 0.0,
                    "semantic_score": score,
                    "combined_score": score,
                }
            )

        results.sort(key=lambda item: item["semantic_score"], reverse=True)
        return self._limit_results_per_document(results, limit)

    def hybrid_search(self, query: str, limit: int = 5) -> list[dict]:
        query_tokens = self.embedding_service.tokenize(query.strip())
        keyword_results = self.keyword_search(query, limit=max(limit * 4, 12))
        semantic_results = self.semantic_search(query, limit=max(limit * 3, 10))
        if not semantic_results:
            return keyword_results[:limit]

        keyword_max = max((item["keyword_score"] for item in keyword_results), default=1.0)
        semantic_max = max((item["semantic_score"] for item in semantic_results), default=1.0)
        merged: dict[int, dict] = {}

        for item in keyword_results:
            merged[item["id"]] = dict(item)
            lexical_score = self._lexical_rerank_score(query, query_tokens, item)
            merged[item["id"]]["combined_score"] = (
                self.KEYWORD_WEIGHT * (item["keyword_score"] / keyword_max)
                + 0.15 * lexical_score
            )

        for item in semantic_results:
            if item["id"] not in merged:
                merged[item["id"]] = dict(item)
                merged[item["id"]]["combined_score"] = 0.0

            merged[item["id"]]["semantic_score"] = item["semantic_score"]
            lexical_score = self._lexical_rerank_score(query, query_tokens, merged[item["id"]])
            merged[item["id"]]["combined_score"] += (
                self.SEMANTIC_WEIGHT * (item["semantic_score"] / semantic_max)
                + 0.15 * lexical_score
            )

        for item in merged.values():
            has_keyword = item.get("keyword_score", 0.0) > 0.0
            has_semantic = item.get("semantic_score", 0.0) > 0.0
            if has_semantic and not has_keyword and item["semantic_score"] < self.MIN_SEMANTIC_NO_OVERLAP_SCORE:
                item["combined_score"] = 0.0
            if has_keyword and has_semantic:
                item["match_type"] = "hybrid"
            elif has_semantic:
                item["match_type"] = "semantic"
            else:
                item["match_type"] = "keyword"

        ranked = sorted(
            (item for item in merged.values() if item["combined_score"] > 0.0),
            key=lambda item: item["combined_score"],
            reverse=True,
        )
        return self._limit_results_per_document(ranked, limit)

    def similar_documents_for_results(self, results: list[dict], limit: int = 3) -> list[dict]:
        if not results:
            return []
        source_chunk_ids = [int(item.get("id", 0) or 0) for item in results if int(item.get("id", 0) or 0) > 0]
        if not source_chunk_ids:
            return []

        source_rows = self.session.execute(
            select(
                DocumentChunk.id,
                DocumentChunk.document_id,
                DocumentChunk.chunk_text,
                ChunkEmbedding.embedding,
            )
            .outerjoin(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
            .where(DocumentChunk.id.in_(source_chunk_ids))
        ).all()
        if not source_rows:
            return []

        result_by_chunk_id = {int(item["id"]): item for item in results}
        source_document_ids = {row.document_id for row in source_rows}
        source_vectors_with_weights: list[tuple[list[float], float]] = []
        for row in source_rows:
            source_vector = self._resolve_chunk_vector(row.embedding)
            if not self.embedding_service.has_signal(source_vector):
                continue
            result_item = result_by_chunk_id.get(int(row.id), {})
            weight = max(
                float(result_item.get("combined_score", 0.0) or 0.0),
                float(result_item.get("semantic_score", 0.0) or 0.0),
                float(result_item.get("keyword_score", 0.0) or 0.0),
                0.1,
            )
            source_vectors_with_weights.append((source_vector, weight))

        if not source_vectors_with_weights:
            return []

        return self._rank_similar_documents(
            source_vectors_with_weights=source_vectors_with_weights,
            excluded_document_ids=source_document_ids,
            limit=limit,
        )

    def similar_documents_for_document(self, document_id: int, limit: int = 3) -> list[dict]:
        source_chunks = self.session.execute(
            select(DocumentChunk.id, DocumentChunk.chunk_text, ChunkEmbedding.embedding)
            .outerjoin(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
            .where(DocumentChunk.document_id == document_id)
        ).all()
        if not source_chunks:
            return []

        source_vectors = [
            self._resolve_chunk_vector(row.embedding)
            for row in source_chunks
        ]
        source_vectors = [vector for vector in source_vectors if self.embedding_service.has_signal(vector)]
        if not source_vectors:
            return []
        return self._rank_similar_documents(
            source_vectors_with_weights=[(vector, 1.0) for vector in source_vectors],
            excluded_document_ids={document_id},
            limit=limit,
        )

    def semantic_available(self) -> bool:
        chunk_id = self.session.scalar(select(DocumentChunk.id).limit(1))
        return chunk_id is not None

    def embedding_provider_name(self) -> str:
        return self.embedding_service.provider_name

    @classmethod
    def _keyword_score(
        cls,
        query: str,
        tokens: list[str],
        chunk_text: str,
        document_title: str = "",
        file_name: str = "",
        section_title: str | None = None,
    ) -> float:
        searchable_text = " ".join(
            value for value in (document_title, file_name, section_title or "", chunk_text) if value
        )
        normalized_text = cls._normalize_search_text(searchable_text)
        normalized_chunk = cls._normalize_search_text(chunk_text)
        normalized_query = cls._normalize_search_text(query)
        unique_tokens = list(dict.fromkeys(tokens))
        normalized_tokens = [cls._normalize_search_text(token) for token in unique_tokens]
        if not normalized_tokens:
            return 0.0

        words = set(cls._search_words(normalized_text))
        chunk_words = set(cls._search_words(normalized_chunk))
        phrase_bonus = 2.4 if normalized_query and normalized_query in normalized_text else 0.0

        token_scores = [cls._best_token_match_score(token, normalized_text, words) for token in normalized_tokens]
        matched_count = sum(1 for score in token_scores if score > 0.0)
        token_coverage = sum(token_scores) / len(normalized_tokens)

        specific_tokens = [token for token in normalized_tokens if token not in cls.GENERIC_QUERY_TOKENS]
        if specific_tokens:
            specific_scores = [cls._best_token_match_score(token, normalized_text, words) for token in specific_tokens]
            specific_coverage = sum(specific_scores) / len(specific_tokens)
            missing_specific_penalty = sum(1 for score in specific_scores if score <= 0.0) * 0.85
        else:
            specific_coverage = 0.0
            missing_specific_penalty = 0.0

        chunk_token_bonus = sum(
            0.18
            for token in normalized_tokens
            if cls._best_token_match_score(token, normalized_chunk, chunk_words) >= 0.8
        )
        frequency = sum(normalized_text.count(token) for token in normalized_tokens)
        missing_penalty = max(len(normalized_tokens) - matched_count, 0) * 0.18
        return (
            phrase_bonus
            + token_coverage * 1.2
            + specific_coverage * 1.7
            + chunk_token_bonus
            + min(frequency, 5) * 0.08
            - missing_penalty
            - missing_specific_penalty
        )

    @classmethod
    def _expand_search_terms(cls, tokens: list[str]) -> list[str]:
        terms: list[str] = []
        for token in tokens:
            normalized = cls._normalize_search_text(token)
            for term in {token, normalized}:
                if term and term not in terms:
                    terms.append(term)
        return terms

    @classmethod
    def _best_token_match_score(cls, token: str, text: str, words: set[str]) -> float:
        if token and token in text:
            return 1.0
        if len(token) < 5:
            return 0.0
        return 0.78 if any(cls._is_near_token(token, word) for word in words) else 0.0

    @classmethod
    def _lexical_rerank_score(cls, query: str, tokens: list[str], item: dict) -> float:
        score = cls._keyword_score(
            query=query,
            tokens=tokens,
            chunk_text=item.get("chunk_text", ""),
            document_title=item.get("document_title", ""),
            file_name=item.get("file_name", ""),
            section_title=item.get("section_title"),
        )
        return max(0.0, min(score / 4.0, 1.0))

    @staticmethod
    def _is_near_token(left: str, right: str) -> bool:
        if abs(len(left) - len(right)) > 1 or min(len(left), len(right)) < 5:
            return False
        if left[0] != right[0]:
            return False
        previous_row = list(range(len(right) + 1))
        for left_index, left_char in enumerate(left, start=1):
            current_row = [left_index]
            for right_index, right_char in enumerate(right, start=1):
                insert_cost = current_row[right_index - 1] + 1
                delete_cost = previous_row[right_index] + 1
                replace_cost = previous_row[right_index - 1] + (left_char != right_char)
                current_row.append(min(insert_cost, delete_cost, replace_cost))
            previous_row = current_row
        max_distance = 2 if min(len(left), len(right)) >= 6 else 1
        return previous_row[-1] <= max_distance

    @staticmethod
    def _normalize_search_text(text: str) -> str:
        translated = text.casefold().translate(
            str.maketrans(
                {
                    "ı": "i",
                    "ğ": "g",
                    "ü": "u",
                    "ş": "s",
                    "ö": "o",
                    "ç": "c",
                    "İ": "i",
                }
            )
        )
        normalized = unicodedata.normalize("NFKD", translated)
        return "".join(char for char in normalized if not unicodedata.combining(char))

    @classmethod
    def _search_words(cls, text: str) -> list[str]:
        return re.findall(r"\w+", text)

    @staticmethod
    def _base_chunk_query():
        return (
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
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .order_by(DocumentChunk.chunk_order.asc())
        )

    def _resolve_chunk_vector(
        self,
        serialized_embedding: str | None,
        expected_dimensions: int | None = None,
    ) -> list[float]:
        if serialized_embedding:
            stored_vector = self.embedding_service.deserialize(serialized_embedding)
            if expected_dimensions is None or len(stored_vector) == expected_dimensions:
                return stored_vector
        return []

    @staticmethod
    def _shorten_text(text: str, max_length: int = 240) -> str:
        compact = " ".join(text.split())
        if len(compact) <= max_length:
            return compact
        return compact[: max_length - 3].rstrip() + "..."

    def _find_document_id_by_title(self, title: str) -> int:
        return int(
            self.session.scalar(select(Document.id).where(Document.title == title).limit(1)) or 0
        )

    def _rank_similar_documents(
        self,
        source_vectors_with_weights: list[tuple[list[float], float]],
        excluded_document_ids: set[int],
        limit: int,
    ) -> list[dict]:
        candidate_rows = self.session.execute(
            select(
                DocumentChunk.document_id,
                Document.title.label("document_title"),
                Document.file_name,
                DocumentChunk.page_start,
                DocumentChunk.page_end,
                DocumentChunk.section_title,
                DocumentChunk.chunk_text,
                ChunkEmbedding.embedding,
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .outerjoin(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
            .where(DocumentChunk.document_id.not_in(excluded_document_ids))
        ).all()

        by_document: dict[int, dict] = {}
        for row in candidate_rows:
            candidate_vector = self._resolve_chunk_vector(row.embedding)
            if not self.embedding_service.has_signal(candidate_vector):
                continue

            best_similarity = max(
                self.embedding_service.cosine_similarity(source_vector, candidate_vector) * weight
                for source_vector, weight in source_vectors_with_weights
            )
            if best_similarity < self.MIN_SIMILAR_DOCUMENT_SCORE:
                continue

            current = by_document.get(row.document_id)
            excerpt = self._shorten_text(row.chunk_text)
            if current is None:
                by_document[row.document_id] = {
                    "document_id": row.document_id,
                    "document_title": row.document_title,
                    "file_name": row.file_name,
                    "matched_chunks": 1,
                    "score": best_similarity,
                    "best_chunk_score": best_similarity,
                    "top_section_title": row.section_title,
                    "top_page_start": row.page_start,
                    "top_page_end": row.page_end,
                    "top_excerpt": excerpt,
                }
                continue

            current["matched_chunks"] += 1
            current["score"] += best_similarity
            if best_similarity > current["best_chunk_score"]:
                current["best_chunk_score"] = best_similarity
                current["top_section_title"] = row.section_title
                current["top_page_start"] = row.page_start
                current["top_page_end"] = row.page_end
                current["top_excerpt"] = excerpt

        ranked = sorted(by_document.values(), key=lambda item: item["score"], reverse=True)
        for item in ranked:
            item.pop("best_chunk_score", None)
        return ranked[:limit]

    def _limit_results_per_document(self, results: list[dict], limit: int) -> list[dict]:
        limited: list[dict] = []
        counts: dict[int, int] = {}
        for item in results:
            document_id = int(item.get("document_id", 0) or 0)
            if document_id > 0 and counts.get(document_id, 0) >= self.MAX_RESULTS_PER_DOCUMENT:
                continue
            if document_id > 0:
                counts[document_id] = counts.get(document_id, 0) + 1
            limited.append(item)
            if len(limited) >= limit:
                break
        return limited

    @staticmethod
    def _token_overlap_ratio(tokens: list[str], text: str) -> float:
        unique_tokens = list(dict.fromkeys(token for token in tokens if token))
        if not unique_tokens:
            return 0.0
        lowered_text = text.casefold()
        overlap = sum(1 for token in unique_tokens if token in lowered_text)
        return overlap / len(unique_tokens)
