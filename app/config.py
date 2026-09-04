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

    OCR_ENABLED: bool = True
    OCR_LANGUAGES: str = "tur+eng"
    OCR_DPI: int = 250
    OCR_MIN_TEXT_CHARACTERS: int = 100
    OCR_TESSDATA_DIR: str = Field(
        default="", validation_alias=AliasChoices("OCR_TESSDATA_DIR", "TESSDATA_PREFIX")
    )
    OCR_TESSERACT_CMD: str = Field(
        default="", validation_alias=AliasChoices("OCR_TESSERACT_CMD", "TESSERACT_CMD")
    )

    @field_validator("OCR_LANGUAGES", mode="after")
    @classmethod
    def _default_ocr_languages(cls, value: str) -> str:
        return value.strip() or "tur+eng"

    @field_validator("OCR_DPI", mode="after")
    @classmethod
    def _clamp_ocr_dpi(cls, value: int) -> int:
        return max(150, min(value, 400))

    @field_validator("OCR_MIN_TEXT_CHARACTERS", mode="after")
    @classmethod
    def _clamp_ocr_min_text_characters(cls, value: int) -> int:
        return max(20, value)

    @field_validator("OCR_TESSDATA_DIR", "OCR_TESSERACT_CMD", mode="after")
    @classmethod
    def _strip_ocr_paths(cls, value: str) -> str:
        return value.strip()

    REPOCTO_LIBRARY_ROOTS_RAW: str = Field(
        default="", validation_alias="REPOCTO_LIBRARY_ROOTS"
    )

    # CATIA kütle/CG skill'i (skill/catia-mass-cg.skill). Kapalı başlar:
    # CATIA'sı olan mühendis kendi makinesinde açıkça açar. Kaynak varsayılanı
    # "fake" — gerçek CATIA COM bağlantısı için bilinçli olarak "catia" yapılır;
    # kaynak seçimi oturum/istek bazında modele bırakılmaz (SKILL harness).
    CATIA_SKILL_ENABLED: bool = True
    CATIA_SKILL_SOURCE: str = "fake"
    CATIA_SKILL_MODEL_NAME: str = "qwen3:4b-instruct"
    CATIA_SKILL_LLM_TIMEOUT_SECONDS: float = 600.0
    CATIA_SKILL_CMC_TIMEOUT_SECONDS: float = 900.0
    CATIA_SKILL_MAX_STEPS: int = 12
    CATIA_SKILL_MAX_NUDGES: int = 3
    CATIA_SKILL_WORKSPACE_ROOT_RAW: str = Field(
        default="", validation_alias="CATIA_SKILL_WORKSPACE_ROOT"
    )
    # Uçlar varsayılan olarak her istemciye açık. Ölçüm her hâlükârda sunucunun
    # CATIA'sında çalışır, bu yüzden LAN'daki mühendis de aynı makineyi
    # kullanmış olur; istemcinin IP'si bunu değiştirmez. Erişimi daraltmak
    # isteyen kurulum buraya bir istemci listesi yazar (";" ya da "," ile
    # ayrılmış); "local" / "localhost" loopback'in tüm yazımlarını kapsar.
    CATIA_SKILL_ALLOWED_CLIENTS_RAW: str = Field(
        default="", validation_alias="CATIA_SKILL_ALLOWED_CLIENTS"
    )

    @field_validator("CATIA_SKILL_SOURCE", mode="after")
    @classmethod
    def _normalize_catia_source(cls, value: str) -> str:
        normalized = value.strip().casefold()
        return normalized if normalized in {"fake", "catia"} else "fake"

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
        "OCR_ENABLED",
        "CATIA_SKILL_ENABLED",
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
    def REPOCTO_LIBRARY_ROOTS(self) -> tuple[Path, ...]:
        configured = [
            Path(item.strip()).expanduser()
            for item in self.REPOCTO_LIBRARY_ROOTS_RAW.split(";")
            if item.strip()
        ]
        defaults = [
            self.DOCUMENTS_DIR,
            BASE_DIR / "data" / "documents",
            Path("V:/RAPORLAR"),
            Path("V:/CAE/Dijital Dönüşüm Çalışmaları"),
        ]
        unique: list[Path] = []
        for root in [*defaults, *configured]:
            if root not in unique:
                unique.append(root)
        return tuple(unique)

    @property
    def CATIA_SKILL_ALLOWED_CLIENTS(self) -> tuple[str, ...]:
        """Boş demet: kısıtlama yok, her istemci geçer."""
        hosts: list[str] = []
        for part in self.CATIA_SKILL_ALLOWED_CLIENTS_RAW.replace(",", ";").split(";"):
            token = part.strip().casefold()
            if not token:
                continue
            # "localhost" yazan da "local" yazanla aynı şeyi kastediyor;
            # tek bir işarete indiriyoruz ki çağıran taraf loopback'in
            # yazımlarını ("127.0.0.1", "::1") tek yerde bilsin.
            token = "local" if token == "localhost" else token
            if token not in hosts:
                hosts.append(token)
        return tuple(hosts)

    @property
    def CATIA_SKILL_WORKSPACE_ROOT(self) -> Path:
        if self.CATIA_SKILL_WORKSPACE_ROOT_RAW.strip():
            return Path(self.CATIA_SKILL_WORKSPACE_ROOT_RAW.strip()).expanduser()
        return self.DATA_DIR / "catia_skill"

    @property
    def APP_BRAND(self) -> AppBrand:
        return get_app_brand(self.APP_VARIANT)


@lru_cache
def get_settings() -> Settings:
    return Settings()
