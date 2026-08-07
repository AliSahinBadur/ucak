# SmartCAE AI

SmartCAE AI is a local-first report assistant for vehicle test and analysis documents. It ingests PDF, DOCX, and PPTX files, stores searchable chunks, links catalog records to report files, and answers questions with source passages.

Current version: `v0.50.114`

## SmartCAE AI and RaporHub

SmartCAE AI is now the canonical codebase for both products. The API, RAG, ingestion,
catalog, comparison, and report-writing services are shared. `APP_VARIANT` selects
the product identity and theme, while each instance keeps its own data directory.

Run SmartCAE AI:

```powershell
$env:APP_VARIANT = "big_agent"
$env:BIG_AGENT_DATA_DIR = "C:\Users\ISU34977\PyCharmMiscProject\Big_Agent\data"
& 'C:\Users\ISU34977\PyCharmMiscProject\.venv312\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8002
```

Run RaporHub from the same codebase in another terminal:

```powershell
$env:APP_VARIANT = "raporhub"
$env:RAPORHUB_DATA_DIR = "C:\Users\ISU34977\PyCharmMiscProject\Big_Agent\data_raporhub"
$env:APP_AUTH_COOKIE_NAME = "raporhub_session"
& 'C:\Users\ISU34977\PyCharmMiscProject\.venv312\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8003
```

The old standalone `RaporHub` folder is not modified by this setup. New shared
features should be developed here once; product-specific UI work is selected by
the variant configuration.

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
& 'C:\Users\ISU34977\PyCharmMiscProject\.venv\Scripts\python.exe' -m pip install -r requirements.txt
```

Optional embedding dependency:

```powershell
& 'C:\Users\ISU34977\PyCharmMiscProject\.venv\Scripts\python.exe' -m pip install -r requirements-embeddings.txt
```

## Run

Sabit portlarla başlatmak için:

```bat
start_big_agent.bat
start_raporhub.bat
```

SmartCAE AI `8002`, ReportHub `8003` portunda açılır. Smart AIOS klasöründeki
`start_all_apps.bat` üç uygulamayı birlikte başlatır.

From the project folder:

```powershell
cd C:\Users\ISU34977\PyCharmMiscProject\Big_Agent
& 'C:\Users\ISU34977\PyCharmMiscProject\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8002
```

Open:

```text
http://127.0.0.1:8002/
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8002/health
```

## Local Network Test Login

For sharing the app with two test teams on the same local network:

```powershell
$env:APP_AUTH_ENABLED = "true"
$env:APP_USERS = "analiz:Sifre1;test:Sifre2"
$env:APP_SESSION_SECRET = "change-this-to-a-long-random-local-secret"
& 'C:\Users\ISU34977\PyCharmMiscProject\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 0.0.0.0 --port 8002
```

Share the IPv4 address from `ipconfig`:

```text
http://YOUR-IPV4:8002/
```

For isolated team tests, run separate app instances with separate data folders:

```powershell
# Analiz
$env:BIG_AGENT_DATA_DIR = "C:\Users\ISU34977\PyCharmMiscProject\Big_Agent\data_analiz"
$env:APP_AUTH_ENABLED = "true"
$env:APP_USERS = "analiz:Sifre1"
$env:APP_SESSION_SECRET = "change-this-to-a-long-random-local-secret"
$env:APP_AUTH_COOKIE_NAME = "big_agent_analiz"
& 'C:\Users\ISU34977\PyCharmMiscProject\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 0.0.0.0 --port 8011
```

```powershell
# Test
$env:BIG_AGENT_DATA_DIR = "C:\Users\ISU34977\PyCharmMiscProject\Big_Agent\data_test"
$env:APP_AUTH_ENABLED = "true"
$env:APP_USERS = "test:Sifre2"
$env:APP_SESSION_SECRET = "change-this-to-another-long-random-local-secret"
$env:APP_AUTH_COOKIE_NAME = "big_agent_test"
& 'C:\Users\ISU34977\PyCharmMiscProject\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 0.0.0.0 --port 8012
```

Share separate links:

```text
Analiz: http://YOUR-IPV4:8011/
Test: http://YOUR-IPV4:8012/
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
$env:EMBEDDING_MODEL_PATH = "C:\Users\ISU34977\PyCharmMiscProject\Big_Agent\models\Qwen3-Embedding-4B"
$env:EMBEDDING_LOCAL_FILES_ONLY = "true"
$env:EMBEDDING_DEVICE = "cpu"
```

If CUDA-enabled PyTorch is installed, the app can auto-select `cuda`; otherwise it safely falls back to CPU.

After changing embedding model/provider:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8002/embeddings/rebuild
```

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

Smoke test the running app:

```powershell
& 'C:\Users\ISU34977\PyCharmMiscProject\.venv\Scripts\python.exe' scripts\run_smoke_checks.py
```

Run the QA/search regression set:

```powershell
& 'C:\Users\ISU34977\PyCharmMiscProject\.venv\Scripts\python.exe' scripts\run_qa_checks.py
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
