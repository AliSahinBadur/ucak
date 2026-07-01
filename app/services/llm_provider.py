from __future__ import annotations

from functools import lru_cache
import json
import logging
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from ..config import (
    LLM_BACKEND,
    LLM_ENABLED,
    LLM_MODEL_NAME,
    LLM_TIMEOUT_SECONDS,
)


logger = logging.getLogger(__name__)
SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMProvider(Protocol):
    provider_name: str

    def is_available(self) -> bool:
        ...

    def generate(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> str:
        ...

    def generate_json(self, prompt: str, schema: type[SchemaT]) -> SchemaT:
        ...


class DisabledLLMProvider:
    provider_name = "disabled"

    def is_available(self) -> bool:
        return False

    def generate(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> str:
        raise RuntimeError("LLM provider is disabled.")

    def generate_json(self, prompt: str, schema: type[SchemaT]) -> SchemaT:
        raise RuntimeError("LLM provider is disabled.")


class OllamaLLMProvider:
    def __init__(self, model_name: str, timeout_seconds: float = 30.0) -> None:
        if not model_name:
            raise RuntimeError("LLM_MODEL_NAME is required for Ollama.")
        try:
            import ollama
        except ImportError as exc:
            raise RuntimeError("ollama package is not installed.") from exc

        self._ollama = ollama
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.provider_name = f"ollama:{model_name}"

    def is_available(self) -> bool:
        return True

    def generate(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> str:
        options: dict[str, float | int] = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        response = self._ollama.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            options=options,
        )
        return str(response["message"]["content"])

    def generate_json(self, prompt: str, schema: type[SchemaT]) -> SchemaT:
        raw_text = self.generate(prompt, temperature=0.0)
        try:
            payload = json.loads(_extract_json_object(raw_text))
            return schema.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise RuntimeError("LLM returned invalid JSON.") from exc


def _extract_json_object(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    return stripped


@lru_cache(maxsize=1)
def build_llm_provider() -> LLMProvider:
    if not LLM_ENABLED or LLM_BACKEND in {"", "disabled", "none"}:
        logger.info("LLM provider disabled.")
        return DisabledLLMProvider()

    if LLM_BACKEND == "ollama":
        try:
            provider = OllamaLLMProvider(
                model_name=LLM_MODEL_NAME,
                timeout_seconds=LLM_TIMEOUT_SECONDS,
            )
            logger.info("Loaded LLM provider %s", provider.provider_name)
            return provider
        except Exception:
            logger.exception("LLM provider could not load; continuing with disabled LLM.")
            return DisabledLLMProvider()

    logger.warning("Unsupported LLM_BACKEND=%s; continuing with disabled LLM.", LLM_BACKEND)
    return DisabledLLMProvider()
