========================
Retrieval and answering
========================

Retrieval is where most of the project's engineering lives. The contract is
simple -- given a Turkish or English question, return the chunks that actually
answer it, with the report and page they came from -- and the implementation is
tuned around one failure mode: a semantically plausible chunk from the wrong
report is worse than no answer at all.

Search modes
============

``SearchService`` (``app/services/search_service.py``) offers three modes,
selected by the ``mode`` parameter on ``GET /search``, ``POST /ask`` and
``POST /chat``.

Keyword search
--------------

Token-level scoring over chunk text, section titles, document titles and file
names. Notable behaviour:

* **Turkish folding.** Queries and text are folded through
  ``app/text/normalize.py`` (``ı`` to ``i``, ``ğ`` to ``g`` and so on) before
  matching, so a query typed without Turkish characters still hits.
* **Generic tokens are discounted.** Words that appear in almost every
  question -- ``rapor``, ``analiz``, ``hangi``, ``nedir``, ``sonuc`` and about
  thirty more -- carry little weight, so they cannot carry a match on their
  own.
* **Domain aliases expand.** ``titresim`` also matches ``nvh`` and
  ``vibration``; ``dayanim`` matches ``dur``, ``durability``; ``termal``
  matches ``thermal``, ``cfd``. The table lives in
  ``SearchService.TOKEN_ALIASES``.
* **Fuzzy scanning is bounded** to ``MAX_FUZZY_SCAN_ROWS`` (1500) rows, so a
  vague query cannot turn into a full-table scan.

Keyword search works with no model installed, and it is the mode the system
falls back to whenever semantic retrieval is unavailable.

Semantic search
---------------

The query is embedded and scored against the cached vector index with one
cosine matrix product (see :doc:`architecture`). Candidates then pass through
several gates:

.. list-table::
   :header-rows: 1
   :widths: 40 14 46

   * - Guard
     - Value
     - Purpose
   * - ``MIN_SEMANTIC_SCORE``
     - ``0.22``
     - Floor for any semantic candidate.
   * - ``MIN_SEMANTIC_NO_OVERLAP_SCORE``
     - ``0.27``
     - Higher floor when the chunk shares no query token at all.
   * - ``MAX_SEMANTIC_CANDIDATES``
     - ``500``
     - Cap on candidates carried into the scoring stage.
   * - Required-token gate
     - --
     - For identity-shaped queries (a report code, a vehicle name) the chunk
       must contain the identifying token, whatever the cosine score says.

Hybrid search
-------------

The default. Keyword and semantic results are gathered with widened limits
(``4x`` and ``3x`` the requested limit), min-max normalized within their own
result set, and combined:

.. code-block:: text

   combined = 0.45 * (keyword_score / keyword_max)
            + 0.55 * (semantic_score / semantic_max)
            + 0.15 * lexical_rerank_score      (added once per contributing side)

Then two corrections are applied:

* a chunk found **only** semantically and scoring below
  ``MIN_SEMANTIC_NO_OVERLAP_SCORE`` is zeroed out -- this is the guard against
  confident nonsense from the wrong report; and
* ``match_type`` is set to ``hybrid``, ``semantic`` or ``keyword`` according to
  which sides actually contributed.

If semantic search returns nothing, hybrid degrades cleanly to keyword results
with metadata reranking.

Metadata reranking
------------------

Whatever the mode, the final ordering passes through
``_metadata_rerank_results``, which reads the catalog text linked to each
document (report code, vehicle, discipline, year) and promotes chunks whose
document matches the identity terms of the query. This is what makes "the NVH
report for BIG-E" return chunks from that report rather than the
best-phrased passage in the corpus.

By default at most one chunk per document is returned
(``MAX_RESULTS_PER_DOCUMENT = 1``), so a five-result answer surveys five
reports instead of five paragraphs of one.

Search scope
------------

``GET /search`` takes ``search_scope``:

``content`` (default)
   Rank chunks. Each result is a passage with its page range.

``reports``
   Rank documents. ``report_search()`` aggregates chunk evidence per document
   and returns the reports themselves -- the mode behind the "find the report"
   half of the UI.

Retrieval versions
==================

``retrieval_version`` selects the retrieval implementation. It is a request
parameter, not configuration, so a single instance can be compared against
itself.

.. list-table::
   :header-rows: 1
   :widths: 12 88

   * - Version
     - Behaviour
   * - ``v1``
     - Legacy in-house path. Query and document text are embedded with the
       *same* symmetric call, and the required-token gate is applied to every
       result, not only to identity-shaped queries. Stricter, and blunter.
   * - ``v2``
     - Default in-house path. Queries use ``embed_query`` and documents
       ``embed_document``, which matters for asymmetric embedding models; the
       token gate applies only where query identity demands it.
   * - ``v3``
     - The Haystack pipeline (``HaystackRetrievalService``), built over the
       same stored chunks and vectors. It is a second opinion, not a
       replacement: if ``haystack-ai`` is not installed the endpoint answers
       ``503`` rather than silently falling back.

