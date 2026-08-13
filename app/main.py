from __future__ import annotations

import base64
import hashlib
import hmac
from html import escape
from pathlib import Path
import logging
import os
import re
import secrets
import tempfile
import time
import unicodedata
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .api_models import (
    AskRequest,
    AskResponse,
    BatchIngestItemResponse,
    BatchIngestResponse,
    CatalogAskRequest,
    CatalogAskResponse,
    CatalogCandidateIngestRequest,
    CatalogImportResponse,
    CatalogSampleIngestItemResponse,
    CatalogSampleIngestResponse,
    CatalogSearchResponse,
    CatalogSelectedIngestRequest,
    CatalogSelectedIngestResponse,
    CatalogTableResponse,
    ChatRequest,
    ChatResponse,
    DraftReportRequest,
    DraftReportResponse,
    DuplicateReportListResponse,
    DuplicateReportScanResponse,
    HealthResponse,
    IngestResponse,
    LibraryScanRequest,
    MultiDocumentAskRequest,
    MultiDocumentAskResponse,
    ReindexEmbeddingsResponse,
    ReportComparisonRequest,
    ReportComparisonResponse,
    ReportComparisonUploadResponse,
    SearchResponse,
    StorageCheckResponse,
)
from .db.session import SessionLocal, get_session, init_db
from .db.models import ChunkEmbedding, Document, DocumentChunk, DocumentPage
from .services.embedding_reindex_service import EmbeddingReindexService
from .services.embedding_service import build_embedding_service
from .services.catalog_ingest_service import CatalogIngestService
from .services.catalog_service import CatalogService
from .services.duplicate_detection_service import DuplicateDetectionService
from .services.document_intelligence_service import DocumentIntelligenceService
from .services.document_path_service import resolve_document_file_path
from .services.general_chat_service import GeneralChatService
from .services.graph_service import GraphService
from .services.haystack_retrieval_service import (
    HaystackRetrievalError,
    HaystackRetrievalService,
    HaystackUnavailableError,
)
from .services.ingest_service import IngestService
from .services.library_service import LibraryService
from .services.multi_document_qa_service import MultiDocumentQAService
from .services.qa_service import QAService
from .services.report_comparison_service import (
    ReportComparisonService,
    resolve_comparison_pdf_path,
)
from .services.report_writer_service import ReportWriterService
from .services.retrieval_orchestrator import RetrievalOrchestrator
from .services.search_service import SearchService
from .services.storage_service import StorageService
from .ui.variant_styles import get_variant_css
from .version import APP_VERSION
from .config import (
    APP_AUTH_COOKIE_NAME,
    APP_AUTH_ENABLED,
    APP_BRAND,
    APP_SESSION_SECRET,
    APP_USERS_RAW,
    APP_VARIANT,
    REPOCTO_LIBRARY_ROOTS,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
#dfgasdgfasdfasdfasdfasdf
app = FastAPI(title=APP_BRAND.api_title, version=APP_VERSION)
RAPORHUB_LANDING_DIR = Path(__file__).resolve().parent / "ui" / "raporhub_landing"
REPOCTO_LANDING_DIR = Path(__file__).resolve().parent / "ui" / "repocto_landing"
REPOCTO_LANDING_V2_DIR = REPOCTO_LANDING_DIR / "v2"
REPORT_WORKSPACE_VARIANTS = frozenset({"raporhub", "repocto"})
app.mount(
    "/raporhub-landing",
    StaticFiles(directory=str(RAPORHUB_LANDING_DIR)),
    name="raporhub-landing",
)
app.mount(
    "/repocto-landing",
    StaticFiles(directory=str(REPOCTO_LANDING_DIR)),
    name="repocto-landing",
)
AUTH_COOKIE_NAME = APP_AUTH_COOKIE_NAME
AUTH_SESSION_SECONDS = 8 * 60 * 60
FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
<text x="50" y="52" dy="0.35em" text-anchor="middle" font-size="86" font-family="Segoe UI Emoji, Apple Color Emoji, sans-serif">🤖</text>
</svg>"""


def _parse_app_users(raw_value: str) -> dict[str, str]:
    users: dict[str, str] = {}
    for item in raw_value.split(";"):
        if ":" not in item:
            continue
        username, password = item.split(":", 1)
        username = username.strip()
        password = password.strip()
        if username and password:
            users[username] = password
    return users


APP_USERS = _parse_app_users(APP_USERS_RAW)


def _auth_secret() -> str:
    return APP_SESSION_SECRET or "change-this-local-test-secret"


def _session_signature(username: str, expires_at: int) -> str:
    payload = f"{username}|{expires_at}".encode("utf-8")
    return hmac.new(_auth_secret().encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _create_session_cookie(username: str) -> str:
    expires_at = int(time.time()) + AUTH_SESSION_SECONDS
    signature = _session_signature(username, expires_at)
    raw = f"{username}|{expires_at}|{signature}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _read_session_user(request: Request) -> str | None:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        return None
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        username, expires_text, signature = raw.split("|", 2)
        expires_at = int(expires_text)
    except Exception:
        return None
    if expires_at < int(time.time()):
        return None
    if username not in APP_USERS:
        return None
    expected = _session_signature(username, expires_at)
    if not hmac.compare_digest(signature, expected):
        return None
    return username


def _auth_enabled() -> bool:
    return APP_AUTH_ENABLED and bool(APP_USERS)


def _application_home_path() -> str:
    return "/app" if APP_VARIANT in REPORT_WORKSPACE_VARIANTS else "/"


def _login_html(error: str = "") -> str:
    error_html = f'<div class="error">{escape(error)}</div>' if error else ""
    return f"""<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="icon" href="/favicon.ico" type="image/svg+xml" />
  <title>{APP_BRAND.display_name} Login</title>
  <style>
    body {{ margin:0; min-height:100vh; display:grid; place-items:center; font-family:Arial,sans-serif; background:{APP_BRAND.background}; color:{APP_BRAND.text}; }}
    form {{ width:min(380px, calc(100vw - 32px)); background:{APP_BRAND.panel}; border:1px solid {APP_BRAND.line}; border-radius:{APP_BRAND.card_radius}; padding:24px; box-shadow:0 18px 50px {APP_BRAND.card_shadow}; }}
    h1 {{ margin:0 0 6px; font-size:24px; }}
    p {{ margin:0 0 18px; color:{APP_BRAND.muted}; font-size:14px; }}
    label {{ display:block; font-size:13px; font-weight:700; margin:14px 0 6px; }}
    input {{ width:100%; box-sizing:border-box; border:1px solid {APP_BRAND.line}; border-radius:8px; padding:12px; font-size:15px; }}
    button {{ width:100%; margin-top:18px; border:0; border-radius:8px; padding:12px; background:{APP_BRAND.accent_strong}; color:#fff; font-weight:700; cursor:pointer; }}
    .error {{ margin:12px 0 0; color:#9b1024; background:#fff1f3; border:1px solid #f1c9cf; border-radius:10px; padding:10px; font-size:13px; }}
    .version {{ margin-top:14px; color:{APP_BRAND.muted}; font-size:12px; text-align:center; }}
  </style>
</head>
<body>
  <form method="post" action="/login">
    <h1>{APP_BRAND.display_name}</h1>
    <p>Test kullanicisi ile giris yap.</p>
    <label for="username">Kullanici</label>
    <input id="username" name="username" autocomplete="username" autofocus />
    <label for="password">Sifre</label>
    <input id="password" name="password" type="password" autocomplete="current-password" />
    {error_html}
    <button type="submit">Giris</button>
    <div class="version">v{APP_VERSION}</div>
  </form>
</body>
</html>"""


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if not _auth_enabled():
        return await call_next(request)

    path = request.url.path
    if path in {"/health", "/login", "/logout", "/favicon.ico"}:
        return await call_next(request)
    if APP_VARIANT in REPORT_WORKSPACE_VARIANTS:
        landing_prefix = (
            "/raporhub-landing/"
            if APP_VARIANT == "raporhub"
            else "/repocto-landing/"
        )
        repocto_v2_landing = APP_VARIANT == "repocto" and path in {
            "/repocto-v2",
            "/repocto-v2/",
        }
        if path == "/" or path.startswith(landing_prefix) or repocto_v2_landing:
            return await call_next(request)

    username = _read_session_user(request)
    if username:
        request.state.username = username
        return await call_next(request)

    if request.method == "GET" and (path == "/" or "text/html" in request.headers.get("accept", "")):
        return RedirectResponse("/login", status_code=303)
    return JSONResponse({"detail": "Authentication required."}, status_code=401)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
        description=app.description,
    )
    openapi_schema["openapi"] = "3.0.3"
    _patch_binary_upload_schema(openapi_schema)
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


def _patch_binary_upload_schema(openapi_schema: dict) -> None:
    schemas = openapi_schema.get("components", {}).get("schemas", {})
    for schema in schemas.values():
        properties = schema.get("properties", {})
        for property_schema in properties.values():
            _convert_content_media_type_to_binary(property_schema)


def _convert_content_media_type_to_binary(node: dict) -> None:
    if not isinstance(node, dict):
        return

    if node.get("type") == "string" and node.get("contentMediaType") == "application/octet-stream":
        node.pop("contentMediaType", None)
        node["format"] = "binary"

    if node.get("type") == "array" and isinstance(node.get("items"), dict):
        _convert_content_media_type_to_binary(node["items"])


@app.on_event("startup")
def on_startup() -> None:
    init_db()


def _display_model_name() -> str:
    provider_name = build_embedding_service().provider_name
    if ":" not in provider_name:
        return provider_name

    _, raw_model = provider_name.split(":", 1)
    candidate = Path(raw_model).name or raw_model
    if "/" in candidate:
        candidate = candidate.split("/")[-1]
    return candidate


def _display_embedding_device() -> tuple[str, str]:
    service = build_embedding_service()
    raw_device = str(getattr(service, "device", "cpu")).strip().casefold()
    is_gpu = raw_device.startswith(("cuda", "mps", "xpu"))
    return ("GPU", "gpu") if is_gpu else ("CPU", "cpu")


def _apply_brand_tokens(html: str) -> str:
    brand_dative = "RepOcto'ya" if APP_VARIANT == "repocto" else f"{APP_BRAND.display_name}'a"
    workspace_intro = (
        "Raporları bilgiye, bilgiyi karara dönüştürün."
        if APP_VARIANT == "repocto"
        else "Rapor havuzunu yonet, katalogla eslestir, kaynakli cevap al ve mukerrer adaylari ayni yerel sistemde incele."
    )
    replacements = {
        "__BRAND_NAME__": escape(APP_BRAND.display_name),
        "__BRAND_DATIVE__": brand_dative,
        "__WORKSPACE_INTRO__": workspace_intro,
        "__BRAND_INITIALS__": escape(APP_BRAND.initials),
        "__APP_VARIANT__": APP_VARIANT,
        "__VARIANT_CSS__": get_variant_css(APP_VARIANT),
        "__THEME_BG__": APP_BRAND.background,
        "__THEME_PANEL__": APP_BRAND.panel,
        "__THEME_LINE__": APP_BRAND.line,
        "__THEME_TEXT__": APP_BRAND.text,
        "__THEME_MUTED__": APP_BRAND.muted,
        "__THEME_ACCENT__": APP_BRAND.accent,
        "__THEME_ACCENT_STRONG__": APP_BRAND.accent_strong,
        "__THEME_SOFT__": APP_BRAND.soft,
        "__THEME_SOFT_2__": APP_BRAND.soft_2,
        "__THEME_HALO_1__": APP_BRAND.halo_1,
        "__THEME_HALO_2__": APP_BRAND.halo_2,
        "__THEME_SURFACE_TOP__": APP_BRAND.surface_top,
        "__THEME_CARD_SHADOW__": APP_BRAND.card_shadow,
        "__THEME_CARD_RADIUS__": APP_BRAND.card_radius,
    }
    for token, value in replacements.items():
        html = html.replace(token, value)
    return html


def _safe_download_name(value: str, fallback: str = "rapor") -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^\w.-]+", "_", ascii_only).strip("_")
    return cleaned or fallback


@app.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=APP_VERSION,
        application=APP_BRAND.display_name,
        variant=APP_VARIANT,
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    if APP_VARIANT == "raporhub":
        return FileResponse(
            RAPORHUB_LANDING_DIR / "assets" / "raporhub-favicon.ico",
            media_type="image/x-icon",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    if APP_VARIANT == "repocto":
        return FileResponse(
            REPOCTO_LANDING_DIR / "assets" / "repocto-favicon.svg",
            media_type="image/svg+xml",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    return Response(
        content=FAVICON_SVG,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if _auth_enabled() and _read_session_user(request):
        return RedirectResponse(_application_home_path(), status_code=303)
    return HTMLResponse(_login_html())


@app.post("/login")
async def login(request: Request):
    if not _auth_enabled():
        return RedirectResponse(_application_home_path(), status_code=303)

    form = await request.form()
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    expected = APP_USERS.get(username)
    if not expected or not secrets.compare_digest(password, expected):
        return HTMLResponse(_login_html("Kullanici adi veya sifre hatali."), status_code=401)

    response = RedirectResponse(_application_home_path(), status_code=303)
    response.set_cookie(
        AUTH_COOKIE_NAME,
        _create_session_cookie(username),
        max_age=AUTH_SESSION_SECONDS,
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(AUTH_COOKIE_NAME)
    return response


@app.get("/repocto-v2/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/repocto-v2", response_class=HTMLResponse, include_in_schema=False)
def repocto_v2_landing() -> HTMLResponse:
    if APP_VARIANT != "repocto":
        raise HTTPException(status_code=404, detail="Not found")
    return HTMLResponse(
        REPOCTO_LANDING_V2_DIR.joinpath("index.html").read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/app/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/app", response_class=HTMLResponse, include_in_schema=False)
@app.get("/", response_class=HTMLResponse)
def upload_page(request: Request) -> HTMLResponse:
    if APP_VARIANT == "raporhub" and request.url.path == "/":
        return HTMLResponse(
            RAPORHUB_LANDING_DIR.joinpath("index.html").read_text(encoding="utf-8"),
            headers={"Cache-Control": "no-cache"},
        )
    if APP_VARIANT == "repocto" and request.url.path == "/":
        return HTMLResponse(
            REPOCTO_LANDING_DIR.joinpath("index.html").read_text(encoding="utf-8"),
            headers={"Cache-Control": "no-cache"},
        )

    model_label = escape(_display_model_name())
    device_label, device_kind = _display_embedding_device()
    device_label = escape(device_label)
    device_kind = escape(device_kind)
    html = """
<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="icon" href="/favicon.ico" type="image/svg+xml" />
  <title>__BRAND_NAME__</title>
  <style>
    :root {
      --bg: __THEME_BG__;
      --panel: __THEME_PANEL__;
      --line: __THEME_LINE__;
      --text: __THEME_TEXT__;
      --muted: __THEME_MUTED__;
      --accent: __THEME_ACCENT__;
      --accent-strong: __THEME_ACCENT_STRONG__;
      --soft: __THEME_SOFT__;
      --soft-2: __THEME_SOFT_2__;
      --ok: #1b7f4b;
      --error: #a61b2b;
      --halo-1: __THEME_HALO_1__;
      --halo-2: __THEME_HALO_2__;
      --surface-top: __THEME_SURFACE_TOP__;
      --card-shadow: __THEME_CARD_SHADOW__;
      --card-radius: __THEME_CARD_RADIUS__;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", Tahoma, sans-serif;
      background:
        radial-gradient(circle at top right, var(--halo-1) 0%, transparent 26%),
        radial-gradient(circle at left center, var(--halo-2) 0%, transparent 20%),
        linear-gradient(180deg, var(--surface-top) 0%, var(--bg) 100%);
      color: var(--text);
    }
    .wrap {
      max-width: 1620px;
      margin: 36px auto;
      padding: 0 20px 40px;
      transition: max-width 180ms ease;
    }
    body.chat-focus .wrap {
      max-width: 1880px;
    }
    .stack {
      display: grid;
      gap: 22px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--card-radius);
      box-shadow: 0 16px 38px var(--card-shadow);
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }
    .hero {
      padding: 28px 28px 18px;
      border-bottom: 1px solid var(--line);
    }
    .hero-title-row {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
      margin-bottom: 8px;
    }
    .hero h1 {
      margin: 0;
      font-size: 30px;
      line-height: 1.1;
    }
    .version-pill {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 999px;
      padding: 7px 12px;
      background: var(--soft);
      color: var(--accent-strong);
      border: 1px solid var(--line);
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.02em;
    }
    .compute-pill {
      gap: 7px;
    }
    .compute-pill::before {
      content: "";
      width: 8px;
      height: 8px;
      flex: 0 0 8px;
      border-radius: 50%;
      background: #b87517;
      box-shadow: 0 0 0 3px rgba(184, 117, 23, 0.12);
    }
    .compute-pill.compute-gpu::before {
      background: #16834f;
      box-shadow: 0 0 0 3px rgba(22, 131, 79, 0.14);
    }
    .logout-link {
      margin-left: auto;
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
      text-decoration: none;
    }
    .logout-link:hover {
      color: var(--accent-strong);
    }
    .hero p {
      margin: 0;
      color: var(--muted);
      line-height: 1.55;
      max-width: 820px;
    }
    .hero-meta {
      margin-top: 12px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }
    .hero-pill {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 6px 10px;
      background: var(--soft);
      color: var(--accent-strong);
      font-size: 12px;
      font-weight: 700;
    }
    .module-switcher {
      margin-top: 14px;
      display: flex;
      gap: 9px;
      flex-wrap: wrap;
      align-items: center;
    }
    .module-filter {
      border: 1px solid #f1c8cf;
      border-radius: 999px;
      background: #fdecef;
      color: var(--accent-strong);
      cursor: pointer;
      font-size: 12px;
      font-weight: 800;
      padding: 8px 12px;
      line-height: 1;
      white-space: nowrap;
    }
    .module-filter:hover {
      background: #ffe4e8;
    }
    .module-filter.active {
      background: var(--accent);
      border-color: var(--accent);
      color: #ffffff;
      box-shadow: 0 8px 18px rgba(198, 40, 57, 0.16);
    }
    .section.module-hidden {
      display: none;
    }
    .section {
      padding: 24px 28px 28px;
      position: relative;
    }
    .section[data-module-key="upload"] { order: 1; }
    .section[data-module-key="catalog"] { order: 2; }
    .section[data-module-key="search"] { order: 3; }
    .section[data-module-key="chat"] { order: 4; }
    .section[data-module-key="duplicates"] { order: 5; }
    .section[data-module-key="graph"] { order: 6; }
    .section[data-module-key="qa"] { order: 7; }
    .section[data-module-key="writing"] { order: 8; }
    .section + .section {
      border-top: 1px solid var(--line);
    }
    .upload-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 20px;
      align-items: stretch;
    }
    .report-upload-grid {
      grid-template-columns: minmax(0, 1fr);
    }
    .upload-card {
      display: flex;
      flex-direction: column;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: #fffdfd;
      padding: 20px 22px 18px;
      box-shadow: inset 0 0 0 1px rgba(255, 245, 246, 0.9);
    }
    .upload-card .result {
      margin-top: 18px;
      padding-top: 14px;
      border-top: 1px solid #f0d8dc;
    }
    h2 {
      margin: 0 0 8px;
      font-size: 22px;
      line-height: 1.2;
    }
    .section p {
      margin: 0;
      color: var(--muted);
      line-height: 1.55;
    }
    .section-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 14px;
    }
    .section-head h2 {
      margin-bottom: 8px;
    }
    .section-head p {
      max-width: 820px;
    }
    .expand-button {
      flex: 0 0 auto;
      border: 1px solid #f0c6cd;
      background: #fff6f8;
      color: var(--accent-strong);
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 13px;
      font-weight: 800;
      cursor: pointer;
    }
    .expand-button:hover {
      background: #ffe9ed;
    }
    .module-modal {
      position: fixed;
      inset: 0;
      z-index: 50;
      display: none;
      background: rgba(42, 16, 20, 0.54);
      backdrop-filter: blur(4px);
      padding: 22px;
    }
    .module-modal.open {
      display: block;
    }
    .module-modal-shell {
      height: min(94vh, 980px);
      max-width: 1480px;
      margin: 0 auto;
      background: var(--panel);
      border: 1px solid #efc0c8;
      border-radius: 22px;
      box-shadow: 0 24px 80px rgba(42, 16, 20, 0.32);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .module-modal-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 16px 20px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(90deg, #fff6f8, #ffffff);
    }
    .module-modal-title {
      font-size: 18px;
      font-weight: 900;
    }
    .module-modal-close {
      border: 0;
      background: var(--accent);
      color: white;
      border-radius: 999px;
      padding: 9px 14px;
      cursor: pointer;
      font-weight: 800;
    }
    .module-modal-body {
      overflow: auto;
      padding: 0;
    }
    body.modal-open::before {
      content: "";
      position: fixed;
      inset: 0;
      z-index: 50;
      background: rgba(42, 16, 20, 0.54);
      backdrop-filter: blur(4px);
    }
    .section.module-expanded {
      position: fixed;
      inset: 22px;
      z-index: 60;
      overflow: auto;
      background: var(--panel);
      border: 1px solid #efc0c8;
      border-radius: 22px;
      box-shadow: 0 24px 80px rgba(42, 16, 20, 0.32);
      padding: 28px;
    }
    .section.module-expanded[data-modal-layout="catalog-stack"] .upload-grid,
    .section.module-expanded[data-modal-layout="catalog-stack"] .catalog-workspace {
      grid-template-columns: 1fr;
    }
    .section.module-expanded[data-modal-layout="catalog-stack"] .catalog-board {
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    }
    .section.module-expanded[data-modal-layout="catalog-stack"] .upload-card,
    .section.module-expanded[data-modal-layout="catalog-stack"] .panel {
      min-width: 0;
    }
    .section.module-expanded[data-modal-layout="catalog-stack"] .catalog-table-scroll {
      max-height: min(58vh, 620px);
    }
    .modal-only {
      display: none;
    }
    .section.module-expanded .modal-only {
      display: block;
    }
    body.modal-open {
      overflow: hidden;
    }
    .actions {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
      margin-top: 16px;
    }
    .button {
      border: 0;
      border-radius: 12px;
      padding: 12px 18px;
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
      transition: transform 0.05s ease, background 0.2s ease, box-shadow 0.2s ease;
    }
    .button:active { transform: translateY(1px); }
    .primary {
      background: var(--accent);
      color: white;
      box-shadow: 0 10px 24px rgba(198, 40, 57, 0.18);
    }
    .primary:hover { background: var(--accent-strong); }
    .secondary {
      background: var(--soft);
      color: var(--accent-strong);
    }
    .meta, .note {
      margin-top: 16px;
      font-size: 14px;
      color: var(--muted);
    }
    .files {
      margin-top: 16px;
      border: 1px dashed var(--line);
      border-radius: 14px;
      padding: 14px 16px;
      background: #fffefe;
      min-height: 84px;
    }
    .upload-spacer {
      margin-top: 16px;
      min-height: 84px;
      border-radius: 14px;
    }
    .files ul {
      margin: 0;
      padding-left: 18px;
    }
    .status {
      margin-top: 16px;
      padding: 12px 14px;
      border-radius: 12px;
      display: none;
      font-size: 14px;
      line-height: 1.5;
    }
    .status.show { display: block; }
    .status.ok {
      background: #f3fff7;
      color: var(--ok);
      border: 1px solid #abefc6;
    }
    .status.error {
      background: #fff3f4;
      color: var(--error);
      border: 1px solid #f4c7ce;
    }
    .result {
      margin-top: 18px;
      border-top: 1px solid var(--line);
      padding-top: 18px;
    }
    .log-details {
      border-top: 1px solid var(--line);
      padding-top: 14px;
    }
    .log-details summary {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid #f0c6cd;
      border-radius: 999px;
      background: #fff6f8;
      color: var(--accent-strong);
      padding: 8px 12px;
      font-size: 13px;
      font-weight: 800;
      cursor: pointer;
      user-select: none;
    }
    .log-details pre {
      margin-top: 12px;
      max-height: min(42vh, 420px);
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      background: #231417;
      color: #ffe8eb;
      padding: 14px 16px;
      border-radius: 14px;
      font-size: 13px;
      overflow: auto;
      min-height: 48px;
    }
    .search-grid {
      display: grid;
      grid-template-columns: minmax(0, 2fr) 190px 160px 120px;
      gap: 12px;
      align-items: end;
      margin-top: 16px;
    }
    .toggle-field {
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 42px;
      color: var(--accent-strong);
      font-size: 13px;
      font-weight: 800;
    }
    .toggle-field input {
      width: 18px;
      height: 18px;
      accent-color: var(--accent);
    }
    .ask-grid {
      display: grid;
      grid-template-columns: minmax(0, 2fr) 180px 160px 120px;
      gap: 12px;
      align-items: end;
      margin-top: 16px;
    }
    .field label {
      display: block;
      margin-bottom: 8px;
      font-size: 14px;
      font-weight: 600;
      color: var(--text);
    }
    .field input,
    .field select,
    .field textarea {
      width: 100%;
      border: 1px solid var(--line);
      background: white;
      border-radius: 12px;
      padding: 12px 14px;
      font-size: 15px;
      color: var(--text);
    }
    .field input:focus,
    .field select:focus,
    .field textarea:focus {
      outline: 2px solid rgba(198, 40, 57, 0.14);
      border-color: var(--accent);
    }
    .field textarea {
      min-height: 126px;
      resize: vertical;
      font-family: "Segoe UI", Tahoma, sans-serif;
      line-height: 1.5;
    }
    .split {
      margin-top: 20px;
      display: grid;
      grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.95fr);
      gap: 18px;
    }
    .panel {
      border: 1px solid var(--line);
      border-radius: 16px;
      background: var(--soft-2);
      padding: 16px;
      min-height: 120px;
    }
    .panel-title {
      margin: 0 0 12px;
      font-size: 16px;
      font-weight: 700;
    }
    .qa-layout {
      margin-top: 18px;
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(300px, 1fr);
      gap: 18px;
    }
    .stats-grid {
      margin-top: 16px;
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .stat-card {
      border: 1px solid var(--line);
      border-radius: 14px;
      background: white;
      padding: 14px 16px;
    }
    .stat-label {
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--muted);
      margin-bottom: 6px;
    }
    .stat-value {
      font-size: 22px;
      font-weight: 800;
      color: var(--accent-strong);
    }
    .catalog-workspace {
      margin-top: 18px;
      display: grid;
      grid-template-columns: minmax(320px, 0.95fr) minmax(0, 1.35fr);
      gap: 18px;
      align-items: start;
    }
    .table-box {
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: white;
    }
    .table-box table {
      width: 100%;
      border-collapse: collapse;
      min-width: 520px;
    }
    .table-box th,
    .table-box td {
      padding: 12px 14px;
      border-bottom: 1px solid #f1d9dd;
      text-align: left;
      vertical-align: top;
      font-size: 14px;
      line-height: 1.5;
    }
    .table-box th {
      background: #fff5f7;
      color: var(--accent-strong);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .uploaded-documents-panel {
      margin-top: 20px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: #fffdfd;
      padding: 18px;
    }
    .uploaded-documents-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 14px;
    }
    .uploaded-documents-head h2 {
      margin-bottom: 4px;
    }
    .uploaded-documents-head p {
      max-width: 720px;
    }
    .catalog-board {
      margin-top: 16px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 14px;
    }
    .catalog-pane {
      border: 1px solid var(--line);
      border-radius: 16px;
      background: white;
      overflow: hidden;
      min-height: 320px;
    }
    .catalog-pane.ingested {
      border-color: #a8dfbd;
      background: #f8fffb;
    }
    .catalog-pane.pending {
      border-color: #efb3bd;
      background: var(--soft-2);
    }
    .catalog-pane-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      font-weight: 800;
    }
    .catalog-pane.ingested .catalog-pane-head {
      color: #17653b;
      background: #effaf3;
    }
    .catalog-pane.pending .catalog-pane-head {
      color: var(--accent-strong);
      background: var(--soft);
    }
    .catalog-pane-actions {
      display: flex;
      justify-content: flex-end;
      gap: 10px;
      padding: 12px 14px;
      border-top: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.72);
    }
    .catalog-count {
      border-radius: 999px;
      padding: 4px 9px;
      background: white;
      font-size: 12px;
    }
    .catalog-table-scroll {
      overflow: auto;
      max-height: 430px;
    }
    .catalog-table {
      width: 100%;
      border-collapse: collapse;
      min-width: 760px;
    }
    .catalog-table th,
    .catalog-table td {
      padding: 10px 12px;
      border-bottom: 1px solid #f1d9dd;
      text-align: left;
      vertical-align: top;
      font-size: 13px;
      line-height: 1.45;
    }
    .catalog-table th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: #fffafa;
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
    }
    .catalog-table a {
      color: var(--accent-strong);
      font-weight: 700;
      text-decoration: none;
    }
    .catalog-table a:hover {
      text-decoration: underline;
    }
    .catalog-preview-cell {
      width: 118px;
      min-width: 118px;
      white-space: nowrap;
    }
    .catalog-preview-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 92px;
      min-height: 34px;
      padding: 7px 10px;
      white-space: nowrap;
      line-height: 1;
      text-align: center;
    }
    .catalog-select {
      width: 18px;
      height: 18px;
      accent-color: var(--accent);
    }
    .catalog-candidate-row.hidden {
      display: none;
    }
    .catalog-candidate-cell {
      background: #fffafa;
      padding: 0 !important;
    }
    .catalog-candidates {
      display: grid;
      gap: 8px;
      padding: 10px 12px 12px;
    }
    .catalog-candidate-item {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: center;
      border: 1px solid #f0c9cf;
      border-radius: 8px;
      background: white;
      padding: 10px;
    }
    .catalog-candidate-name {
      font-weight: 800;
      color: var(--text);
      word-break: break-word;
    }
    .catalog-candidate-name a {
      color: var(--accent-strong);
      text-decoration: none;
    }
    .catalog-candidate-name a:hover {
      text-decoration: underline;
    }
    .catalog-candidate-meta {
      margin-top: 3px;
      color: var(--muted);
      font-size: 12px;
      word-break: break-word;
    }
    .status-pill {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 11px;
      font-weight: 800;
      white-space: nowrap;
    }
    .status-pill.complete {
      color: #0e5d83;
      background: #e5f5ff;
    }
    .status-pill.partial,
    .status-pill.missing {
      color: #8a5a00;
      background: #fff0c2;
    }
    .status-pill.not_ingested {
      color: var(--accent-strong);
      background: #ffe7eb;
    }
    .draft-grid {
      margin-top: 18px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr);
      gap: 18px;
    }
    .draft-toolbar {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
      margin-top: 12px;
    }
    .draft-toolbar .button {
      padding: 10px 14px;
      font-size: 14px;
    }
    .draft-hint {
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #fff8f9;
      padding: 12px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
      margin-top: 14px;
    }
    .answer-box {
      border: 1px solid var(--line);
      border-radius: 16px;
      background: white;
      padding: 16px;
      min-height: 150px;
    }
    .answer-text {
      font-size: 15px;
      line-height: 1.65;
      color: var(--text);
      white-space: pre-wrap;
    }
    .draft-box {
      border: 1px solid var(--line);
      border-radius: 16px;
      background: white;
      padding: 16px;
      min-height: 340px;
    }
    .draft-text {
      font-size: 14px;
      line-height: 1.7;
      color: var(--text);
      white-space: pre-wrap;
      margin: 0;
      background: transparent;
      padding: 0;
      min-height: auto;
    }
    .source-card {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      background: white;
    }
    .cards {
      display: grid;
      gap: 12px;
    }
    .result-card,
    .similar-card {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      background: white;
    }
    .result-card:hover,
    .similar-card:hover,
    .source-card:hover {
      border-color: #df9da8;
      box-shadow: 0 10px 24px rgba(161, 33, 49, 0.08);
    }
    .result-head,
    .similar-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
      margin-bottom: 8px;
    }
    .title {
      font-weight: 700;
      line-height: 1.35;
    }
    .tag {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 10px;
      background: var(--soft);
      color: var(--accent-strong);
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }
    .duplicate-workspace-tabs,
    .comparison-result-tabs {
      display: flex;
      align-items: center;
      gap: 4px;
      border-bottom: 1px solid var(--line);
      margin-bottom: 18px;
    }
    .duplicate-workspace-tab,
    .comparison-result-tab {
      min-height: 42px;
      border: 0;
      border-bottom: 3px solid transparent;
      background: transparent;
      color: var(--muted);
      cursor: pointer;
      font-size: 14px;
      font-weight: 800;
      padding: 9px 14px 8px;
    }
    .duplicate-workspace-tab:hover,
    .comparison-result-tab:hover {
      color: var(--accent-strong);
      background: var(--soft-2);
    }
    .duplicate-workspace-tab.active,
    .comparison-result-tab.active {
      color: var(--accent-strong);
      border-bottom-color: var(--accent);
    }
    .comparison-result-tab.active::before {
      content: "\\2713";
      margin-right: 7px;
      color: var(--ok);
    }
    .duplicate-workspace-pane[hidden],
    .comparison-result-pane[hidden] {
      display: none;
    }
    .comparison-source-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 44px minmax(0, 1fr);
      gap: 14px;
      align-items: stretch;
    }
    .comparison-source {
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      padding: 16px 0;
      min-width: 0;
    }
    .comparison-source-label {
      color: var(--accent-strong);
      font-size: 12px;
      font-weight: 900;
      margin-bottom: 8px;
      text-transform: uppercase;
    }
    .comparison-source select {
      width: 100%;
      min-height: 44px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: white;
      color: var(--text);
      padding: 10px 12px;
      font-size: 14px;
    }
    .comparison-source-actions {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 10px;
      min-height: 38px;
    }
    .comparison-swap {
      align-self: center;
      width: 44px;
      height: 44px;
      border: 1px solid var(--line);
      border-radius: 50%;
      background: white;
      color: var(--accent-strong);
      cursor: pointer;
      font-size: 20px;
      font-weight: 900;
    }
    .comparison-swap:hover {
      border-color: var(--accent);
      background: var(--soft);
    }
    .comparison-controls {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 16px;
    }
    .comparison-run-actions {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .comparison-method-help {
      position: relative;
    }
    .comparison-info-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 34px;
      height: 34px;
      border: 1px solid var(--line);
      border-radius: 50%;
      background: white;
      color: var(--accent-strong);
      cursor: help;
      font-size: 15px;
      font-weight: 900;
    }
    .comparison-info-button:hover,
    .comparison-info-button:focus-visible {
      border-color: var(--accent);
      outline: 2px solid rgba(194, 36, 55, 0.16);
      outline-offset: 2px;
    }
    .comparison-method-tooltip {
      position: absolute;
      right: 0;
      bottom: calc(100% + 10px);
      z-index: 30;
      width: min(340px, calc(100vw - 32px));
      padding: 13px 14px;
      border: 1px solid #5a3339;
      background: #24191b;
      box-shadow: 0 12px 28px rgba(45, 20, 25, 0.22);
      color: white;
      opacity: 0;
      pointer-events: none;
      transform: translateY(4px);
      visibility: hidden;
      transition: opacity 140ms ease, transform 140ms ease, visibility 140ms ease;
    }
    .comparison-method-tooltip::after {
      position: absolute;
      right: 10px;
      bottom: -7px;
      width: 12px;
      height: 12px;
      border-right: 1px solid #5a3339;
      border-bottom: 1px solid #5a3339;
      background: #24191b;
      content: "";
      transform: rotate(45deg);
    }
    .comparison-method-help:hover .comparison-method-tooltip,
    .comparison-method-help:focus-within .comparison-method-tooltip {
      opacity: 1;
      transform: translateY(0);
      visibility: visible;
    }
    .comparison-method-title {
      margin-bottom: 8px;
      font-size: 13px;
      font-weight: 900;
    }
    .comparison-method-row {
      display: grid;
      grid-template-columns: 88px minmax(0, 1fr);
      gap: 8px;
      padding: 4px 0;
      font-size: 12px;
      line-height: 1.35;
    }
    .comparison-method-row strong {
      color: #ffd36a;
    }
    .comparison-method-note {
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px solid rgba(255, 255, 255, 0.2);
      color: #eadcdf;
      font-size: 11px;
      line-height: 1.4;
    }
    .comparison-persist {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
    }
    .comparison-persist input {
      width: 18px;
      height: 18px;
      accent-color: var(--accent);
    }
    .comparison-summary {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin: 16px 0;
    }
    .comparison-summary-item {
      border-left: 3px solid var(--accent);
      background: var(--soft-2);
      padding: 10px 12px;
      min-width: 0;
    }
    .comparison-summary-value {
      display: block;
      color: var(--text);
      font-size: 20px;
      font-weight: 900;
      line-height: 1.1;
    }
    .comparison-summary-label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    .comparison-results {
      border-top: 1px solid var(--line);
    }
    .comparison-row {
      padding: 16px 0;
      border-bottom: 1px solid #ead8dc;
    }
    .comparison-row.has-pdf-highlight {
      border-left: 4px solid var(--pair-color);
      padding-left: 12px;
    }
    .comparison-row-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }
    .comparison-row-topic {
      font-size: 15px;
      font-weight: 900;
      line-height: 1.35;
    }
    .comparison-row-summary {
      color: var(--text);
      font-size: 14px;
      line-height: 1.55;
      margin-top: 4px;
    }
    .comparison-evidence-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 12px;
    }
    .comparison-evidence {
      border-left: 3px solid #df9da8;
      background: #fffafa;
      padding: 10px 12px;
      min-width: 0;
    }
    .comparison-evidence-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      color: var(--accent-strong);
      font-size: 12px;
      font-weight: 900;
    }
    .comparison-evidence-text {
      margin-top: 7px;
      color: var(--text);
      font-size: 13px;
      line-height: 1.5;
      overflow-wrap: anywhere;
    }
    .comparison-open {
      border: 0;
      background: transparent;
      color: var(--accent-strong);
      cursor: pointer;
      font-size: 12px;
      font-weight: 800;
      padding: 2px 0;
    }
    .comparison-open:hover {
      text-decoration: underline;
    }
    .comparison-open:disabled {
      color: var(--muted);
      cursor: default;
      text-decoration: none;
    }
    .comparison-highlight-actions {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .comparison-pair-marker {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid var(--pair-color);
      border-radius: 999px;
      background: white;
      box-shadow: inset 0 -3px 0 var(--pair-color);
      color: var(--text);
      font-size: 12px;
      font-weight: 900;
      padding: 4px 9px;
      white-space: nowrap;
    }
    .comparison-pair-marker::before,
    .comparison-highlight-swatch {
      width: 11px;
      height: 11px;
      border: 1px solid rgba(32, 20, 22, 0.18);
      border-radius: 3px;
      background: var(--pair-color);
      content: "";
      flex: 0 0 auto;
    }
    .comparison-focus {
      border: 0;
      background: transparent;
      color: var(--accent-strong);
      cursor: pointer;
      font-size: 12px;
      font-weight: 900;
      padding: 4px 0;
    }
    .comparison-focus:hover {
      text-decoration: underline;
    }
    .comparison-pdf-workspace {
      border-top: 1px solid var(--line);
      margin-top: 24px;
      padding-top: 20px;
    }
    .comparison-pdf-head,
    .comparison-pdf-toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .comparison-pdf-head-actions {
      display: flex;
      align-items: flex-end;
      flex-direction: column;
      gap: 8px;
    }
    .comparison-pair-fullscreen {
      min-height: 36px;
      padding: 7px 12px;
      white-space: nowrap;
    }
    .comparison-highlight-legend {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 6px;
      flex-wrap: wrap;
    }
    .comparison-highlight-legend-item {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
    }
    .comparison-pdf-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 12px;
      margin-top: 14px;
    }
    .comparison-pdf-panel {
      border: 1px solid var(--line);
      background: #f7f4f5;
      min-width: 0;
    }
    .comparison-pdf-toolbar {
      min-height: 44px;
      padding: 9px 12px;
      border-bottom: 1px solid var(--line);
      background: white;
      color: var(--text);
      font-size: 12px;
      font-weight: 900;
    }
    .comparison-pdf-frame {
      display: block;
      width: 100%;
      height: 680px;
      border: 0;
      background: #e8e3e4;
    }
    .comparison-pdf-placeholder {
      min-height: 220px;
      padding: 28px 18px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.55;
    }
    .graph-layout {
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
      gap: 18px;
      margin-top: 16px;
      align-items: start;
    }
    .graph-dashboard {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 16px;
    }
    .graph-browser {
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
      gap: 18px;
      margin-top: 16px;
      align-items: start;
    }
    .graph-sidebar,
    .graph-main {
      border: 1px solid var(--line);
      border-radius: 16px;
      background: linear-gradient(180deg, #fffafa 0%, #fff 100%);
      padding: 16px;
      min-width: 0;
    }
    .graph-sidebar {
      max-height: 720px;
      overflow: auto;
    }
    .graph-controls {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 220px;
      gap: 12px;
      margin-bottom: 14px;
      align-items: end;
    }
    .category-tree {
      display: grid;
      gap: 10px;
    }
    .category-group {
      display: grid;
      gap: 6px;
    }
    .category-group-title {
      color: var(--muted);
      font-size: 11px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      margin-top: 4px;
    }
    .category-button {
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      border: 1px solid #f0c6cd;
      border-radius: 10px;
      background: #fff;
      color: var(--text);
      padding: 9px 10px;
      cursor: pointer;
      font-size: 13px;
      font-weight: 800;
      text-align: left;
    }
    .category-button:hover,
    .category-button.active {
      border-color: var(--accent);
      background: var(--soft);
      color: var(--accent-strong);
    }
    .category-button .count {
      color: var(--muted);
      font-weight: 800;
      flex: 0 0 auto;
    }
    .density-chart {
      display: grid;
      gap: 9px;
      margin-bottom: 16px;
    }
    .density-row {
      display: grid;
      grid-template-columns: minmax(120px, 0.55fr) minmax(120px, 1fr) 44px;
      gap: 10px;
      align-items: center;
      font-size: 12px;
      color: var(--muted);
    }
    .density-label {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--text);
      font-weight: 800;
    }
    .density-track {
      height: 10px;
      border-radius: 999px;
      background: #f7dfe3;
      overflow: hidden;
    }
    .density-bar {
      height: 100%;
      border-radius: 999px;
      background: var(--accent);
    }
    .document-table-wrap {
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: white;
    }
    .document-table {
      width: 100%;
      min-width: 780px;
      border-collapse: collapse;
    }
    .document-table th,
    .document-table td {
      padding: 11px 12px;
      border-bottom: 1px solid #f1d9dd;
      text-align: left;
      vertical-align: top;
      font-size: 13px;
      line-height: 1.45;
    }
    .document-table th {
      background: #fff5f7;
      color: var(--accent-strong);
      font-size: 11px;
      text-transform: uppercase;
    }
    .doc-name {
      font-weight: 900;
      color: var(--text);
    }
    .doc-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
    }
    .doc-tag {
      border-radius: 999px;
      background: var(--soft);
      color: var(--accent-strong);
      padding: 3px 7px;
      font-size: 11px;
      font-weight: 800;
    }
    @media (max-width: 980px) {
      .graph-dashboard,
      .graph-browser,
      .graph-layout,
      .graph-controls {
        grid-template-columns: 1fr;
      }
    }
    .chat-layout {
      display: grid;
      grid-template-columns: minmax(0, 1.7fr) minmax(340px, 0.75fr);
      gap: 18px;
      margin-top: 16px;
      align-items: stretch;
    }
    body.chat-focus .section[data-module-key="chat"] {
      padding-left: 34px;
      padding-right: 34px;
    }
    body.chat-focus .chat-layout {
      grid-template-columns: minmax(0, 1.85fr) minmax(360px, 0.85fr);
      gap: 22px;
    }
    .section.module-expanded[data-module-key="chat"] .chat-layout {
      grid-template-columns: minmax(0, 1.95fr) minmax(380px, 0.85fr);
      gap: 22px;
    }
    .chat-panel {
      display: flex;
      flex-direction: column;
      min-height: 650px;
    }
    .chat-toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }
    .chat-agent {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
    }
    .chat-avatar {
      width: 38px;
      height: 38px;
      border-radius: 12px;
      display: grid;
      place-items: center;
      background: #c92037;
      color: white;
      font-weight: 900;
      letter-spacing: 0;
      flex: 0 0 auto;
    }
    .chat-agent-title {
      font-weight: 800;
      line-height: 1.2;
    }
    .chat-agent-subtitle {
      color: var(--muted);
      font-size: 12px;
      margin-top: 2px;
    }
    .chat-toolbar-actions {
      display: flex;
      align-items: center;
      gap: 8px;
      flex: 0 0 auto;
    }
    .chat-toolbar-actions select {
      min-width: 128px;
      height: 38px;
      padding: 0 34px 0 12px;
      font-size: 13px;
    }
    .chat-messages {
      display: flex;
      flex-direction: column;
      gap: 10px;
      min-height: 420px;
      max-height: 620px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 16px;
      background:
        linear-gradient(180deg, rgba(255, 246, 248, 0.72), rgba(255, 255, 255, 0.96)),
        white;
      padding: 16px;
      scroll-behavior: smooth;
    }
    .chat-message {
      max-width: min(82%, 720px);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 10px 12px 12px;
      white-space: pre-wrap;
      line-height: 1.55;
      font-size: 14px;
      box-shadow: 0 8px 18px rgba(56, 23, 29, 0.05);
    }
    .chat-message.user {
      align-self: flex-end;
      background: #c92037;
      border-color: #c92037;
      color: white;
    }
    .chat-message.assistant {
      align-self: flex-start;
      background: #fff;
    }
    .chat-message-label {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 5px;
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      color: var(--muted);
      letter-spacing: 0;
    }
    .chat-message.user .chat-message-label {
      color: rgba(255, 255, 255, 0.72);
    }
    .chat-message-body {
      white-space: pre-wrap;
    }
    .chat-message-meta {
      color: #8a4c57;
      font-size: 10px;
      font-weight: 700;
      text-transform: none;
    }
    .chat-prompts-shell {
      position: relative;
      min-width: 0;
    }
    .chat-prompts {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }
    .chat-prompt {
      border: 1px solid #efbdc5;
      border-radius: 999px;
      background: #fff8f9;
      color: #5b2730;
      padding: 8px 11px;
      font-size: 12px;
      font-weight: 800;
      cursor: pointer;
    }
    .chat-prompt:hover {
      border-color: #d85a6b;
      color: var(--accent-strong);
    }
    .chat-prompt-help {
      position: relative;
      display: inline-flex;
    }
    .chat-prompt.chat-prompt-feature {
      border-color: var(--accent);
      background: var(--accent);
      color: white;
    }
    .chat-prompt.chat-prompt-feature:hover,
    .chat-prompt.chat-prompt-feature:focus-visible {
      border-color: var(--accent-strong);
      background: var(--accent-strong);
      color: white;
    }
    .chat-prompt-tooltip {
      position: absolute;
      bottom: calc(100% + 10px);
      left: 0;
      z-index: 40;
      width: min(300px, calc(100vw - 32px));
      visibility: hidden;
      border: 1px solid rgba(255, 255, 255, 0.14);
      border-radius: 6px;
      background: #17201e;
      color: #f4fbf8;
      padding: 10px 12px;
      font-size: 12px;
      font-weight: 600;
      line-height: 1.45;
      text-align: left;
      opacity: 0;
      pointer-events: none;
      transform: translateY(4px);
      transition: opacity 120ms ease, transform 120ms ease, visibility 120ms ease;
      box-shadow: 0 10px 28px rgba(13, 31, 24, 0.2);
    }
    .chat-prompt-tooltip::after {
      content: "";
      position: absolute;
      top: 100%;
      left: 22px;
      border: 6px solid transparent;
      border-top-color: #17201e;
    }
    .chat-prompts-shell:has(.chat-prompt-feature:hover) .chat-prompt-tooltip,
    .chat-prompts-shell:has(.chat-prompt-feature:focus-visible) .chat-prompt-tooltip {
      visibility: visible;
      opacity: 1;
      transform: translateY(0);
    }
    .chat-input-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 132px;
      gap: 10px;
      margin-top: 12px;
      align-items: stretch;
    }
    .chat-input-row textarea {
      min-height: 54px;
      max-height: 140px;
      resize: vertical;
      line-height: 1.45;
    }
    .chat-input-row .button {
      min-height: 54px;
    }
    .chat-side {
      display: flex;
      flex-direction: column;
      min-height: 650px;
    }
    .chat-source-head {
      display: flex;
      align-items: start;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 10px;
    }
    .chat-source-meta {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }
    .chat-source-card {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 13px;
      background: white;
      cursor: pointer;
    }
    .chat-source-card:hover {
      border-color: #df9da8;
      box-shadow: 0 10px 24px rgba(161, 33, 49, 0.08);
    }
    .chat-source-card .excerpt {
      max-height: 160px;
      overflow: hidden;
    }
    .graph-node {
      cursor: pointer;
    }
    .graph-label {
      font-size: 11px;
      fill: #3a1a20;
      pointer-events: none;
    }
    .graph-edge {
      stroke: #e4a8b1;
      stroke-width: 1.2;
      opacity: 0.62;
    }
    .tag-cloud {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .tag-chip {
      display: inline-flex;
      gap: 6px;
      align-items: center;
      border: 1px solid #f0c6cd;
      background: #fff6f8;
      color: var(--accent-strong);
      border-radius: 999px;
      padding: 7px 10px;
      font-size: 12px;
      font-weight: 800;
    }
    .tag-chip span {
      color: var(--muted);
      font-weight: 700;
    }
    .small {
      font-size: 13px;
      color: var(--muted);
    }
    .excerpt {
      margin-top: 10px;
      font-size: 14px;
      line-height: 1.55;
      color: var(--text);
    }
    mark {
      background: #fff29a;
      color: #4b2a00;
      padding: 0 2px;
      border-radius: 4px;
      box-shadow: inset 0 -1px 0 rgba(196, 147, 0, 0.18);
    }
    .empty {
      color: var(--muted);
      font-size: 14px;
    }
    .count {
      color: var(--accent-strong);
      font-weight: 700;
    }
    input[type="file"] { display: none; }
    @media (max-width: 920px) {
      .upload-grid,
      .search-grid,
      .ask-grid,
      .qa-layout,
      .catalog-workspace,
      .catalog-board,
      .graph-layout,
      .chat-layout,
      .comparison-source-grid,
      .comparison-evidence-grid,
      .comparison-pdf-grid,
      .split {
        grid-template-columns: 1fr;
      }
      .comparison-summary {
        grid-template-columns: 1fr;
      }
      .comparison-swap {
        justify-self: center;
        transform: rotate(90deg);
      }
      .comparison-row-head {
        flex-direction: column;
      }
      .comparison-row-head .tag {
        align-self: flex-start;
      }
      .comparison-highlight-actions,
      .comparison-highlight-legend {
        justify-content: flex-start;
      }
      .comparison-pdf-head {
        align-items: flex-start;
        flex-direction: column;
      }
      .comparison-pdf-head-actions {
        align-items: flex-start;
      }
      .comparison-method-tooltip {
        right: auto;
        left: 0;
        width: min(300px, calc(100vw - 96px));
      }
      .comparison-method-tooltip::after {
        right: auto;
        left: 10px;
      }
      .comparison-method-row {
        grid-template-columns: 58px minmax(0, 1fr);
      }
      .comparison-pdf-frame {
        height: 520px;
      }
      .chat-input-row {
        grid-template-columns: 1fr;
      }
      .chat-toolbar {
        align-items: flex-start;
        flex-direction: column;
      }
      .chat-toolbar-actions {
        width: 100%;
        flex-wrap: wrap;
      }
      .chat-toolbar-actions select {
        flex: 1 1 140px;
        min-width: 0;
      }
      .chat-message {
        max-width: 100%;
      }
      .stats-grid {
        grid-template-columns: 1fr;
      }
      .module-modal {
        padding: 10px;
      }
      .section-head {
        flex-direction: column;
      }

      body[data-app-variant="big_agent"].chat-focus .section[data-module-key="chat"],
      body[data-app-variant="big_agent"] .section.module-expanded[data-module-key="chat"] {
        padding-right: 18px;
        padding-left: 18px;
      }
      body[data-app-variant="big_agent"] .chat-layout,
      body[data-app-variant="big_agent"].chat-focus .chat-layout,
      body[data-app-variant="big_agent"] .section.module-expanded[data-module-key="chat"] .chat-layout {
        width: 100%;
        min-width: 0;
        grid-template-columns: minmax(0, 1fr);
      }
      body[data-app-variant="big_agent"] .chat-layout > *,
      body[data-app-variant="big_agent"] .chat-panel,
      body[data-app-variant="big_agent"] .chat-side {
        width: 100%;
        min-width: 0;
      }
      body[data-app-variant="big_agent"] .chat-side {
        min-height: 300px;
      }
    }

    @media (max-width: 620px) {
      body[data-app-variant="big_agent"].chat-focus .section[data-module-key="chat"],
      body[data-app-variant="big_agent"] .section.module-expanded[data-module-key="chat"] {
        padding-right: 12px;
        padding-left: 12px;
      }
      body[data-app-variant="big_agent"] .chat-layout {
        gap: 12px;
        margin-top: 12px;
      }
      body[data-app-variant="big_agent"] .chat-panel,
      body[data-app-variant="big_agent"] .chat-side {
        min-height: 0;
        padding: 12px;
      }
      body[data-app-variant="big_agent"] .chat-toolbar {
        gap: 9px;
        margin-bottom: 9px;
      }
      body[data-app-variant="big_agent"] .chat-agent-subtitle {
        font-size: 11px;
      }
      body[data-app-variant="big_agent"] .chat-toolbar-actions {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 6px;
      }
      body[data-app-variant="big_agent"] .chat-toolbar-actions select,
      body[data-app-variant="big_agent"] .chat-toolbar-actions .button {
        width: 100%;
        min-width: 0;
        height: 38px;
        padding-right: 8px;
        padding-left: 8px;
        font-size: 11px;
      }
      body[data-app-variant="big_agent"] .chat-messages {
        width: 100%;
        min-width: 0;
        min-height: 340px;
        max-height: 52vh;
        overflow-x: hidden;
        padding: 12px;
        border-radius: 10px;
      }
      body[data-app-variant="big_agent"] .chat-message {
        max-width: 94%;
        overflow-wrap: anywhere;
        padding: 9px 10px 10px;
        font-size: 13px;
      }
      body[data-app-variant="big_agent"] .chat-prompts {
        flex-wrap: nowrap;
        gap: 6px;
        margin-top: 9px;
        padding-bottom: 4px;
        overflow-x: auto;
      }
      body[data-app-variant="big_agent"] .chat-prompt-help,
      body[data-app-variant="big_agent"] .chat-prompt {
        flex: 0 0 auto;
      }
      body[data-app-variant="big_agent"] .chat-prompt {
        padding: 7px 9px;
        white-space: nowrap;
      }
      body[data-app-variant="big_agent"] .chat-input-row {
        grid-template-columns: minmax(0, 1fr) 48px;
        gap: 7px;
        margin-top: 9px;
        align-items: end;
      }
      body[data-app-variant="big_agent"] .chat-input-row textarea {
        width: 100%;
        min-width: 0;
        min-height: 48px;
        max-height: 112px;
        resize: none;
      }
      body[data-app-variant="big_agent"] .chat-input-row .button {
        display: grid;
        place-items: center;
        width: 48px;
        min-width: 48px;
        min-height: 48px;
        padding: 0;
        font-size: 0;
      }
      body[data-app-variant="big_agent"] .chat-input-row .button::before {
        content: "\\2191";
        font-size: 22px;
        line-height: 1;
      }
      body[data-app-variant="big_agent"] #chatStatus {
        min-width: 0;
        overflow-wrap: anywhere;
      }
      body[data-app-variant="big_agent"] .chat-source-head {
        align-items: flex-start;
        flex-direction: column;
      }
    }
