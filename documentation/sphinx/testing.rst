===============
Testing and QA
===============

There are two layers of checking in this project, and they answer different
questions:

* **the pytest suite** -- does the code still do what it says? Offline,
  deterministic, fast, and part of CI.
* **the check scripts** -- is retrieval and review still *good*? Scored against
  golden sets over a real corpus, run by hand when something changes.

The pytest suite
================

.. code-block:: powershell

   & '.venv\Scripts\python.exe' -m pytest -q

   # with coverage
   & '.venv\Scripts\python.exe' -m pytest -q --cov=app --cov-report=term

The suite needs no model, no Ollama and no network.

The conftest contract
---------------------

``tests/conftest.py`` pins the environment **at import time**, before anything
under ``app`` is imported:

.. code-block:: python

   TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="ucak-test-data-"))
   os.environ["BIG_AGENT_DATA_DIR"] = str(TEST_DATA_DIR)
   os.environ["EMBEDDING_BACKEND"] = "token-hash"
   os.environ["LLM_ENABLED"] = "false"
   # ... every other LLM and the CATIA skill disabled ...

   from app.db.session import SessionLocal, engine, init_db  # noqa: E402

This ordering is load-bearing, not stylistic. ``app/db/session.py`` builds the
engine from ``Settings`` when it is imported, and ``get_settings()`` is cached,
so a fixture body cannot redirect the database after the fact.

Two rules follow, and both are absolute:

#. **Never import ``app`` above that environment block.**
#. **Never add a test that reaches the network or loads a sentence-transformers
   model.**

At session end the engine is disposed before the temp directory is removed --
Windows will not delete a database file while a pooled connection still holds
it.

Fixtures
--------

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Fixture
     - What it gives you
   * - ``db_session``
     - A clean database per test.
   * - ``client``
     - A ``TestClient`` over the real application -- real routing, real
       retrieval, no mocks.
   * - ``seed_corpus``
     - Three Turkish reports with embeddings.
   * - ``add_document``, ``add_page``, ``add_chunk``
     - Helpers for building a corpus with known vectors. Pass
       ``AUTO_EMBEDDING`` to derive the vector from the chunk text, or ``None``
       to store no embedding at all.

What is covered
---------------

The suite spans parsing and chunking, text cleaning and normalization, ingest
and hash deduplication, the three search modes and their scoring, the vector
index, the embedding service, the Haystack retrieval service, catalog and
library services, document path and reference resolution, the job manager, the
LLM provider abstraction, OCR service behaviour, the report review rules and
profile catalog, report quality, the report writer, multi-report comparison,
chat routing, the CATIA skill service, and the API routes.

The check scripts
=================

All of them read the corpus in the **current** ``BIG_AGENT_DATA_DIR`` and print
the data directory and document count on their first line. Read that line
before reading the results -- it is the difference between checking your real
corpus and checking a demo folder you set up an hour ago.

Smoke checks
------------

.. code-block:: powershell

   & '.venv\Scripts\python.exe' scripts\run_smoke_checks.py
   & '.venv\Scripts\python.exe' scripts\run_smoke_checks.py --base-url http://127.0.0.1:8001

Hits a **running** instance and verifies the endpoints answer.

QA and retrieval regression
---------------------------

.. code-block:: powershell

   & '.venv\Scripts\python.exe' scripts\run_qa_checks.py

Beyond the pass/fail gate, this scores retrieval with the Haystack evaluators
for the in-house stack (``v2``) and the Haystack pipeline (``v3``) side by
side:

.. code-block:: text

   Summary: 22 passed, 0 failed (gate: v2)

   version     cases   recall@k      MRR     nDCG  provider
   v2             22     100.0%    0.977    0.983  token-hash-v1
   v3             22      90.9%    0.886    0.892  haystack:3.1.0

Options: ``--cases`` (a different case file), ``--k`` (recall cutoff, default
5), ``--no-metrics`` (gate only), ``--no-persist`` (do not write the run).
Each run is written to ``data/qa_runs/<timestamp>.json``, so a regression reads
as a trend rather than a single bad afternoon. The gate still runs on its own
if ``haystack-ai`` is not installed.

Portable document references
----------------------------

Cases name a **report**, not a database id. Pinning ``"document_id": 9``
resolves only against one operator's ``data/app.db``: re-ingest the corpus in a
different order and the suite silently checks the wrong reports.

A reference is one of:

.. code-block:: json

   "2025-BIG-E-NVH-01"
   {"report_code": "2025-BIG-E-NVH-01"}
   {"title_contains": ["fren", "pedal"]}
   {"document_id": 9}

