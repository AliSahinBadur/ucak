from pathlib import Path

import pytest

from app.services.library_service import LibraryService


def _document_names(node: dict) -> list[str]:
    names: list[str] = []
    if node.get("type") == "document":
        return [str(node["name"])]
    for child in node.get("children", []):
        names.extend(_document_names(child))
    return names


def test_library_scan_builds_nested_supported_document_tree(tmp_path: Path) -> None:
    reports = tmp_path / "RAPORLAR"
    durability = reports / "BIG-E" / "Dayanım"
    comfort = reports / "CITIBUS" / "Konfor"
    durability.mkdir(parents=True)
    comfort.mkdir(parents=True)
    (durability / "analiz.pdf").write_bytes(b"pdf")
    (durability / "taslak.docx").write_bytes(b"docx")
    (comfort / "sunum.pptx").write_bytes(b"pptx")
    (comfort / "notlar.txt").write_text("ignored", encoding="utf-8")

    result = LibraryService([reports]).scan(str(reports))

    assert result["root_path"] == str(reports)
    assert result["document_count"] == 3
    assert result["directory_count"] == 5
    assert result["truncated"] is False
    assert sorted(_document_names(result["tree"])) == ["analiz.pdf", "sunum.pptx", "taslak.docx"]


def test_library_scan_reports_missing_root(tmp_path: Path) -> None:
    missing = tmp_path / "bu-klasor-yok"
    with pytest.raises(ValueError, match="bulunamadı"):
        LibraryService([tmp_path]).scan(str(missing))


def test_library_scan_honors_document_limit(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    for index in range(4):
        (reports / f"rapor-{index}.pdf").write_bytes(b"pdf")

    result = LibraryService([reports]).scan(str(reports), limit=2)

    assert result["document_count"] == 2
    assert result["truncated"] is True


def test_library_scan_rejects_paths_outside_allowed_roots(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()

    with pytest.raises(ValueError, match="izinli köklerin dışında"):
        LibraryService([allowed]).scan(str(outside))


def test_library_scan_rejects_unc_paths_before_access(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="ağ ve aygıt yolları"):
        LibraryService([tmp_path]).scan(r"\\example.invalid\reports")
