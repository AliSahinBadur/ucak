# Big_Agent

Big_Agent is a local-first report assistant for vehicle test and analysis documents. It ingests PDF, DOCX, and PPTX files, stores searchable chunks, links catalog records to report files, and answers questions with source passages.

Current version: see `app/version.py` (`APP_VERSION`)

## UI

The app now serves the SmartCAE v2 interface (`app/ui/smartcae_v2/`) at `/`. The
previous single-page UI is still available at `/app` or `/legacy`
(`app/static/`). `APP_VARIANT` (see `.env.example`, `app/branding.py`) selects
the product identity/branding; only `big_agent` (default) has a fully wired
application workspace here.

## What Works

- Folder and single-file report ingestion
- PDF, DOCX, and PPTX parsing
- Chunking, database storage, and embedding generation
- Keyword, semantic, and hybrid search
- Source-grounded Q&A
- Similar report discovery
- Excel/catalog import and catalog-to-report matching
- Report preview/open workflow for PDF, DOCX, and PPTX
- Graph view
- Duplicate report detection
- Chatbot with three modes:
  - `otomatik`: routes general chat/math to the LLM and report questions to RAG
  - `genel`: uses the local chat LLM
  - `rapor`: forces source-grounded report retrieval

## Local Data Policy

The following are intentionally not committed to GitHub:

- `data/`
- `models/`
- report files such as PDF, DOCX, PPTX, XLSX, CSV
- `.env` files

This keeps company documents, local databases, and model weights out of the repository.

## Requirements

Install Python dependencies:

```powershell
& '.venv\Scripts\python.exe' -m pip install -r requirements.txt
```

Optional embedding dependency:

```powershell
& '.venv\Scripts\python.exe' -m pip install -r requirements-embeddings.txt
```

## Run

From the project folder:

```powershell
cd path\to\ucak
& '.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## Local Network Test Login

For sharing the app with two test teams on the same local network:

```powershell
$env:APP_AUTH_ENABLED = "true"
$env:APP_USERS = "analiz:Sifre1;test:Sifre2"
$env:APP_SESSION_SECRET = "change-this-to-a-long-random-local-secret"
& '.venv\Scripts\python.exe' -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Share the IPv4 address from `ipconfig`:

```text
http://YOUR-IPV4:8000/
```

For isolated team tests, run separate app instances with separate data folders:

```powershell
# Analiz
$env:BIG_AGENT_DATA_DIR = ".\data_analiz"
$env:APP_AUTH_ENABLED = "true"
$env:APP_USERS = "analiz:Sifre1"
$env:APP_SESSION_SECRET = "change-this-to-a-long-random-local-secret"
$env:APP_AUTH_COOKIE_NAME = "big_agent_analiz"
& '.venv\Scripts\python.exe' -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

```powershell
# Test
$env:BIG_AGENT_DATA_DIR = ".\data_test"
$env:APP_AUTH_ENABLED = "true"
$env:APP_USERS = "test:Sifre2"
$env:APP_SESSION_SECRET = "change-this-to-another-long-random-local-secret"
$env:APP_AUTH_COOKIE_NAME = "big_agent_test"
& '.venv\Scripts\python.exe' -m uvicorn app.main:app --host 0.0.0.0 --port 8002
```

Share separate links:

```text
Analiz: http://YOUR-IPV4:8001/
Test: http://YOUR-IPV4:8002/
```

## Embeddings

The app auto-detects a local embedding model in `models/` when available.

Expected local model folders include:

- `models/Qwen3-Embedding-4B`
- `models/Qwen3-Embedding-0.6B`
- `models/qwen3-embedding-4b`
- `models/qwen3-embedding-0.6b`

Useful environment variables:

```powershell
$env:EMBEDDING_BACKEND = "sentence-transformers"
$env:EMBEDDING_MODEL_PATH = ".\models\Qwen3-Embedding-4B"
$env:EMBEDDING_LOCAL_FILES_ONLY = "true"
$env:EMBEDDING_DEVICE = "cpu"
```

If CUDA-enabled PyTorch is installed, the app can auto-select `cuda`; otherwise it safely falls back to CPU.

After changing embedding model/provider:

```powershell
$job = Invoke-RestMethod -Method Post http://127.0.0.1:8000/embeddings/rebuild
Invoke-RestMethod "http://127.0.0.1:8000/jobs/$($job.job_id)"
```

The rebuild (like batch ingest, catalog ingest and the duplicate scan) now runs as a
background job: the POST returns `202` with a `job_id` immediately, and
`GET /jobs/{job_id}` reports `queued/running/succeeded/failed` plus progress and the
final result. Embeddings are stored as packed `float32` BLOBs; databases written by
older versions (JSON text vectors) keep working, and one `/embeddings/rebuild` run
converts them to the new format.

## Ollama Chat LLM

General chatbot mode uses local Ollama by default:

```text
qwen2.5:3b
```

Check local Ollama models:

```powershell
ollama list
```

Useful chat LLM environment variables:

```powershell
$env:CHAT_LLM_ENABLED = "true"
$env:CHAT_LLM_BACKEND = "ollama"
$env:CHAT_LLM_MODEL_NAME = "qwen2.5:3b"
$env:OLLAMA_HOST = "http://127.0.0.1:11434"
```

Report Q&A does not require the LLM. RAG and source-grounded answers continue to work when the chat LLM is unavailable.

## Test

Run the unit and API test suite (no model, no Ollama, no network needed):

```powershell
& '.venv\Scripts\python.exe' -m pytest -q
```

`tests/conftest.py` pins the environment before `app` is imported: the database
goes to a throwaway temp directory, `EMBEDDING_BACKEND=token-hash`, and every LLM
is disabled. The `client` fixture is a `TestClient` over the real app; `db_session`
gives a clean database per test and `seed_corpus` a three-report corpus.

For a coverage report:

```powershell
& '.venv\Scripts\python.exe' -m pytest -q --cov=app --cov-report=term
```

Smoke test the running app:

```powershell
& '.venv\Scripts\python.exe' scripts\run_smoke_checks.py
```

Run the QA/search regression set:

```powershell
& '.venv\Scripts\python.exe' scripts\run_qa_checks.py
```

Expected current regression result:

```text
Summary: 22 passed, 0 failed
```

## Demo

Use `DEMO_CHECKLIST.md` for the current manager-demo flow.

Short version:

1. Show report upload and the inside-report list.
2. Show catalog search and report preview.
3. Ask: `BIG-E konfor raporunda hangi parkurlar var?`
4. Show source cards.
5. Show duplicate detection.
6. Show chatbot mode routing with `4 + 4`, `adam misin`, and a report question.
