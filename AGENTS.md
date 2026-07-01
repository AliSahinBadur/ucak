# AGENTS.md

## Purpose
This project builds an MVP for intelligent engineering report search and similar-report discovery.

The first working version should:
- accept PDF and DOCX reports
- extract selectable text
- split content into meaningful chunks
- make chunks searchable
- support similar report suggestions

---

## MVP Scope

### In scope
- PDF/DOCX upload and ingest
- text extraction
- text cleaning and normalization
- chunking with overlap
- keyword search
- semantic search
- similar report listing

### Out of scope for the first version
- OCR
- image-to-text extraction
- summarization
- question-answer interface
- lessons learned extraction
- revision comparison

---

## Delivery Priority
Build the system in this order:

1. Parsing
2. Cleaning
3. Chunking
4. Database persistence
5. Basic search

Do not prioritize advanced search, OCR, or UI polish before the ingestion pipeline is stable.

---

## Architecture

### 1. Ingest Layer
Purpose:
- accept `.pdf` and `.docx`
- store files
- generate file hash
- detect duplicates
- record basic metadata

Requirements:
- duplicate files must be detected by hash
- ingestion should be idempotent where possible
- file type must be validated before parsing

### 2. Parser Layer
Purpose:
- extract page text from PDF
- extract headings, paragraphs, and tables from DOCX
- preserve page number or logical section information
- detect possible section titles when available

Requirements:
- parser output should use a consistent internal structure
- preserve Turkish characters correctly
- return empty-safe structured outputs instead of crashing on weak documents

### 3. Normalize Layer
Purpose:
- remove unnecessary whitespace
- normalize line breaks
- preserve Unicode and Turkish characters
- filter empty or very short content
- reduce repeated headers and footers

Requirements:
- avoid overly aggressive cleaning
- preserve retrieval-relevant wording
- keep both raw text and cleaned text when useful

### 4. Chunking Layer
Purpose:
- split documents into meaningful searchable pieces
- support overlap between chunks

Defaults:
- chunk size: 500-800 words
- overlap: 50-100 words

Strategy:
- **PDF**: split by page first, then split long pages into overlapping word blocks
- **DOCX**: split by heading first, then re-split very long sections if needed

Requirements:
- chunks are the main searchable unit
- chunk order must be preserved
- page range and section title should be attached when available

### 5. Indexing Layer
Purpose:
- maintain keyword search support
- maintain vector/embedding search support
- support hybrid retrieval

Target model:
`keyword score + semantic score = final retrieval score`

Requirements:
- keyword search must work even if semantic search is temporarily unavailable
- semantic search should be added only after the ingest pipeline is stable

---

## Data Model

Primary tables:
- `documents`
- `document_pages`
- `document_chunks`
- `chunk_embeddings`

Expected chunk fields:
- `document_id`
- `chunk_id`
- `page_start`
- `page_end`
- `section_title`
- `chunk_text`
- `chunk_order`

Requirements:
- duplicate files must be detected by hash
- raw text and cleaned text should both be preserved when useful
- chunks are the main searchable unit

---

## Search Flow

Expected flow:
1. clean the query
2. run keyword search
3. run semantic search
4. combine scores
5. rank the most relevant chunks
6. return document title, page, relevant passage, and similar reports

---

## LLM-Assisted RAG Direction

The existing deterministic retrieval system is the main system and must be preserved.

Optional LLM features are layered on top:
- query understanding
- Turkish/English technical term expansion
- metadata filter extraction
- grounded answer generation

Defaults:
- `LLM_ENABLED=false`
- `LLM_BACKEND=disabled`
- `RERANKER_ENABLED=false`

The app must start and remain useful without an LLM. LLM failures should fall back to the current heuristic/extractive flow.

Embedding models and generation models are separate roles:
- `Qwen3-Embedding-*` = retrieval/similarity embeddings only
- Chat/Instruct LLM = optional query support and answer generation
- Reranker = optional candidate ordering

Do not load an embedding model with `AutoModelForCausalLM`.

---

## Similar Report Strategy

Start with chunk-based similarity.

Initial approach:
- find chunks similar to the query
- aggregate strong matches at the document level

A document-centroid strategy can be added later.

---

## File Layout

```text
app/
├── parsers/
│   ├── pdf_parser.py
│   └── docx_parser.py
├── processing/
│   ├── text_cleaner.py
│   └── chunker.py
├── db/
│   ├── models.py
│   └── crud.py
├── services/
│   ├── ingest_service.py
│   └── search_service.py
└── main.py
```

---

## Engineering Rules

- Prefer simple, testable implementations over complex abstractions.
- Keep parser, processing, db, and service responsibilities separate.
- Focus on selectable text before OCR.
- Preserve Turkish characters correctly.
- Avoid overly aggressive cleaning that harms retrieval quality.
- Update README when setup or usage changes.
- Add semantic search only after the ingest pipeline is stable.
- Add logging around ingest and parsing failures.
- Keep interfaces modular so embedding provider and vector backend can change later.

---

## Minimum Testing Expectations

Add tests for:

- PDF parsing on selectable-text PDFs
- DOCX parsing with headings and paragraphs
- text cleaning behavior
- chunk creation with overlap
- duplicate detection by file hash

---

## Success Criteria for the First Demo

The MVP demo is successful if:

- 20-30 reports can be ingested
- a user can submit a query
- the system returns 5 relevant results
- each result includes document title, page, and passage
- the system can suggest 2-3 similar reports
