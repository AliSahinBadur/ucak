==========
Operations
==========

Running the application
=======================

.. code-block:: powershell

   cd path\to\ucak
   & '.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000

Bound to ``127.0.0.1`` the application is reachable only from the machine it
runs on. That is the right default; everything below about the LAN is an
explicit decision to widen it.

Serving a team on the local network
===================================

.. code-block:: powershell

   $env:APP_AUTH_ENABLED   = "true"
   $env:APP_USERS          = "analiz:Sifre1;test:Sifre2"
   $env:APP_SESSION_SECRET = "change-this-to-a-long-random-local-secret"
   & '.venv\Scripts\python.exe' -m uvicorn app.main:app --host 0.0.0.0 --port 8000

Share the IPv4 address from ``ipconfig``:

.. code-block:: text

   http://YOUR-IPV4:8000/

Remember to allow the port in Windows Firewall. The login is LAN-demo grade --
a signed cookie over a static user list -- so treat it as a way to keep teams
apart, not as protection for confidential data on an untrusted network.

Isolated instances
==================

For two teams that should not see each other's corpus, run two processes with
separate data folders, ports and cookie names:

.. code-block:: powershell

   # Analiz
   $env:BIG_AGENT_DATA_DIR   = ".\data_analiz"
   $env:APP_AUTH_ENABLED     = "true"
   $env:APP_USERS            = "analiz:Sifre1"
   $env:APP_SESSION_SECRET   = "change-this-to-a-long-random-local-secret"
   $env:APP_AUTH_COOKIE_NAME = "big_agent_analiz"
   & '.venv\Scripts\python.exe' -m uvicorn app.main:app --host 0.0.0.0 --port 8001

.. code-block:: powershell

   # Test
   $env:BIG_AGENT_DATA_DIR   = ".\data_test"
   $env:APP_AUTH_ENABLED     = "true"
   $env:APP_USERS            = "test:Sifre2"
   $env:APP_SESSION_SECRET   = "change-this-to-another-long-random-local-secret"
   $env:APP_AUTH_COOKIE_NAME = "big_agent_test"
   & '.venv\Scripts\python.exe' -m uvicorn app.main:app --host 0.0.0.0 --port 8002

Distinct cookie names matter: two instances on the same host share a cookie
namespace, and without distinct names logging into one logs you out of the
other.

.. warning::

   ``BIG_AGENT_DATA_DIR`` stays set for the whole PowerShell session. Every
   script run in that window afterwards -- ``run_qa_checks.py``,
   ``run_report_review_checks.py`` -- reads the same folder. The check scripts
   print the data directory and document count on their first line for exactly
   this reason. To go back: ``Remove-Item Env:\BIG_AGENT_DATA_DIR``, or open a
   new window.

Monitoring
==========

.. code-block:: powershell

   Invoke-RestMethod http://127.0.0.1:8000/health
   Invoke-RestMethod http://127.0.0.1:8000/system/model-status

``/health`` is exempt from authentication and does no database work, so it is
safe to poll. ``/system/model-status`` reports which embedding provider and
device are live and whether Ollama answered -- the first thing to check when
answers get worse for no obvious reason.

Application logs go to standard output at ``INFO`` via ``logging.basicConfig``.
Ingest and parse failures are logged with a stack trace before the exception
propagates.

.. _rebuild-embeddings:

Rebuilding embeddings
=====================

Do this after changing the embedding model or provider, and after upgrading a
database whose vectors are still in the old JSON text format.

.. code-block:: powershell

   $job = Invoke-RestMethod -Method Post http://127.0.0.1:8000/embeddings/rebuild
   Invoke-RestMethod "http://127.0.0.1:8000/jobs/$($job.job_id)"

The job re-embeds every chunk with the active provider, reports progress every
20 chunks, and invalidates the vector index when it finishes. Search keeps
working throughout -- WAL means readers are not blocked -- but results reflect
a partially rebuilt index until it completes.

Storage integrity
=================

.. code-block:: powershell

   Invoke-RestMethod http://127.0.0.1:8000/storage/check

Lists documents whose stored file can no longer be resolved. Because
``resolve_document_file_path()`` already tries the stored path, the path
relative to the current documents directory, and the bare file name inside it,
anything reported here is genuinely missing rather than merely moved.

Backup and restore
==================

Everything that matters is under ``<DATA_DIR>``:

.. code-block:: powershell

   # stop the application first -- WAL files are part of the database
   Copy-Item -Recurse .\data .\data-backup-2026-01-31

To restore, put the folder back and start the application; ``init_db()`` adds
any columns a newer version expects. To start clean, delete the data folder --
the next start recreates the database and the documents directory.

Note that ``data/app.db-wal`` and ``data/app.db-shm`` are part of the database
while the process runs. Copying ``app.db`` alone from a running instance can
produce a file missing the most recent writes.

Upgrading
=========

#. Stop the application.
#. Back up ``data/``.
#. Update the code and re-run ``pip install -r requirements.txt``.
#. Start it. ``init_db()`` creates missing tables and adds missing columns.
#. Check ``GET /health`` reports the new version, and run the test suite.
#. If the embedding provider changed, run ``POST /embeddings/rebuild``.

There is no downgrade path: an older build will not know about columns a newer
one added. Restore the backup instead.

Performance notes
=================

* **Jobs are serialized.** One background worker, by design -- SQLite allows
  one writer, and a queue of heavy jobs is better than a thundering herd. A
  batch ingest and an embedding rebuild will not overlap.
* **The vector index is a process-wide cache.** The first semantic query after
  an ingest pays to rebuild the matrix; subsequent queries do not.
* **Embeddings are ``float32``.** Half the memory and materially faster
  matrix products compared with the old JSON text vectors.
* **Share scans are bounded** by visit counts, depth and a wall-clock deadline,
  so a disconnected network drive degrades a request instead of hanging it.
* **The sentence-transformers model dominates startup cost** when one is
  configured. With ``token-hash`` the application starts instantly, which is
  why the tests use it.

Security posture
================

What the application does protect:

* the library browser refuses any path outside its allowed roots;
* the CATIA skill can be restricted to an explicit client list, serializes
  measurements, and gates every export behind a human approval that the model
  cannot fake;
* review-preview and catalog-preview endpoints validate their path arguments
  before touching the filesystem.

What it does not:

* the login is a static user list with a signed cookie, not an identity
  provider, and it does not distinguish roles;
* there is no transport encryption -- put a reverse proxy in front if that
  matters; and
* ``POST /documents/{id}/open-folder`` and ``POST /catalog/{id}/open-best-file``
  act on the **server's** desktop. They are convenience features for a
  single-workstation install, and they behave oddly on a shared server.

Treat the whole application as trusted-network software. That is what it was
built to be.
