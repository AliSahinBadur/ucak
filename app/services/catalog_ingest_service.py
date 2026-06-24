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
    DEFAULT_SEARCH_ROOTS = (
        Path(r"\\isufile02\argevalidasyon$\RAPORLAR"),
        Path("V:/RAPORLAR"),
        Path("V:/"),
    )
    MAX_DIRECTORY_FILES = 250
    MAX_DIRECTORY_DEPTH = 8
    MAX_DIRECTORY_VISITS = 600
    MAX_REPORT_DIRECTORY_VISITS = 220
    COMMON_REPORT_GROUPS = (
        "",
        "RAPOR",
        "REPORT",
        "DUR",
        "DURABILITY",
        "FAT",
        "FATIGUE",
        "SAFE",
        "SAFETY",
        "TASE",
        "CFD",
        "NVH",
        "VED",
        "TEST",
        "BLAST",
        "DEF",
        "6X6",
        "4X4",
        "8X8",
    )

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

        selected_path = self.validated_candidate_path(entry, file_path)
        if selected_path is None:
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
            selected_path,
            dry_run=False,
            match_method="catalog_candidate",
        )

    def candidate_preview_path(self, catalog_entry_id: int, file_path: str) -> Path | None:
        entry = self.session.get(ReportCatalogEntry, catalog_entry_id)
        if entry is None:
            return None
        return self.validated_candidate_path(entry, file_path)

    def best_candidate_preview_path(self, catalog_entry_id: int) -> Path | None:
        entry = self.session.get(ReportCatalogEntry, catalog_entry_id)
        if entry is None:
            return None
        return self._resolve_entry_file(entry)

    def has_accessible_report_root(self) -> bool:
        return any(self._is_directory(root) for root in self.DEFAULT_SEARCH_ROOTS)

    def validated_candidate_path(self, entry: ReportCatalogEntry, file_path: str) -> Path | None:
        candidate_map = {
            item["path"].casefold(): item
            for item in self._entry_file_candidates(entry)
        }
        selected = candidate_map.get(str(Path(file_path)).casefold()) or candidate_map.get(file_path.casefold())
        if selected is None:
            return None
        return Path(selected["path"])

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
            self._vehicle_report_folder(entry),
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
        for report_directory in self._structured_report_directories(entry):
            if self._is_directory(report_directory):
                for nested in self._directory_supported_files(report_directory):
                    candidates.append(self._candidate_payload(entry, nested, "structured_folder"))

        deduped: dict[str, dict] = {}
        for candidate in candidates:
            key = candidate["path"].casefold()
            if key not in deduped or candidate["score"] > deduped[key]["score"]:
                deduped[key] = candidate
        return sorted(deduped.values(), key=lambda item: (-item["score"], item["file_name"].casefold()))

    def _structured_report_directories(self, entry: ReportCatalogEntry) -> list[Path]:
        report_code = (entry.report_code or "").strip().strip("\\/")
        if not report_code or "\\" in report_code or "/" in report_code:
            return []

        directories: list[Path] = []
        for root in self.DEFAULT_SEARCH_ROOTS:
            if self._should_skip_structured_root(root):
                continue
            for vehicle_dir in self._vehicle_directory_candidates(root, entry):
                for group_dir in self._report_group_directories(vehicle_dir, entry):
                    directories.append(group_dir / report_code)
                directories.extend(self._matching_report_directories(vehicle_dir, entry))
        return self._dedupe_paths(directories)

    def _vehicle_directory_candidates(self, root: Path, entry: ReportCatalogEntry) -> list[Path]:
        keys = self._vehicle_keys(entry)
        if not keys:
            return []

        candidates: list[tuple[int, Path]] = []
        for raw_name in self._vehicle_name_variants(entry):
            path = root / raw_name
            if self._is_directory(path):
                candidates.append((150, path))

        try:
            children = [path for path in root.iterdir() if path.is_dir()]
        except OSError:
            children = []

        for child in children[:600]:
            score = self._directory_name_score(child.name, keys)
            if score > 0:
                candidates.append((score, child))

        best: dict[str, tuple[int, Path]] = {}
        for score, path in candidates:
            key = str(path).casefold()
            if key not in best or score > best[key][0]:
                best[key] = (score, path)
        return [
            path
            for score, path in sorted(best.values(), key=lambda item: (-item[0], item[1].name.casefold()))[:18]
        ]

    def _matching_report_directories(self, vehicle_dir: Path, entry: ReportCatalogEntry) -> list[Path]:
        report_keys = self._report_directory_keys(entry)
        if not report_keys:
            return []
        matches: list[Path] = []
        visited = 0
        try:
            for parent in self._report_group_directories(vehicle_dir, entry):
                if visited >= self.MAX_REPORT_DIRECTORY_VISITS:
                    break
                try:
                    children = [child for child in parent.iterdir() if child.is_dir()]
                except OSError:
                    continue
                for child in children[: self.MAX_REPORT_DIRECTORY_VISITS - visited]:
                    visited += 1
                    if not child.is_dir():
                        continue
                    child_key = self._normalize_stem(child.name)
                    if self._matches_any_key(child_key, report_keys):
                        matches.append(child)
                        if len(matches) >= 25:
                            return matches
        except OSError:
            return matches
        return matches[:25]

    def _report_group_directories(self, vehicle_dir: Path, entry: ReportCatalogEntry) -> list[Path]:
        raw_names = list(self.COMMON_REPORT_GROUPS)
        raw_names.extend(self._discipline_group_names(entry.discipline or ""))
        raw_names.extend(self._report_code_group_names(entry.report_code or ""))

        directories = [vehicle_dir]
        for raw_name in raw_names:
            cleaned = raw_name.strip().strip("\\/")
            if not cleaned:
                continue
            directories.append(vehicle_dir / cleaned)
            directories.append(vehicle_dir / cleaned.replace(" ", "_"))
            directories.append(vehicle_dir / cleaned.replace(" ", ""))
        directories.extend(self._matching_group_directories(vehicle_dir, raw_names))
        return self._dedupe_paths(directories)

    def _matching_group_directories(self, vehicle_dir: Path, raw_names: list[str]) -> list[Path]:
        group_keys = [
            self._normalize_stem(name)
            for name in raw_names
            if len(self._normalize_stem(name)) >= 3
        ]
        if not group_keys:
            return []
        try:
            children = [path for path in vehicle_dir.iterdir() if path.is_dir()]
        except OSError:
            return []

        matches: list[Path] = []
        for child in children[:250]:
            child_key = self._normalize_stem(child.name)
            if any(key == child_key or key in child_key or child_key in key for key in group_keys):
                matches.append(child)
        return matches[:30]

    @staticmethod
    def _discipline_group_names(discipline: str) -> list[str]:
        normalized = discipline.strip().upper()
        names = [normalized]
        aliases = {
            "DURABILITY": ["DUR", "DURABILITY"],
            "DURABILITY - VED": ["DUR", "DURABILITY", "VED"],
            "FATIGUE": ["FAT", "FATIGUE"],
            "SAFETY": ["SAFE", "SAFETY"],
            "CFD": ["CFD", "TASE"],
            "NVH": ["NVH"],
            "VED": ["VED"],
            "TEST": ["TEST"],
            "BLAST": ["BLAST"],
            "BLAST & BALISTIC": ["BLAST", "DEF"],
        }
        names.extend(aliases.get(normalized, []))
        return names

    @staticmethod
    def _report_code_group_names(report_code: str) -> list[str]:
        names: list[str] = []
        upper = report_code.upper()
        for token in ("DUR", "FAT", "SAFE", "SAFETY", "TASE", "CFD", "NVH", "VED", "TEST", "BLAST", "DEF"):
            if token in upper:
                names.append(token)
        for token in ("6X6", "4X4", "8X8", "P0", "P1", "RETROFIT"):
            if token in upper:
                names.append(token)
        return names

    def _report_directory_keys(self, entry: ReportCatalogEntry) -> list[str]:
        report_code = (entry.report_code or "").strip()
        if not report_code or "\\" in report_code or "/" in report_code:
            return []
        keys = [self._normalize_stem(report_code)]
        compact = re.sub(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", "-", report_code)
        keys.append(self._normalize_stem(compact))
        return [key for key in dict.fromkeys(keys) if len(key) >= 5]

    @staticmethod
    def _matches_any_key(value: str, keys: list[str]) -> bool:
        return any(key == value or key in value or value in key for key in keys)

    def _vehicle_keys(self, entry: ReportCatalogEntry) -> list[str]:
        values = self._vehicle_name_variants(entry)
        values.extend(self._vehicle_values_from_report_code(entry.report_code or ""))
        keys: list[str] = []
        for value in values:
            key = self._normalize_stem(value)
            if len(key) >= 3 and key not in keys:
                keys.append(key)
        return keys

    def _vehicle_name_variants(self, entry: ReportCatalogEntry) -> list[str]:
        vehicle = (entry.vehicle_name or "").strip()
        if not vehicle:
            return []
        variants = [vehicle, vehicle.replace(" ", "_"), vehicle.replace(" ", "")]
        lowered = vehicle.casefold()
        suffixes = (" gen2", " mux", " xl", " p0", " p1", " lf", " hp", " long", " short")
        for suffix in suffixes:
            if lowered.endswith(suffix):
                variants.append(vehicle[: -len(suffix)].strip())
        first_token = re.split(r"[\s_/-]+", vehicle.strip())[0]
        if len(first_token) >= 4:
            variants.append(first_token)
        return [value for value in variants if value]

    def _vehicle_values_from_report_code(self, report_code: str) -> list[str]:
        parts = [part for part in re.split(r"[-_\s]+", report_code.strip()) if part]
        if not parts:
            return []
        ignored = {
            "2021", "2022", "2023", "2024", "2025", "2026",
            "dur", "fat", "safe", "tase", "nvh", "ved", "test", "blast", "def", "cfd",
            "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
            "rev", "rev01", "rev02", "rev03", "rev04",
        }
        vehicle_parts: list[str] = []
        for part in parts[1:]:
            normalized = self._normalize_stem(part)
            if normalized in ignored or normalized.isdigit():
                break
            vehicle_parts.append(part)
            if len(vehicle_parts) >= 4:
                break
        values = [" ".join(vehicle_parts), "".join(vehicle_parts)]
        values.extend(vehicle_parts)
        if vehicle_parts:
            values.append(vehicle_parts[0])
        if len(vehicle_parts) > 1:
            values.append(" ".join(vehicle_parts[1:]))
            values.append("".join(vehicle_parts[1:]))
        return [value for value in values if value]

    @staticmethod
    def _directory_name_score(name: str, keys: list[str]) -> int:
        name_key = CatalogIngestService._normalize_stem(name)
        score = 0
        for key in keys:
            if key == name_key:
                score = max(score, 140)
            elif key in name_key or name_key in key:
                score = max(score, 95)
            elif len(key) >= 5 and key[:5] in name_key:
                score = max(score, 45)
        return score

    def _should_skip_structured_root(self, root: Path) -> bool:
        root_key = str(root).rstrip("\\/").casefold()
        return root_key.endswith(":") or root_key.endswith(":/") or root_key.endswith(":\\")

    @staticmethod
    def _dedupe_paths(paths: list[Path]) -> list[Path]:
        deduped: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            key = str(path).casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(path)
        return deduped

    @staticmethod
    def _vehicle_report_folder(entry: ReportCatalogEntry) -> str:
        vehicle = (entry.vehicle_name or "").strip().strip("\\/")
        report_code = (entry.report_code or "").strip().strip("\\/")
        if not vehicle or not report_code:
            return ""
        return str(Path(vehicle) / report_code)

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
        queue: list[tuple[Path, int]] = [(directory, 0)]
        visited = 0
        try:
            while queue and visited < self.MAX_DIRECTORY_VISITS:
                current, depth = queue.pop(0)
                visited += 1
                child_dirs: list[Path] = []
                for child in current.iterdir():
                    if child.is_file() and child.suffix.lower() in SUPPORTED_EXTENSIONS:
                        files.append(child)
                        if len(files) >= self.MAX_DIRECTORY_FILES:
                            return files
                    elif child.is_dir() and depth < self.MAX_DIRECTORY_DEPTH:
                        child_dirs.append(child)

                if files:
                    # Stop at the first depth that contains report files. This avoids
                    # crawling unrelated archive folders under the same report code.
                    same_depth_dirs = [item for item in queue if item[1] == depth]
                    if not same_depth_dirs:
                        return files
                for child_dir in sorted(child_dirs, key=lambda path: path.name.casefold()):
                    queue.append((child_dir, depth + 1))
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
            cleaned = variant.strip().strip('"').replace("/", "\\")
            if not cleaned:
                continue

            for path_text in self._relative_root_variants(cleaned):
                direct = Path(path_text)
                candidates.append(direct)
                if direct.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    candidates.extend(Path(f"{path_text}{suffix}") for suffix in SUPPORTED_EXTENSIONS)
                if direct.is_absolute():
                    continue
                for root in self.DEFAULT_SEARCH_ROOTS:
                    rooted = root / path_text
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
    def _relative_root_variants(value: str) -> list[str]:
        if value.startswith("\\\\") or re.match(r"^[A-Za-z]:", value):
            return [value]
        cleaned = value.strip().strip("\\/")
        variants = [cleaned]
        parts = [part for part in re.split(r"[\\/]+", cleaned) if part]
        if parts and CatalogIngestService._normalize_stem(parts[0]) == "raporlar":
            variants.append(str(Path(*parts[1:])))
        return [variant for variant in dict.fromkeys(variants) if variant]

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
