from __future__ import annotations

import base64
from contextlib import asynccontextmanager
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

import httpx
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
    CatiaSkillApproveRequest,
    CatiaSkillChatRequest,
    CatiaSkillChatResponse,
    ChatRequest,
    ChatResponse,
    DraftReportRequest,
    DraftReportResponse,
    DuplicateReportListResponse,
    DuplicateReportScanResponse,
    HealthResponse,
    IngestResponse,
    JobListResponse,
    JobStatusResponse,
    LibraryScanRequest,
    MultiDocumentAskRequest,
    MultiDocumentAskResponse,
    ReindexEmbeddingsResponse,
    ReportComparisonMultiRequest,
    ReportComparisonMultiResponse,
    ReportComparisonRequest,
    ReportComparisonResponse,
    ReportComparisonUploadResponse,
    ReportReviewDecisionRequest,
    ReportReviewDecisionResponse,
    SearchResponse,
    StorageCheckResponse,
)
from .text.normalize import normalize_search_text
from .db.session import SessionLocal, get_session, init_db
from .db.models import ChunkEmbedding, Document, DocumentChunk, DocumentPage
from .services.embedding_reindex_service import EmbeddingReindexService
from .services.embedding_service import build_embedding_service
from .services.catalog_ingest_service import CatalogIngestService
from .services.catalog_service import CatalogService
from .services.catia_skill_service import (
    CatiaSkillBusyError,
    CatiaSkillLLMError,
    CatiaSkillUnavailableError,
    get_catia_skill_service,
)
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
from .services.job_manager import JobContext, get_job_manager
from .services.library_service import LibraryService
from .services.multi_document_qa_service import MultiDocumentQAService
from .services.qa_service import QAService
from .services.report_comparison_service import (
    ReportComparisonService,
    resolve_comparison_pdf_path,
)
from .services.report_review_service import ReportReviewService
from .services.report_review_export_service import ReportReviewExportService
from .services.report_writer_service import ReportWriterService
from .services.retrieval_orchestrator import RetrievalOrchestrator
from .services.search_service import SearchService
from .services.storage_service import StorageService
from .version import APP_VERSION
from .config import get_settings


settings = get_settings()
APP_VARIANT = settings.APP_VARIANT
APP_BRAND = settings.APP_BRAND
REPORT_WORKSPACE_VARIANTS = frozenset({"raporhub", "repocto"})

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title=APP_BRAND.api_title, version=APP_VERSION, lifespan=lifespan)
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
RAPORHUB_LANDING_DIR = Path(__file__).resolve().parent / "ui" / "raporhub_landing"
REPOCTO_LANDING_DIR = Path(__file__).resolve().parent / "ui" / "repocto_landing"
SMARTCAE_V2_DIR = Path(__file__).resolve().parent / "ui" / "smartcae_v2"
app.mount("/raporhub-landing", StaticFiles(directory=str(RAPORHUB_LANDING_DIR)), name="raporhub-landing")
app.mount("/repocto-landing", StaticFiles(directory=str(REPOCTO_LANDING_DIR)), name="repocto-landing")
if APP_VARIANT == "big_agent":
    app.mount(
        "/smartcae-v2/assets",
        StaticFiles(directory=str(SMARTCAE_V2_DIR / "assets")),
        name="smartcae-v2-assets",
    )
FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
<text x="50" y="52" dy="0.35em" text-anchor="middle" font-size="86" font-family="Segoe UI Emoji, Apple Color Emoji, sans-serif">🤖</text>
</svg>"""
AUTH_COOKIE_NAME = settings.APP_AUTH_COOKIE_NAME
AUTH_SESSION_SECONDS = 8 * 60 * 60


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


APP_USERS = _parse_app_users(settings.APP_USERS_RAW)


def _auth_secret() -> str:
    return settings.APP_SESSION_SECRET or "change-this-local-test-secret"


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
    return settings.APP_AUTH_ENABLED and bool(APP_USERS)


def _application_home_path() -> str:
    return "/app" if APP_VARIANT in REPORT_WORKSPACE_VARIANTS else "/"


def _login_html(error: str = "") -> str:
    error_html = f'<div class="error">{escape(error)}</div>' if error else ""
    return f"""<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="icon" href="/favicon.ico" />
  <title>{APP_BRAND.display_name} Login</title>
  <style>
    body {{ margin:0; min-height:100vh; display:grid; place-items:center; font-family:Arial,sans-serif; background:{APP_BRAND.background}; color:{APP_BRAND.text}; }}
    form {{ width:min(380px, calc(100vw - 32px)); background:{APP_BRAND.panel}; border:1px solid {APP_BRAND.line}; border-radius:{APP_BRAND.card_radius}; padding:24px; box-shadow:0 18px 50px {APP_BRAND.card_shadow}; }}
    h1 {{ margin:0 0 6px; font-size:24px; }}
    p {{ margin:0 0 18px; color:{APP_BRAND.muted}; font-size:14px; }}
    label {{ display:block; font-size:13px; font-weight:700; margin:14px 0 6px; }}
    input {{ width:100%; box-sizing:border-box; border:1px solid {APP_BRAND.line}; border-radius:10px; padding:12px; font-size:15px; }}
    button {{ width:100%; margin-top:18px; border:0; border-radius:10px; padding:12px; background:{APP_BRAND.accent_strong}; color:#fff; font-weight:700; cursor:pointer; }}
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
        landing_prefix = "/raporhub-landing/" if APP_VARIANT == "raporhub" else "/repocto-landing/"
        if path == "/" or path.startswith(landing_prefix):
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


def _short_runtime_model_name(value: str) -> str:
    candidate = Path(value).name or value
    return candidate.split("/")[-1]


def _embedding_runtime_status() -> dict[str, object]:
    service = build_embedding_service()
    active_provider = str(getattr(service, "provider_name", "unknown"))
    configured_provider = settings.EMBEDDING_PROVIDER.strip().casefold()
    real_model_loaded = active_provider.startswith("sentence-transformers:") and hasattr(service, "model")
    configured_for_sentence_transformers = configured_provider in {
        "sentence-transformer",
        "sentence-transformers",
        "hf",
        "huggingface",
    }
    configured_path = Path(settings.EMBEDDING_MODEL_NAME).expanduser()
    active_model = (
        _short_runtime_model_name(active_provider.split(":", 1)[1])
        if ":" in active_provider
        else active_provider
    )
    device = str(getattr(service, "device", settings.EMBEDDING_DEVICE)).strip() or "cpu"
    fallback_active = configured_for_sentence_transformers and not real_model_loaded

    if real_model_loaded:
        state = "ready"
        message = "Sentence Transformers modeli yuklendi ve kullanima hazir."
    elif fallback_active:
        state = "warning"
        message = "Yapilandirilan embedding modeli yuklenemedi; token-hash yedek modu aktif."
    else:
        state = "warning"
        message = "Token-hash embedding saglayicisi aktif; Qwen modeli kullanilmiyor."

    return {
        "state": state,
        "ready": real_model_loaded,
        "message": message,
        "configured_provider": settings.EMBEDDING_PROVIDER,
        "active_provider": active_provider,
        "configured_model": _short_runtime_model_name(settings.EMBEDDING_MODEL_NAME),
        "active_model": active_model,
        "device": device,
        "local_files_only": settings.EMBEDDING_LOCAL_FILES_ONLY,
        "model_path_exists": configured_path.exists(),
        "fallback_active": fallback_active,
    }


def _ollama_runtime_status() -> dict[str, object]:
    configured = settings.CHAT_LLM_ENABLED and settings.CHAT_LLM_BACKEND == "ollama"
    base_status: dict[str, object] = {
        "configured": configured,
        "connected": False,
        "host": settings.OLLAMA_HOST,
        "configured_model": settings.CHAT_LLM_MODEL_NAME,
        "model_available": False,
        "models": [],
        "state": "disabled" if not configured else "checking",
        "message": "Ollama sohbet saglayicisi devre disi." if not configured else "",
    }
    if not configured:
        return base_status

    try:
        with httpx.Client(timeout=2.0) as client:
            response = client.get(f"{settings.OLLAMA_HOST}/api/tags")
            response.raise_for_status()
            payload = response.json()
        models = sorted(
            {
                str(item.get("name") or item.get("model") or "").strip()
                for item in payload.get("models", [])
                if isinstance(item, dict) and (item.get("name") or item.get("model"))
            }
        )
        expected_model = settings.CHAT_LLM_MODEL_NAME.strip().casefold()
        model_available = bool(expected_model) and any(
            model.casefold() == expected_model for model in models
        )
        base_status.update(
            {
                "connected": True,
                "model_available": model_available,
                "models": models,
                "state": "ready" if model_available else "warning",
                "message": (
                    "Ollama baglantisi ve yapilandirilan sohbet modeli hazir."
                    if model_available
                    else "Ollama bagli, ancak yapilandirilan sohbet modeli bulunamadi."
                ),
            }
        )
    except Exception as exc:
        error_text = re.sub(r"\s+", " ", str(exc)).strip()[:240]
        base_status.update(
            {
                "state": "error",
                "message": f"Ollama baglantisi kurulamadi: {error_text or type(exc).__name__}",
            }
        )
    return base_status


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


@app.get("/system/model-status")
def system_model_status() -> dict[str, object]:
    return {
        "embedding": _embedding_runtime_status(),
        "ollama": _ollama_runtime_status(),
        "version": APP_VERSION,
    }


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


@app.get("/smartcae-v2/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/smartcae-v2", response_class=HTMLResponse, include_in_schema=False)
def smartcae_v2_page() -> HTMLResponse:
    if APP_VARIANT != "big_agent":
        raise HTTPException(status_code=404, detail="Not found")
    html = SMARTCAE_V2_DIR.joinpath("index.html").read_text(encoding="utf-8")
    return HTMLResponse(
        html.replace("__APP_VERSION__", APP_VERSION),
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/app/", include_in_schema=False)
@app.get("/app", include_in_schema=False)
@app.get("/legacy/", include_in_schema=False)
@app.get("/legacy", include_in_schema=False)
@app.get("/")
def upload_page(request: Request) -> Response:
    if APP_VARIANT == "big_agent" and request.url.path == "/":
        return smartcae_v2_page()
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
    return FileResponse(STATIC_DIR / "index.html", media_type="text/html")


@app.get("/meta")
def app_meta() -> dict[str, str]:
    return {"version": APP_VERSION, "model": _display_model_name()}

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


@app.post("/ingest/batch", response_model=JobStatusResponse, status_code=202, include_in_schema=False)
def ingest_files_batch(
    files: Annotated[list[UploadFile], File(...)],
) -> JobStatusResponse:
    # Upload temp files disappear when the request ends, so stage the payloads
    # to our own temp files before handing the work to the background job.
    staged_files: list[tuple[Path, str]] = []
    for file in files:
        file_name = file.filename or ""
        suffix = Path(file_name).suffix.lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix or ".bin") as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(file.file.read())
        staged_files.append((temp_path, file_name))

    def run_batch_ingest(context: JobContext) -> dict:
        items: list[BatchIngestItemResponse] = []
        try:
            for position, (temp_path, file_name) in enumerate(staged_files, start=1):
                context.set_progress(position - 1, len(staged_files), file_name)
                if Path(file_name).suffix.lower() not in {".pdf", ".docx", ".pptx"}:
                    items.append(
                        BatchIngestItemResponse(
                            file_name=file_name,
                            status="error",
                            error="Only PDF, DOCX and PPTX files are supported.",
                        )
                    )
                    continue

                batch_session = SessionLocal()
                try:
                    service = IngestService(batch_session)
                    result = service.ingest(temp_path, original_file_name=file_name)
                    items.append(BatchIngestItemResponse(**result))
                except Exception as exc:
                    batch_session.rollback()
                    items.append(
                        BatchIngestItemResponse(
                            file_name=file_name,
                            status="error",
                            error=str(exc),
                        )
                    )
                finally:
                    batch_session.close()
        finally:
            for temp_path, _ in staged_files:
                temp_path.unlink(missing_ok=True)

        return BatchIngestResponse(
            total_files=len(staged_files),
            ingested_count=sum(1 for item in items if item.status == "ingested"),
            duplicate_count=sum(1 for item in items if item.status == "duplicate"),
            error_count=sum(1 for item in items if item.status == "error"),
            items=items,
        ).model_dump()

    return JobStatusResponse(**get_job_manager().submit("ingest_batch", run_batch_ingest))


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


@app.post("/duplicates/scan", response_model=JobStatusResponse, status_code=202)
def scan_duplicate_report_pairs(
    threshold: float = Query(0.90, ge=0.1, le=1.0),
    dry_run: bool = Query(False),
) -> JobStatusResponse:
    def run_duplicate_scan(context: JobContext) -> dict:
        scan_session = SessionLocal()
        try:
            service = DuplicateDetectionService(scan_session)
            result = service.scan(
                threshold=threshold,
                dry_run=dry_run,
                progress_callback=lambda done, total: context.set_progress(done, total, "dokuman"),
            )
            return DuplicateReportScanResponse(**result).model_dump()
        finally:
            scan_session.close()

    return JobStatusResponse(**get_job_manager().submit("duplicates_scan", run_duplicate_scan))


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


@app.post("/report-comparison/multi", response_model=ReportComparisonMultiResponse)
def compare_multiple_reports(
    payload: ReportComparisonMultiRequest,
    session: Session = Depends(get_session),
) -> ReportComparisonMultiResponse:
    sources = [source.model_dump() for source in payload.sources]
    for source in sources:
        selected_count = int(bool(source.get("document_id"))) + int(bool(source.get("upload_token")))
        if selected_count != 1:
            raise HTTPException(status_code=400, detail="Her dokuman icin tek bir kaynak sec.")
    if payload.reference_index >= len(sources):
        raise HTTPException(status_code=400, detail="Referans dokuman secimi gecersiz.")
    try:
        service = ReportComparisonService(session)
        return ReportComparisonMultiResponse(
            **service.compare_many(
                sources,
                mode=payload.mode,
                reference_index=payload.reference_index,
                use_llm=payload.use_llm,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Multi-report comparison failed.")
        raise HTTPException(status_code=500, detail="Dokuman karsilastirmasi tamamlanamadi.") from exc


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

    if _should_use_general_chat(payload.assistant_mode, payload.message):
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


def _should_use_general_chat(assistant_mode: str, message: str) -> bool:
    return (
        assistant_mode == "general"
        or _is_chat_small_talk(message)
        or (assistant_mode == "auto" and _is_general_chat_message(message))
    )


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
        "sagol",
        "sag ol",
        "tesekkur",
        "tesekkurler",
        "eyvallah",
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
    if len(normalized.split()) <= 5 and any(
        phrase in normalized for phrase in ("sagol", "sag ol", "tesekkur", "eyvallah")
    ):
        return "Rica ederim.", "chat-direct", 1.0
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
    return re.sub(r"[^a-z0-9\s]+", " ", normalize_search_text(message)).strip()


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


@app.post("/catalog/ingest-sample", response_model=JobStatusResponse, status_code=202)
def ingest_catalog_sample(
    per_discipline: int = Query(2, ge=1, le=10),
    dry_run: bool = Query(True),
    scan_limit_per_discipline: int = Query(25, ge=1, le=500),
) -> JobStatusResponse:
    def run_sample_ingest(context: JobContext) -> dict:
        job_session = SessionLocal()
        try:
            service = CatalogIngestService(job_session)
            result = service.ingest_sample_per_discipline(
                per_discipline=per_discipline,
                dry_run=dry_run,
                scan_limit_per_discipline=scan_limit_per_discipline,
                progress_callback=context.set_progress,
            )
            return CatalogSampleIngestResponse(**result).model_dump()
        finally:
            job_session.close()

    return JobStatusResponse(**get_job_manager().submit("catalog_ingest_sample", run_sample_ingest))


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


def _catia_skill_username(request: Request) -> str:
    return str(getattr(request.state, "username", "") or "local")


def _is_local_catia_client(request: Request) -> bool:
    # "testclient": Starlette TestClient süreç içinden gelir, ağdan gelmez.
    host = request.client.host if request.client else None
    return host in {"127.0.0.1", "::1", "testclient"}


def _require_catia_skill_client(request: Request) -> None:
    """CATIA skill uçları: bayrak açık olmalı ve istemci yerel olmalı.

    cmc, CATIA'ya COM üzerinden aynı makinede bağlanır; LAN'daki bir istemcinin
    isteği sunucunun CATIA'sında ölçüm başlatır ve sunucunun diskine .cmd yazar.
    O yüzden uçlar yalnızca localhost'tan çalışır (AGENT_INTEGRATION_PLAN §2).
    """
    if not settings.CATIA_SKILL_ENABLED:
        raise HTTPException(
            status_code=404,
            detail="CATIA skill'i devre dışı. Açmak için CATIA_SKILL_ENABLED=true ayarlayın.",
        )
    if not _is_local_catia_client(request):
        raise HTTPException(
            status_code=403,
            detail="CATIA skill'i yalnızca CATIA'nın çalıştığı makineden (localhost) kullanılabilir.",
        )


@app.get("/skills/catia-mass-cg/status")
def catia_skill_status(request: Request) -> dict:
    """UI bu uca bakarak modülü gösterip göstermeyeceğine karar verir.

    `local_client`, chat/approve uçlarının bu istemci için 403 döneceğini
    arayüzün önceden söyleyebilmesi içindir: LAN'dan bakan biri modülü boş
    bir sohbet olarak değil, sebebiyle birlikte görür.
    """
    if not settings.CATIA_SKILL_ENABLED:
        return {"enabled": False}
    local_client = _is_local_catia_client(request)
    try:
        return {"available": True, **get_catia_skill_service().status(), "local_client": local_client}
    except CatiaSkillUnavailableError as exc:
        return {
            "enabled": True,
            "available": False,
            "local_client": local_client,
            "error": str(exc),
        }


@app.post("/skills/catia-mass-cg/chat", response_model=CatiaSkillChatResponse)
def catia_skill_chat(
    payload: CatiaSkillChatRequest,
    request: Request,
) -> CatiaSkillChatResponse:
    _require_catia_skill_client(request)
    try:
        service = get_catia_skill_service()
        result = service.chat(
            payload.message,
            session_id=payload.session_id,
            username=_catia_skill_username(request),
        )
        return CatiaSkillChatResponse(**result)
    except CatiaSkillUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except CatiaSkillLLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except CatiaSkillBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/skills/catia-mass-cg/approve", response_model=CatiaSkillChatResponse)
def catia_skill_approve(
    payload: CatiaSkillApproveRequest,
    request: Request,
) -> CatiaSkillChatResponse:
    _require_catia_skill_client(request)
    try:
        service = get_catia_skill_service()
        result = service.approve_and_export(
            payload.session_id,
            username=_catia_skill_username(request),
        )
        return CatiaSkillChatResponse(**result)
    except CatiaSkillUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except CatiaSkillBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/library/scan")
def scan_library(payload: LibraryScanRequest) -> dict:
    if APP_VARIANT != "repocto":
        raise HTTPException(status_code=404, detail="Kütüphane yalnızca RepOcto'da kullanılabilir.")
    try:
        return LibraryService(settings.REPOCTO_LIBRARY_ROOTS).scan(payload.path, limit=payload.limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Kök klasör okunamadı.") from exc


@app.post("/catalog/ingest-selected", response_model=JobStatusResponse, status_code=202)
def ingest_selected_catalog_entries(
    payload: CatalogSelectedIngestRequest,
) -> JobStatusResponse:
    catalog_entry_ids = list(payload.catalog_entry_ids)

    def run_selected_ingest(context: JobContext) -> dict:
        job_session = SessionLocal()
        try:
            service = CatalogIngestService(job_session)
            result = service.ingest_catalog_entries(
                catalog_entry_ids,
                progress_callback=context.set_progress,
            )
            return CatalogSelectedIngestResponse(**result).model_dump()
        finally:
            job_session.close()

    return JobStatusResponse(**get_job_manager().submit("catalog_ingest_selected", run_selected_ingest))


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

    file_exists = Path(document.file_path).exists()
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


@app.post("/documents/{document_id}/open-folder")
def open_document_folder(document_id: int, session: Session = Depends(get_session)) -> dict:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    file_path = resolve_document_file_path(document.file_path)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Original file not found.")

    try:
        os.startfile(str(file_path.parent))  # type: ignore[attr-defined]
    except AttributeError as exc:
        raise HTTPException(status_code=501, detail="Folder opening is only supported on Windows.") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Document folder could not be opened: {exc}") from exc

    return {
        "opened": True,
        "document_id": document.id,
        "file_name": document.file_name,
        "folder_path": str(file_path.parent),
    }


@app.get("/documents/{document_id}/preview")
def document_preview(
    document_id: int,
    page: Annotated[int, Query(ge=1)] = 1,
    session: Session = Depends(get_session),
) -> Response:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    file_path = resolve_document_file_path(document.file_path)
    if file_path is not None and file_path.suffix.lower() == ".pdf":
        return FileResponse(
            path=file_path,
            filename=document.file_name,
            media_type="application/pdf",
            content_disposition_type="inline",
        )

    page_row = session.scalar(
        select(DocumentPage).where(
            DocumentPage.document_id == document_id,
            DocumentPage.page_number == page,
        )
    )

    if page_row is None:
        page_row = session.scalar(
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number.asc())
        )

    page_label = f"Sayfa {page_row.page_number}" if page_row is not None else "Metin önizlemesi"
    section_label = page_row.section_title if page_row is not None and page_row.section_title else "Doküman içeriği"
    preview_text = page_row.clean_text if page_row is not None and page_row.clean_text else "Bu doküman için önizlenebilir metin bulunamadı."
    return HTMLResponse(
        f"""
<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(document.title)} · Önizleme</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; padding: 16px; background: #fff; color: #302326; font-family: "Segoe UI", Tahoma, sans-serif; }}
    header {{ position: sticky; top: 0; margin: -16px -16px 14px; padding: 12px 16px; border-bottom: 1px solid #eadde0; background: rgba(255,255,255,.96); }}
    strong, span {{ display: block; }}
    strong {{ font-size: 13px; line-height: 1.35; }}
    span {{ margin-top: 4px; color: #9b2e43; font-size: 10px; font-weight: 700; }}
    pre {{ margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; font: 11px/1.62 "Segoe UI", Tahoma, sans-serif; }}
  </style>
</head>
<body>
  <header><strong>{escape(document.title)}</strong><span>{escape(page_label)} · {escape(section_label)}</span></header>
  <pre>{escape(preview_text)}</pre>
</body>
</html>
        """
    )


@app.get("/documents/{document_id}/review-preview")
def document_review_preview(
    document_id: int,
    rule_id: Annotated[str, Query(min_length=3, max_length=100, pattern=r"^[a-z0-9_.-]+$")],
    page: Annotated[int, Query(ge=1)] = 1,
    session: Session = Depends(get_session),
) -> FileResponse:
    try:
        preview_path, highlighted_passages = ReportReviewService(session).build_highlighted_preview(
            document_id,
            rule_id,
            page,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(
        path=preview_path,
        filename=f"rapor-kontrol-{document_id}.pdf",
        media_type="application/pdf",
        content_disposition_type="inline",
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Review-Highlights": str(highlighted_passages),
        },
    )


@app.post(
    "/report-review/decisions",
    response_model=ReportReviewDecisionResponse,
)
def save_report_review_decision(
    payload: ReportReviewDecisionRequest,
    session: Session = Depends(get_session),
) -> ReportReviewDecisionResponse:
    try:
        result = ReportReviewService(session).record_decision(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReportReviewDecisionResponse(**result)


@app.get("/report-review/export")
def export_report_review(
    document_ids: Annotated[list[int], Query()],
    session: Session = Depends(get_session),
) -> Response:
    normalized_ids = list(dict.fromkeys(int(item) for item in document_ids if int(item) > 0))
    if not normalized_ids or len(normalized_ids) > 8:
        raise HTTPException(status_code=422, detail="Select between 1 and 8 documents.")
    review = ReportReviewService(session).analyze_documents(normalized_ids)
    if not review["summary"]["documents_analyzed"]:
        raise HTTPException(status_code=404, detail="No report could be reviewed.")
    pdf_content = ReportReviewExportService.build_pdf(review)
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="smartcae-rapor-kontrol.pdf"',
            "Cache-Control": "no-store",
        },
    )


@app.get("/storage/check", response_model=StorageCheckResponse)
def storage_check(session: Session = Depends(get_session)) -> StorageCheckResponse:
    service = StorageService(session)
    return StorageCheckResponse(**service.check_storage())


@app.post("/embeddings/rebuild", response_model=JobStatusResponse, status_code=202)
def rebuild_embeddings() -> JobStatusResponse:
    def run_rebuild(context: JobContext) -> dict:
        job_session = SessionLocal()
        try:
            service = EmbeddingReindexService(job_session)
            result = service.rebuild(
                progress_callback=lambda done, total: context.set_progress(done, total, "chunk"),
            )
            HaystackRetrievalService.clear_cache()
            return ReindexEmbeddingsResponse(**result).model_dump()
        finally:
            job_session.close()

    return JobStatusResponse(**get_job_manager().submit("embeddings_rebuild", run_rebuild))


@app.get("/jobs", response_model=JobListResponse)
def list_background_jobs(limit: int = Query(20, ge=1, le=100)) -> JobListResponse:
    return JobListResponse(items=get_job_manager().list(limit=limit))


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def background_job_status(job_id: str) -> JobStatusResponse:
    payload = get_job_manager().get(job_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobStatusResponse(**payload)
