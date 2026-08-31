"""Report catalog: spreadsheet import, dedupe, search and document matching."""

from __future__ import annotations

from io import BytesIO

import pytest

from app.db.models import ReportCatalogEntry
from app.services.catalog_service import CatalogRow, CatalogService

from .conftest import add_document


HEADER_LINE = "Report Name;Vehicle;Report Title;Analysis Type;Date;Prepared By"
CATALOG_LINES = (
    "2025-BIG-E-DUR-01;BIG-E;Sasi Yorulma Dayanim Raporu;DURABILITY;2025-03-14;Ali Veli",
    "2024-BIG-E-NVH-07;BIG-E;Kabin Titresim Raporu;NVH;2024-11-02;Ayse Yilmaz",
    "2025-CITIBUS-CFD-03;CITIBUS;Motor Bolmesi Akis Analizi;CFD;2025-01-20;Mehmet Kaya",
)


def _csv_bytes(*lines: str) -> bytes:
    return "\n".join([HEADER_LINE, *(lines or CATALOG_LINES)]).encode("utf-8")


def _xlsx_bytes(rows: list[list[str]], hyperlink: tuple[int, int, str] | None = None) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    if hyperlink is not None:
        row_index, column_index, target = hyperlink
        sheet.cell(row=row_index, column=column_index).hyperlink = target
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def catalog(db_session) -> CatalogService:
    return CatalogService(db_session)


@pytest.fixture
def imported_catalog(catalog) -> CatalogService:
    catalog.import_bytes("katalog.csv", _csv_bytes())
    return catalog


# --- import ------------------------------------------------------------------


def test_import_creates_one_entry_per_data_row(catalog, db_session) -> None:
    result = catalog.import_bytes("katalog.csv", _csv_bytes())

    assert result["file_name"] == "katalog.csv"
    assert result["rows_seen"] == 3
    assert result["created_count"] == 3
    assert result["duplicate_count"] == 0
    assert result["error_count"] == 0
    assert db_session.query(ReportCatalogEntry).count() == 3


def test_import_skips_the_header_row(catalog) -> None:
    result = catalog.import_bytes("katalog.csv", _csv_bytes())

    # rows_seen counts parsed data rows, so the header never reaches the database.
    assert result["rows_seen"] == 3
    assert [entry["report_code"] for entry in catalog.search(limit=10)] != [HEADER_LINE.split(";")[0]]


def test_import_uppercases_the_discipline(imported_catalog) -> None:
    disciplines = {entry["discipline"] for entry in imported_catalog.search(limit=10)}

    assert disciplines == {"DURABILITY", "NVH", "CFD"}


def test_re_importing_the_same_file_creates_nothing_new(catalog, db_session) -> None:
    catalog.import_bytes("katalog.csv", _csv_bytes())

    second = catalog.import_bytes("katalog.csv", _csv_bytes())

    assert second["created_count"] == 0
    assert second["duplicate_count"] == 3
    assert db_session.query(ReportCatalogEntry).count() == 3


def test_rows_duplicated_within_one_file_are_counted_once(catalog, db_session) -> None:
    result = catalog.import_bytes("katalog.csv", _csv_bytes(CATALOG_LINES[0], CATALOG_LINES[0]))

    assert result["rows_seen"] == 2
    assert result["created_count"] == 1
    assert result["duplicate_count"] == 1
    assert db_session.query(ReportCatalogEntry).count() == 1


def test_rows_with_too_few_columns_are_ignored(catalog) -> None:
    result = catalog.import_bytes("katalog.csv", _csv_bytes("2025-X-1;BIG-E;Baslik"))

    assert result["rows_seen"] == 0
    assert result["created_count"] == 0


def test_rows_missing_a_required_field_are_ignored(catalog) -> None:
    result = catalog.import_bytes("katalog.csv", _csv_bytes("2025-X-1;;Baslik;NVH;2025-01-01;Ali"))

    assert result["rows_seen"] == 0


def test_tab_separated_files_are_detected(catalog) -> None:
    content = "\n".join(line.replace(";", "\t") for line in [HEADER_LINE, *CATALOG_LINES]).encode("utf-8")

    result = catalog.import_bytes("katalog.tsv", content)

    assert result["created_count"] == 3


def test_comma_separated_files_are_detected(catalog) -> None:
    content = "\n".join(line.replace(";", ",") for line in [HEADER_LINE, *CATALOG_LINES]).encode("utf-8")

    result = catalog.import_bytes("katalog.csv", content)

    assert result["created_count"] == 3


def test_a_utf8_bom_does_not_corrupt_the_first_report_code(catalog) -> None:
    result = catalog.import_bytes("katalog.csv", b"\xef\xbb\xbf" + _csv_bytes())

    assert result["created_count"] == 3
    assert "2025-BIG-E-DUR-01" in {entry["report_code"] for entry in catalog.search(limit=10)}