``DocumentReferenceResolver`` resolves the first three through the catalog and
the document titles and file names. The last is the legacy pin, kept so an
un-migrated file still runs -- and surfaced as the portability hazard it is.

Report review regression
------------------------

.. code-block:: powershell

   & '.venv\Scripts\python.exe' scripts\run_report_review_checks.py --precision

Runs the golden set in ``test_cases/report_review_cases.json`` -- keyed by
report code, resolved the same way -- and reports the per-rule confirm rate
alongside the gate.

Other runners
-------------

.. list-table::
   :header-rows: 1
   :widths: 42 58

   * - Script
     - Purpose
   * - ``run_document_intelligence_checks.py``
     - Chat-path answering against its case file. ``--live-llm`` uses the
       configured Ollama model instead of a test provider.
   * - ``run_rag_v2_checks.py``
     - The in-house retrieval stack on its own.
   * - ``run_report_comparison_checks.py``
     - Comparison output against expectations.

The synthetic corpus
====================

For clicking through the application the way an operator would, without
touching real company documents:

.. code-block:: powershell

   & '.venv\Scripts\python.exe' scripts\generate_sample_reports.py --clean
   & '.venv\Scripts\python.exe' scripts\verify_sample_reports.py

Everything in the corpus is invented -- fictional vehicles (``SYN-Bus 12``,
``SYN-Van 3``), fictional people, report codes prefixed ``2026-SYN-`` -- so
nothing can be mistaken for a real document. It writes 16 files plus a catalog
to ``sample_reports\`` (gitignored); ``--out D:\demo`` puts them elsewhere.

Each report exercises one known part of the engine. Four are clean, one per
discipline; the rest each carry exactly one planted defect, so when a finding
appears you know whether it is the one you were looking for.
``verify_sample_reports.py`` ingests the corpus into a **throwaway** database,
prints the findings per report, and ends with::

   OK - every report matched its expectation

Use a separate data folder so the demo does not land in your working database:

.. code-block:: powershell

   $env:BIG_AGENT_DATA_DIR = ".\data_demo"

Walking the corpus
------------------

**Load it.** Sort by name so the original is ingested before its copy:

.. code-block:: powershell

   Get-ChildItem sample_reports\*.pdf, sample_reports\*.docx | Sort-Object Name | ForEach-Object {
     curl.exe -s -X POST http://127.0.0.1:8000/ingest -F "file=@$($_.FullName)"
   }

   curl.exe -s -X POST http://127.0.0.1:8000/catalog/import -F "file=@sample_reports\katalog_SYN.csv"
   curl.exe -s -X POST http://127.0.0.1:8000/catalog/reconcile-documents

15 files ingest and the copy comes back ``"status":"duplicate"`` -- caught by
its hash before parsing. The catalog import creates 15 rows and the reconcile
links each to its file. The link matters for review: the catalog's
``discipline`` column is what the ``auto`` profile reads first.

**Ask for a review.** The wording reaches the review engine only through the
intent router, which looks for ``raporu kontrol et``, ``rapor kontrolu``,
``kalite kontrolu``, ``teknik kontrol``, ``raporda hata var mi``, ``raporda
eksik var mi`` or ``rapor uygun mu``. Anything else goes to ordinary retrieval.

.. code-block:: powershell

   $body = '{"message":"Bu raporu kontrol et","document_ids":[8],"assistant_mode":"report"}'
   curl.exe -s -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d $body

**Compare revisions.** Select both revisions and satisfy two conditions at
once -- a review phrase from above, plus ``revizyon`` and a comparison verb
(``karsilastir``, ``kiyasla``, ``yeni bulgu``, ``giderilen``, ``devam eden``):

.. code-block:: text

   Bu raporu kontrol et ve revizyonlari karsilastir

``Bu iki revizyonu karsilastir`` alone does **not** work; it routes to generic
document comparison instead.

**Run the golden set against this corpus.** The shipped case file names the
real ``2025-BIG-*`` reports, so against the synthetic corpus every case reports
SKIP -- and a run where everything skipped exits non-zero rather than claiming
a green build. A companion file covers the synthetic reports:

