from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Iterable

from ..schemas import CleanSection, ParsedSection


WHITESPACE_RE = re.compile(r"[ \t]+")
LINEBREAK_RE = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """Normalize whitespace while preserving readable line breaks and Turkish chars."""
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(WHITESPACE_RE.sub(" ", line).strip() for line in normalized.split("\n"))
    normalized = LINEBREAK_RE.sub("\n\n", normalized)
    return normalized.strip()


def remove_repeated_page_artifacts(texts: Iterable[str]) -> list[str]:
    """Remove lines repeated on many pages, which are often headers/footers."""
    pages = [text for text in texts]
    if len(pages) < 2:
        return [clean_text(text) for text in pages]

    candidates = Counter()
    split_pages = []
    for text in pages:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        split_pages.append(lines)
        for line in set(lines):
            if 3 <= len(line) <= 120:
                candidates[line] += 1

    repeated = {
        line
        for line, count in candidates.items()
        if count >= max(2, len(split_pages) // 2)
    }

    cleaned_pages: list[str] = []
    for lines in split_pages:
        filtered = [line for line in lines if line not in repeated]
        cleaned_pages.append(clean_text("\n".join(filtered)))
    return cleaned_pages


def normalize_sections(sections: list[ParsedSection]) -> list[CleanSection]:
    raw_texts = [section.raw_text for section in sections]
    cleaned_texts = remove_repeated_page_artifacts(raw_texts)

    cleaned_sections: list[CleanSection] = []
    for section, cleaned_text in zip(sections, cleaned_texts, strict=True):
        normalized = clean_text(cleaned_text)
        if not normalized:
            continue
        cleaned_sections.append(
            CleanSection(
                page_number=section.page_number,
                raw_text=section.raw_text,
                clean_text=normalized,
                section_title=section.section_title,
            )
        )
    return cleaned_sections
