from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from ipaddress import ip_address
import socket
from typing import Iterable

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db.models import AnalyticsOperation, AnalyticsSession, utc_now


APPLICATIONS: tuple[dict[str, object], ...] = (
    {
        "id": "big_agent",
        "name": "SmartCAE AI",
        "group": "Bilgi ve AI",
        "port": 8002,
        "path": "/smartcae-v2",
        "icon": "🤖",
        "description": "Kaynaklı mühendislik asistanı",
    },
    {
        "id": "repocto",
        "name": "RepOcto",
        "group": "Bilgi ve AI",
        "port": 8004,
        "path": "/repocto-v2",
        "icon": "🐙",
        "description": "Doküman ve kurumsal hafıza çalışma alanı",
    },
    {
        "id": "raporhub",
        "name": "RaporHub",
        "group": "Bilgi ve AI",
        "port": 8003,
        "path": "/app",
        "icon": "📚",
        "description": "Eski rapor arama ve inceleme alanı",
    },
    {
        "id": "smartaios",
        "name": "SmartAIOS",
        "group": "Mühendislik araçları",
        "port": 8001,
        "path": "/",
        "icon": "🧰",
        "description": "Tüm hesaplama modüllerinin ana uygulaması",
    },
    {
        "id": "bolt",
        "name": "Bolt Calculator",
        "group": "Araç analizleri",
        "port": 8001,
        "path": "/",
        "icon": "🔩",
        "description": "Civata hesabı ve toplu sonuç üretimi",
    },
    {
        "id": "cog",
        "name": "COG Analizi",
        "group": "Araç analizleri",
        "port": 8001,
        "path": "/",
        "icon": "⚖️",
        "description": "Araç ağırlık merkezi hesabı",
    },
    {
        "id": "static_load",
        "name": "Statik Yük Çıkarma",
        "group": "Araç analizleri",
        "port": 8001,
        "path": "/",
        "icon": "🚛",
        "description": "Araç statik yük senaryoları",
    },
    {
        "id": "takoz",
        "name": "Takoz / İzolatör",
        "group": "Mühendislik araçları",
        "port": 8001,
        "path": "/",
        "icon": "🧱",
        "description": "İzolatör seçimi ve mühendislik hesabı",
    },
    {
        "id": "heat_transfer",
        "name": "Isı Transferi",
        "group": "Mühendislik araçları",
        "port": 8001,
        "path": "/",
        "icon": "🌡️",
        "description": "Katmanlı ısı transferi hesabı",
    },
    {
        "id": "aconnect",
        "name": "AConnect",
        "group": "CAE araçları",
        "port": 8001,
        "path": "/",
        "icon": "🔗",
        "description": "Sürüş verisi ve senaryo eşleştirme",
    },
)


_TRACKED_EXACT: dict[tuple[str, str], tuple[str, str]] = {
    ("POST", "/ingest"): ("Doküman yükleme", "document"),
    ("POST", "/ingest/batch"): ("Toplu doküman yükleme", "document"),
    ("GET", "/search"): ("Doküman arama", "search"),
    ("POST", "/duplicates/scan"): ("Tekrar doküman tarama", "analysis"),
    ("POST", "/report-comparison"): ("Doküman karşılaştırma", "analysis"),
    ("POST", "/report-comparison/multi"): ("Çoklu doküman karşılaştırma", "analysis"),
    ("POST", "/ask"): ("Kaynaklı soru", "assistant"),
    ("POST", "/chat"): ("AI sohbet", "assistant"),
    ("POST", "/ask/catalog"): ("Katalog sorusu", "assistant"),
    ("POST", "/ask/multi-document"): ("Çoklu doküman sorusu", "assistant"),
    ("POST", "/catalog/import"): ("Katalog içe aktarma", "document"),
    ("POST", "/catalog/reconcile-documents"): ("Katalog eşleştirme", "document"),
    ("POST", "/library/scan"): ("Kütüphane tarama", "document"),
    ("POST", "/draft-report"): ("Doküman taslağı hazırlama", "writing"),
    ("POST", "/draft-report/pdf"): ("Taslak PDF oluşturma", "writing"),
    ("POST", "/report-review/decisions"): ("İnceleme kararı", "review"),
    ("GET", "/report-review/export"): ("İnceleme dışa aktarma", "review"),
    ("POST", "/embeddings/rebuild"): ("Embedding yenileme", "system"),
}


