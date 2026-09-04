=============
Configuration
=============

All configuration lives in one place: the ``Settings`` class in
``app/config.py``, a ``pydantic-settings`` model. Values are read from the
process environment and from a ``.env`` file in the project root (UTF-8).
``get_settings()`` is ``lru_cache``-d, so settings are resolved **once per
process** -- changing an environment variable after start has no effect until
the application is restarted.

Copy ``.env.example`` to ``.env`` and uncomment only what you need to override.

.. code-block:: powershell

   Copy-Item .env.example .env

Application and storage
=======================

.. list-table::
   :header-rows: 1
   :widths: 30 18 52

   * - Variable
     - Default
     - Meaning
   * - ``APP_VARIANT``
     - ``big_agent``
     - Product identity: ``big_agent``, ``raporhub`` or ``repocto``. An
       unknown value is normalized back to the default.
   * - ``BIG_AGENT_DATA_DIR``
     - ``./data``
     - Root for everything the application writes. ``~`` is expanded and the
       directory is created at import time.

Two paths are derived from the data directory and cannot be set directly:

``DOCUMENTS_DIR``
   ``<DATA_DIR>/documents`` -- the stored copy of every ingested file.

``DATABASE_URL``
   ``sqlite:///<DATA_DIR>/app.db``.

Authentication
==============

The built-in login is LAN-demo grade: a signed cookie over a static user list.
It keeps two test teams apart on an internal network; it is not a security
boundary against a determined attacker.

.. list-table::
   :header-rows: 1
   :widths: 30 18 52

   * - Variable
     - Default
     - Meaning
   * - ``APP_AUTH_ENABLED``
     - ``false``
     - Turns the login middleware on.
   * - ``APP_USERS``
     - (empty)
     - ``user:password`` pairs separated by ``;``.
   * - ``APP_SESSION_SECRET``
     - (empty)
     - Key for the session cookie signature. Set a long random value.
   * - ``APP_AUTH_COOKIE_NAME``
     - ``big_agent_session``
     - Cookie name. Give each instance its own so two instances on one host do
       not overwrite each other's sessions.

Sessions last eight hours. With authentication off every caller is the
anonymous ``local`` user, which matters wherever state is partitioned per user
-- notably the CATIA skill workspace.

Embeddings
==========

.. list-table::
   :header-rows: 1
   :widths: 32 20 48

   * - Variable
     - Default
     - Meaning
   * - ``EMBEDDING_MODEL_PATH`` / ``EMBEDDING_MODEL_NAME``
     - auto-detected
     - Model directory or Hugging Face id. Empty means: probe ``models/`` for
       a known Qwen3 embedding folder, else ``Qwen/Qwen3-Embedding-0.6B``.
   * - ``EMBEDDING_BACKEND`` / ``EMBEDDING_PROVIDER``
     - derived
     - ``sentence-transformers`` when the resolved model path exists on disk,
       otherwise ``token-hash``.
   * - ``EMBEDDING_DEVICE``
     - ``auto``
     - ``auto`` resolves to ``cuda`` when CUDA-enabled torch is importable,
       else ``cpu``. Explicit values pass straight through.
   * - ``EMBEDDING_LOCAL_FILES_ONLY``
     - ``false``
     - Forbid any download attempt; required for air-gapped installs.
   * - ``EMBEDDING_SHOW_PROGRESS``
     - ``false``
     - Show the sentence-transformers progress bar.

Language models
===============

There are three LLM roles and they cascade. ``REPORT_LLM_*`` falls back through
``CHAT_LLM_*`` to the base ``LLM_*`` value, and finally to its own static
default. The cascade uses pydantic's ``AliasChoices``, which resolves an alias
naming a sibling field against that field's fully resolved value -- not merely
against raw environment-variable presence.

Base role, and the fallback for the two below:

