=========================
The ingestion pipeline
=========================

Ingestion is the part of the system everything else depends on, so it is
deliberately the least clever part. One call to ``IngestService.ingest()``
takes a file and leaves behind a document row, its pages, its chunks and their
embeddings -- or raises, having stored nothing but the file copy.

.. code-block:: text

   file --> hash --> duplicate?  --yes--> return {"status": "duplicate"}
                        |no
                        v
                     store copy in data/documents/
                        |
                        v
                     parse  (pdf | docx | pptx)  -> list[ParsedSection]
                        |
                        v
                     selective OCR (PDF only, sparse pages)
                        |
                        v
                     normalize -> list[CleanSection]   (drops empty pages)
                        |
                        v
                     chunk     -> list[ChunkPayload]   (650 words / 75 overlap)
                        |
                        v
                     persist: Document + DocumentPage* + DocumentChunk*
                        |
                        v
                     embed each chunk -> ChunkEmbedding (float32 blob)
                        |
                        v
                     commit + invalidate the vector index

Supported formats
=================

``.pdf``, ``.docx`` and ``.pptx``. Anything else raises ``ValueError`` from the
service and becomes ``400 Unsupported file type`` at the HTTP layer.

Deduplication
=============

The file is hashed (SHA-256, streamed) before anything else. If a document with
that hash exists, ingestion stops and returns ``status: "duplicate"`` with the
existing document id -- no second copy, no re-parse. ``file_hash`` carries a
unique index, so the invariant is enforced by the database and not only by the
check.

This is exact-bytes deduplication. Two exports of the same report with
different metadata are different files here; near-duplicates are a separate
concern handled by :ref:`duplicate-detection`.

Storage
=======

The accepted file is copied into ``<DATA_DIR>/documents`` under
``<sanitized stem>__<first 8 hex of the hash><extension>`` -- readable enough
to recognize in a file listing, unique enough not to collide -- and
``documents.file_path`` records where it went.
``resolve_document_file_path()`` re-resolves that path at read time, so an
installation that was moved to another drive still finds its files: it tries
the stored path, then the path relative to the current documents directory,
then the bare file name inside it.

Parsers
=======

Every parser returns the same structure -- ``list[ParsedSection]`` with a page
number, the raw text, an optional section title, and the extraction provenance
fields. Weak documents produce empty-safe output rather than exceptions.

PDF (``app/parsers/pdf_parser.py``)
   ``pypdf`` extracts text page by page. A section title is guessed from the
   first line that is either all-caps or ends with a colon. After extraction
   the page list is handed to the selective OCR service, and any page that came
   back from OCR gets its title re-detected from the new text.

DOCX (``app/parsers/docx_parser.py``)
   ``python-docx`` walks paragraphs. A paragraph whose style name starts with
   ``Heading`` closes the current section and opens a new one, so "pages" here
   are logical sections numbered from 1. Table rows are appended as
   pipe-separated lines, which keeps tabular values searchable without
   pretending to preserve layout.

PPTX (``app/parsers/pptx_parser.py``)
   Slides are read straight from the OOXML inside the ``.pptx`` archive with
   the standard library -- no PowerPoint and no extra dependency. Slide order
   comes from the numeric part of ``ppt/slides/slideN.xml``; each slide is one
   section, and its first meaningful line becomes the section title.

Selective OCR
=============

``SelectiveOCRService`` exists to rescue scanned pages without paying for OCR
on documents that do not need it. It applies only to PDFs and only to pages
whose native text scores below ``OCR_MIN_TEXT_CHARACTERS``.

* The page is rasterized with ``pymupdf`` at ``OCR_DPI`` and passed to
  Tesseract with ``OCR_LANGUAGES``.
* Native and OCR text are merged rather than swapped, so a page that had a
  little real text does not lose it.
* The section records ``extraction_method="ocr"`` and ``ocr_attempted=True``,
  which is what makes the result auditable afterwards.
* If Tesseract, its language data or ``pymupdf`` is missing, the service
  reports itself unavailable and ingestion continues with native text only.

