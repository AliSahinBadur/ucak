from __future__ import annotations

import logging
import threading
from collections import Counter
from dataclasses import dataclass

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import ChunkEmbedding, DocumentChunk
from .embedding_service import BaseEmbeddingService


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VectorIndex:
    """All chunk embeddings as one L2-normalized float32 matrix.

    Row i of `matrix` belongs to chunk `chunk_ids[i]` in document `document_ids[i]`,
    so cosine similarity against every chunk is a single `matrix @ query` product.
    """

    chunk_ids: np.ndarray
    document_ids: np.ndarray
    matrix: np.ndarray
    dimensions: int

    def cosine_scores(self, query_vector: list[float]) -> np.ndarray | None:
        query = np.asarray(query_vector, dtype=np.float32)
        if query.ndim != 1 or query.shape[0] != self.dimensions:
            return None
        norm = float(np.linalg.norm(query))
        if norm == 0.0:
            return None
        return self.matrix @ (query / norm)

    def cosine_scores_many(self, query_vectors: list[list[float]]) -> np.ndarray | None:
        """Scores for several query vectors at once, shape (chunks, queries)."""
        compatible = [vector for vector in query_vectors if len(vector) == self.dimensions]
        if not compatible:
            return None
        queries = np.asarray(compatible, dtype=np.float32)
        norms = np.linalg.norm(queries, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        return self.matrix @ (queries / norms).T


class _VectorIndexCache:
    """Process-wide cache of the embedding matrix.

    Freshness is stamped with (count, max id, sum of ids) over chunk_embeddings —
    a cheap query that changes whenever embeddings are added, removed or replaced,
    so readers never need explicit invalidation to stay correct. Writers still call
    invalidate() to drop the matrix eagerly after commits.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._index: VectorIndex | None = None
        self._stamp: tuple[int, int, int] | None = None

    def get(self, session: Session) -> VectorIndex | None:
        stamp = self._current_stamp(session)
        with self._lock:
            if stamp == self._stamp and self._index is not None:
                return self._index if self._index.chunk_ids.size else None
            index = self._load(session)
            self._index = index
            self._stamp = stamp
            return index if index.chunk_ids.size else None

    def invalidate(self) -> None:
        with self._lock:
            self._index = None
            self._stamp = None

    @staticmethod
    def _current_stamp(session: Session) -> tuple[int, int, int]:
        row = session.execute(
            select(
                func.count(ChunkEmbedding.chunk_id),
                func.coalesce(func.max(ChunkEmbedding.chunk_id), 0),
                func.coalesce(func.sum(ChunkEmbedding.chunk_id), 0),
            )
        ).one()
        return (int(row[0]), int(row[1]), int(row[2]))

    @staticmethod
    def _load(session: Session) -> VectorIndex:
        rows = session.execute(
            select(ChunkEmbedding.chunk_id, DocumentChunk.document_id, ChunkEmbedding.embedding)
            .join(DocumentChunk, DocumentChunk.id == ChunkEmbedding.chunk_id)
            .order_by(ChunkEmbedding.chunk_id.asc())
        ).all()

        vectors: list[list[float]] = []
        chunk_ids: list[int] = []
        document_ids: list[int] = []
        for chunk_id, document_id, payload in rows:
            try:
                vector = BaseEmbeddingService.deserialize(payload)
            except (ValueError, UnicodeDecodeError):
                logger.warning("Skipping undecodable embedding for chunk %s.", chunk_id)
                continue
            if vector:
                vectors.append(vector)
                chunk_ids.append(int(chunk_id))
                document_ids.append(int(document_id))

        empty = VectorIndex(
            chunk_ids=np.empty(0, dtype=np.int64),
            document_ids=np.empty(0, dtype=np.int64),
            matrix=np.empty((0, 0), dtype=np.float32),
            dimensions=0,
        )
        if not vectors:
            return empty

        # Mixed dimensions can appear when the embedding provider changed without a
        # rebuild; keep the dominant dimension and let a rebuild reconcile the rest.
        dimension_counts = Counter(len(vector) for vector in vectors)
        dimensions = dimension_counts.most_common(1)[0][0]
        if len(dimension_counts) > 1:
            logger.warning(
                "chunk_embeddings holds mixed dimensions %s; indexing only %d-dim vectors. "
                "Run /embeddings/rebuild to re-embed the corpus consistently.",
                dict(dimension_counts),
                dimensions,
            )

        keep = [position for position, vector in enumerate(vectors) if len(vector) == dimensions]
        matrix = np.asarray([vectors[position] for position in keep], dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1)
        signal = norms > 0.0
        if not bool(signal.any()):
            return empty
        matrix = matrix[signal] / norms[signal][:, np.newaxis]
        kept_ids = np.asarray([chunk_ids[position] for position in keep], dtype=np.int64)[signal]
        kept_documents = np.asarray([document_ids[position] for position in keep], dtype=np.int64)[signal]
        logger.info("Vector index loaded: %d chunks x %d dimensions.", matrix.shape[0], dimensions)
        return VectorIndex(
            chunk_ids=kept_ids,
            document_ids=kept_documents,
            matrix=matrix,
            dimensions=dimensions,
        )


_CACHE = _VectorIndexCache()


def get_vector_index(session: Session) -> VectorIndex | None:
    """Return the cached embedding matrix, reloading it if the table changed."""
    return _CACHE.get(session)


def invalidate_vector_index() -> None:
    """Drop the cached matrix; call after committing embedding writes."""
    _CACHE.invalidate()
