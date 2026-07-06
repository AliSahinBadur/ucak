# Big_Agent Demo Checklist

Use this checklist for a short, safe demo. Keep the app open at:

```text
http://127.0.0.1:8000/
```

## 1. Opening

Say:

```text
Big_Agent is a local report assistant. It reads vehicle test reports, indexes their content, connects catalog records to report files, and answers questions with source passages.
```

Show:

- Version badge
- Module buttons
- Raporlar / Katalog / Arama / Chatbot / Mukerrer

## 2. Report Pool

Open `Raporlar`.

Show:

- Single report upload area
- Folder upload area
- Inside reports list

Message:

```text
The important part is not only uploading files. The system keeps an internal report pool that can be searched and used for Q&A.
```

## 3. Catalog Workflow

Open `Katalog`.

Show:

- Catalog records
- Pending/inside report separation
- Preview/open report action

Message:

```text
The Excel catalog gives metadata and paths. Big_Agent resolves report folders and finds PDF, DOCX, or PPTX files inside them.
```

## 4. Source-Grounded Report Q&A

Open `Chatbot`.

Mode: `otomatik`

Ask:

```text
BIG-E konfor raporunda hangi parkurlar var?
```

Expected:

- Answer mentions BozukYol, Arnavut Kaldirim, Otoban
- Source cards appear on the right
- Provider is `sentence-transformers...`

Message:

```text
For report questions, the chatbot routes to RAG and keeps sources visible.
```

## 5. General Chat Routing

Still in `Chatbot`.

Mode: `otomatik`

Ask:

```text
4 + 4
```

Expected:

- Answer is 8
- Provider is `chat-llm:ollama:qwen2.5:3b`
- No source cards

Ask:

```text
adam misin
```

Expected:

- Direct assistant identity answer
- Provider is `chat-direct`

Message:

```text
Automatic mode separates normal chat, simple math, identity questions, and report questions.
```

## 6. Duplicate Detection

Open `Mukerrer`.

Show:

- Existing duplicate candidates
- Scan/refresh flow

Message:

```text
Duplicate detection is stored so it does not need to be recomputed manually every time.
```

## 7. Closing

Say:

```text
The current system is a working local RAG assistant. The next step is product hardening: cleaner UI, stronger test coverage, and deployment/run documentation.
```

## Quick Pre-Demo Test

Before presenting, run:

```powershell
& 'C:\Users\ISU34977\PyCharmMiscProject\.venv\Scripts\python.exe' scripts\run_smoke_checks.py
& 'C:\Users\ISU34977\PyCharmMiscProject\.venv\Scripts\python.exe' scripts\run_qa_checks.py
```

Expected:

```text
Smoke checks: all pass
QA checks: 22 passed, 0 failed
```
