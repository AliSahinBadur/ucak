=========================
The CATIA mass/CG skill
=========================

The skill lets an engineer ask, in the chat UI, for the mass and centre of
gravity of a CATIA assembly, and -- after explicitly approving the preview --
export the result as an Adams/Car ``.cmd`` file.

It is the one feature in the project that reaches outside the application: it
drives CATIA over COM and writes files to disk. Everything about its design
follows from that.

Where the gates live
====================

The security gates -- the command allow-list, the placeholder check, the human
approval gate and the channel separation -- are **not reimplemented** in the
web application. The skill package ``skill/catia-mass-cg.skill`` carries its own
harness (``runner/agent.py``), and ``CatiaSkillService`` unpacks the archive at
runtime and imports ``validate``, ``dispatch``, ``Gate`` and ``for_model`` from
it.

The consequence is the point: updating the ``.skill`` file updates the gates
with it, from one source. The service adds only what a web application has to
add:

* unpacking the archive under ``<DATA_DIR>/skills``, stamped with the archive
  hash so a new build lands in a new folder;
* session management -- message history, gate state, one workspace per user;
* the tool-calling chat request to Ollama, made with ``httpx`` so a slow model
  cannot take the server down;
* carrying screen-channel events (the preview table, the command lines) to the
  UI; and
* a deterministic export path for the approval button, which does not depend on
  the model remembering to call ``export``.

Sessions and workspaces
=======================

A session holds the message history and the approval gate, and is kept **in
memory**. A server restart clears the conversation, but not the work: runs and
``memory.sqlite`` live in the workspace and come back through ``history``.

The workspace is ``<CATIA_SKILL_WORKSPACE_ROOT>/<username>``, where the
username comes from the auth session -- or is ``local`` when authentication is
off. On first use the workspace is seeded with the example asset files from the
skill package (sub-assembly map, Adams map, transform profile).

.. warning::

   With ``APP_AUTH_ENABLED=false`` **every caller shares the ``local``
   workspace and its run history.** Turn authentication on if several engineers
   should keep separate histories.

Running over the network
========================

The endpoints accept any client by default, so an engineer can drive the skill
from another machine. Serve on the LAN the usual way:

.. code-block:: powershell

   $env:UCAK_HOST = "0.0.0.0"
   .\start.bat

Two things do not travel with the client, and the UI says so to a remote user:

* **The measurement runs on the server's CATIA**, over COM, and the Adams/Car
  ``.cmd`` file is written to the **server's** disk -- the workspace folder
  shown in the module header. Enable the skill on the machine CATIA actually
  runs on.
* **CATIA answers one measurement at a time.** Concurrent ``cmc`` commands are
  serialized behind a lock; a second engineer gets "another measurement is
  running" rather than a corrupted result.

To restrict which clients may use the skill, list them -- ``;`` or ``,``
separated, where ``local``/``localhost`` covers every loopback spelling. Empty
means no restriction:

.. code-block:: powershell

   $env:CATIA_SKILL_ALLOWED_CLIENTS = "local;10.0.0.7"

Endpoints
=========

``GET /skills/catia-mass-cg/status``
   What the UI polls to decide whether to show the module at all.

   .. code-block:: json

      {
        "available": true,
        "enabled": true,
        "source": "fake",
        "model": "qwen3:4b-instruct",
        "ollama_host": "http://127.0.0.1:11434",
        "skill_root": "...\\data\\skills\\catia-mass-cg-<hash>",
        "workspace_root": "...\\data\\catia_skill",
        "sessions": 1,
        "client_allowed": true,
        "remote_client": false
      }

   ``client_allowed`` lets the interface say *why* the module is unusable
   instead of presenting an empty chat that will answer ``403``.
   ``remote_client`` is information, not a block: it is how a remote engineer
   is told the measurement will run on the server. With the skill disabled the
   response is simply ``{"enabled": false}``.

``POST /skills/catia-mass-cg/chat``
   One conversation turn. Send ``message`` and, after the first turn, the
   ``session_id`` from the previous response. Returns the events produced by
   the turn.

``POST /skills/catia-mass-cg/approve``
   Approves the pending preview and runs the export deterministically through
   the harness. The gate is still checked inside the harness -- run-id
   matching, the approval code read from disk, ``E_STALE_APPROVAL`` raised by
   ``cmc`` -- so pressing the button cannot approve something other than what
   was shown.

Events
------

A response carries a list of events, each with a ``kind``:

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Kind
     - Meaning
   * - ``model``
     - Text the model produced for the user.
   * - ``command``
     - A ``cmc`` command the harness accepted and ran.
   * - ``result``
     - The structured result of that command, with ``status``, ``code`` and a
       Turkish ``message_tr`` / ``hint_tr``.
   * - ``screen``
     - Something to render: the preview table, command output.
   * - ``harness``
     - A note from the harness itself, such as a nudge after a malformed tool
       call.

Alongside the events, the response carries ``state``, ``approval_pending`` and
``pending_run_id`` -- which is what the UI needs to decide whether to show the
approval button.

Status codes
------------

.. list-table::
   :header-rows: 1
   :widths: 14 86

   * - Code
     - When
   * - ``404``
     - The skill is disabled (``CATIA_SKILL_ENABLED=false``), or the session id
       is unknown or expired.
   * - ``403``
     - The client is not on ``CATIA_SKILL_ALLOWED_CLIENTS``.
   * - ``409``
     - A request is already running in this session, or there is nothing
       pending to approve.
   * - ``503``
     - The skill package or the model is unavailable.

Practice mode
=============

``CATIA_SKILL_SOURCE=fake`` -- the default -- drives a synthetic assembly
shipped with the skill. No CATIA, no COM, no licence: the whole flow, including
the approval gate and the export, can be rehearsed on any machine. Set it to
``catia`` deliberately, on the workstation with CATIA, when the measurements
should be real.

Operational checks
==================

.. code-block:: powershell

   # from the server itself
   Invoke-RestMethod http://127.0.0.1:8000/skills/catia-mass-cg/status

   # from another machine on the LAN -- expect remote_client: true
   Invoke-RestMethod http://SERVER-IP:8000/skills/catia-mass-cg/status

The model needs reliable tool calling: it has to emit well-formed tool calls
turn after turn, because a malformed one costs a nudge and the harness only
allows ``CATIA_SKILL_MAX_NUDGES`` of them. ``qwen3:4b-instruct`` at a Q5_K_M
quantization or better is the tested configuration. A smaller or more
aggressively quantized model tends to narrate the command instead of calling
it, which the harness rejects rather than guesses at.