def tracked_operation(method: str, path: str) -> tuple[str, str] | None:
    normalized_method = method.upper()
    exact = _TRACKED_EXACT.get((normalized_method, path))
    if exact is not None:
        return exact
    if normalized_method == "POST" and path.startswith("/catalog/ingest-"):
        return "Katalog dokümanı işleme", "document"
    return None


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    normalized = _utc(value)
    return normalized.isoformat() if normalized else None


def _safe_text(value: str | None, maximum: int) -> str:
    return " ".join((value or "").strip().split())[:maximum]


def _ip_display_name(client_id: str) -> str:
    candidate = _safe_text(client_id, 160)
    if candidate.startswith("ip:"):
        candidate = candidate[3:]
    try:
        return str(ip_address(candidate))
    except ValueError:
        return "IP bilinmiyor"


def _session_bucket_id(session_id: str, application: str, when: datetime) -> str:
    """Keep active time separate per browser session, app and UTC hour."""
    normalized_when = _utc(when) or when.replace(tzinfo=timezone.utc)
    hour_key = normalized_when.strftime("%Y-%m-%dT%H")
    raw_key = f"{session_id}:{application}:{hour_key}"
    if len(raw_key) <= 80:
        return raw_key
    return f"bucket:{sha256(raw_key.encode('utf-8')).hexdigest()}"


