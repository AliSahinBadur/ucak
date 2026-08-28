from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .branding import AppBrand, get_app_brand, normalize_app_variant


BASE_DIR = Path(__file__).resolve().parent.parent

_TRUE_VALUES = {"1", "true", "yes", "on"}


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


def resolve_embedding_device(device: str) -> str:
    """Resolve 'auto' to a concrete torch device, importing torch lazily.

    Kept out of Settings so constructing/collecting Settings (e.g. under pytest)
    never pays for a torch import or a CUDA probe.
    """
    if device != "auto":
        return device
    try:
        import torch
    except Exception:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATA_DIR: Path = Field(default_factory=lambda: BASE_DIR / "data", validation_alias="BIG_AGENT_DATA_DIR")

    @field_validator("DATA_DIR", mode="after")
    @classmethod
    def _expand_data_dir(cls, value: Path) -> Path:
        return value.expanduser()

    APP_VARIANT: str = "big_agent"

    @field_validator("APP_VARIANT", mode="after")
    @classmethod
    def _normalize_app_variant(cls, value: str) -> str:
        return normalize_app_variant(value)

    APP_AUTH_ENABLED: bool = False
    APP_USERS_RAW: str = Field(default="", validation_alias="APP_USERS")
    APP_SESSION_SECRET: str = ""
    APP_AUTH_COOKIE_NAME: str = "big_agent_session"

    EMBEDDING_MODEL_NAME: str = Field(
        default="", validation_alias=AliasChoices("EMBEDDING_MODEL_PATH", "EMBEDDING_MODEL_NAME")
    )
    EMBEDDING_PROVIDER: str = Field(
        default="", validation_alias=AliasChoices("EMBEDDING_BACKEND", "EMBEDDING_PROVIDER")
    )
    EMBEDDING_DEVICE: str = "auto"
    EMBEDDING_LOCAL_FILES_ONLY: bool = False
    EMBEDDING_SHOW_PROGRESS: bool = False

    LLM_ENABLED: bool = False
    LLM_BACKEND: str = "disabled"
    LLM_MODEL_NAME: str = ""
    LLM_MODEL_PATH: str = ""
    LLM_MAX_CONTEXT_TOKENS: int = 4096
    LLM_TIMEOUT_SECONDS: float = 30.0
    LLM_ANSWER_ENABLED: bool = False
    OLLAMA_HOST: str = "http://127.0.0.1:11434"

    CHAT_LLM_ENABLED: bool = True
    CHAT_LLM_BACKEND: str = "ollama"
    CHAT_LLM_MODEL_NAME: str = Field(
        default="qwen2.5:3b", validation_alias=AliasChoices("CHAT_LLM_MODEL_NAME", "LLM_MODEL_NAME")
    )
    CHAT_LLM_TIMEOUT_SECONDS: float = Field(
        default=45.0, validation_alias=AliasChoices("CHAT_LLM_TIMEOUT_SECONDS", "LLM_TIMEOUT_SECONDS")
    )

    REPORT_LLM_ENABLED: bool = True
    # Each REPORT_LLM_* falls back through CHAT_LLM_* to the base LLM_* value,
    # then to its own static default, via pydantic-settings' AliasChoices (which
    # resolves an alias naming a sibling field against that field's fully-resolved
    # value, not just raw env-var presence). Note: the pre-migration config.py had
    # REPORT_LLM_TIMEOUT_SECONDS fall back only one level (to a raw getenv of
    # CHAT_LLM_TIMEOUT_SECONDS, not cascading to LLM_TIMEOUT_SECONDS) while
    # REPORT_LLM_BACKEND/REPORT_LLM_MODEL_NAME cascaded fully — an inconsistency
    # that looked like an oversight rather than an intentional difference; this
    # migration makes all three cascade the same way.
    REPORT_LLM_BACKEND: str = Field(
        default="ollama", validation_alias=AliasChoices("REPORT_LLM_BACKEND", "CHAT_LLM_BACKEND")
    )
    REPORT_LLM_MODEL_NAME: str = Field(
        default="qwen2.5:3b",
        validation_alias=AliasChoices("REPORT_LLM_MODEL_NAME", "CHAT_LLM_MODEL_NAME", "LLM_MODEL_NAME"),
    )
    REPORT_LLM_TIMEOUT_SECONDS: float = Field(
        default=45.0, validation_alias=AliasChoices("REPORT_LLM_TIMEOUT_SECONDS", "CHAT_LLM_TIMEOUT_SECONDS")
    )

    RERANKER_ENABLED: bool = False
    RERANKER_BACKEND: str = "disabled"
    RERANKER_MODEL_PATH: str = ""

    CATALOG_SEARCH_ROOTS_RAW: str = Field(
        default=r"\\isufile02\argevalidasyon$\RAPORLAR;V:/RAPORLAR;V:/",
        validation_alias="CATALOG_SEARCH_ROOTS",
    )

    @field_validator(
        "APP_AUTH_ENABLED",
        "EMBEDDING_LOCAL_FILES_ONLY",
        "EMBEDDING_SHOW_PROGRESS",
        "LLM_ENABLED",
        "LLM_ANSWER_ENABLED",
        "CHAT_LLM_ENABLED",
        "REPORT_LLM_ENABLED",
        "RERANKER_ENABLED",
        mode="before",
    )
    @classmethod
    def _parse_loose_bool(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return value.strip().casefold() in _TRUE_VALUES

    @field_validator("LLM_BACKEND", "CHAT_LLM_BACKEND", "REPORT_LLM_BACKEND", "RERANKER_BACKEND", mode="after")
    @classmethod
    def _fold_backend_name(cls, value: str) -> str:
        return value.strip().casefold()

    @field_validator("OLLAMA_HOST", mode="after")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @model_validator(mode="after")
    def _resolve_dependent_defaults(self) -> "Settings":
        # EMBEDDING_PROVIDER's default genuinely depends on the *resolved*
        # EMBEDDING_MODEL_NAME (a filesystem check), so it can't be expressed
        # as a static AliasChoices default like the REPORT_LLM_* fields above.
        if not self.EMBEDDING_MODEL_NAME:
            self.EMBEDDING_MODEL_NAME = _default_embedding_model_name()
        if not self.EMBEDDING_PROVIDER:
            self.EMBEDDING_PROVIDER = (
                "sentence-transformers" if Path(self.EMBEDDING_MODEL_NAME).exists() else "token-hash"
            )
        return self

    @property
    def DOCUMENTS_DIR(self) -> Path:
        return self.DATA_DIR / "documents"

    @property
    def DATABASE_URL(self) -> str:
        return f"sqlite:///{(self.DATA_DIR / 'app.db').as_posix()}"

    @property
    def CATALOG_SEARCH_ROOTS(self) -> tuple[str, ...]:
        return tuple(root for root in (part.strip() for part in self.CATALOG_SEARCH_ROOTS_RAW.split(";")) if root)

    @property
    def APP_BRAND(self) -> AppBrand:
        return get_app_brand(self.APP_VARIANT)


@lru_cache
def get_settings() -> Settings:
    return Settings()
