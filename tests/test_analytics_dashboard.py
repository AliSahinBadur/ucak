from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from starlette.requests import Request
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.config import APP_VARIANT
from app.db.models import AnalyticsIdentity, Base
from app.db.session import _ensure_analytics_schema
from app.main import app
import app.main as main_module
from app.services.analytics_service import AnalyticsService, tracked_operation


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = ROOT / "app" / "ui" / "smartaios_dashboard"


def test_tracked_operation_registry_counts_work_instead_of_page_assets() -> None:
    assert tracked_operation("POST", "/chat") == ("AI sohbet", "assistant")
    assert tracked_operation("POST", "/report-comparison/multi") == (
        "Çoklu doküman karşılaştırma",
        "analysis",
    )
    assert tracked_operation("POST", "/catalog/ingest-selected") == (
        "Katalog dokümanı işleme",
        "document",
    )
    assert tracked_operation("GET", "/smartcae-v2") is None
    assert tracked_operation("GET", "/smartcae-v2/assets/smartcae-v2.css") is None
    assert tracked_operation("GET", "/health") is None
    assert AnalyticsService.client_id(username=None, client_host="127.0.0.1", claimed_user="10.4.7.6") == "ip:10.4.7.6"
    assert AnalyticsService.client_id(username="Ali", client_host="10.4.8.19") == "ip:10.4.8.19"
    assert AnalyticsService.client_id(
        username=None,
        client_host="127.0.0.1",
        claimed_user="Ali",
    ) == "ip:127.0.0.1"


def test_dashboard_proxy_can_preserve_the_remote_workstation_host() -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/analytics/dashboard",
            "query_string": b"",
            "headers": [(b"host", b"127.0.0.1:8002"), (b"x-smartaios-public-host", b"10.4.12.19")],
            "scheme": "http",
            "server": ("127.0.0.1", 8002),
            "client": ("127.0.0.1", 50000),
        }
    )

    assert main_module._analytics_public_host(request) == "10.4.12.19"


def test_dashboard_aggregates_real_operations_active_time_and_filters() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        service = AnalyticsService(session)
        session.add(
            AnalyticsIdentity(
                client_id="ip:10.4.7.6",
                display_name="Ali Şahin",
                source="manual",
            )
        )
        session.commit()
        service.heartbeat(
            session_id="session-0001",
            client_id="ip:10.4.7.6",
            application="big_agent",
            current_view="chat",
            active_seconds_delta=30,
        )
        service.heartbeat(
            session_id="session-0001",
            client_id="ip:10.4.7.6",
            application="big_agent",
            current_view="compare",
            active_seconds_delta=20,
        )
        success_id = service.start_operation(
            client_id="ip:10.4.7.6",
            application="big_agent",
            operation="AI sohbet",
            category="assistant",
            method="POST",
            path="/chat",
        )
        service.finish_operation(success_id, status="success", status_code=200, duration_ms=1250)
        failure_id = service.start_operation(
            client_id="ip:10.4.7.6",
            application="repocto",
            operation="Kütüphane tarama",
            category="document",
            method="POST",
            path="/library/scan",
        )
        service.finish_operation(
            failure_id,
            status="failure",
            status_code=500,
            duration_ms=500,
            detail="Klasör okunamadı.",
        )

        dashboard = service.dashboard(
            client_id="ip:10.4.7.6",
            days=30,
            public_host="10.4.12.19",
        )
        filtered = service.dashboard(
            client_id="ip:10.4.7.6",
            days=30,
            public_host="10.4.12.19",
            application_filter="big_agent",
            status_filter="success",
        )
        preserved_mapping = session.get(AnalyticsIdentity, "ip:10.4.7.6")

    assert dashboard["identity"] == {
        "client_id": "ip:10.4.7.6",
        "display_name": "10.4.7.6",
        "is_named": False,
    }
    assert dashboard["summary"] == {
        "total_operations": 2,
        "successful": 1,
        "failed": 1,
        "running": 0,
        "success_rate": 50.0,
        "failure_rate": 50.0,
        "active_users": 1,
        "total_users": 1,
        "active_seconds": 50,
        "operation_seconds": 1.75,
    }
    assert dashboard["users"][0]["display_name"] == "10.4.7.6"
    assert dashboard["users"][0]["operations"] == 2
    assert dashboard["users"][0]["active_seconds"] == 50
    assert any(item["title"] == "Kütüphane tarama tamamlanamadı" for item in dashboard["notifications"])
    assert {item["status"] for item in dashboard["logs"]} == {"success", "failure"}
    assert {item["display_name"] for item in dashboard["logs"]} == {"10.4.7.6"}
    assert dashboard["filters"]["actors"] == [
        {"id": "ip:10.4.7.6", "name": "10.4.7.6"}
    ]
    assert preserved_mapping is not None
    assert preserved_mapping.display_name == "Ali Şahin"
    assert any(item["url"] == "http://10.4.12.19:8002/smartcae-v2" for item in dashboard["applications"])

    assert filtered["summary"]["total_operations"] == 1
    assert filtered["summary"]["successful"] == 1
    assert filtered["summary"]["failed"] == 0


