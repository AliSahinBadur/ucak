from __future__ import annotations

import os
from pathlib import Path

from .branding import get_app_brand, normalize_app_variant


BASE_DIR = Path(__file__).resolve().parent.parent
APP_VARIANT = normalize_app_variant(os.getenv("APP_VARIANT"))
APP_BRAND = get_app_brand(APP_VARIANT)
_variant_data_dir = os.getenv(APP_BRAND.data_dir_env) or os.getenv("APP_DATA_DIR")
DATA_DIR = Path(
    _variant_data_dir
    or BASE_DIR / APP_BRAND.default_data_dir
).expanduser()
DOCUMENTS_DIR = DATA_DIR / "documents"
DATABASE_URL = f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}"


def _repocto_library_roots() -> tuple[Path, ...]:
    configured = [
        Path(item.strip()).expanduser()
        for item in os.getenv("REPOCTO_LIBRARY_ROOTS", "").split(";")
        if item.strip()
    ]
    defaults = [
        DOCUMENTS_DIR,
        BASE_DIR / "data" / "documents",
        Path("V:/RAPORLAR"),
        Path("V:/CAE/Dijital Dönüşüm Çalışmaları"),
    ]
    unique: list[Path] = []
    for root in [*defaults, *configured]:
        if root not in unique:
            unique.append(root)
    return tuple(unique)


REPOCTO_LIBRARY_ROOTS = _repocto_library_roots()
APP_AUTH_ENABLED = False
APP_USERS_RAW = ""
APP_SESSION_SECRET = ""


def _env_bool(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().casefold() in {"1", "true", "yes", "on"}


APP_AUTH_ENABLED = _env_bool("APP_AUTH_ENABLED", default=False)
APP_USERS_RAW = os.getenv("APP_USERS", "")
APP_SESSION_SECRET = os.getenv("APP_SESSION_SECRET", "")
APP_AUTH_COOKIE_NAME = os.getenv("APP_AUTH_COOKIE_NAME", APP_BRAND.default_cookie_name)


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


def _default_embedding_device() -> str:
    try:
        import torch
    except Exception:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", _default_embedding_device())
EMBEDDING_LOCAL_FILES_ONLY = _env_bool("EMBEDDING_LOCAL_FILES_ONLY", default=False)
EMBEDDING_SHOW_PROGRESS = _env_bool("EMBEDDING_SHOW_PROGRESS", default=False)

OCR_ENABLED = _env_bool("OCR_ENABLED", default=True)
OCR_LANGUAGES = os.getenv("OCR_LANGUAGES", "tur+eng").strip() or "tur+eng"
OCR_DPI = max(150, min(int(os.getenv("OCR_DPI", "250")), 400))
OCR_MIN_TEXT_CHARACTERS = max(20, int(os.getenv("OCR_MIN_TEXT_CHARACTERS", "100")))
OCR_TESSDATA_DIR = os.getenv("OCR_TESSDATA_DIR", os.getenv("TESSDATA_PREFIX", "")).strip()
OCR_TESSERACT_CMD = os.getenv("OCR_TESSERACT_CMD", os.getenv("TESSERACT_CMD", "")).strip()

LLM_ENABLED = _env_bool("LLM_ENABLED", default=False)
LLM_BACKEND = os.getenv("LLM_BACKEND", "disabled").strip().casefold()
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "")
LLM_MODEL_PATH = os.getenv("LLM_MODEL_PATH", "")
LLM_MAX_CONTEXT_TOKENS = int(os.getenv("LLM_MAX_CONTEXT_TOKENS", "4096"))
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
LLM_ANSWER_ENABLED = _env_bool("LLM_ANSWER_ENABLED", default=False)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_CHAT_LLM_MODEL_NAME = (
    os.getenv("CHAT_LLM_MODEL_NAME")
    or os.getenv("LLM_MODEL_NAME")
    or "qwen2.5:3b"
).strip() or "qwen2.5:3b"

# CATIA V5 mass / center-of-gravity skill is visible by default with the
# synthetic source. Real COM access still requires CATIA_SKILL_SOURCE=catia.
CATIA_SKILL_ENABLED = _env_bool("CATIA_SKILL_ENABLED", default=True)
CATIA_SKILL_SOURCE = os.getenv("CATIA_SKILL_SOURCE", "fake").strip().casefold()
if CATIA_SKILL_SOURCE not in {"fake", "catia"}:
    CATIA_SKILL_SOURCE = "fake"
CATIA_SKILL_MODEL_NAME = (
    os.getenv("CATIA_SKILL_MODEL_NAME", "").strip()
    or DEFAULT_CHAT_LLM_MODEL_NAME
)
CATIA_SKILL_WORKSPACE_ROOT = Path(
    os.getenv("CATIA_SKILL_WORKSPACE_ROOT", "").strip() or DATA_DIR / "catia_skill"
).expanduser()
CATIA_SKILL_LLM_TIMEOUT_SECONDS = max(10.0, float(os.getenv("CATIA_SKILL_LLM_TIMEOUT_SECONDS", "600")))
CATIA_SKILL_CMC_TIMEOUT_SECONDS = max(10.0, float(os.getenv("CATIA_SKILL_CMC_TIMEOUT_SECONDS", "900")))
CATIA_SKILL_MAX_STEPS = max(1, min(int(os.getenv("CATIA_SKILL_MAX_STEPS", "12")), 32))
CATIA_SKILL_MAX_NUDGES = max(0, min(int(os.getenv("CATIA_SKILL_MAX_NUDGES", "3")), 8))

CHAT_LLM_ENABLED = _env_bool("CHAT_LLM_ENABLED", default=True)
CHAT_LLM_BACKEND = os.getenv("CHAT_LLM_BACKEND", "ollama").strip().casefold()
CHAT_LLM_MODEL_NAME = DEFAULT_CHAT_LLM_MODEL_NAME
CHAT_LLM_TIMEOUT_SECONDS = float(os.getenv("CHAT_LLM_TIMEOUT_SECONDS", os.getenv("LLM_TIMEOUT_SECONDS", "45")))

REPORT_LLM_ENABLED = _env_bool("REPORT_LLM_ENABLED", default=True)
REPORT_LLM_BACKEND = os.getenv("REPORT_LLM_BACKEND", CHAT_LLM_BACKEND).strip().casefold()
REPORT_LLM_MODEL_NAME = os.getenv("REPORT_LLM_MODEL_NAME", CHAT_LLM_MODEL_NAME)
REPORT_LLM_TIMEOUT_SECONDS = float(os.getenv("REPORT_LLM_TIMEOUT_SECONDS", os.getenv("CHAT_LLM_TIMEOUT_SECONDS", "45")))

RERANKER_ENABLED = _env_bool("RERANKER_ENABLED", default=False)
RERANKER_BACKEND = os.getenv("RERANKER_BACKEND", "disabled").strip().casefold()
RERANKER_MODEL_PATH = os.getenv("RERANKER_MODEL_PATH", "")
