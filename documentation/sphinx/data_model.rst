==========
Data model
==========

The database is one SQLite file, ``<DATA_DIR>/app.db``, defined by the
SQLAlchemy models in ``app/db/models.py``. Timestamps are timezone-aware UTC.

.. code-block:: text

   documents 1---* document_pages
       |
       +-----* document_chunks 1---1 chunk_embeddings
       |
       +-----* report_review_decisions
       |
       +-----* duplicate_report_pairs   (twice: document_id_a, document_id_b)
       |
       +-----1 catalog_document_links *---1 report_catalog_entries

``documents``
=============

One row per ingested file.

.. list-table::
   :header-rows: 1
   :widths: 26 18 56

   * - Column
     - Type
     - Note
   * - ``id``
     - int PK
     -
   * - ``title``
     - str(255)
     - The file stem at ingest time.
   * - ``file_name``
     - str(255)
     - The name as uploaded.
   * - ``file_type``
     - str(32)
     - ``pdf``, ``docx``, ``pptx``.
   * - ``file_hash``
     - str(64), unique
     - SHA-256. The deduplication key.
   * - ``file_path``
     - str(1024)
     - Where the copy was stored; re-resolved at read time.
   * - ``extraction_quality``
     - JSON, nullable
     - The rollup described in :doc:`ingestion`. ``NULL`` means the document
       predates the column -- unknown, not perfect.
   * - ``created_at``
     - datetime
     -

Cascades: deleting a document deletes its pages and chunks
(``all, delete-orphan``).

``document_pages``
==================

One row per page (PDF), logical section (DOCX) or slide (PPTX) that survived
normalization.

.. list-table::
   :header-rows: 1
   :widths: 26 18 56

   * - Column
     - Type
     - Note
   * - ``document_id``
     - FK, indexed
     -
   * - ``page_number``
     - int
     - 1-based, in document order.
   * - ``raw_text`` / ``clean_text``
     - text
     - Both are kept: raw for provenance, clean for retrieval.
   * - ``section_title``
     - str(255), nullable
     - Detected heading, where the format allows one.
   * - ``extraction_method``
     - str(32), nullable
     - ``native`` or ``ocr``.
   * - ``ocr_attempted``
     - bool, nullable
     - Whether OCR was tried on this page.
   * - ``char_count`` / ``word_count``
     - int, nullable
     - Size of the cleaned text.

The last four are nullable because they were added to a table already in the
field; ``NULL`` means *unknown*, never "native and empty".

``document_chunks``
===================

The searchable unit.

.. list-table::
   :header-rows: 1
   :widths: 26 18 56

   * - Column
     - Type
     - Note
   * - ``document_id``
     - FK, indexed
     -
   * - ``page_start`` / ``page_end``
     - int
     - The page range the chunk covers.
   * - ``section_title``
     - str(255), nullable
     - Inherited from the source section.
   * - ``chunk_text``
     - text
     - Cleaned text, 650 words with 75 overlapping.
   * - ``chunk_order``
     - int
     - Global order within the document, 1-based.

``chunk_embeddings``
====================

.. list-table::
   :header-rows: 1
   :widths: 26 18 56

   * - Column
     - Type
     - Note
   * - ``chunk_id``
     - FK PK
     - One embedding per chunk, at most.
   * - ``embedding``
     - blob
     - Packed little-endian ``float32``.

Databases written by older versions hold JSON text in this column -- SQLite
stores either in a TEXT-affinity column -- and ``EmbeddingService.deserialize``
accepts both. One ``POST /embeddings/rebuild`` converts them.

Chunks whose vector has no signal have no row here, so the embedding count can
legitimately be lower than the chunk count.

``report_catalog_entries``
==========================

The imported register.

.. list-table::
   :header-rows: 1
   :widths: 26 18 56

   * - Column
     - Type
     - Note
   * - ``report_code``
     - str(255), indexed
     - The code a golden-set case names a report by.
   * - ``vehicle_name``
     - str(255), indexed
     -
   * - ``report_title``
     - str(512)
     -
   * - ``discipline``
     - str(80), indexed
     - Upper-cased on import; drives review profile selection.
   * - ``report_date``
     - str(40), nullable
     - Kept as text -- registers are inconsistent about dates.
   * - ``authors``
     - str(512), nullable
     -
   * - ``source_path``
     - str(1024), nullable
     - Where the register says the file lives.
   * - ``row_hash``
     - str(64), unique
     - Makes re-import idempotent.
   * - ``imported_at``
     - datetime
     -

``catalog_document_links``
==========================

Joins a register row to an ingested document. A unique constraint on
``catalog_entry_id`` means **at most one document per catalog entry**.
``match_method`` records how the link was made (default ``catalog_ingest``).

``duplicate_report_pairs``
==========================

Near-duplicate candidates, unique on ``(document_id_a, document_id_b)``.

.. list-table::
   :header-rows: 1
   :widths: 30 18 52

   * - Column
     - Type
     - Note
   * - ``similarity_score``
     - float
     - The combined score.
   * - ``title_score`` / ``embedding_score``
     - float
     - The two axes, kept separately so a pair can be understood.
   * - ``matched_chunks``
     - int
     - How much of the documents actually matched.
   * - ``reason``
     - str(255)
     - Which axis carried the pair.
   * - ``status``
     - str(40)
     - ``candidate`` until a human moves it.
   * - ``created_at`` / ``updated_at``
     - datetime
     - ``updated_at`` refreshes on write.

``report_review_decisions``
===========================

A human verdict on one finding, unique on ``(document_id, finding_key)``.

.. list-table::
   :header-rows: 1
   :widths: 26 18 56

   * - Column
     - Type
     - Note
   * - ``finding_key``
     - str(64), indexed
     - Hash over the identifying parts of the finding, so a re-run keeps the
       decision.
   * - ``rule_id``
     - str(120), indexed
     - What the precision report groups by.
   * - ``decision``
     - str(24)
     - ``open``, ``confirmed`` or ``dismissed``.
   * - ``note`` / ``reviewer``
     - text / str(120)
     - Optional.
   * - ``created_at`` / ``updated_at``
     - datetime
     -

Files on disk
=============

.. code-block:: text

   <DATA_DIR>/
     app.db               SQLite database (plus -wal and -shm while running)
     documents/           stored report files, <stem>__<hash8><ext>
     qa_runs/             one JSON file per scripts/run_qa_checks.py run
     skills/              unpacked .skill packages, stamped by archive hash
     catia_skill/         per-user CATIA workspaces (runs, memory.sqlite, maps)

None of this is committed; see the local data policy in :doc:`overview`.

Adding a column
===============

There is no migration tool. To add a column to a table that already ships:

#. add it to the ORM model as **nullable with no default**;
#. add it to ``_SQLITE_ADDED_COLUMNS`` in ``app/db/session.py`` with its SQL
   type; and
#. make every reader treat ``NULL`` as *unknown*.

``init_db()`` will add it on the next start of any installation that lacks it.
See :ref:`schema-evolution`.
