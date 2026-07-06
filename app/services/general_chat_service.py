from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import logging
from typing import Any

from ..config import (
    CHAT_LLM_BACKEND,
    CHAT_LLM_ENABLED,
    CHAT_LLM_MODEL_NAME,
    CHAT_LLM_TIMEOUT_SECONDS,
)
from .llm_provider import DisabledLLMProvider, LLMProvider, OllamaLLMProvider


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeneralChatResult:
    answer: str
    provider_name: str
    confidence: float


class GeneralChatService:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or _build_chat_provider()

    def answer(self, message: str, history: list[dict[str, Any]]) -> GeneralChatResult | None:
        if not self.provider.is_available():
            return None

        prompt = self._build_prompt(message, history)
        try:
            answer = self.provider.generate(prompt, max_tokens=240, temperature=0.25).strip()
        except Exception:
            logger.exception("General chat LLM failed.")
            return None
        if not answer:
            return None
        return GeneralChatResult(
            answer=answer,
            provider_name=f"chat-llm:{self.provider.provider_name}",
            confidence=0.95,
        )

    @staticmethod
    def _build_prompt(message: str, history: list[dict[str, Any]]) -> str:
        history_lines = []
        for item in history[-6:]:
            role = "Kullanici" if item.get("role") == "user" else "Big Agent"
            content = " ".join(str(item.get("content", "")).split())
            if content:
                history_lines.append(f"{role}: {content}")
        joined_history = "\n".join(history_lines) if history_lines else "Yok."
        return f"""Sen Big Agent uygulamasinin genel sohbet modusun.
Turkce cevap ver. Kisa, net, dogal ve yardimci ol.
Kendini Big Agent icindeki arac test raporu asistani olarak tanit.
Basit sohbet, matematik ve genel yardim sorularini direkt cevapla.
Insan oldugunu iddia etme; kimligini sorarlarsa yapay zeka destekli bir asistan oldugunu rahat bir dille soyle.
Rapor, test, analiz, katalog veya kaynak gerektiren teknik sorularda cevap verebilirsin; kaynakli cevap gerekiyorsa rapor modunu veya otomatik modu kullanabildigini belirt.
Bilmedigin bir seyi uydurma.

Onceki sohbet:
{joined_history}

Kullanici:
{message}

Cevap:"""


@lru_cache(maxsize=1)
def _build_chat_provider() -> LLMProvider:
    if not CHAT_LLM_ENABLED or CHAT_LLM_BACKEND in {"", "disabled", "none"}:
        logger.info("General chat LLM disabled.")
        return DisabledLLMProvider()
    if CHAT_LLM_BACKEND == "ollama":
        try:
            return OllamaLLMProvider(
                model_name=CHAT_LLM_MODEL_NAME,
                timeout_seconds=CHAT_LLM_TIMEOUT_SECONDS,
            )
        except Exception:
            logger.exception("General chat Ollama provider could not load.")
            return DisabledLLMProvider()
    logger.warning("Unsupported CHAT_LLM_BACKEND=%s; general chat disabled.", CHAT_LLM_BACKEND)
    return DisabledLLMProvider()
