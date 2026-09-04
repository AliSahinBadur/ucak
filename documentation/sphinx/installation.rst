============
Installation
============

Requirements
============

* **Python 3.11 or newer** (``requires-python = ">=3.11"``). The project is
  developed on Python 3.13.
* **Windows** is the primary platform. The CATIA skill and the "open the file
  in its native application" workflows are Windows-only; everything else runs
  anywhere Python does.
* Roughly 1 GB of disk for the application and its dependencies, plus whatever
  the ingested corpus and the embedding model need.

Optional components, each independently switchable:

* **A local embedding model** under ``models/`` -- without one the application
  falls back to the deterministic ``token-hash`` provider and still works.
* **Ollama** for chat and the LLM-assisted features.
* **Tesseract OCR** with Turkish and English language data, for scanned PDFs.

Install
=======

.. code-block:: powershell

   cd path\to\ucak
   py -3.11 -m venv .venv
   & '.venv\Scripts\python.exe' -m pip install -r requirements.txt

Optional dependency groups:

.. code-block:: powershell

   # sentence-transformers, for local embedding models
   & '.venv\Scripts\python.exe' -m pip install -r requirements-embeddings.txt

   # pywin32, for the CATIA COM bridge (Windows only)
   & '.venv\Scripts\python.exe' -m pip install -r requirements-skill.txt

The same groups are declared in ``pyproject.toml`` as ``embeddings``, ``skill``
and ``dev`` dependency groups, for installers that read them (``uv sync``
resolves against the committed ``uv.lock``).

Run
===

.. code-block:: powershell

   cd path\to\ucak
   & '.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000

Then open http://127.0.0.1:8000/ and check the instance answers:

.. code-block:: powershell

   Invoke-RestMethod http://127.0.0.1:8000/health
   # status      : ok
   # version     : 0.51.3
   # application : SmartCAE AI
   # variant     : big_agent

The database and the documents folder are created on first start:
``init_db()`` runs in the FastAPI lifespan hook, creating any missing tables
and adding any missing columns (see :ref:`schema-evolution`).

Launcher scripts
================

Two Windows batch files wrap the same command for operators who do not work in
a terminal:

``start.bat``
   Installs ``requirements.txt`` with the project's ``.venv`` interpreter, then
   starts uvicorn. It fails loudly if ``.venv\Scripts\python.exe`` is missing.

``run-generic.bat``
   The same flow with no machine-specific path: it uses ``.venv`` if present,
   otherwise ``py``, otherwise ``python`` from ``PATH``.

Both read two environment variables:

.. list-table::
   :header-rows: 1
   :widths: 22 20 58

   * - Variable
     - Default
     - Meaning
   * - ``UCAK_HOST``
     - ``127.0.0.1``
     - Bind address. Set to ``0.0.0.0`` to accept connections from the LAN,
       and open the port in the firewall.
   * - ``UCAK_PORT``
     - ``8000``
     - Listening port.

.. code-block:: powershell

   $env:UCAK_HOST = "0.0.0.0"
   .\start.bat

Embedding model
===============

The application auto-detects a local model directory at import time and
chooses its provider accordingly (``app/config.py``,
``_default_embedding_model_name``). These paths are probed in order:

.. code-block:: text

   models/Qwen3-Embedding-4B
   models/qwen3-embedding-4b
   models/Qwen3-Embedding-0.6B
   models/qwen3-embedding-0.6b
   models/Qwen/Qwen3-Embedding-4B
   models/Qwen/Qwen3-Embedding-0.6B

If one exists, ``EMBEDDING_PROVIDER`` defaults to ``sentence-transformers`` and
``EMBEDDING_MODEL_NAME`` to that path. If none exists, the provider defaults to
``token-hash``: a deterministic 256-dimension hashed bag-of-tokens vector that
needs no model, no GPU and no network. Retrieval quality is lower, but every
endpoint behaves the same way, which is exactly what the test suite relies on.

To pin the choice explicitly:

.. code-block:: powershell

   $env:EMBEDDING_BACKEND = "sentence-transformers"
   $env:EMBEDDING_MODEL_PATH = ".\models\Qwen3-Embedding-4B"
   $env:EMBEDDING_LOCAL_FILES_ONLY = "true"
   $env:EMBEDDING_DEVICE = "cpu"

``EMBEDDING_DEVICE=auto`` (the default) resolves to ``cuda`` when a
CUDA-enabled PyTorch is importable and reports a device, otherwise ``cpu``. The
probe is deliberately kept out of ``Settings`` so that merely constructing
settings -- as the test suite does -- never imports torch.

.. important::

   Changing the embedding provider or model invalidates every stored vector.
   Run ``POST /embeddings/rebuild`` afterwards; see :ref:`rebuild-embeddings`.

Ollama (optional)
=================

General chat, LLM-assisted answers, the semantic review pass, the LLM report
draft and the CATIA skill all speak to a local Ollama server.

.. code-block:: powershell

   ollama list
   ollama pull qwen2.5:3b

.. code-block:: powershell

   $env:CHAT_LLM_ENABLED = "true"
   $env:CHAT_LLM_BACKEND = "ollama"
   $env:CHAT_LLM_MODEL_NAME = "qwen2.5:3b"
   $env:OLLAMA_HOST = "http://127.0.0.1:11434"

Report question answering does **not** require the LLM. Retrieval and
source-grounded extraction keep working when Ollama is unreachable; the answer
simply comes from the extractive path instead of the generated one.

Tesseract OCR (optional)
========================

OCR is applied selectively: only to PDF pages whose selectable text falls below
``OCR_MIN_TEXT_CHARACTERS``. It needs a local Tesseract install with the
requested language data, plus ``pymupdf`` (already in ``requirements.txt``).

.. code-block:: powershell

   $env:OCR_ENABLED = "true"
   $env:OCR_LANGUAGES = "tur+eng"
   $env:OCR_TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
   $env:OCR_TESSDATA_DIR = "C:\Program Files\Tesseract-OCR\tessdata"

If Tesseract or the language data is missing, ``SelectiveOCRService`` reports
itself unavailable and ingestion proceeds with native text only -- pages that
would have been OCR'd are simply recorded as sparse in the extraction quality
rollup.

Verify the installation
=======================

.. code-block:: powershell

   # unit and API tests: no model, no Ollama, no network
   & '.venv\Scripts\python.exe' -m pytest -q

   # against a running instance
   & '.venv\Scripts\python.exe' scripts\run_smoke_checks.py

See :doc:`testing` for the full check inventory.