def test_xlsx_import_reads_cells_and_hyperlinks(catalog) -> None:
    rows = [HEADER_LINE.split(";"), CATALOG_LINES[0].split(";")]

    result = catalog.import_bytes(
        "katalog.xlsx",
        _xlsx_bytes(rows, hyperlink=(2, 1, r"file:///V:/RAPORLAR/2025-BIG-E-DUR-01.pdf")),
    )

    assert result["created_count"] == 1
    entry = catalog.search(limit=1)[0]
    assert entry["report_code"] == "2025-BIG-E-DUR-01"
    assert entry["source_path"] == r"V:\RAPORLAR\2025-BIG-E-DUR-01.pdf"


def test_a_later_import_backfills_a_missing_source_path(catalog) -> None:
    rows = [HEADER_LINE.split(";"), CATALOG_LINES[0].split(";")]
    catalog.import_bytes("katalog.csv", _csv_bytes(CATALOG_LINES[0]))

    result = catalog.import_bytes(
        "katalog.xlsx",
        _xlsx_bytes(rows, hyperlink=(2, 1, r"file:///V:/RAPORLAR/2025-BIG-E-DUR-01.pdf")),
    )

    assert result["created_count"] == 0
    assert result["updated_count"] == 1
    assert catalog.search(limit=1)[0]["source_path"] == r"V:\RAPORLAR\2025-BIG-E-DUR-01.pdf"


# --- search ------------------------------------------------------------------


def test_search_without_filters_returns_everything_newest_first(imported_catalog) -> None:
    results = imported_catalog.search(limit=10)

    assert [entry["report_date"] for entry in results] == ["2025-03-14", "2025-01-20", "2024-11-02"]


def test_search_matches_any_of_the_indexed_columns(imported_catalog) -> None:
    by_code = imported_catalog.search(query="DUR-01")
    by_title = imported_catalog.search(query="Titresim")
    by_author = imported_catalog.search(query="Mehmet")

    assert [entry["report_code"] for entry in by_code] == ["2025-BIG-E-DUR-01"]
    assert [entry["report_code"] for entry in by_title] == ["2024-BIG-E-NVH-07"]
    assert [entry["report_code"] for entry in by_author] == ["2025-CITIBUS-CFD-03"]


def test_search_filters_combine_as_and(imported_catalog) -> None:
    assert len(imported_catalog.search(vehicle="BIG-E")) == 2
    assert len(imported_catalog.search(vehicle="BIG-E", discipline="NVH")) == 1
    assert imported_catalog.search(vehicle="CITIBUS", discipline="NVH") == []


def test_search_honours_the_limit(imported_catalog) -> None:
    assert len(imported_catalog.search(limit=2)) == 2


def test_search_on_an_empty_catalog_returns_nothing(catalog) -> None:
    assert catalog.search(query="dayanim") == []


# --- question routing --------------------------------------------------------


def test_catalog_question_returns_matching_entries_and_filters(imported_catalog) -> None:
    answer = imported_catalog.answer_catalog_question("BIG-E dayanim raporlari")

    assert answer["filters"]["vehicle"] == "BIG-E"
    assert answer["filters"]["discipline"] == "DURABILITY"
    assert [entry["report_code"] for entry in answer["catalog_matches"]] == ["2025-BIG-E-DUR-01"]
    assert answer["answer_found"] is True
    assert answer["match_count"] == 1
    assert answer["answer"]


def test_catalog_question_with_no_match_says_so(imported_catalog) -> None:
    answer = imported_catalog.answer_catalog_question("2019-YOK-BOYLE-BIR-KOD-99 raporu")

    assert answer["catalog_matches"] == []
    assert answer["answer_found"] is False
    assert "bulunamadi" in answer["answer"].casefold()


def test_discipline_aliases_fold_turkish_terms_onto_catalog_values(catalog) -> None:
    assert catalog._detect_discipline("dayanim raporu") == "DURABILITY"
    assert catalog._detect_discipline("titresim ve nvh") == "NVH"
    assert catalog._detect_discipline("guvenlik testi") == "SAFETY"
    assert catalog._detect_discipline("akis analizi") == "CFD"
    assert catalog._detect_discipline("genel bir soru") == ""


def test_vehicles_are_detected_from_the_stored_vehicle_names(imported_catalog) -> None:
    assert imported_catalog._detect_vehicles("bige raporlari") == ["BIG-E"]
    assert imported_catalog._detect_vehicles("citibus akis analizi") == ["CITIBUS"]
    assert imported_catalog._detect_vehicles("bilinmeyen bir arac") == []


def test_intent_detection_separates_summary_comparison_and_search() -> None:
    assert CatalogService._detect_intent("hangi analiz tipi var", [], "") == "analysis_type_summary"
    assert CatalogService._detect_intent("a ve b karsilastir", ["A", "B"], "") == "vehicle_comparison"
    assert CatalogService._detect_intent("en cok rapor hangi arac", [], "") == "vehicle_ranking"
    assert CatalogService._detect_intent("dayanim raporlari", [], "") == "catalog_search"


