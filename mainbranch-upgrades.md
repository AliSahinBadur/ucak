# Upgrades available from mainbranch (doctest/ucak) not yet in this branch

Context: this branch (`improvement`) and `origin/main` (checked out at
`doctest/ucak`) both diverged from commit `25cf75a` ("Add start.bat - single
all-in-one setup and run script"). Since then:

- **This branch** did local hygiene work: migrated `app/config.py` to
  `pydantic-settings`, added `uv` support, a generic run script, and the CATIA
  mass/CG skill.
- **`origin/main`** grew into a multi-brand product platform (SmartCAE AI /
  RaporHub / RepOcto sharing one backend) with a large set of new report-
  intelligence features — see `doctest/ucak`'s `README.md`,
  `REPORT_REVIEW_SKILL.md`, and `WORKSTATION_SMARTAIOS.md`.

## Already applied to this branch (this session)

The **UI** has been upgraded from the old plain `app/static/` page to
mainbranch's branded SmartCAE v2 interface:

- Added `app/branding.py` (the `AppBrand` dataclass + `big_agent` / `raporhub`
  / `repocto` brand definitions) and `app/ui/` (`smartcae_v2/`,
  `raporhub_landing/`, `repocto_landing/`).
- `app/config.py`: added `APP_VARIANT` (default `big_agent`) and an
  `APP_BRAND` property, adapted to this branch's `pydantic-settings` `Settings`
  class (mainbranch itself uses flat module constants — see the "porting
  notes" caveat below).
- `app/main.py`: `/` now serves the SmartCAE v2 workspace; the old UI is still
  available, unchanged, at `/app` and `/legacy`. Added static mounts for all
  three brands, a `/favicon.ico` route, a `/system/model-status` route (with
  `_display_embedding_device` / `_embedding_runtime_status` /
  `_ollama_runtime_status`), and brand-driven colors on the login page.
- `app/api_models.py`: `HealthResponse` gained `application` and `variant`.
- `.env.example` / `README.md`: documented `APP_VARIANT`.

Not activated: the RaporHub/RepOcto **landing pages** are copied in and
routed, but their themed `/app` report workspace was not ported — switching
`APP_VARIANT` away from `big_agent` still shows the plain legacy workspace at
`/app`, not a RaporHub/RepOcto-skinned one. That workspace only exists as part
of mainbranch's much larger `app/main.py` (see below).

## Backend feature upgrades still on mainbranch only

1. **Report Review workflow** — `app/services/report_review_service.py`
   (~1975 lines, the single largest addition). Runs rule-based
   compliance/quality checks against ingested reports and now feeds findings
   into chat/QA answers (`AnswerSourceResponse` gained ~14 `review_*` /
   `human_decision*` fields). Adds a `ReportReviewDecision` DB model
   (open/confirmed/dismissed per finding, with reviewer + note), a PDF export
   (`report_review_export_service.py`, ~213 lines, via `reportlab` — already a
   dependency here), and endpoints `POST /report-review/decisions`,
   `GET /report-review/export`, `GET /documents/{id}/review-preview`.
   Documented in `REPORT_REVIEW_SKILL.md`.

2. **Report Quality Service** — `app/services/report_quality_service.py`
   (~306 lines). Checks figure/table caption numbering consistency across a
   report. Heavily tested (`tests/test_report_quality_service.py`, 558 lines).

3. **OCR pipeline** — `app/services/ocr_service.py`'s `SelectiveOCRService`
   (~185 lines). Runs local Tesseract only on PDF pages with too little
   selectable text. Touches `app/parsers/pdf_parser.py`,
   `app/schemas.py` (`ParsedSection`/`CleanSection` gain `extraction_method`
   /`ocr_attempted`), and `IngestResponse`/`BatchIngestItemResponse` (new
   `ocr_pages` field). Needs new settings (`OCR_ENABLED`, `OCR_LANGUAGES`,
   `OCR_DPI`, `OCR_MIN_TEXT_CHARACTERS`, `OCR_TESSDATA_DIR`,
   `OCR_TESSERACT_CMD`) and a local Tesseract install.

4. **Haystack-based retrieval ("v3")** —
   `app/services/haystack_retrieval_service.py` (~483 lines). Adds a third
   `retrieval_version` option (`"v1"|"v2"|"v3"`) to `/chat` and `/ask`.
   Requires the new `haystack-ai>=3.0.0,<4.0.0` dependency.

5. **Multi-document comparison** — extends
   `app/services/report_comparison_service.py` (+271 lines) with
   `"reference"` vs `"all_pairs"` comparison modes across more than two
   documents, topic-row diffing with evidence excerpts, and a new
   `POST /report-comparison/multi` endpoint
   (`ReportComparisonMultiRequest`/`Response`).

6. **Document library browsing** — `app/services/library_service.py`
   (~194 lines). Read-only, bounded directory-tree browser for PDF/DOCX/PPTX
   under allow-listed roots, exposed via `POST /library/scan`. Needs
   `REPOCTO_LIBRARY_ROOTS` config; only useful once a library UI panel exists.

7. **Document path resolution** — `app/services/document_path_service.py`
   (~33 lines). Re-resolves a stored document's file path if the data/report
   root has moved. Small, self-contained, no new dependencies — a good
   candidate to port on its own regardless of the rest. Backs the new
   `/documents/{id}/open-folder` and `/documents/{id}/preview` endpoints.

8. **Supporting tweaks** across `document_intelligence_service.py` (+217),
   `llm_provider.py` (+39), `qa_service.py`, `search_service.py`,
   `storage_service.py`, `pdf_highlight_service.py`,
   `general_chat_service.py`, `ingest_service.py` — mostly wiring the features
   above into the existing QA/chat pipeline.

9. **Chat routing refactor** (small, easy win, no new deps): mainbranch pulled
   the `assistant_mode == "general" or (...)` condition in `/chat` out into a
   standalone `_should_use_general_chat(assistant_mode, message)` helper next
   to the existing `_is_general_chat_message`, making it independently
   testable (`tests/test_chat_routing.py`).

10. New dependencies needed to adopt the above:
    `haystack-ai>=3.0.0,<4.0.0`, `pymupdf>=1.25.0`
    (`reportlab>=4.0.0` is already in this branch's `requirements.txt`).

11. New run scripts: `start_big_agent.bat`, `start_raporhub.bat`,
    `start_repocto.bat` (this branch instead uses `run-generic.bat` + `uv`).

12. New docs not reconciled here: `REPORT_REVIEW_SKILL.md`,
    `WORKSTATION_SMARTAIOS.md`, `README1.md`.

13. New tests with no equivalent here yet: `test_app_variants.py`,
    `test_chat_routing.py`, `test_document_path_service.py`,
    `test_haystack_retrieval_service.py`, `test_library_service.py`,
    `test_llm_provider.py`, `test_ocr_service.py`,
    `test_report_comparison_multi.py`, `test_report_quality_service.py`,
    `test_smartcae_v2.py`, `test_system_model_status.py`.

## Porting notes / gotchas

- Mainbranch's `app/config.py` is the old flat, `os.getenv()`-per-module-
  constant style (`APP_VARIANT`, `EMBEDDING_PROVIDER`, etc. as bare module
  attributes) and its own tests import them that way
  (`from app.config import APP_VARIANT`). This branch's `config.py` was
  migrated to a `pydantic-settings` `Settings` class
  (`settings = get_settings(); settings.EMBEDDING_PROVIDER`). Porting
  mainbranch's tests or services verbatim will need this adjustment — the
  UI-support code added this session (`_embedding_runtime_status`,
  `_ollama_runtime_status`, `APP_BRAND` property) already does it.
- `app/ui/variant_styles.py` and `app/ui/repocto_styles.py` were **not**
  ported — they only feed mainbranch's old inline-HTML "legacy" template
  (a giant string embedded in `app/main.py`, superseded here by the existing
  `app/static/` files), so they'd be dead code without also inlining that
  template.

## Suggested order if picking this up

1. `document_path_service` (self-contained, no new deps).
2. `_should_use_general_chat` refactor (trivial, improves testability).
3. OCR pipeline (needs a local Tesseract install).
4. Report Quality + Report Review + export (largest and most interdependent —
   do together).
5. Haystack retrieval v3 (heavier dependency, `haystack-ai`).
6. Multi-document comparison.
7. `library_service` / `REPOCTO_LIBRARY_ROOTS` (only pays off once a
   RaporHub/RepOcto-style library panel exists in this branch's UI).
