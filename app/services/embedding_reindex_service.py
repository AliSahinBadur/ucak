from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db.models import ChunkEmbedding, DocumentChunk
from .embedding_service import EmbeddingService, build_embedding_service


class EmbeddingReindexService:
    def __init__(
        self,
        session: Session,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.session = session
        self.embedding_service = embedding_service or build_embedding_service()

    def rebuild(self) -> dict:
        chunks = self.session.scalars(select(DocumentChunk).order_by(DocumentChunk.id.asc())).all()
        self.session.execute(delete(ChunkEmbedding))
        self.session.flush()

        embeddings_created = 0
        for chunk in chunks:
            vector = self.embedding_service.embed_text(chunk.chunk_text)
            if not self.embedding_service.has_signal(vector):
                continue
            self.session.add(
                ChunkEmbedding(
                    chunk_id=chunk.id,
                    embedding=self.embedding_service.serialize(vector),
                )
            )
            embeddings_created += 1

        self.session.commit()
        return {
            "embedding_provider": self.embedding_service.provider_name,
            "chunks_seen": len(chunks),
            "embeddings_created": embeddings_created,
        }