.. list-table::
   :header-rows: 1
   :widths: 32 20 48

   * - Variable
     - Default
     - Meaning
   * - ``LLM_ENABLED``
     - ``false``
     - Master switch for the optional LLM layer.
   * - ``LLM_BACKEND``
     - ``disabled``
     - ``ollama`` or ``disabled``. Case-folded on read.
   * - ``LLM_MODEL_NAME`` / ``LLM_MODEL_PATH``
     - (empty)
     - Model identifier for the backend.
   * - ``LLM_MAX_CONTEXT_TOKENS``
     - ``4096``
     - Prompt budget hint.
   * - ``LLM_TIMEOUT_SECONDS``
     - ``30``
     - Request timeout in seconds.
   * - ``LLM_ANSWER_ENABLED``
     - ``false``
     - Lets ``AnswerGenerationService`` rewrite an extractive answer.
   * - ``OLLAMA_HOST``
     - ``http://127.0.0.1:11434``
     - Ollama base URL; a trailing slash is stripped.

Chat role -- the general-purpose conversational model:

.. list-table::
   :header-rows: 1
   :widths: 32 20 48

   * - Variable
     - Default
     - Meaning
   * - ``CHAT_LLM_ENABLED``
     - ``true``
     - Enables ``genel`` chat mode and auto-routed general answers.
   * - ``CHAT_LLM_BACKEND``
     - ``ollama``
     - Backend name.
   * - ``CHAT_LLM_MODEL_NAME``
     - ``qwen2.5:3b``
     - Falls back to ``LLM_MODEL_NAME``.
   * - ``CHAT_LLM_TIMEOUT_SECONDS``
     - ``45``
     - Falls back to ``LLM_TIMEOUT_SECONDS``.

Report role -- report drafting and the semantic review pass:

.. list-table::
   :header-rows: 1
   :widths: 32 20 48

   * - Variable
     - Default
     - Meaning
   * - ``REPORT_LLM_ENABLED``
     - ``true``
     - Enables the generated report draft and semantic review findings.
   * - ``REPORT_LLM_BACKEND``
     - ``ollama``
     - Falls back to ``CHAT_LLM_BACKEND``.
   * - ``REPORT_LLM_MODEL_NAME``
     - ``qwen2.5:3b``
     - Falls back to ``CHAT_LLM_MODEL_NAME``, then ``LLM_MODEL_NAME``.
   * - ``REPORT_LLM_TIMEOUT_SECONDS``
     - ``45``
     - Falls back to ``CHAT_LLM_TIMEOUT_SECONDS``, then
       ``LLM_TIMEOUT_SECONDS``.

Reranker
========

.. list-table::
   :header-rows: 1
   :widths: 32 20 48

   * - Variable
     - Default
     - Meaning
   * - ``RERANKER_ENABLED``
     - ``false``
     - Enables candidate reordering after retrieval.
   * - ``RERANKER_BACKEND``
     - ``disabled``
     - ``disabled`` selects the no-op reranker; ``score`` reorders candidates
       by their combined retrieval score.
   * - ``RERANKER_MODEL_PATH``
     - (empty)
     - Reserved for a cross-encoder backend.

OCR
===

.. list-table::
   :header-rows: 1
   :widths: 32 20 48

   * - Variable
     - Default
     - Meaning
   * - ``OCR_ENABLED``
     - ``true``
     - Selective OCR for PDF pages with too little selectable text.
   * - ``OCR_LANGUAGES``
     - ``tur+eng``
     - Tesseract language spec. An empty value falls back to ``tur+eng``.
   * - ``OCR_DPI``
     - ``250``
     - Rasterization DPI, clamped to 150-400.
   * - ``OCR_MIN_TEXT_CHARACTERS``
     - ``100``
     - Below this much native text a page becomes an OCR candidate. Clamped
       to a minimum of 20.
   * - ``OCR_TESSDATA_DIR`` / ``TESSDATA_PREFIX``
     - (empty)
     - Language data directory; auto-detected when empty.
   * - ``OCR_TESSERACT_CMD`` / ``TESSERACT_CMD``
     - (empty)
     - Path to the Tesseract executable when it is not on ``PATH``.

