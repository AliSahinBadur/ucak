=============================
Catalog, library and graph
=============================

Most organizations already have a report register -- an Excel sheet listing
every report, its vehicle, its discipline and where the file lives on a share.
The catalog features connect that register to the ingested corpus, so a
question can be answered about *reports that exist* and not only about reports
that happen to have been ingested.

The catalog
===========

Import
------

``POST /catalog/import`` accepts ``.xlsx`` (via ``openpyxl``) or a delimited
text file. Delimiter detection for text is automatic: tab, semicolon or comma,
whichever the first 2 KB suggests.

A row must have at least six columns, and the first four must be non-empty:

.. list-table::
   :header-rows: 1
   :widths: 12 24 64

   * - Column
     - Field
     - Note
   * - 1
     - ``report_code``
     - Required. Also inspected as a possible file path.
   * - 2
     - ``vehicle_name``
     - Required.
   * - 3
     - ``report_title``
     - Required.
   * - 4
     - ``discipline``
     - Required. Upper-cased on import.
   * - 5
     - ``report_date``
     - Optional. Dates are stored as ISO strings.
   * - 6
     - ``authors``
     - Optional.

Header rows are detected by their wording and skipped. A cell hyperlink is the
preferred source of the file path -- an Excel register usually links the report
rather than spelling the path out; ``file:`` URLs are decoded, ``http(s)``
links are ignored, and separators are normalized to Windows form.

Each row is hashed. Re-importing the same sheet creates nothing new; if a row
now carries a source path it did not have before, only that path is updated.
The response reports ``rows_seen``, ``created_count``, ``duplicate_count``,
``updated_count`` and the first twenty row-level errors.

Searching the catalog
---------------------

``GET /catalog/search`` filters by free text, vehicle and discipline.
``GET /catalog/table`` returns the register as a table, joined with what is
known about each row's ingestion state -- whether a document is linked, how
many chunks it has, and whether those chunks are embedded.

Catalog questions
-----------------

``POST /ask/catalog`` answers questions about the *register itself* rather than
report content. ``CatalogService`` profiles the question (vehicles mentioned,
discipline, year, report code, intent) and then answers one of:

* an **analysis-type summary** -- what kinds of analysis exist for a vehicle;
* a **vehicle comparison** -- two or more vehicles side by side, with a
  declared winner where the question asks for one; or
* a **ranking** -- vehicles ordered by report count within a discipline or
  year.

Everything is computed from catalog rows with SQL and deterministic profiling;
no model is involved.

Linking catalog rows to files
-----------------------------

The link between a register row and a real file is the interesting part,
because the file lives on a share whose layout nobody controls.

``CatalogIngestService`` searches the roots in ``CATALOG_SEARCH_ROOTS`` with
hard bounds -- maximum directory visits, maximum depth, maximum files per
directory, and a wall-clock deadline on the whole share scan. A disconnected
network drive slows a request down; it cannot pin a worker indefinitely.

.. list-table::
   :header-rows: 1
   :widths: 44 56

   * - Endpoint
     - Purpose
   * - ``GET /catalog/{id}/file-candidates``
     - The files that might be this row's report, scored.
   * - ``GET /catalog/{id}/file-preview``
     - Preview one specific candidate.
   * - ``GET /catalog/{id}/best-file-preview``
     - Preview the best candidate.
   * - ``GET /catalog/{id}/best-file-preview-info``
     - Metadata about that candidate without fetching it.
   * - ``POST /catalog/{id}/open-best-file``
     - Open it in the operating system's default application (server-side,
       Windows).
   * - ``POST /catalog/ingest-candidate``
     - Ingest one chosen candidate and link it to the row.
   * - ``POST /catalog/ingest-sample``
     - Background job: ingest a few reports per discipline. ``dry_run``
       defaults to ``true``, so the safe call is the default one.
   * - ``POST /catalog/ingest-selected``
     - Background job: ingest the listed catalog rows.
   * - ``POST /catalog/reconcile-documents``
     - Re-check existing links against the documents in the database;
       supports ``dry_run``.

Links are stored in ``catalog_document_links``, at most one document per
catalog entry, with the ``match_method`` that produced the link.

The library browser
===================

``POST /library/scan`` returns a bounded, read-only tree of the supported
report files under a path. It exists for the ``repocto`` variant's file
browser, and it is written defensively:

* the path must sit inside an allowed root (``REPOCTO_LIBRARY_ROOTS`` plus the
  built-in defaults) -- anything else is refused;
* the walk is capped at 800 documents, 800 directories, depth 10, and 2000
  entries per directory; and
* only ``.pdf``, ``.docx`` and ``.pptx`` appear in the result.

It never reads file contents, and it never ingests anything.

The graph overview
==================

``GET /graph/overview`` builds a small graph of the corpus from catalog
entries: nodes for vehicles, disciplines, years and authors, with edges to the
reports that connect them, plus tag counts. The result is bounded (``limit``
defaults to 160, clamped to 20-300) because the view is meant to be readable,
not exhaustive.

The ``ANALYSIS TYPE`` placeholder discipline -- a header artefact that survives
some registers -- is filtered out here, as it is everywhere else in the catalog
code.