__VARIANT_CSS__
  </style>
</head>
<body data-app-variant="__APP_VARIANT__">
  <div class="wrap">
    <div class="stack">
      <div class="card">
        <div class="hero">
          <div class="hero-title-row">
            <h1>__BRAND_NAME__</h1>
            <button class="raporhub-sidebar-toggle" id="raporhubSidebarToggle" type="button" aria-label="Sol menuyu daralt" aria-expanded="true" title="Sol menuyu daralt" data-raporhub-only hidden>
              <span class="raporhub-sidebar-toggle-icon" aria-hidden="true"></span>
            </button>
            <span class="version-pill app-version-pill">v__APP_VERSION__</span>
            <span class="version-pill compute-pill compute-__DEVICE_KIND__" title="Embedding islemleri __DEVICE_LABEL__ ile calisiyor">__DEVICE_LABEL__</span>
            <span class="version-pill model-pill">model: __MODEL_LABEL__</span>
            <a class="logout-link" href="/logout">Cikis</a>
          </div>
          <div class="raporhub-brand-subtitle" data-raporhub-only hidden>Muhendislik rapor zekasi</div>
          <p>__WORKSPACE_INTRO__</p>
          <div class="module-switcher" aria-label="Modul secimi">
            <div class="raporhub-nav-label" data-raporhub-only hidden>Calisma Alani</div>
            <button class="module-filter" type="button" data-module-filter="home" data-nav-label="Genel Bakis" data-nav-short="GB" title="Genel Bakis" data-raporhub-only hidden>Genel Bakis</button>
            <button class="module-filter active" type="button" data-module-filter="upload" data-nav-label="Raporlar" data-nav-short="RP" title="Raporlar">Raporlar</button>
            <button class="module-filter" type="button" data-module-filter="catalog" data-nav-label="Katalog" data-nav-short="KT" title="Katalog" data-repocto-hide>Katalog</button>
            <div class="raporhub-nav-label" data-raporhub-only hidden>Bilgi Analizi</div>
            <button class="module-filter" type="button" data-module-filter="search" data-nav-label="Arama" data-nav-short="AR" title="Arama">Arama</button>
            <button class="module-filter" type="button" data-module-filter="chat" data-nav-label="Chatbot" data-nav-short="AI" title="Chatbot">Chatbot</button>
            <button class="module-filter" type="button" data-module-filter="duplicates" data-nav-label="Mukerrer" data-nav-short="MK" title="Mukerrer">Mukerrer</button>
            <button class="module-filter" type="button" data-module-filter="graph" data-nav-label="Kategoriler" data-nav-short="KG" title="Kategoriler" data-repocto-label="Kütüphane" data-repocto-short="KT">Kategoriler</button>
            <div class="raporhub-nav-label" data-raporhub-only hidden>Rapor Uretimi</div>
            <button class="module-filter" type="button" data-module-filter="qa" data-nav-label="Q&A" data-nav-short="QA" title="Q&A" data-raporhub-hide>Q&A</button>
            <button class="module-filter" type="button" data-module-filter="writing" data-nav-label="Yazim" data-nav-short="YZ" title="Yazim" data-repocto-label="Raporlama" data-repocto-short="RP">Yazim</button>
            <button class="module-filter" type="button" data-module-filter="all" data-raporhub-hide>Her sey</button>
          </div>
          <div class="raporhub-sidebar-footer" data-raporhub-only hidden>
            <div class="raporhub-local-status"><span></span>Yerel calisma alani hazir</div>
            <a href="/logout">Oturumu kapat</a>
          </div>
        </div>
        <header class="raporhub-topbar" data-raporhub-only hidden>
          <div class="repocto-page-context" data-repocto-only hidden>
            <span>REPORT INTELLIGENCE</span>
            <strong id="repoctoPageTitle">Chatbot</strong>
          </div>
          <button class="raporhub-theme-toggle" id="raporhubThemeToggle" type="button" aria-label="Karanlik moda gec" aria-pressed="false" title="Karanlik moda gec">
            <span class="raporhub-theme-icon" aria-hidden="true"></span>
          </button>
          <details class="raporhub-system-menu">
            <summary title="Sistem durumunu goster">
              <span class="raporhub-device-dot compute-__DEVICE_KIND__"></span>
              <strong>__DEVICE_LABEL__</strong>
              <span>v__APP_VERSION__</span>
            </summary>
            <div class="raporhub-system-popover">
              <div><span>Embedding</span><strong>__DEVICE_LABEL__</strong></div>
              <div><span>Model</span><strong>__MODEL_LABEL__</strong></div>
              <div><span>Surum</span><strong>v__APP_VERSION__</strong></div>
            </div>
          </details>
        </header>
        <div class="section raporhub-home" data-module-title="Genel Bakis" data-module-key="home" data-raporhub-only hidden>
          <div class="raporhub-welcome-band">
            <div>
              <div class="raporhub-eyebrow">RAPOR ZEKA CALISMA ALANI</div>
              <h2>Bugun hangi raporu inceleyecegiz?</h2>
              <p>Rapor havuzunda ara, kaynakli cevap al veya yeni belgeleri calisma alanina ekle.</p>
            </div>
            <button class="button secondary" id="raporhubUploadShortcut" type="button">Rapor Yukle</button>
          </div>

          <div class="repocto-capability-strip" data-repocto-only hidden aria-label="RepOcto hizli islemleri">
            <button type="button" data-home-action="chat"><i>01</i><span><strong>Kaynakli Asistan</strong><span>Raporlardan kanitli cevap al</span></span></button>
            <button type="button" data-home-action="search"><i>02</i><span><strong>Akilli Arama</strong><span>Bilgiyi belge ve pasajda bul</span></span></button>
            <button type="button" data-home-action="comparison"><i>03</i><span><strong>Karsilastirma</strong><span>Iki teknik raporu yan yana incele</span></span></button>
            <button type="button" data-home-action="writing"><i>04</i><span><strong>Rapor Yazimi</strong><span>Kaynaklardan ilk taslagi olustur</span></span></button>
          </div>

          <div class="raporhub-question-workspace">
            <div class="raporhub-question-copy">
              <span>__BRAND_DATIVE__ sor</span>
              <strong>Belgelerden kanitli bir cevap olustur</strong>
            </div>
            <div class="raporhub-question-row">
              <textarea id="raporhubHomeQuestion" rows="2" placeholder="Ornek: BIG-E konfor raporunu ozetle veya iki raporun sonuclarini karsilastir"></textarea>
              <button class="button primary" id="raporhubHomeAskButton" type="button">Asistana Sor</button>
            </div>
            <div class="raporhub-starters" aria-label="Ornek sorular">
              <button type="button" data-home-prompt="En son yuklenen raporun ana konusu nedir?">Son raporun konusu</button>
              <button type="button" data-home-prompt="En uzun rapor hangisidir?">En uzun rapor</button>
              <button type="button" data-home-action="comparison">Iki raporu karsilastir</button>
            </div>
          </div>

          <div class="raporhub-metric-strip" aria-label="Calisma alani ozeti">
            <div><span>Toplam rapor</span><strong id="raporhubDocumentCount">-</strong></div>
            <div><span>Metin parcasi</span><strong id="raporhubChunkCount">-</strong></div>
            <div><span>Embedding kapsami</span><strong id="raporhubEmbeddingCoverage">-</strong></div>
            <div><span>Son yukleme</span><strong id="raporhubLastUpload">-</strong></div>
          </div>

          <div class="raporhub-overview-grid">
            <section class="raporhub-recent-workspace">
              <div class="raporhub-panel-heading">
                <div>
                  <span>RAPOR HAVUZU</span>
                  <h3>Son eklenen raporlar</h3>
                </div>
                <button type="button" data-home-action="upload">Tumunu gor</button>
              </div>
              <div class="raporhub-recent-list" id="raporhubRecentDocuments">
                <div class="raporhub-skeleton-row"></div>
                <div class="raporhub-skeleton-row"></div>
                <div class="raporhub-skeleton-row"></div>
              </div>
            </section>

            <aside class="raporhub-readiness-panel">
              <div class="raporhub-panel-heading">
                <div>
                  <span>SISTEM DURUMU</span>
                  <h3>Aramaya hazirlik</h3>
                </div>
                <span class="raporhub-ready-badge" id="raporhubReadinessLabel">Kontrol ediliyor</span>
              </div>
              <div class="raporhub-coverage-track"><span id="raporhubCoverageBar"></span></div>
              <div class="raporhub-readiness-copy" id="raporhubReadinessCopy">Rapor ve embedding bilgileri yukleniyor.</div>
              <dl class="raporhub-system-facts">
                <div><dt>Calisma birimi</dt><dd>__DEVICE_LABEL__</dd></div>
                <div><dt>Embedding modeli</dt><dd>__MODEL_LABEL__</dd></div>
                <div><dt>Dosya turleri</dt><dd id="raporhubFileTypes">-</dd></div>
              </dl>
              <button class="raporhub-text-action" type="button" data-home-action="search">Raporlarda arama yap</button>
            </aside>
          </div>
          <div class="raporhub-overview-status" id="raporhubOverviewStatus">Calisma alani verileri yukleniyor.</div>
        </div>
        <div class="section" data-module-title="Raporlar" data-module-key="upload">
          <div class="section-head">
            <div>
              <h2>Raporlar</h2>
              <p>Bir veya birden fazla PDF/DOCX/PPTX raporunu ayni alandan sisteme ekle.</p>
            </div>
            <button class="expand-button" type="button" data-expand-module>Buyut</button>
          </div>
          <div class="upload-grid report-upload-grid">
            <div class="upload-card">
              <h2>Rapor Yukle</h2>
              <p>Tek dosya veya birden fazla rapor sec; hepsi ayni yukleme islemiyle islenir.</p>
              <div class="actions">
                <label class="button secondary" for="reportPicker">Rapor Sec</label>
                <button class="button primary" id="uploadButton" type="button">Yuklemeyi Baslat</button>
                <input id="reportPicker" type="file" accept=".pdf,.docx,.pptx" multiple />
              </div>
              <div class="meta" id="summary">Henuz rapor secilmedi.</div>
              <div class="files">
                <ul id="filesList"><li>Dosya listesi burada gorunecek.</li></ul>
              </div>
              <div class="status" id="statusBox"></div>
              <div class="result" id="uploadResults" hidden>
                <div class="panel-title">Islem Sonucu</div>
                <div class="files">
                  <ul id="uploadResultList"></ul>
                </div>
              </div>
            </div>
          </div>
          <div class="modal-only uploaded-documents-panel">
            <div class="uploaded-documents-head">
              <div>
                <h2>Icerideki Raporlar</h2>
                <p>Sisteme yuklenmis PDF/DOCX/PPTX raporlarini burada kontrol et. Satira tiklayinca orijinal dosya acilir.</p>
              </div>
              <button class="button secondary" id="uploadedDocumentsRefreshButton" type="button">Listeyi Yenile</button>
            </div>
            <div class="note" id="uploadedDocumentsStatus">Rapor listesi henuz yuklenmedi.</div>
            <div class="table-box" style="margin-top:12px;">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Rapor</th>
                    <th>Tur</th>
                    <th>Chunk</th>
                    <th>Embedding</th>
                    <th>Yuklenme</th>
                  </tr>
                </thead>
                <tbody id="uploadedDocumentsTable">
                  <tr><td colspan="6" class="small">Raporlar modulu buyutulunce liste yenilenecek.</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <div class="section" data-module-title="Arama" data-module-key="search">
          <div class="section-head">
            <div>
              <h2>Arama</h2>
              <p>Rapor iceriginde ara; sagda bulunan sonuclara benzer raporlari gor.</p>
            </div>
            <button class="expand-button" type="button" data-expand-module>Buyut</button>
          </div>
          <div class="search-grid">
            <div class="field">
              <label for="searchQuery">Sorgu</label>
              <input id="searchQuery" type="text" placeholder="Ornek: titresim analizi, motor takozu, en kotu senaryo" />
            </div>
            <div class="field">
              <label for="searchMode">Mod</label>
              <select id="searchMode">
                <option value="hybrid">hybrid</option>
                <option value="semantic">semantic</option>
                <option value="keyword">keyword</option>
              </select>
            </div>
            <div class="field">
              <label>&nbsp;</label>
              <button class="button primary" id="searchButton" type="button" style="width:100%;">Ara</button>
            </div>
          </div>
          <div class="note" id="searchMeta">Arama yapilmadi.</div>
          <div class="split" id="searchResultsLayout">
            <div class="panel">
              <div class="panel-title">Sonuclar</div>
              <div id="resultsList" class="cards">
                <div class="empty">Sonuclar burada listelenecek.</div>
              </div>
            </div>
            <div class="panel similar-panel">
              <div class="panel-title">Benzer Raporlar</div>
              <div id="similarList" class="cards">
                <div class="empty">Benzer rapor onerileri burada listelenecek.</div>
              </div>
            </div>
          </div>
        </div>
        <div class="section" data-module-title="Chatbot" data-module-key="chat">
          <div class="section-head">
            <div>
              <h2>Chatbot</h2>
              <p>Raporlar uzerinden sohbet et; cevaplar kaynak pasajlarla birlikte gelir.</p>
            </div>
            <button class="expand-button" type="button" data-expand-module>Buyut</button>
          </div>
          <div class="chat-layout">
            <div class="panel chat-panel">
              <div class="chat-toolbar">
                <div class="chat-agent">
                  <div class="chat-avatar">__BRAND_INITIALS__</div>
                  <div>
                    <div class="chat-agent-title">Rapor Asistani</div>
                    <div class="chat-agent-subtitle">Kaynakli cevap ve rapor bulma</div>
                  </div>
                </div>
                <div class="chat-toolbar-actions">
                  <select id="chatAssistantMode" aria-label="Asistan modu">
                    <option value="auto">otomatik</option>
                    <option value="report">rapor</option>
                    <option value="general">genel</option>
                  </select>
                  <select id="chatRetrievalVersion" aria-label="RAG surumu">
                    <option value="v2">RAG v2 (Beta)</option>
                    <option value="v3">RAG v3 (Haystack)</option>
                    <option value="v1">RAG v1 (Klasik)</option>
                  </select>
                  <select id="chatMode" aria-label="Chat arama modu">
                    <option value="hybrid">hybrid</option>
                    <option value="semantic">semantic</option>
                    <option value="keyword">keyword</option>
                  </select>
                  <button class="button secondary" id="chatClearButton" type="button" data-raporhub-hide>Yeni Sohbet</button>
                </div>
              </div>
              <div id="chatMessages" class="chat-messages">
                <div class="chat-message assistant">Merhaba. Icerideki raporlar uzerinden soru sorabilirsin.</div>
              </div>
              <div class="chat-prompts-shell">
                <div class="chat-prompts">
                  <div class="chat-prompt-help">
                    <button
                      class="chat-prompt chat-prompt-feature"
                      type="button"
                      data-chat-prompt="RAPOR-KODU raporundaki tablo ve sekil numaralandirmasi dogru mu yapilmis?"
                      data-chat-select="RAPOR-KODU"
                      data-chat-assistant-mode="report"
                      aria-describedby="qualityPromptTooltip"
                    >Tablo / Sekil Kontrolu</button>
                  </div>
                  <button class="chat-prompt" type="button" data-chat-prompt="__BRAND_NAME__ ne yapar?" data-chat-assistant-mode="auto">__BRAND_NAME__ ne yapar?</button>
                  <button class="chat-prompt" type="button" data-chat-prompt="Bu uygulama ne yapar?" data-chat-assistant-mode="auto">Uygulama nedir?</button>
                  <button class="chat-prompt" type="button" data-chat-prompt="Kendinden bahset" data-chat-assistant-mode="auto">Kendinden bahset</button>
                  <button class="chat-prompt" type="button" data-chat-prompt="BIG-E konfor raporunda hangi parkurlar var?" data-chat-assistant-mode="report">BIG-E konfor parkurlari</button>
                  <button class="chat-prompt" type="button" data-chat-prompt="Alternator braket raporunda dogal frekans kac Hz?" data-chat-assistant-mode="report">Alternator braket</button>
                  <button class="chat-prompt" type="button" data-chat-prompt="TASE sicaklik testinde kac sensor kullanildi?" data-chat-assistant-mode="report">TASE sensor</button>
                </div>
                <div class="chat-prompt-tooltip" id="qualityPromptTooltip" role="tooltip">
                  Rapordaki tablo, sekil ve resim numaralarinda eksik, tekrar veya sira bozuklugunu kontrol eder.
                  Tiklayip secili RAPOR-KODU alanini degistirmen yeterli.
                </div>
              </div>
              <div class="chat-input-row">
                <textarea id="chatInput" rows="2" placeholder="Rapor, test veya analiz hakkinda soru sor..."></textarea>
                <div class="chat-composer-footer" id="raporhubChatComposerFooter" data-raporhub-only hidden>
                  <div class="chat-composer-options" id="raporhubChatComposerOptions"></div>
                </div>
                <button class="button primary" id="chatSendButton" type="button" aria-label="Mesaj gonder" title="Mesaj gonder">Gonder</button>
              </div>
              <div class="note" id="chatStatus">Chatbot hazir.</div>
            </div>
            <div class="panel chat-side">
              <div class="chat-source-head">
                <div>
                  <div class="panel-title">Son Kaynaklar</div>
                  <div class="chat-source-meta" id="chatSourceMeta">Cevap geldikce ilgili rapor pasajlari burada gorunur.</div>
                </div>
              </div>
              <div id="chatSources" class="cards">
                <div class="empty">Kaynaklar cevap geldikce burada listelenecek.</div>
              </div>
            </div>
          </div>
        </div>
        <div class="section" data-module-title="Mukerrer" data-module-key="duplicates">
          <div class="section-head">
            <div>
              <h2>Mukerrer</h2>
              <p>Mukerrer adaylarini tara veya iki teknik raporu kaynaklariyla karsilastir.</p>
            </div>
            <button class="expand-button" type="button" data-expand-module>Buyut</button>
          </div>
          <div class="duplicate-workspace-tabs" role="tablist" aria-label="Mukerrer calisma alani">
            <button class="duplicate-workspace-tab active" id="duplicateCandidatesTab" type="button" role="tab" aria-selected="true" aria-controls="duplicateCandidatesPane">Mukerrer Adaylari</button>
            <button class="duplicate-workspace-tab" id="reportComparisonTab" type="button" role="tab" aria-selected="false" aria-controls="reportComparisonPane">Rapor Karsilastirma</button>
          </div>
          <div class="duplicate-workspace-pane" id="duplicateCandidatesPane" role="tabpanel" aria-labelledby="duplicateCandidatesTab">
            <div class="actions">
              <button class="button primary" id="duplicateScanButton" type="button">Taramayi Baslat</button>
              <button class="button secondary" id="duplicateRefreshButton" type="button">Kayitli Sonuclari Yenile</button>
            </div>
            <div class="note" id="duplicateStatus">Mukerrer adaylari henuz yuklenmedi.</div>
            <div id="duplicateList" class="cards" style="margin-top:16px;">
              <div class="empty">Kayitli mukerrer adaylari burada listelenecek.</div>
            </div>
          </div>
          <div class="duplicate-workspace-pane" id="reportComparisonPane" role="tabpanel" aria-labelledby="reportComparisonTab" hidden>
            <div class="comparison-source-grid">
              <div class="comparison-source">
                <div class="comparison-source-label">Rapor A</div>
                <select id="comparisonLeftSelect" aria-label="Rapor A secimi">
                  <option value="">Rapor sec...</option>
                </select>
                <div class="comparison-source-actions">
                  <label class="button secondary" for="comparisonLeftUpload">Dosya Yukle</label>
                  <input id="comparisonLeftUpload" type="file" accept=".pdf,.docx,.pptx" />
                  <span class="small" id="comparisonLeftMeta">Kaynak secilmedi.</span>
                </div>
              </div>
              <button class="comparison-swap" id="comparisonSwapButton" type="button" title="Raporlari degistir" aria-label="Raporlari degistir">&#8646;</button>
              <div class="comparison-source">
                <div class="comparison-source-label">Rapor B</div>
                <select id="comparisonRightSelect" aria-label="Rapor B secimi">
                  <option value="">Rapor sec...</option>
                </select>
                <div class="comparison-source-actions">
                  <label class="button secondary" for="comparisonRightUpload">Dosya Yukle</label>
                  <input id="comparisonRightUpload" type="file" accept=".pdf,.docx,.pptx" />
                  <span class="small" id="comparisonRightMeta">Kaynak secilmedi.</span>
                </div>
              </div>
            </div>
            <div class="comparison-controls">
              <label class="comparison-persist">
                <input id="comparisonPersistUploads" type="checkbox" />
                Yuklenen raporlari rapor havuzuna da ekle
              </label>
              <div class="comparison-run-actions">
                <div class="comparison-method-help">
                  <button class="comparison-info-button" type="button" aria-label="Eslesme yontemini goster" aria-describedby="comparisonMethodTooltip">i</button>
                  <div class="comparison-method-tooltip" id="comparisonMethodTooltip" role="tooltip">
                    <div class="comparison-method-title">Eslesme puani nasil hesaplanir?</div>
                    <div class="comparison-method-row"><strong>%62</strong><span>Anlamsal benzerlik - Qwen embedding</span></div>
                    <div class="comparison-method-row"><strong>%23</strong><span>Kelime ve teknik terim benzerligi</span></div>
                    <div class="comparison-method-row"><strong>%10</strong><span>Bolum ve baslik benzerligi</span></div>
                    <div class="comparison-method-row"><strong>%5</strong><span>Sayi, birim ve OK/NOK sinyalleri</span></div>
                    <div class="comparison-method-note">Toplam puani 0.42'nin altinda kalan pasaj ciftleri elenir.</div>
                  </div>
                </div>
                <button class="button primary" id="comparisonRunButton" type="button">Karsilastir</button>
              </div>
            </div>
            <div class="note" id="comparisonStatus">Iki farkli rapor sec veya yukle.</div>
            <div id="comparisonOutput" hidden>
              <div class="comparison-summary" id="comparisonSummary"></div>
              <div class="comparison-result-tabs" role="tablist" aria-label="Karsilastirma sonuclari">
                <button class="comparison-result-tab active" id="comparisonSimilaritiesTab" type="button" role="tab" aria-selected="true">Benzerlikler</button>
                <button class="comparison-result-tab" id="comparisonDifferencesTab" type="button" role="tab" aria-selected="false">Farkliliklar</button>
              </div>
              <div class="comparison-result-pane" id="comparisonSimilaritiesPane" role="tabpanel">
                <div class="comparison-results" id="comparisonSimilarities"></div>
              </div>
              <div class="comparison-result-pane" id="comparisonDifferencesPane" role="tabpanel" hidden>
                <div class="comparison-results" id="comparisonDifferences"></div>
              </div>
              <div class="comparison-pdf-workspace" id="comparisonPdfWorkspace" hidden>
                <div class="comparison-pdf-head">
                  <div>
                    <div class="panel-title">PDF Eslesme Gorunumu</div>
                    <div class="small" id="comparisonPdfStatus">Eslesen pasajlar iki PDF'de ayni renklerle isaretlenir.</div>
                  </div>
                  <div class="comparison-pdf-head-actions">
                    <button class="button secondary comparison-pair-fullscreen" id="comparisonPairFullscreenOpen" type="button" disabled>Iki PDF'yi Tam Ekranda Ac</button>
                    <div class="comparison-highlight-legend" id="comparisonHighlightLegend"></div>
                  </div>
                </div>
                <div class="comparison-pdf-grid">
                  <div class="comparison-pdf-panel">
                    <div class="comparison-pdf-toolbar">
                      <span id="comparisonLeftPdfTitle">Rapor A</span>
                      <button class="comparison-open" id="comparisonLeftPdfOpen" type="button">Tum PDF'yi Ac</button>
                    </div>
                    <iframe class="comparison-pdf-frame" id="comparisonLeftPdfFrame" title="Rapor A renkli PDF onizlemesi" loading="lazy"></iframe>
                    <div class="comparison-pdf-placeholder" id="comparisonLeftPdfPlaceholder" hidden></div>
                  </div>
                  <div class="comparison-pdf-panel">
                    <div class="comparison-pdf-toolbar">
                      <span id="comparisonRightPdfTitle">Rapor B</span>
                      <button class="comparison-open" id="comparisonRightPdfOpen" type="button">Tum PDF'yi Ac</button>
                    </div>
                    <iframe class="comparison-pdf-frame" id="comparisonRightPdfFrame" title="Rapor B renkli PDF onizlemesi" loading="lazy"></iframe>
                    <div class="comparison-pdf-placeholder" id="comparisonRightPdfPlaceholder" hidden></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="section" data-module-title="Katalog" data-modal-layout="catalog-stack" data-module-key="catalog" data-repocto-hide>
          <div class="section-head">
            <div>
              <h2>Katalog</h2>
              <p>Excel/CSV katalogunu yukle, katalog kayitlarini icerdeki raporlarla eslestir ve rapor dosyalarini ac.</p>
            </div>
            <button class="expand-button" type="button" data-expand-module>Buyut</button>
          </div>
          <div class="upload-grid">
            <div class="upload-card">
              <h2>Katalog Yukleme</h2>
              <p>Excel (.xlsx), CSV, TSV veya TXT formatinda rapor listesini ekle.</p>
              <div class="actions">
                <label class="button secondary" for="catalogPicker">Katalog Sec</label>
                <button class="button primary" id="catalogImportButton" type="button">Katalogu Yukle</button>
                <input id="catalogPicker" type="file" accept=".xlsx,.csv,.tsv,.txt" />
                <button class="button secondary" id="catalogTableRefreshButton" type="button">Katalog Tablosunu Yenile</button>
              </div>
              <div class="meta" id="catalogSummary">Henuz katalog dosyasi secilmedi.</div>
              <div class="status" id="catalogStatusBox"></div>
              <div class="catalog-board">
                <div class="catalog-pane ingested">
                  <div class="catalog-pane-head">
                    <span>Icerideki Raporlar</span>
                    <span class="catalog-count" id="catalogIngestedCount">0</span>
                  </div>
                  <div class="catalog-table-scroll">
                    <table class="catalog-table">
                      <thead>
                        <tr>
                          <th>Rapor</th>
                          <th>Arac</th>
                          <th>Tip</th>
                          <th>Durum</th>
                          <th>Link</th>
                        </tr>
                      </thead>
                      <tbody id="catalogIngestedTable">
                        <tr><td colspan="5" class="small">Katalog tablosu henuz yuklenmedi.</td></tr>
                      </tbody>
                    </table>
                  </div>
                  <div class="catalog-pane-actions">
                    <button class="button secondary" id="catalogEmbeddingRebuildButton" type="button">Embeddingleri Yenile</button>
                  </div>
                </div>
                <div class="catalog-pane pending">
                  <div class="catalog-pane-head">
                    <span>Iceri Alinacak Raporlar</span>
                    <span class="catalog-count" id="catalogPendingCount">0</span>
                  </div>
                  <div class="catalog-table-scroll">
                    <table class="catalog-table">
                      <thead>
                        <tr>
                          <th>Sec</th>
                          <th>Rapor</th>
                          <th>Arac</th>
                          <th>Tip</th>
                          <th>Link</th>
                          <th>Rapor</th>
                        </tr>
                      </thead>
                      <tbody id="catalogPendingTable">
                        <tr><td colspan="6" class="small">Katalog tablosu henuz yuklenmedi.</td></tr>
                      </tbody>
                    </table>
                  </div>
                  <div class="catalog-pane-actions">
                    <button class="button primary" id="catalogSelectedIngestButton" type="button">Secilenleri Ice Al</button>
                  </div>
                </div>
              </div>
              <details class="log-details">
                <summary id="catalogLogSummary">Teknik log</summary>
                <pre id="catalogResultBox">{}</pre>
              </details>
            </div>
            <div class="upload-card">
              <h2>Coklu Belge Calisma Alani</h2>
              <p>1. Katalogdan ilgili rapor grubunu bul. 2. Yalnizca bu grubun yuklenmis PDF/DOCX/PPTX icerigi uzerinden ikinci soruyu sor.</p>
              <div class="field">
                <label for="catalogQuestion">Katalog Sorusu</label>
                <input id="catalogQuestion" type="text" placeholder="Ornek: Novocitivolt araci ile kac tane NVH testi yapildi?" />
              </div>
              <div class="actions" style="margin-top:12px;">
                <button class="button primary" id="catalogAskButton" type="button">Katalogdan Sor</button>
              </div>
              <div class="note" id="catalogAskMeta">Katalog sorusu sorulmadi.</div>
              <div class="answer-box">
                <div id="catalogAnswer" class="answer-text">Katalog cevabi burada gorunecek.</div>
              </div>
              <div class="stats-grid">
                <div class="stat-card">
                  <div class="stat-label">Katalog Kaydi</div>
                  <div class="stat-value" id="catalogMatchCount">0</div>
                </div>
                <div class="stat-card">
                  <div class="stat-label">Yuklu Belge</div>
                  <div class="stat-value" id="catalogDocumentCount">0</div>
                </div>
                <div class="stat-card">
                  <div class="stat-label">Hazir Kapsam</div>
                  <div class="stat-value" id="catalogScopeReady">Hayir</div>
                </div>
              </div>
              <div class="field" style="margin-top:16px;">
                <label for="multiDocumentQuestion">Bu Raporlar Uzerinden Soru</label>
                <input id="multiDocumentQuestion" type="text" placeholder="Ornek: Bu raporlarda ortak test kosullari nelerdir?" />
              </div>
              <div class="search-grid" style="margin-top:12px; grid-template-columns:minmax(0,2fr) 210px 160px;">
                <div class="field">
                  <label for="multiDocumentMode">Mod</label>
                  <select id="multiDocumentMode">
                    <option value="hybrid">hybrid</option>
                    <option value="semantic">semantic</option>
                    <option value="keyword">keyword</option>
                  </select>
                </div>
                <div class="field">
                  <label for="multiDocumentLimit">Kaynak Limiti</label>
                  <select id="multiDocumentLimit">
                    <option value="4">4</option>
                    <option value="6" selected>6</option>
                    <option value="8">8</option>
                    <option value="10">10</option>
                  </select>
                </div>
                <div class="field">
                  <label>&nbsp;</label>
                  <button class="button primary" id="multiDocumentAskButton" type="button" style="width:100%;">Icerikten Sor</button>
                </div>
              </div>
              <div class="note" id="multiDocumentMeta">Ikinci asama soru sorulmadi.</div>
              <div class="catalog-workspace">
                <div class="panel">
                  <div class="panel-title">Icerik Cevabi</div>
                  <div class="answer-box">
                    <div id="multiDocumentAnswer" class="answer-text">Secilen rapor grubunun icerik cevabi burada gorunecek.</div>
                  </div>
                  <div class="panel-title" style="margin-top:16px;">Kullanilan Belgeler</div>
                  <div id="multiDocumentDocuments" class="cards">
                    <div class="empty">Yuklu ve eslesen belgeler burada listelenecek.</div>
                  </div>
                </div>
                <div class="panel">
                  <div class="panel-title">Belge Karsilastirma Tablosu</div>
                  <div class="table-box" id="multiDocumentComparison">
                    <table>
                      <thead>
                        <tr>
                          <th>Belge</th>
                          <th>Cevap</th>
                          <th>Guven</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td colspan="3" class="small">Karsilastirma sonuclari burada yer alacak.</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div class="panel-title" style="margin-top:16px;">Eslesen Katalog Kayitlari</div>
                  <div id="catalogMatches" class="cards">
                    <div class="empty">Eslesen katalog kayitlari burada listelenecek.</div>
                  </div>
                  <div class="panel-title" style="margin-top:16px;">Kaynak Pasajlar</div>
                  <div id="multiDocumentSources" class="cards">
                    <div class="empty">Kaynak pasajlar burada listelenecek.</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="section" data-module-title="Kategori Tarayici" data-repocto-title="Kütüphane" data-module-key="graph">
          <div class="repocto-library" data-repocto-only hidden>
            <div class="repocto-library-hero">
              <div>
                <div class="repocto-library-eyebrow">KURUMSAL HAFIZA</div>
                <h2>Kütüphane</h2>
                <p>Bir kök klasör seçin; RepOcto alt klasörlerdeki PDF, DOCX ve PPTX belgelerini okunabilir bir doküman ağacına dönüştürsün.</p>
              </div>
              <div class="repocto-library-path">
                <label for="libraryPathInput">Kök klasör</label>
                <div>
                  <input id="libraryPathInput" type="text" value="V:\\RAPORLAR" placeholder="Örnek: V:\\RAPORLAR" autocomplete="off" spellcheck="false" />
                  <button class="button primary" id="libraryScanButton" type="button">Kütüphaneyi Tara</button>
                </div>
              </div>
            </div>
            <div class="repocto-library-pipeline" aria-label="Kütüphane işleme adımları">
              <div><b>01</b><span><strong>Kök klasör</strong><small>Yolu güvenli biçimde doğrula</small></span></div>
              <div><b>02</b><span><strong>Alt klasörler</strong><small>Özyinelemeli olarak tara</small></span></div>
              <div><b>03</b><span><strong>Dokümanlar</strong><small>PDF · DOCX · PPTX</small></span></div>
              <div><b>04</b><span><strong>Belge ağacı</strong><small>Klasör yapısını görünür kıl</small></span></div>
            </div>
            <div class="repocto-library-status" id="libraryStatus" role="status" aria-live="polite">Taranacak kök klasör yolunu girin.</div>
            <div class="repocto-library-controls">
              <label for="librarySearchInput">Doküman ara</label>
              <input id="librarySearchInput" type="search" placeholder="Dosya veya klasör adı" autocomplete="off" />
              <label for="libraryTypeFilter">Dosya türü</label>
              <select id="libraryTypeFilter">
                <option value="all">Tümü</option>
                <option value="PDF">PDF</option>
                <option value="DOCX">DOCX</option>
                <option value="PPTX">PPTX</option>
              </select>
              <button class="button secondary" id="libraryClearButton" type="button">Temizle</button>
            </div>
            <div class="repocto-library-workspace">
              <aside class="repocto-library-tree-pane" aria-label="Doküman ağacı">
                <div class="repocto-library-pane-head"><strong>Doküman ağacı</strong><span id="libraryTreeSummary">Henüz taranmadı</span></div>
                <div class="repocto-library-tree" id="libraryTree">
                  <div class="repocto-library-empty">Klasör yolu tarandığında belge ağacı burada oluşacak.</div>
                </div>
              </aside>
              <section class="repocto-library-map-pane" aria-label="Klasör haritası">
                <div class="repocto-library-pane-head"><strong>Klasör haritası</strong><span>Kök → klasör → doküman</span></div>
                <div class="repocto-library-map" id="libraryMap">
                  <div class="repocto-library-empty">Kütüphane tarandığında klasör haritası burada oluşacak.</div>
                </div>
              </section>
              <section class="repocto-library-detail-pane" aria-label="Seçili doküman ayrıntıları">
                <div class="repocto-library-pane-head"><strong>Belge profili</strong><span>Salt okunur</span></div>
                <div class="repocto-library-detail" id="libraryDetail">
                  <div class="repocto-library-detail-empty">
                    <span>REP</span>
                    <strong>Bir doküman seçin</strong>
                    <p>Dosya türü, boyutu, güncellenme zamanı ve klasör yolu burada gösterilecek.</p>
                  </div>
                </div>
              </section>
            </div>
          </div>
          <div data-repocto-hide>
          <div class="section-head">
            <div>
              <h2>Kategori Tarayici</h2>
              <p>Katalog ve yuklu raporlari kategori agaci, belge tablosu ve yogunluk grafikleriyle incele.</p>
            </div>
            <button class="expand-button" type="button" data-expand-module>Buyut</button>
          </div>
          <div class="actions">
            <button class="button primary" id="graphRefreshButton" type="button">Veriyi Yenile</button>
          </div>
          <div class="note" id="graphStatus">Kategori verisi henuz yuklenmedi.</div>
          <div class="graph-dashboard" id="graphStats">
            <div class="stat-card"><div class="stat-label">Kategori</div><div class="stat-value">0</div></div>
            <div class="stat-card"><div class="stat-label">Belge</div><div class="stat-value">0</div></div>
            <div class="stat-card"><div class="stat-label">En Yogun</div><div class="stat-value">-</div></div>
          </div>
          <div class="graph-browser">
            <aside class="graph-sidebar">
              <div class="panel-title">Kategori Agaci</div>
              <div id="graphTree" class="category-tree">
                <div class="empty">Kategoriler burada listelenecek.</div>
              </div>
            </aside>
            <div class="graph-main">
              <div class="graph-controls">
                <div class="field">
                  <label for="graphSearchInput">Arama</label>
                  <input id="graphSearchInput" type="text" placeholder="Belge adi, etiket, durum veya yil ara" />
                </div>
                <div class="field">
                  <label for="graphCategoryFilter">Kategori</label>
                  <select id="graphCategoryFilter">
                    <option value="all">Tum kategoriler</option>
                  </select>
                </div>
              </div>
              <div class="panel-title">Kategori Yogunlugu</div>
              <div id="graphDensityChart" class="density-chart">
                <div class="empty">Yogunluk grafigi burada gorunecek.</div>
              </div>
              <div class="panel-title">Belgeler</div>
              <div class="document-table-wrap">
                <table class="document-table">
                  <thead>
                    <tr>
                      <th>Ad</th>
                      <th>Tur</th>
                      <th>Tarih</th>
                      <th>Etiket</th>
                      <th>Durum</th>
                    </tr>
                  </thead>
                  <tbody id="graphDocumentsTable">
                    <tr><td colspan="5" class="small">Belge listesi burada gorunecek.</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
          </div>
        </div>
        <div class="section" data-module-title="Soru-Cevap" data-module-key="qa">
          <div class="section-head">
            <div>
              <h2>Soru-Cevap</h2>
              <p>Rapora dogal dilde soru sor. Sistem ilgili chunk'lari bulup metne dayali kisa bir cevap dondursun.</p>
            </div>
            <button class="expand-button" type="button" data-expand-module>Buyut</button>
          </div>
          <div class="ask-grid">
            <div class="field">
              <label for="askQuestion">Soru</label>
              <input id="askQuestion" type="text" placeholder="Ornek: Bu raporda maksimum gerilme nedir?" />
            </div>
            <div class="field">
              <label for="askMode">Mod</label>
              <select id="askMode">
                <option value="hybrid">hybrid</option>
                <option value="semantic">semantic</option>
                <option value="keyword">keyword</option>
              </select>
            </div>
            <div class="field">
              <label for="askDocumentId">Belge ID</label>
              <input id="askDocumentId" type="number" min="1" placeholder="Opsiyonel" />
            </div>
            <div class="field">
              <label>&nbsp;</label>
              <button class="button primary" id="askButton" type="button" style="width:100%;">Sor</button>
            </div>
          </div>
          <div class="note" id="askMeta">Soru sorulmadi.</div>
          <div class="qa-layout">
            <div class="panel">
              <div class="panel-title">Cevap</div>
              <div class="answer-box">
                <div id="answerText" class="answer-text">Cevap burada gorunecek.</div>
              </div>
            </div>
            <div class="panel">
              <div class="panel-title">Kaynaklar</div>
              <div id="answerSources" class="cards">
                <div class="empty">Kullanilan kaynak pasajlar burada listelenecek.</div>
              </div>
            </div>
          </div>
        </div>
        <div class="section" data-module-title="Rapor Yazma Destegi" data-module-key="writing">
          <div class="section-head">
            <div>
              <h2>Rapor Yazma Destegi</h2>
              <p>Baslik, amac, anahtar kelimeler ve ham notlar ver. Sistem bunlari daha duzgun bir rapor taslagina cevirsin ve benzer raporlardan ornek pasajlar getirsin.</p>
            </div>
            <button class="expand-button" type="button" data-expand-module>Buyut</button>
          </div>
          <div class="draft-grid">
            <div class="panel">
              <div class="field">
                <label for="draftTitle">Rapor Basligi</label>
                <input id="draftTitle" type="text" placeholder="Ornek: BIG-E Yol Verisi Toplama Degerlendirme Raporu" />
              </div>
              <div class="search-grid">
                <div class="field">
                  <label for="draftType">Rapor Turu</label>
                  <input id="draftType" type="text" placeholder="Ornek: Test Degerlendirme Raporu" />
                </div>
                <div class="field">
                  <label for="draftMode">Mod</label>
                  <select id="draftMode">
                    <option value="keyword">keyword</option>
                    <option value="hybrid">hybrid</option>
                    <option value="semantic">semantic</option>
                  </select>
                </div>
              </div>
              <div class="search-grid">
                <div class="field">
                  <label for="draftReportNo">Rapor No</label>
                  <input id="draftReportNo" type="text" placeholder="Ornek: 2025-BIG-e-NVH-01" />
                </div>
                <div class="field">
                  <label for="draftReportDate">Tarih</label>
                  <input id="draftReportDate" type="text" placeholder="Ornek: 13.01.2025" />
                </div>
              </div>
              <div class="search-grid">
                <div class="field">
                  <label for="draftPreparedBy">Hazirlayan</label>
                  <input id="draftPreparedBy" type="text" placeholder="Ornek: KEMAL DEMIR" />
                </div>
                <div class="field">
                  <label for="draftRequestedBy">Talep Eden</label>
                  <input id="draftRequestedBy" type="text" placeholder="Ornek: ERKAN KUTLU" />
                </div>
              </div>
              <div class="field">
                <label for="draftCheckedBy">Kontrol</label>
                <input id="draftCheckedBy" type="text" placeholder="Ornek: EROL CIFCI, A.SALIH YILMAZ" />
              </div>
              <div class="actions" style="margin-top:12px;">
                <button class="button primary" id="draftQuickButton" type="button" style="flex:1;">Hizli Rapor Olustur</button>
                <button class="button primary" id="draftDetailedButton" type="button" style="flex:1;">Detayli Rapor Olustur</button>
              </div>
              <div class="draft-toolbar">
                <button class="button secondary" id="draftSampleButton" type="button">Ornek Doldur</button>
                <button class="button secondary" id="draftClearButton" type="button">Temizle</button>
              </div>
              <div class="field" style="margin-top:16px;">
                <label for="draftObjective">Amac</label>
                <textarea id="draftObjective" placeholder="Bu raporun neyi anlatmasini istedigini yaz."></textarea>
              </div>
              <div class="field" style="margin-top:16px;">
                <label for="draftKeywords">Anahtar Kelimeler</label>
                <input id="draftKeywords" type="text" placeholder="Ornek: yol verisi, parkur, titreşim, test senaryosu" />
              </div>
              <div class="field" style="margin-top:16px;">
                <label for="draftNotes">Ham Notlar / Veriler</label>
                <textarea id="draftNotes" placeholder="Madde madde notlarini, sayisal degerleri veya duzeltmek istedigin cumleleri buraya yaz."></textarea>
              </div>
              <div class="note" id="draftMeta">Taslak uretilmedi.</div>
              <div class="draft-hint">Once baslik ve notlari gir, taslagi uret, sonra metni kontrol edip kopyala veya PDF olarak indir.</div>
            </div>
            <div class="panel">
              <div class="panel-title">Taslak Metin</div>
              <div class="draft-toolbar">
                <button class="button secondary" id="draftCopyButton" type="button" disabled>Kopyala</button>
                <button class="button secondary" id="draftPdfButton" type="button" disabled>PDF Indir</button>
              </div>
              <div class="draft-box">
                <pre id="draftOutput" class="draft-text">Taslak burada gorunecek.</pre>
              </div>
              <div class="panel-title" style="margin-top:16px;">Referans Kaynaklar</div>
              <div id="draftSources" class="cards">
                <div class="empty">Taslak icin kullanilan referans pasajlar burada listelenecek.</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div class="module-modal" id="moduleModal" aria-hidden="true">
    <div class="module-modal-shell">
      <div class="module-modal-bar">
        <div class="module-modal-title" id="moduleModalTitle">Modul</div>
        <button class="module-modal-close" id="moduleModalClose" type="button">Kapat</button>
      </div>
      <div class="module-modal-body" id="moduleModalBody"></div>
    </div>
  </div>

  <script>
    const appVariant = document.body.dataset.appVariant;
    const isLegacyRaporHub = appVariant === "raporhub";
    const isRepOcto = appVariant === "repocto";
    const isRaporHub = isLegacyRaporHub || isRepOcto;
    const raporhubSidebarPreferenceKey = isRepOcto ? "repoctoSidebarCollapsed" : "raporhubSidebarCollapsed";
    const raporhubThemePreferenceKey = isRepOcto ? "repoctoColorMode" : "raporhubColorMode";
    let raporhubSidebarCollapsedPreference = false;
    let raporhubThemePreference = "light";
    if (isRaporHub) {
      document.querySelectorAll("[data-raporhub-only]").forEach(element => {
        element.hidden = false;
      });
      document.querySelectorAll("[data-raporhub-hide]").forEach(element => {
        element.hidden = true;
      });
      if (isRepOcto) {
        document.querySelectorAll("[data-repocto-only]").forEach(element => {
          element.hidden = false;
        });
        document.querySelectorAll("[data-repocto-hide]").forEach(element => {
          element.hidden = true;
        });
        document.querySelectorAll("[data-repocto-label]").forEach(element => {
          const label = element.dataset.repoctoLabel || "";
          if (!label) return;
          element.textContent = label;
          element.dataset.navLabel = label;
          element.title = label;
          if (element.dataset.repoctoShort) {
            element.dataset.navShort = element.dataset.repoctoShort;
          }
        });
        document.querySelectorAll("[data-repocto-title]").forEach(element => {
          element.dataset.moduleTitle = element.dataset.repoctoTitle;
        });
      }
      const raporhubModuleSwitcher = document.querySelector(".module-switcher");
      const raporhubChatButton = document.querySelector('[data-module-filter="chat"]');
      if (isRaporHub && raporhubModuleSwitcher && raporhubChatButton) {
        raporhubModuleSwitcher.prepend(raporhubChatButton);
      }
      const raporhubComposerFooter = document.getElementById("raporhubChatComposerFooter");
      const raporhubComposerOptions = document.getElementById("raporhubChatComposerOptions");
      const raporhubSendButton = document.getElementById("chatSendButton");
      const raporhubChatInput = document.getElementById("chatInput");
      ["chatAssistantMode", "chatRetrievalVersion", "chatMode"].forEach(id => {
        const control = document.getElementById(id);
        if (raporhubComposerOptions && control) {
          raporhubComposerOptions.append(control);
        }
      });
      if (raporhubComposerFooter && raporhubSendButton) {
        raporhubComposerFooter.append(raporhubSendButton);
      }
      if (raporhubChatInput) {
        raporhubChatInput.rows = 1;
      }
      try {
        raporhubSidebarCollapsedPreference = localStorage.getItem(raporhubSidebarPreferenceKey) === "true";
        raporhubThemePreference = localStorage.getItem(raporhubThemePreferenceKey) === "dark" ? "dark" : "light";
      } catch (error) {
        raporhubSidebarCollapsedPreference = false;
        raporhubThemePreference = "light";
      }
      document.body.classList.toggle(
        "raporhub-sidebar-collapsed",
        raporhubSidebarCollapsedPreference && window.innerWidth > 980
      );
      document.body.classList.toggle("raporhub-dark", raporhubThemePreference === "dark");
    }

    const picker = document.getElementById("reportPicker");
    const uploadButton = document.getElementById("uploadButton");
    const summary = document.getElementById("summary");
    const filesList = document.getElementById("filesList");
    const statusBox = document.getElementById("statusBox");
    const uploadResults = document.getElementById("uploadResults");
    const uploadResultList = document.getElementById("uploadResultList");
    const uploadedDocumentsRefreshButton = document.getElementById("uploadedDocumentsRefreshButton");
    const uploadedDocumentsStatus = document.getElementById("uploadedDocumentsStatus");
    const uploadedDocumentsTable = document.getElementById("uploadedDocumentsTable");
    const raporhubSidebarToggle = document.getElementById("raporhubSidebarToggle");
    const raporhubThemeToggle = document.getElementById("raporhubThemeToggle");
    const repoctoPageTitle = document.getElementById("repoctoPageTitle");
    const raporhubHomeQuestion = document.getElementById("raporhubHomeQuestion");
    const raporhubHomeAskButton = document.getElementById("raporhubHomeAskButton");
    const raporhubUploadShortcut = document.getElementById("raporhubUploadShortcut");
    const raporhubDocumentCount = document.getElementById("raporhubDocumentCount");
    const raporhubChunkCount = document.getElementById("raporhubChunkCount");
    const raporhubEmbeddingCoverage = document.getElementById("raporhubEmbeddingCoverage");
    const raporhubLastUpload = document.getElementById("raporhubLastUpload");
    const raporhubRecentDocuments = document.getElementById("raporhubRecentDocuments");
    const raporhubReadinessLabel = document.getElementById("raporhubReadinessLabel");
    const raporhubCoverageBar = document.getElementById("raporhubCoverageBar");
    const raporhubReadinessCopy = document.getElementById("raporhubReadinessCopy");
    const raporhubFileTypes = document.getElementById("raporhubFileTypes");
    const raporhubOverviewStatus = document.getElementById("raporhubOverviewStatus");
    const catalogPicker = document.getElementById("catalogPicker");
    const catalogImportButton = document.getElementById("catalogImportButton");
    const catalogSummary = document.getElementById("catalogSummary");
    const catalogStatusBox = document.getElementById("catalogStatusBox");
    const catalogResultBox = document.getElementById("catalogResultBox");
    const catalogLogSummary = document.getElementById("catalogLogSummary");
    const catalogTableRefreshButton = document.getElementById("catalogTableRefreshButton");
    const catalogSelectedIngestButton = document.getElementById("catalogSelectedIngestButton");
    const catalogEmbeddingRebuildButton = document.getElementById("catalogEmbeddingRebuildButton");
    const catalogIngestedCount = document.getElementById("catalogIngestedCount");
    const catalogPendingCount = document.getElementById("catalogPendingCount");
    const catalogIngestedTable = document.getElementById("catalogIngestedTable");
    const catalogPendingTable = document.getElementById("catalogPendingTable");
    const catalogQuestion = document.getElementById("catalogQuestion");
    const catalogAskButton = document.getElementById("catalogAskButton");
    const catalogAskMeta = document.getElementById("catalogAskMeta");
    const catalogAnswer = document.getElementById("catalogAnswer");
    const catalogMatches = document.getElementById("catalogMatches");
    const catalogMatchCount = document.getElementById("catalogMatchCount");
    const catalogDocumentCount = document.getElementById("catalogDocumentCount");
    const catalogScopeReady = document.getElementById("catalogScopeReady");
    const multiDocumentQuestion = document.getElementById("multiDocumentQuestion");
    const multiDocumentMode = document.getElementById("multiDocumentMode");
    const multiDocumentLimit = document.getElementById("multiDocumentLimit");
    const multiDocumentAskButton = document.getElementById("multiDocumentAskButton");
    const multiDocumentMeta = document.getElementById("multiDocumentMeta");
    const multiDocumentAnswer = document.getElementById("multiDocumentAnswer");
    const multiDocumentDocuments = document.getElementById("multiDocumentDocuments");
    const multiDocumentComparison = document.getElementById("multiDocumentComparison");
    const multiDocumentSources = document.getElementById("multiDocumentSources");
    const graphRefreshButton = document.getElementById("graphRefreshButton");
    const graphStatus = document.getElementById("graphStatus");
    const graphStats = document.getElementById("graphStats");
    const graphTree = document.getElementById("graphTree");
    const graphSearchInput = document.getElementById("graphSearchInput");
    const graphCategoryFilter = document.getElementById("graphCategoryFilter");
    const graphDensityChart = document.getElementById("graphDensityChart");
    const graphDocumentsTable = document.getElementById("graphDocumentsTable");
    const libraryPathInput = document.getElementById("libraryPathInput");
    const libraryScanButton = document.getElementById("libraryScanButton");
    const libraryStatus = document.getElementById("libraryStatus");
    const libraryTree = document.getElementById("libraryTree");
    const libraryTreeSummary = document.getElementById("libraryTreeSummary");
    const librarySearchInput = document.getElementById("librarySearchInput");
    const libraryTypeFilter = document.getElementById("libraryTypeFilter");
    const libraryClearButton = document.getElementById("libraryClearButton");
    const libraryMap = document.getElementById("libraryMap");
    const libraryDetail = document.getElementById("libraryDetail");
    const searchQuery = document.getElementById("searchQuery");
    const searchMode = document.getElementById("searchMode");
    const searchButton = document.getElementById("searchButton");
    const searchMeta = document.getElementById("searchMeta");
    const searchResultsLayout = document.getElementById("searchResultsLayout");
    const resultsList = document.getElementById("resultsList");
    const similarList = document.getElementById("similarList");
    const duplicateScanButton = document.getElementById("duplicateScanButton");
    const duplicateRefreshButton = document.getElementById("duplicateRefreshButton");
    const duplicateStatus = document.getElementById("duplicateStatus");
    const duplicateList = document.getElementById("duplicateList");
    const duplicateCandidatesTab = document.getElementById("duplicateCandidatesTab");
    const reportComparisonTab = document.getElementById("reportComparisonTab");
    const duplicateCandidatesPane = document.getElementById("duplicateCandidatesPane");
    const reportComparisonPane = document.getElementById("reportComparisonPane");
    const comparisonLeftSelect = document.getElementById("comparisonLeftSelect");
    const comparisonRightSelect = document.getElementById("comparisonRightSelect");
    const comparisonLeftUpload = document.getElementById("comparisonLeftUpload");
    const comparisonRightUpload = document.getElementById("comparisonRightUpload");
    const comparisonLeftMeta = document.getElementById("comparisonLeftMeta");
    const comparisonRightMeta = document.getElementById("comparisonRightMeta");
    const comparisonPersistUploads = document.getElementById("comparisonPersistUploads");
    const comparisonSwapButton = document.getElementById("comparisonSwapButton");
    const comparisonRunButton = document.getElementById("comparisonRunButton");
    const comparisonStatus = document.getElementById("comparisonStatus");
    const comparisonOutput = document.getElementById("comparisonOutput");
    const comparisonSummary = document.getElementById("comparisonSummary");
    const comparisonSimilaritiesTab = document.getElementById("comparisonSimilaritiesTab");
    const comparisonDifferencesTab = document.getElementById("comparisonDifferencesTab");
    const comparisonSimilaritiesPane = document.getElementById("comparisonSimilaritiesPane");
    const comparisonDifferencesPane = document.getElementById("comparisonDifferencesPane");
    const comparisonSimilarities = document.getElementById("comparisonSimilarities");
    const comparisonDifferences = document.getElementById("comparisonDifferences");
    const comparisonPdfWorkspace = document.getElementById("comparisonPdfWorkspace");
    const comparisonPdfStatus = document.getElementById("comparisonPdfStatus");
    const comparisonHighlightLegend = document.getElementById("comparisonHighlightLegend");
    const comparisonPairFullscreenOpen = document.getElementById("comparisonPairFullscreenOpen");
    const comparisonLeftPdfTitle = document.getElementById("comparisonLeftPdfTitle");
    const comparisonRightPdfTitle = document.getElementById("comparisonRightPdfTitle");
    const comparisonLeftPdfOpen = document.getElementById("comparisonLeftPdfOpen");
    const comparisonRightPdfOpen = document.getElementById("comparisonRightPdfOpen");
    const comparisonLeftPdfFrame = document.getElementById("comparisonLeftPdfFrame");
    const comparisonRightPdfFrame = document.getElementById("comparisonRightPdfFrame");
    const comparisonLeftPdfPlaceholder = document.getElementById("comparisonLeftPdfPlaceholder");
    const comparisonRightPdfPlaceholder = document.getElementById("comparisonRightPdfPlaceholder");
    const chatMessages = document.getElementById("chatMessages");
    const chatInput = document.getElementById("chatInput");
    const chatAssistantMode = document.getElementById("chatAssistantMode");
    const chatRetrievalVersion = document.getElementById("chatRetrievalVersion");
    const chatMode = document.getElementById("chatMode");
    const chatSendButton = document.getElementById("chatSendButton");
    const chatClearButton = document.getElementById("chatClearButton");
    const chatStatus = document.getElementById("chatStatus");
    const chatSources = document.getElementById("chatSources");
    const chatSourceMeta = document.getElementById("chatSourceMeta");
    const chatPromptButtons = Array.from(document.querySelectorAll("[data-chat-prompt]"));
    const askQuestion = document.getElementById("askQuestion");
    const askMode = document.getElementById("askMode");
    const askDocumentId = document.getElementById("askDocumentId");
    const askButton = document.getElementById("askButton");
    const askMeta = document.getElementById("askMeta");
    const answerText = document.getElementById("answerText");
    const answerSources = document.getElementById("answerSources");
    const draftTitle = document.getElementById("draftTitle");
    const draftType = document.getElementById("draftType");
    const draftMode = document.getElementById("draftMode");
    const draftReportNo = document.getElementById("draftReportNo");
    const draftReportDate = document.getElementById("draftReportDate");
    const draftPreparedBy = document.getElementById("draftPreparedBy");
    const draftRequestedBy = document.getElementById("draftRequestedBy");
    const draftCheckedBy = document.getElementById("draftCheckedBy");
    const draftObjective = document.getElementById("draftObjective");
    const draftKeywords = document.getElementById("draftKeywords");
    const draftNotes = document.getElementById("draftNotes");
    const draftQuickButton = document.getElementById("draftQuickButton");
    const draftDetailedButton = document.getElementById("draftDetailedButton");
    const draftSampleButton = document.getElementById("draftSampleButton");
    const draftClearButton = document.getElementById("draftClearButton");
    const draftCopyButton = document.getElementById("draftCopyButton");
    const draftPdfButton = document.getElementById("draftPdfButton");
    const draftMeta = document.getElementById("draftMeta");
    const draftOutput = document.getElementById("draftOutput");
    const draftSources = document.getElementById("draftSources");
    const moduleModal = document.getElementById("moduleModal");
    const moduleModalTitle = document.getElementById("moduleModalTitle");
    const moduleModalBody = document.getElementById("moduleModalBody");
    const moduleModalClose = document.getElementById("moduleModalClose");
    const moduleFilterButtons = Array.from(document.querySelectorAll("[data-module-filter]"));
    const moduleSections = Array.from(document.querySelectorAll(".section[data-module-key]"));

    let selectedFiles = [];
    let selectedCatalogFile = null;
    let lastCatalogQuestion = "";
    let lastCatalogMatches = [];
    let chatHistory = [];
    let chatContextDocumentIds = [];
    let lastDraftPayload = null;
    let lastDraftData = null;
    let lastAutoReportNo = "";
    let selectedDraftDocumentIds = [];
    let graphState = { categories: [], documents: [], selectedCategoryId: "all", search: "" };
    let activeTimerId = null;
    let activeModule = null;
    let selectedModuleFilter = isRaporHub ? "chat" : "upload";
    let duplicateWorkspaceView = "candidates";
    let comparisonDocumentsLoaded = false;
    let latestComparisonData = null;

    function syncRaporHubSidebar() {
      if (!isRaporHub) return;
      const isCollapsed = raporhubSidebarCollapsedPreference && window.innerWidth > 980;
      document.body.classList.toggle("raporhub-sidebar-collapsed", isCollapsed);
      raporhubSidebarToggle.setAttribute("aria-expanded", String(!isCollapsed));
      raporhubSidebarToggle.setAttribute("aria-label", isCollapsed ? "Sol menuyu genislet" : "Sol menuyu daralt");
      raporhubSidebarToggle.title = isCollapsed ? "Sol menuyu genislet" : "Sol menuyu daralt";
    }

    function toggleRaporHubSidebar() {
      raporhubSidebarCollapsedPreference = !raporhubSidebarCollapsedPreference;
      try {
        localStorage.setItem(raporhubSidebarPreferenceKey, String(raporhubSidebarCollapsedPreference));
      } catch (error) {
        // The sidebar still works when browser storage is unavailable.
      }
      syncRaporHubSidebar();
    }

    function syncRaporHubTheme() {
      if (!isRaporHub) return;
      const isDark = raporhubThemePreference === "dark";
      document.body.classList.toggle("raporhub-dark", isDark);
      raporhubThemeToggle.setAttribute("aria-pressed", String(isDark));
      raporhubThemeToggle.setAttribute("aria-label", isDark ? "Aydinlik moda gec" : "Karanlik moda gec");
      raporhubThemeToggle.title = isDark ? "Aydinlik moda gec" : "Karanlik moda gec";
    }

    function toggleRaporHubTheme() {
      raporhubThemePreference = raporhubThemePreference === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(raporhubThemePreferenceKey, raporhubThemePreference);
      } catch (error) {
        // The theme still works when browser storage is unavailable.
      }
      syncRaporHubTheme();
    }

    function applyModuleFilter(filterKey) {
      selectedModuleFilter = filterKey || (isRaporHub ? "chat" : "upload");
      if (activeModule) {
        closeModule();
      }

      moduleFilterButtons.forEach(button => {
        button.classList.toggle("active", button.dataset.moduleFilter === selectedModuleFilter);
      });
      if (repoctoPageTitle) {
        const activeButton = moduleFilterButtons.find(button => button.dataset.moduleFilter === selectedModuleFilter);
        repoctoPageTitle.textContent = activeButton?.dataset.navLabel || "Calisma Alani";
      }
      document.body.classList.toggle("chat-focus", selectedModuleFilter === "chat");

      moduleSections.forEach(section => {
        const keys = String(section.dataset.moduleKey || "").split(/\\s+/);
        const shouldShow = selectedModuleFilter === "all" || keys.includes(selectedModuleFilter);
        section.classList.toggle("module-hidden", !shouldShow);
      });

      if (selectedModuleFilter === "graph") {
        if (isRepOcto) {
          focusRepOctoLibrary();
        } else {
          refreshGraph();
        }
      }
      if (selectedModuleFilter === "home" && isRaporHub) {
        refreshRaporHubOverview();
      }
      if (selectedModuleFilter === "upload" && isRaporHub) {
        refreshUploadedDocuments();
      }
      if (selectedModuleFilter === "duplicates") {
        if (duplicateWorkspaceView === "comparison") {
          refreshComparisonDocuments();
        } else {
          refreshDuplicates();
        }
      }
    }

    function formatElapsed(milliseconds) {
      const seconds = milliseconds / 1000;
      return seconds < 10 ? `${seconds.toFixed(2)} sn` : `${seconds.toFixed(1)} sn`;
    }

    function startTimer(setMessage, baseMessage) {
      const startedAt = performance.now();
      if (activeTimerId) {
        clearInterval(activeTimerId);
      }
      const update = () => {
        setMessage(`${baseMessage} | Sure: ${formatElapsed(performance.now() - startedAt)}`);
      };
      update();
      activeTimerId = setInterval(update, 200);
      return startedAt;
    }

    function stopTimer(startedAt, setMessage, finalMessage) {
      if (activeTimerId) {
        clearInterval(activeTimerId);
        activeTimerId = null;
      }
      setMessage(`${finalMessage} | Sure: ${formatElapsed(performance.now() - startedAt)}`);
    }

    function formatTodayForDraft() {
      const today = new Date();
      const day = String(today.getDate()).padStart(2, "0");
      const month = String(today.getMonth() + 1).padStart(2, "0");
      return `${day}.${month}.${today.getFullYear()}`;
    }

    function guessDraftReportNo(title) {
      const match = String(title || "").match(/\\b20\\d{2}[-_][0-9A-Za-z.]+(?:[-_][0-9A-Za-z.]+){1,}\\b/);
      return match ? match[0] : "TASLAK";
    }

    function updateDraftReportNoAuto(force = false) {
      const current = draftReportNo.value.trim();
      const guessed = guessDraftReportNo(draftTitle.value);
      if (force || !current || current === "TASLAK" || current === lastAutoReportNo) {
        draftReportNo.value = guessed;
        lastAutoReportNo = guessed;
      }
    }

    function ensureDraftDefaults() {
      if (!draftReportDate.value.trim()) {
        draftReportDate.value = formatTodayForDraft();
      }
      updateDraftReportNoAuto(false);
    }

    function openModule(section) {
      closeModule();
      activeModule = section;
      section.classList.add("module-expanded");
      const expandButton = section.querySelector("[data-expand-module]");
      if (expandButton) {
        expandButton.textContent = "Kucult";
      }
      document.body.classList.add("modal-open");
      if (section.dataset.moduleKey === "upload") {
        refreshUploadedDocuments();
      }
      if (section.dataset.moduleKey === "graph") {
        if (isRepOcto) {
          focusRepOctoLibrary();
        } else {
          refreshGraph();
        }
      }
      if (section.dataset.moduleKey === "duplicates") {
        if (duplicateWorkspaceView === "comparison") {
          refreshComparisonDocuments();
        } else {
          refreshDuplicates();
        }
      }
    }

    function closeModule() {
      if (!activeModule) {
        return;
      }
      activeModule.classList.remove("module-expanded");
      const expandButton = activeModule.querySelector("[data-expand-module]");
      if (expandButton) {
        expandButton.textContent = "Buyut";
      }
      activeModule = null;
      document.body.classList.remove("modal-open");
    }

    function renderFiles() {
      filesList.innerHTML = "";
      if (selectedFiles.length === 0) {
        filesList.innerHTML = "<li>Dosya listesi burada gorunecek.</li>";
        summary.textContent = "Henuz rapor secilmedi.";
        return;
      }

      const supported = selectedFiles.filter(file => {
        const lower = file.name.toLowerCase();
        return lower.endsWith(".pdf") || lower.endsWith(".docx") || lower.endsWith(".pptx");
      });

      summary.textContent = supported.length === 1
        ? "1 rapor secildi."
        : `${supported.length} rapor secildi.`;
      supported.slice(0, 12).forEach(file => {
        const item = document.createElement("li");
        item.textContent = file.webkitRelativePath || file.name;
        filesList.appendChild(item);
      });
      if (supported.length > 12) {
        const more = document.createElement("li");
        more.textContent = `... ve ${supported.length - 12} dosya daha`;
        filesList.appendChild(more);
      }
    }

    function renderUploadResults(items) {
      uploadResultList.innerHTML = "";
      if (!items || items.length === 0) {
        uploadResults.hidden = true;
        return;
      }
      items.forEach(result => {
        const item = document.createElement("li");
        const statusLabels = {
          ingested: "Yeni eklendi",
          duplicate: "Zaten mevcut",
          error: "Hata",
        };
        const details = [];
        if (result.pages) details.push(`${result.pages} sayfa`);
        if (result.chunks) details.push(`${result.chunks} parca`);
        if (result.ocr_pages) details.push(`${result.ocr_pages} sayfa OCR`);
        if (result.embeddings_created) details.push(`${result.embeddings_created} embedding`);
        if (result.error) details.push(result.error);
        const detailText = details.length ? ` | ${details.join(" | ")}` : "";
        item.textContent = `${result.file_name}: ${statusLabels[result.status] || result.status}${detailText}`;
        uploadResultList.appendChild(item);
      });
      uploadResults.hidden = false;
    }

    function renderUploadedDocuments(items) {
      if (!items || items.length === 0) {
        uploadedDocumentsTable.innerHTML = '<tr><td colspan="6" class="small">Iceride yuklenmis rapor bulunamadi.</td></tr>';
        return;
      }

      uploadedDocumentsTable.innerHTML = items.map(item => `
        <tr onclick="openDocumentFile(${item.document_id})" style="cursor:pointer;">
          <td>${item.document_id}</td>
          <td>
            <div class="title">${escapeHtml(item.title)}</div>
            <div class="small">${escapeHtml(item.file_name)}</div>
          </td>
          <td>${escapeHtml(item.file_type)}</td>
          <td>${item.chunk_count}</td>
          <td>${item.embedding_count}</td>
          <td>${escapeHtml(item.created_at || "")}</td>
        </tr>
      `).join("");
    }

    async function refreshUploadedDocuments() {
      uploadedDocumentsRefreshButton.disabled = true;
      uploadedDocumentsStatus.textContent = "Icerideki raporlar yukleniyor...";
      try {
        const response = await fetch("/documents/list?limit=300");
        const data = await response.json();
        if (!response.ok) {
          uploadedDocumentsStatus.textContent = data.detail || "Rapor listesi alinamadi.";
          return;
        }
        renderUploadedDocuments(data.items || []);
        uploadedDocumentsStatus.textContent = `Icerideki rapor: ${data.total}. Gosterilen: ${(data.items || []).length}.`;
      } catch (error) {
        uploadedDocumentsStatus.textContent = `Rapor listesi alinamadi: ${error}`;
      } finally {
        uploadedDocumentsRefreshButton.disabled = false;
      }
    }

    function formatRaporHubDate(value) {
      const datePart = String(value || "").split(" ")[0];
      const parts = datePart.split("-");
      if (parts.length !== 3) return value || "-";
      return `${parts[2]}.${parts[1]}.${parts[0]}`;
    }

    function renderRaporHubRecentDocuments(items) {
      const recentItems = (items || []).slice(0, 5);
      if (recentItems.length === 0) {
        raporhubRecentDocuments.innerHTML = `
          <div class="raporhub-empty-state">
            <strong>Calisma alaninda henuz rapor yok</strong>
            <span>Ilk PDF, DOCX veya PPTX raporunu ekleyerek basla.</span>
          </div>
        `;
        return;
      }

      raporhubRecentDocuments.innerHTML = recentItems.map(item => {
        const fileType = ["pdf", "docx", "pptx"].includes(String(item.file_type).toLowerCase())
          ? String(item.file_type).toLowerCase()
          : "file";
        return `
          <button class="raporhub-document-row" type="button" data-home-document-id="${Number(item.document_id)}">
            <span class="raporhub-file-badge type-${fileType}">${escapeHtml(fileType.toUpperCase())}</span>
            <span class="raporhub-document-main">
              <strong title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</strong>
              <span title="${escapeHtml(item.file_name)}">${escapeHtml(item.file_name)}</span>
            </span>
            <span class="raporhub-document-meta">${Number(item.chunk_count || 0)} parca<br>${escapeHtml(formatRaporHubDate(item.created_at))}</span>
            <span class="raporhub-document-open" aria-hidden="true">&gt;</span>
          </button>
        `;
      }).join("");
    }

    async function refreshRaporHubOverview() {
      if (!isRaporHub) return;
      raporhubOverviewStatus.textContent = "Calisma alani verileri yenileniyor.";
      try {
        const response = await fetch("/documents/list?limit=300");
        const data = await response.json();
        if (!response.ok) {
          raporhubOverviewStatus.textContent = data.detail || "Calisma alani verileri alinamadi.";
          return;
        }

        const items = data.items || [];
        const chunkCount = items.reduce((total, item) => total + Number(item.chunk_count || 0), 0);
        const embeddingCount = items.reduce((total, item) => total + Number(item.embedding_count || 0), 0);
        const coverage = chunkCount > 0 ? Math.min(100, Math.round(embeddingCount * 100 / chunkCount)) : 0;
        const typeCounts = items.reduce((counts, item) => {
          const key = String(item.file_type || "diger").toUpperCase();
          counts[key] = (counts[key] || 0) + 1;
          return counts;
        }, {});

        raporhubDocumentCount.textContent = Number(data.total || 0).toLocaleString("tr-TR");
        raporhubChunkCount.textContent = chunkCount.toLocaleString("tr-TR");
        raporhubEmbeddingCoverage.textContent = `%${coverage}`;
        raporhubLastUpload.textContent = items.length ? formatRaporHubDate(items[0].created_at) : "-";
        raporhubCoverageBar.style.width = `${coverage}%`;
        raporhubFileTypes.textContent = Object.entries(typeCounts)
          .map(([type, count]) => `${type} ${count}`)
          .join(" / ") || "-";
        renderRaporHubRecentDocuments(items);

        raporhubReadinessLabel.classList.toggle("partial", coverage < 95);
        if (!items.length) {
          raporhubReadinessLabel.textContent = "Veri bekliyor";
          raporhubReadinessCopy.textContent = "Arama ve kaynakli cevap icin once rapor eklenmeli.";
        } else if (coverage >= 95) {
          raporhubReadinessLabel.textContent = "Hazir";
          raporhubReadinessCopy.textContent = `${embeddingCount.toLocaleString("tr-TR")} embedding arama icin hazir.`;
        } else {
          raporhubReadinessLabel.textContent = "Kismi hazir";
          raporhubReadinessCopy.textContent = `${embeddingCount.toLocaleString("tr-TR")} / ${chunkCount.toLocaleString("tr-TR")} metin parcasi aramaya hazir.`;
        }
        raporhubOverviewStatus.textContent = `${Math.min(items.length, 5)} son rapor gosteriliyor. Toplam ${Number(data.total || 0)} rapor var.`;
      } catch (error) {
        raporhubOverviewStatus.textContent = `Calisma alani verileri alinamadi: ${error}`;
        raporhubRecentDocuments.innerHTML = `
          <div class="raporhub-empty-state">
            <strong>Rapor listesine ulasilamadi</strong>
            <span>Sunucu durumunu kontrol edip yeniden dene.</span>
          </div>
        `;
      }
    }

    function openRaporHubAction(action) {
      if (action === "comparison") {
        applyModuleFilter("duplicates");
        setDuplicateWorkspace("comparison");
        return;
      }
      applyModuleFilter(action || "home");
    }

    function askFromRaporHubHome() {
      const question = raporhubHomeQuestion.value.trim();
      if (!question) {
        raporhubHomeQuestion.focus();
        return;
      }
      applyModuleFilter("chat");
      chatInput.value = question;
      sendChatMessage();
    }

    function setStatus(kind, message) {
      statusBox.className = `status show ${kind}`;
      statusBox.textContent = message;
    }

    function setCatalogStatus(kind, message) {
      catalogStatusBox.className = `status show ${kind}`;
      catalogStatusBox.textContent = message;
    }

    function setCatalogLog(data) {
      catalogResultBox.textContent = JSON.stringify(data, null, 2);
      if (data.total_seen !== undefined) {
        catalogLogSummary.textContent = `Teknik log | toplam ${data.total_seen} | ingested ${data.ingested_count} | pending ${data.pending_count}`;
        return;
      }
      if (data.created_count !== undefined) {
        catalogLogSummary.textContent = `Teknik log | yeni ${data.created_count} | guncellenen ${data.updated_count || 0} | duplicate ${data.duplicate_count} | hata ${data.error_count}`;
        return;
      }
      if (data.ingested_count !== undefined) {
        catalogLogSummary.textContent = `Teknik log | ingested ${data.ingested_count} | duplicate ${data.duplicate_count} | hata ${data.error_count}`;
        return;
      }
      if (data.chunks_seen !== undefined) {
        catalogLogSummary.textContent = `Teknik log | chunk ${data.chunks_seen} | embedding ${data.embeddings_created}`;
        return;
      }
      catalogLogSummary.textContent = "Teknik log";
    }

    function catalogIngestResultMessage(data) {
      const base = `Ice alma tamamlandi. Yeni: ${data.ingested_count}, duplicate: ${data.duplicate_count}, hata: ${data.error_count}.`;
      const failedItems = (data.items || []).filter(item => item.status === "error");
      if (failedItems.length === 0) {
        return base;
      }

      const firstError = failedItems[0];
      const report = firstError.report_code || firstError.source_path || `ID ${firstError.catalog_entry_id}`;
      return `${base} Ilk hata: ${report} -> ${firstError.error || "detay yok"}`;
    }

    function formatScore(value) {
      if (typeof value !== "number") return "0.000";
      return value.toFixed(3);
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function tokenizeHighlightTerms(query) {
      return String(query || "")
        .split(/\\s+/)
        .map(term => term.trim())
        .filter(term => term.length >= 2);
    }

    function normalizeSearchText(value) {
      return String(value || "")
        .toLocaleLowerCase("tr-TR")
        .replaceAll("ı", "i")
        .replaceAll("ğ", "g")
        .replaceAll("ü", "u")
        .replaceAll("ş", "s")
        .replaceAll("ö", "o")
        .replaceAll("ç", "c")
        .normalize("NFD")
        .replace(/[\\u0300-\\u036f]/g, "");
    }

    function editDistance(left, right) {
      if (Math.abs(left.length - right.length) > 1) {
        return 2;
      }
      const previous = Array.from({ length: right.length + 1 }, (_, index) => index);
      for (let leftIndex = 1; leftIndex <= left.length; leftIndex += 1) {
        const current = [leftIndex];
        for (let rightIndex = 1; rightIndex <= right.length; rightIndex += 1) {
          const insertCost = current[rightIndex - 1] + 1;
          const deleteCost = previous[rightIndex] + 1;
          const replaceCost = previous[rightIndex - 1] + (left[leftIndex - 1] === right[rightIndex - 1] ? 0 : 1);
          current.push(Math.min(insertCost, deleteCost, replaceCost));
        }
        previous.splice(0, previous.length, ...current);
      }
      return previous[right.length];
    }

    function isHighlightMatch(word, terms) {
      const normalizedWord = normalizeSearchText(word);
      return terms.some(term => {
        const normalizedTerm = normalizeSearchText(term);
        if (!normalizedTerm) {
          return false;
        }
        if (normalizedWord.includes(normalizedTerm) || normalizedTerm.includes(normalizedWord)) {
          return true;
        }
        if (normalizedTerm.length < 5 || normalizedWord.length < 5 || normalizedTerm[0] !== normalizedWord[0]) {
          return false;
        }
        const maxDistance = Math.min(normalizedTerm.length, normalizedWord.length) >= 6 ? 2 : 1;
        return editDistance(normalizedTerm, normalizedWord) <= maxDistance;
      });
    }

    function highlightText(value, query) {
      const terms = tokenizeHighlightTerms(query).sort((a, b) => b.length - a.length);
      if (terms.length === 0) {
        return escapeHtml(value);
      }

      return String(value ?? "")
        .split(/([\\p{L}\\p{N}_]+)/gu)
        .map(part => isHighlightMatch(part, terms) ? `<mark>${escapeHtml(part)}</mark>` : escapeHtml(part))
        .join("");
    }

    function renderResults(items, query) {
      if (!items || items.length === 0) {
        resultsList.innerHTML = '<div class="empty">Sonuc bulunamadi.</div>';
        return;
      }

      resultsList.innerHTML = items.map(item => `
        <article class="result-card" onclick="openDocumentFile(${item.document_id})" style="cursor:pointer;">
          <div class="result-head">
            <div>
              <div class="title">${highlightText(item.document_title, query)}</div>
              <div class="small">Belge ID: ${item.document_id} | Sayfa ${item.page_start}-${item.page_end}${item.section_title ? " | " + highlightText(item.section_title, query) : ""}</div>
            </div>
            <span class="tag">${escapeHtml(item.match_type)}</span>
          </div>
          <div class="small">keyword: ${formatScore(item.keyword_score)} | semantic: ${formatScore(item.semantic_score)} | combined: ${formatScore(item.combined_score)}</div>
          <div class="excerpt">${highlightText(item.chunk_text, query)}</div>
        </article>
      `).join("");
    }

    function renderSimilar(items, query) {
      if (!items || items.length === 0) {
        similarList.innerHTML = '<div class="empty">Benzer rapor bulunamadi.</div>';
        return;
      }

      similarList.innerHTML = items.map(item => `
        <article class="similar-card" onclick="openDocumentFile(${item.document_id})" style="cursor:pointer;">
          <div class="similar-head">
            <div>
              <div class="title">${highlightText(item.document_title, query)}</div>
              <div class="small">Belge ID: ${item.document_id} | ${highlightText(item.file_name, query)}</div>
            </div>
            <span class="tag">score ${formatScore(item.score)}</span>
          </div>
          <div class="small">matched chunks: <span class="count">${item.matched_chunks}</span>${item.top_page_start ? ` | sayfa ${item.top_page_start}-${item.top_page_end}` : ""}</div>
          <div class="excerpt">${highlightText(item.top_excerpt, query)}</div>
        </article>
      `).join("");
    }

    function renderDuplicatePairs(items) {
      if (!items || items.length === 0) {
        duplicateList.innerHTML = '<div class="empty">Kayitli mukerrer adayi bulunamadi. Once taramayi baslat.</div>';
        return;
      }

      duplicateList.innerHTML = items.map(item => `
        <article class="similar-card">
          <div class="similar-head">
            <div>
              <div class="title">Benzerlik: ${formatScore(item.similarity_score)}</div>
              <div class="small">Sebep: ${escapeHtml(item.reason)} | Baslik: ${formatScore(item.title_score)} | Embedding: ${formatScore(item.embedding_score)}</div>
            </div>
            <span class="tag">${escapeHtml(item.status || "candidate")}</span>
          </div>
          <div class="split" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:12px;">
            <div class="source-card" onclick="openDocumentFile(${item.document_id_a})" style="cursor:pointer;">
              <div class="title">${escapeHtml(item.document_title_a)}</div>
              <div class="small">Belge ID: ${item.document_id_a} | ${escapeHtml(item.file_name_a)}</div>
            </div>
            <div class="source-card" onclick="openDocumentFile(${item.document_id_b})" style="cursor:pointer;">
              <div class="title">${escapeHtml(item.document_title_b)}</div>
              <div class="small">Belge ID: ${item.document_id_b} | ${escapeHtml(item.file_name_b)}</div>
            </div>
          </div>
        </article>
      `).join("");
    }

    async function refreshDuplicates() {
      duplicateRefreshButton.disabled = true;
      duplicateStatus.textContent = "Kayitli mukerrer adaylari yukleniyor...";
      try {
        const response = await fetch("/duplicates?limit=100");
        const data = await response.json();
        if (!response.ok) {
          duplicateStatus.textContent = data.detail || "Mukerrer adaylari alinamadi.";
          return;
        }
        renderDuplicatePairs(data.items || []);
        duplicateStatus.textContent = `Kayitli mukerrer adayi: ${data.total}.`;
      } catch (error) {
        duplicateStatus.textContent = `Mukerrer adaylari alinamadi: ${error}`;
      } finally {
        duplicateRefreshButton.disabled = false;
      }
    }

    async function runDuplicateScan() {
      duplicateScanButton.disabled = true;
      duplicateRefreshButton.disabled = true;
      const startedAt = startTimer(
        message => { duplicateStatus.textContent = message; },
        "Mukerrer taramasi calisiyor..."
      );
      try {
        const response = await fetch("/duplicates/scan?threshold=0.90&dry_run=false", {
          method: "POST",
        });
        const data = await response.json();
        if (!response.ok) {
          stopTimer(startedAt, message => { duplicateStatus.textContent = message; }, data.detail || "Mukerrer taramasi basarisiz oldu.");
          return;
        }
        stopTimer(
          startedAt,
          message => { duplicateStatus.textContent = message; },
          `Tarama tamamlandi. Dokuman: ${data.documents_seen}, aday: ${data.candidate_count}, yeni: ${data.created_count}, guncellenen: ${data.updated_count}.`
        );
        await refreshDuplicates();
      } catch (error) {
        stopTimer(startedAt, message => { duplicateStatus.textContent = message; }, `Mukerrer taramasi basarisiz oldu: ${error}`);
      } finally {
        duplicateScanButton.disabled = false;
        duplicateRefreshButton.disabled = false;
      }
    }

    function setDuplicateWorkspace(view) {
      duplicateWorkspaceView = view === "comparison" ? "comparison" : "candidates";
      const comparisonActive = duplicateWorkspaceView === "comparison";
      duplicateCandidatesTab.classList.toggle("active", !comparisonActive);
      reportComparisonTab.classList.toggle("active", comparisonActive);
      duplicateCandidatesTab.setAttribute("aria-selected", String(!comparisonActive));
      reportComparisonTab.setAttribute("aria-selected", String(comparisonActive));
      duplicateCandidatesPane.hidden = comparisonActive;
      reportComparisonPane.hidden = !comparisonActive;
      if (comparisonActive) {
        refreshComparisonDocuments();
      } else {
        refreshDuplicates();
      }
    }

    function temporaryOptionSnapshot(select) {
      const option = select.selectedOptions[0];
      if (!option || !option.value.startsWith("temp:")) {
        return null;
      }
      return { value: option.value, text: option.textContent };
    }

    function fillComparisonSelect(select, items, preserved) {
      const previousValue = select.value;
      select.innerHTML = '<option value="">Rapor sec...</option>';
      items.forEach(item => {
        const option = document.createElement("option");
        option.value = `doc:${item.document_id}`;
        option.textContent = `${item.title} | ${item.file_name}`;
        select.appendChild(option);
      });
      if (preserved && !Array.from(select.options).some(option => option.value === preserved.value)) {
        const option = document.createElement("option");
        option.value = preserved.value;
        option.textContent = preserved.text;
        option.dataset.temporary = "true";
        select.appendChild(option);
      }
      if (Array.from(select.options).some(option => option.value === previousValue)) {
        select.value = previousValue;
      } else if (preserved) {
        select.value = preserved.value;
      }
    }

    async function refreshComparisonDocuments(force = false) {
      if (comparisonDocumentsLoaded && !force) {
        return;
      }
      const leftTemporary = temporaryOptionSnapshot(comparisonLeftSelect);
      const rightTemporary = temporaryOptionSnapshot(comparisonRightSelect);
      try {
        const response = await fetch("/documents/list?limit=500");
        const data = await response.json();
        if (!response.ok) {
          comparisonStatus.textContent = data.detail || "Rapor listesi alinamadi.";
          return;
        }
        fillComparisonSelect(comparisonLeftSelect, data.items || [], leftTemporary);
        fillComparisonSelect(comparisonRightSelect, data.items || [], rightTemporary);
        comparisonDocumentsLoaded = true;
      } catch (error) {
        comparisonStatus.textContent = `Rapor listesi alinamadi: ${error}`;
      }
    }

    function setTemporaryComparisonSelection(select, data) {
      const value = `temp:${data.upload_token}`;
      let option = Array.from(select.options).find(item => item.value === value);
      if (!option) {
        option = document.createElement("option");
        option.value = value;
        option.dataset.temporary = "true";
        select.appendChild(option);
      }
      option.textContent = `${data.title} | gecici yukleme`;
      select.value = value;
    }

    function updateComparisonSourceMeta(select, meta) {
      const option = select.selectedOptions[0];
      if (!option || !option.value) {
        meta.textContent = "Kaynak secilmedi.";
        return;
      }
      meta.textContent = option.value.startsWith("temp:")
        ? "Gecici rapor, havuza eklenmedi."
        : "Rapor havuzundan secildi.";
    }

    async function uploadComparisonSource(side, input) {
      const file = input.files && input.files[0];
      if (!file) {
        return;
      }
      const select = side === "left" ? comparisonLeftSelect : comparisonRightSelect;
      const meta = side === "left" ? comparisonLeftMeta : comparisonRightMeta;
      comparisonRunButton.disabled = true;
      input.disabled = true;
      const persist = comparisonPersistUploads.checked;
      const startedAt = startTimer(
        message => { comparisonStatus.textContent = message; },
        persist ? "Rapor havuza ekleniyor..." : "Gecici rapor yukleniyor..."
      );
      try {
        const formData = new FormData();
        formData.append("file", file);
        const endpoint = persist ? "/ingest" : "/report-comparison/upload";
        const response = await fetch(endpoint, { method: "POST", body: formData });
        const data = await response.json();
        if (!response.ok) {
          stopTimer(
            startedAt,
            message => { comparisonStatus.textContent = message; },
            data.detail || "Rapor yuklenemedi."
          );
          return;
        }
        if (persist) {
          comparisonDocumentsLoaded = false;
          await refreshComparisonDocuments(true);
          select.value = `doc:${data.document_id}`;
          meta.textContent = "Rapor havuzuna eklendi ve secildi.";
        } else {
          setTemporaryComparisonSelection(select, data);
          meta.textContent = "Gecici rapor yuklendi; rapor havuzuna eklenmedi.";
        }
        stopTimer(
          startedAt,
          message => { comparisonStatus.textContent = message; },
          `${file.name} karsilastirma icin hazir.`
        );
      } catch (error) {
        stopTimer(
          startedAt,
          message => { comparisonStatus.textContent = message; },
          `Rapor yuklenemedi: ${error}`
        );
      } finally {
        input.value = "";
        input.disabled = false;
        comparisonRunButton.disabled = false;
      }
    }

    function comparisonSourcePayload(value) {
      if (value.startsWith("doc:")) {
        return { document_id: Number(value.slice(4)) };
      }
      if (value.startsWith("temp:")) {
        return { upload_token: value.slice(5) };
      }
      return null;
    }

    function ensureComparisonOption(target, source, value) {
      if (!value || Array.from(target.options).some(option => option.value === value)) {
        return;
      }
      const sourceOption = Array.from(source.options).find(option => option.value === value);
      if (sourceOption) {
        target.appendChild(sourceOption.cloneNode(true));
      }
    }

    function swapComparisonSources() {
      const leftValue = comparisonLeftSelect.value;
      const rightValue = comparisonRightSelect.value;
      ensureComparisonOption(comparisonLeftSelect, comparisonRightSelect, rightValue);
      ensureComparisonOption(comparisonRightSelect, comparisonLeftSelect, leftValue);
      comparisonLeftSelect.value = rightValue;
      comparisonRightSelect.value = leftValue;
      updateComparisonSourceMeta(comparisonLeftSelect, comparisonLeftMeta);
      updateComparisonSourceMeta(comparisonRightSelect, comparisonRightMeta);
    }

    function comparisonTypeLabel(type) {
      const labels = {
        value_change: "Deger degisikligi",
        result_change: "Sonuc degisikligi",
        contradiction: "Celiski",
        content_change: "Icerik farki",
        only_left: "Yalniz Rapor A",
        only_right: "Yalniz Rapor B",
      };
      return labels[type] || "Farklilik";
    }

    function comparisonHighlightColor(value) {
      const color = String(value || "").trim();
      return /^#[0-9a-fA-F]{6}$/.test(color) ? color : "";
    }

    function renderComparisonEvidence(source, label) {
      const page = source.page_start
        ? `Sayfa ${source.page_start}${source.page_end && source.page_end !== source.page_start ? "-" + source.page_end : ""}`
        : "Eslesen kaynak yok";
      const section = source.section_title ? ` | ${escapeHtml(source.section_title)}` : "";
      const openButton = Number.isInteger(source.document_id)
        ? `<button class="comparison-open" type="button" onclick="openDocumentFile(${source.document_id})">Raporu Ac</button>`
        : "";
      return `
        <div class="comparison-evidence">
          <div class="comparison-evidence-title">
            <span>${label} | ${escapeHtml(source.document_title)}</span>
            ${openButton}
          </div>
          <div class="small">${page}${section}</div>
          <div class="comparison-evidence-text">${escapeHtml(source.excerpt)}</div>
        </div>
      `;
    }

    function renderComparisonRows(container, items, emptyMessage) {
      if (!items || items.length === 0) {
        container.innerHTML = `<div class="empty" style="padding:16px 0;">${escapeHtml(emptyMessage)}</div>`;
        return;
      }
      container.innerHTML = items.map(item => {
        const tag = item.kind === "difference"
          ? comparisonTypeLabel(item.difference_type)
          : "Ortak bulgu";
        const confidence = Math.round((Number(item.confidence) || 0) * 100);
        const highlightColor = comparisonHighlightColor(item.highlight_color);
        const highlightNumber = Number(item.highlight_number) || 0;
        const highlighted = Boolean(highlightColor && highlightNumber);
        const highlightActions = highlighted
          ? `
            <span class="comparison-pair-marker" style="--pair-color:${highlightColor}">Eslesme ${highlightNumber}</span>
            <button class="comparison-focus" type="button" data-comparison-focus="${escapeHtml(item.id)}">PDF'de Goster</button>
          `
          : "";
        return `
          <article class="comparison-row${highlighted ? " has-pdf-highlight" : ""}"${highlighted ? ` style="--pair-color:${highlightColor}"` : ""}>
            <div class="comparison-row-head">
              <div>
                <div class="comparison-row-topic">${escapeHtml(item.topic)}</div>
                <div class="comparison-row-summary">${escapeHtml(item.summary)}</div>
              </div>
              <div class="comparison-highlight-actions">
                ${highlightActions}
                <span class="tag">${escapeHtml(tag)} | %${confidence}</span>
              </div>
            </div>
            <div class="comparison-evidence-grid">
              ${renderComparisonEvidence(item.left, "Rapor A")}
              ${renderComparisonEvidence(item.right, "Rapor B")}
            </div>
          </article>
        `;
      }).join("");
    }

    function setComparisonResultView(view) {
      const showDifferences = view === "differences";
      comparisonSimilaritiesTab.classList.toggle("active", !showDifferences);
      comparisonDifferencesTab.classList.toggle("active", showDifferences);
      comparisonSimilaritiesTab.setAttribute("aria-selected", String(!showDifferences));
      comparisonDifferencesTab.setAttribute("aria-selected", String(showDifferences));
      comparisonSimilaritiesPane.hidden = showDifferences;
      comparisonDifferencesPane.hidden = !showDifferences;
    }

    function comparisonItems() {
      if (!latestComparisonData) return [];
      return [
        ...(latestComparisonData.similarities || []),
        ...(latestComparisonData.differences || []),
      ];
    }

    function comparisonPdfPageUrl(url, page) {
      const safePage = Math.max(Number(page) || 1, 1);
      return `${url}#page=${safePage}&zoom=page-width`;
    }

    function setComparisonPdfSide(side, preview, documentData, page) {
      const leftSide = side === "left";
      const frame = leftSide ? comparisonLeftPdfFrame : comparisonRightPdfFrame;
      const placeholder = leftSide ? comparisonLeftPdfPlaceholder : comparisonRightPdfPlaceholder;
      const title = leftSide ? comparisonLeftPdfTitle : comparisonRightPdfTitle;
      const openButton = leftSide ? comparisonLeftPdfOpen : comparisonRightPdfOpen;
      const label = leftSide ? "Rapor A" : "Rapor B";
      title.textContent = `${label} | ${documentData?.title || documentData?.file_name || "PDF"}`;
      if (preview?.available && preview.url) {
        const targetUrl = comparisonPdfPageUrl(preview.url, page);
        frame.hidden = false;
        placeholder.hidden = true;
        if (frame.getAttribute("src") !== targetUrl) {
          frame.setAttribute("src", targetUrl);
        }
        openButton.disabled = false;
        openButton.dataset.url = targetUrl;
        return;
      }
      frame.hidden = true;
      frame.removeAttribute("src");
      placeholder.hidden = false;
      placeholder.textContent = preview?.reason || "Bu kaynak icin PDF onizlemesi bulunmuyor.";
      openButton.disabled = true;
      delete openButton.dataset.url;
    }

    function focusComparisonPdf(itemId, scrollToViewer = true) {
      if (!latestComparisonData) return;
      const item = comparisonItems().find(row => row.id === itemId);
      if (!item) return;
      const leftPage = item.left?.highlight_page || item.left?.page_start || 1;
      const rightPage = item.right?.highlight_page || item.right?.page_start || 1;
      setComparisonPdfSide("left", latestComparisonData.left_pdf, latestComparisonData.left, leftPage);
      setComparisonPdfSide("right", latestComparisonData.right_pdf, latestComparisonData.right, rightPage);
      const number = Number(item.highlight_number) || "";
      comparisonPdfStatus.textContent = number
        ? `Eslesme ${number} secildi. PDF'lerin tamami acik; ayni renk eslestirilen pasaj ciftini gosterir.`
        : "PDF'lerin tamami renkli isaretlemelerle acildi.";
      if (scrollToViewer) {
        comparisonPdfWorkspace.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }

    function renderComparisonPdfWorkspace(data) {
      comparisonPdfWorkspace.hidden = false;
      const pairViewerAvailable = Boolean(
        data.comparison_id && data.left_pdf?.available && data.right_pdf?.available
      );
      comparisonPairFullscreenOpen.disabled = !pairViewerAvailable;
      if (pairViewerAvailable) {
        comparisonPairFullscreenOpen.dataset.url =
          `/report-comparison/${encodeURIComponent(data.comparison_id)}/viewer`;
        comparisonPairFullscreenOpen.title = "Renkli iki PDF'yi yeni sekmede yan yana ac";
      } else {
        delete comparisonPairFullscreenOpen.dataset.url;
        comparisonPairFullscreenOpen.title = "Tam ekran icin iki kaynagin da PDF olmasi gerekir";
      }
      const highlightedItems = comparisonItems().filter(
        item => comparisonHighlightColor(item.highlight_color) && Number(item.highlight_number)
      );
      const legendItems = [];
      const seenNumbers = new Set();
      highlightedItems.forEach(item => {
        const number = Number(item.highlight_number);
        if (seenNumbers.has(number)) return;
        seenNumbers.add(number);
        legendItems.push(item);
      });
      comparisonHighlightLegend.innerHTML = legendItems.map(item => {
        const color = comparisonHighlightColor(item.highlight_color);
        return `
          <span class="comparison-highlight-legend-item" title="${escapeHtml(item.topic)}">
            <span class="comparison-highlight-swatch" style="--pair-color:${color}"></span>
            ${Number(item.highlight_number)}
          </span>
        `;
      }).join("");

      const leftCount = Number(data.left_pdf?.highlighted_passages) || 0;
      const rightCount = Number(data.right_pdf?.highlighted_passages) || 0;
      comparisonPdfStatus.textContent = highlightedItems.length
        ? `Rapor A: ${leftCount}, Rapor B: ${rightCount} pasaj isaretlendi. Bir sonuc uzerinden PDF'de Goster'e basabilirsin.`
        : "PDF'ler acildi ancak eslesen pasaj koordinati bulunamadi.";

      const initialItem = highlightedItems[0];
      const leftPage = initialItem?.left?.highlight_page || initialItem?.left?.page_start || 1;
      const rightPage = initialItem?.right?.highlight_page || initialItem?.right?.page_start || 1;
      setComparisonPdfSide("left", data.left_pdf, data.left, leftPage);
      setComparisonPdfSide("right", data.right_pdf, data.right, rightPage);
    }

    function renderComparison(data) {
      latestComparisonData = data;
      comparisonOutput.hidden = false;
      comparisonSummary.innerHTML = `
        <div class="comparison-summary-item">
          <span class="comparison-summary-value">${data.similarity_count}</span>
          <span class="comparison-summary-label">Benzerlik</span>
        </div>
        <div class="comparison-summary-item">
          <span class="comparison-summary-value">${data.difference_count}</span>
          <span class="comparison-summary-label">Farklilik</span>
        </div>
        <div class="comparison-summary-item">
          <span class="comparison-summary-value">%${Math.round((Number(data.coverage) || 0) * 100)}</span>
          <span class="comparison-summary-label">Eslesen icerik kapsami</span>
        </div>
      `;
      comparisonSimilaritiesTab.textContent = `Benzerlikler (${data.similarity_count})`;
      comparisonDifferencesTab.textContent = `Farkliliklar (${data.difference_count})`;
      renderComparisonRows(
        comparisonSimilarities,
        data.similarities || [],
        "Guvenilir ortak teknik bulgu bulunamadi."
      );
      renderComparisonRows(
        comparisonDifferences,
        data.differences || [],
        "Guvenilir farklilik bulunamadi."
      );
      renderComparisonPdfWorkspace(data);
      setComparisonResultView(data.similarity_count > 0 ? "similarities" : "differences");
    }

    async function runReportComparison() {
      const left = comparisonSourcePayload(comparisonLeftSelect.value);
      const right = comparisonSourcePayload(comparisonRightSelect.value);
      if (!left || !right) {
        comparisonStatus.textContent = "Karsilastirma icin Rapor A ve Rapor B secilmeli.";
        return;
      }
      if (comparisonLeftSelect.value === comparisonRightSelect.value) {
        comparisonStatus.textContent = "Iki farkli rapor sec.";
        return;
      }
      comparisonRunButton.disabled = true;
      comparisonOutput.hidden = true;
      comparisonPdfWorkspace.hidden = true;
      comparisonPairFullscreenOpen.disabled = true;
      delete comparisonPairFullscreenOpen.dataset.url;
      comparisonLeftPdfFrame.removeAttribute("src");
      comparisonRightPdfFrame.removeAttribute("src");
      const startedAt = startTimer(
        message => { comparisonStatus.textContent = message; },
        "Raporlar eslestiriliyor ve farklar dogrulaniyor..."
      );
      try {
        const response = await fetch("/report-comparison", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ left, right, use_llm: true }),
        });
        const data = await response.json();
        if (!response.ok) {
          stopTimer(
            startedAt,
            message => { comparisonStatus.textContent = message; },
            data.detail || "Raporlar karsilastirilamadi."
          );
          return;
        }
        renderComparison(data);
        const generation = data.llm_used ? data.generation_provider : "kural tabanli";
        const cacheText = data.cache_hit ? " | onbellek" : "";
        stopTimer(
          startedAt,
          message => { comparisonStatus.textContent = message; },
          `Karsilastirma tamamlandi. Benzerlik: ${data.similarity_count}, farklilik: ${data.difference_count} | ${generation}${cacheText}`
        );
      } catch (error) {
        stopTimer(
          startedAt,
          message => { comparisonStatus.textContent = message; },
          `Raporlar karsilastirilamadi: ${error}`
        );
      } finally {
        comparisonRunButton.disabled = false;
      }
    }

    function compactChatProvider(provider) {
      const value = String(provider || "");
      if (!value) return "";
      if (value.startsWith("haystack:")) return `Haystack ${value.slice("haystack:".length)}`;
      if (value.includes("Qwen3-Embedding")) return "Qwen3 Embedding";
      if (value.includes("ollama:")) return value.split("ollama:").pop();
      if (value === "document-analysis:status") return "Kural tabanli";
      if (value === "database") return "Veritabani";
      if (value === "keyword-only") return "Keyword";
      return value.split(":").pop();
    }

    function chatEngineLabel(data) {
      if (!data.retrieval_used) {
        return `Genel LLM${data.embedding_provider ? ` • ${compactChatProvider(data.embedding_provider)}` : ""}`;
      }
      const version = data.retrieval_version === "v1"
        ? "RAG v1 • Klasik"
        : data.retrieval_version === "v3"
          ? "RAG v3"
          : "RAG v2 • Beta";
      const providers = [
        compactChatProvider(data.retrieval_provider),
        compactChatProvider(data.embedding_provider),
      ].filter((value, index, items) => value && items.indexOf(value) === index);
      return [version, ...providers].join(" • ");
    }

    function appendChatMessage(role, content, meta = "") {
      const node = document.createElement("div");
      node.className = `chat-message ${role}`;
      const label = document.createElement("div");
      label.className = "chat-message-label";
      const labelText = document.createElement("span");
      labelText.textContent = role === "user" ? "Sen" : "__BRAND_NAME__";
      label.appendChild(labelText);
      if (meta) {
        const metaNode = document.createElement("span");
        metaNode.className = "chat-message-meta";
        metaNode.textContent = meta;
        label.appendChild(metaNode);
      }
      const body = document.createElement("div");
      body.className = "chat-message-body";
      body.textContent = content;
      node.appendChild(label);
      node.appendChild(body);
      chatMessages.appendChild(node);
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function syncChatInputHeight() {
      chatInput.style.height = "auto";
      chatInput.style.height = `${Math.min(chatInput.scrollHeight, 150)}px`;
    }

    function resetChat() {
      chatHistory = [];
      chatContextDocumentIds = [];
      chatMessages.innerHTML = "";
      appendChatMessage("assistant", "Merhaba. Raporlar uzerinden soru sorabilir, ben de kaynaklariyla birlikte cevaplayabilirim.");
      chatSources.innerHTML = '<div class="empty">Kaynaklar cevap geldikce burada listelenecek.</div>';
      chatSourceMeta.textContent = "Cevap geldikce ilgili rapor pasajlari burada gorunur.";
      chatStatus.textContent = "Chatbot hazir.";
      chatInput.value = "";
      syncChatInputHeight();
      chatInput.focus();
    }

    async function sendChatMessage() {
      const message = chatInput.value.trim();
      if (!message) {
        chatStatus.textContent = "Mesaj yazmadan gonderemem.";
        return;
      }

      chatInput.value = "";
      syncChatInputHeight();
      appendChatMessage("user", message);
      chatHistory.push({ role: "user", content: message });
      chatSendButton.disabled = true;
      const startedAt = startTimer(
        text => { chatStatus.textContent = text; },
        "Chatbot cevap ariyor..."
      );

      try {
        const response = await fetch("/chat", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            message,
            history: chatHistory.slice(-8),
            assistant_mode: chatAssistantMode.value,
            retrieval_version: chatRetrievalVersion.value,
            mode: chatMode.value,
            limit: 5,
            document_ids: chatContextDocumentIds.slice(0, 8),
          }),
        });
        const data = await response.json();
        if (!response.ok) {
          stopTimer(startedAt, text => { chatStatus.textContent = text; }, data.detail || "Chatbot cevap veremedi.");
          appendChatMessage("assistant", data.detail || "Cevap olusturulamadi.");
          return;
        }
        const engineLabel = chatEngineLabel(data);
        appendChatMessage("assistant", data.answer, engineLabel);
        chatHistory = data.history || [
          ...chatHistory,
          { role: "assistant", content: data.answer },
        ];
        chatContextDocumentIds = [...new Set((data.sources || [])
          .map(item => Number(item.document_id))
          .filter(value => Number.isInteger(value) && value > 0)
        )].slice(0, 8);
        renderChatSources(data.sources || []);
        stopTimer(
          startedAt,
          text => { chatStatus.textContent = text; },
          `${engineLabel} | Guven: ${formatScore(data.confidence)} | Kaynak: ${(data.sources || []).length}`
        );
      } catch (error) {
        stopTimer(startedAt, text => { chatStatus.textContent = text; }, `Chatbot hata verdi: ${error}`);
        appendChatMessage("assistant", "Cevap olusturulurken hata olustu.");
      } finally {
        chatSendButton.disabled = false;
      }
    }

    function renderChatSources(items) {
      if (!items || items.length === 0) {
        chatSources.innerHTML = '<div class="empty">Bu cevap icin kaynak bulunamadi.</div>';
        chatSourceMeta.textContent = "Bu cevap sohbet yaniti olarak dondu; kaynak pasaj kullanilmadi.";
        return;
      }

      chatSourceMeta.textContent = `${items.length} kaynak bulundu. Karta tiklayinca orijinal dosya acilir.`;
      chatSources.innerHTML = items.map(item => `
        <article class="chat-source-card" onclick="openDocumentFile(${item.document_id})">
          <div class="title">${escapeHtml(item.document_title)}</div>
          <div class="small">Belge ID: ${item.document_id} | Sayfa ${item.page_start}-${item.page_end}${item.section_title ? " | " + escapeHtml(item.section_title) : ""}</div>
          <div class="small">match: ${escapeHtml(item.match_type)} | combined: ${formatScore(item.combined_score)}</div>
          <div class="excerpt">${escapeHtml(item.chunk_text)}</div>
        </article>
      `).join("");
    }

    function renderAnswerSources(items) {
      if (!items || items.length === 0) {
        answerSources.innerHTML = '<div class="empty">Kaynak bulunamadi.</div>';
        return;
      }

      answerSources.innerHTML = items.map(item => `
        <article class="source-card" onclick="openDocumentFile(${item.document_id})" style="cursor:pointer;">
          <div class="title">${escapeHtml(item.document_title)}</div>
          <div class="small">Belge ID: ${item.document_id} | Sayfa ${item.page_start}-${item.page_end}${item.section_title ? " | " + escapeHtml(item.section_title) : ""}</div>
          <div class="small">match: ${escapeHtml(item.match_type)} | combined: ${formatScore(item.combined_score)}</div>
          <div class="excerpt">${escapeHtml(item.chunk_text)}</div>
        </article>
      `).join("");
    }

    function renderDraftSources(items) {
      if (!items || items.length === 0) {
        draftSources.innerHTML = '<div class="empty">Referans kaynak bulunamadi.</div>';
        selectedDraftDocumentIds = [];
        return;
      }

      const previousSelection = new Set(selectedDraftDocumentIds.map(Number));
      const hasPreviousSelection = previousSelection.size > 0;
      const sourceDocumentIds = [...new Set(items.map(item => Number(item.document_id)).filter(value => Number.isInteger(value) && value > 0))];
      selectedDraftDocumentIds = hasPreviousSelection
        ? sourceDocumentIds.filter(value => previousSelection.has(value))
        : sourceDocumentIds;

      draftSources.innerHTML = items.map(item => `
        <article class="source-card">
          <div class="title">${escapeHtml(item.document_title)}</div>
          <div class="small">Belge ID: ${item.document_id} | Sayfa ${item.page_start}-${item.page_end}${item.section_title ? " | " + escapeHtml(item.section_title) : ""}</div>
          <label class="small" style="display:flex;gap:8px;align-items:center;margin:8px 0;">
            <input type="checkbox" class="draft-source-check" value="${item.document_id}" ${selectedDraftDocumentIds.includes(Number(item.document_id)) ? "checked" : ""} />
            Rapor taslaginda kullan
          </label>
          <div class="excerpt">${escapeHtml(item.chunk_text)}</div>
          <button class="button secondary" type="button" onclick="openDocumentFile(${item.document_id})" style="margin-top:8px;">Raporu Gor</button>
        </article>
      `).join("");

      draftSources.querySelectorAll(".draft-source-check").forEach(input => {
        input.addEventListener("change", updateSelectedDraftSources);
      });
      updateSelectedDraftSources();
    }

    function updateSelectedDraftSources() {
      selectedDraftDocumentIds = Array.from(draftSources.querySelectorAll(".draft-source-check:checked"))
        .map(input => Number(input.value))
        .filter(value => Number.isInteger(value) && value > 0);
    }

    function renderCatalogMatches(items) {
      if (!items || items.length === 0) {
        catalogMatches.innerHTML = '<div class="empty">Eslesen katalog kaydi bulunamadi.</div>';
        return;
      }

      catalogMatches.innerHTML = items.map(item => {
        const openAction = item.matched_document_id ? ` onclick="openDocumentFile(${item.matched_document_id})" style="cursor:pointer;"` : "";
        const matched = item.matched_document_id ? ` | Belge ID: ${item.matched_document_id}` : "";
        return `
          <article class="source-card"${openAction}>
            <div class="title">${escapeHtml(item.report_code)}</div>
            <div class="small">${escapeHtml(item.vehicle_name)} | ${escapeHtml(item.discipline)}${item.report_date ? " | " + escapeHtml(item.report_date) : ""}${matched}</div>
            <div class="excerpt">${escapeHtml(item.report_title)}</div>
            <div class="small">${escapeHtml(item.authors || "")}</div>
          </article>
        `;
      }).join("");
    }

    function updateCatalogScope(items, question = "") {
      const matches = Array.isArray(items) ? items : [];
      const matchedDocumentIds = [...new Set(matches
        .map(item => Number(item.matched_document_id))
        .filter(value => Number.isInteger(value) && value > 0)
      )];
      catalogMatchCount.textContent = String(matches.length);
      catalogDocumentCount.textContent = String(matchedDocumentIds.length);
      catalogScopeReady.textContent = matchedDocumentIds.length > 0 ? "Evet" : "Hayir";
      lastCatalogMatches = matches;
      lastCatalogQuestion = question || "";
    }

    function renderMultiDocumentDocuments(items) {
      if (!items || items.length === 0) {
        multiDocumentDocuments.innerHTML = '<div class="empty">Yuklu ve eslesen belge bulunamadi.</div>';
        return;
      }

      multiDocumentDocuments.innerHTML = items.map(item => `
        <article class="source-card" onclick="openDocumentFile(${item.document_id})" style="cursor:pointer;">
          <div class="title">${escapeHtml(item.document_title)}</div>
          <div class="small">Belge ID: ${item.document_id} | ${escapeHtml(item.file_name || "")}</div>
        </article>
      `).join("");
    }

    function renderMultiDocumentSources(items) {
      if (!items || items.length === 0) {
        multiDocumentSources.innerHTML = '<div class="empty">Kaynak pasaj bulunamadi.</div>';
        return;
      }

      multiDocumentSources.innerHTML = items.map(item => `
        <article class="source-card" onclick="openDocumentFile(${item.document_id})" style="cursor:pointer;">
          <div class="title">${escapeHtml(item.document_title)}</div>
          <div class="small">Belge ID: ${item.document_id} | Sayfa ${item.page_start}-${item.page_end}${item.section_title ? " | " + escapeHtml(item.section_title) : ""}</div>
          <div class="small">match: ${escapeHtml(item.match_type)} | combined: ${formatScore(item.combined_score)}</div>
          <div class="excerpt">${escapeHtml(item.chunk_text)}</div>
        </article>
      `).join("");
    }

    function renderMultiDocumentComparison(rows) {
      if (!rows || rows.length === 0) {
        multiDocumentComparison.innerHTML = `
          <table>
            <thead>
              <tr>
                <th>Belge</th>
                <th>Cevap</th>
                <th>Guven</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colspan="3" class="small">Karsilastirma sonuclari burada yer alacak.</td>
              </tr>
            </tbody>
          </table>
        `;
        return;
      }

      multiDocumentComparison.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>Belge</th>
              <th>Cevap</th>
              <th>Guven</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map(row => `
              <tr>
                <td>${escapeHtml(row.document_title)}</td>
                <td>${escapeHtml(row.answer)}</td>
                <td>${formatScore(row.confidence)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `;
    }

    function resetMultiDocumentWorkspace() {
      multiDocumentAnswer.textContent = "Secilen rapor grubunun icerik cevabi burada gorunecek.";
      multiDocumentMeta.textContent = "Ikinci asama soru sorulmadi.";
      renderMultiDocumentDocuments([]);
      renderMultiDocumentSources([]);
      renderMultiDocumentComparison([]);
    }

    async function runCatalogAsk() {
      const question = catalogQuestion.value.trim();
      if (!question) {
        catalogAskMeta.textContent = "Katalog sorusu icin once bir soru gir.";
        return;
      }

      catalogAskButton.disabled = true;
      const startedAt = startTimer(
        message => { catalogAskMeta.textContent = message; },
        "Katalog sorusu isleniyor..."
      );
      try {
        const response = await fetch("/ask/catalog", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ question, limit: 30 }),
        });
        const data = await response.json();
        if (!response.ok) {
          stopTimer(startedAt, message => { catalogAskMeta.textContent = message; }, data.detail || "Katalog sorusu basarisiz oldu.");
          return;
        }
        stopTimer(
          startedAt,
          message => { catalogAskMeta.textContent = message; },
          `Eslesen katalog kaydi: ${data.match_count}`
        );
        catalogAnswer.textContent = data.answer;
        updateCatalogScope(data.catalog_matches, question);
        renderCatalogMatches(data.catalog_matches);
        resetMultiDocumentWorkspace();
      } catch (error) {
        stopTimer(startedAt, message => { catalogAskMeta.textContent = message; }, `Katalog sorusu basarisiz oldu: ${error}`);
      } finally {
        catalogAskButton.disabled = false;
      }
    }

    async function runMultiDocumentAsk() {
      const question = multiDocumentQuestion.value.trim();
      if (!question) {
        multiDocumentMeta.textContent = "Icerik sorusu icin once bir soru gir.";
        return;
      }

      const documentIds = [...new Set((lastCatalogMatches || [])
        .map(item => Number(item.matched_document_id))
        .filter(value => Number.isInteger(value) && value > 0)
      )];
      const catalogScopeQuestion = lastCatalogQuestion || catalogQuestion.value.trim();
      if (documentIds.length === 0 && !catalogScopeQuestion) {
        multiDocumentMeta.textContent = "Once katalog sorusu sorup eslesen rapor grubunu olustur.";
        return;
      }

      multiDocumentAskButton.disabled = true;
      const startedAt = startTimer(
        message => { multiDocumentMeta.textContent = message; },
        "Coklu belge icerigi taraniyor..."
      );
      try {
        const response = await fetch("/ask/multi-document", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            question,
            catalog_question: catalogScopeQuestion || null,
            mode: multiDocumentMode.value,
            limit: Number(multiDocumentLimit.value) || 6,
            document_ids: documentIds,
          }),
        });
        const data = await response.json();
        if (!response.ok) {
          stopTimer(startedAt, message => { multiDocumentMeta.textContent = message; }, data.detail || "Coklu belge QA basarisiz oldu.");
          return;
        }
        stopTimer(
          startedAt,
          message => { multiDocumentMeta.textContent = message; },
          `Yuklu belge: ${data.matched_document_count} | Katalog kaydi: ${data.matched_catalog_count} | Guven: ${formatScore(data.confidence)}`
        );
        multiDocumentAnswer.textContent = data.answer;
        renderMultiDocumentDocuments(data.documents);
        renderMultiDocumentComparison(data.comparison_rows);
        renderMultiDocumentSources(data.sources);
      } catch (error) {
        stopTimer(startedAt, message => { multiDocumentMeta.textContent = message; }, `Coklu belge QA basarisiz oldu: ${error}`);
      } finally {
        multiDocumentAskButton.disabled = false;
      }
    }

    function renderGraph(data) {
      graphState = buildGraphBrowserState(data);
      renderGraphBrowser();
      graphStatus.textContent = `Kategori tarayici hazir. Kategori: ${graphState.categories.length}, belge: ${graphState.documents.length}.`;
    }

    function buildGraphBrowserState(data) {
      const nodes = data.nodes || [];
      const nodeById = new Map(nodes.map(node => [node.id, node]));
      const tagNodes = nodes.filter(node => node.type === "tag");
      const reportNodes = nodes.filter(node => node.type === "document" || node.type === "catalog");
      const tagsByReport = new Map(reportNodes.map(node => [node.id, []]));

      (data.edges || []).forEach(edge => {
        if (!tagsByReport.has(edge.source)) return;
        const tagNode = nodeById.get(edge.target);
        if (!tagNode || tagNode.type !== "tag") return;
        tagsByReport.get(edge.source).push({
          id: `${tagNode.tag_type || "tag"}::${tagNode.label}`,
          type: tagNode.tag_type || "tag",
          label: tagNode.label || "",
        });
      });

      const categories = tagNodes
        .map(node => ({
          id: `${node.tag_type || "tag"}::${node.label}`,
          type: node.tag_type || "tag",
          label: node.label || "",
          count: 0,
        }))
        .filter(category => category.label);
      const categoryById = new Map(categories.map(category => [category.id, category]));

      const documents = reportNodes.map(node => {
        const tags = tagsByReport.get(node.id) || [];
        tags.forEach(tag => {
          const category = categoryById.get(tag.id);
          if (category) category.count += 1;
        });
        const discipline = tags.find(tag => tag.type === "discipline");
        const year = tags.find(tag => tag.type === "year");
        return {
          id: node.id,
          name: node.label || "-",
          type: discipline ? discipline.label : (node.type === "document" ? "Yuklu belge" : "Katalog kaydi"),
          date: year ? year.label : "-",
          tags,
          status: node.status === "ingested" ? "Iceride" : "Iceri alinacak",
          documentId: node.document_id,
          catalogEntryId: node.catalog_entry_id,
        };
      });

      return {
        categories: categories.sort((a, b) => b.count - a.count || a.label.localeCompare(b.label)),
        documents,
        selectedCategoryId: graphState.selectedCategoryId || "all",
        search: graphState.search || "",
      };
    }

    function renderGraphBrowser() {
      const selectedExists = graphState.selectedCategoryId === "all" || graphState.categories.some(category => category.id === graphState.selectedCategoryId);
      if (!selectedExists) graphState.selectedCategoryId = "all";
      renderGraphStats();
      renderGraphTree();
      renderGraphCategoryFilter();
      renderGraphDensityChart();
      renderGraphDocuments();
    }

    function graphCategoryTypeLabel(type) {
      const labels = {
        vehicle: "Arac",
        discipline: "Analiz Tipi",
        year: "Yil",
        author: "Yazar",
        status: "Durum",
      };
      return labels[type] || "Etiket";
    }

    function filteredGraphDocuments() {
      const search = normalizeSearchText(graphState.search || "");
      return graphState.documents.filter(document => {
        const categoryMatch = graphState.selectedCategoryId === "all" || document.tags.some(tag => tag.id === graphState.selectedCategoryId);
        if (!categoryMatch) return false;
        if (!search) return true;
        const haystack = normalizeSearchText([
          document.name,
          document.type,
          document.date,
          document.status,
          document.tags.map(tag => tag.label).join(" "),
        ].join(" "));
        return haystack.includes(search);
      });
    }

    function renderGraphStats() {
      const densest = graphState.categories[0];
      graphStats.innerHTML = `
        <div class="stat-card"><div class="stat-label">Kategori</div><div class="stat-value">${graphState.categories.length}</div></div>
        <div class="stat-card"><div class="stat-label">Belge</div><div class="stat-value">${graphState.documents.length}</div></div>
        <div class="stat-card"><div class="stat-label">En Yogun</div><div class="stat-value">${densest ? escapeHtml(densest.label).slice(0, 18) : "-"}</div></div>
      `;
    }

    function renderGraphTree() {
      const groups = new Map();
      graphState.categories.forEach(category => {
        if (!groups.has(category.type)) groups.set(category.type, []);
        groups.get(category.type).push(category);
      });
      const allButton = `
        <button class="category-button ${graphState.selectedCategoryId === "all" ? "active" : ""}" type="button" data-graph-category="all">
          <span>Tum Belgeler</span><span class="count">${graphState.documents.length}</span>
        </button>
      `;
      const groupHtml = Array.from(groups.entries()).map(([type, items]) => `
        <div class="category-group">
          <div class="category-group-title">${escapeHtml(graphCategoryTypeLabel(type))}</div>
          ${items.slice(0, 30).map(category => `
            <button class="category-button ${graphState.selectedCategoryId === category.id ? "active" : ""}" type="button" data-graph-category="${escapeHtml(category.id)}">
              <span>${escapeHtml(category.label)}</span><span class="count">${category.count}</span>
            </button>
          `).join("")}
        </div>
      `).join("");
      graphTree.innerHTML = allButton + groupHtml;
      graphTree.querySelectorAll("[data-graph-category]").forEach(button => {
        button.addEventListener("click", () => {
          graphState.selectedCategoryId = button.dataset.graphCategory || "all";
          graphCategoryFilter.value = graphState.selectedCategoryId;
          renderGraphBrowser();
        });
      });
    }

    function renderGraphCategoryFilter() {
      const options = [
        '<option value="all">Tum kategoriler</option>',
        ...graphState.categories.map(category => `<option value="${escapeHtml(category.id)}">${escapeHtml(graphCategoryTypeLabel(category.type))}: ${escapeHtml(category.label)}</option>`),
      ];
      graphCategoryFilter.innerHTML = options.join("");
      graphCategoryFilter.value = graphState.selectedCategoryId;
    }

    function renderGraphDensityChart() {
      const top = graphState.categories.slice(0, 10);
      if (!top.length) {
        graphDensityChart.innerHTML = '<div class="empty">Yogunluk verisi bulunamadi.</div>';
        return;
      }
      const maxCount = Math.max(...top.map(category => category.count), 1);
      graphDensityChart.innerHTML = top.map(category => `
        <div class="density-row">
          <div class="density-label" title="${escapeHtml(category.label)}">${escapeHtml(category.label)}</div>
          <div class="density-track"><div class="density-bar" style="width:${Math.max(4, Math.round(category.count * 100 / maxCount))}%;"></div></div>
          <div>${category.count}</div>
        </div>
      `).join("");
    }

    function renderGraphDocuments() {
      const items = filteredGraphDocuments();
      if (!items.length) {
        graphDocumentsTable.innerHTML = '<tr><td colspan="5" class="small">Bu filtreyle belge bulunamadi.</td></tr>';
        return;
      }
      graphDocumentsTable.innerHTML = items.slice(0, 120).map(document => `
        <tr>
          <td><div class="doc-name">${escapeHtml(document.name)}</div><div class="small">${escapeHtml(document.documentId ? `Belge ID: ${document.documentId}` : `Katalog ID: ${document.catalogEntryId || "-"}`)}</div></td>
          <td>${escapeHtml(document.type)}</td>
          <td>${escapeHtml(document.date)}</td>
          <td><div class="doc-tags">${document.tags.slice(0, 5).map(tag => `<span class="doc-tag">${escapeHtml(tag.label)}</span>`).join("")}</div></td>
          <td><span class="status-pill ${document.status === "Iceride" ? "complete" : "not_ingested"}">${escapeHtml(document.status)}</span></td>
        </tr>
      `).join("");
    }

    async function refreshGraph() {
      graphRefreshButton.disabled = true;
      graphStatus.textContent = "Kategori verisi yukleniyor...";
      try {
        const response = await fetch("/graph/overview?limit=160");
        const data = await response.json();
        if (!response.ok) {
          graphStatus.textContent = data.detail || "Kategori verisi yuklenemedi.";
          return;
        }
        renderGraph(data);
      } catch (error) {
        graphStatus.textContent = `Kategori verisi yuklenemedi: ${error}`;
      } finally {
        graphRefreshButton.disabled = false;
      }
    }

    function focusRepOctoLibrary() {
      if (!isRepOcto || !libraryPathInput) return;
      window.setTimeout(() => libraryPathInput.focus({ preventScroll: true }), 0);
    }

    function formatLibrarySize(sizeBytes) {
      const size = Number(sizeBytes || 0);
      if (size < 1024) return `${size} B`;
      if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
      return `${(size / (1024 * 1024)).toFixed(1)} MB`;
    }

    function renderLibraryDetail(node) {
      if (!libraryDetail || !node) return;
      const modified = node.modified_at ? new Date(node.modified_at).toLocaleString("tr-TR") : "-";
      libraryDetail.innerHTML = `
        <div class="repocto-library-document-icon">${escapeHtml(node.extension || "DOC")}</div>
        <div class="repocto-library-document-copy">
          <span>SEÇİLİ DOKÜMAN</span>
          <h3>${escapeHtml(node.name || "-")}</h3>
          <dl>
            <div><dt>Tür</dt><dd>${escapeHtml(node.extension || "-")}</dd></div>
            <div><dt>Boyut</dt><dd>${escapeHtml(formatLibrarySize(node.size_bytes))}</dd></div>
            <div><dt>Güncelleme</dt><dd>${escapeHtml(modified)}</dd></div>
          </dl>
          <div class="repocto-library-document-path"><span>Dosya yolu</span><code>${escapeHtml(node.path || "-")}</code></div>
        </div>
      `;
    }

    function renderLibraryDetailEmpty(message = "Dosya türü, boyutu, güncellenme zamanı ve klasör yolu burada gösterilecek.") {
      if (!libraryDetail) return;
      libraryDetail.innerHTML = `
        <div class="repocto-library-detail-empty">
          <span>REP</span>
          <strong>Bir doküman seçin</strong>
          <p>${escapeHtml(message)}</p>
        </div>
      `;
    }

    function renderLibraryNode(node, depth = 0) {
      if (!node) return "";
      if (node.type === "document") {
        return `
          <button class="repocto-library-document" type="button" data-library-document="${encodeURIComponent(JSON.stringify(node))}" style="--library-depth:${depth}">
            <span class="repocto-library-file-icon">${escapeHtml(node.extension || "DOC")}</span>
            <span><strong>${escapeHtml(node.name || "-")}</strong><small>${escapeHtml(formatLibrarySize(node.size_bytes))}</small></span>
          </button>
        `;
      }
      const children = Array.isArray(node.children) ? node.children : [];
      return `
        <details class="repocto-library-folder" open style="--library-depth:${depth}">
          <summary><span class="repocto-library-folder-icon"></span><strong>${escapeHtml(node.name || "Klasör")}</strong><small>${children.length}</small></summary>
          <div>${children.map(child => renderLibraryNode(child, depth + 1)).join("")}</div>
        </details>
      `;
    }

    let libraryData = null;

    function filterLibraryNode(node, query, type) {
      if (!node) return null;
      if (node.type === "document") {
        const searchable = `${node.name || ""} ${node.relative_path || ""}`.toLocaleLowerCase("tr-TR");
        const queryMatches = !query || searchable.includes(query);
        const typeMatches = type === "all" || String(node.extension || "").toLowerCase() === type;
        return queryMatches && typeMatches ? { ...node } : null;
      }
      const originalChildren = Array.isArray(node.children) ? node.children : [];
      const children = originalChildren.map(child => filterLibraryNode(child, query, type)).filter(Boolean);
      const folderMatches = !query || String(node.name || "").toLocaleLowerCase("tr-TR").includes(query);
      if (folderMatches && query && type === "all") return { ...node };
      return children.length ? { ...node, children } : null;
    }

    function libraryMapNodes(node, depth = 0, output = []) {
      if (!node || output.length >= 28) return output;
      output.push({ name: node.name || "Doküman", type: node.type, extension: node.extension || "", depth });
      (Array.isArray(node.children) ? node.children : []).forEach(child => libraryMapNodes(child, depth + 1, output));
      return output;
    }

    function renderLibraryMap(tree) {
      if (!libraryMap) return;
      const nodes = libraryMapNodes(tree);
      if (!nodes.length) {
        libraryMap.innerHTML = '<div class="repocto-library-empty">Bu filtreyle harita düğümü bulunamadı.</div>';
        return;
      }
      libraryMap.innerHTML = `
        <div class="repocto-library-map-root">Kütüphane</div>
        <div class="repocto-library-map-list">
          ${nodes.slice(1).map(node => `
            <div class="repocto-library-map-node ${node.type === "document" ? "document" : "folder"}" style="--map-depth:${Math.min(node.depth, 5)}">
              <span>${node.type === "document" ? escapeHtml(node.extension || "DOC") : "KLS"}</span>
              <strong>${escapeHtml(node.name)}</strong>
            </div>
          `).join("")}
        </div>
      `;
    }

    function bindLibraryDocuments() {
      libraryTree.querySelectorAll("[data-library-document]").forEach(button => {
        button.addEventListener("click", () => {
          libraryTree.querySelectorAll("[data-library-document]").forEach(item => item.classList.remove("active"));
          button.classList.add("active");
          try {
            renderLibraryDetail(JSON.parse(decodeURIComponent(button.dataset.libraryDocument || "")));
          } catch (error) {
            libraryStatus.textContent = "Belge ayrıntıları görüntülenemedi.";
          }
        });
      });
    }

    function applyLibraryFilters() {
      if (!libraryData) return;
      const query = String(librarySearchInput?.value || "").trim().toLocaleLowerCase("tr-TR");
      const type = String(libraryTypeFilter?.value || "all").toLowerCase();
      const filteredTree = filterLibraryNode(libraryData.tree, query, type);
      libraryTree.innerHTML = filteredTree
        ? renderLibraryNode(filteredTree)
        : '<div class="repocto-library-empty">Bu filtreyle doküman bulunamadı.</div>';
      renderLibraryMap(filteredTree);
      bindLibraryDocuments();
      const firstDocument = libraryTree.querySelector("[data-library-document]");
      if (firstDocument) {
        firstDocument.click();
      } else {
        renderLibraryDetailEmpty("Bu filtreyle eşleşen bir doküman bulunamadı.");
      }
    }

    function renderLibrary(data) {
      libraryData = data;
      const documentCount = Number(data.document_count || 0);
      const directoryCount = Number(data.directory_count || 0);
      libraryTreeSummary.textContent = `${directoryCount} klasör · ${documentCount} doküman`;
      const suffix = data.truncated ? " · güvenli tarama sınırında durduruldu" : "";
      libraryStatus.textContent = `Kütüphane hazır: ${directoryCount} klasör ve ${documentCount} doküman bulundu${suffix}.`;
      applyLibraryFilters();
    }

    async function scanRepOctoLibrary() {
      if (!isRepOcto || !libraryPathInput || !libraryScanButton) return;
      const path = libraryPathInput.value.trim();
      if (!path) {
        libraryStatus.textContent = "Taramak için bir kök klasör yolu girin.";
        libraryPathInput.focus();
        return;
      }
      libraryScanButton.disabled = true;
      libraryScanButton.textContent = "Taranıyor...";
      libraryStatus.textContent = `${path} altındaki klasörler ve dokümanlar taranıyor.`;
      try {
        const response = await fetch("/library/scan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path, limit: 500 }),
        });
        const data = await response.json();
        if (!response.ok) {
          libraryStatus.textContent = data.detail || "Kütüphane taranamadı.";
          return;
        }
        renderLibrary(data);
      } catch (error) {
        libraryStatus.textContent = `Kütüphane taranamadı: ${error}`;
      } finally {
        libraryScanButton.disabled = false;
        libraryScanButton.textContent = "Kütüphaneyi Tara";
      }
    }

    function fileHrefFromPath(rawPath) {
      const backslash = String.fromCharCode(92);
      return rawPath && (rawPath.includes(backslash) || rawPath.includes("/"))
        ? `file:///${rawPath.split(backslash).join("/")}`
        : "";
    }

    function catalogLinkHtml(item) {
      const rawPath = item.source_path || item.report_code || "";
      if (!rawPath) {
        return "";
      }
      const label = rawPath.length > 42 ? `${rawPath.slice(0, 39)}...` : rawPath;
      const href = fileHrefFromPath(rawPath);
      if (!href) {
        return `<span title="${escapeHtml(rawPath)}">${escapeHtml(label)}</span>`;
      }
      return `<a href="${escapeHtml(href)}" title="${escapeHtml(rawPath)}" target="_blank">${escapeHtml(label)}</a>`;
    }

    function renderCatalogTableRows(target, items, options = {}) {
      const selectable = Boolean(options.selectable);
      const columns = selectable ? 6 : 5;
      if (!items || items.length === 0) {
        target.innerHTML = `<tr><td colspan="${columns}" class="small">Kayit bulunamadi.</td></tr>`;
        return;
      }

      target.innerHTML = items.map(item => {
        const checkbox = selectable
          ? `<td><input class="catalog-select" type="checkbox" data-catalog-entry-id="${item.id}" /></td>`
          : "";
        const statusCell = selectable ? "" : `<td>${embeddingStatusHtml(item)}</td>`;
        const previewCell = selectable
          ? `<td class="catalog-preview-cell"><button class="button secondary catalog-preview-button" type="button" data-catalog-preview="${item.id}">Raporu Gor</button></td>`
          : "";
        const openAction = item.matched_document_id
          ? ` onclick="openDocumentFile(${item.matched_document_id})" style="cursor:pointer;"`
          : "";
        const documentText = item.matched_document_id ? ` | Belge ID: ${item.matched_document_id}` : "";
        return `
          <tr${openAction}>
            ${checkbox}
            <td>
              <div class="title">${escapeHtml(item.report_code)}</div>
              <div class="small">${escapeHtml(item.report_title || "")}${documentText}</div>
            </td>
            <td>${escapeHtml(item.vehicle_name || "")}</td>
            <td>${escapeHtml(item.discipline || "")}</td>
            ${statusCell}
            <td>${catalogLinkHtml(item)}</td>
            ${previewCell}
          </tr>
        `;
      }).join("");
    }

    function catalogCandidateLogPayload(item) {
      return {
        requested_count: 1,
        ingested_count: item.status === "ingested" ? 1 : 0,
        duplicate_count: item.status === "duplicate" ? 1 : 0,
        error_count: item.status === "error" ? 1 : 0,
        items: [item],
      };
    }

    function renderCatalogCandidates(entryId, data) {
      const items = data.items || [];
      if (items.length === 0) {
        return '<div class="small">Bu katalog kaydi icin PDF/DOCX/PPTX aday dosya bulunamadi.</div>';
      }
      const rows = items.slice(0, 20).map(item => {
        const fileName = item.file_name || item.path || "";
        const href = `/catalog/${entryId}/file-preview?file_path=${encodeURIComponent(item.path || "")}`;
        const fileLabel = href
          ? `<a href="${escapeHtml(href)}" title="${escapeHtml(item.path || "")}" target="_blank">${escapeHtml(fileName)}</a>`
          : escapeHtml(fileName);
        const encodedPath = escapeHtml(encodeURIComponent(item.path || ""));
        return `
        <div class="catalog-candidate-item">
          <div>
            <div class="catalog-candidate-name">${fileLabel}</div>
            <div class="catalog-candidate-meta">
              ${escapeHtml((item.extension || "").toUpperCase())} | skor ${Number(item.score || 0)} | ${escapeHtml(item.match_method || "")}
            </div>
            <div class="catalog-candidate-meta">${escapeHtml(item.path || "")}</div>
          </div>
          <div class="actions">
            <a class="button secondary" href="${escapeHtml(href)}" target="_blank">Gor</a>
            <button
              class="button primary"
              type="button"
              data-catalog-ingest-candidate="${entryId}"
              data-file-path="${encodedPath}"
            >Bu dosyayi ice al</button>
          </div>
        </div>
      `;
      }).join("");
      const more = items.length > 20
        ? `<div class="small">... ve ${items.length - 20} aday daha var. Ilk 20 aday gosteriliyor.</div>`
        : "";
      return rows + more;
    }

    async function loadCatalogCandidates(entryId) {
      const row = document.getElementById(`catalogCandidateRow${entryId}`);
      const list = document.getElementById(`catalogCandidateList${entryId}`);
      if (!row || !list) return;
      if (!row.classList.contains("hidden") && list.dataset.loaded === "true") {
        row.classList.add("hidden");
        return;
      }

      row.classList.remove("hidden");
      list.dataset.loaded = "false";
      list.innerHTML = '<div class="small">Aday dosyalar araniyor...</div>';
      try {
        const response = await fetch(`/catalog/${entryId}/file-candidates`);
        const data = await response.json();
        setCatalogLog(data);
        if (!response.ok || data.error) {
          list.innerHTML = `<div class="small">${escapeHtml(data.detail || data.error || "Aday dosyalar alinamadi.")}</div>`;
          return;
        }
        list.innerHTML = renderCatalogCandidates(entryId, data);
        list.dataset.loaded = "true";
      } catch (error) {
        list.innerHTML = `<div class="small">Aday dosyalar alinamadi: ${escapeHtml(error)}</div>`;
      }
    }

    async function ingestCatalogCandidate(entryId, encodedFilePath) {
      const filePath = decodeURIComponent(encodedFilePath || "");
      if (!filePath) {
        setCatalogStatus("error", "Iceri almak icin aday dosya yolu bulunamadi.");
        return;
      }

      catalogTableRefreshButton.disabled = true;
      catalogSelectedIngestButton.disabled = true;
      const startedAt = startTimer(
        message => setCatalogStatus("ok", message),
        "Secilen aday dosya ice aliniyor..."
      );
      try {
        const response = await fetch("/catalog/ingest-candidate", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ catalog_entry_id: entryId, file_path: filePath }),
        });
        const data = await response.json();
        const logPayload = catalogCandidateLogPayload(data);
        setCatalogLog(logPayload);
        if (!response.ok || data.status === "error") {
          stopTimer(
            startedAt,
            message => setCatalogStatus("error", message),
            data.detail || data.error || "Secilen aday dosya ice alinamadi."
          );
          return;
        }
        stopTimer(
          startedAt,
          message => setCatalogStatus("ok", message),
          `Aday dosya ice alindi. Durum: ${data.status}. Belge ID: ${data.document_id || "-"}`
        );
        await refreshCatalogTable();
        await refreshUploadedDocuments();
      } catch (error) {
        stopTimer(startedAt, message => setCatalogStatus("error", message), `Secilen aday dosya ice alinamadi: ${error}`);
      } finally {
        catalogTableRefreshButton.disabled = false;
        catalogSelectedIngestButton.disabled = false;
      }
    }

    function embeddingStatusHtml(item) {
      const status = item.embedding_status || "not_ingested";
      const labels = {
        complete: "Embedding tamam",
        partial: "Embedding eksik",
        missing: "Embedding yok",
        not_ingested: "Ingest yok",
      };
      const countText = Number(item.chunk_count) > 0
        ? ` ${Number(item.embedding_count || 0)}/${Number(item.chunk_count || 0)}`
        : "";
      return `<span class="status-pill ${escapeHtml(status)}">${escapeHtml(labels[status] || status)}${countText}</span>`;
    }

    function renderCatalogTable(data) {
      catalogIngestedCount.textContent = String(data.ingested_count || 0);
      catalogPendingCount.textContent = String(data.pending_count || 0);
      renderCatalogTableRows(catalogIngestedTable, data.ingested || [], { selectable: false });
      renderCatalogTableRows(catalogPendingTable, data.pending || [], { selectable: true });
    }

    async function refreshCatalogTable() {
      catalogTableRefreshButton.disabled = true;
      catalogSelectedIngestButton.disabled = true;
      const startedAt = startTimer(
        message => setCatalogStatus("ok", message),
        "Katalog tablosu yenileniyor..."
      );
      try {
        const response = await fetch("/catalog/table?limit=2000");
        const data = await response.json();
        setCatalogLog(data);
        if (!response.ok) {
          stopTimer(startedAt, message => setCatalogStatus("error", message), data.detail || "Katalog tablosu alinamadi.");
          return;
        }
        renderCatalogTable(data);
        const autoLinkText = Number(data.auto_link_created_count || 0) > 0
          ? ` Yeni otomatik eslesme: ${data.auto_link_created_count}.`
          : "";
        stopTimer(
          startedAt,
          message => setCatalogStatus("ok", message),
          `Katalog tablosu hazir. Ingest edilmis: ${data.ingested_count}, edilmemis: ${data.pending_count}.${autoLinkText}`
        );
      } catch (error) {
        stopTimer(startedAt, message => setCatalogStatus("error", message), `Katalog tablosu alinamadi: ${error}`);
      } finally {
        catalogTableRefreshButton.disabled = false;
        catalogSelectedIngestButton.disabled = false;
      }
    }

    async function ingestSelectedCatalogRows() {
      const selectedIds = Array.from(document.querySelectorAll(".catalog-select:checked"))
        .map(input => Number(input.dataset.catalogEntryId))
        .filter(value => Number.isInteger(value) && value > 0);
      if (selectedIds.length === 0) {
        setCatalogStatus("error", "Ice almak icin once kirmizi tablodan rapor sec.");
        return;
      }

      catalogTableRefreshButton.disabled = true;
      catalogSelectedIngestButton.disabled = true;
      const startedAt = startTimer(
        message => setCatalogStatus("ok", message),
        `${selectedIds.length} katalog kaydi ice aliniyor...`
      );
      const controller = new AbortController();
      const timeoutId = window.setTimeout(() => controller.abort(), 60000);
      try {
        const response = await fetch("/catalog/ingest-selected", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ catalog_entry_ids: selectedIds }),
          signal: controller.signal,
        });
        window.clearTimeout(timeoutId);
        const data = await response.json();
        setCatalogLog(data);
        if (!response.ok) {
          stopTimer(startedAt, message => setCatalogStatus("error", message), data.detail || "Secilen raporlar ice alinamadi.");
          return;
        }
        stopTimer(
          startedAt,
          message => setCatalogStatus(data.error_count ? "error" : "ok", message),
          catalogIngestResultMessage(data)
        );
        await refreshCatalogTable();
        await refreshUploadedDocuments();
      } catch (error) {
        window.clearTimeout(timeoutId);
        const message = error && error.name === "AbortError"
          ? "Secilen raporlar ice alinamadi: dosya arama 60 saniyeyi asti."
          : `Secilen raporlar ice alinamadi: ${error}`;
        stopTimer(startedAt, messageText => setCatalogStatus("error", messageText), message);
      } finally {
        catalogTableRefreshButton.disabled = false;
        catalogSelectedIngestButton.disabled = false;
      }
    }

    async function openCatalogPreview(entryId) {
      if (!entryId) {
        setCatalogStatus("error", "Raporu acmak icin katalog kaydi bulunamadi.");
        return;
      }
      setCatalogStatus("ok", "Rapor dosyasi araniyor...");
      try {
        const response = await fetch(`/catalog/${entryId}/best-file-preview-info`);
        const data = await response.json();
        if (!response.ok || !data.available) {
          setCatalogStatus("error", data.detail || data.error || "Bu katalog kaydi icin acilacak rapor dosyasi bulunamadi.");
          setCatalogLog(data);
          return;
        }
        const extension = String(data.extension || "").toLowerCase();
        if (extension === ".pdf") {
          setCatalogStatus("ok", `PDF tarayicida aciliyor: ${data.file_name || "dosya"}`);
          window.open(data.preview_url, "_blank");
          return;
        }

        const openResponse = await fetch(data.open_url, { method: "POST" });
        const openData = await openResponse.json();
        if (!openResponse.ok || !openData.opened) {
          setCatalogStatus("error", openData.detail || openData.error || "Dosya Office/Explorer ile acilamadi.");
          return;
        }
        setCatalogStatus("ok", `Dosya Office/Explorer ile acildi: ${openData.file_name || data.file_name || "dosya"}`);
      } catch (error) {
        setCatalogStatus("error", `Rapor dosyasi acilamadi: ${error}`);
      }
    }

    async function rebuildCatalogEmbeddings() {
      catalogEmbeddingRebuildButton.disabled = true;
      catalogTableRefreshButton.disabled = true;
      catalogSelectedIngestButton.disabled = true;
      const startedAt = startTimer(
        message => setCatalogStatus("ok", message),
        "Embeddingler yenileniyor..."
      );
      try {
        const response = await fetch("/embeddings/rebuild", {
          method: "POST",
        });
        const data = await response.json();
        setCatalogLog(data);
        if (!response.ok) {
          stopTimer(startedAt, message => setCatalogStatus("error", message), data.detail || "Embedding yenileme basarisiz oldu.");
          return;
        }
        stopTimer(
          startedAt,
          message => setCatalogStatus("ok", message),
          `Embeddingler yenilendi. Chunk: ${data.chunks_seen}, embedding: ${data.embeddings_created}.`
        );
        await refreshCatalogTable();
      } catch (error) {
        stopTimer(startedAt, message => setCatalogStatus("error", message), `Embedding yenileme basarisiz oldu: ${error}`);
      } finally {
        catalogEmbeddingRebuildButton.disabled = false;
        catalogTableRefreshButton.disabled = false;
        catalogSelectedIngestButton.disabled = false;
      }
    }

    async function runSearch() {
      const query = searchQuery.value.trim();
      const mode = searchMode.value;
      if (!query) {
        searchMeta.textContent = "Arama yapmak icin once bir sorgu gir.";
        return;
      }

      searchButton.disabled = true;
      const startedAt = startTimer(
        message => { searchMeta.textContent = message; },
        "Arama calisiyor..."
      );
      try {
        const useQueryEnhancement = true;
        const response = await fetch(`/search?query=${encodeURIComponent(query)}&mode=${encodeURIComponent(mode)}&limit=5&search_scope=content&use_query_enhancement=${useQueryEnhancement}`);
        const data = await response.json();
        if (!response.ok) {
          stopTimer(startedAt, message => { searchMeta.textContent = message; }, data.detail || "Arama basarisiz oldu.");
          return;
        }
        const retrieval = data.retrieval || {};
        const expandedCount = Array.isArray(retrieval.expanded_queries) ? retrieval.expanded_queries.length : 0;
        const filters = retrieval.applied_filters || {};
        const activeFilters = Object.entries(filters)
          .filter(([, value]) => value !== null && value !== undefined && value !== "")
          .map(([key, value]) => `${key}: ${value}`);
        const filterText = activeFilters.length ? ` | Filtre: ${activeFilters.join(", ")}` : "";
        const catalogScope = retrieval.catalog_scope || {};
        const catalogText = ` | Katalog: ${catalogScope.match_count || 0}`;
        const scopeWarning = catalogScope.scope_status === "catalog_matches_not_ingested"
          ? " | Katalogda var ama henuz iceri alinmis dokuman yok"
          : catalogScope.scope_status === "strict_catalog_title_fallback"
            ? " | Katalog linki yok, basliktan eslesen dokumanlar gosteriliyor"
          : "";
        const enhancementText = ` | Ek sorgu: ${expandedCount}${filterText}${catalogText}${scopeWarning}`;
        stopTimer(
          startedAt,
          message => { searchMeta.textContent = message; },
          `Mod: ${data.mode} | Provider: ${data.embedding_provider} | Sonuc: ${data.results.length} | Benzer rapor: ${data.similar_documents.length}${enhancementText}`
        );
        renderResults(data.results, query);
        renderSimilar(data.similar_documents, query);
      } catch (error) {
        stopTimer(startedAt, message => { searchMeta.textContent = message; }, `Arama basarisiz oldu: ${error}`);
      } finally {
        searchButton.disabled = false;
      }
    }

    async function runAsk() {
      const question = askQuestion.value.trim();
      const mode = askMode.value;
      const documentId = Number(askDocumentId.value);
      if (!question) {
        askMeta.textContent = "Soru sormak icin once bir soru gir.";
        return;
      }

      const payload = {
        question,
        mode,
        limit: 5,
      };
      if (Number.isInteger(documentId) && documentId > 0) {
        payload.document_id = documentId;
      }

      askButton.disabled = true;
      const startedAt = startTimer(
        message => { askMeta.textContent = message; },
        "Soru isleniyor..."
      );
      try {
        const response = await fetch("/ask", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) {
          stopTimer(startedAt, message => { askMeta.textContent = message; }, data.detail || "Soru-cevap basarisiz oldu.");
          return;
        }
        const scopeText = payload.document_id ? ` | Belge ID: ${payload.document_id}` : "";
        stopTimer(
          startedAt,
          message => { askMeta.textContent = message; },
          `Mod: ${data.mode}${scopeText} | Provider: ${data.embedding_provider} | Guven: ${formatScore(data.confidence)} | Kaynak: ${data.sources.length}`
        );
        answerText.textContent = data.answer;
        renderAnswerSources(data.sources);
      } catch (error) {
        stopTimer(startedAt, message => { askMeta.textContent = message; }, `Soru-cevap basarisiz oldu: ${error}`);
      } finally {
        askButton.disabled = false;
      }
    }

    async function runDraft(detailLevel) {
      ensureDraftDefaults();
      const title = draftTitle.value.trim();
      if (!title) {
        draftMeta.textContent = "Taslak uretmek icin once rapor basligi gir.";
        return;
      }

      const payload = {
        title,
        report_type: draftType.value.trim() || "Genel Teknik Rapor",
        report_no: draftReportNo.value.trim(),
        report_date: draftReportDate.value.trim(),
        prepared_by: draftPreparedBy.value.trim(),
        requested_by: draftRequestedBy.value.trim(),
        checked_by: draftCheckedBy.value.trim(),
        classification: "GENEL / PUBLIC",
        objective: draftObjective.value.trim(),
        keywords: draftKeywords.value.trim(),
        raw_notes: draftNotes.value.trim(),
        detail_level: detailLevel,
        mode: draftMode.value,
        limit: 5,
      };
      updateSelectedDraftSources();
      if (selectedDraftDocumentIds.length > 0) {
        payload.document_ids = selectedDraftDocumentIds;
      }

      draftQuickButton.disabled = true;
      draftDetailedButton.disabled = true;
      draftCopyButton.disabled = true;
      draftPdfButton.disabled = true;
      const startedAt = startTimer(
        message => { draftMeta.textContent = message; },
        detailLevel === "quick" ? "Hizli rapor uretiliyor..." : "Detayli rapor uretiliyor..."
      );
      try {
        const response = await fetch("/draft-report", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) {
          stopTimer(startedAt, message => { draftMeta.textContent = message; }, data.detail || "Taslak olusturma basarisiz oldu.");
          return;
        }
        stopTimer(
          startedAt,
          message => { draftMeta.textContent = message; },
          `Tur: ${data.detail_level} | Arama: ${data.embedding_provider} | Yazim: ${data.generation_provider || "template"} | Anahtar kelime: ${data.refined_keywords.length} | Kaynak: ${data.sources.length}${payload.document_ids ? " | Secili belge: " + payload.document_ids.length : ""}`
        );
        draftOutput.textContent = data.draft;
        renderDraftSources(data.sources);
        lastDraftPayload = payload;
        lastDraftData = data;
        draftCopyButton.disabled = false;
        draftPdfButton.disabled = false;
      } catch (error) {
        stopTimer(startedAt, message => { draftMeta.textContent = message; }, `Taslak olusturma basarisiz oldu: ${error}`);
      } finally {
        draftQuickButton.disabled = false;
        draftDetailedButton.disabled = false;
      }
    }

    async function downloadDraftPdf(payload, title, detailLevel) {
      const response = await fetch("/draft-report/pdf", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error("PDF olusturulamadi.");
      }

      const blob = await response.blob();
      const safeTitle = String(title || "rapor")
        .replace(/[\\/:*?"<>|]+/g, "_")
        .replace(/\\s+/g, "_");
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${safeTitle}_${detailLevel}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    }

    async function downloadLatestDraftPdf() {
      if (!lastDraftPayload || !lastDraftData) {
        draftMeta.textContent = "Once bir taslak olustur.";
        return;
      }
      draftPdfButton.disabled = true;
      const startedAt = startTimer(
        message => { draftMeta.textContent = message; },
        "PDF hazirlaniyor..."
      );
      try {
        await downloadDraftPdf(lastDraftPayload, lastDraftData.title, lastDraftData.detail_level);
        stopTimer(startedAt, message => { draftMeta.textContent = message; }, "PDF indirildi.");
      } catch (error) {
        stopTimer(startedAt, message => { draftMeta.textContent = message; }, `PDF olusturulamadi: ${error}`);
      } finally {
        draftPdfButton.disabled = false;
      }
    }

    async function copyDraftText() {
      const text = draftOutput.textContent.trim();
      if (!lastDraftData || !text || text === "Taslak burada gorunecek.") {
        draftMeta.textContent = "Kopyalanacak taslak yok.";
        return;
      }
      try {
        await navigator.clipboard.writeText(text);
        draftMeta.textContent = "Taslak metin panoya kopyalandi.";
      } catch (error) {
        draftMeta.textContent = `Kopyalama basarisiz oldu: ${error}`;
      }
    }

    function fillDraftSample() {
      draftTitle.value = "BIG-E Surus Konfor Degerlendirme Raporu";
      draftType.value = "Test Degerlendirme Raporu";
      draftReportNo.value = "2025-BIG-e-NVH-01";
      draftReportDate.value = "13.01.2025";
      draftPreparedBy.value = "KEMAL DEMIR";
      draftRequestedBy.value = "ERKAN KUTLU";
      draftCheckedBy.value = "EROL CIFCI, A.SALIH YILMAZ";
      lastAutoReportNo = draftReportNo.value;
      draftMode.value = "keyword";
      draftObjective.value = "BIG-E araci icin surus konforu kapsaminda elde edilen test bulgularini ozetlemek ve onceki raporlarla uyumlu bir degerlendirme dili olusturmak.";
      draftKeywords.value = "BIG-E, surus konforu, NVH, yol verisi, titreşim, parkur";
      draftNotes.value = [
        "Farkli parkur kosullarinda surus konforu izlenmistir.",
        "Titreşim ve yol verisi bulgulari karsilastirmali olarak degerlendirilecektir.",
        "Sonucta iyilestirme alanlari ve takip aksiyonlari belirtilecektir."
      ].join("\\n");
      draftMeta.textContent = "Ornek alanlar dolduruldu. Istersen hizli veya detayli taslak uret.";
    }

    function clearDraftForm() {
      draftTitle.value = "";
      draftType.value = "";
      draftReportNo.value = "TASLAK";
      lastAutoReportNo = "TASLAK";
      draftReportDate.value = formatTodayForDraft();
      draftPreparedBy.value = "";
      draftRequestedBy.value = "";
      draftCheckedBy.value = "";
      draftMode.value = "keyword";
      draftObjective.value = "";
      draftKeywords.value = "";
      draftNotes.value = "";
      draftOutput.textContent = "Taslak burada gorunecek.";
      draftSources.innerHTML = '<div class="empty">Taslak icin kullanilan referans pasajlar burada listelenecek.</div>';
      draftMeta.textContent = "Taslak uretilmedi.";
      lastDraftPayload = null;
      lastDraftData = null;
      selectedDraftDocumentIds = [];
      draftCopyButton.disabled = true;
      draftPdfButton.disabled = true;
    }

    if (isRaporHub) {
      raporhubSidebarToggle.addEventListener("click", toggleRaporHubSidebar);
      raporhubThemeToggle.addEventListener("click", toggleRaporHubTheme);
      window.addEventListener("resize", syncRaporHubSidebar);
      chatInput.placeholder = "__BRAND_DATIVE__ mesaj yaz...";
      raporhubHomeAskButton.addEventListener("click", askFromRaporHubHome);
      raporhubHomeQuestion.addEventListener("keydown", event => {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          askFromRaporHubHome();
        }
      });
      raporhubUploadShortcut.addEventListener("click", () => openRaporHubAction("upload"));
      document.querySelectorAll("[data-home-prompt]").forEach(button => {
        button.addEventListener("click", () => {
          raporhubHomeQuestion.value = button.dataset.homePrompt || "";
          raporhubHomeQuestion.focus();
        });
      });
      document.querySelectorAll("[data-home-action]").forEach(button => {
        button.addEventListener("click", () => openRaporHubAction(button.dataset.homeAction));
      });
      raporhubRecentDocuments.addEventListener("click", event => {
        const button = event.target.closest("[data-home-document-id]");
        if (button) openDocumentFile(Number(button.dataset.homeDocumentId));
      });
    }

    picker.addEventListener("change", () => {
      selectedFiles = Array.from(picker.files || []);
      renderFiles();
      renderUploadResults([]);
      if (selectedFiles.length > 0) {
        setStatus("ok", "Raporlar secildi. Yuklemeyi baslatabilirsin.");
      }
    });

    catalogPicker.addEventListener("change", () => {
      selectedCatalogFile = (catalogPicker.files && catalogPicker.files[0]) ? catalogPicker.files[0] : null;
      if (!selectedCatalogFile) {
        catalogSummary.textContent = "Henuz katalog dosyasi secilmedi.";
        return;
      }
      catalogSummary.textContent = `Secilen katalog: ${selectedCatalogFile.name}`;
      setCatalogStatus("ok", "Katalog secildi. Istersen simdi yukleyebilirsin.");
    });

    uploadButton.addEventListener("click", async () => {
      const supported = selectedFiles.filter(file => {
        const lower = file.name.toLowerCase();
        return lower.endsWith(".pdf") || lower.endsWith(".docx") || lower.endsWith(".pptx");
      });

      if (supported.length === 0) {
        setStatus("error", "Yuklemek icin en az bir PDF, DOCX veya PPTX sec.");
        return;
      }

      const formData = new FormData();
      supported.forEach(file => formData.append("files", file, file.name));

      uploadButton.disabled = true;
      const startedAt = startTimer(
        message => setStatus("ok", message),
        supported.length === 1 ? "Rapor yukleniyor..." : "Raporlar yukleniyor..."
      );

      try {
        const response = await fetch("/ingest/batch", {
          method: "POST",
          body: formData,
        });
        const data = await response.json();
        renderUploadResults(data.items || []);
        if (response.ok) {
          stopTimer(
            startedAt,
            message => setStatus("ok", message),
            `Yukleme tamamlandi. Yeni: ${data.ingested_count}, zaten mevcut: ${data.duplicate_count}, hata: ${data.error_count}.`
          );
          if (activeModule && activeModule.dataset.moduleKey === "upload") {
            await refreshUploadedDocuments();
          }
          if (isRaporHub) {
            await refreshRaporHubOverview();
          }
        } else {
          stopTimer(startedAt, message => setStatus("error", message), data.detail || "Yukleme basarisiz oldu.");
        }
      } catch (error) {
        stopTimer(startedAt, message => setStatus("error", message), `Istek basarisiz oldu: ${error}`);
      } finally {
        uploadButton.disabled = false;
      }
    });

    catalogImportButton.addEventListener("click", async () => {
      if (!selectedCatalogFile) {
        setCatalogStatus("error", "Yuklemek icin once katalog dosyasi sec.");
        return;
      }
      const lower = selectedCatalogFile.name.toLowerCase();
      if (!(lower.endsWith(".xlsx") || lower.endsWith(".csv") || lower.endsWith(".tsv") || lower.endsWith(".txt"))) {
        setCatalogStatus("error", "Sadece XLSX, CSV, TSV veya TXT katalog dosyasi desteklenir.");
        return;
      }

      const formData = new FormData();
      formData.append("file", selectedCatalogFile, selectedCatalogFile.name);
      catalogImportButton.disabled = true;
      const startedAt = startTimer(message => setCatalogStatus("ok", message), "Katalog yukleniyor...");

      try {
        const response = await fetch("/catalog/import", {
          method: "POST",
          body: formData,
        });
        const data = await response.json();
        setCatalogLog(data);
        if (response.ok) {
          stopTimer(
            startedAt,
            message => setCatalogStatus("ok", message),
          `Katalog yuklendi. ${data.created_count} yeni kayit, ${data.updated_count || 0} guncellenen path, ${data.duplicate_count} duplicate.`
        );
          await refreshCatalogTable();
        } else {
          stopTimer(startedAt, message => setCatalogStatus("error", message), data.detail || "Katalog yukleme basarisiz oldu.");
        }
      } catch (error) {
        stopTimer(startedAt, message => setCatalogStatus("error", message), `Istek basarisiz oldu: ${error}`);
      } finally {
        catalogImportButton.disabled = false;
      }
    });

    searchButton.addEventListener("click", runSearch);
    chatSendButton.addEventListener("click", sendChatMessage);
    chatClearButton.addEventListener("click", resetChat);
    chatRetrievalVersion.addEventListener("change", () => {
      const selectedLabel = chatRetrievalVersion.value === "v1"
        ? "RAG v1 (Klasik)"
        : chatRetrievalVersion.value === "v3"
          ? "RAG v3 (Haystack)"
          : "RAG v2 (Beta)";
      resetChat();
      chatStatus.textContent = `${selectedLabel} secildi. Yeni sohbet baglami hazir.`;
    });
    chatPromptButtons.forEach(button => {
      button.addEventListener("click", () => {
        chatInput.value = button.dataset.chatPrompt || "";
        if (button.dataset.chatAssistantMode) {
          chatAssistantMode.value = button.dataset.chatAssistantMode;
        }
        syncChatInputHeight();
        chatInput.focus();
        const selectionText = button.dataset.chatSelect || "";
        const selectionStart = selectionText ? chatInput.value.indexOf(selectionText) : -1;
        if (selectionStart >= 0) {
          chatInput.setSelectionRange(selectionStart, selectionStart + selectionText.length);
        }
      });
    });
    chatInput.addEventListener("input", syncChatInputHeight);
    chatInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendChatMessage();
      }
    });
    duplicateScanButton.addEventListener("click", runDuplicateScan);
    duplicateRefreshButton.addEventListener("click", refreshDuplicates);
    duplicateCandidatesTab.addEventListener("click", () => setDuplicateWorkspace("candidates"));
    reportComparisonTab.addEventListener("click", () => setDuplicateWorkspace("comparison"));
    comparisonLeftSelect.addEventListener("change", () => {
      updateComparisonSourceMeta(comparisonLeftSelect, comparisonLeftMeta);
    });
    comparisonRightSelect.addEventListener("change", () => {
      updateComparisonSourceMeta(comparisonRightSelect, comparisonRightMeta);
    });
    comparisonLeftUpload.addEventListener("change", () => {
      uploadComparisonSource("left", comparisonLeftUpload);
    });
    comparisonRightUpload.addEventListener("change", () => {
      uploadComparisonSource("right", comparisonRightUpload);
    });
    comparisonSwapButton.addEventListener("click", swapComparisonSources);
    comparisonRunButton.addEventListener("click", runReportComparison);
    comparisonSimilaritiesTab.addEventListener("click", () => setComparisonResultView("similarities"));
    comparisonDifferencesTab.addEventListener("click", () => setComparisonResultView("differences"));
    [comparisonSimilarities, comparisonDifferences].forEach(container => {
      container.addEventListener("click", event => {
        const button = event.target.closest("[data-comparison-focus]");
        if (!button) return;
        focusComparisonPdf(button.dataset.comparisonFocus);
      });
    });
    [comparisonLeftPdfOpen, comparisonRightPdfOpen].forEach(button => {
      button.addEventListener("click", () => {
        const url = button.dataset.url;
        if (url) window.open(url, "_blank", "noopener,noreferrer");
      });
    });
    comparisonPairFullscreenOpen.addEventListener("click", () => {
      const url = comparisonPairFullscreenOpen.dataset.url;
      if (url) window.open(url, "_blank", "noopener,noreferrer");
    });
    searchQuery.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        runSearch();
      }
    });
    askButton.addEventListener("click", runAsk);
    askQuestion.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        runAsk();
      }
    });
    catalogAskButton.addEventListener("click", runCatalogAsk);
    catalogTableRefreshButton.addEventListener("click", refreshCatalogTable);
    catalogSelectedIngestButton.addEventListener("click", ingestSelectedCatalogRows);
    catalogEmbeddingRebuildButton.addEventListener("click", rebuildCatalogEmbeddings);
    catalogPendingTable.addEventListener("click", (event) => {
      const previewButton = event.target.closest("[data-catalog-preview]");
      if (previewButton) {
        event.preventDefault();
        openCatalogPreview(Number(previewButton.dataset.catalogPreview));
        return;
      }
      const ingestButton = event.target.closest("[data-catalog-ingest-candidate]");
      if (ingestButton) {
        event.preventDefault();
        ingestCatalogCandidate(
          Number(ingestButton.dataset.catalogIngestCandidate),
          ingestButton.dataset.filePath || ""
        );
      }
    });
    uploadedDocumentsRefreshButton.addEventListener("click", refreshUploadedDocuments);
    graphRefreshButton.addEventListener("click", refreshGraph);
    if (libraryScanButton) {
      libraryScanButton.addEventListener("click", scanRepOctoLibrary);
    }
    if (libraryPathInput) {
      libraryPathInput.addEventListener("keydown", event => {
        if (event.key === "Enter") {
          event.preventDefault();
          scanRepOctoLibrary();
        }
      });
    }
    if (librarySearchInput) {
      librarySearchInput.addEventListener("input", applyLibraryFilters);
    }
    if (libraryTypeFilter) {
      libraryTypeFilter.addEventListener("change", applyLibraryFilters);
    }
    if (libraryClearButton) {
      libraryClearButton.addEventListener("click", () => {
        if (librarySearchInput) librarySearchInput.value = "";
        if (libraryTypeFilter) libraryTypeFilter.value = "all";
        applyLibraryFilters();
        librarySearchInput?.focus();
      });
    }
    graphSearchInput.addEventListener("input", () => {
      graphState.search = graphSearchInput.value;
      renderGraphDocuments();
    });
    graphCategoryFilter.addEventListener("change", () => {
      graphState.selectedCategoryId = graphCategoryFilter.value || "all";
      renderGraphBrowser();
    });
    catalogQuestion.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        runCatalogAsk();
      }
    });
    multiDocumentAskButton.addEventListener("click", runMultiDocumentAsk);
    multiDocumentQuestion.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        runMultiDocumentAsk();
      }
    });
    document.querySelectorAll("[data-expand-module]").forEach(button => {
      button.addEventListener("click", () => {
        const section = button.closest(".section");
        if (section) {
          if (section.classList.contains("module-expanded")) {
            closeModule();
          } else {
            openModule(section);
          }
        }
      });
    });
    moduleFilterButtons.forEach(button => {
      button.addEventListener("click", () => {
        applyModuleFilter(button.dataset.moduleFilter);
      });
    });
    moduleModalClose.addEventListener("click", closeModule);
    moduleModal.addEventListener("click", (event) => {
      if (event.target === moduleModal) {
        closeModule();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && activeModule) {
        closeModule();
      }
    });
    draftTitle.addEventListener("input", () => {
      updateDraftReportNoAuto(false);
    });
    draftReportNo.addEventListener("input", () => {
      if (draftReportNo.value.trim() !== lastAutoReportNo) {
        lastAutoReportNo = "";
      }
    });
    draftQuickButton.addEventListener("click", () => runDraft("quick"));
    draftDetailedButton.addEventListener("click", () => runDraft("detailed"));
    draftSampleButton.addEventListener("click", fillDraftSample);
    draftClearButton.addEventListener("click", clearDraftForm);
    draftCopyButton.addEventListener("click", copyDraftText);
    draftPdfButton.addEventListener("click", downloadLatestDraftPdf);
    ensureDraftDefaults();
    updateCatalogScope([], "");
    resetMultiDocumentWorkspace();
    resetChat();
    syncRaporHubSidebar();
    syncRaporHubTheme();
    applyModuleFilter(isRaporHub ? "chat" : "upload");

    function openDocumentFile(documentId) {
      window.open(`/documents/${documentId}/file`, "_blank");
    }
    window.openDocumentFile = openDocumentFile;
  </script>