def test_report_code_detection_needs_at_least_three_separators() -> None:
    assert CatalogService._detect_report_code("2025-BIG-E-DUR-01 raporu") == "2025-BIG-E-DUR-01"
    assert CatalogService._detect_report_code("2025-BIG raporu") == ""


# --- document matching -------------------------------------------------------


def test_a_catalog_entry_is_matched_to_the_document_with_its_report_code(imported_catalog, db_session) -> None:
    document = add_document(
        db_session,
        "2025-BIG-E-DUR-01 Sasi Yorulma",
        file_name="2025-BIG-E-DUR-01.pdf",
    )
    add_document(db_session, "Alakasiz Rapor", file_name="alakasiz.pdf")
    db_session.commit()
    entries = db_session.query(ReportCatalogEntry).all()

    matches = imported_catalog._match_documents(entries)

    durability = next(entry for entry in entries if entry.report_code == "2025-BIG-E-DUR-01")
    assert matches[durability.id] == document.id
    assert len(matches) == 1


def test_match_documents_is_empty_without_entries(catalog) -> None:
    assert catalog._match_documents([]) == {}


def test_document_match_score_ranks_code_above_title(catalog, db_session) -> None:
    entry = ReportCatalogEntry(
        report_code="2025-BIG-E-DUR-01",
        vehicle_name="BIG-E",
        report_title="Sasi Yorulma Dayanim Raporu",
        discipline="DURABILITY",
        row_hash="hash-1",
    )
    by_code = add_document(db_session, "2025-BIG-E-DUR-01", file_name="rapor.pdf")
    by_title = add_document(db_session, "Sasi Yorulma Dayanim Raporu", file_name="baska.pdf")
    unrelated = add_document(db_session, "Termal Analiz", file_name="termal.pdf")
    db_session.commit()

    assert catalog._document_match_score(entry, by_code) == 300
    assert catalog._document_match_score(entry, by_title) == 180
    assert catalog._document_match_score(entry, unrelated) == 0


# --- pure helpers ------------------------------------------------------------


def test_source_paths_are_normalised_to_windows_separators() -> None:
    assert CatalogService._normalize_source_path("file:///V:/RAPORLAR/a.pdf") == r"V:\RAPORLAR\a.pdf"
    assert CatalogService._normalize_source_path("V:/RAPORLAR/a.pdf") == r"V:\RAPORLAR\a.pdf"
    assert CatalogService._normalize_source_path(r"\\isufile02\pay$\a.pdf") == r"\\isufile02\pay$\a.pdf"


def test_source_paths_that_are_not_paths_are_dropped() -> None:
    assert CatalogService._normalize_source_path("https://intranet/rapor") is None
    assert CatalogService._normalize_source_path("#Sayfa1!A1") is None
    assert CatalogService._normalize_source_path("2025-BIG-E-DUR-01") is None
    assert CatalogService._normalize_source_path("") is None
    assert CatalogService._normalize_source_path(None) is None


def test_percent_encoding_in_a_source_path_is_decoded() -> None:
    assert CatalogService._normalize_source_path("file:///V:/RAPOR%20LAR/a.pdf") == r"V:\RAPOR LAR\a.pdf"


def test_cell_values_are_flattened_to_text() -> None:
    from datetime import date, datetime

    assert CatalogService._cell_to_text(None) == ""
    assert CatalogService._cell_to_text("  bosluk  ") == "bosluk"
    assert CatalogService._cell_to_text(42) == "42"
    assert CatalogService._cell_to_text(date(2025, 3, 14)) == "2025-03-14"
    assert CatalogService._cell_to_text(datetime(2025, 3, 14, 9, 30)) == "2025-03-14"


def test_header_detection_recognises_both_languages() -> None:
    assert CatalogService._looks_like_header(HEADER_LINE.split(";")) is True
    assert CatalogService._looks_like_header(["Rapor Kodu", "Arac", "Baslik", "Disiplin", "", ""]) is True
    assert CatalogService._looks_like_header(CATALOG_LINES[0].split(";")) is False


def test_row_hash_ignores_the_source_path() -> None:
    base = dict(
        report_code="2025-X-1",
        vehicle_name="BIG-E",
        report_title="Baslik",
        discipline="NVH",
        report_date="2025-01-01",
        authors="Ali",
    )

    assert CatalogService._row_hash(CatalogRow(**base, source_path=r"V:\a.pdf")) == (
        CatalogService._row_hash(CatalogRow(**base, source_path=r"V:\b.pdf"))
    )
    assert CatalogService._row_hash(CatalogRow(**base)) != CatalogService._row_hash(
        CatalogRow(**{**base, "discipline": "CFD"})
    )


def test_match_tokens_split_on_every_non_alphanumeric() -> None:
    assert CatalogService._match_tokens("2025-BIG_E.DUR 01") == ["2025", "big", "e", "dur", "01"]
    assert CatalogService._match_key("2025-BIG-E-DUR-01") == "2025bigedur01"
