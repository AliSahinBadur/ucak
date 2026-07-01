from __future__ import annotations

import unicodedata

from pydantic import BaseModel, Field

from .llm_provider import LLMProvider, build_llm_provider


class MetadataFilters(BaseModel):
    year_from: int | None = None
    year_to: int | None = None
    author: str | None = None
    software: str | None = None
    analysis_type: str | None = None


class QueryUnderstanding(BaseModel):
    intent: str = "search"
    normalized_query: str
    expanded_queries: list[str] = Field(default_factory=list)
    metadata_filters: MetadataFilters = Field(default_factory=MetadataFilters)
    subqueries: list[str] = Field(default_factory=list)
    enhancement_used: bool = False
    fallback_reason: str | None = None


class QueryUnderstandingService:
    TECHNICAL_GLOSSARY = {
        "titresim": ["vibration", "NVH"],
        "yorulma": ["fatigue", "durability"],
        "dayanim": ["durability", "strength"],
        "gerilme": ["stress"],
        "sinir sartlari": ["boundary conditions"],
        "civata on yuku": ["bolt preload"],
        "dogal frekans": ["natural frequency"],
        "guvenlik": ["safety", "SAFE"],
        "emniyet": ["safety", "SAFE"],
        "termal": ["thermal", "CFD", "TASE"],
    }

    def __init__(self, llm_provider: LLMProvider | None = None) -> None:
        self.llm_provider = llm_provider or build_llm_provider()

    def understand(self, query: str) -> QueryUnderstanding:
        normalized = " ".join(query.split())
        fallback = self._deterministic_understanding(normalized)
        if not normalized:
            return fallback
        if not self.llm_provider.is_available():
            fallback.fallback_reason = "llm_disabled"
            return fallback

        try:
            enhanced = self.llm_provider.generate_json(
                self._query_understanding_prompt(normalized),
                QueryUnderstanding,
            )
        except Exception as exc:
            fallback.fallback_reason = f"llm_failed:{exc.__class__.__name__}"
            return fallback

        enhanced.normalized_query = enhanced.normalized_query or normalized
        enhanced.expanded_queries = self._dedupe_queries([normalized, *enhanced.expanded_queries])
        enhanced.subqueries = enhanced.subqueries[:3]
        enhanced.enhancement_used = True
        return enhanced

    def _deterministic_understanding(self, normalized: str) -> QueryUnderstanding:
        expanded = [normalized] if normalized else []
        lowered = self._fold_text(normalized)
        for term, translations in self.TECHNICAL_GLOSSARY.items():
            if term in lowered:
                expanded.extend(f"{normalized} {translation}" for translation in translations)

        return QueryUnderstanding(
            intent=self._detect_intent(lowered),
            normalized_query=normalized,
            expanded_queries=self._dedupe_queries(expanded),
            metadata_filters=self._metadata_filters(lowered),
            subqueries=[],
            enhancement_used=False,
        )

    @staticmethod
    def _detect_intent(lowered_query: str) -> str:
        question_words = ("nedir", "nelerdir", "hangi", "kac", "neden", "nasil")
        if any(word in lowered_query for word in question_words):
            return "question_answer"
        return "search"

    @staticmethod
    def _metadata_filters(lowered_query: str) -> MetadataFilters:
        filters = MetadataFilters()
        for year in ("2021", "2022", "2023", "2024", "2025", "2026"):
            if year in lowered_query:
                filters.year_from = int(year)
                filters.year_to = int(year)
                break
        analysis_aliases = {
            "nvh": "NVH",
            "titresim": "NVH",
            "safety": "SAFETY",
            "safe": "SAFETY",
            "guvenlik": "SAFETY",
            "emniyet": "SAFETY",
            "durability": "DURABILITY",
            "dayanim": "DURABILITY",
            "cfd": "CFD",
            "tase": "TASE",
        }
        for alias, value in analysis_aliases.items():
            if alias in lowered_query:
                filters.analysis_type = value
                break
        for software in ("ansys", "abaqus", "hypermesh", "ncode", "matlab"):
            if software in lowered_query:
                filters.software = software.upper()
                break
        return filters

    @staticmethod
    def _dedupe_queries(queries: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for query in queries:
            cleaned = " ".join(str(query or "").split())
            key = cleaned.casefold()
            if cleaned and key not in seen:
                seen.add(key)
                deduped.append(cleaned)
        return deduped[:4]

    @staticmethod
    def _fold_text(text: str) -> str:
        translated = text.casefold().translate(
            str.maketrans(
                {
                    "\u0131": "i",
                    "\u011f": "g",
                    "\u00fc": "u",
                    "\u015f": "s",
                    "\u00f6": "o",
                    "\u00e7": "c",
                }
            )
        )
        normalized = unicodedata.normalize("NFKD", translated)
        return "".join(char for char in normalized if not unicodedata.combining(char))

    @staticmethod
    def _query_understanding_prompt(query: str) -> str:
        return f"""You are a local engineering report query understanding component.
Return only JSON matching this schema:
{{
  "intent": "search|question_answer|metadata_lookup",
  "normalized_query": "...",
  "expanded_queries": ["..."],
  "metadata_filters": {{
    "year_from": null,
    "year_to": null,
    "author": null,
    "software": null,
    "analysis_type": null
  }},
  "subqueries": []
}}
Do not invent unsupported filters. Keep the original meaning.
User query: {query}
"""