</body>
</html>
    """
    html = html.replace("__APP_VERSION__", APP_VERSION)
    html = html.replace("__MODEL_LABEL__", model_label)
    html = html.replace("__DEVICE_LABEL__", device_label)
    html = html.replace("__DEVICE_KIND__", device_kind)
    return HTMLResponse(_apply_brand_tokens(html))


@app.post("/ingest", response_model=IngestResponse)
def ingest_file(
    file: Annotated[UploadFile, File(...)],
    session: Session = Depends(get_session),
) -> IngestResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".docx", ".pptx"}:
        raise HTTPException(status_code=400, detail="Only PDF, DOCX and PPTX files are supported.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(file.file.read())

    try:
        service = IngestService(session)
        return IngestResponse(**service.ingest(temp_path, original_file_name=file.filename))
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail="Ingest failed.") from exc
    finally:
        temp_path.unlink(missing_ok=True)


@app.post("/ingest/batch", response_model=BatchIngestResponse, include_in_schema=False)
def ingest_files_batch(
    files: Annotated[list[UploadFile], File(...)],
) -> BatchIngestResponse:
    items: list[BatchIngestItemResponse] = []

    for file in files:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in {".pdf", ".docx", ".pptx"}:
            items.append(
                BatchIngestItemResponse(
                    file_name=file.filename or "",
                    status="error",
                    error="Only PDF, DOCX and PPTX files are supported.",
                )
            )
            continue

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(file.file.read())

        batch_session = SessionLocal()
        try:
            service = IngestService(batch_session)
            result = service.ingest(temp_path, original_file_name=file.filename)
            items.append(BatchIngestItemResponse(**result))
        except ValueError as exc:
            batch_session.rollback()
            items.append(
                BatchIngestItemResponse(
                    file_name=file.filename or "",
                    status="error",
                    error=str(exc),
                )
            )
        except Exception as exc:
            batch_session.rollback()
            items.append(
                BatchIngestItemResponse(
                    file_name=file.filename or "",
                    status="error",
                    error=str(exc),
                )
            )
        finally:
            batch_session.close()
            temp_path.unlink(missing_ok=True)

    ingested_count = sum(1 for item in items if item.status == "ingested")
    duplicate_count = sum(1 for item in items if item.status == "duplicate")
    error_count = sum(1 for item in items if item.status == "error")

    return BatchIngestResponse(
        total_files=len(files),
        ingested_count=ingested_count,
        duplicate_count=duplicate_count,
        error_count=error_count,
        items=items,
    )


@app.get("/search", response_model=SearchResponse)
def search(
    query: str = Query(..., min_length=2),
    limit: int = Query(5, ge=1, le=20),
    mode: Literal["keyword", "semantic", "hybrid"] = Query("hybrid"),
    search_scope: Literal["reports", "content"] = Query("content"),
    use_query_enhancement: bool = Query(False),
    use_reranking: bool = Query(False),
    session: Session = Depends(get_session),
) -> SearchResponse:
    service = SearchService(session)
    retrieval = None
    if search_scope == "reports":
        results = service.report_search(query=query, limit=limit)
        similar_documents = []
    elif use_query_enhancement or use_reranking:
        orchestrated = RetrievalOrchestrator(session, search_service=service).retrieve(
            query=query,
            mode=mode,
            limit=limit,
            use_query_enhancement=use_query_enhancement,
            use_reranking=use_reranking,
        )
        results = orchestrated["results"]
        similar_documents = orchestrated["similar_documents"]
        retrieval = orchestrated["retrieval"]
    elif mode == "keyword":
        results = service.keyword_search(query=query, limit=limit)
        similar_documents = service.similar_documents_for_results(results, limit=3)
    elif mode == "semantic":
        results = service.semantic_search(query=query, limit=limit)
        similar_documents = service.similar_documents_for_results(results, limit=3)
    else:
        results = service.hybrid_search(query=query, limit=limit)
        similar_documents = service.similar_documents_for_results(results, limit=3)

    return SearchResponse(
        mode=mode,
        semantic_available=service.semantic_available(),
        embedding_provider=service.embedding_provider_name(),
        results=results,
        similar_documents=similar_documents,
        retrieval=retrieval,
    )


@app.get("/duplicates", response_model=DuplicateReportListResponse)
def duplicate_report_pairs(
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> DuplicateReportListResponse:
    service = DuplicateDetectionService(session)
    return DuplicateReportListResponse(**service.list_pairs(limit=limit))


@app.post("/duplicates/scan", response_model=DuplicateReportScanResponse)
def scan_duplicate_report_pairs(
    threshold: float = Query(0.90, ge=0.1, le=1.0),
    dry_run: bool = Query(False),
    session: Session = Depends(get_session),
) -> DuplicateReportScanResponse:
    service = DuplicateDetectionService(session)
    return DuplicateReportScanResponse(**service.scan(threshold=threshold, dry_run=dry_run))


@app.post("/report-comparison/upload", response_model=ReportComparisonUploadResponse)
def upload_report_for_comparison(
    file: Annotated[UploadFile, File(...)],
    session: Session = Depends(get_session),
) -> ReportComparisonUploadResponse:
    try:
        service = ReportComparisonService(session)
        result = service.store_temporary_upload(file.filename or "report", file.file.read())
        return ReportComparisonUploadResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Temporary report comparison upload failed.")
        raise HTTPException(status_code=500, detail="Gecici rapor yuklenemedi.") from exc


@app.post("/report-comparison", response_model=ReportComparisonResponse)
def compare_reports(
    payload: ReportComparisonRequest,
    session: Session = Depends(get_session),
) -> ReportComparisonResponse:
    left = payload.left.model_dump()
    right = payload.right.model_dump()
    for source in (left, right):
        selected_count = int(bool(source.get("document_id"))) + int(bool(source.get("upload_token")))
        if selected_count != 1:
            raise HTTPException(status_code=400, detail="Her taraf icin tek bir rapor kaynagi sec.")
    try:
        service = ReportComparisonService(session)
        return ReportComparisonResponse(
            **service.compare(left, right, use_llm=payload.use_llm)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Report comparison failed.")
        raise HTTPException(status_code=500, detail="Rapor karsilastirmasi tamamlanamadi.") from exc


@app.get("/report-comparison/{comparison_id}/pdf/{side}")
def comparison_highlighted_pdf(
    comparison_id: str,
    side: Literal["left", "right"],
) -> FileResponse:
    try:
        pdf_path = resolve_comparison_pdf_path(comparison_id, side)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(
        path=pdf_path,
        filename=f"karsilastirma-{side}.pdf",
        media_type="application/pdf",
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@app.get("/report-comparison/{comparison_id}/viewer", response_class=HTMLResponse)
def comparison_fullscreen_viewer(comparison_id: str) -> HTMLResponse:
    try:
        resolve_comparison_pdf_path(comparison_id, "left")
        resolve_comparison_pdf_path(comparison_id, "right")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    viewer_html = """
