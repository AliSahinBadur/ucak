from __future__ import annotations

import re
import unicodedata

_TURKISH_FOLD_MAP = str.maketrans(
    {
        "ı": "i",
        "ğ": "g",
        "ü": "u",
        "ş": "s",
        "ö": "o",
        "ç": "c",
        "İ": "i",
    }
)


def normalize_search_text(text: str) -> str:
    """Casefold, fold Turkish characters to ASCII, and strip combining marks."""
    translated = str(text or "").casefold().translate(_TURKISH_FOLD_MAP)
    decomposed = unicodedata.normalize("NFKD", translated)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def compact_search_text(text: str) -> str:
    """Keep only lowercase letters and digits, for tight substring matching."""
    return re.sub(r"[^a-z0-9]+", "", text)


def tokenize(text: str) -> list[str]:
    """Split raw text into word tokens after NFC normalization and casefolding."""
    normalized = unicodedata.normalize("NFC", text).casefold()
    return re.findall(r"\w+", normalized, re.UNICODE)


def search_words(text: str) -> list[str]:
    """Split already-normalized text into word tokens."""
    return re.findall(r"\w+", text)