``run_qa_checks.py`` scores ``v2`` and ``v3`` side by side on every run; see
:doc:`testing`.

The orchestrator
================

``RetrievalOrchestrator`` is an opt-in shell around ``SearchService``, switched
on per request with ``use_query_enhancement`` and ``use_reranking`` on
``GET /search``. With both off -- the default -- behaviour is exactly
``SearchService``.

``QueryUnderstandingService``
   Produces an intent, a normalized query, expanded query variants and
   metadata filters (year range, author, software, analysis type). It has a
   deterministic implementation that runs with no model; the LLM path only
   refines what the deterministic path already produced, and any failure falls
   back to it.

``Reranker``
   ``NoOpReranker`` unless ``RERANKER_ENABLED`` is set. The shipped
   ``ScoreReranker`` reorders by combined score; the interface is a
   ``Protocol``, so a cross-encoder can be dropped in without touching
   callers.

The orchestrator returns a ``retrieval`` block alongside the results,
describing what it did -- which queries were run, what was expanded, which
provider answered. That block is the reason the feature is opt-in per request:
it makes an experiment observable.

Similar reports
===============

Two related features, both built on chunk-level similarity aggregated to the
document:

``similar_documents_for_results()``
   Given the current result set, find other documents whose chunks are close to
   the matched ones. Returned inline with every search response.

``similar_documents_for_document()``
   Given a document, find its neighbours. Used from the document detail view.

Both require ``MIN_SIMILAR_DOCUMENT_SCORE`` (0.24) and report the matched chunk
count alongside the score, so a single lucky chunk is visibly different from a
document that matches throughout.

.. _duplicate-detection:

Duplicate detection
===================

``DuplicateDetectionService`` finds *near*-duplicates -- the same report
re-exported, renamed, or re-issued with a new cover -- as opposed to the
byte-identical duplicates ingestion already rejects.

Each document is reduced to a signature: an average embedding over its chunks
plus a normalized key built from the title and file name. A candidate pair is
scored on both axes, and the recorded ``reason`` says which axis carried it:
title similarity, embedding similarity, or both.

* ``POST /duplicates/scan`` runs as a background job, takes a ``threshold``
  (default ``0.90``) and supports ``dry_run``.
* ``GET /duplicates`` lists stored pairs.
* Pairs live in ``duplicate_report_pairs`` with a ``status`` field, so a
  reviewed pair does not come back as new next scan.

Question answering
==================

Four services answer questions, each over a different scope. They share one
rule: **the answer is built from retrieved passages, and every response carries
those passages.**

``QAService``
   Single-report and general report Q&A behind ``POST /ask``. Retrieves,
   filters candidates against the question profile, and builds an extractive
   answer -- a list answer, a summary answer, or a passage answer, depending on
   what the question asks for. Guard thresholds (``MIN_ANSWER_SCORE = 0.58``,
   token-overlap and section-title minima) decide whether an answer is claimed
   at all; below them the response is honest about having found nothing.

``DocumentIntelligenceService``
   The chat path behind ``POST /chat``. It adds conversation history,
   resolution of document mentions ("in that report"), evidence selection and
   scoring, citation-coverage measurement over the generated text, and a
   grounded confidence estimate. It also routes questions that are really
   review or caption-numbering questions to ``ReportReviewService`` and
   ``ReportQualityService``.

``MultiDocumentQAService``
   ``POST /ask/multi-document``: answers across a chosen set of reports and
   detects comparison questions, returning per-document rows rather than one
   blended paragraph.

``CatalogService.answer_catalog_question``
   ``POST /ask/catalog``: answers over catalog *metadata* rather than report
   text -- counts by analysis type, comparisons between vehicles, rankings.
   See :doc:`catalog`.

Generated answers
=================

Generation is optional and constrained:

* ``AnswerGenerationService`` runs only when ``LLM_ANSWER_ENABLED`` is on and a
  provider is available, and it is given the retrieved sources, not the corpus.
* Generated text is sanitized, and citation coverage is measured against the
  supplied sources; a low-coverage answer lowers the reported confidence.
* If generation is unavailable or fails, the extractive answer that was already
  built is returned. No endpoint has an LLM on its critical path.

Chat routing
============

``POST /chat`` takes ``assistant_mode``:

.. list-table::
   :header-rows: 1
   :widths: 16 84

   * - Mode
     - Behaviour
   * - ``auto``
     - Routes per message. Small talk, arithmetic and questions about the
       application itself go to the general chat model; anything that looks
       like a report question goes to retrieval.
   * - ``general``
     - Always the local chat model. No retrieval, no sources.
   * - ``report``
     - Always source-grounded retrieval, even for a message that does not
       look like a report question.

The routing heuristics in ``app/main.py`` are deterministic string checks --
folded text, small-talk phrases, a simple arithmetic detector, report-focused
term lists. The model is never asked to decide whether to use retrieval.

The response reports what happened: ``retrieval_used``, ``retrieval_provider``,
``retrieval_version``, ``confidence`` and the trimmed ``history`` to send back
with the next turn.
