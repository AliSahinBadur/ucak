# Big_Agent

Big_Agent is a local-first report assistant for vehicle test and analysis documents. It ingests PDF, DOCX, and PPTX files, stores searchable chunks, links catalog records to report files, and answers questions with source passages.

Current version: `v0.50.88`

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

From the project folder:

```powershell
cd C:\Users\ISU34977\PyCharmMiscProject\Big_Agent
& 'C:\Users\ISU34977\PyCharmMiscProject\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
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
Invoke-RestMethod -Method Post http://127.0.0.1:8000/embeddings/rebuild
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
