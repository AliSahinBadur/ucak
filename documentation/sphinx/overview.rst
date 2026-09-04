========
Overview
========

What the system does
====================

Big_Agent turns a folder of engineering reports into something an engineer can
question. The pipeline is deliberately ordinary: parse, clean, chunk, embed,
retrieve, and answer only from what was retrieved. The deterministic half of
the system is the product; the language model is an optional layer on top of
it and the application stays useful when that layer is switched off.

Capabilities
============

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Area
     - What is implemented
   * - Ingestion
     - Single-file and folder ingestion of PDF, DOCX and PPTX, duplicate
       detection by file hash, selective OCR for scanned PDF pages.
   * - Processing
     - Whitespace and Unicode normalization that preserves Turkish characters,
       repeated header/footer removal, overlapping chunking.
   * - Retrieval
     - Keyword search, semantic search over stored embeddings, hybrid scoring,
       and an optional Haystack pipeline as a second retrieval implementation.
   * - Question answering
     - Source-grounded answers over one report, several reports, or the report
       catalog; every answer carries the passages it was built from.
   * - Catalog
     - Excel/catalog import, catalog-to-file matching over network shares,
       preview and open workflows, and a graph overview of the corpus.
   * - Review
     - Deterministic report-review rules with discipline profiles, human
       confirm/dismiss decisions, per-rule precision, PDF review records, and
       revision comparison.
   * - Comparison
     - Pairwise and multi-report comparison with highlighted PDF evidence.
   * - Drafting
     - A report draft builder that writes a cover block and a body grounded in
       retrieved passages, exportable as PDF.
   * - CATIA skill
     - A mass/centre-of-gravity measurement skill driven from the chat UI,
       backed by the ``skill/catia-mass-cg.skill`` package.

Product variants
================

One codebase serves three product identities, selected with ``APP_VARIANT``
(see :mod:`app.branding`):

.. list-table::
   :header-rows: 1
   :widths: 18 22 20 40

   * - Variant
     - Display name
     - Data dir env
     - Notes
   * - ``big_agent``
     - SmartCAE AI
     - ``BIG_AGENT_DATA_DIR``
     - Default. The only variant with a fully wired application workspace.
   * - ``raporhub``
     - RaporHub
     - ``RAPORHUB_DATA_DIR``
     - Landing experience served from ``app/ui/raporhub_landing``.
   * - ``repocto``
     - RepOcto
     - ``REPOCTO_DATA_DIR``
     - Landing experience plus the library browser (``POST /library/scan``).

The variant changes the API title, the browser icon, the palette and which
front end ``/`` serves. It does not change the retrieval or review engines.

User interfaces
===============

``/``
   The SmartCAE v2 workspace (``app/ui/smartcae_v2``) for the ``big_agent``
   variant, or the variant landing page otherwise.

``/app``, ``/legacy``
   The earlier single-page interface in ``app/static``. Still served, still
   functional, useful when debugging an endpoint without the newer front end.

``/docs``, ``/redoc``
   FastAPI's generated OpenAPI documentation for the live instance. This
   manual describes intent and behaviour; ``/docs`` is the authority on the
   exact schema of the version you are running.

Design rules the project holds to
=================================

These are worth stating up front, because most of the code makes more sense
once they are known.

#. **The deterministic retrieval system is the main system.** LLM features are
   layered on top and must fail soft: an unavailable model degrades an answer,
   it never breaks an endpoint.
#. **Defaults are offline.** ``LLM_ENABLED=false``, ``LLM_BACKEND=disabled``,
   ``RERANKER_ENABLED=false``. The application must start with no model
   present at all.
#. **Embedding models and generation models are separate roles.** A
   ``Qwen3-Embedding-*`` model produces retrieval vectors and nothing else; it
   is never loaded with a causal-LM head.
#. **Turkish text is first-class.** Normalization folds Turkish characters for
   matching but never destroys them in stored text.
#. **Parser, processing, database and service responsibilities stay
   separate**, and interfaces stay modular so the embedding provider or vector
   backend can be replaced.

Local data policy
=================

The following are intentionally not committed to the repository:

* ``data/`` -- the SQLite database, stored documents, job artefacts
* ``models/`` -- local embedding model weights
* report files: ``.pdf``, ``.docx``, ``.pptx``, ``.xlsx``, ``.csv``
* ``.env`` files

This keeps company documents, local databases and model weights out of version
control. Synthetic corpora produced by ``scripts/generate_sample_reports.py``
are also gitignored; see :doc:`testing`.

Version
=======

The running version is ``APP_VERSION`` in ``app/version.py``, returned by
``GET /health`` and ``GET /system/model-status``, and used as the FastAPI
application version. This manual is built against |release|.