def test_active_time_is_kept_separate_when_one_browser_switches_applications() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        service = AnalyticsService(session)
        service.heartbeat(
            session_id="shared-session",
            client_id="ip:10.4.7.6",
            application="big_agent",
            current_view="chat",
            active_seconds_delta=30,
        )
        service.heartbeat(
            session_id="shared-session",
            client_id="ip:10.4.7.6",
            application="cog",
            current_view="cog",
            active_seconds_delta=20,
        )
        big_agent = service.dashboard(
            client_id="ip:10.4.7.6",
            days=1,
            public_host="127.0.0.1",
            application_filter="big_agent",
        )
        cog = service.dashboard(
            client_id="ip:10.4.7.6",
            days=1,
            public_host="127.0.0.1",
            application_filter="cog",
        )

    assert big_agent["summary"]["active_seconds"] == 30
    assert cog["summary"]["active_seconds"] == 20


def test_dashboard_preserves_running_jobs_and_external_events() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        service = AnalyticsService(session)
        running_id = service.start_operation(
            client_id="user:engineer",
            application="big_agent",
            operation="Çoklu doküman karşılaştırma",
            category="analysis",
            method="POST",
            path="/report-comparison/multi",
        )
        external_id = service.record_external_event(
            client_id="user:engineer",
            application="cog",
            operation="COG hesaplama",
            category="analysis",
            status="success",
            duration_ms=2200,
            detail="Tek aks hesabı tamamlandı.",
        )
        correlated_running_id = service.record_external_event(
            event_id="external-cog-operation-0001",
            client_id="user:engineer",
            application="cog",
            operation="COG kalite kontrolü",
            category="analysis",
            status="running",
            duration_ms=None,
            detail="İşlem başladı.",
        )
        dashboard = service.dashboard(
            client_id="user:engineer",
            days=7,
            public_host="127.0.0.1",
        )
        correlated_completed_id = service.record_external_event(
            event_id="external-cog-operation-0001",
            client_id="user:engineer",
            application="cog",
            operation="COG kalite kontrolü",
            category="analysis",
            status="success",
            status_code=200,
            duration_ms=800,
            detail="İşlem tamamlandı.",
        )
        completed_dashboard = service.dashboard(
            client_id="user:engineer",
            days=7,
            public_host="127.0.0.1",
        )

    assert running_id != external_id
    assert dashboard["summary"]["running"] == 2
    assert {item["operation"] for item in dashboard["running_jobs"]} == {
        "Çoklu doküman karşılaştırma",
        "COG kalite kontrolü",
    }
    assert any(item["id"] == "cog" and item["operations"] == 2 for item in dashboard["applications"])
    assert correlated_running_id == correlated_completed_id
    assert completed_dashboard["summary"]["running"] == 1
    assert any(
        item["operation"] == "COG kalite kontrolü" and item["status"] == "success"
        for item in completed_dashboard["logs"]
    )


