from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.document_path_service import resolve_document_file_path  # noqa: E402


class DocumentPathServiceTests(unittest.TestCase):
    def test_uses_existing_stored_path(self) -> None:
        stored_file = Path("C:/active-data/documents/report.pdf")
        with patch.object(Path, "is_file", lambda candidate: candidate == stored_file):
            resolved = resolve_document_file_path(
                stored_file,
                documents_dir=Path("C:/other-data/documents"),
            )

        self.assertEqual(resolved, stored_file)

    def test_falls_back_to_active_documents_directory_after_move(self) -> None:
        documents_dir = Path("D:/Big_Agent/data/documents")
        moved_file = documents_dir / "report__12345678.pdf"
        stale_path = Path("C:/old-machine/Big_Agent/data/documents") / moved_file.name

        def simulated_is_file(candidate: Path) -> bool:
            if candidate == stale_path:
                raise PermissionError("Old location is inaccessible")
            return candidate == moved_file

        with patch.object(Path, "is_file", simulated_is_file):
            resolved = resolve_document_file_path(
                stale_path,
                documents_dir=documents_dir,
            )

        self.assertEqual(resolved, moved_file)

    def test_returns_none_when_file_is_unavailable(self) -> None:
        with patch.object(Path, "is_file", return_value=False):
            resolved = resolve_document_file_path(
                "C:/old-machine/missing.pdf",
                documents_dir=Path("D:/Big_Agent/data/documents"),
            )

        self.assertIsNone(resolved)


if __name__ == "__main__":
    unittest.main()