<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Renkli Rapor Karsilastirma</title>
  <style>
    :root {
      --text: #261b1d;
      --muted: #715f63;
      --line: #d8c8cb;
      --accent: #c22437;
      --surface: #f2edef;
    }
    * { box-sizing: border-box; }
    html, body {
      width: 100%;
      height: 100%;
      margin: 0;
      overflow: hidden;
      background: var(--surface);
      color: var(--text);
      font-family: "Segoe UI", Tahoma, sans-serif;
    }
    .viewer-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      height: 62px;
      padding: 9px 16px;
      border-bottom: 1px solid var(--line);
      background: white;
    }
    .viewer-title {
      min-width: 0;
    }
    .viewer-title strong {
      display: block;
      font-size: 16px;
    }
    .viewer-title span {
      display: block;
      margin-top: 2px;
      color: var(--muted);
      font-size: 12px;
    }
    .fullscreen-button {
      min-height: 38px;
      border: 1px solid var(--accent);
      background: var(--accent);
      color: white;
      cursor: pointer;
      font-size: 13px;
      font-weight: 800;
      padding: 8px 13px;
      white-space: nowrap;
    }
    .fullscreen-button:hover {
      background: #9f1d2c;
    }
    .viewer-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      height: calc(100vh - 62px);
    }
    .pdf-pane {
      display: grid;
      grid-template-rows: 36px minmax(0, 1fr);
      min-width: 0;
      min-height: 0;
      border-right: 1px solid var(--line);
      background: #ded7d9;
    }
    .pdf-pane:last-child {
      border-right: 0;
    }
    .pdf-label {
      display: flex;
      align-items: center;
      padding: 0 12px;
      border-bottom: 1px solid var(--line);
      background: #fbf9fa;
      color: var(--accent);
      font-size: 12px;
      font-weight: 900;
    }
    .pdf-frame {
      display: block;
      width: 100%;
      height: 100%;
      border: 0;
      background: #d8d1d3;
    }
    @media (max-width: 900px) {
      html, body {
        overflow: auto;
      }
      .viewer-bar {
        height: auto;
        min-height: 62px;
      }
      .viewer-title span {
        display: none;
      }
      .viewer-grid {
        grid-template-columns: 1fr;
        height: auto;
      }
      .pdf-pane {
        height: calc(100vh - 62px);
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }
    }
  </style>
