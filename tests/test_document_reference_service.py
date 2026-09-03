"""Portable document references (F6).

Golden-set case files used to pin `"document_id": 9`, which resolves only
against one operator's database. These tests fix the semantics the case files
now depend on: a report code or a title fragment finds the same report on any
machine holding it, whatever ids the ingest happened to hand out.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, CatalogDocumentLink, Document, ReportCatalogEntry
from app.services.document_reference_service import (
    DocumentReferenceResolver,
    describe_reference,
    is_legacy_id_reference,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


def add_document(session, title: str, *, file_name: str | None = None) -> Document:
    resolved = file_name or f"{title}.pdf"
    document = Document(
        title=title,
        file_name=resolved,
        file_type="pdf",
        file_hash=("0" * 64 + title)[-64:],
        file_path=f"C:/{resolved}",
    )
    session.add(document)
    session.flush()
    return document


def link_catalog(session, document: Document, report_code: str) -> None:
    entry = ReportCatalogEntry(
        report_code=report_code,
        vehicle_name="SYN",
        report_title=f"{report_code} raporu",
        discipline="TEST",
        row_hash=("0" * 64 + report_code)[-64:],
    )
    session.add(entry)
    session.flush()
    session.add(
        CatalogDocumentLink(
            catalog_entry_id=int(entry.id),
            document_id=int(document.id),
            match_method="test",
        )
    )
    session.flush()


# --- report codes ------------------------------------------------------------


def test_a_bare_string_reference_is_a_report_code(session) -> None:
    document = add_document(session, "2025-BIG-E-NVH-01 Konfor Raporu")

    resolution = DocumentReferenceResolver(session).resolve("2025-BIG-E-NVH-01")

    assert resolution.document_id == int(document.id)
    assert resolution.method == "report_code"


def test_report_codes_match_regardless_of_case_and_separators(session) -> None:
    document = add_document(session, "2025-BIG-e-NVH-01 Konfor Raporu")
    resolver = DocumentReferenceResolver(session)

    for written_as in ("2025-BIG-E-NVH-01", "2025_big_e_nvh_01", "2025 BIG E NVH 01"):
        assert resolver.resolve({"report_code": written_as}).document_id == int(document.id)


def test_a_catalog_link_outranks_a_file_name_match(session) -> None:
    # The file name says NVH-01 but the catalog says this *other* file is the
    # report: an explicit link beats a text coincidence.
    by_name = add_document(session, "2025-BIG-E-NVH-01 taslak")
    linked = add_document(session, "Konfor olcum raporu son surum")
    link_catalog(session, linked, "2025-BIG-E-NVH-01")

    resolution = DocumentReferenceResolver(session).resolve("2025-BIG-E-NVH-01")

    assert resolution.document_id == int(linked.id)
    assert resolution.document_id != int(by_name.id)
    assert resolution.method == "catalog"


def test_the_file_name_is_searched_when_the_title_does_not_carry_the_code(session) -> None:
    document = add_document(session, "Konfor Raporu", file_name="2025-BIG-E-NVH-01-konfor.pdf")

    assert DocumentReferenceResolver(session).resolve("2025-BIG-E-NVH-01").document_id == int(
        document.id
    )


# --- title fragments ---------------------------------------------------------


def test_title_fragments_must_all_match(session) -> None:
    pedal = add_document(session, "Fren Pedali Statik Analiz Calismasi")
    add_document(session, "Fren Diski Termal Analizi")
    resolver = DocumentReferenceResolver(session)

    assert resolver.resolve({"title_contains": ["fren", "pedal"]}).document_id == int(pedal.id)
    assert not resolver.resolve({"title_contains": ["fren", "kompozit"]}).found


def test_title_fragments_are_accent_and_case_folded(session) -> None:
    document = add_document(session, "İvmeölçer Yerleşimi Raporu")

    resolution = DocumentReferenceResolver(session).resolve({"title_contains": ["ivmeolcer"]})

    assert resolution.document_id == int(document.id)
    assert resolution.method == "title"


def test_a_report_code_falls_back_to_title_fragments(session) -> None:
    # The corpus has the report but under a name that carries no code.
    document = add_document(session, "Yan Ayna Titresim Analizi Raporu")

    resolution = DocumentReferenceResolver(session).resolve(
        {"report_code": "2025-BIG-E-NVH-99", "title_contains": ["yan ayna"]}
    )

    assert resolution.document_id == int(document.id)
    assert resolution.method == "title"


# --- ambiguity and misses ----------------------------------------------------


def test_an_ambiguous_reference_is_reported_rather_than_silently_picked(session) -> None:
    first = add_document(session, "2025-BIG-E-DUR-01 Dayanim Raporu")
    add_document(session, "2025-BIG-E-DUR-01 Dayanim Raporu revizyon", file_name="dur-01-rev.pdf")

    resolution = DocumentReferenceResolver(session).resolve("2025-BIG-E-DUR-01")

    assert resolution.ambiguous
    assert resolution.match_count == 2
    # The lowest id is used so a run stays deterministic, but the caller is told.
    assert resolution.document_id == int(first.id)


def test_a_reference_to_a_missing_report_resolves_to_nothing(session) -> None:
    add_document(session, "2025-BIG-E-DUR-01 Dayanim Raporu")

    resolution = DocumentReferenceResolver(session).resolve("2026-BIG-E-CFD-42")

    assert not resolution.found
    assert resolution.document_id is None
    assert resolution.method == ""


def test_an_empty_or_unusable_reference_resolves_to_nothing(session) -> None:
    add_document(session, "2025-BIG-E-DUR-01 Dayanim Raporu")
    resolver = DocumentReferenceResolver(session)

    assert not resolver.resolve(None).found
    assert not resolver.resolve({}).found
    assert not resolver.resolve(["not", "a", "reference"]).found


# --- the legacy id escape hatch ----------------------------------------------


def test_a_legacy_id_reference_still_resolves(session) -> None:
    document = add_document(session, "2025-BIG-E-DUR-01 Dayanim Raporu")

    resolution = DocumentReferenceResolver(session).resolve({"document_id": int(document.id)})

    assert resolution.document_id == int(document.id)
    assert resolution.method == "document_id"


def test_a_portable_reference_wins_over_the_id_it_ships_with(session) -> None:
    # A half-migrated case: the id points at the wrong report after a re-ingest,
    # the code still points at the right one.
    wrong = add_document(session, "Alakasiz Rapor")
    right = add_document(session, "2025-BIG-E-DUR-01 Dayanim Raporu")

    resolution = DocumentReferenceResolver(session).resolve(
        {"report_code": "2025-BIG-E-DUR-01", "document_id": int(wrong.id)}
    )

    assert resolution.document_id == int(right.id)


def test_legacy_id_references_are_identifiable(session) -> None:
    assert is_legacy_id_reference(9)
    assert is_legacy_id_reference({"document_id": 9})
    assert not is_legacy_id_reference("2025-BIG-E-DUR-01")
    assert not is_legacy_id_reference({"report_code": "2025-BIG-E-DUR-01", "document_id": 9})
    assert not is_legacy_id_reference({"title_contains": ["fren"]})
    assert not is_legacy_id_reference(None)


# --- helpers -----------------------------------------------------------------


def test_references_describe_themselves_for_check_output() -> None:
    assert describe_reference("2025-BIG-E-DUR-01") == "2025-BIG-E-DUR-01"
    assert describe_reference({"report_code": "2025-BIG-E-DUR-01"}) == "2025-BIG-E-DUR-01"
    assert describe_reference({"title_contains": ["fren", "pedal"]}) == "fren + pedal"
    assert describe_reference({"document_id": 9}) == "document_id=9"
    assert describe_reference({}) == "<empty reference>"


def test_resolve_ids_keeps_order_drops_misses_and_deduplicates(session) -> None:
    nvh = add_document(session, "2025-BIG-E-NVH-01 Konfor Raporu")
    dur = add_document(session, "2025-BIG-E-DUR-01 Dayanim Raporu")

    ids = DocumentReferenceResolver(session).resolve_ids(
        [
            "2025-BIG-E-DUR-01",
            "2026-BIG-E-CFD-42",
            {"title_contains": ["konfor"]},
            "2025-BIG-E-DUR-01",
        ]
    )

    assert ids == [int(dur.id), int(nvh.id)]


def test_the_corpus_snapshot_is_taken_once_per_resolver(session) -> None:
    add_document(session, "2025-BIG-E-DUR-01 Dayanim Raporu")
    resolver = DocumentReferenceResolver(session)
    assert resolver.resolve("2025-BIG-E-DUR-01").found

    # A resolver caches the corpus for the length of a run, so a document added
    # afterwards is deliberately not visible to it; a fresh resolver sees it.
    add_document(session, "2025-BIG-E-NVH-01 Konfor Raporu")
    session.commit()

    assert not resolver.resolve("2025-BIG-E-NVH-01").found
    assert DocumentReferenceResolver(session).resolve("2025-BIG-E-NVH-01").found