class AnalyticsService:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def client_id(*, username: str | None, client_host: str | None, claimed_user: str | None = None) -> str:
        # Analytics deliberately identifies clients by network address only.
        # SmartAIOS forwards the original browser IP as the claimed value; any
        # non-IP name/header is ignored and cannot become a dashboard identity.
        for candidate in (claimed_user, client_host):
            clean_claim = _safe_text(candidate, 120)
            if clean_claim.startswith("ip:"):
                clean_claim = clean_claim[3:]
            try:
                return f"ip:{ip_address(clean_claim)}"
            except ValueError:
                continue
        return "ip:unknown"

    def identity(self, client_id: str) -> dict[str, str | bool]:
        return {
            "client_id": client_id,
            "display_name": _ip_display_name(client_id),
            "is_named": False,
        }

    def heartbeat(
        self,
        *,
        session_id: str,
        client_id: str,
        application: str,
        current_view: str,
        active_seconds_delta: int,
    ) -> dict[str, object]:
        clean_session_id = _safe_text(session_id, 80)
        clean_application = _safe_text(application, 80) or "big_agent"
        clean_view = _safe_text(current_view, 120) or "home"
        active_delta = max(0, min(int(active_seconds_delta), 60))
        now = utc_now()
        bucket_id = _session_bucket_id(clean_session_id, clean_application, now)
        row = self.session.get(AnalyticsSession, bucket_id)
        if row is None:
            row = AnalyticsSession(
                session_id=bucket_id,
                client_id=client_id,
                application=clean_application,
                current_view=clean_view,
                active_seconds=active_delta,
                started_at=now,
                last_seen_at=now,
            )
            self.session.add(row)
            try:
                self.session.commit()
            except IntegrityError:
                # A second heartbeat for the same bucket may arrive concurrently.
                self.session.rollback()
                row = self.session.get(AnalyticsSession, bucket_id)
                if row is None:
                    raise
                self.session.execute(
                    update(AnalyticsSession)
                    .where(AnalyticsSession.session_id == bucket_id)
                    .values(
                        client_id=client_id,
                        application=clean_application,
                        current_view=clean_view,
                        active_seconds=AnalyticsSession.active_seconds + active_delta,
                        last_seen_at=now,
                    )
                )
                self.session.commit()
        else:
            self.session.execute(
                update(AnalyticsSession)
                .where(AnalyticsSession.session_id == bucket_id)
                .values(
                    client_id=client_id,
                    application=clean_application,
                    current_view=clean_view,
                    active_seconds=AnalyticsSession.active_seconds + active_delta,
                    last_seen_at=now,
                )
            )
            self.session.commit()
        row = self.session.get(AnalyticsSession, bucket_id)
        if row is None:
            raise RuntimeError("Analytics session bucket could not be loaded.")
        return {
            "status": "ok",
            "session_id": clean_session_id,
            "bucket_id": row.session_id,
            "active_seconds": row.active_seconds,
            "last_seen_at": _iso(row.last_seen_at),
        }

    def start_operation(
        self,
        *,
        client_id: str,
        application: str,
        operation: str,
        category: str,
        method: str,
        path: str,
        detail: str | None = None,
        external_event_id: str | None = None,
    ) -> int:
        clean_event_id = _safe_text(external_event_id, 80) or None
        if clean_event_id:
            existing = self.session.scalar(
                select(AnalyticsOperation).where(
                    AnalyticsOperation.external_event_id == clean_event_id
                )
            )
            if existing is not None:
                return existing.id
        row = AnalyticsOperation(
            external_event_id=clean_event_id,
            client_id=client_id,
            application=_safe_text(application, 80),
            operation=_safe_text(operation, 160),
            category=_safe_text(category, 80),
            method=_safe_text(method.upper(), 12),
            path=_safe_text(path, 512),
            status="running",
            detail=_safe_text(detail, 512) or None,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row.id

    def finish_operation(
        self,
        operation_id: int,
        *,
        status: str,
        status_code: int | None,
        duration_ms: float,
        detail: str | None = None,
    ) -> None:
        row = self.session.get(AnalyticsOperation, operation_id)
        if row is None:
            return
        row.status = status if status in {"success", "failure", "partial", "cancelled"} else "failure"
        row.status_code = status_code
        row.duration_ms = max(0.0, float(duration_ms))
        row.completed_at = utc_now()
        if detail:
            row.detail = _safe_text(detail, 512)
        self.session.commit()

    def finish_operation_by_event_id(
        self,
        event_id: str,
        *,
        client_id: str,
        application: str,
        operation: str,
        category: str,
        method: str,
        path: str,
        status: str,
        status_code: int | None,
        duration_ms: float,
        detail: str | None = None,
    ) -> int:
        clean_event_id = _safe_text(event_id, 80)
        row = self.session.scalar(
            select(AnalyticsOperation).where(
                AnalyticsOperation.external_event_id == clean_event_id
            )
        )
        duration = max(0.0, float(duration_ms))
        now = utc_now()
        normalized_status = status if status in {"success", "failure", "partial", "cancelled"} else "failure"
        if row is None:
            row = AnalyticsOperation(
                external_event_id=clean_event_id,
                client_id=client_id,
                application=_safe_text(application, 80),
                operation=_safe_text(operation, 160),
                category=_safe_text(category, 80) or "operation",
                method=_safe_text(method.upper(), 12),
                path=_safe_text(path, 512),
                status=normalized_status,
                status_code=status_code,
                duration_ms=duration,
                detail=_safe_text(detail, 512) or None,
                started_at=now - timedelta(milliseconds=duration),
                completed_at=now,
            )
            self.session.add(row)
        else:
            row.status = normalized_status
            row.status_code = status_code
            row.duration_ms = duration
            row.completed_at = now
            if detail:
                row.detail = _safe_text(detail, 512)
        self.session.commit()
        self.session.refresh(row)
        return row.id

    def record_external_event(
        self,
        *,
        client_id: str,
        application: str,
        operation: str,
        category: str,
        status: str,
        duration_ms: float | None,
        detail: str | None,
        event_id: str | None = None,
        status_code: int | None = None,
    ) -> int:
        clean_event_id = _safe_text(event_id, 80) or None
        if clean_event_id and status == "running":
            return self.start_operation(
                client_id=client_id,
                application=application,
                operation=operation,
                category=category,
                method="EVENT",
                path="/external",
                detail=detail,
                external_event_id=clean_event_id,
            )
        if clean_event_id:
            return self.finish_operation_by_event_id(
                clean_event_id,
                client_id=client_id,
                application=application,
                operation=operation,
                category=category,
                method="EVENT",
                path="/external",
                status=status,
                status_code=status_code,
                duration_ms=float(duration_ms or 0.0),
                detail=detail,
            )
        now = utc_now()
        duration = max(0.0, float(duration_ms or 0.0))
        row = AnalyticsOperation(
            client_id=client_id,
            application=_safe_text(application, 80),
            operation=_safe_text(operation, 160),
            category=_safe_text(category, 80) or "operation",
            method="EVENT",
            path="/external",
            status=status if status in {"success", "failure", "partial", "cancelled"} else "failure",
            status_code=status_code,
            duration_ms=duration,
            detail=_safe_text(detail, 512) or None,
            started_at=now - timedelta(milliseconds=duration),
            completed_at=now,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row.id

    def recover_stale_operations(self, maximum_age: timedelta = timedelta(hours=2)) -> int:
        cutoff = utc_now() - maximum_age
        rows = self.session.scalars(
            select(AnalyticsOperation).where(
                AnalyticsOperation.status == "running",
                AnalyticsOperation.started_at < cutoff,
            )
        ).all()
        now = utc_now()
        for row in rows:
            started_at = _utc(row.started_at) or now
            row.status = "failure"
            row.status_code = 500
            row.duration_ms = max(0.0, (now - started_at).total_seconds() * 1000)
            row.completed_at = now
            row.detail = "Uygulama kapanması veya bağlantı kesilmesi nedeniyle işlem tamamlanamadı."
        if rows:
            self.session.commit()
        return len(rows)

    def dashboard(
        self,
        *,
        client_id: str,
        days: int,
        public_host: str,
        application_filter: str = "",
        actor_filter: str = "",
        status_filter: str = "",
    ) -> dict[str, object]:
        now = utc_now()
        since = now - timedelta(days=max(1, min(int(days), 3650)))
        operations = self.session.scalars(
            select(AnalyticsOperation)
            .where(AnalyticsOperation.started_at >= since)
            .order_by(AnalyticsOperation.started_at.desc(), AnalyticsOperation.id.desc())
        ).all()
        sessions = self.session.scalars(
            select(AnalyticsSession)
            .where(AnalyticsSession.last_seen_at >= since)
            .order_by(AnalyticsSession.last_seen_at.desc())
        ).all()
        all_actor_ids = {row.client_id for row in operations} | {row.client_id for row in sessions}
        actor_labels = {
            actor_id: _ip_display_name(actor_id)
            for actor_id in all_actor_ids
        }

        filtered_operations = [
            row
            for row in operations
            if (not application_filter or row.application == application_filter)
            and (not actor_filter or row.client_id == actor_filter)
            and (not status_filter or row.status == status_filter)
        ]
        filtered_sessions = [
            row
            for row in sessions
            if (not application_filter or row.application == application_filter)
            and (not actor_filter or row.client_id == actor_filter)
        ]

        successful = sum(row.status == "success" for row in filtered_operations)
        failed = sum(row.status in {"failure", "partial", "cancelled"} for row in filtered_operations)
        running = sum(row.status == "running" for row in filtered_operations)
        completed = successful + failed
        operation_seconds = sum(float(row.duration_ms or 0.0) for row in filtered_operations) / 1000.0
        active_seconds = sum(max(0, row.active_seconds) for row in filtered_sessions)
        active_cutoff = now - timedelta(minutes=2)
        active_user_ids = {
            row.client_id
            for row in filtered_sessions
            if (_utc(row.last_seen_at) or since) >= active_cutoff
        }

        trend_days = max(7, min(int(days), 90))
        trend_start = (now - timedelta(days=trend_days - 1)).date()
        trend_map = {
            (trend_start + timedelta(days=index)).isoformat(): {"total": 0, "success": 0, "failed": 0}
            for index in range(trend_days)
        }
        for row in filtered_operations:
            date_key = (_utc(row.started_at) or now).date().isoformat()
            if date_key not in trend_map:
                continue
            trend_map[date_key]["total"] += 1
            if row.status == "success":
                trend_map[date_key]["success"] += 1
            elif row.status != "running":
                trend_map[date_key]["failed"] += 1

        user_rows: dict[str, dict[str, object]] = {}
        for actor_id in {row.client_id for row in [*filtered_operations, *filtered_sessions]}:
            actor_operations = [row for row in filtered_operations if row.client_id == actor_id]
            actor_sessions = [row for row in filtered_sessions if row.client_id == actor_id]
            last_operation = actor_operations[0] if actor_operations else None
            last_seen_candidates = [
                value
                for value in [
                    *[_utc(row.last_seen_at) for row in actor_sessions],
                    *[_utc(row.started_at) for row in actor_operations],
                ]
                if value is not None
            ]
            user_rows[actor_id] = {
                "actor_id": actor_id,
                "display_name": actor_labels.get(actor_id, actor_id),
                "active_seconds": sum(max(0, row.active_seconds) for row in actor_sessions),
                "operations": len(actor_operations),
                "successful": sum(row.status == "success" for row in actor_operations),
                "failed": sum(row.status in {"failure", "partial", "cancelled"} for row in actor_operations),
                "last_operation": last_operation.operation if last_operation else "Henüz işlem yok",
                "last_seen_at": _iso(max(last_seen_candidates)) if last_seen_candidates else None,
                "is_active": any((_utc(row.last_seen_at) or since) >= active_cutoff for row in actor_sessions),
            }

        operation_by_app: dict[str, list[AnalyticsOperation]] = defaultdict(list)
        session_by_app: dict[str, list[AnalyticsSession]] = defaultdict(list)
        for row in filtered_operations:
            operation_by_app[row.application].append(row)
        for row in filtered_sessions:
            session_by_app[row.application].append(row)

        port_status: dict[int, bool] = {}
        for port in {int(item["port"]) for item in APPLICATIONS}:
            port_status[port] = self._port_is_open(port)
        applications: list[dict[str, object]] = []
        for item in APPLICATIONS:
            app_id = str(item["id"])
            app_operations = operation_by_app.get(app_id, [])
            app_success = sum(row.status == "success" for row in app_operations)
            app_finished = sum(row.status != "running" for row in app_operations)
            port = int(item["port"])
            applications.append(
                {
                    **item,
                    "url": f"http://{public_host}:{port}{item['path']}",
                    "status": "online" if port_status.get(port) else "offline",
                    "operations": len(app_operations),
                    "successful": app_success,
                    "failed": sum(row.status in {"failure", "partial", "cancelled"} for row in app_operations),
                    "success_rate": round((app_success / app_finished * 100) if app_finished else 0.0, 1),
                    "active_seconds": sum(max(0, row.active_seconds) for row in session_by_app.get(app_id, [])),
                }
            )

        running_jobs = []
        for row in filtered_operations:
            if row.status != "running":
                continue
            started_at = _utc(row.started_at) or now
            running_jobs.append(
                {
                    "id": row.id,
                    "actor_id": row.client_id,
                    "display_name": actor_labels.get(row.client_id, row.client_id),
                    "application": row.application,
                    "application_name": self._application_name(row.application),
                    "operation": row.operation,
                    "started_at": _iso(started_at),
                    "elapsed_seconds": max(0, int((now - started_at).total_seconds())),
                    "status": row.status,
                }
            )

        notifications: list[dict[str, object]] = []
        for row in filtered_operations:
            if row.status not in {"failure", "partial", "cancelled"}:
                continue
            notifications.append(
                {
                    "level": "error" if row.status == "failure" else "warning",
                    "title": f"{row.operation} tamamlanamadı",
                    "message": row.detail or f"{self._application_name(row.application)} işlemi {row.status} durumuyla bitti.",
                    "occurred_at": _iso(row.completed_at or row.started_at),
                }
            )
            if len(notifications) >= 5:
                break
        offline_apps = [item for item in applications if item["status"] == "offline" and item["id"] in {"big_agent", "smartaios", "raporhub", "repocto"}]
        for item in offline_apps:
            notifications.append(
                {
                    "level": "warning",
                    "title": f"{item['name']} çevrimdışı",
                    "message": f"{item['port']} portunda çalışan servis bulunamadı.",
                    "occurred_at": _iso(now),
                }
            )

        logs = [
            {
                "id": row.id,
                "time": _iso(row.started_at),
                "completed_at": _iso(row.completed_at),
                "kind": "technical" if row.status in {"failure", "partial", "cancelled"} else "activity",
                "actor_id": row.client_id,
                "display_name": actor_labels.get(row.client_id, row.client_id),
                "application": row.application,
                "application_name": self._application_name(row.application),
                "operation": row.operation,
                "category": row.category,
                "status": row.status,
                "duration_ms": row.duration_ms,
                "method": row.method,
                "path": row.path,
                "status_code": row.status_code,
                "detail": row.detail,
            }
            for row in filtered_operations[:150]
        ]

        return {
            "generated_at": _iso(now),
            "period_days": days,
            "identity": self.identity(client_id),
            "summary": {
                "total_operations": len(filtered_operations),
                "successful": successful,
                "failed": failed,
                "running": running,
                "success_rate": round((successful / completed * 100) if completed else 0.0, 1),
                "failure_rate": round((failed / completed * 100) if completed else 0.0, 1),
                "active_users": len(active_user_ids),
                "total_users": len(user_rows),
                "active_seconds": active_seconds,
                "operation_seconds": round(operation_seconds, 3),
            },
            "trend": [{"date": date, **values} for date, values in trend_map.items()],
            "users": sorted(
                user_rows.values(),
                key=lambda row: (int(row["operations"]), int(row["active_seconds"])),
                reverse=True,
            ),
            "applications": applications,
            "running_jobs": running_jobs,
            "notifications": notifications[:8],
            "logs": logs,
            "filters": {
                "actors": [
                    {"id": actor_id, "name": actor_labels[actor_id]}
                    for actor_id in sorted(actor_labels, key=lambda value: actor_labels[value].casefold())
                ],
                "applications": [
                    {"id": str(item["id"]), "name": str(item["name"])} for item in APPLICATIONS
                ],
                "statuses": ["success", "failure", "partial", "cancelled", "running"],
            },
        }

    @staticmethod
    def _application_name(application: str) -> str:
        for item in APPLICATIONS:
            if item["id"] == application:
                return str(item["name"])
        return application.replace("_", " ").title()

    @staticmethod
    def _port_is_open(port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.08):
                return True
        except OSError:
            return False


def analytics_application_ids() -> Iterable[str]:
    return (str(item["id"]) for item in APPLICATIONS)
