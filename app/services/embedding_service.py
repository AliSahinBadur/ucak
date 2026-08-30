from __future__ import annotations

from functools import lru_cache
import json
import logging
import math
import os
import re
import threading
import unicodedata
from hashlib import sha256
from pathlib import Path
from typing import Protocol

import numpy as np

from ..config import get_settings, resolve_embedding_device


logger = logging.getLogger(__name__)
TOKEN_RE = re.compile(r"\w+", re.UNICODE)


class EmbeddingService(Protocol):
    provider_name: str

    def embed_text(self, text: str) -> list[float]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...

    def embed_document(self, text: str) -> list[float]:
        ...

    @staticmethod
    def serialize(vector: list[float]) -> bytes:
        ...

    @staticmethod
    def deserialize(payload: bytes | str | None) -> list[float]:
        ...

    @staticmethod
    def cosine_similarity(left: list[float], right: list[float]) -> float:
        ...

    @staticmethod
    def has_signal(vector: list[float]) -> bool:
        ...

    @staticmethod
    def tokenize(text: str) -> list[str]:
        ...


class BaseEmbeddingService:
    def embed_query(self, text: str) -> list[float]:
        return self.embed_text(text)

    def embed_document(self, text: str) -> list[float]:
        return self.embed_text(text)

    @staticmethod
    def serialize(vector: list[float]) -> bytes:
        return np.asarray(vector, dtype=np.float32).tobytes()

    @staticmethod
    def deserialize(payload: bytes | str | None) -> list[float]:
        if not payload:
            return []
        if isinstance(payload, (bytes, bytearray, memoryview)):
            raw = bytes(payload)
            # Databases written before the BLOB migration hold JSON text, which
            # some access paths hand back as bytes.
            if raw[:1] == b"[" and raw[-1:] == b"]":
                try:
                    return [float(value) for value in json.loads(raw.decode("utf-8"))]
                except (UnicodeDecodeError, ValueError):
                    pass
            return np.frombuffer(raw, dtype=np.float32).astype(np.float64).tolist()
        return [float(value) for value in json.loads(payload)]

    @staticmethod
    def cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        left_array = np.asarray(left, dtype=np.float32)
        right_array = np.asarray(right, dtype=np.float32)
        left_norm = float(np.linalg.norm(left_array))
        right_norm = float(np.linalg.norm(right_array))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return float(left_array @ right_array) / (left_norm * right_norm)

    @staticmethod
    def has_signal(vector: list[float]) -> bool:
        return any(value != 0.0 for value in vector)

    @staticmethod
    def tokenize(text: str) -> list[str]:
        normalized = unicodedata.normalize("NFC", text).casefold()
        return TOKEN_RE.findall(normalized)


class TokenHashEmbeddingService(BaseEmbeddingService):
    """Deterministic local embedding placeholder for development and fallback."""

    provider_name = "token-hash-v1"

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def embed_text(self, text: str) -> list[float]:
        tokens = self.tokenize(text)
        if not tokens:
            return [0.0] * self.dimensions

        vector = [0.0] * self.dimensions
        for token in tokens:
            digest = sha256(token.encode("utf-8")).digest()
            primary_index = int.from_bytes(digest[:4], "big") % self.dimensions
            primary_sign = 1.0 if digest[4] % 2 == 0 else -1.0
            secondary_index = int.from_bytes(digest[5:9], "big") % self.dimensions
            secondary_sign = 1.0 if digest[9] % 2 == 0 else -1.0

            vector[primary_index] += primary_sign
            vector[secondary_index] += secondary_sign * 0.5

        return self._normalize(vector)

    @staticmethod
    def _normalize(vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]


class SentenceTransformerEmbeddingService(BaseEmbeddingService):
    def __init__(self, model_name: str, device: str = "cpu", local_files_only: bool = False) -> None:
        self.show_progress = get_settings().EMBEDDING_SHOW_PROGRESS
        if not self.show_progress:
            os.environ.setdefault("TQDM_DISABLE", "1")
            os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is not installed. Install optional embedding dependencies first."
            ) from exc

        self.model_name = str(Path(model_name)) if Path(model_name).exists() else model_name
        self.device = device
        self.provider_name = f"sentence-transformers:{model_name}"
        self.local_files_only = local_files_only
        self._encode_lock = threading.Lock()
        self.model = SentenceTransformer(
            self.model_name,
            device=device,
            local_files_only=local_files_only,
        )

    def embed_text(self, text: str) -> list[float]:
        return self.embed_document(text)

    def embed_query(self, text: str) -> list[float]:
        normalized = self._normalize_input(text)
        if not normalized:
            return []
        return list(self._embed_query_cached(normalized))

    def embed_document(self, text: str) -> list[float]:
        normalized = self._normalize_input(text)
        if not normalized:
            return []
        return self._encode(normalized, role="document")

    @lru_cache(maxsize=128)
    def _embed_query_cached(self, normalized: str) -> tuple[float, ...]:
        return tuple(self._encode(normalized, role="query"))

    def _encode(self, normalized: str, *, role: str) -> list[float]:
        encoder = self.model.encode_query if role == "query" else self.model.encode_document
        with self._encode_lock:
            vector = encoder(
                normalized,
                normalize_embeddings=True,
                show_progress_bar=self.show_progress,
            )
        return [float(value) for value in vector.tolist()]

    @staticmethod
    def _normalize_input(text: str) -> str:
        normalized = unicodedata.normalize("NFC", text).strip()
        return normalized


_EMBEDDING_SERVICE_LOCK = threading.Lock()


def build_embedding_service() -> EmbeddingService:
    with _EMBEDDING_SERVICE_LOCK:
        return _build_embedding_service_cached()


@lru_cache(maxsize=1)
def _build_embedding_service_cached() -> EmbeddingService:
    settings = get_settings()
    provider = settings.EMBEDDING_PROVIDER.strip().casefold()
    if provider in {"sentence-transformer", "sentence-transformers", "hf", "huggingface"}:
        device = resolve_embedding_device(settings.EMBEDDING_DEVICE)
        attempted_devices: list[str] = []
        try:
            attempted_devices.append(device)
            service = SentenceTransformerEmbeddingService(
                model_name=settings.EMBEDDING_MODEL_NAME,
                device=device,
                local_files_only=settings.EMBEDDING_LOCAL_FILES_ONLY,
            )
            logger.info("Loaded embedding provider %s", service.provider_name)
            return service
        except Exception as exc:
            logger.exception("Sentence-transformers could not load on %s.", device)
            if device != "cpu":
                try:
                    attempted_devices.append("cpu")
                    service = SentenceTransformerEmbeddingService(
                        model_name=settings.EMBEDDING_MODEL_NAME,
                        device="cpu",
                        local_files_only=settings.EMBEDDING_LOCAL_FILES_ONLY,
                    )
                    logger.info("Loaded embedding provider %s on CPU after %s failed.", service.provider_name, device)
                    return service
                except Exception:
                    logger.exception("Sentence-transformers CPU fallback also failed.")
            logger.warning(
                "Falling back to token-hash embeddings after trying devices: %s",
                ", ".join(attempted_devices),
            )

    service = TokenHashEmbeddingService()
    logger.info("Using embedding provider %s", service.provider_name)
    return service
