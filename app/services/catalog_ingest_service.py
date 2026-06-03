from __future__ import annotations

from pathlib import Path
import os

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import ChunkEmbedding, DocumentChunk, ReportCatalogEntry
from .catalog_service import CatalogService
from .ingest_service import IngestService, SUPPORTED_EXTENSIONS


class CatalogIngestService:
    IGNORED_DISCIPLINES = {"", "ANALYSIS TYPE"}
    DEFAULT_SEARCH_ROOTS = (Path("V:/RAPORLAR"), Path("V:/"))

    def __init__(self, session: Session) -> None:
        self.session = session
        self.catalog_service = CatalogService(session)
        self._file_index: dict[str, Path] | None = None

    def ingest_sample_per_discipline(
        self,
        per_discipline: int = 2,
        dry_run: bool = True,
        scan_limit_per_discipline: int = 25,
    ) -> dict:
        per_discipline = max(1, min(per_discipline, 10))
        scan_limit_per_discipline = max(per_discipline, min(scan_limit_per_discipline, 500))
        disciplines = self._disciplines()

        items: list[dict] = []
        summary: dict[str, dict] = {}
        for discipline in disciplines:
            picked = 0
            scanned = 0
            missing = 0
            entries = self._entries_for_discipline(discipline, limit=scan_limit_per_discipline)
            for entry in entries:
                if picked >= per_discipline:
                    break
                scanned += 1
                resolved_file = self._resolve_entry_file(entry)
                if resolved_file is None:
                    missing += 1
                    continue

                item = self._ingest_or_preview(entry, resolved_file, dry_run=dry_run)
                items.append(item)
                picked += 1

            summary[discipline] = {
                "requested": per_discipline,
                "picked": picked,
                "scanned": scanned,
                "missing_before_pick": missing,
            }

        return {
            "dry_run": dry_run,
            "per_discipline": per_discipline,
            "disciplines_seen": len(disciplines),
            "files_selected": len(items),
            "ingested_count": sum(1 for item in items if item["status"] == "ingested"),
            "duplicate_count": sum(1 for item in items if item["status"] == "duplicate"),
            "found_count": sum(1 for item in items if item["status"] == "found"),
            "error_count": sum(1 for item in items if item["status"] == "error"),
            "summary": summary,
            "items": items,
        }

    def catalog_table(self, limit: int = 2000) -> dict:
        limit = max(20, min(limit, 5000))
        entries = self.session.execute(
            select(ReportCatalogEntry)
            .where(ReportCatalogEntry.discipline.notin_(self.IGNORED_DISCIPLINES))
            .order_by(ReportCatalogEntry.id.asc())
            .limit(limit)
        ).scalars().all()
        matched_documents = self.catalog_service._match_documents(entries)
        embedding_stats = self._embedding_stats(matched_documents.values())
        rows = [
            self._catalog_row_payload(
                entry,
                matched_document_id=matched_documents.get(entry.id),
                embedding_stats=embedding_stats,
            )
            for entry in entries
        ]
        ingested = [row for row in rows if row["matched_document_id"]]
        pending = [row for row in rows if not row["matched_document_id"]]
        embedded = [row for row in ingested if row["embedding_status"] == "complete"]
        embedding_pending = [row for row in ingested if row["embedding_status"] != "complete"]
        return {
            "total_seen": len(rows),
            "ingested_count": len(ingested),
            "pending_count": len(pending),
            "embedded_count": len(embedded),
            "embedding_pending_count": len(embedding_pending),
            "ingested": ingested,
            "pending": pending,
            "embedded": embedded,
            "embedding_pending": embedding_pending,
        }

    def ingest_catalog_entries(self, catalog_entry_ids: list[int]) -> dict:
        normalized_ids = self._normalize_entry_ids(catalog_entry_ids)
        if not normalized_ids:
            return {
                "requested_count": 0,
                "ingested_count": 0,
                "duplicate_count": 0,
                "error_count": 0,
                "items": [],
            }

        entries = self.session.execute(
            select(ReportCatalogEntry).where(ReportCatalogEntry.id.in_(normalized_ids))
        ).scalars().all()
        entries_by_id = {entry.id: entry for entry in entries}
        items: list[dict] = []
        for entry_id in normalized_ids:
            entry = entries_by_id.get(entry_id)
            if entry is None:
                items.append(
                    {
                        "catalog_entry_id": entry_id,
                        "discipline": "",
                        "report_code": "",
                        "vehicle_name": "",
                        "report_title": "",
                        "source_path": "",
                        "document_id": None,
                        "status": "error",
                        "error": "Catalog entry not found.",
                    }
                )
                continue

            resolved_file = self._resolve_entry_file(entry)
            if resolved_file is None:
                items.append(
                    {
                        "catalog_entry_id": entry.id,
                        "discipline": entry.discipline,
                        "report_code": entry.report_code,
                        "vehicle_name": entry.vehicle_name,
                        "report_title": entry.report_title,
                        "source_path": entry.source_path or entry.report_code,
                        "document_id": None,
                        "status": "error",
                        "error": "PDF/DOCX file could not be found from catalog path.",
                    }
                )
                continue

            items.append(self._ingest_or_preview(entry, resolved_file, dry_run=False))

        return {
            "requested_count": len(normalized_ids),
            "ingested_count": sum(1 for item in items if item["status"] == "ingested"),
            "duplicate_count": sum(1 for item in items if item["status"] == "duplicate"),
            "error_count": sum(1 for item in items if item["status"] == "error"),
            "items": items,
        }

    def _ingest_or_preview(self, entry: ReportCatalogEntry, source_path: Path, dry_run: bool) -> dict:
        base_payload = {
            "catalog_entry_id": entry.id,
            "discipline": entry.discipline,
            "report_code": entry.report_code,
            "vehicle_name": entry.vehicle_name,
            "report_title": entry.report_title,
            "source_path": str(source_path),
            "document_id": None,
            "status": "found",
            "error": None,
        }
        if dry_run:
            return base_payload

        try:
            result = IngestService(self.session).ingest(source_path, original_file_name=source_path.name)
            return {
                **base_payload,
                "document_id": result.get("document_id"),
                "status": result.get("status", "ingested"),
                "error": None,
            }
        except Exception as exc:
            self.session.rollback()
            return {
                **base_payload,
                "status": "error",
                "error": str(exc),
            }

    def _catalog_row_payload(
        self,
        entry: ReportCatalogEntry,
        matched_document_id: int | None = None,
        embedding_stats: dict[int, dict] | None = None,
    ) -> dict:
        stats = (embedding_stats or {}).get(matched_document_id or 0, {"chunk_count": 0, "embedding_count": 0})
        chunk_count = int(stats["chunk_count"])
        embedding_count = int(stats["embedding_count"])
        embedding_status = self._embedding_status(chunk_count=chunk_count, embedding_count=embedding_count, is_ingested=bool(matched_document_id))
        return {
            "id": entry.id,
            "report_code": entry.report_code,
            "vehicle_name": entry.vehicle_name,
            "report_title": entry.report_title,
            "discipline": entry.discipline,
            "report_date": entry.report_date,
            "authors": entry.authors,
            "source_path": entry.source_path,
            "matched_document_id": matched_document_id,
            "status": "ingested" if matched_document_id else "pending",
            "chunk_count": chunk_count,
            "embedding_count": embedding_count,
            "embedding_status": embedding_status,
        }

    def _embedding_stats(self, document_ids) -> dict[int, dict]:
        normalized_ids = [document_id for document_id in {int(value) for value in document_ids if value} if document_id > 0]
        if not normalized_ids:
            return {}
        rows = self.session.execute(
            select(
                DocumentChunk.document_id,
                func.count(DocumentChunk.id).label("chunk_count"),
                func.count(ChunkEmbedding.chunk_id).label("embedding_count"),
            )
            .outerjoin(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
            .where(DocumentChunk.document_id.in_(normalized_ids))
            .group_by(DocumentChunk.document_id)
        ).all()
        return {
            int(row.document_id): {
                "chunk_count": int(row.chunk_count),
                "embedding_count": int(row.embedding_count),
            }
            for row in rows
        }

    @staticmethod
    def _embedding_status(chunk_count: int, embedding_count: int, is_ingested: bool) -> str:
        if not is_ingested:
            return "not_ingested"
        if chunk_count <= 0:
            return "missing"
        if embedding_count >= chunk_count:
            return "complete"
        if embedding_count > 0:
            return "partial"
        return "missing"

    @staticmethod
    def _normalize_entry_ids(catalog_entry_ids: list[int]) -> list[int]:
        normalized: list[int] = []
        seen: set[int] = set()
        for raw_value in catalog_entry_ids:
            try:
                entry_id = int(raw_value)
            except (TypeError, ValueError):
                continue
            if entry_id <= 0 or entry_id in seen:
                continue
            seen.add(entry_id)
            normalized.append(entry_id)
        return normalized[:100]

    def _disciplines(self) -> list[str]:
        rows = self.session.execute(
            select(ReportCatalogEntry.discipline)
            .where(ReportCatalogEntry.discipline.notin_(self.IGNORED_DISCIPLINES))
            .group_by(ReportCatalogEntry.discipline)
            .order_by(func.count(ReportCatalogEntry.id).desc())
        ).all()
        return [row.discipline for row in rows if row.discipline not in self.IGNORED_DISCIPLINES]

    def _entries_for_discipline(self, discipline: str, limit: int) -> list[ReportCatalogEntry]:
        return self.session.execute(
            select(ReportCatalogEntry)
            .where(ReportCatalogEntry.discipline == discipline)
            .order_by(
                ReportCatalogEntry.source_path.desc(),
                ReportCatalogEntry.report_date.desc(),
                ReportCatalogEntry.id.desc(),
            )
            .limit(limit)
        ).scalars().all()

    def _resolve_entry_file(self, entry: ReportCatalogEntry) -> Path | None:
        raw_candidates = [
            entry.source_path or "",
            entry.report_code or "",
        ]
        for raw_value in raw_candidates:
            for candidate in self._path_candidates(raw_value):
                if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
                    return candidate
                if candidate.is_dir():
                    nested = self._first_supported_file(candidate, preferred_stem=Path(raw_value).name)
                    if nested:
                        return nested
        return None

    def _path_candidates(self, raw_value: str) -> list[Path]:
        cleaned = raw_value.strip().strip('"')
        if not cleaned:
            return []

        direct = Path(cleaned)
        candidates = [direct]
        if direct.suffix.lower() not in SUPPORTED_EXTENSIONS:
            candidates.extend(Path(f"{cleaned}{suffix}") for suffix in SUPPORTED_EXTENSIONS)

        if not direct.is_absolute():
            for root in self.DEFAULT_SEARCH_ROOTS:
                rooted = root / cleaned
                candidates.append(rooted)
                if rooted.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    candidates.extend(Path(f"{rooted}{suffix}") for suffix in SUPPORTED_EXTENSIONS)

        deduped: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = str(candidate).casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)
        return deduped

    @staticmethod
    def _first_supported_file(directory: Path, preferred_stem: str = "") -> Path | None:
        preferred = CatalogIngestService._normalize_stem(preferred_stem)
        direct_files = [
            path for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        if not direct_files:
            return None
        if preferred:
            for path in direct_files:
                if preferred and preferred in CatalogIngestService._normalize_stem(path.stem):
                    return path
        return sorted(direct_files, key=lambda path: path.name.casefold())[0]

    def _resolve_from_index(self, raw_value: str) -> Path | None:
        key = self._normalize_stem(Path(raw_value.strip()).name)
        if not key:
            return None
        file_index = self._build_file_index()
        if key in file_index:
            return file_index[key]
        for indexed_key, indexed_path in file_index.items():
            if key and (key in indexed_key or indexed_key in key):
                return indexed_path
        return None

    def _resolve_by_targeted_search(self, entry: ReportCatalogEntry) -> Path | None:
        target_keys = self._target_keys(entry)
        if not target_keys:
            return None
        for directory in self._target_directories(entry):
            found = self._find_matching_file(directory, target_keys)
            if found:
                return found
        return None

    def _target_keys(self, entry: ReportCatalogEntry) -> list[str]:
        raw_values = [entry.source_path or "", entry.report_code or ""]
        keys: list[str] = []
        for raw_value in raw_values:
            stem = self._normalize_stem(Path(raw_value.strip()).name)
            if len(stem) >= 5 and stem not in keys:
                keys.append(stem)
        return keys

    def _target_directories(self, entry: ReportCatalogEntry) -> list[Path]:
        candidate_dirs: list[Path] = []
        raw_path = Path((entry.source_path or entry.report_code or "").strip())
        if raw_path.parts and not raw_path.is_absolute():
            rooted = self.DEFAULT_SEARCH_ROOTS[0] / raw_path.parts[0]
            if rooted.exists() and rooted.is_dir():
                candidate_dirs.append(rooted)

        tokens = self._entry_search_tokens(entry)
        for child in self._root_children():
            normalized_child = self._normalize_stem(child.name)
            if any(token and (token in normalized_child or normalized_child in token) for token in tokens):
                candidate_dirs.append(child)
            if len(candidate_dirs) >= 10:
                break

        deduped: list[Path] = []
        seen: set[str] = set()
        for directory in candidate_dirs:
            key = str(directory).casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(directory)
        return deduped

    def _root_children(self) -> list[Path]:
        root = self.DEFAULT_SEARCH_ROOTS[0]
        if not root.exists() or not root.is_dir():
            return []
        return [path for path in root.iterdir() if path.is_dir()]

    def _entry_search_tokens(self, entry: ReportCatalogEntry) -> list[str]:
        text = f"{entry.report_code} {entry.vehicle_name} {entry.report_title}"
        raw_tokens = [
            self._normalize_stem(token)
            for token in text.replace("_", " ").replace("-", " ").split()
        ]
        ignored = {"2021", "2022", "2023", "2024", "2025", "2026", "raporu", "analiz", "analizi", "rev"}
        return [token for token in raw_tokens if len(token) >= 3 and token not in ignored][:12]

    def _find_matching_file(self, directory: Path, target_keys: list[str]) -> Path | None:
        scanned = 0
        for dirpath, _, filenames in os.walk(directory):
            for file_name in filenames:
                suffix = Path(file_name).suffix.lower()
                if suffix not in SUPPORTED_EXTENSIONS:
                    continue
                scanned += 1
                stem = self._normalize_stem(Path(file_name).stem)
                if any(target and (target in stem or stem in target) for target in target_keys):
                    return Path(dirpath) / file_name
                if scanned >= 250:
                    return None
        return None

    def _build_file_index(self) -> dict[str, Path]:
        if self._file_index is not None:
            return self._file_index

        index: dict[str, Path] = {}
        for root in self.DEFAULT_SEARCH_ROOTS:
            if not root.exists() or not root.is_dir():
                continue
            for dirpath, _, filenames in os.walk(root):
                for file_name in filenames:
                    suffix = Path(file_name).suffix.lower()
                    if suffix not in SUPPORTED_EXTENSIONS:
                        continue
                    path = Path(dirpath) / file_name
                    key = self._normalize_stem(path.stem)
                    if key and key not in index:
                        index[key] = path
                if len(index) >= 50000:
                    break
        self._file_index = index
        return index

    @staticmethod
    def _normalize_stem(value: str) -> str:
        return "".join(character for character in value.casefold() if character.isalnum())
