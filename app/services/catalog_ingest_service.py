from __future__ import annotations

from pathlib import Path
import os
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import CatalogDocumentLink, ChunkEmbedding, DocumentChunk, ReportCatalogEntry
from .catalog_service import CatalogService
from .ingest_service import IngestService, SUPPORTED_EXTENSIONS


class CatalogIngestService:
    IGNORED_DISCIPLINES = {"", "ANALYSIS TYPE"}
    DEFAULT_SEARCH_ROOTS = (Path("V:/RAPORLAR"), Path("V:/"))
    MAX_DIRECTORY_FILES = 150
    MAX_DIRECTORY_DEPTH = 2

    def __init__(self, session: Session) -> None:
        self.session = session
        self.catalog_service = CatalogService(session)

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
                        "error": "PDF/DOCX/PPTX file could not be found from the direct catalog path.",
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

    def ingest_catalog_candidate(self, catalog_entry_id: int, file_path: str) -> dict:
        entry = self.session.get(ReportCatalogEntry, catalog_entry_id)
        if entry is None:
            return {
                "catalog_entry_id": catalog_entry_id,
                "discipline": "",
                "report_code": "",
                "vehicle_name": "",
                "report_title": "",
                "source_path": file_path,
                "document_id": None,
                "status": "error",
                "error": "Catalog entry not found.",
            }

        candidate_map = {
            item["path"].casefold(): item
            for item in self._entry_file_candidates(entry)
        }
        selected = candidate_map.get(str(Path(file_path)).casefold()) or candidate_map.get(file_path.casefold())
        if selected is None:
            return {
                "catalog_entry_id": entry.id,
                "discipline": entry.discipline,
                "report_code": entry.report_code,
                "vehicle_name": entry.vehicle_name,
                "report_title": entry.report_title,
                "source_path": file_path,
                "document_id": None,
                "status": "error",
                "error": "Selected file is not a valid candidate for this catalog entry.",
            }

        return self._ingest_or_preview(
            entry,
            Path(selected["path"]),
            dry_run=False,
            match_method="catalog_candidate",
        )

    def _ingest_or_preview(
        self,
        entry: ReportCatalogEntry,
        source_path: Path,
        dry_run: bool,
        match_method: str = "catalog_ingest",
    ) -> dict:
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
            document_id = result.get("document_id")
            if document_id:
                self._link_catalog_document(
                    catalog_entry_id=entry.id,
                    document_id=int(document_id),
                    source_path=str(source_path),
                    match_method=match_method,
                )
            return {
                **base_payload,
                "document_id": document_id,
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
        candidates = self._entry_file_candidates(entry)
        if candidates:
            return Path(candidates[0]["path"])
        return None

    def file_candidates_for_entry(self, catalog_entry_id: int) -> dict:
        entry = self.session.get(ReportCatalogEntry, catalog_entry_id)
        if entry is None:
            return {
                "catalog_entry_id": catalog_entry_id,
                "items": [],
                "error": "Catalog entry not found.",
            }
        return {
            "catalog_entry_id": entry.id,
            "report_code": entry.report_code,
            "source_path": entry.source_path,
            "items": self._entry_file_candidates(entry),
            "error": None,
        }

    def _entry_file_candidates(self, entry: ReportCatalogEntry) -> list[dict]:
        raw_candidates = [
            entry.source_path or "",
            entry.report_code or "",
        ]
        candidates: list[dict] = []
        for raw_value in raw_candidates:
            for candidate in self._path_candidates(raw_value):
                if self._is_supported_file(candidate):
                    candidates.append(self._candidate_payload(entry, candidate, "direct_file"))
                    continue
                if self._is_directory(candidate):
                    for nested in self._directory_supported_files(candidate):
                        candidates.append(self._candidate_payload(entry, nested, "folder_candidate"))

        deduped: dict[str, dict] = {}
        for candidate in candidates:
            key = candidate["path"].casefold()
            if key not in deduped or candidate["score"] > deduped[key]["score"]:
                deduped[key] = candidate
        return sorted(deduped.values(), key=lambda item: (-item["score"], item["file_name"].casefold()))

    def _candidate_payload(self, entry: ReportCatalogEntry, path: Path, match_method: str) -> dict:
        return {
            "path": str(path),
            "file_name": path.name,
            "extension": path.suffix.lower(),
            "score": self._candidate_score(entry, path),
            "match_method": match_method,
        }

    def _candidate_score(self, entry: ReportCatalogEntry, path: Path) -> int:
        name_key = self._normalize_stem(path.stem)
        score = {".pdf": 12, ".docx": 9, ".pptx": 7}.get(path.suffix.lower(), 0)
        keys = self._target_keys(entry)
        for key in keys:
            if not key:
                continue
            if key == name_key:
                score += 120
            elif key in name_key or name_key in key:
                score += 70

        tokens = set(self._target_tokens(entry))
        name_tokens = set(self._stem_tokens(path.stem))
        score += len(tokens & name_tokens) * 8
        if any(token in name_tokens for token in {"rapor", "report", "analiz", "analysis"}):
            score += 8
        return score

    def _target_keys(self, entry: ReportCatalogEntry) -> list[str]:
        raw_values = [
            entry.source_path or "",
            entry.report_code or "",
            entry.report_title or "",
        ]
        keys: list[str] = []
        for raw_value in raw_values:
            for variant in self._text_variants(raw_value):
                for value in {variant, Path(variant.strip()).name, Path(variant.strip()).stem}:
                    key = self._normalize_stem(value)
                    if len(key) >= 5 and key not in keys:
                        keys.append(key)
        return keys

    def _target_tokens(self, entry: ReportCatalogEntry) -> list[str]:
        text = " ".join(
            value for value in [
                entry.report_code,
                entry.vehicle_name,
                entry.report_title,
                entry.discipline,
            ]
            if value
        )
        tokens: list[str] = []
        ignored = {"2021", "2022", "2023", "2024", "2025", "2026", "rev", "raporu", "report"}
        for variant in self._text_variants(text):
            for token in self._stem_tokens(variant):
                if len(token) >= 3 and token not in ignored and token not in tokens:
                    tokens.append(token)
        return tokens[:24]

    def _directory_supported_files(self, directory: Path) -> list[Path]:
        if self._is_search_root(directory):
            return []

        files: list[Path] = []
        base_depth = len(directory.parts)
        try:
            for dirpath, dirnames, filenames in os.walk(directory):
                current = Path(dirpath)
                if len(current.parts) - base_depth >= self.MAX_DIRECTORY_DEPTH:
                    dirnames[:] = []
                for file_name in filenames:
                    candidate = current / file_name
                    if candidate.suffix.lower() not in SUPPORTED_EXTENSIONS:
                        continue
                    files.append(candidate)
                    if len(files) >= self.MAX_DIRECTORY_FILES:
                        return files
        except OSError:
            return files
        return files

    def _link_catalog_document(
        self,
        catalog_entry_id: int,
        document_id: int,
        source_path: str,
        match_method: str,
    ) -> None:
        existing = self.session.scalar(
            select(CatalogDocumentLink).where(CatalogDocumentLink.catalog_entry_id == catalog_entry_id)
        )
        if existing:
            existing.document_id = document_id
            existing.source_path = source_path
            existing.match_method = match_method
        else:
            self.session.add(
                CatalogDocumentLink(
                    catalog_entry_id=catalog_entry_id,
                    document_id=document_id,
                    source_path=source_path,
                    match_method=match_method,
                )
            )
        self.session.commit()

    @staticmethod
    def _is_supported_file(path: Path) -> bool:
        try:
            return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        except OSError:
            return False

    @staticmethod
    def _is_directory(path: Path) -> bool:
        try:
            return path.is_dir()
        except OSError:
            return False

    def _is_search_root(self, path: Path) -> bool:
        normalized = str(path).rstrip("\\/").casefold()
        return any(normalized == str(root).rstrip("\\/").casefold() for root in self.DEFAULT_SEARCH_ROOTS)

    @staticmethod
    def _text_variants(value: str) -> list[str]:
        variants = [value]
        for encoding in ("latin1", "cp1252"):
            try:
                repaired = value.encode(encoding).decode("utf-8")
            except UnicodeError:
                continue
            if repaired and repaired not in variants:
                variants.append(repaired)
        return variants

    def _path_candidates(self, raw_value: str) -> list[Path]:
        candidates: list[Path] = []
        for variant in self._text_variants(raw_value):
            cleaned = variant.strip().strip('"')
            if not cleaned:
                continue

            direct = Path(cleaned)
            candidates.append(direct)
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

    @staticmethod
    def _normalize_stem(value: str) -> str:
        return "".join(character for character in value.casefold() if character.isalnum())

    @staticmethod
    def _stem_tokens(value: str) -> list[str]:
        normalized = re.sub(r"[^0-9A-Za-zÇĞİÖŞÜçğıöşü]+", " ", value.casefold())
        return [
            CatalogIngestService._normalize_stem(token)
            for token in normalized.split()
            if len(CatalogIngestService._normalize_stem(token)) >= 2
        ]
