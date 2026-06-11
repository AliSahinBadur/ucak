from __future__ import annotations

import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Document, ReportCatalogEntry
from .catalog_service import CatalogService


class GraphService:
    IGNORED_DISCIPLINES = {"", "ANALYSIS TYPE"}

    def __init__(self, session: Session) -> None:
        self.session = session
        self.catalog_service = CatalogService(session)

    def overview(self, limit: int = 120) -> dict:
        limit = max(20, min(limit, 300))
        entries = self.session.execute(
            select(ReportCatalogEntry)
            .where(ReportCatalogEntry.discipline.notin_(self.IGNORED_DISCIPLINES))
            .order_by(ReportCatalogEntry.id.desc())
            .limit(limit)
        ).scalars().all()
        matched_documents = self.catalog_service._match_documents(entries)
        documents = {
            document.id: document
            for document in self.session.execute(select(Document)).scalars().all()
        }

        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        tag_counter: Counter[str] = Counter()

        self._add_node(nodes, "root:reports", "Raporlar", "root")
        for entry in entries:
            document_id = matched_documents.get(entry.id)
            document = documents.get(document_id or 0)
            report_node_id = f"document:{document_id}" if document else f"catalog:{entry.id}"
            report_label = document.title if document else entry.report_code
            report_status = "ingested" if document else "pending"
            self._add_node(
                nodes,
                report_node_id,
                report_label,
                "document" if document else "catalog",
                status=report_status,
                catalog_entry_id=entry.id,
                document_id=document_id,
            )
            self._add_edge(edges, "root:reports", report_node_id, "contains")

            for tag in self._entry_tags(entry, report_status=report_status):
                tag_id = f"tag:{tag['type']}:{self._slug(tag['label'])}"
                self._add_node(
                    nodes,
                    tag_id,
                    tag["label"],
                    "tag",
                    tag_type=tag["type"],
                )
                self._add_edge(edges, report_node_id, tag_id, tag["type"])
                tag_counter[f"{tag['type']}::{tag['label']}"] += 1

        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": list(nodes.values()),
            "edges": edges,
            "tags": self._tag_payload(tag_counter),
        }

    def _entry_tags(self, entry: ReportCatalogEntry, report_status: str) -> list[dict]:
        tags = [
            {"type": "status", "label": "Iceride" if report_status == "ingested" else "Iceri alinacak"},
        ]
        if entry.vehicle_name:
            tags.append({"type": "vehicle", "label": entry.vehicle_name.strip()})
        if entry.discipline:
            tags.append({"type": "discipline", "label": entry.discipline.strip()})
        year = self._year(entry)
        if year:
            tags.append({"type": "year", "label": year})
        for author in self._authors(entry.authors or "")[:3]:
            tags.append({"type": "author", "label": author})
        return tags

    @staticmethod
    def _authors(value: str) -> list[str]:
        parts = re.split(r"\s*(?:-|/|,|;|\+|\&|\bVE\b)\s*", value, flags=re.IGNORECASE)
        authors: list[str] = []
        for part in parts:
            cleaned = " ".join(part.split()).strip()
            if len(cleaned) >= 3 and cleaned not in authors:
                authors.append(cleaned)
        return authors

    @staticmethod
    def _year(entry: ReportCatalogEntry) -> str:
        text = f"{entry.report_date or ''} {entry.report_code or ''}"
        match = re.search(r"\b(20\d{2})\b", text)
        return match.group(1) if match else ""

    @staticmethod
    def _add_node(nodes: dict[str, dict], node_id: str, label: str, node_type: str, **extra) -> None:
        if node_id in nodes:
            return
        nodes[node_id] = {
            "id": node_id,
            "label": label,
            "type": node_type,
            **extra,
        }

    @staticmethod
    def _add_edge(edges: list[dict], source: str, target: str, label: str) -> None:
        edges.append({"source": source, "target": target, "label": label})

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:80] or "tag"

    @staticmethod
    def _tag_payload(counter: Counter[str]) -> list[dict]:
        tags = []
        for key, count in counter.most_common(80):
            tag_type, label = key.split("::", 1)
            tags.append({"type": tag_type, "label": label, "count": count})
        return tags
