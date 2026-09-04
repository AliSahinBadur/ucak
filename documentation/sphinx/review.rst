======================================
Report review, comparison and drafting
======================================

Three features share a theme: they look at reports as *documents to be
checked*, not as a corpus to be searched.

.. _report-review:

Report review
=============

The review skill inspects a technical report before it reaches a human
reviewer. It does not re-solve the CAE analysis and it never certifies physical
correctness. What it does is check that the report says what a report of its
discipline is expected to say, and show the evidence for every complaint.

Findings
--------

Every rule produces zero or more findings with a fixed shape:

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Field
     - Meaning
   * - ``rule_id``
     - Stable identifier, e.g. ``captions.sequence`` or ``nvh.measurement_setup``.
   * - ``category``
     - ``structure``, ``captions``, ``numbers``, ``extraction``, ``content``,
       or the discipline name.
   * - ``severity``
     - ``critical``, ``warning`` or ``info``.
   * - ``status``
     - The engine's verdict, e.g. ``needs_review``.
   * - ``message`` / ``suggested_fix``
     - What is wrong, and what to do about it.
   * - ``evidence``
     - The quoted lines the finding rests on, page-prefixed.
   * - ``page_start`` / ``page_end``
     - Where in the report, used to drive the highlighted PDF preview.
   * - ``engine``
     - ``rules`` or ``semantic``.
   * - ``finding_key``
     - A hash over the identifying parts of the finding. It is what a human
       decision is recorded against, so the same finding on a re-run keeps its
       decision.

Deterministic rules
-------------------

These run with no model and apply to every report:

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - Rule
     - Checks
   * - ``metadata.required_fields``
     - Cover fields: report number, date, prepared by, checked by.
   * - ``structure.required_sections``
     - Presence of a scope section and a results/conclusion section.
   * - ``captions.sequence``
     - Table and figure numbering runs in order with no gaps or repeats.
   * - ``captions.title``
     - Every table and figure caption actually has a title.
   * - ``captions.references``
     - Captions are referenced from the body text, and references resolve.
   * - ``numbers.decimal_style``
     - Decimal separators are used consistently in measured values.
   * - ``extraction.no_text``
     - Pages whose text could not be read at all.
   * - ``extraction.ocr_low_quality``
     - Pages where OCR produced text of doubtful quality.
   * - ``content.embedded_paths``
     - Local or network file paths left in the report body.

The last two categories are why extraction provenance is stored per page: a
report the engine cannot read is a finding about the *report*, not a silent
gap in the review.

Discipline profiles
-------------------

Discipline rules are **data, not code**. One JSON file per discipline lives in
``app/rules/profiles/``:

.. list-table::
   :header-rows: 1
   :widths: 24 20 56

   * - File
     - Label
     - Rules
   * - ``nvh.json``
     - NVH
     - Measurement setup, signal processing, result interpretation.
   * - ``cfd.json``
     - CFD
     - Solution model and boundary conditions, mesh, convergence.
   * - ``durability.json``
     - Durability
     - Material definition, loads and supports, mesh, contacts,
       result-to-criterion link.
   * - ``test.json``
     - Test / Validasyon
     - Test object and configuration, equipment, conditions, procedure,
       acceptance decision, calibration.

Every discipline rule runs through one generic handler: each
``requirement_groups`` entry must be mentioned somewhere in the report by at
least one of the wordings it lists, and the groups that are not mentioned are
named in the finding message.

.. _profile-schema:

The profile file schema
-----------------------

.. code-block:: json

   {
     "profile": "nvh",
     "label": "NVH",
     "detect_priority": 10,
     "aliases": ["nvh", "noise vibration harshness"],
     "detect_patterns": ["\\bnvh\\b", "titresim"],
     "rules": [
       {
         "rule_id": "nvh.measurement_setup",
         "label": "NVH olcum duzeni ve kosullari",
         "category": "nvh",
         "severity": "warning",
         "message": "NVH olcum duzeni raporda tam izlenemiyor.",
         "suggested_fix": "Sensoru ve olcum noktasini, eksenleri ve her olcumdeki calisma kosulunu yazin.",
         "requirement_groups": [
           {
             "label": "olcum noktasi / sensor",
             "aliases": ["sensor", "ivmeolcer", "akselerometre"]
           }
         ]
       }
     ]
   }

Top-level keys -- all six required, no others accepted:

.. list-table::
   :header-rows: 1
   :widths: 24 18 58

   * - Key
     - Type
     - Meaning and constraints
   * - ``profile``
     - string
     - Must equal the file name without ``.json``. ``general`` and ``auto``
       are reserved for the built-in profiles.
   * - ``label``
     - string
     - The profile name shown in the interface.
   * - ``detect_priority``
     - integer
     - Order in which ``auto`` tries the identity patterns; lower goes first.
       A profile whose patterns are broad belongs later in the sequence.
   * - ``aliases``
     - list of strings
     - Non-empty, no duplicates. What a catalog discipline value may say to
       select this profile.
   * - ``detect_patterns``
     - list of strings
     - Non-empty regular expressions, each compiled at load time, matched
       against the report identity when no catalog discipline settles it.
   * - ``rules``
     - list of objects
     - Non-empty. The rules below.

Each entry in ``rules`` -- again all seven keys required, no others accepted:

.. list-table::
   :header-rows: 1
   :widths: 26 18 56

   * - Key
     - Type
     - Meaning and constraints
   * - ``rule_id``
     - string
     - Must start with ``<profile>.``. That prefix is what keeps ids unique
       across files without a global registry; a collision with a built-in or
       semantic rule id is rejected.
   * - ``label``
     - string
     - Non-empty. The rule name in the interface.
   * - ``category``
     - string
     - Non-empty. Groups the finding, conventionally the discipline name.
   * - ``severity``
     - string
     - Exactly one of ``critical``, ``warning``, ``info``.
   * - ``message``
     - string
     - Non-empty. What the reader is told when a group is missing.
   * - ``suggested_fix``
     - string
     - Non-empty. What to do about it.
   * - ``requirement_groups``
     - list of objects
     - Non-empty, with distinct ``label`` values. Each is
       ``{"label": ..., "aliases": [...]}``, the aliases being a non-empty,
       duplicate-free list of the wordings that count as mentioning the thing.

An alias may legitimately carry a trailing space -- ``"iso "`` so that it does
not also match ``isolation`` -- so the emptiness check strips, but the stored
alias does not.

``profile_catalog.py`` validates all of this at import time, unknown keys
included. A typo is therefore an import-time error naming the file and the path
inside it (``nvh.json: rules[2].severity: must be one of critical, warning,
info``), never a rule that quietly stops firing.

Profile selection is ``auto`` by default: the catalog discipline of the report
decides, or failing that the identity patterns in the profile files, tried in
``detect_priority`` order with the first match kept.

Semantic review
---------------

An optional pass, requiring ``REPORT_LLM_*`` and a reachable Ollama. It asks
for structured JSON output and looks for three things:

* ``semantic.scope_result_alignment`` -- do the results answer the stated
  scope?
* ``semantic.unsupported_conclusion`` -- is each conclusion grounded in the
  report itself?
* ``semantic.internal_contradiction`` -- does the text contradict itself?

Only findings whose quoted evidence can be verified **verbatim on the page they
claim** survive; anything the model invented or left unsupported is dropped
before it reaches a reviewer. With the LLM disabled the deterministic findings
stand alone.

Human decisions and precision
-----------------------------

A finding is a hypothesis until a person rules on it.

.. code-block:: text

   POST /report-review/decisions
     {document_id, finding_key, rule_id,
      decision: open | confirmed | dismissed, note, reviewer}

Decisions are stored in ``report_review_decisions``, unique per
``(document_id, finding_key)``. ``GET /report-review/rule-precision`` then
reports the confirm rate per rule -- how often reviewers agreed with it.

A rule needs at least ``MINIMUM_PRECISION_DECISIONS`` (10) decided findings
before a rate is reported: below that, one reviewer dismissing two findings
would read as 0% precision, which is noise rather than a measurement.

Evidence and export
-------------------

``GET /documents/{id}/review-preview``
   The report PDF with the findings for one ``rule_id`` highlighted on the
   requested page. Severity picks the colour (critical red, warning amber, info
   blue).

``GET /report-review/export``
   A PDF review record for the requested documents: the summary table, then
   each finding with its evidence, severity, suggested fix and the human
   decision recorded against it.

Revision comparison
-------------------

When two reports are selected, the review engine compares their findings rather
than their full text, and reports them as **new**, **resolved** and
**still open**. It answers "what changed about the quality of this report
between revisions", which is a different and more tractable question than a
full redline.

Report comparison
=================

``ReportComparisonService`` compares report *content*, either pairwise
(``POST /report-comparison``) or across a set (``POST /report-comparison/multi``,
``reference`` or ``all_pairs`` mode).

* Either side may be a document already in the database (``document_id``) or a
  one-off upload (``POST /report-comparison/upload`` returns an
  ``upload_token`` valid for a short window; the file is never ingested).
* Chunks are aligned semantically and lexically; the result is split into
  **similarities** and **differences**, each with a topic, a summary, evidence
  from both sides and a confidence.
* With ``use_llm`` and a working provider, the LLM refines topics and
  summaries. Without it the deterministic alignment stands.
* ``GET /report-comparison/{id}/pdf/{side}`` returns the PDF with the matched
  passages highlighted and numbered, and
  ``GET /report-comparison/{id}/viewer`` opens a two-pane full-screen viewer.

Results are cached per comparison id, which is what makes the viewer and the
two PDF endpoints cheap to open after the comparison itself has run.

Report quality questions
========================

``ReportQualityService`` answers a narrow class of question directly from the
document structure rather than from retrieval -- "are the tables numbered
correctly?", "which figures are missing?". It extracts caption occurrences
(``Tablo 3.2``, ``Şekil 4``, ``Resim 1``), checks the sequence, and answers with
the page each conclusion came from. ``DocumentIntelligenceService`` routes
matching chat questions here automatically.

Report drafting
===============

``ReportWriterService`` (``POST /draft-report``) builds a report draft from a
title, an objective, free-form notes and an optional set of source documents.

* Keywords are refined from the title, objective and notes; a retrieval query
  is built from the result and run against the corpus.
* The draft is composed from a cover block plus a body grounded in the
  retrieved passages. ``detail_level`` selects ``quick`` or ``detailed``.
* With ``REPORT_LLM_*`` available the body is generated and then **sanitized**
  against the cover block and the allowed terms; otherwise a deterministic
  composition is used. Either way the response lists the sources it drew on.
* ``POST /draft-report/pdf`` renders the same payload as a PDF with a cover
  table, a summary table and a Turkish-capable font.