</head>
<body>
  <header class="viewer-bar">
    <div class="viewer-title">
      <strong>Renkli Rapor Karsilastirma</strong>
      <span>Eslesen pasajlar iki PDF'de ayni renklerle isaretlidir.</span>
    </div>
    <button class="fullscreen-button" id="browserFullscreenButton" type="button">Tarayici Tam Ekran</button>
  </header>
  <main class="viewer-grid">
    <section class="pdf-pane">
      <div class="pdf-label">Rapor A</div>
      <iframe class="pdf-frame" title="Rapor A renkli tam PDF" src="/report-comparison/__COMPARISON_ID__/pdf/left#page=1&zoom=page-width"></iframe>
    </section>
    <section class="pdf-pane">
      <div class="pdf-label">Rapor B</div>
      <iframe class="pdf-frame" title="Rapor B renkli tam PDF" src="/report-comparison/__COMPARISON_ID__/pdf/right#page=1&zoom=page-width"></iframe>
    </section>
  </main>
  <script>
    const fullscreenButton = document.getElementById("browserFullscreenButton");
    fullscreenButton.addEventListener("click", async () => {
      try {
        if (document.fullscreenElement) {
          await document.exitFullscreen();
        } else {
          await document.documentElement.requestFullscreen();
        }
      } catch (error) {
        fullscreenButton.textContent = "Tam Ekran Kullanilamiyor";
      }
    });
    document.addEventListener("fullscreenchange", () => {
      fullscreenButton.textContent = document.fullscreenElement
        ? "Tam Ekrandan Cik"
        : "Tarayici Tam Ekran";
    });
  </script>
