from __future__ import annotations

import hashlib
from pathlib import Path

from app.services.ingest_service import IngestService


def test_hash_file_matches_sha256_of_contents(tmp_path: Path) -> None:
    file_path = tmp_path / "report.txt"
    file_path.write_bytes(b"Turkce test raporu icerigi")

    digest = IngestService._hash_file(file_path)

    assert digest == hashlib.sha256(b"Turkce test raporu icerigi").hexdigest()


def test_hash_file_is_stable_across_calls(tmp_path: Path) -> None:
    file_path = tmp_path / "report.txt"
    file_path.write_bytes(b"same content")

    assert IngestService._hash_file(file_path) == IngestService._hash_file(file_path)


def test_hash_file_differs_for_different_content(tmp_path: Path) -> None:
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_a.write_bytes(b"content a")
    file_b.write_bytes(b"content b")

    assert IngestService._hash_file(file_a) != IngestService._hash_file(file_b)


def test_hash_file_reads_large_file_in_chunks(tmp_path: Path) -> None:
    file_path = tmp_path / "large.bin"
    # bigger than the 1 MiB read chunk used internally, to exercise the loop more than once
    payload = b"x" * (1024 * 1024 + 10)
    file_path.write_bytes(payload)

    digest = IngestService._hash_file(file_path)

    assert digest == hashlib.sha256(payload).hexdigest()
