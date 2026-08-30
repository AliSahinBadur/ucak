from __future__ import annotations

from typing import Callable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db.models import ChunkEmbedding, DocumentChunk
from .embedding_service import EmbeddingService, build_embedding_service
from .vector_index import invalidate_vector_index


class EmbeddingReindexService:
    PROGRESS_EVERY = 20

    def __init__(
        self,
        session: Session,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.session = session
        self.embedding_service = embedding_service or build_embedding_service()

    def rebuild(self, progress_callback: Callable[[int, int], None] | None = None) -> dict:
        chunks = self.session.scalars(select(DocumentChunk).order_by(DocumentChunk.id.asc())).all()
        self.session.execute(delete(ChunkEmbedding))
        self.session.flush()

        total = len(chunks)
        embeddings_created = 0
        for position, chunk in enumerate(chunks, start=1):
            vector = self.embedding_service.embed_document(chunk.chunk_text)
            if self.embedding_service.has_signal(vector):
                self.session.add(
                    ChunkEmbedding(
                        chunk_id=chunk.id,
                        embedding=self.embedding_service.serialize(vector),
                    )
                )
                embeddings_created += 1
            if progress_callback and (position % self.PROGRESS_EVERY == 0 or position == total):
                progress_callback(position, total)

        self.session.commit()
        invalidate_vector_index()
        return {
            "embedding_provider": self.embedding_service.provider_name,
            "chunks_seen": total,
            "embeddings_created": embeddings_created,
        }