</body>
</html>
    """.replace("__COMPARISON_ID__", comparison_id)
    return HTMLResponse(
        viewer_html,
        headers={"Cache-Control": "private, no-store"},
    )


@app.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    session: Session = Depends(get_session),
) -> AskResponse:
    service = QAService(session)
    return AskResponse(
        **service.answer_question(
            payload.question,
            mode=payload.mode,
            limit=payload.limit,
            document_id=payload.document_id,
            use_llm_answer=payload.use_llm_answer,
        )
    )


@app.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    session: Session = Depends(get_session),
) -> ChatResponse:
    history = [
        item.model_dump()
        for item in payload.history[-8:]
        if item.content.strip()
    ]
    if (
        history
        and history[-1]["role"] == "user"
        and history[-1]["content"].strip() == payload.message.strip()
    ):
        history.pop()

    if payload.assistant_mode == "general" or (
        payload.assistant_mode == "auto" and _is_general_chat_message(payload.message)
    ):
        answer_text, provider_name, confidence = _chat_general_answer(payload.message, history)
        history.append({"role": "user", "content": payload.message})
        history.append({"role": "assistant", "content": answer_text})
        return ChatResponse(
            message=payload.message,
            answer=answer_text,
            answer_found=True,
            confidence=confidence,
            embedding_provider=provider_name,
            retrieval_provider=None,
            retrieval_version=payload.retrieval_version,
            retrieval_used=False,
            sources=[],
            history=history[-10:],
        )

    service = DocumentIntelligenceService(session)
    try:
        answer = service.answer_question(
            payload.message,
            history=history,
            mode=payload.mode,
            limit=payload.limit,
            document_id=payload.document_id,
            context_document_ids=payload.document_ids,
            retrieval_version=payload.retrieval_version,
        )
    except (HaystackUnavailableError, HaystackRetrievalError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    history.append({"role": "user", "content": payload.message})
    history.append({"role": "assistant", "content": answer["answer"]})
    return ChatResponse(
        message=payload.message,
        answer=answer["answer"],
        answer_found=answer["answer_found"],
        confidence=answer["confidence"],
        embedding_provider=answer["embedding_provider"],
        retrieval_provider=service.retrieval_provider_name(payload.retrieval_version),
        retrieval_version=payload.retrieval_version,
        retrieval_used=True,
        sources=answer["sources"],
        history=history[-10:],
    )


def _is_general_chat_message(message: str) -> bool:
    normalized = _fold_chat_text(message)
    if not normalized:
        return False
    if _is_application_meta_message(normalized):
        return True
    if _is_report_focused_message(normalized):
        return False
    if _is_simple_math_message(message):
        return True

    general_phrases = {
        "kendinden bahset",
        "sen kimsin",
        "kimsin",
        "ne yapabilirsin",
        "ne ise yararsin",
        "amacın ne",
        "amacin ne",
        "bu sistem nedir",
        "kendini tanit",
        "adam misin",
        "insan misin",
        "robot musun",
        "gercek misin",
        "kendini tanıt",
    }
    if any(phrase in normalized for phrase in general_phrases):
        return True

    if _is_chat_small_talk(message):
        return True

    return True


def _is_application_meta_message(normalized: str) -> bool:
    identity_phrases = {
        "kendinden bahset",
        "kendini tanit",
        "sen kimsin",
        "bu uygulama ne yapar",
        "uygulama nedir",
        "bu sistem nedir",
    }
    if any(phrase in normalized for phrase in identity_phrases):
        return True

    brand_names = {
        _fold_chat_text(APP_BRAND.display_name),
        "raporhub",
        "repocto",
        "smartcae ai",
        "big agent",
    }
    capability_phrases = {"ne yapar", "ne ise yarar", "ne yapabilir"}
    return any(name and name in normalized for name in brand_names) and any(
        phrase in normalized for phrase in capability_phrases
    )


def _is_simple_math_message(message: str) -> bool:
    stripped = message.strip()
    if not stripped:
        return False
    if re.fullmatch(r"[0-9\s+\-*/().,=]+", stripped) and re.search(r"[+\-*/]", stripped):
        return True
    normalized = _fold_chat_text(message)
    math_words = {"arti", "eksi", "carpi", "bolu", "kac", "kactir", "hesapla"}
    return any(word in normalized.split() for word in math_words) and bool(re.search(r"\d", normalized))


def _is_chat_small_talk(message: str) -> bool:
    normalized = _fold_chat_text(message)
    if not normalized:
        return False
    if _is_report_focused_message(normalized):
        return False
    small_talk_phrases = {
        "naber",
        "nasilsin",
        "nasil gidiyor",
        "selam",
        "merhaba",
        "hello",
        "hi",
        "iyi misin",
        "ne haber",
        "gunaydin",
        "iyi aksamlar",
    }
    return normalized in small_talk_phrases or (
        len(normalized.split()) <= 3
        and any(phrase in normalized for phrase in small_talk_phrases)
    )


def _is_report_focused_message(normalized: str) -> bool:
    report_terms = {
        "rapor",
        "analiz",
        "test",
        "katalog",
        "belge",
        "dokuman",
        "doküman",
        "titreşim",
        "titresim",
        "konfor",
        "parkur",
        "sensor",
        "sensör",
        "nvh",
        "dur",
        "safe",
        "tase",
        "bige",
        "big e",
        "citi",
        "citibus",
        "goupil",
        "tasarim",
        "dayanikli",
        "gerilme",
        "stres",
        "karsilastir",
        "kiyasla",
        "ozetle",
        "ana konu",
        "kapsam",
        "sonuc",
    }
    if any(term in normalized for term in report_terms):
        return True
    return bool(re.search(r"\b20\d{2}[a-z0-9-]*-[a-z0-9-]+", normalized))


def _chat_general_answer(message: str, history: list[dict] | None = None) -> tuple[str, str, float]:
    normalized = _fold_chat_text(message)
    if any(phrase in normalized for phrase in ("adam misin", "insan misin", "robot musun", "gercek misin")):
        return (
            f"Ben insan degilim; {APP_BRAND.display_name} icinde calisan yapay zeka destekli bir rapor asistaniyim. "
            "Genel sohbet edebilirim, ama asil isim raporlar ve teknik dokumanlar uzerinden yardim etmek.",
            "chat-direct",
            1.0,
        )
    if any(phrase in normalized for phrase in ("kendinden bahset", "sen kimsin", "kimsin", "kendini tanit", "kendini tanıt")):
        return (
            f"Ben {APP_BRAND.display_name} icindeki rapor asistaniyim. PDF, DOCX ve PPTX raporlarindan kaynakli cevap bulmak, "
            "benzer raporlari gostermek, katalog kayitlariyla icerdeki dokumanlari eslestirmek ve mukerrer rapor "
            "adaylarini incelemek icin tasarlandim. Genel sohbet edebilirim ama asil gucum raporlar uzerinden kaynakli cevap vermek.",
            "chat-direct",
            1.0,
        )
    if (
        "ne yapabilirsin" in normalized
        or "ne ise yararsin" in normalized
        or "amacin ne" in normalized
        or "big agent ne yapar" in normalized
        or "smartcae ai ne yapar" in normalized
        or "raporhub ne yapar" in normalized
        or "repocto ne yapar" in normalized
        or "bu uygulama ne yapar" in normalized
        or "sistem ne yapar" in normalized
    ):
        return (
            f"{APP_BRAND.display_name}; muhendislik raporlarini yukleme, katalogdan ice aktarma, icerik ve anlamsal "
            "arama, kaynakli soru-cevap, rapor karsilastirma, mukerrer tespiti, tablo/sekil numaralandirma kontrolu "
            "ve rapor taslagi olusturma islemlerini tek yerde yapar.",
            "chat-direct",
            1.0,
        )
    if "nasil" in normalized or "iyi misin" in normalized:
        return "Iyiyim, hazirim. Raporlar uzerinden bir sey sormak istersen beraber bakalim.", "chat-direct", 1.0
    result = GeneralChatService().answer(message, history or [])
    if result is not None:
        return result.answer, result.provider_name, result.confidence
    return "Buradayim, hazirim. Bana rapor, test, analiz veya katalogla ilgili bir soru sorabilirsin.", "chat-direct", 1.0


def _fold_chat_text(message: str) -> str:
    translated = message.casefold().translate(
        str.maketrans(
            {
                "\u0131": "i",
                "\u011f": "g",
                "\u00fc": "u",
                "\u015f": "s",
                "\u00f6": "o",
                "\u00e7": "c",
                "\u0130": "i",
            }
        )
    )
    return re.sub(r"[^a-z0-9\s]+", " ", translated).strip()


@app.post("/catalog/import", response_model=CatalogImportResponse)
def import_catalog(
    file: Annotated[UploadFile, File(...)],
    session: Session = Depends(get_session),
) -> CatalogImportResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".xlsx", ".csv", ".tsv", ".txt"}:
        raise HTTPException(status_code=400, detail="Only XLSX, CSV, TSV and TXT catalog files are supported.")

    try:
        service = CatalogService(session)
        return CatalogImportResponse(**service.import_bytes(file.filename or "catalog", file.file.read()))
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail="Catalog import failed.") from exc


@app.get("/catalog/search", response_model=CatalogSearchResponse)
def search_catalog(
    query: str = Query("", min_length=0),
    vehicle: str = Query("", min_length=0),
    discipline: str = Query("", min_length=0),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> CatalogSearchResponse:
    service = CatalogService(session)
    return CatalogSearchResponse(results=service.search(query=query, vehicle=vehicle, discipline=discipline, limit=limit))


@app.post("/ask/catalog", response_model=CatalogAskResponse)
def ask_catalog(
    payload: CatalogAskRequest,
    session: Session = Depends(get_session),
) -> CatalogAskResponse:
    service = CatalogService(session)
    return CatalogAskResponse(**service.answer_catalog_question(payload.question, limit=payload.limit))


@app.post("/ask/multi-document", response_model=MultiDocumentAskResponse)
def ask_multi_document(
    payload: MultiDocumentAskRequest,
    session: Session = Depends(get_session),
) -> MultiDocumentAskResponse:
    service = MultiDocumentQAService(session)
    return MultiDocumentAskResponse(
        **service.answer_question(
            payload.question,
            mode=payload.mode,
            limit=payload.limit,
            document_ids=payload.document_ids,
            catalog_question=payload.catalog_question,
        )
    )


@app.post("/catalog/ingest-sample", response_model=CatalogSampleIngestResponse)
def ingest_catalog_sample(
    per_discipline: int = Query(2, ge=1, le=10),
    dry_run: bool = Query(True),
    scan_limit_per_discipline: int = Query(25, ge=1, le=500),
    session: Session = Depends(get_session),
) -> CatalogSampleIngestResponse:
    service = CatalogIngestService(session)
    return CatalogSampleIngestResponse(
        **service.ingest_sample_per_discipline(
            per_discipline=per_discipline,
            dry_run=dry_run,
            scan_limit_per_discipline=scan_limit_per_discipline,
        )
    )


@app.get("/catalog/table", response_model=CatalogTableResponse)
def catalog_table(
    limit: int = Query(2000, ge=20, le=5000),
    session: Session = Depends(get_session),
) -> CatalogTableResponse:
    service = CatalogIngestService(session)
    return CatalogTableResponse(**service.catalog_table(limit=limit))


@app.post("/catalog/reconcile-documents")
def reconcile_catalog_documents(
    dry_run: bool = Query(False),
    session: Session = Depends(get_session),
) -> dict:
    service = CatalogIngestService(session)
    return service.reconcile_catalog_document_links(dry_run=dry_run)


@app.get("/catalog/{catalog_entry_id}/file-candidates")
def catalog_file_candidates(
    catalog_entry_id: int,
    session: Session = Depends(get_session),
) -> dict:
    service = CatalogIngestService(session)
    return service.file_candidates_for_entry(catalog_entry_id)


@app.get("/catalog/{catalog_entry_id}/file-preview")
def catalog_file_preview(
    catalog_entry_id: int,
    file_path: str = Query(..., min_length=1),
    session: Session = Depends(get_session),
) -> FileResponse:
    service = CatalogIngestService(session)
    preview_path = service.candidate_preview_path(catalog_entry_id, file_path)
    return _catalog_preview_response(preview_path)


@app.get("/catalog/{catalog_entry_id}/best-file-preview")
def catalog_best_file_preview(
    catalog_entry_id: int,
    session: Session = Depends(get_session),
) -> FileResponse:
    service = CatalogIngestService(session)
    preview_path = service.best_candidate_preview_path(catalog_entry_id)
    return _catalog_preview_response(preview_path)


@app.get("/catalog/{catalog_entry_id}/best-file-preview-info")
def catalog_best_file_preview_info(
    catalog_entry_id: int,
    session: Session = Depends(get_session),
) -> dict:
    service = CatalogIngestService(session)
    preview_path = service.best_candidate_preview_path(catalog_entry_id)
    if preview_path is None or not preview_path.exists():
        if not service.has_accessible_report_root():
            return {
                "available": False,
                "catalog_entry_id": catalog_entry_id,
                "error": "Sunucu RAPORLAR kok klasorune erisemiyor. Uygulamayi V: surucusunu veya \\\\isufile02\\argevalidasyon$ paylasimini goren Windows oturumundan baslatmak gerekir.",
            }
        return {
            "available": False,
            "catalog_entry_id": catalog_entry_id,
            "error": "Bu katalog kaydi icin RAPORLAR\\<arac>\\<rapor kodu> klasoru veya bu klasorun icinde PDF/DOCX/PPTX bulunamadi.",
        }
    return {
        "available": True,
        "catalog_entry_id": catalog_entry_id,
        "file_name": preview_path.name,
        "extension": preview_path.suffix.lower(),
        "source_path": str(preview_path),
        "preview_url": f"/catalog/{catalog_entry_id}/best-file-preview",
        "open_url": f"/catalog/{catalog_entry_id}/open-best-file",
    }


def _catalog_preview_response(preview_path: Path | None) -> FileResponse:
    if preview_path is None or not preview_path.exists():
        raise HTTPException(status_code=404, detail="Report file could not be opened.")
    media_type = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }.get(preview_path.suffix.lower(), "application/octet-stream")
    headers = {}
    if preview_path.suffix.lower() == ".pdf":
        headers["Content-Disposition"] = f'inline; filename="{_safe_download_name(preview_path.name, "report.pdf")}"'
        return FileResponse(path=preview_path, media_type=media_type, headers=headers)
    return FileResponse(path=preview_path, media_type=media_type, filename=preview_path.name)


@app.post("/catalog/{catalog_entry_id}/open-best-file")
def catalog_open_best_file(
    catalog_entry_id: int,
    session: Session = Depends(get_session),
) -> dict:
    service = CatalogIngestService(session)
    preview_path = service.best_candidate_preview_path(catalog_entry_id)
    if preview_path is None or not preview_path.exists():
        raise HTTPException(status_code=404, detail="Report file could not be opened.")
    if preview_path.suffix.lower() == ".pdf":
        return {
            "opened": False,
            "catalog_entry_id": catalog_entry_id,
            "file_name": preview_path.name,
            "error": "PDF files are opened in the browser preview.",
        }
    try:
        os.startfile(str(preview_path))  # type: ignore[attr-defined]
    except AttributeError as exc:
        raise HTTPException(status_code=501, detail="Local file opening is only supported on Windows.") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Local file could not be opened: {exc}") from exc
    return {
        "opened": True,
        "catalog_entry_id": catalog_entry_id,
        "file_name": preview_path.name,
        "source_path": str(preview_path),
    }


@app.post("/catalog/ingest-candidate", response_model=CatalogSampleIngestItemResponse)
def ingest_catalog_candidate(
    payload: CatalogCandidateIngestRequest,
    session: Session = Depends(get_session),
) -> CatalogSampleIngestItemResponse:
    service = CatalogIngestService(session)
    return CatalogSampleIngestItemResponse(
        **service.ingest_catalog_candidate(payload.catalog_entry_id, payload.file_path)
    )


@app.get("/graph/overview")
def graph_overview(
    limit: int = Query(160, ge=20, le=300),
    session: Session = Depends(get_session),
) -> dict:
    service = GraphService(session)
    return service.overview(limit=limit)


@app.post("/library/scan")
def scan_library(payload: LibraryScanRequest) -> dict:
    if APP_VARIANT != "repocto":
        raise HTTPException(status_code=404, detail="Kütüphane yalnızca RepOcto'da kullanılabilir.")
    try:
        return LibraryService(REPOCTO_LIBRARY_ROOTS).scan(payload.path, limit=payload.limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Kök klasör okunamadı.") from exc


@app.post("/catalog/ingest-selected", response_model=CatalogSelectedIngestResponse)
def ingest_selected_catalog_entries(
    payload: CatalogSelectedIngestRequest,
    session: Session = Depends(get_session),
) -> CatalogSelectedIngestResponse:
    service = CatalogIngestService(session)
    return CatalogSelectedIngestResponse(**service.ingest_catalog_entries(payload.catalog_entry_ids))


@app.post("/draft-report", response_model=DraftReportResponse)
def draft_report(
    payload: DraftReportRequest,
    session: Session = Depends(get_session),
) -> DraftReportResponse:
    service = ReportWriterService(session)
    return DraftReportResponse(
        **service.build_draft(
            title=payload.title,
            report_type=payload.report_type,
            report_no=payload.report_no,
            report_date=payload.report_date,
            prepared_by=payload.prepared_by,
            checked_by=payload.checked_by,
            requested_by=payload.requested_by,
            classification=payload.classification,
            objective=payload.objective,
            keywords=payload.keywords,
            raw_notes=payload.raw_notes,
            detail_level=payload.detail_level,
            mode=payload.mode,
            limit=payload.limit,
            document_ids=payload.document_ids,
        )
    )


@app.post("/draft-report/pdf")
def draft_report_pdf(
    payload: DraftReportRequest,
    session: Session = Depends(get_session),
) -> Response:
    service = ReportWriterService(session)
    draft_payload = service.build_draft(
        title=payload.title,
        report_type=payload.report_type,
        report_no=payload.report_no,
        report_date=payload.report_date,
        prepared_by=payload.prepared_by,
        checked_by=payload.checked_by,
        requested_by=payload.requested_by,
        classification=payload.classification,
        objective=payload.objective,
        keywords=payload.keywords,
        raw_notes=payload.raw_notes,
        detail_level=payload.detail_level,
        mode=payload.mode,
        limit=payload.limit,
        document_ids=payload.document_ids,
    )
    pdf_bytes = service.build_pdf_bytes(draft_payload)
    safe_title = _safe_download_name(draft_payload["title"])
    filename = f"{safe_title}_{payload.detail_level}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/documents/list")
def list_documents(
    limit: Annotated[int, Query(ge=1, le=500)] = 300,
    session: Session = Depends(get_session),
) -> dict:
    total = session.scalar(select(func.count(Document.id))) or 0
    rows = session.execute(
        select(
            Document,
            func.count(DocumentChunk.id).label("chunk_count"),
            func.count(ChunkEmbedding.chunk_id).label("embedding_count"),
        )
        .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
        .outerjoin(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc(), Document.id.desc())
        .limit(limit)
    ).all()
    return {
        "total": int(total),
        "items": [
            {
                "document_id": document.id,
                "title": document.title,
                "file_name": document.file_name,
                "file_type": document.file_type,
                "created_at": document.created_at.strftime("%Y-%m-%d %H:%M") if document.created_at else "",
                "chunk_count": int(chunk_count or 0),
                "embedding_count": int(embedding_count or 0),
            }
            for document, chunk_count, embedding_count in rows
        ],
    }


@app.get("/documents/{document_id}", response_class=HTMLResponse)
def document_detail(document_id: int, session: Session = Depends(get_session)) -> HTMLResponse:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    pages = session.scalars(
        select(DocumentPage).where(DocumentPage.document_id == document_id).order_by(DocumentPage.page_number.asc())
    ).all()
    page_sections = []
    for page in pages:
        page_sections.append(
            f"""
            <section class="page-card">
              <div class="page-head">
                <div class="page-title">Sayfa {page.page_number}</div>
                <div class="page-meta">{escape(page.section_title or "Bolum bilgisi yok")}</div>
              </div>
              <pre>{escape(page.clean_text)}</pre>
            </section>
            """
        )

    file_exists = resolve_document_file_path(document.file_path) is not None
    open_file_button = (
        f'<a class="button primary" href="/documents/{document_id}/file" target="_blank">Orijinal Dosyayi Ac</a>'
        if file_exists
        else '<span class="button muted">Orijinal dosya bulunamadi</span>'
    )

    return HTMLResponse(
        f"""
