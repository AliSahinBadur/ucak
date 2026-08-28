from __future__ import annotations

from app.text.normalize import compact_search_text, normalize_search_text, search_words, tokenize


def test_normalize_search_text_folds_lowercase_turkish_characters() -> None:
    assert normalize_search_text("ığüşöç") == "igusoc"


def test_normalize_search_text_folds_uppercase_turkish_characters() -> None:
    assert normalize_search_text("İĞÜŞÖÇ") == "igusoc"


def test_normalize_search_text_casefolds_plain_ascii() -> None:
    assert normalize_search_text("KALIBRASYON") == "kalibrasyon"


def test_normalize_search_text_strips_combining_marks_from_other_diacritics() -> None:
    assert normalize_search_text("café") == "cafe"


def test_normalize_search_text_handles_empty_and_none() -> None:
    assert normalize_search_text("") == ""
    assert normalize_search_text(None) == ""  # type: ignore[arg-type]


def test_compact_search_text_removes_non_alnum() -> None:
    assert compact_search_text("2024-abc def.ghi") == "2024abcdefghi"


def test_compact_search_text_drops_anything_not_already_lowercase_or_digit() -> None:
    # compact_search_text does not casefold; it is meant to run on already-folded
    # text, so uppercase characters are stripped rather than lowercased
    assert compact_search_text("abc123 XYZ") == "abc123"


def test_tokenize_splits_on_non_word_characters_and_casefolds() -> None:
    assert tokenize("Rapor No: 2024-ABC/12") == ["rapor", "no", "2024", "abc", "12"]


def test_tokenize_preserves_turkish_letters_as_word_characters() -> None:
    assert tokenize("Doğrulama Şüphesi") == ["doğrulama", "şüphesi"]


def test_search_words_splits_already_normalized_text() -> None:
    assert search_words("igusoc metin 2024") == ["igusoc", "metin", "2024"]
