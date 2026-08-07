from __future__ import annotations

from pathlib import Path

from ..config import DOCUMENTS_DIR


def resolve_document_file_path(
    stored_path: str | Path,
    *,
    documents_dir: str | Path | None = None,
) -> Path | None:
    """Resolve document files after the application directory has been moved."""
    raw_path = Path(stored_path).expanduser()
    active_documents_dir = Path(documents_dir) if documents_dir else DOCUMENTS_DIR

    candidates = [raw_path]
    if not raw_path.is_absolute():
        candidates.append(active_documents_dir / raw_path)
    candidates.append(active_documents_dir / raw_path.name)

    seen: set[str] = set()
    for candidate in candidates:
        candidate_key = str(candidate).casefold()
        if candidate_key in seen:
            continue
        seen.add(candidate_key)
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None