Catalog and library roots
=========================

.. list-table::
   :header-rows: 1
   :widths: 32 22 46

   * - Variable
     - Default
     - Meaning
   * - ``CATALOG_SEARCH_ROOTS``
     - see below
     - Semicolon-separated roots scanned when matching a catalog row to a
       report file on a share. The shipped default lists the company report
       share followed by ``V:/RAPORLAR`` and ``V:/``.
   * - ``REPOCTO_LIBRARY_ROOTS``
     - (empty)
     - Extra roots allowed for ``POST /library/scan``. The built-in defaults
       -- ``DOCUMENTS_DIR``, ``data/documents``, ``V:/RAPORLAR`` and the CAE
       digital-transformation folder -- are always included, and the endpoint
       refuses any path outside the resulting allow-list.

CATIA mass/CG skill
===================

.. list-table::
   :header-rows: 1
   :widths: 34 20 46

   * - Variable
     - Default
     - Meaning
   * - ``CATIA_SKILL_ENABLED``
     - ``true`` in code, ``false`` in ``.env.example``
     - Enable it on the workstation where CATIA actually runs.
   * - ``CATIA_SKILL_SOURCE``
     - ``fake``
     - ``fake`` drives a synthetic assembly (practice mode, no CATIA needed);
       ``catia`` opens a real COM connection. Any other value normalizes back
       to ``fake``.
   * - ``CATIA_SKILL_MODEL_NAME``
     - ``qwen3:4b-instruct``
     - Ollama model. Needs reliable tool calling.
   * - ``CATIA_SKILL_WORKSPACE_ROOT``
     - ``<DATA_DIR>/catia_skill``
     - Where run history and exported ``.cmd`` files are written, one
       sub-folder per user.
   * - ``CATIA_SKILL_LLM_TIMEOUT_SECONDS``
     - ``600``
     - Per-turn model timeout.
   * - ``CATIA_SKILL_CMC_TIMEOUT_SECONDS``
     - ``900``
     - Per-measurement timeout.
   * - ``CATIA_SKILL_MAX_STEPS``
     - ``12``
     - Tool-call budget per conversation turn.
   * - ``CATIA_SKILL_MAX_NUDGES``
     - ``3``
     - How often the harness may correct a misbehaving model before giving up.
   * - ``CATIA_SKILL_ALLOWED_CLIENTS``
     - (empty)
     - Client allow-list, ``;`` or ``,`` separated. Empty means no
       restriction. ``local`` and ``localhost`` are one token covering every
       loopback spelling.

Value parsing rules
===================

A few conventions apply across the whole settings model, and knowing them
avoids surprises:

* **Booleans are loose.** ``1``, ``true``, ``yes`` and ``on`` (any case) are
  true; everything else is false. A typo is not an error -- ``ture`` reads as
  ``false``.
* **Backend names are case-folded** and stripped, so ``Ollama`` and ``ollama``
  select the same backend.
* **List-shaped values** are semicolon-separated strings in the environment,
  exposed as tuples through a derived property (``CATALOG_SEARCH_ROOTS``,
  ``REPOCTO_LIBRARY_ROOTS``, ``CATIA_SKILL_ALLOWED_CLIENTS``). Blank entries
  are dropped.
* **Numeric guards clamp rather than reject.** An out-of-range ``OCR_DPI`` is
  pulled into 150-400 instead of raising.

Configuration in tests
======================

``tests/conftest.py`` sets the environment **at import time**, before anything
under ``app`` is imported: a throwaway ``BIG_AGENT_DATA_DIR``,
``EMBEDDING_BACKEND=token-hash``, and every LLM disabled. This ordering is
load-bearing -- ``app/db/session.py`` builds the engine from ``Settings`` when
it is imported and ``get_settings()`` is cached, so a fixture body cannot
redirect the database after the fact. See :doc:`testing`.