<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(document.title)}</title>
  <style>
    body {{
      margin: 0;
      font-family: "Segoe UI", Tahoma, sans-serif;
      background: #f4f7fb;
      color: #15202b;
    }}
    .wrap {{
      max-width: 1000px;
      margin: 32px auto;
      padding: 0 20px 40px;
    }}
    .hero {{
      background: white;
      border: 1px solid #d8dee7;
      border-radius: 18px;
      box-shadow: 0 12px 32px rgba(18, 38, 63, 0.08);
      padding: 24px;
      margin-bottom: 18px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 30px;
    }}
    .meta {{
      color: #5d6b79;
      font-size: 14px;
      line-height: 1.5;
      margin-bottom: 14px;
    }}
    .button {{
      display: inline-flex;
      align-items: center;
      text-decoration: none;
      border-radius: 12px;
      padding: 10px 14px;
      font-weight: 700;
      font-size: 14px;
      border: 1px solid #d8dee7;
    }}
    .primary {{
      background: #0b6bcb;
      color: white;
      border-color: #0b6bcb;
    }}
    .muted {{
      background: #edf4fb;
      color: #5d6b79;
    }}
    .pages {{
      display: grid;
      gap: 16px;
    }}
    .page-card {{
      background: white;
      border: 1px solid #d8dee7;
      border-radius: 16px;
      padding: 18px;
      box-shadow: 0 10px 26px rgba(18, 38, 63, 0.05);
    }}
    .page-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 10px;
    }}
    .page-title {{
      font-size: 18px;
      font-weight: 800;
    }}
    .page-meta {{
      color: #5d6b79;
      font-size: 13px;
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: "Segoe UI", Tahoma, sans-serif;
      font-size: 15px;
      line-height: 1.6;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <h1>{escape(document.title)}</h1>
      <div class="meta">Dosya: {escape(document.file_name)} | Tur: {escape(document.file_type)} | ID: {document.id}</div>
      {open_file_button}
    </div>
    <div class="pages">
      {''.join(page_sections) if page_sections else '<div class="hero">Bu belge icin sayfa verisi bulunamadi.</div>'}
    </div>
  </div>
</body>
</html>
        """
    )


@app.get("/documents/{document_id}/file")
def document_file(document_id: int, session: Session = Depends(get_session)):
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    file_path = resolve_document_file_path(document.file_path)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Original file not found.")

    media_type = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }.get(document.file_type, "application/octet-stream")
    return FileResponse(
        path=file_path,
        filename=document.file_name,
        media_type=media_type,
        content_disposition_type="inline",
    )


@app.get("/storage/check", response_model=StorageCheckResponse)
def storage_check(session: Session = Depends(get_session)) -> StorageCheckResponse:
    service = StorageService(session)
    return StorageCheckResponse(**service.check_storage())


@app.post("/embeddings/rebuild", response_model=ReindexEmbeddingsResponse)
def rebuild_embeddings(session: Session = Depends(get_session)) -> ReindexEmbeddingsResponse:
    service = EmbeddingReindexService(session)
    result = service.rebuild()
    HaystackRetrievalService.clear_cache()
    return ReindexEmbeddingsResponse(**result)