Normalization
=============

``normalize_sections()`` (``app/processing/text_cleaner.py``) does three things:

#. **Clean each page.** NFC normalization, ``\r\n`` folding, per-line
   whitespace collapse, and at most one blank line between blocks. Turkish
   characters are preserved exactly -- folding for *matching* happens later and
   separately, in ``app/text/normalize.py``.
#. **Drop repeated page artefacts.** A line 3-120 characters long that appears
   on at least half the pages (minimum two) is treated as a running header or
   footer and removed from every page.
#. **Drop pages that cleaned to nothing.** Their page numbers survive only in
   the extraction quality rollup, as ``empty_pages``.

The cleaning is intentionally conservative. Aggressive cleaning removes wording
that retrieval needs; both the raw and the cleaned text are stored, so nothing
is lost either way.

Chunking
========

``chunk_sections()`` walks the cleaned sections and emits overlapping word
blocks:

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Parameter
     - Default
     - Note
   * - ``target_words``
     - ``650``
     - Within the 500-800 range the project settled on.
   * - ``overlap_words``
     - ``75``
     - Must be smaller than ``target_words``; otherwise ``ValueError``.

Each chunk carries ``chunk_order`` (global, 1-based, in document order), the
page range it came from, and the section title of its source section. Chunks
are the searchable unit: keyword search, semantic search, review rules and
comparison all read chunks, never raw pages.

Extraction quality
==================

``app/processing/extraction_metrics.py`` computes per-page metrics and rolls
them up into ``documents.extraction_quality`` (a JSON column). This is the
field to read when an answer looks thin -- it usually means the document
arrived as images.

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Key
     - Meaning
   * - ``page_count``
     - Pages the parser produced.
   * - ``stored_page_count``
     - Pages that survived normalization and have a ``document_pages`` row.
   * - ``ocr_page_count`` / ``ocr_attempted_page_count``
     - Pages whose text came from OCR, and pages OCR was tried on.
   * - ``sparse_page_count``
     - Pages with text below the sparse threshold.
   * - ``no_text_page_count`` / ``no_text_pages``
     - Unreadable pages, including the ones normalization dropped.
   * - ``empty_pages``
     - Page numbers dropped at normalization. They have no page row, so this
       is the only record they exist at all.
   * - ``total_chars`` / ``mean_chars_per_page``
     - Size of what was extracted.

The value is ``NULL`` for documents ingested before the column existed; treat
that as *unknown*, not as *perfect*.

Embeddings
==========

Each chunk is embedded with the active provider and stored as packed
little-endian ``float32`` bytes in ``chunk_embeddings``. A vector with no
signal -- the zero vector a ``token-hash`` provider returns for text with no
usable tokens -- is skipped rather than stored, so ``embeddings_created`` can
be lower than the chunk count.

After the commit, ``invalidate_vector_index()`` drops the cached matrix so the
next search sees the new document.

Ingestion endpoints
===================

``POST /ingest``
   One file, one synchronous response. Returns document id, status, page and
   chunk counts, ``ocr_pages``, the extraction quality rollup, the number of
   embeddings created and the provider name.

``POST /ingest/batch``
   Many files. Uploads are staged to temporary files first -- an ``UploadFile``
   is gone once the request ends -- and the work is handed to a background job,
   which returns ``202`` with a ``job_id``. Each file gets its own database
   session, so one failure does not poison the rest of the batch; failures land
   in the per-item result with ``status: "error"`` and a message.

The catalog ingestion endpoints (:doc:`catalog`) reuse the same service to pull
files off network shares.

Result payload
==============

.. code-block:: json

   {
     "document_id": 42,
     "status": "ingested",
     "file_name": "2025-BIG-E-NVH-01.pdf",
     "pages": 18,
     "ocr_pages": 2,
     "extraction_quality": {"...": "..."},
     "chunks": 57,
     "embeddings_created": 57,
     "embedding_provider": "token-hash-v1"
   }
