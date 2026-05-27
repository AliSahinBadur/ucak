from __future__ import annotations

from html import escape
from pathlib import Path
import logging
import re
import tempfile
import unicodedata
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, HTMLResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .api_models import (
    AskRequest,
    AskResponse,
    BatchIngestItemResponse,
    BatchIngestResponse,
    CatalogAskRequest,
    CatalogAskResponse,
    CatalogImportResponse,
    CatalogSearchResponse,
    DraftReportRequest,
    DraftReportResponse,
    HealthResponse,
    IngestResponse,
    ReindexEmbeddingsResponse,
    SearchResponse,
    StorageCheckResponse,
)
from .db.session import SessionLocal, get_session, init_db
from .db.models import Document, DocumentPage
from .services.embedding_reindex_service import EmbeddingReindexService
from .services.embedding_service import build_embedding_service
from .services.catalog_service import CatalogService
from .services.ingest_service import IngestService
from .services.qa_service import QAService
from .services.report_writer_service import ReportWriterService
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
      --line: #e8cfd4;
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
    .section {
      padding: 24px 28px 28px;
    }
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
      grid-template-columns: minmax(0, 2fr) 210px 120px;
      gap: 12px;
      align-items: end;
      margin-top: 16px;
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
      .split {
        grid-template-columns: 1fr;
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
            <h1>RaporHub</h1>
            <span class="version-pill">v__APP_VERSION__</span>
            <span class="version-pill">model: __MODEL_LABEL__</span>
          </div>
          <p>PDF ve DOCX raporlarini yukle, sonra ayni ekranda keyword, semantic veya hybrid arama ile ilgili pasajlari ve benzer raporlari incele.</p>
          <div class="hero-meta">
            <span class="hero-pill">Upload</span>
            <span class="hero-pill">Search</span>
            <span class="hero-pill">Similar Reports</span>
          </div>
        </div>
        <div class="section">
          <div class="upload-grid">
            <div class="upload-card">
              <h2>Tekli Rapor Yukleme</h2>
              <p>Tek bir PDF veya DOCX eklemek istersen bu alani kullan.</p>
              <div class="actions">
                <label class="button secondary" for="singlePicker">Dosya Sec</label>
                <button class="button primary" id="singleUploadButton" type="button">Tekli Yukleme Baslat</button>
                <input id="singlePicker" type="file" accept=".pdf,.docx" />
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
        </div>
        <div class="section">
          <h2>Arama</h2>
          <p>Bir ifade gir, modu sec ve sonuc kartlariyla benzer raporlari ayni ekranda gor.</p>
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
          <div class="split">
            <div class="panel">
              <div class="panel-title">Sonuclar</div>
              <div id="resultsList" class="cards">
                <div class="empty">Sonuclar burada listelenecek.</div>
              </div>
            </div>
            <div class="panel">
              <div class="panel-title">Benzer Raporlar</div>
              <div id="similarList" class="cards">
                <div class="empty">Benzer rapor onerileri burada listelenecek.</div>
              </div>
            </div>
          </div>
        </div>
        <div class="section">
          <h2>Rapor Katalogu ve Coklu Belge QA</h2>
          <p>Surekli guncellenen Excel/CSV katalogunu yukle. Sonra arac, disiplin veya test tipi uzerinden katalog seviyesinde soru sor.</p>
          <div class="upload-grid">
            <div class="upload-card">
              <h2>Katalog Yukleme</h2>
              <p>Excel (.xlsx), CSV, TSV veya TXT formatinda rapor listesini ekle.</p>
              <div class="actions">
                <label class="button secondary" for="catalogPicker">Katalog Sec</label>
                <button class="button primary" id="catalogImportButton" type="button">Katalogu Yukle</button>
                <input id="catalogPicker" type="file" accept=".xlsx,.csv,.tsv,.txt" />
              </div>
              <div class="meta" id="catalogSummary">Henuz katalog dosyasi secilmedi.</div>
              <div class="status" id="catalogStatusBox"></div>
              <div class="result">
                <pre id="catalogResultBox">{}</pre>
              </div>
            </div>
            <div class="upload-card">
              <h2>Coklu Belge Sorusu</h2>
              <p>Ornek: Novocitivolt araci ile kac tane NVH testi yapildi?</p>
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
              <div id="catalogMatches" class="cards" style="margin-top:12px;">
                <div class="empty">Eslesen katalog kayitlari burada listelenecek.</div>
              </div>
            </div>
          </div>
        </div>
        <div class="section">
          <h2>Soru-Cevap</h2>
          <p>Rapora dogal dilde soru sor. Sistem ilgili chunk'lari bulup metne dayali kisa bir cevap dondursun.</p>
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
        <div class="section">
          <h2>Rapor Yazma Destegi</h2>
          <p>Baslik, amac, anahtar kelimeler ve ham notlar ver. Sistem bunlari daha duzgun bir rapor taslagina cevirsin ve benzer raporlardan ornek pasajlar getirsin.</p>
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
    const catalogPicker = document.getElementById("catalogPicker");
    const catalogImportButton = document.getElementById("catalogImportButton");
    const catalogSummary = document.getElementById("catalogSummary");
    const catalogStatusBox = document.getElementById("catalogStatusBox");
    const catalogResultBox = document.getElementById("catalogResultBox");
    const catalogQuestion = document.getElementById("catalogQuestion");
    const catalogAskButton = document.getElementById("catalogAskButton");
    const catalogAskMeta = document.getElementById("catalogAskMeta");
    const catalogAnswer = document.getElementById("catalogAnswer");
    const catalogMatches = document.getElementById("catalogMatches");
    const searchQuery = document.getElementById("searchQuery");
    const searchMode = document.getElementById("searchMode");
    const searchButton = document.getElementById("searchButton");
    const searchMeta = document.getElementById("searchMeta");
    const resultsList = document.getElementById("resultsList");
    const similarList = document.getElementById("similarList");
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

    let selectedFiles = [];
    let selectedSingleFile = null;
    let selectedCatalogFile = null;
    let activeTimerId = null;

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

    function renderFiles() {
      filesList.innerHTML = "";
      if (selectedFiles.length === 0) {
        filesList.innerHTML = "<li>Dosya listesi burada gorunecek.</li>";
        summary.textContent = "Henuz klasor secilmedi.";
        return;
      }

      const supported = selectedFiles.filter(file => {
        const lower = file.name.toLowerCase();
        return lower.endsWith(".pdf") || lower.endsWith(".docx");
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
        renderCatalogMatches(data.catalog_matches);
      } catch (error) {
        stopTimer(startedAt, message => { catalogAskMeta.textContent = message; }, `Katalog sorusu basarisiz oldu: ${error}`);
      } finally {
        catalogAskButton.disabled = false;
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
        const response = await fetch(`/search?query=${encodeURIComponent(query)}&mode=${encodeURIComponent(mode)}&limit=5`);
        const data = await response.json();
        if (!response.ok) {
          stopTimer(startedAt, message => { searchMeta.textContent = message; }, data.detail || "Arama basarisiz oldu.");
          return;
        }
        stopTimer(
          startedAt,
          message => { searchMeta.textContent = message; },
          `Mod: ${data.mode} | Provider: ${data.embedding_provider} | Sonuc: ${data.results.length} | Benzer rapor: ${data.similar_documents.length}`
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
      if (!(lower.endsWith(".pdf") || lower.endsWith(".docx"))) {
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
        return lower.endsWith(".pdf") || lower.endsWith(".docx");
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
        catalogResultBox.textContent = JSON.stringify(data, null, 2);
        if (response.ok) {
          stopTimer(
            startedAt,
            message => setCatalogStatus("ok", message),
            `Katalog yuklendi. ${data.created_count} yeni kayit, ${data.duplicate_count} duplicate.`
          );
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
    catalogQuestion.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        runCatalogAsk();
      }
    });
    draftQuickButton.addEventListener("click", () => runDraft("quick"));
    draftDetailedButton.addEventListener("click", () => runDraft("detailed"));

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
    if suffix not in {".pdf", ".docx"}:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported.")

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
        if suffix not in {".pdf", ".docx"}:
            items.append(
                BatchIngestItemResponse(
                    file_name=file.filename or "",
                    status="error",
                    error="Only PDF and DOCX files are supported.",
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
    session: Session = Depends(get_session),
) -> SearchResponse:
    service = SearchService(session)
    if mode == "keyword":
        results = service.keyword_search(query=query, limit=limit)
    elif mode == "semantic":
        results = service.semantic_search(query=query, limit=limit)
    else:
        results = service.hybrid_search(query=query, limit=limit)

    return SearchResponse(
        mode=mode,
        semantic_available=service.semantic_available(),
        embedding_provider=service.embedding_provider_name(),
        results=results,
        similar_documents=service.similar_documents_for_results(results, limit=3),
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
        )
    )


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
