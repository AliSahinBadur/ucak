from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"
DATABASE_URL = f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}"


def _env_bool(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().casefold() in {"1", "true", "yes", "on"}


def _default_embedding_model_name() -> str:
    local_candidates = (
        BASE_DIR / "models" / "Qwen3-Embedding-4B",
        BASE_DIR / "models" / "qwen3-embedding-4b",
        BASE_DIR / "models" / "Qwen3-Embedding-0.6B",
        BASE_DIR / "models" / "qwen3-embedding-0.6b",
        BASE_DIR / "models" / "Qwen" / "Qwen3-Embedding-4B",
        BASE_DIR / "models" / "Qwen" / "Qwen3-Embedding-0.6B",
    )
    for candidate in local_candidates:
        if candidate.exists():
            return str(candidate)
    return "Qwen/Qwen3-Embedding-0.6B"


EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_PATH",
    os.getenv("EMBEDDING_MODEL_NAME", _default_embedding_model_name()),
)


def _default_embedding_provider() -> str:
    return "sentence-transformers" if Path(EMBEDDING_MODEL_NAME).exists() else "token-hash"


EMBEDDING_PROVIDER = os.getenv("EMBEDDING_BACKEND", os.getenv("EMBEDDING_PROVIDER", _default_embedding_provider()))
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")
EMBEDDING_LOCAL_FILES_ONLY = _env_bool("EMBEDDING_LOCAL_FILES_ONLY", default=False)

LLM_ENABLED = _env_bool("LLM_ENABLED", default=False)
LLM_BACKEND = os.getenv("LLM_BACKEND", "disabled").strip().casefold()
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "")
LLM_MODEL_PATH = os.getenv("LLM_MODEL_PATH", "")
LLM_MAX_CONTEXT_TOKENS = int(os.getenv("LLM_MAX_CONTEXT_TOKENS", "4096"))
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
LLM_ANSWER_ENABLED = _env_bool("LLM_ANSWER_ENABLED", default=False)

RERANKER_ENABLED = _env_bool("RERANKER_ENABLED", default=False)
RERANKER_BACKEND = os.getenv("RERANKER_BACKEND", "disabled").strip().casefold()
RERANKER_MODEL_PATH = os.getenv("RERANKER_MODEL_PATH", "")
