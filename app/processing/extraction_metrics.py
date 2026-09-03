"""Deterministic extraction metrics for ingested pages.

`IngestService` persists these numbers on `DocumentPage` and rolls them up onto
`Document.extraction_quality`, so that later stages can tell three cases apart
that used to look identical once the text was in the database:

* **native** - the parser read selectable text and OCR was never needed,
* **OCR-rescued** - the page was text-poor, Tesseract ran and beat the native
  text, so the stored text is (partly) OCR output,
* **unreadable** - nothing usable came out, with or without OCR.

The thresholds are module constants rather than settings on purpose. Review
findings must be reproducible across machines, so a workstation with OCR tuned
differently still classifies a stored page exactly the same way. They are
aligned with the defaults `SelectiveOCRService` uses to decide when to run
(`OCR_MIN_TEXT_CHARACTERS` = 100 characters, 10 words).
"""

from __future__ import annotations

from dataclasses import dataclass
import re


WORD_PATTERN = re.compile(r"\w+", flags=re.UNICODE)

# Below this a page carries no usable text at all: a scan the parser could not
# read, or a pure-image page. Reported as a failure.
NO_TEXT_CHARACTERS = 30
NO_TEXT_WORDS = 5

# Thin but not empty. Matches the default bar at which selective OCR decides a
# page is worth re-reading; a page that stays under it *after* OCR ran is the
# case an engineer has to look at by eye.
LOW_QUALITY_CHARACTERS = 100
LOW_QUALITY_WORDS = 10

# A rollup is a record, not a page list: cap the page numbers it carries so a
# 400-page scan does not write a 400-entry array into every document row.
MAX_LISTED_PAGES = 50

NATIVE = "native"
OCR = "ocr"

READABLE = "readable"
LOW_QUALITY = "low_quality"
NO_TEXT = "no_text"


def char_count(text: str | None) -> int:
    """Characters of stored page text, ignoring surrounding whitespace."""
    return len(str(text or "").strip())


def word_count(text: str | None) -> int:
    return len(WORD_PATTERN.findall(str(text or "")))


@dataclass(frozen=True, slots=True)
class PageExtractionMetrics:
    """What was recorded about one page's extraction.

    `extraction_method` and `ocr_attempted` are optional because pages ingested
    before these columns existed carry no provenance; `None` means "unknown"
    and must never be read as "native, OCR never needed".
    """

    page_number: int
    char_count: int
    word_count: int
    extraction_method: str | None = None
    ocr_attempted: bool | None = None

    @property
    def is_ocr(self) -> bool:
        return self.extraction_method == OCR

    @property
    def has_no_text(self) -> bool:
        return self.char_count < NO_TEXT_CHARACTERS or self.word_count < NO_TEXT_WORDS

    @property
    def is_sparse(self) -> bool:
        """Thin text, whether or not OCR was involved."""
        return self.char_count < LOW_QUALITY_CHARACTERS or self.word_count < LOW_QUALITY_WORDS

    @property
    def classification(self) -> str:
        if self.has_no_text:
            return NO_TEXT
        if self.ocr_attempted and self.is_sparse:
            return LOW_QUALITY
        return READABLE


def metrics_for_text(
    page_number: int,
    text: str | None,
    *,
    extraction_method: str | None = None,
    ocr_attempted: bool | None = None,
) -> PageExtractionMetrics:
    return PageExtractionMetrics(
        page_number=int(page_number),
        char_count=char_count(text),
        word_count=word_count(text),
        extraction_method=extraction_method,
        ocr_attempted=ocr_attempted,
    )


def summarize(
    page_metrics: list[PageExtractionMetrics],
    *,
    parsed_page_count: int,
    empty_pages: list[int] | None = None,
) -> dict:
    """Roll per-page metrics up into the record stored on the document.

    `parsed_page_count` counts what the parser produced; `empty_pages` are the
    page numbers that normalisation dropped because nothing survived cleaning.
    Those pages have no `DocumentPage` row, so the rollup is the only place
    they are ever recorded.
    """
    dropped = sorted(empty_pages or [])
    total_chars = sum(item.char_count for item in page_metrics)
    stored_count = len(page_metrics)
    no_text_pages = [item.page_number for item in page_metrics if item.has_no_text]
    return {
        "page_count": int(parsed_page_count),
        "stored_page_count": stored_count,
        "ocr_page_count": sum(1 for item in page_metrics if item.is_ocr),
        "ocr_attempted_page_count": sum(1 for item in page_metrics if item.ocr_attempted),
        "sparse_page_count": sum(1 for item in page_metrics if item.is_sparse),
        # Pages dropped at normalisation are unreadable by definition.
        "no_text_page_count": len(no_text_pages) + len(dropped),
        "no_text_pages": sorted(set(no_text_pages) | set(dropped))[:MAX_LISTED_PAGES],
        "empty_pages": dropped[:MAX_LISTED_PAGES],
        "total_chars": total_chars,
        "mean_chars_per_page": round(total_chars / stored_count, 1) if stored_count else 0.0,
    }
