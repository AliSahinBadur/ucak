from __future__ import annotations

from app.processing.text_cleaner import clean_text, normalize_sections, remove_repeated_page_artifacts
from app.schemas import ParsedSection


def test_clean_text_preserves_turkish_characters() -> None:
    assert clean_text("Türkçe şıöüğ ÇĞİÖŞÜ metin") == "Türkçe şıöüğ ÇĞİÖŞÜ metin"


def test_clean_text_collapses_inline_whitespace_but_keeps_linebreaks() -> None:
    assert clean_text("line one\n\nline   two\t\tthree") == "line one\n\nline two three"


def test_clean_text_collapses_three_or_more_blank_lines() -> None:
    assert clean_text("a\n\n\n\n\nb") == "a\n\nb"


def test_clean_text_normalizes_crlf_and_strips_outer_whitespace() -> None:
    assert clean_text("  \r\n a \r\n b \r\n  ") == "a\nb"


def test_remove_repeated_page_artifacts_strips_lines_on_at_least_half_the_pages() -> None:
    pages = [
        "Header\nPage one body",
        "Header\nPage two body",
        "Page three body",
    ]

    cleaned = remove_repeated_page_artifacts(pages)

    assert cleaned == ["Page one body", "Page two body", "Page three body"]


def test_remove_repeated_page_artifacts_keeps_lines_below_the_repetition_threshold() -> None:
    pages = ["Unique one", "Unique two", "Unique three"]

    cleaned = remove_repeated_page_artifacts(pages)

    assert cleaned == pages


def test_remove_repeated_page_artifacts_handles_single_page_without_removal() -> None:
    assert remove_repeated_page_artifacts(["Only Page"]) == ["Only Page"]


def test_remove_repeated_page_artifacts_ignores_lines_outside_length_bounds() -> None:
    short = "ab"
    long_line = "x" * 200
    pages = [f"{short}\n{long_line}\nbody one", f"{short}\n{long_line}\nbody two"]

    cleaned = remove_repeated_page_artifacts(pages)

    # both the too-short and too-long repeated lines survive; only in-range repeats are stripped
    assert cleaned[0] == f"{short}\n{long_line}\nbody one"
    assert cleaned[1] == f"{short}\n{long_line}\nbody two"


def test_normalize_sections_drops_sections_that_clean_to_empty() -> None:
    sections = [
        ParsedSection(page_number=1, raw_text="   \n  ", section_title=None),
        ParsedSection(page_number=2, raw_text="Real content", section_title="Title"),
    ]

    cleaned = normalize_sections(sections)

    assert len(cleaned) == 1
    assert cleaned[0].page_number == 2
    assert cleaned[0].clean_text == "Real content"
    assert cleaned[0].section_title == "Title"
