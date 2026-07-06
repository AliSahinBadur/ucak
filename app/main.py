from __future__ import annotations

from html import escape
from pathlib import Path
import logging
import os
import re
import tempfile
import unicodedata
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, HTMLResponse, Response
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
    MultiDocumentAskRequest,
    MultiDocumentAskResponse,
    ReindexEmbeddingsResponse,
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
from .services.general_chat_service import GeneralChatService
from .services.graph_service import GraphService
from .services.ingest_service import IngestService
from .services.multi_document_qa_service import MultiDocumentQAService
from .services.qa_service import QAService
from .services.report_writer_service import ReportWriterService
from .services.retrieval_orchestrator import RetrievalOrchestrator
from .services.search_service import SearchService
from .services.storage_service import StorageService
from .version import APP_VERSION


logging.basicConfig(level=logging.INFO)
#dfgasdgfasdfasdfasdfasdf
app = FastAPI(title="Big Agent MVP", version=APP_VERSION)


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


def _safe_download_name(value: str, fallback: str = "rapor") -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^\w.-]+", "_", ascii_only).strip("_")
    return cleaned or fallback


@app.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok", version=APP_VERSION)


@app.get("/", response_class=HTMLResponse)
def upload_page() -> HTMLResponse:
    model_label = escape(_display_model_name())
    html = """
<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Big Agent</title>
  <style>
    :root {
      --bg: #fbf3f4;
      --panel: #ffffff;
      --line: #ae848d;
      --text: #2a1014;
      --muted: #7a555b;
      --accent: #c62839;
      --accent-strong: #8f1421;
      --soft: #fdecef;
      --soft-2: #fff9fa;
      --ok: #1b7f4b;
      --error: #a61b2b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", Tahoma, sans-serif;
      background:
        radial-gradient(circle at top right, #ffd9df 0%, transparent 26%),
        radial-gradient(circle at left center, #fff0f2 0%, transparent 20%),
        linear-gradient(180deg, #fff7f8 0%, var(--bg) 100%);
      color: var(--text);
    }
    .wrap {
      max-width: 1120px;
      margin: 36px auto;
      padding: 0 20px 40px;
      transition: max-width 180ms ease;
    }
    body.chat-focus .wrap {
      max-width: 1480px;
    }
    .stack {
      display: grid;
      gap: 22px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 20px;
      box-shadow: 0 16px 38px rgba(120, 24, 38, 0.08);
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
      background: #ffe6ea;
      color: var(--accent-strong);
      border: 1px solid #f2bcc5;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.02em;
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
      background: #fff7f8;
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
      background: #fff0f2;
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
      background: #fff0f2;
      color: var(--accent-strong);
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
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
      background: #fff0f2;
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
      background: #fff0f2;
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
      .split {
        grid-template-columns: 1fr;
      }
      .chat-input-row {
        grid-template-columns: 1fr;
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
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="stack">
      <div class="card">
        <div class="hero">
          <div class="hero-title-row">
            <h1>Big Agent</h1>
            <span class="version-pill">v__APP_VERSION__</span>
            <span class="version-pill">model: __MODEL_LABEL__</span>
          </div>
          <p>Rapor havuzunu yonet, katalogla eslestir, kaynakli cevap al ve mukerrer adaylari ayni yerel sistemde incele.</p>
          <div class="module-switcher" aria-label="Modul secimi">
            <button class="module-filter active" type="button" data-module-filter="upload">Raporlar</button>
            <button class="module-filter" type="button" data-module-filter="catalog">Katalog</button>
            <button class="module-filter" type="button" data-module-filter="search">Arama</button>
            <button class="module-filter" type="button" data-module-filter="chat">Chatbot</button>
            <button class="module-filter" type="button" data-module-filter="duplicates">Mukerrer</button>
            <button class="module-filter" type="button" data-module-filter="graph">Kategoriler</button>
            <button class="module-filter" type="button" data-module-filter="qa">Q&A</button>
            <button class="module-filter" type="button" data-module-filter="writing">Yazim</button>
            <button class="module-filter" type="button" data-module-filter="all">Her sey</button>
          </div>
        </div>
        <div class="section" data-module-title="Raporlar" data-module-key="upload">
          <div class="section-head">
            <div>
              <h2>Raporlar</h2>
              <p>Tekli veya toplu PDF/DOCX/PPTX raporlarini sisteme ekle.</p>
            </div>
            <button class="expand-button" type="button" data-expand-module>Buyut</button>
          </div>
          <div class="upload-grid">
            <div class="upload-card">
              <h2>Tekli Rapor Yukleme</h2>
              <p>Tek bir PDF veya DOCX eklemek istersen bu alani kullan.</p>
              <div class="actions">
                <label class="button secondary" for="singlePicker">Dosya Sec</label>
                <button class="button primary" id="singleUploadButton" type="button">Tekli Yukleme Baslat</button>
                <input id="singlePicker" type="file" accept=".pdf,.docx,.pptx" />
              </div>
              <div class="meta" id="singleSummary">Henuz tekli dosya secilmedi.</div>
              <div class="status" id="singleStatusBox"></div>
              <div class="upload-spacer" aria-hidden="true"></div>
              <div class="result">
                <pre id="singleResultBox">{}</pre>
              </div>
            </div>
            <div class="upload-card">
              <h2>Toplu Rapor Yukleme</h2>
              <p>Klasor sec, icindeki PDF ve DOCX dosyalarini tek seferde yukle.</p>
              <div class="actions">
                <label class="button secondary" for="folderPicker">Klasor Sec</label>
                <button class="button primary" id="uploadButton" type="button">Yuklemeyi Baslat</button>
                <input id="folderPicker" type="file" webkitdirectory directory multiple />
              </div>
              <div class="meta" id="summary">Henuz klasor secilmedi.</div>
              <div class="files">
                <ul id="filesList"><li>Dosya listesi burada gorunecek.</li></ul>
              </div>
              <div class="status" id="statusBox"></div>
              <div class="result">
                <pre id="resultBox">{}</pre>
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
                  <div class="chat-avatar">BA</div>
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
                  <select id="chatMode" aria-label="Chat arama modu">
                    <option value="hybrid">hybrid</option>
                    <option value="semantic">semantic</option>
                    <option value="keyword">keyword</option>
                  </select>
                  <button class="button secondary" id="chatClearButton" type="button">Yeni Sohbet</button>
                </div>
              </div>
              <div id="chatMessages" class="chat-messages">
                <div class="chat-message assistant">Merhaba. Icerideki raporlar uzerinden soru sorabilirsin.</div>
              </div>
              <div class="chat-prompts">
                <button class="chat-prompt" type="button" data-chat-prompt="Big Agent ne yapar?">Big Agent ne yapar?</button>
                <button class="chat-prompt" type="button" data-chat-prompt="Bu uygulama ne yapar?">Uygulama nedir?</button>
                <button class="chat-prompt" type="button" data-chat-prompt="Kendinden bahset">Kendinden bahset</button>
                <button class="chat-prompt" type="button" data-chat-prompt="BIG-E konfor raporunda hangi parkurlar var?">BIG-E konfor parkurlari</button>
                <button class="chat-prompt" type="button" data-chat-prompt="Alternator braket raporunda dogal frekans kac Hz?">Alternator braket</button>
                <button class="chat-prompt" type="button" data-chat-prompt="TASE sicaklik testinde kac sensor kullanildi?">TASE sensor</button>
              </div>
              <div class="chat-input-row">
                <textarea id="chatInput" rows="2" placeholder="Rapor, test veya analiz hakkinda soru sor..."></textarea>
                <button class="button primary" id="chatSendButton" type="button">Gonder</button>
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
              <p>Icerideki raporlar arasinda birbirine cok benzeyen kayitli adaylari gor.</p>
            </div>
            <button class="expand-button" type="button" data-expand-module>Buyut</button>
          </div>
          <div class="actions">
            <button class="button primary" id="duplicateScanButton" type="button">Taramayi Baslat</button>
            <button class="button secondary" id="duplicateRefreshButton" type="button">Kayitli Sonuclari Yenile</button>
          </div>
          <div class="note" id="duplicateStatus">Mukerrer adaylari henuz yuklenmedi.</div>
          <div id="duplicateList" class="cards" style="margin-top:16px;">
            <div class="empty">Kayitli mukerrer adaylari burada listelenecek.</div>
          </div>
        </div>
        <div class="section" data-module-title="Katalog" data-modal-layout="catalog-stack" data-module-key="catalog">
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
        <div class="section" data-module-title="Kategori Tarayici" data-module-key="graph">
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
                    <option value="hybrid">hybrid</option>
                    <option value="semantic">semantic</option>
                    <option value="keyword">keyword</option>
                  </select>
                </div>
              </div>
              <div class="actions" style="margin-top:12px;">
                <button class="button primary" id="draftQuickButton" type="button" style="flex:1;">Hizli Rapor Olustur</button>
                <button class="button primary" id="draftDetailedButton" type="button" style="flex:1;">Detayli Rapor Olustur</button>
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
            </div>
            <div class="panel">
              <div class="panel-title">Taslak Metin</div>
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
    const picker = document.getElementById("folderPicker");
    const uploadButton = document.getElementById("uploadButton");
    const summary = document.getElementById("summary");
    const filesList = document.getElementById("filesList");
    const statusBox = document.getElementById("statusBox");
    const resultBox = document.getElementById("resultBox");
    const singlePicker = document.getElementById("singlePicker");
    const singleUploadButton = document.getElementById("singleUploadButton");
    const singleSummary = document.getElementById("singleSummary");
    const singleStatusBox = document.getElementById("singleStatusBox");
    const singleResultBox = document.getElementById("singleResultBox");
    const uploadedDocumentsRefreshButton = document.getElementById("uploadedDocumentsRefreshButton");
    const uploadedDocumentsStatus = document.getElementById("uploadedDocumentsStatus");
    const uploadedDocumentsTable = document.getElementById("uploadedDocumentsTable");
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
    const chatMessages = document.getElementById("chatMessages");
    const chatInput = document.getElementById("chatInput");
    const chatAssistantMode = document.getElementById("chatAssistantMode");
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
    const draftObjective = document.getElementById("draftObjective");
    const draftKeywords = document.getElementById("draftKeywords");
    const draftNotes = document.getElementById("draftNotes");
    const draftQuickButton = document.getElementById("draftQuickButton");
    const draftDetailedButton = document.getElementById("draftDetailedButton");
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
    let selectedSingleFile = null;
    let selectedCatalogFile = null;
    let lastCatalogQuestion = "";
    let lastCatalogMatches = [];
    let chatHistory = [];
    let graphState = { categories: [], documents: [], selectedCategoryId: "all", search: "" };
    let activeTimerId = null;
    let activeModule = null;
    let selectedModuleFilter = "upload";

    function applyModuleFilter(filterKey) {
      selectedModuleFilter = filterKey || "upload";
      if (activeModule) {
        closeModule();
      }

      moduleFilterButtons.forEach(button => {
        button.classList.toggle("active", button.dataset.moduleFilter === selectedModuleFilter);
      });
      document.body.classList.toggle("chat-focus", selectedModuleFilter === "chat");

      moduleSections.forEach(section => {
        const keys = String(section.dataset.moduleKey || "").split(/\\s+/);
        const shouldShow = selectedModuleFilter === "all" || keys.includes(selectedModuleFilter);
        section.classList.toggle("module-hidden", !shouldShow);
      });

      if (selectedModuleFilter === "graph") {
        refreshGraph();
      }
      if (selectedModuleFilter === "duplicates") {
        refreshDuplicates();
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
        refreshGraph();
      }
      if (section.dataset.moduleKey === "duplicates") {
        refreshDuplicates();
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
        summary.textContent = "Henuz klasor secilmedi.";
        return;
      }

      const supported = selectedFiles.filter(file => {
        const lower = file.name.toLowerCase();
        return lower.endsWith(".pdf") || lower.endsWith(".docx") || lower.endsWith(".pptx");
      });

      summary.textContent = `${selectedFiles.length} dosya secildi, ${supported.length} tanesi desteklenen turde.`;
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

    function setStatus(kind, message) {
      statusBox.className = `status show ${kind}`;
      statusBox.textContent = message;
    }

    function setSingleStatus(kind, message) {
      singleStatusBox.className = `status show ${kind}`;
      singleStatusBox.textContent = message;
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

    function appendChatMessage(role, content) {
      const node = document.createElement("div");
      node.className = `chat-message ${role}`;
      const label = document.createElement("div");
      label.className = "chat-message-label";
      label.textContent = role === "user" ? "Sen" : "Big Agent";
      const body = document.createElement("div");
      body.className = "chat-message-body";
      body.textContent = content;
      node.appendChild(label);
      node.appendChild(body);
      chatMessages.appendChild(node);
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function resetChat() {
      chatHistory = [];
      chatMessages.innerHTML = "";
      appendChatMessage("assistant", "Merhaba. Raporlar uzerinden soru sorabilir, ben de kaynaklariyla birlikte cevaplayabilirim.");
      chatSources.innerHTML = '<div class="empty">Kaynaklar cevap geldikce burada listelenecek.</div>';
      chatSourceMeta.textContent = "Cevap geldikce ilgili rapor pasajlari burada gorunur.";
      chatStatus.textContent = "Chatbot hazir.";
      chatInput.value = "";
      chatInput.focus();
    }

    async function sendChatMessage() {
      const message = chatInput.value.trim();
      if (!message) {
        chatStatus.textContent = "Mesaj yazmadan gonderemem.";
        return;
      }

      chatInput.value = "";
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
            mode: chatMode.value,
            limit: 5,
          }),
        });
        const data = await response.json();
        if (!response.ok) {
          stopTimer(startedAt, text => { chatStatus.textContent = text; }, data.detail || "Chatbot cevap veremedi.");
          appendChatMessage("assistant", data.detail || "Cevap olusturulamadi.");
          return;
        }
        appendChatMessage("assistant", data.answer);
        chatHistory = data.history || [
          ...chatHistory,
          { role: "assistant", content: data.answer },
        ];
        renderChatSources(data.sources || []);
        stopTimer(
          startedAt,
          text => { chatStatus.textContent = text; },
          `Cevap hazir. Guven: ${formatScore(data.confidence)} | Kaynak: ${(data.sources || []).length}`
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
        return;
      }

      draftSources.innerHTML = items.map(item => `
        <article class="source-card" onclick="openDocumentFile(${item.document_id})" style="cursor:pointer;">
          <div class="title">${escapeHtml(item.document_title)}</div>
          <div class="small">Sayfa ${item.page_start}-${item.page_end}${item.section_title ? " | " + escapeHtml(item.section_title) : ""}</div>
          <div class="excerpt">${escapeHtml(item.chunk_text)}</div>
        </article>
      `).join("");
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
      const title = draftTitle.value.trim();
      if (!title) {
        draftMeta.textContent = "Taslak uretmek icin once rapor basligi gir.";
        return;
      }

      const payload = {
        title,
        report_type: draftType.value.trim() || "Genel Teknik Rapor",
        objective: draftObjective.value.trim(),
        keywords: draftKeywords.value.trim(),
        raw_notes: draftNotes.value.trim(),
        detail_level: detailLevel,
        mode: draftMode.value,
        limit: 5,
      };

      draftQuickButton.disabled = true;
      draftDetailedButton.disabled = true;
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
          `Tur: ${data.detail_level} | Provider: ${data.embedding_provider} | Anahtar kelime: ${data.refined_keywords.length} | Kaynak: ${data.sources.length} | PDF indiriliyor...`
        );
        draftOutput.textContent = data.draft;
        renderDraftSources(data.sources);
        await downloadDraftPdf(payload, data.title, data.detail_level);
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

    picker.addEventListener("change", () => {
      selectedFiles = Array.from(picker.files || []);
      renderFiles();
      setStatus("ok", "Klasor secildi. Istersen simdi yuklemeyi baslatabilirsin.");
    });

    singlePicker.addEventListener("change", () => {
      selectedSingleFile = (singlePicker.files && singlePicker.files[0]) ? singlePicker.files[0] : null;
      if (!selectedSingleFile) {
        singleSummary.textContent = "Henuz tekli dosya secilmedi.";
        return;
      }
      singleSummary.textContent = `Secilen dosya: ${selectedSingleFile.name}`;
      setSingleStatus("ok", "Dosya secildi. Istersen simdi yuklemeyi baslatabilirsin.");
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

    singleUploadButton.addEventListener("click", async () => {
      if (!selectedSingleFile) {
        setSingleStatus("error", "Yuklemek icin once bir dosya sec.");
        return;
      }
      const lower = selectedSingleFile.name.toLowerCase();
      if (!(lower.endsWith(".pdf") || lower.endsWith(".docx") || lower.endsWith(".pptx"))) {
        setSingleStatus("error", "Sadece PDF ve DOCX desteklenir.");
        return;
      }

      const formData = new FormData();
      formData.append("file", selectedSingleFile, selectedSingleFile.name);

      singleUploadButton.disabled = true;
      const startedAt = startTimer(message => setSingleStatus("ok", message), "Dosya yukleniyor...");

      try {
        const response = await fetch("/ingest", {
          method: "POST",
          body: formData,
        });
        const data = await response.json();
        singleResultBox.textContent = JSON.stringify(data, null, 2);
        if (response.ok) {
          stopTimer(startedAt, message => setSingleStatus("ok", message), `Islem tamamlandi. Durum: ${data.status}.`);
          if (activeModule && activeModule.dataset.moduleKey === "upload") {
            await refreshUploadedDocuments();
          }
        } else {
          stopTimer(startedAt, message => setSingleStatus("error", message), data.detail || "Yukleme basarisiz oldu.");
        }
      } catch (error) {
        stopTimer(startedAt, message => setSingleStatus("error", message), `Istek basarisiz oldu: ${error}`);
      } finally {
        singleUploadButton.disabled = false;
      }
    });

    uploadButton.addEventListener("click", async () => {
      const supported = selectedFiles.filter(file => {
        const lower = file.name.toLowerCase();
        return lower.endsWith(".pdf") || lower.endsWith(".docx") || lower.endsWith(".pptx");
      });

      if (supported.length === 0) {
        setStatus("error", "Yuklenecek PDF veya DOCX bulunamadi.");
        return;
      }

      const formData = new FormData();
      supported.forEach(file => formData.append("files", file, file.name));

      uploadButton.disabled = true;
      const startedAt = startTimer(message => setStatus("ok", message), "Dosyalar yukleniyor...");

      try {
        const response = await fetch("/ingest/batch", {
          method: "POST",
          body: formData,
        });
        const data = await response.json();
        resultBox.textContent = JSON.stringify(data, null, 2);
        if (response.ok) {
          stopTimer(
            startedAt,
            message => setStatus("ok", message),
            `Yukleme tamamlandi. ${data.ingested_count} yeni dosya islendi, ${data.duplicate_count} duplicate bulundu.`
          );
          if (activeModule && activeModule.dataset.moduleKey === "upload") {
            await refreshUploadedDocuments();
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
    chatPromptButtons.forEach(button => {
      button.addEventListener("click", () => {
        chatInput.value = button.dataset.chatPrompt || "";
        chatInput.focus();
      });
    });
    chatInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendChatMessage();
      }
    });
    duplicateScanButton.addEventListener("click", runDuplicateScan);
    duplicateRefreshButton.addEventListener("click", refreshDuplicates);
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
    draftQuickButton.addEventListener("click", () => runDraft("quick"));
    draftDetailedButton.addEventListener("click", () => runDraft("detailed"));
    updateCatalogScope([], "");
    resetMultiDocumentWorkspace();
    resetChat();
    applyModuleFilter("upload");

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
    return HTMLResponse(html)


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
    if payload.assistant_mode == "general" or (
        payload.assistant_mode == "auto" and _is_general_chat_message(payload.message)
    ):
        history = [
            item.model_dump()
            for item in payload.history[-8:]
            if item.content.strip()
        ]
        answer_text, provider_name, confidence = _chat_general_answer(payload.message, history)
        history.append({"role": "user", "content": payload.message})
        history.append({"role": "assistant", "content": answer_text})
        return ChatResponse(
            message=payload.message,
            answer=answer_text,
            answer_found=True,
            confidence=confidence,
            embedding_provider=provider_name,
            sources=[],
            history=history[-10:],
        )

    service = QAService(session)
    answer = service.answer_question(
        payload.message,
        mode=payload.mode,
        limit=payload.limit,
        document_id=payload.document_id,
        use_llm_answer=payload.use_llm_answer,
    )
    history = [
        item.model_dump()
        for item in payload.history[-8:]
        if item.content.strip()
    ]
    history.append({"role": "user", "content": payload.message})
    history.append({"role": "assistant", "content": answer["answer"]})
    return ChatResponse(
        message=payload.message,
        answer=answer["answer"],
        answer_found=answer["answer_found"],
        confidence=answer["confidence"],
        embedding_provider=answer["embedding_provider"],
        sources=answer["sources"],
        history=history[-10:],
    )


def _is_general_chat_message(message: str) -> bool:
    normalized = _fold_chat_text(message)
    if not normalized:
        return False
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
    }
    if any(term in normalized for term in report_terms):
        return True
    return bool(re.search(r"\b20\d{2}[a-z0-9-]*-[a-z0-9-]+", normalized))


def _chat_general_answer(message: str, history: list[dict] | None = None) -> tuple[str, str, float]:
    normalized = _fold_chat_text(message)
    if any(phrase in normalized for phrase in ("adam misin", "insan misin", "robot musun", "gercek misin")):
        return (
            "Ben insan degilim; Big Agent icinde calisan yapay zeka destekli bir rapor asistaniyim. "
            "Genel sohbet edebilirim, ama asil isim raporlar ve teknik dokumanlar uzerinden yardim etmek.",
            "chat-direct",
            1.0,
        )
    if any(phrase in normalized for phrase in ("kendinden bahset", "sen kimsin", "kimsin", "kendini tanit", "kendini tanıt")):
        return (
            "Ben Big Agent icindeki rapor asistaniyim. PDF, DOCX ve PPTX raporlarindan kaynakli cevap bulmak, "
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
        or "bu uygulama ne yapar" in normalized
        or "sistem ne yapar" in normalized
    ):
        return (
            "Rapor iceriginde arama yapabilir, teknik sorulara kaynak pasajlarla cevap verebilir, ilgili raporlari ve "
            "benzer dokumanlari gosterebilir, katalog kayitlarini icerdeki raporlarla eslestirebilir ve mukerrer rapor "
            "adaylarini listeleyebilirim.",
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
            objective=payload.objective,
            keywords=payload.keywords,
            raw_notes=payload.raw_notes,
            detail_level=payload.detail_level,
            mode=payload.mode,
            limit=payload.limit,
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
        objective=payload.objective,
        keywords=payload.keywords,
        raw_notes=payload.raw_notes,
        detail_level=payload.detail_level,
        mode=payload.mode,
        limit=payload.limit,
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

    file_path = Path(document.file_path)
    if not file_path.exists():
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
    return ReindexEmbeddingsResponse(**service.rebuild())
