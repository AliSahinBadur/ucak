from __future__ import annotations

from ..config import LLM_ANSWER_ENABLED, LLM_MAX_CONTEXT_TOKENS
from .llm_provider import LLMProvider, build_llm_provider


class AnswerGenerationService:
    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm_provider = llm_provider or build_llm_provider()

    def is_available(self) -> bool:
        return LLM_ANSWER_ENABLED and self.llm_provider.is_available()

    def generate_answer(self, question: str, sources: list[dict]) -> str | None:
        if not self.is_available() or not sources:
            return None

        prompt = self._prompt(question, sources)
        answer = self.llm_provider.generate(prompt, max_tokens=220, temperature=0.0).strip()
        if not answer:
            return None
        return answer

    @staticmethod
    def _prompt(question: str, sources: list[dict]) -> str:
        contexts = []
        budget = max(1800, LLM_MAX_CONTEXT_TOKENS * 3)
        used = 0
        for index, source in enumerate(sources[:3], start=1):
            text = " ".join(str(source.get("chunk_text", "")).split())
            if not text:
                continue
            remaining = max(budget - used, 0)
            if remaining <= 0:
                break
            text = text[:remaining]
            used += len(text)
            contexts.append(
                "\n".join(
                    [
                        f"[Kaynak {index}]",
                        f"Belge: {source.get('document_title', '')}",
                        f"Sayfa: {source.get('page_start', '')}-{source.get('page_end', '')}",
                        f"Metin: {text}",
                    ]
                )
            )

        joined_context = "\n\n".join(contexts)
        return f"""Sen bir arac test raporu asistanisin.
Sadece verilen kaynak metinlere dayanarak Turkce cevap ver.
Kaynaklarda cevap yoksa bunu acikca soyle.
Cevabin sonunda kullandigin kaynak numaralarini parantez icinde yaz, ornek: (Kaynak 1, Kaynak 3).
Uydurma, tahmin ekleme, verilen sayisal degerleri degistirme.

Soru:
{question}

Kaynaklar:
{joined_context}

Cevap:"""
