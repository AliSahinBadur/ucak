from __future__ import annotations

from pathlib import Path

from ..schemas import ParsedSection


def parse_pdf(file_path: str | Path) -> list[ParsedSection]:
    """Extract selectable text from a PDF file page by page."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "PDF parsing requires the 'pypdf' package. Install project dependencies first."
        ) from exc

    path = Path(file_path)
    reader = PdfReader(str(path))
    pages: list[ParsedSection] = []

    for index, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        pages.append(
            ParsedSection(
                page_number=index,
                raw_text=raw_text,
                section_title=_detect_section_title(raw_text),
            )
        )

    return pages


def _detect_section_title(text: str) -> str | None:
    for line in text.splitlines():
        candidate = " ".join(line.split())
        if len(candidate) < 4:
            continue
        if candidate.isupper() or candidate.endswith(":"):
            return candidate[:200]
    return None
