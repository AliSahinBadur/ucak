========
Glossary
========

.. glossary::
   :sorted:

   chunk
      The unit of retrieval: a block of about 650 words with 75 words
      overlapping its neighbour, carrying the page range and section title it
      came from. Search, review and comparison all operate on chunks, never on
      raw pages.

   catalog
      The imported report register -- report code, vehicle, title, discipline,
      date, authors -- independent of whether the file behind a row has been
      ingested.

   catalog link
      The join between a catalog row and an ingested document. At most one
      document per catalog entry.

   discipline profile
      A set of review rules for one engineering discipline (NVH, CFD,
      Durability, Test/Validasyon), defined as data in
      ``app/rules/profiles/<name>.json``.

   document
      One ingested file, identified by the SHA-256 hash of its bytes.

   extraction quality
      The per-document JSON rollup describing how well text came out: pages
      parsed and stored, OCR counts, sparse and unreadable pages, mean
      characters per page.

   finding
      One complaint from the review engine, carrying a rule id, a severity, the
      evidence it rests on, the page range, and a suggested fix.

   finding key
      A hash over the identifying parts of a finding. A human decision is
      recorded against this key, so the decision survives a re-run.

   hybrid search
      The default retrieval mode: keyword and semantic results normalized and
      combined at 0.45 / 0.55, with a lexical rerank contribution and a guard
      against semantic-only matches that share no query token.

   job
      A background unit of work with an id, a status, progress and a result.
      Jobs run on a single worker thread; poll ``GET /jobs/{job_id}``.

   near-duplicate
      Two documents that are the same report in substance but not byte
      identical. Detected by title and embedding similarity, unlike ingestion's
      exact hash match.

   provider
      The named implementation behind a pluggable role -- an embedding provider
      (``token-hash-v1``, ``sentence-transformers:<model>``), a retrieval
      provider, a generation provider. Reported in responses so an answer can
      be traced to what produced it.

   retrieval version
      Which retrieval implementation answered: ``v1`` (legacy symmetric
      embedding with a strict token gate), ``v2`` (the default asymmetric
      in-house path) or ``v3`` (the Haystack pipeline). A request parameter,
      not configuration.

   section
      What a parser produces per unit of a document: a PDF page, a DOCX
      heading-delimited block, or a PPTX slide. Sections become
      ``document_pages`` rows after cleaning.

   selective OCR
      OCR applied only to PDF pages whose selectable text falls below
      ``OCR_MIN_TEXT_CHARACTERS``, merging the OCR text with whatever native
      text the page had.

   skill
      A packaged capability outside the ordinary request path. The CATIA
      mass/CG skill ships as ``skill/catia-mass-cg.skill`` and carries its own
      harness and safety gates.

   token-hash
      The deterministic fallback embedding provider: a 256-dimension hashed
      bag-of-tokens vector needing no model, no GPU and no network. Lower
      retrieval quality, identical interface -- which is what the test suite
      depends on.

   variant
      The product identity selected by ``APP_VARIANT``: ``big_agent``
      (SmartCAE AI), ``raporhub`` or ``repocto``. It changes branding and the
      served front end, not the engines.

   vector index
      The process-wide NumPy matrix of all stored embeddings, stamped with a
      cheap database signature so it is rebuilt whenever embeddings change.
