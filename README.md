# Big_Agent MVP

This project now uses a FastAPI-based ingestion API for the first MVP sprint.

Current scope:
- PDF and DOCX ingestion
- text extraction
- text cleaning and normalization
- overlap-aware chunking
- SQLAlchemy-backed database persistence
- keyword, vector, and hybrid-ready search

## Embedding Backends

Default backend:
- `token-hash-v1`

Optional open-source backend:
- `sentence-transformers`

Environment variables:

```powershell
$env:EMBEDDING_BACKEND = "sentence-transformers"
$env:EMBEDDING_MODEL_PATH = "Qwen/Qwen3-Embedding-0.6B"
$env:EMBEDDING_DEVICE = "cpu"
```

If your network blocks Hugging Face downloads, point `EMBEDDING_MODEL_NAME` to a local model directory and force local loading:

```powershell
$env:EMBEDDING_BACKEND = "sentence-transformers"
$env:EMBEDDING_MODEL_PATH = "C:\Users\ISU34977\PyCharmMiscProject\Big_Agent\models\Qwen3-Embedding-0.6B"
$env:EMBEDDING_LOCAL_FILES_ONLY = "true"
$env:EMBEDDING_DEVICE = "cpu"
```

Recommended higher-parameter embedding model:
- `Qwen/Qwen3-Embedding-0.6B`

Why this is the current target:
- significantly larger than the old `0.1B` MiniLM setup
- sentence-transformers compatible
- better fit for multilingual retrieval upgrades

Expected local model folder names:
- `models/Qwen3-Embedding-0.6B`
- `models/Qwen3-Embedding-4B`
- `models/qwen3-embedding-0.6b`

`Qwen3-Embedding-*` models are embedding models only. They power retrieval, chunk similarity, and similar-report discovery; they must not be loaded as chat/generation models.

After changing the embedding provider, rebuild stored embeddings:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/embeddings/rebuild
```

## Optional Local LLM Layer

The app starts with LLM features disabled:

```powershell
$env:LLM_ENABLED = "false"
$env:LLM_BACKEND = "disabled"
```

With LLM disabled, ingestion, search, similar reports, catalog preview, and heuristic QA continue to work normally.

The LLM layer is optional and local-first. When enabled, query understanding can use the LLM and Q&A can generate a Turkish answer from the retrieved source chunks. If the LLM fails or is disabled, the app falls back to the existing heuristic/extractive answer flow.

Example optional Ollama configuration:

```powershell
$env:LLM_ENABLED = "true"
$env:LLM_BACKEND = "ollama"
$env:LLM_MODEL_NAME = "qwen2.5:3b"
```

LLM answer generation is intentionally gated separately because local chat models can be slow:

```powershell
$env:LLM_ANSWER_ENABLED = "true"
```

Reranking is also optional and disabled by default:

```powershell
$env:RERANKER_ENABLED = "false"
$env:RERANKER_BACKEND = "disabled"
```

## Project Structure

```text
app/
|-- db/
|-- parsers/
|-- processing/
|-- services/
`-- main.py
```

## Install

```powershell
& 'C:\Users\ISU34977\PyCharmMiscProject\.venv\Scripts\python.exe' -m pip install -r requirements.txt
```

## Run API

```powershell
& 'C:\Users\ISU34977\PyCharmMiscProject\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload
```

## Endpoints

- `GET /health`
- `POST /ingest`
- `GET /search?query=...&limit=5&mode=keyword`
- `GET /search?query=...&limit=5&mode=semantic`
- `GET /search?query=...&limit=5&mode=hybrid`
- `POST /embeddings/rebuild`

## Next Steps

- add tests for parsing, cleaning, chunking, and duplicate detection
- install and enable the Qwen embedding backend locally, then rebuild embeddings
- add similar-report suggestions at document level
"# ucak" 
