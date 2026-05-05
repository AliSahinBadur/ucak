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
$env:EMBEDDING_PROVIDER = "sentence-transformers"
$env:EMBEDDING_MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"
$env:EMBEDDING_DEVICE = "cpu"
```

If your network blocks Hugging Face downloads, point `EMBEDDING_MODEL_NAME` to a local model directory and force local loading:

```powershell
$env:EMBEDDING_PROVIDER = "sentence-transformers"
$env:EMBEDDING_MODEL_NAME = "C:\Users\ISU34977\PyCharmMiscProject\Big_Agent\models\Qwen3-Embedding-0.6B"
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
- `models/qwen3-embedding-0.6b`

After changing the embedding provider, rebuild stored embeddings:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/embeddings/rebuild
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
