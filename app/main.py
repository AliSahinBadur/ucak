from __future__ import annotations

from html import escape
from pathlib import Path
import logging
import tempfile
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .api_models import (
    AskRequest,
    AskResponse,
    BatchIngestItemResponse,
    BatchIngestResponse,
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
from .services.ingest_service import IngestService
from .services.qa_service import QAService
from .services.search_service import SearchService
from .services.storage_service import StorageService
from .version import APP_VERSION


logging.basicConfig(level=logging.INFO)

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
    .field label {
      display: block;
      margin-bottom: 8px;
      font-size: 14px;
      font-weight: 600;
      color: var(--text);
    }
    .field input,
    .field select {
      width: 100%;
      border: 1px solid var(--line);
      background: white;
      border-radius: 12px;
      padding: 12px 14px;
      font-size: 15px;
      color: var(--text);
    }
    .field input:focus,
    .field select:focus {
      outline: 2px solid rgba(198, 40, 57, 0.14);
      border-color: var(--accent);
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
            <h1>Big Agent Report Search</h1>
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
          <h2>Soru-Cevap</h2>
          <p>Rapora dogal dilde soru sor. Sistem ilgili chunk'lari bulup metne dayali kisa bir cevap dondursun.</p>
          <div class="search-grid">
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
    const searchQuery = document.getElementById("searchQuery");
    const searchMode = document.getElementById("searchMode");
    const searchButton = document.getElementById("searchButton");
    const searchMeta = document.getElementById("searchMeta");
    const resultsList = document.getElementById("resultsList");
    const similarList = document.getElementById("similarList");
    const askQuestion = document.getElementById("askQuestion");
    const askMode = document.getElementById("askMode");
    const askButton = document.getElementById("askButton");
    const askMeta = document.getElementById("askMeta");
    const answerText = document.getElementById("answerText");
    const answerSources = document.getElementById("answerSources");

    let selectedFiles = [];
    let selectedSingleFile = null;

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

    function renderResults(items) {
      if (!items || items.length === 0) {
        resultsList.innerHTML = '<div class="empty">Sonuc bulunamadi.</div>';
        return;
      }

      resultsList.innerHTML = items.map(item => `
        <article class="result-card" onclick="openDocumentFile(${item.document_id})" style="cursor:pointer;">
          <div class="result-head">
            <div>
              <div class="title">${escapeHtml(item.document_title)}</div>
              <div class="small">Sayfa ${item.page_start}-${item.page_end}${item.section_title ? " | " + escapeHtml(item.section_title) : ""}</div>
            </div>
            <span class="tag">${escapeHtml(item.match_type)}</span>
          </div>
          <div class="small">keyword: ${formatScore(item.keyword_score)} | semantic: ${formatScore(item.semantic_score)} | combined: ${formatScore(item.combined_score)}</div>
          <div class="excerpt">${escapeHtml(item.chunk_text)}</div>
        </article>
      `).join("");
    }

    function renderSimilar(items) {
      if (!items || items.length === 0) {
        similarList.innerHTML = '<div class="empty">Benzer rapor bulunamadi.</div>';
        return;
      }

      similarList.innerHTML = items.map(item => `
        <article class="similar-card" onclick="openDocumentFile(${item.document_id})" style="cursor:pointer;">
          <div class="similar-head">
            <div>
              <div class="title">${escapeHtml(item.document_title)}</div>
              <div class="small">${escapeHtml(item.file_name)}</div>
            </div>
            <span class="tag">score ${formatScore(item.score)}</span>
          </div>
          <div class="small">matched chunks: <span class="count">${item.matched_chunks}</span>${item.top_page_start ? ` | sayfa ${item.top_page_start}-${item.top_page_end}` : ""}</div>
          <div class="excerpt">${escapeHtml(item.top_excerpt)}</div>
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
          <div class="small">Sayfa ${item.page_start}-${item.page_end}${item.section_title ? " | " + escapeHtml(item.section_title) : ""}</div>
          <div class="small">match: ${escapeHtml(item.match_type)} | combined: ${formatScore(item.combined_score)}</div>
          <div class="excerpt">${escapeHtml(item.chunk_text)}</div>
        </article>
      `).join("");
    }

    async function runSearch() {
      const query = searchQuery.value.trim();
      const mode = searchMode.value;
      if (!query) {
        searchMeta.textContent = "Arama yapmak icin once bir sorgu gir.";
        return;
      }

      searchButton.disabled = true;
      searchMeta.textContent = "Arama calisiyor...";
      try {
        const response = await fetch(`/search?query=${encodeURIComponent(query)}&mode=${encodeURIComponent(mode)}&limit=5`);
        const data = await response.json();
        if (!response.ok) {
          searchMeta.textContent = data.detail || "Arama basarisiz oldu.";
          return;
        }
        searchMeta.textContent = `Mod: ${data.mode} | Provider: ${data.embedding_provider} | Sonuc: ${data.results.length} | Benzer rapor: ${data.similar_documents.length}`;
        renderResults(data.results);
        renderSimilar(data.similar_documents);
      } catch (error) {
        searchMeta.textContent = `Arama basarisiz oldu: ${error}`;
      } finally {
        searchButton.disabled = false;
      }
    }

    async function runAsk() {
      const question = askQuestion.value.trim();
      const mode = askMode.value;
      if (!question) {
        askMeta.textContent = "Soru sormak icin once bir soru gir.";
        return;
      }

      askButton.disabled = true;
      askMeta.textContent = "Soru isleniyor...";
      try {
        const response = await fetch("/ask", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            question,
            mode,
            limit: 5,
          }),
        });
        const data = await response.json();
        if (!response.ok) {
          askMeta.textContent = data.detail || "Soru-cevap basarisiz oldu.";
          return;
        }
        askMeta.textContent = `Mod: ${data.mode} | Provider: ${data.embedding_provider} | Guven: ${formatScore(data.confidence)} | Kaynak: ${data.sources.length}`;
        answerText.textContent = data.answer;
        renderAnswerSources(data.sources);
      } catch (error) {
        askMeta.textContent = `Soru-cevap basarisiz oldu: ${error}`;
      } finally {
        askButton.disabled = false;
      }
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
      setSingleStatus("ok", "Dosya yukleniyor...");

      try {
        const response = await fetch("/ingest", {
          method: "POST",
          body: formData,
        });
        const data = await response.json();
        singleResultBox.textContent = JSON.stringify(data, null, 2);
        if (response.ok) {
          setSingleStatus("ok", `Islem tamamlandi. Durum: ${data.status}.`);
        } else {
          setSingleStatus("error", data.detail || "Yukleme basarisiz oldu.");
        }
      } catch (error) {
        setSingleStatus("error", `Istek basarisiz oldu: ${error}`);
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
      setStatus("ok", "Dosyalar yukleniyor...");

      try {
        const response = await fetch("/ingest/batch", {
          method: "POST",
          body: formData,
        });
        const data = await response.json();
        resultBox.textContent = JSON.stringify(data, null, 2);
        if (response.ok) {
          setStatus("ok", `Yukleme tamamlandi. ${data.ingested_count} yeni dosya islendi, ${data.duplicate_count} duplicate bulundu.`);
        } else {
          setStatus("error", data.detail || "Yukleme basarisiz oldu.");
        }
      } catch (error) {
        setStatus("error", `Istek basarisiz oldu: ${error}`);
      } finally {
        uploadButton.disabled = false;
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
    return AskResponse(**service.answer_question(payload.question, mode=payload.mode, limit=payload.limit))


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
