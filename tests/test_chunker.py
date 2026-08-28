from __future__ import annotations

import pytest

from app.processing.chunker import chunk_sections
from app.schemas import CleanSection


def _section(page_number: int, text: str, title: str | None = None) -> CleanSection:
    return CleanSection(page_number=page_number, raw_text=text, clean_text=text, section_title=title)


def test_chunk_sections_rejects_overlap_not_smaller_than_target() -> None:
    with pytest.raises(ValueError):
        chunk_sections([_section(1, "a b c")], target_words=10, overlap_words=10)


def test_chunk_sections_empty_input_returns_empty_list() -> None:
    assert chunk_sections([]) == []


def test_chunk_sections_skips_sections_with_no_words() -> None:
    assert chunk_sections([_section(1, "   ")]) == []


def test_chunk_sections_single_short_section_is_one_chunk() -> None:
    chunks = chunk_sections([_section(1, "one two three", title="Intro")], target_words=10, overlap_words=2)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_text == "one two three"
    assert chunk.chunk_order == 1
    assert chunk.page_start == chunk.page_end == 1
    assert chunk.section_title == "Intro"


def test_chunk_sections_splits_long_section_with_overlap() -> None:
    words = [f"w{i}" for i in range(25)]
    section = _section(1, " ".join(words))

    chunks = chunk_sections([section], target_words=10, overlap_words=3)

    assert [c.chunk_text.split() for c in chunks] == [
        words[0:10],
        words[7:17],
        words[14:24],
        words[21:25],
    ]
    assert [c.chunk_order for c in chunks] == [1, 2, 3, 4]


def test_chunk_sections_stops_once_a_window_reaches_the_end_without_a_redundant_tail_chunk() -> None:
    words = [f"w{i}" for i in range(12)]
    section = _section(1, " ".join(words))

    chunks = chunk_sections([section], target_words=10, overlap_words=3)

    # once a window's end reaches len(words), the loop must break rather than
    # advance start (= end - overlap) and emit a near-duplicate final chunk
    assert [c.chunk_text.split() for c in chunks] == [words[0:10], words[7:12]]


def test_chunk_sections_preserves_order_across_multiple_sections() -> None:
    sections = [_section(1, "a b c"), _section(2, "d e f")]

    chunks = chunk_sections(sections, target_words=10, overlap_words=2)

    assert [c.chunk_order for c in chunks] == [1, 2]
    assert [c.page_start for c in chunks] == [1, 2]
