============
Architecture
============

Shape of the system
===================

Big_Agent is a single FastAPI process over a single SQLite file. There is no
message broker, no worker fleet and no external index: background work runs in
an in-process thread pool, and the vector index is a NumPy matrix rebuilt from
the database when it goes stale. That is a deliberate constraint -- the
application has to be installable on one engineer's workstation by copying a
folder.

.. code-block:: text

   HTTP client (SmartCAE v2 UI, legacy UI, scripts, other machines on the LAN)
        |
        v
   +---------------------------------------------------------------+
   | app/main.py -- FastAPI: routes, auth middleware, OpenAPI       |
   +---------------------------------------------------------------+
        |                   |                      |
        v                   v                      v
   +-----------+    +----------------+    +----------------------+
   | parsers   |    | services       |    | job_manager          |
   | pdf/docx/ |    | ingest, search |    | background jobs      |
   | pptx      |    | qa, review ... |    | (thread pool)        |
   +-----------+    +----------------+    +----------------------+
        |                   |                      |
        v                   v                      |
   +-----------+    +----------------+             |
   | processing|    | vector_index   |             |
   | clean,    |    | NumPy matrix   |             |
   | chunk     |    | + cache stamp  |             |
   +-----------+    +----------------+             |
        |                   |                      |
        +---------+---------+----------------------+
                  v
        +--------------------------+
        | db: SQLAlchemy + SQLite  |
        | data/app.db (WAL)        |
        +--------------------------+
                  |
                  v
        data/documents/  -- stored report files, named by hash

Package map
===========

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Module
     - Responsibility
   * - ``app/main.py``
     - Every HTTP route, the auth middleware, the OpenAPI customization and
       the chat-routing heuristics. The only module that knows about requests.
   * - ``app/config.py``
     - ``Settings`` -- the single source of configuration. See
       :doc:`configuration`.
   * - ``app/branding.py``
     - ``AppBrand`` records: display name, initials, palette, cookie and data
       directory defaults per product variant.
   * - ``app/version.py``
     - ``APP_VERSION``, reported by ``/health`` and used as the FastAPI
       application version.
   * - ``app/schemas.py``
     - The internal pipeline dataclasses: ``ParsedSection``, ``CleanSection``,
       ``ChunkPayload``. Not HTTP models.
   * - ``app/api_models.py``
     - The pydantic request and response models for the HTTP layer.
   * - ``app/db/``
     - ``models.py`` (ORM tables) and ``session.py`` (engine, pragmas,
       additive schema evolution, the ``get_session`` dependency).
   * - ``app/parsers/``
     - One function per input format, all returning ``list[ParsedSection]``.
   * - ``app/processing/``
     - ``text_cleaner`` (normalize, drop repeated headers/footers),
       ``chunker`` (overlapping word blocks), ``extraction_metrics``
       (per-page quality rollup).
   * - ``app/text/normalize.py``
     - Turkish-aware folding and tokenization shared by search, catalog
       matching and review rules.
   * - ``app/rules/``
     - ``profile_catalog.py`` plus one JSON file per discipline under
       ``profiles/``. Discipline rules are data, not code.
   * - ``app/services/``
     - Everything else: ingest, search, retrieval, QA, catalog, review,
       comparison, drafting, duplicates, graph, jobs, the CATIA bridge.
   * - ``app/ui/``, ``app/static/``
     - Front ends: SmartCAE v2 workspace, the two landing pages, and the
       legacy single-page UI.

Request lifecycle
=================

#. **Lifespan.** ``init_db()`` runs once at startup: ``create_all`` plus the
   additive column check described below.
#. **Auth middleware.** When ``APP_AUTH_ENABLED`` is on, every request except
   ``/health``, ``/login``, ``/logout`` and ``/favicon.ico`` -- plus the
   landing page for the ``raporhub`` and ``repocto`` variants -- must carry a
   valid signed session cookie. An HTML ``GET`` without one is redirected to
   ``/login``; anything else gets ``401``.
#. **Route.** Routes are ordinary ``def`` functions, so Starlette runs them in
   its thread pool. That is why the SQLite engine is built with
   ``check_same_thread=False`` and a 30-second busy timeout.
#. **Session dependency.** ``get_session`` yields a ``SessionLocal`` and closes
   it in a ``finally`` block. Services take the session as a constructor
   argument -- they never open their own, except inside background jobs.
#. **Response model.** Almost every route declares a response model from
   ``app/api_models.py``, which is what makes the generated OpenAPI schema
   worth reading.

Database engine
===============

