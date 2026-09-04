==================
HTTP API reference
==================

The running instance publishes its own schema at ``/docs`` (Swagger UI) and
``/redoc``, generated from the pydantic models in ``app/api_models.py``. That
is the authority on exact field types for the version you have. This chapter is
the map: what exists, what it is for, and the parameters that matter.

Conventions
===========

* Request bodies are JSON unless the endpoint takes a file, in which case it is
  ``multipart/form-data``.
* Long operations return ``202`` with a job record; poll ``GET /jobs/{job_id}``.
  See :ref:`jobs-api`.
* When authentication is enabled, every endpoint except ``/health``,
  ``/login``, ``/logout`` and ``/favicon.ico`` requires the session cookie.
  An HTML ``GET`` without one redirects to ``/login``; anything else gets
  ``401``.
* Errors are FastAPI's ``{"detail": "..."}``.

System
======

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Endpoint
     - Description
   * - ``GET /health``
     - ``{status, version, application, variant}``. Never requires auth --
       this is the endpoint a monitor should watch.
   * - ``GET /system/model-status``
     - Runtime state of the embedding provider and Ollama: resolved model
       name, device, availability.
   * - ``GET /meta``
     - Branding and variant metadata for the front end.
   * - ``GET /login``, ``POST /login``, ``GET /logout``
     - The session login flow.
   * - ``GET /``, ``/app``, ``/legacy``, ``/smartcae-v2``
     - The user interfaces.

Ingestion
=========

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Endpoint
     - Description
   * - ``POST /ingest``
     - One ``file`` (PDF, DOCX, PPTX). Returns ``IngestResponse`` with
       ``status`` ``ingested`` or ``duplicate``. ``400`` for an unsupported
       extension.
   * - ``POST /ingest/batch``
     - Many ``files``. Returns ``202`` and a job whose result is a
       ``BatchIngestResponse`` with a per-file item list.

Search and question answering
=============================

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Endpoint
     - Parameters
   * - ``GET /search``
     - ``query`` (min 2 chars), ``limit`` 1-20 (default 5), ``mode``
       ``keyword``/``semantic``/``hybrid`` (default ``hybrid``),
       ``search_scope`` ``content``/``reports`` (default ``content``),
       ``use_query_enhancement``, ``use_reranking``. Returns results, similar
       documents, the embedding provider, and a ``retrieval`` block when the
       orchestrator ran.
   * - ``POST /ask``
     - ``question``, ``mode``, ``limit`` 1-10, ``document_id``,
       ``use_llm_answer``. Returns the answer, ``answer_found``,
       ``confidence`` and the sources.
   * - ``POST /chat``
     - ``message``, ``history``, ``mode``, ``assistant_mode``
       (``auto``/``report``/``general``), ``retrieval_version``
       (``v1``/``v2``/``v3``), ``limit``, ``document_id``, ``document_ids``
       (up to 8), ``use_llm_answer``. Returns the answer, sources, the trimmed
       history, and what retrieval did. ``503`` when ``v3`` is requested and
       Haystack is unavailable.
   * - ``POST /ask/catalog``
     - ``question``, ``limit`` 1-100. Answers from catalog metadata.
   * - ``POST /ask/multi-document``
     - ``question``, optional ``catalog_question``, ``mode``, ``limit`` 1-12,
       ``document_ids``. Detects comparison questions and answers per
       document.

Documents
=========

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Endpoint
     - Description
   * - ``GET /documents/list``
     - ``limit`` 1-500 (default 300). The ingested corpus.
   * - ``GET /documents/{id}``
     - An HTML detail page: pages, chunks, extraction quality, similar
       reports.
   * - ``GET /documents/{id}/file``
     - The stored file itself.
   * - ``GET /documents/{id}/preview``
     - Rendered preview of ``page`` (default 1).
   * - ``GET /documents/{id}/review-preview``
     - Preview with the findings of one ``rule_id`` highlighted.
   * - ``POST /documents/{id}/open-folder``
     - Opens the containing folder on the **server** (Windows).
   * - ``GET /storage/check``
     - Documents whose stored file can no longer be resolved.

Duplicates and comparison
=========================

.. list-table::
   :header-rows: 1
   :widths: 44 56

   * - Endpoint
     - Description
   * - ``GET /duplicates``
     - Stored near-duplicate pairs, ``limit`` 1-500.
   * - ``POST /duplicates/scan``
     - ``threshold`` 0.1-1.0 (default 0.90), ``dry_run``. Returns ``202`` and
       a job.
   * - ``POST /report-comparison/upload``
     - Stage a file for comparison without ingesting it; returns an
       ``upload_token``.
   * - ``POST /report-comparison``
     - ``left``/``right`` (each ``document_id`` or ``upload_token``),
       ``use_llm``.
   * - ``POST /report-comparison/multi``
     - ``sources`` (2+), ``mode`` ``reference``/``all_pairs``,
       ``reference_index``, ``use_llm``.
   * - ``GET /report-comparison/{id}/pdf/{side}``
     - The highlighted PDF for ``left`` or ``right``.
   * - ``GET /report-comparison/{id}/viewer``
     - Full-screen two-pane viewer.

