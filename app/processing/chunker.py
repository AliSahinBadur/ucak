from __future__ import annotations

from ..schemas import ChunkPayload, CleanSection


def chunk_sections(
    sections: list[CleanSection],
    target_words: int = 650,
    overlap_words: int = 75,
) -> list[ChunkPayload]:
    """Create overlapping chunks from cleaned sections."""
    if target_words <= overlap_words:
        raise ValueError("target_words must be greater than overlap_words")

    chunks: list[ChunkPayload] = []
    chunk_order = 1

    for section in sections:
        words = section.clean_text.split()
        if not words:
            continue

        start = 0
        while start < len(words):
            end = min(start + target_words, len(words))
            chunk_text = " ".join(words[start:end]).strip()
            if chunk_text:
                chunks.append(
                    ChunkPayload(
                        chunk_text=chunk_text,
                        chunk_order=chunk_order,
                        page_start=section.page_number,
                        page_end=section.page_number,
                        section_title=section.section_title,
                    )
                )
                chunk_order += 1

            if end >= len(words):
                break
            start = max(0, end - overlap_words)

    return chunks
