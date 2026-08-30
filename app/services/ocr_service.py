from __future__ import annotations

import logging
import os
from pathlib import Path
import re

from ..config import get_settings
from ..schemas import ParsedSection


logger = logging.getLogger(__name__)


class SelectiveOCRService:
    """Use local Tesseract only when a PDF page has too little selectable text."""

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        languages: str | None = None,
        dpi: int | None = None,
        min_text_characters: int | None = None,
        tessdata_dir: str | Path | None = None,
    ) -> None:
        settings = get_settings()
        self.enabled = settings.OCR_ENABLED if enabled is None else enabled
        self.requested_languages = languages if languages is not None else settings.OCR_LANGUAGES
        self.dpi = settings.OCR_DPI if dpi is None else dpi
        self.min_text_characters = (
            settings.OCR_MIN_TEXT_CHARACTERS if min_text_characters is None else min_text_characters
        )
        if tessdata_dir is None:
            tessdata_dir = settings.OCR_TESSDATA_DIR or None
        self.tessdata_dir = self._resolve_tessdata_dir(tessdata_dir)
        self.languages = self._available_language_spec(self.requested_languages, self.tessdata_dir)

    @property
    def available(self) -> bool:
        if not self.enabled or self.tessdata_dir is None or not self.languages:
            return False
        try:
            import pymupdf  # noqa: F401
        except ImportError:
            return False
        return True

    def enrich_sections(self, file_path: str | Path, sections: list[ParsedSection]) -> list[ParsedSection]:
        candidates = [section for section in sections if self.needs_ocr(section.raw_text)]
        if not candidates or not self.available:
            if candidates and self.enabled:
                logger.info(
                    "OCR fallback skipped for %s: PyMuPDF or Tesseract language data is unavailable.",
                    Path(file_path).name,
                )
            return sections

        import pymupdf

        enriched_by_page = {section.page_number: section for section in sections}
        try:
            document = pymupdf.open(str(file_path))
        except Exception:
            logger.exception("OCR could not open PDF %s.", file_path)
            return sections

        with document:
            total = len(candidates)
            for position, section in enumerate(candidates, start=1):
                logger.info(
                    "OCR fallback %s page %s (%s/%s, languages=%s).",
                    Path(file_path).name,
                    section.page_number,
                    position,
                    total,
                    self.languages,
                )
                section.ocr_attempted = True
                page_index = section.page_number - 1
                if page_index < 0 or page_index >= document.page_count:
                    continue
                try:
                    page = document.load_page(page_index)
                    text_page = page.get_textpage_ocr(
                        language=self.languages,
                        dpi=self.dpi,
                        full=True,
                        tessdata=str(self.tessdata_dir),
                    )
                    ocr_text = page.get_text("text", textpage=text_page, sort=True).strip()
                except Exception:
                    logger.exception(
                        "OCR failed for %s page %s; native text will be kept.",
                        Path(file_path).name,
                        section.page_number,
                    )
                    continue

                if self._text_score(ocr_text) <= self._text_score(section.raw_text):
                    continue
                section.raw_text = self._merge_text(section.raw_text, ocr_text)
                section.extraction_method = "ocr"
                enriched_by_page[section.page_number] = section

        return [enriched_by_page[section.page_number] for section in sections]

    def needs_ocr(self, text: str) -> bool:
        meaningful_text = self._meaningful_text(text)
        character_count = sum(character.isalnum() for character in meaningful_text)
        word_count = len(re.findall(r"\w+", meaningful_text, flags=re.UNICODE))
        return character_count < self.min_text_characters or word_count < 10

    @classmethod
    def _text_score(cls, text: str) -> int:
        meaningful_text = cls._meaningful_text(text)
        characters = sum(character.isalnum() for character in meaningful_text)
        words = len(re.findall(r"\w+", meaningful_text, flags=re.UNICODE))
        return characters + words * 3

    @staticmethod
    def _meaningful_text(text: str) -> str:
        lines = []
        for line in str(text or "").splitlines():
            compact = " ".join(line.split())
            if re.search(r"\bpage\s+\d+\s*/\s*\d+\b", compact, flags=re.IGNORECASE) and (
                "\\" in compact or "/" in compact
            ):
                continue
            lines.append(compact)
        return " ".join(lines)

    @staticmethod
    def _merge_text(native_text: str, ocr_text: str) -> str:
        merged_lines: list[str] = []
        seen: set[str] = set()
        for text in (native_text, ocr_text):
            for line in text.splitlines():
                compact = " ".join(line.split()).strip()
                if not compact:
                    continue
                key = re.sub(r"\W+", "", compact.casefold(), flags=re.UNICODE)
                if key and key in seen:
                    continue
                if key:
                    seen.add(key)
                merged_lines.append(compact)
        return "\n".join(merged_lines)

    @classmethod
    def _resolve_tessdata_dir(cls, configured: str | Path | None) -> Path | None:
        candidates: list[Path] = []
        if configured:
            candidates.append(Path(configured).expanduser())
        tesseract_cmd = get_settings().OCR_TESSERACT_CMD
        if tesseract_cmd:
            candidates.append(Path(tesseract_cmd).expanduser().parent / "tessdata")

        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            candidates.append(Path(local_app_data) / "Programs" / "Tesseract-OCR" / "tessdata")
        program_files = os.getenv("ProgramFiles")
        if program_files:
            candidates.append(Path(program_files) / "Tesseract-OCR" / "tessdata")

        for candidate in candidates:
            nested_candidate = candidate / "tessdata"
            if nested_candidate.is_dir() and not any(candidate.glob("*.traineddata")):
                candidate = nested_candidate
            if candidate.is_dir() and any(candidate.glob("*.traineddata")):
                return candidate.resolve()
        return None

    @staticmethod
    def _available_language_spec(requested: str, tessdata_dir: Path | None) -> str:
        if tessdata_dir is None:
            return ""
        available = {path.stem.casefold() for path in tessdata_dir.glob("*.traineddata")}
        selected = [
            language.strip()
            for language in requested.split("+")
            if language.strip() and language.strip().casefold() in available
        ]
        return "+".join(selected)