.. code-block:: powershell

   & '.venv\Scripts\python.exe' scripts\run_report_review_checks.py `
       --cases test_cases\report_review_cases_sample.json
   # Summary: 13 passed, 0 failed, 0 skipped

**Note on semantic search.** ``mode=semantic`` returns nothing on a default
install: the ``token-hash`` fallback is a deterministic stand-in, not a real
model. ``keyword`` and ``hybrid`` work with no model at all. Point
``EMBEDDING_MODEL_PATH`` at a Qwen3 model and rebuild embeddings for real
semantic hits.

**Start over.** Delete the data folder and regenerate:

.. code-block:: powershell

   Remove-Item -Recurse -Force .\data_demo
   & '.venv\Scripts\python.exe' scripts\generate_sample_reports.py --clean

What each file is for
---------------------

.. list-table::
   :header-rows: 1
   :widths: 26 16 58

   * - File
     - Profile
     - What it should produce
   * - ``NVH-01.pdf``
     - nvh
     - clean -- every check passes
   * - ``CFD-01.pdf``
     - cfd
     - clean
   * - ``DUR-01.pdf``
     - durability
     - clean
   * - ``TEST-01.docx``
     - test
     - clean -- also exercises the DOCX parser
   * - ``NVH-02.pdf``
     - nvh
     - ``nvh.measurement_setup`` -- measurement axis never stated
   * - ``CFD-02.pdf``
     - cfd
     - ``cfd.numerical_evidence`` -- mesh given, convergence never shown
   * - ``DUR-02.pdf``
     - durability
     - ``durability.result_criterion`` -- a stress number with no acceptance
       basis
   * - ``TEST-02.pdf``
     - test
     - ``test.measurement_traceability`` at **info** -- no calibration record
   * - ``GEN-01.pdf``
     - general
     - ``metadata.required_fields`` -- no cover fields
   * - ``GEN-02.pdf``
     - test
     - ``captions.sequence`` + ``captions.title`` + ``captions.references``
   * - ``GEN-03.pdf``
     - general
     - ``numbers.decimal_style`` (comma and dot mixed) +
       ``content.embedded_paths``
   * - ``GEN-04.pdf``
     - general
     - ``extraction.no_text`` -- **status fail**, page 2 has no text layer
   * - ``GEN-05.pdf``
     - general
     - ``metadata.required_fields`` -- see the known issue below
   * - ``DUR-03-RevA/RevB.pdf``
     - durability
     - revision pair: one finding resolved between them
   * - ``NVH-01_kopya.pdf``
     - --
     - exact duplicate of ``NVH-01``

.. note::

   ``GEN-05.pdf`` reproduces a real defect on purpose. Its cover writes
   ``TARİH:`` with the Turkish dotted capital I (U+0130), and the metadata check
   misses it: ``ReportQualityService._normalize_text`` casefolds first, which
   turns ``İ`` into ``i`` plus a combining dot, and then applies a translate map
   that no longer contains U+0130 -- so ``TARİH`` normalizes to ``tari̇h`` and the
   alias ``tarih`` never matches. This affects every uppercase Turkish keyword
   containing ``İ``, real report covers included. ``app/text/normalize.py``
   already does the right thing (NFKD plus stripping combining marks), so the
   fix is to strip combining marks in ``_normalize_text`` too. The other files
   use ASCII ``TARIH`` to keep the corpus clean.

Adding a discipline review check
================================

Because discipline rules are data, adding one is a data edit plus a golden
case:

#. edit or add the file under ``app/rules/profiles/<discipline>.json``;
#. add a case to ``test_cases/report_review_cases.json`` naming a report by
   code; and
#. run ``scripts\run_report_review_checks.py``.

``profile_catalog.py`` validates every profile file at import time -- unknown
keys included -- so a typo fails the import with the file and the offending
path named, rather than becoming a rule that quietly never fires. The full file
schema, key by key, is in :ref:`profile-schema`.

Two flags are worth knowing when you are iterating on rules:

.. code-block:: powershell

   # only the per-rule confirm rate, no golden cases
   & '.venv\Scripts\python.exe' scripts\run_report_review_checks.py --precision-only

   # lower the decision floor while a rule is still young
   & '.venv\Scripts\python.exe' scripts\run_report_review_checks.py --precision --min-decisions 3

Continuous integration
======================

``.github/workflows/ci.yml`` runs on pushes to ``main`` and ``improvement`` and
on every pull request, with two jobs:

``test``
   ``uv sync --group dev`` followed by ``uv run pytest -q``, resolved against
   the committed ``uv.lock``.

``requirements``
   Installs ``requirements.txt`` on a clean Python 3.11 and imports the
   application -- the guard against ``pyproject.toml`` and ``requirements.txt``
   drifting apart.

Keep the suite offline and model-free: a test that downloads a model passes on
a workstation with a warm cache and fails in CI, which is the worst of both
worlds.
