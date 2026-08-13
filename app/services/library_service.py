from __future__ import annotations

from datetime import datetime
from itertools import islice
import os
from pathlib import Path
from typing import Iterable


class LibraryService:
    """Build a bounded, read-only tree of supported report files."""

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx"}
    MAX_DOCUMENTS = 800
    MAX_DIRECTORIES = 800
    MAX_DEPTH = 10
    MAX_ENTRIES_PER_DIRECTORY = 2_000

    def __init__(self, allowed_roots: Iterable[str | Path]) -> None:
        self.allowed_roots = tuple(Path(root).expanduser() for root in allowed_roots)
        if not self.allowed_roots:
            raise ValueError("Kütüphane için izinli bir kök klasör tanımlanmadı.")

    def scan(self, root_path: str, limit: int = 500) -> dict:
        raw_path = root_path.strip()
        if not raw_path:
            raise ValueError("Kök klasör yolu gerekli.")

        if self._is_network_or_device_path(raw_path):
            raise ValueError("Doğrudan ağ ve aygıt yolları desteklenmiyor; tanımlı sürücü yolunu kullanın.")

        root = Path(raw_path).expanduser()
        if not root.is_absolute():
            raise ValueError("Kök klasör yolu mutlak olmalıdır.")
        lexical_root = Path(os.path.abspath(str(root)))
        allowed_root = self._matching_allowed_root(lexical_root)
        if allowed_root is None:
            raise ValueError("Bu klasör Kütüphane için izinli köklerin dışında.")
        if not root.exists():
            raise ValueError("Kök klasör bulunamadı.")
        if not root.is_dir():
            raise ValueError("Verilen yol bir klasör değil.")

        root = root.resolve(strict=True)
        resolved_allowed_root = allowed_root.resolve(strict=False)
        if not self._is_within(root, resolved_allowed_root):
            raise ValueError("Kök klasör izinli alanın dışına yönleniyor.")
        if root.is_symlink() or (hasattr(root, "is_junction") and root.is_junction()):
            raise ValueError("Bağlantı ve junction klasörleri kök olarak kullanılamaz.")

        document_limit = max(1, min(int(limit), self.MAX_DOCUMENTS))
        state = {
            "document_count": 0,
            "directory_count": 0,
            "inaccessible_count": 0,
            "truncated": False,
        }

        tree = self._scan_directory(
            directory=root,
            root=root,
            depth=0,
            document_limit=document_limit,
            state=state,
        )
        if tree is None:
            tree = self._directory_node(root, root, [])

        return {
            "root_path": str(root),
            "document_count": state["document_count"],
            "directory_count": state["directory_count"],
            "inaccessible_count": state["inaccessible_count"],
            "truncated": state["truncated"],
            "tree": tree,
        }

    def _scan_directory(
        self,
        directory: Path,
        root: Path,
        depth: int,
        document_limit: int,
        state: dict,
    ) -> dict | None:
        if state["directory_count"] >= self.MAX_DIRECTORIES:
            state["truncated"] = True
            return None
        state["directory_count"] += 1

        try:
            entries = list(islice(directory.iterdir(), self.MAX_ENTRIES_PER_DIRECTORY + 1))
        except OSError:
            state["inaccessible_count"] += 1
            return None

        if len(entries) > self.MAX_ENTRIES_PER_DIRECTORY:
            entries = entries[: self.MAX_ENTRIES_PER_DIRECTORY]
            state["truncated"] = True

        entries.sort(key=self._entry_sort_key)
        children: list[dict] = []

        for entry in entries:
            if state["document_count"] >= document_limit:
                state["truncated"] = True
                break
            try:
                if entry.is_symlink() or (
                    hasattr(entry, "is_junction") and entry.is_junction()
                ):
                    continue
                if entry.is_dir():
                    if depth >= self.MAX_DEPTH:
                        state["truncated"] = True
                        continue
                    child = self._scan_directory(
                        directory=entry,
                        root=root,
                        depth=depth + 1,
                        document_limit=document_limit,
                        state=state,
                    )
                    if child and child["children"]:
                        children.append(child)
                    continue
                if not entry.is_file() or entry.suffix.casefold() not in self.SUPPORTED_EXTENSIONS:
                    continue
                children.append(self._document_node(entry, root))
                state["document_count"] += 1
            except OSError:
                state["inaccessible_count"] += 1

        if depth > 0 and not children:
            return None
        return self._directory_node(directory, root, children)

    @staticmethod
    def _directory_node(directory: Path, root: Path, children: list[dict]) -> dict:
        try:
            relative_path = str(directory.relative_to(root))
        except ValueError:
            relative_path = directory.name
        return {
            "type": "directory",
            "name": directory.name or directory.anchor or str(directory),
            "path": str(directory),
            "relative_path": "" if relative_path == "." else relative_path,
            "children": children,
        }

    @staticmethod
    def _document_node(document: Path, root: Path) -> dict:
        stat = document.stat()
        return {
            "type": "document",
            "name": document.name,
            "path": str(document),
            "relative_path": str(document.relative_to(root)),
            "extension": document.suffix.casefold().lstrip(".").upper(),
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="minutes"),
        }

    @staticmethod
    def _entry_sort_key(entry: Path) -> tuple[bool, str]:
        try:
            is_directory = entry.is_dir()
        except OSError:
            is_directory = False
        return (not is_directory, entry.name.casefold())

    def _matching_allowed_root(self, candidate: Path) -> Path | None:
        for allowed_root in self.allowed_roots:
            raw_allowed = str(allowed_root)
            if self._is_network_or_device_path(raw_allowed) or not allowed_root.is_absolute():
                continue
            normalized_allowed = Path(os.path.abspath(raw_allowed))
            if self._is_within(candidate, normalized_allowed):
                return normalized_allowed
        return None

    @staticmethod
    def _is_within(candidate: Path, root: Path) -> bool:
        try:
            os.path.commonpath((str(candidate), str(root)))
        except ValueError:
            return False
        return os.path.normcase(os.path.commonpath((str(candidate), str(root)))) == os.path.normcase(str(root))

    @staticmethod
    def _is_network_or_device_path(value: str) -> bool:
        normalized = value.strip().replace("/", "\\")
        return normalized.startswith("\\\\") or normalized.startswith("\\?\\") or normalized.startswith("\\.\\")