SQLite is used with settings chosen for a multi-threaded single process:

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Setting
     - Why
   * - ``check_same_thread=False``
     - Routes run in a thread pool, so connections cross threads.
   * - ``timeout=30`` / ``PRAGMA busy_timeout=30000``
     - A writer waits out a concurrent write instead of failing with
       "database is locked" at the 5-second default.
   * - ``PRAGMA journal_mode=WAL``
     - Readers keep working during writes -- important while a batch ingest
       job is running.
   * - ``PRAGMA synchronous=NORMAL``
     - Throughput, accepting the usual WAL durability trade-off.
   * - ``autoflush=False``
     - Services decide when to flush; ingest depends on explicit flush points
       to obtain generated ids.

.. _schema-evolution:

Schema evolution without a migration tool
=========================================

The project carries no migration framework, and ``create_all`` only creates
missing *tables*, never missing columns. A workstation whose ``data/app.db``
predates a column would fail every query that selects it.

``app/db/session.py`` therefore keeps an explicit map of columns added to
tables that already shipped, and ``init_db()`` adds any that are absent with
``ALTER TABLE``:

.. code-block:: python

   _SQLITE_ADDED_COLUMNS = {
       "documents": {"extraction_quality": "JSON"},
       "document_pages": {
           "extraction_method": "VARCHAR(32)",
           "ocr_attempted": "BOOLEAN",
           "char_count": "INTEGER",
           "word_count": "INTEGER",
       },
   }

Two rules make this safe, and both must hold for any future entry:

* every added column stays **nullable and default-free** -- the rows already on
  disk have no value to backfill; and
* **readers treat NULL as "unknown"**, never as a synthesized value. A page
  with ``extraction_method IS NULL`` was ingested before provenance existed; it
  is not "native with empty text".

Background jobs
===============

Long operations return immediately instead of holding an HTTP connection open.
``JobManager`` (``app/services/job_manager.py``) is a small in-process
scheduler over a ``ThreadPoolExecutor`` with a **single worker**, so jobs run
one at a time and never contend for the SQLite write lock.

.. code-block:: text

   POST /ingest/batch        -> 202 {"job_id": ..., "status": "queued"}
   POST /catalog/ingest-sample
   POST /catalog/ingest-selected
   POST /duplicates/scan
   POST /embeddings/rebuild

   GET  /jobs/{job_id}       -> queued | running | succeeded | failed
                                + progress {done, total, message}
                                + result (on success) or error (on failure)
   GET  /jobs                -> the most recent records

A job body receives a ``JobContext`` and calls ``context.set_progress(done,
total, message)`` as it advances. Jobs open their **own** session
(``SessionLocal()``) and close it themselves: the request-scoped session is
gone by the time the job runs. Finished records are pruned so the list stays
bounded.

Vector index
============

Semantic search does not query embeddings row by row. ``app/services/
vector_index.py`` loads all stored vectors into one NumPy matrix, normalizes
it once, and answers a query with a single matrix product.

The cache is stamped with a cheap signature over ``chunk_embeddings``: the row
count, the maximum chunk id and the sum of chunk ids. That triple changes
whenever an embedding is added, removed or replaced, so a reader is never
served a stale matrix even if nobody invalidated it. Writers still call
``invalidate_vector_index()`` after a commit -- ingest and the embedding
rebuild both do -- to drop the matrix eagerly.

Embeddings are stored as packed little-endian ``float32`` bytes. Databases
written by older versions hold JSON text in the same column;
``EmbeddingService.deserialize`` accepts both, and one ``/embeddings/rebuild``
run converts them.

Service composition
===================

Services are plain classes constructed per request with an explicit session,
and they compose by construction rather than by inheritance:

.. code-block:: text

   DocumentIntelligenceService     -- chat/report answering
     +-- SearchService             -- keyword / semantic / hybrid
     |     +-- EmbeddingService    -- token-hash | sentence-transformers
     |     +-- VectorIndex         -- cached NumPy matrix
     +-- HaystackRetrievalService  -- the v3 retrieval implementation
     +-- ReportReviewService       -- rule findings, when the question asks
     +-- ReportQualityService      -- caption/numbering questions
     +-- LLMProvider               -- optional generation

   RetrievalOrchestrator           -- opt-in enhancement shell
     +-- QueryUnderstandingService -- intent, expansions, metadata filters
     +-- SearchService
     +-- Reranker                  -- no-op unless enabled

Every optional dependency has a null implementation (``NoOpReranker``, a
disabled ``LLMProvider``, the ``token-hash`` embedding service), which is how
the application keeps working with nothing installed.
