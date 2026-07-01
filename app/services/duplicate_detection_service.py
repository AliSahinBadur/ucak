from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import ChunkEmbedding, Document, DocumentChunk, DuplicateReportPair
from .embedding_service import EmbeddingService, build_embedding_service


@dataclass
class DocumentSignature:
    document_id: int
    title: str
    file_name: str
    chunk_count: int
    vector: list[float]
    key_text: str


class DuplicateDetectionService:
    DEFAULT_THRESHOLD = 0.90

    def __init__(
        self,
        session: Session,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.session = session
        self.embedding_service = embedding_service or build_embedding_service()

    def list_pairs(self, limit: int = 100) -> dict:
        rows = self.session.execute(
            select(
                DuplicateReportPair,
                Document.id.label("document_id_a"),
                Document.title.label("title_a"),
                Document.file_name.label("file_name_a"),
            )
            .join(Document, Document.id == DuplicateReportPair.document_id_a)
            .order_by(DuplicateReportPair.similarity_score.desc(), DuplicateReportPair.id.asc())
            .limit(limit)
        ).all()
        if not rows:
            return {"total": 0, "items": []}

        document_b_ids = [int(row[0].document_id_b) for row in rows]
        documents_b = {
            int(document.id): document
            for document in self.session.scalars(select(Document).where(Document.id.in_(document_b_ids))).all()
        }

        items = []
        for pair, document_id_a, title_a, file_name_a in rows:
            document_b = documents_b.get(int(pair.document_id_b))
            items.append(
                {
                    "id": pair.id,
                    "document_id_a": int(document_id_a),
                    "document_title_a": title_a,
                    "file_name_a": file_name_a,
                    "document_id_b": int(pair.document_id_b),
                    "document_title_b": document_b.title if document_b else "",
                    "file_name_b": document_b.file_name if document_b else "",
                    "similarity_score": float(pair.similarity_score),
                    "title_score": float(pair.title_score),
                    "embedding_score": float(pair.embedding_score),
                    "matched_chunks": int(pair.matched_chunks),
                    "reason": pair.reason,
                    "status": pair.status,
                    "updated_at": pair.updated_at.isoformat() if pair.updated_at else None,
                }
            )
        return {"total": len(items), "items": items}

    def scan(self, threshold: float = DEFAULT_THRESHOLD, dry_run: bool = False) -> dict:
        signatures = self._document_signatures()
        candidates: list[dict] = []
        for index, left in enumerate(signatures):
            for right in signatures[index + 1 :]:
                title_score = self._title_similarity(left.key_text, right.key_text)
                embedding_score = self._embedding_similarity(left.vector, right.vector)
                score = max(title_score, embedding_score)
                if score < threshold:
                    continue
                candidates.append(
                    {
                        "document_id_a": min(left.document_id, right.document_id),
                        "document_id_b": max(left.document_id, right.document_id),
                        "document_title_a": left.title if left.document_id < right.document_id else right.title,
                        "document_title_b": right.title if left.document_id < right.document_id else left.title,
                        "file_name_a": left.file_name if left.document_id < right.document_id else right.file_name,
                        "file_name_b": right.file_name if left.document_id < right.document_id else left.file_name,
                        "similarity_score": score,
                        "title_score": title_score,
                        "embedding_score": embedding_score,
                        "matched_chunks": min(left.chunk_count, right.chunk_count),
                        "reason": self._reason(title_score, embedding_score),
                    }
                )

        candidates.sort(key=lambda item: item["similarity_score"], reverse=True)
        created_count = 0
        updated_count = 0
        if not dry_run:
            for item in candidates:
                pair = self.session.scalar(
                    select(DuplicateReportPair).where(
                        DuplicateReportPair.document_id_a == item["document_id_a"],
                        DuplicateReportPair.document_id_b == item["document_id_b"],
                    )
                )
                if pair is None:
                    pair = DuplicateReportPair(
                        document_id_a=item["document_id_a"],
                        document_id_b=item["document_id_b"],
                        status="candidate",
                    )
                    self.session.add(pair)
                    created_count += 1
                else:
                    updated_count += 1

                pair.similarity_score = float(item["similarity_score"])
                pair.title_score = float(item["title_score"])
                pair.embedding_score = float(item["embedding_score"])
                pair.matched_chunks = int(item["matched_chunks"])
                pair.reason = item["reason"]
            self.session.commit()

        return {
            "dry_run": dry_run,
            "threshold": threshold,
            "documents_seen": len(signatures),
            "candidate_count": len(candidates),
            "created_count": created_count,
            "updated_count": updated_count,
            "items": candidates[:100],
        }

    def _document_signatures(self) -> list[DocumentSignature]:
        rows = self.session.execute(
            select(
                Document.id,
                Document.title,
                Document.file_name,
                DocumentChunk.id.label("chunk_id"),
                ChunkEmbedding.embedding,
            )
            .join(DocumentChunk, DocumentChunk.document_id == Document.id)
            .outerjoin(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
            .order_by(Document.id.asc(), DocumentChunk.chunk_order.asc())
        ).all()

        grouped: dict[int, dict] = {}
        for row in rows:
            document_id = int(row.id)
            current = grouped.setdefault(
                document_id,
                {
                    "title": row.title,
                    "file_name": row.file_name,
                    "vectors": [],
                    "chunk_count": 0,
                },
            )
            current["chunk_count"] += 1
            if row.embedding:
                vector = self.embedding_service.deserialize(row.embedding)
                if self.embedding_service.has_signal(vector):
                    current["vectors"].append(vector)

        signatures = []
        for document_id, data in grouped.items():
            signatures.append(
                DocumentSignature(
                    document_id=document_id,
                    title=data["title"],
                    file_name=data["file_name"],
                    chunk_count=int(data["chunk_count"]),
                    vector=self._average_vector(data["vectors"]),
                    key_text=self._normalize_key(f"{data['title']} {data['file_name']}"),
                )
            )
        return signatures

    def _embedding_similarity(self, left: list[float], right: list[float]) -> float:
        if not self.embedding_service.has_signal(left) or not self.embedding_service.has_signal(right):
            return 0.0
        return max(0.0, self.embedding_service.cosine_similarity(left, right))

    @staticmethod
    def _average_vector(vectors: list[list[float]]) -> list[float]:
        if not vectors:
            return []
        dimensions = len(vectors[0])
        compatible = [vector for vector in vectors if len(vector) == dimensions]
        if not compatible:
            return []
        return [
            sum(vector[index] for vector in compatible) / len(compatible)
            for index in range(dimensions)
        ]

    @staticmethod
    def _title_similarity(left: str, right: str) -> float:
        if not left or not right:
            return 0.0
        ratio = SequenceMatcher(None, left, right).ratio()
        left_tokens = set(left.split())
        right_tokens = set(right.split())
        overlap = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
        return max(ratio, overlap)

    @staticmethod
    def _normalize_key(value: str) -> str:
        translated = value.casefold().translate(
            str.maketrans(
                {
                    "\u0131": "i",
                    "\u011f": "g",
                    "\u00fc": "u",
                    "\u015f": "s",
                    "\u00f6": "o",
                    "\u00e7": "c",
                    "\u0130": "i",
                }
            )
        )
        normalized = unicodedata.normalize("NFKD", translated)
        stripped = "".join(char for char in normalized if not unicodedata.combining(char))
        return " ".join(re.findall(r"[a-z0-9]+", stripped))

    @staticmethod
    def _reason(title_score: float, embedding_score: float) -> str:
        if title_score >= 0.82 and embedding_score >= 0.82:
            return "baslik+embedding"
        if title_score >= 0.82:
            return "baslik"
        return "embedding"
