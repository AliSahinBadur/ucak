from __future__ import annotations

from typing import Protocol

from ..config import RERANKER_BACKEND, RERANKER_ENABLED


class Reranker(Protocol):
    provider_name: str

    def rerank(self, query: str, candidates: list[dict], top_k: int) -> list[dict]:
        ...


class NoOpReranker:
    provider_name = "disabled"

    def rerank(self, query: str, candidates: list[dict], top_k: int) -> list[dict]:
        return candidates[:top_k]


class ScoreReranker:
    provider_name = "score"

    def rerank(self, query: str, candidates: list[dict], top_k: int) -> list[dict]:
        ranked = sorted(
            candidates,
            key=lambda item: (
                float(item.get("combined_score", 0.0) or 0.0),
                float(item.get("semantic_score", 0.0) or 0.0),
                float(item.get("keyword_score", 0.0) or 0.0),
            ),
            reverse=True,
        )
        return ranked[:top_k]


def build_reranker() -> Reranker:
    if not RERANKER_ENABLED or RERANKER_BACKEND in {"", "disabled", "none"}:
        return NoOpReranker()
    if RERANKER_BACKEND == "score":
        return ScoreReranker()
    return NoOpReranker()