def test_batch_outcome_marks_partial_and_complete_failures() -> None:
    partial_request = SimpleNamespace(state=SimpleNamespace())
    main_module._set_analytics_batch_outcome(
        partial_request,
        total_count=5,
        error_count=2,
        label="Toplu test",
    )
    failed_request = SimpleNamespace(state=SimpleNamespace())
    main_module._set_analytics_batch_outcome(
        failed_request,
        total_count=3,
        error_count=3,
        label="Toplu test",
    )

    assert partial_request.state.analytics_status == "partial"
    assert "5 kaydın 2" in partial_request.state.analytics_detail
    assert failed_request.state.analytics_status == "failure"


def test_existing_analytics_table_is_upgraded_without_deleting_data() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE analytics_operations ("
                "id INTEGER PRIMARY KEY, client_id VARCHAR(160) NOT NULL)"
            )
        )
        connection.execute(
            text("INSERT INTO analytics_operations (id, client_id) VALUES (1, 'ip:10.4.7.6')")
        )

    _ensure_analytics_schema(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("analytics_operations")}
    with engine.connect() as connection:
        preserved = connection.scalar(text("SELECT client_id FROM analytics_operations WHERE id = 1"))
    assert "external_event_id" in columns
    assert preserved == "ip:10.4.7.6"


def test_smartaios_dashboard_frontend_contract() -> None:
    html = (DASHBOARD_DIR / "index.html").read_text(encoding="utf-8")
    css = (DASHBOARD_DIR / "assets" / "smartaios-dashboard.css").read_text(encoding="utf-8")
    script = (DASHBOARD_DIR / "assets" / "smartaios-dashboard.js").read_text(encoding="utf-8")

    for element_id in (
        "totalOperations",
        "trendChart",
        "usersTableBody",
        "applicationGroups",
        "runningJobs",
        "notificationsList",
        "activityLogs",
    ):
        assert f'id="{element_id}"' in html
    assert "/smartaios-dashboard/assets/smartaios-dashboard.css?v=__APP_VERSION__" in html
    assert "/smartaios-dashboard/assets/smartaios-dashboard.js?v=__APP_VERSION__" in html
    assert "HIZLI İŞLEMLER" not in html
    assert "Çalışma alanını aç" not in html
    assert "quick-app" not in html
    assert "quick-app" not in css
    assert "quickApp" not in script
    assert 'fetch(`/analytics/dashboard?' in script
    assert 'fetch("/analytics/heartbeat"' in script
    assert 'fetch("/analytics/profile"' not in script
    assert 'id="profileDialog"' not in html
    assert 'id="displayNameInput"' not in html
    assert "saveProfile" not in script
    assert "Bağlanan IP" in html
    assert "Görünen ad" not in html
    assert "@media (max-width:" in css


def test_smartaios_dashboard_route_and_assets_are_served_for_big_agent() -> None:
    if APP_VARIANT != "big_agent":
        return
    with TestClient(app) as client:
        page = client.get("/smartaios-dashboard")
        stylesheet = client.get("/smartaios-dashboard/assets/smartaios-dashboard.css")
        script = client.get("/smartaios-dashboard/assets/smartaios-dashboard.js")
        profile = client.post("/analytics/profile", json={"display_name": "Ali"})

    assert page.status_code == 200
    assert 'data-dashboard-version="1"' in page.text
    assert f"smartaios-dashboard.css?v={main_module.APP_VERSION}" in page.text
    assert "__APP_VERSION__" not in page.text
    assert stylesheet.status_code == 200
    assert script.status_code == 200
    assert profile.status_code == 404
