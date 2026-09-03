"""Resolve a *portable* reference to a document, never a database id.

Golden-set case files used to pin `"document_id": 9`, which resolves only
against one operator's `data/app.db`: re-ingest the corpus in a different order
and the whole suite silently checks the wrong reports. A case should say which
*report* it means and let the runner find it.

A reference is one of:

* a string -- the report code, e.g. ``"2025-BIG-E-NVH-01"``
* ``{"report_code": "..."}`` -- the same, explicitly
* ``{"title_contains": ["fren", "pedal"]}`` -- every fragment must appear in the
  document title or file name, for reports that carry no catalog code
* ``{"document_id": 9}`` -- the legacy pin, kept so an un-migrated file still
  runs; callers should surface it as the portability hazard it is

Report codes are matched the way the retrieval layer already matches a report
reference in a question: normalised (case- and accent-folded) and compacted, so
``2025-BIG-e-NVH-01`` and ``2025-BIG-E-NVH-01`` are the same report.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import CatalogDocumentLink, Document, ReportCatalogEntry
from .search_service import SearchService


@dataclass(frozen=True, slots=True)
class DocumentResolution:
    """What a reference resolved to, and how.

    `match_count` above 1 means the reference is ambiguous: it named more than
    one document and the lowest id was taken. Callers should report that rather
    than let a case quietly assert against an arbitrary report.
    """

    document: Document | None
    method: str = ""
    match_count: int = 0

    @property
    def found(self) -> bool:
        return self.document is not None

    @property
    def document_id(self) -> int | None:
        return int(self.document.id) if self.document is not None else None

    @property
    def ambiguous(self) -> bool:
        return self.match_count > 1


def compact(value: str) -> str:
    return SearchService._compact_search_text(SearchService._normalize_search_text(value or ""))


def normalize(value: str) -> str:
    return SearchService._normalize_search_text(value or "")


def describe_reference(reference: object) -> str:
    """A short human label for a reference, for check output and error text."""
    if isinstance(reference, dict):
        if reference.get("report_code"):
            return str(reference["report_code"])
        if reference.get("title_contains"):
            return " + ".join(str(item) for item in reference["title_contains"])
        if reference.get("document_id") is not None:
            return f"document_id={reference['document_id']}"
        return "<empty reference>"
    return str(reference)


def is_legacy_id_reference(reference: object) -> bool:
    """True when the reference is still pinned to a database id (F6)."""
    if isinstance(reference, bool):
        return False
    if isinstance(reference, int):
        return True
    return isinstance(reference, dict) and not reference.get("report_code") and (
        not reference.get("title_contains") and reference.get("document_id") is not None
    )


class DocumentReferenceResolver:
    """Resolves references against a snapshot of the corpus taken once."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._documents: list[Document] | None = None
        self._catalog_codes: dict[int, list[str]] | None = None

    # --- corpus snapshot ------------------------------------------------------

    @property
    def documents(self) -> list[Document]:
        if self._documents is None:
            self._documents = list(self.session.scalars(select(Document).order_by(Document.id)))
        return self._documents

    @property
    def catalog_codes(self) -> dict[int, list[str]]:
        """document_id -> report codes linked to it, compacted."""
        if self._catalog_codes is None:
            rows = self.session.execute(
                select(CatalogDocumentLink.document_id, ReportCatalogEntry.report_code).join(
                    ReportCatalogEntry, ReportCatalogEntry.id == CatalogDocumentLink.catalog_entry_id
                )
            ).all()
            codes: dict[int, list[str]] = {}
            for document_id, report_code in rows:
                codes.setdefault(int(document_id), []).append(compact(str(report_code)))
            self._catalog_codes = codes
        return self._catalog_codes

    def _searchable(self, document: Document) -> str:
        return compact(f"{document.title} {document.file_name}")

    # --- resolution -----------------------------------------------------------

    def resolve(self, reference: object) -> DocumentResolution:
        if reference is None:
            return DocumentResolution(None)
        if isinstance(reference, (str, int)) and not isinstance(reference, bool):
            reference = (
                {"document_id": int(reference)}
                if isinstance(reference, int)
                else {"report_code": str(reference)}
            )
        if not isinstance(reference, dict):
            return DocumentResolution(None)

        report_code = str(reference.get("report_code") or "").strip()
        if report_code:
            resolution = self._by_report_code(report_code)
            if resolution.found:
                return resolution

        fragments = [str(item) for item in (reference.get("title_contains") or []) if str(item).strip()]
        if fragments:
            resolution = self._by_title_fragments(fragments)
            if resolution.found:
                return resolution

        document_id = reference.get("document_id")
        if document_id is not None:
            document = self.session.get(Document, int(document_id))
            if document is not None:
                return DocumentResolution(document, "document_id", 1)

        return DocumentResolution(None)

    def _by_report_code(self, report_code: str) -> DocumentResolution:
        compact_code = compact(report_code)
        if not compact_code:
            return DocumentResolution(None)

        # A catalog link is an explicit statement that this file *is* that
        # report, so it outranks any text match on the file name.
        linked = [
            document
            for document in self.documents
            if compact_code in self.catalog_codes.get(int(document.id), [])
        ]
        if linked:
            return DocumentResolution(linked[0], "catalog", len(linked))

        matched = [
            document for document in self.documents if compact_code in self._searchable(document)
        ]
        if matched:
            return DocumentResolution(matched[0], "report_code", len(matched))
        return DocumentResolution(None)

    def _by_title_fragments(self, fragments: list[str]) -> DocumentResolution:
        normalized_fragments = [normalize(fragment) for fragment in fragments]
        matched = [
            document
            for document in self.documents
            if all(
                fragment in normalize(f"{document.title} {document.file_name}")
                for fragment in normalized_fragments
            )
        ]
        if matched:
            return DocumentResolution(matched[0], "title", len(matched))
        return DocumentResolution(None)

    def resolve_ids(self, references: list[object]) -> list[int]:
        """Resolved ids for a list of references, skipping the ones not found."""
        ids = []
        for reference in references:
            resolution = self.resolve(reference)
            if resolution.document_id is not None:
                ids.append(resolution.document_id)
        return list(dict.fromkeys(ids))