Report review
=============

.. list-table::
   :header-rows: 1
   :widths: 44 56

   * - Endpoint
     - Description
   * - ``POST /report-review/decisions``
     - Record a human ``confirmed``/``dismissed``/``open`` decision against a
       ``finding_key``, with an optional note and reviewer.
   * - ``GET /report-review/rule-precision``
     - Confirm rate per rule. ``minimum_decisions`` overrides the default
       floor of 10; ``document_ids`` narrows the scope.
   * - ``GET /report-review/export``
     - PDF review record for the given ``document_ids`` (repeatable
       parameter).

Findings themselves are returned inline with the answers from ``POST /chat``
when the question is a review question; see :ref:`report-review`.

Catalog
=======

.. list-table::
   :header-rows: 1
   :widths: 46 54

   * - Endpoint
     - Description
   * - ``POST /catalog/import``
     - Import an ``.xlsx``/CSV/TSV register.
   * - ``GET /catalog/search``
     - ``query``, ``vehicle``, ``discipline``, ``limit`` 1-100.
   * - ``GET /catalog/table``
     - The register with ingestion state, ``limit`` 20-5000.
   * - ``POST /catalog/reconcile-documents``
     - Re-check catalog-to-document links; ``dry_run``.
   * - ``GET /catalog/{id}/file-candidates``
     - Candidate files for a catalog row.
   * - ``GET /catalog/{id}/file-preview``
     - Preview a named ``file_path`` candidate.
   * - ``GET /catalog/{id}/best-file-preview``
     - Preview the best candidate.
   * - ``GET /catalog/{id}/best-file-preview-info``
     - Metadata for that candidate.
   * - ``POST /catalog/{id}/open-best-file``
     - Open it on the server.
   * - ``POST /catalog/ingest-candidate``
     - Ingest ``{catalog_entry_id, file_path}``.
   * - ``POST /catalog/ingest-sample``
     - ``per_discipline`` 1-10 (default 2), ``dry_run`` (default **true**),
       ``scan_limit_per_discipline`` 1-500. Returns ``202``.
   * - ``POST /catalog/ingest-selected``
     - ``{catalog_entry_ids: [...]}``. Returns ``202``.
   * - ``GET /graph/overview``
     - Corpus graph, ``limit`` 20-300 (default 160).
   * - ``POST /library/scan``
     - ``{path, limit}`` -- bounded read-only file tree inside the allowed
       roots.

Drafting
========

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Endpoint
     - Description
   * - ``POST /draft-report``
     - Cover fields plus ``objective``, ``keywords``, ``raw_notes``,
       ``detail_level`` (``quick``/``detailed``), ``mode``, ``limit``,
       ``document_ids``. Returns the draft, the refined keywords, the cleaned
       notes and the sources.
   * - ``POST /draft-report/pdf``
     - The same payload, rendered as a PDF download.

CATIA skill
===========

``GET /skills/catia-mass-cg/status``, ``POST /skills/catia-mass-cg/chat`` and
``POST /skills/catia-mass-cg/approve`` -- see :doc:`catia_skill`.

.. _jobs-api:

Jobs and maintenance
====================

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Endpoint
     - Description
   * - ``POST /embeddings/rebuild``
     - Re-embed every chunk with the active provider. ``202`` + job.
   * - ``GET /jobs``
     - The most recent job records, ``limit`` 1-100 (default 20).
   * - ``GET /jobs/{job_id}``
     - One job: ``status`` (``queued``/``running``/``succeeded``/``failed``),
       ``progress`` ``{done, total, message}``, ``result`` or ``error``, and
       the created/started/finished timestamps.

A typical job flow:

.. code-block:: powershell

   $job = Invoke-RestMethod -Method Post http://127.0.0.1:8000/embeddings/rebuild
   Invoke-RestMethod "http://127.0.0.1:8000/jobs/$($job.job_id)"

Examples
========

Search:

.. code-block:: powershell

   Invoke-RestMethod "http://127.0.0.1:8000/search?query=fren+pedali&mode=hybrid&limit=5"

Ingest a file:

.. code-block:: powershell

   $form = @{ file = Get-Item .\rapor.pdf }
   Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/ingest -Form $form

Ask a grounded question:

.. code-block:: powershell

   $body = @{
       message        = "BIG-E konfor raporunda hangi parkurlar var?"
       assistant_mode = "report"
       limit          = 5
   } | ConvertTo-Json

   Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat `
       -ContentType "application/json" -Body $body

Record a review decision:

.. code-block:: powershell

   $body = @{
       document_id = 12
       finding_key = "9f2c1a77b3e40d18"
       rule_id     = "captions.sequence"
       decision    = "confirmed"
       note        = "Tablo 4 gercekten atlanmis."
       reviewer    = "analiz"
   } | ConvertTo-Json

   Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/report-review/decisions `
       -ContentType "application/json" -Body $body
