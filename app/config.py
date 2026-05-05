from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"
DATABASE_URL = f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}"
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "token-hash")


def _default_embedding_model_name() -> str:
    local_candidates = (
        BASE_DIR / "models" / "Qwen3-Embedding-0.6B",
        BASE_DIR / "models" / "qwen3-embedding-0.6b",
        BASE_DIR / "models" / "Qwen" / "Qwen3-Embedding-0.6B",
    )
    for candidate in local_candidates:
        if candidate.exists():
            return str(candidate)
    return "Qwen/Qwen3-Embedding-0.6B"


EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", _default_embedding_model_name())
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")
EMBEDDING_LOCAL_FILES_ONLY = os.getenv("EMBEDDING_LOCAL_FILES_ONLY", "false").strip().casefold() in {
    "1",
    "true",
    "yes",
    "on",
}
