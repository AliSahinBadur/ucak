from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ParsedSection:
    page_number: int
    raw_text: str
    section_title: str | None = None
    extraction_method: str = "native"
    ocr_attempted: bool = False


@dataclass(slots=True)
class CleanSection:
    page_number: int
    raw_text: str
    clean_text: str
    section_title: str | None = None
    extraction_method: str = "native"
    ocr_attempted: bool = False


@dataclass(slots=True)
class ChunkPayload:
    chunk_text: str
    chunk_order: int
    page_start: int
    page_end: int
    section_title: str | None = None
