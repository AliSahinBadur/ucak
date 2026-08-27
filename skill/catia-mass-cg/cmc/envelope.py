"""The one output contract.

Every cmc command prints exactly one JSON object on stdout and nothing else.
A small model only has to read two fields: `message_tr` (show to the user)
and `next_command` (run it).  Everything else is for humans and for logs.
"""

import json
import sys

MAX_WARNINGS_SHOWN = 5


class CmcError(Exception):
    """Raised by commands. `code` is a stable machine-readable identifier."""

    def __init__(self, code, message_tr, hint_tr=None, **extra):
        super().__init__(message_tr)
        self.code = code
        self.message_tr = message_tr
        self.hint_tr = hint_tr
        self.extra = extra


def _emit(payload):
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    sys.stdout.flush()


def ok(step, message_tr, next_command=None, warnings=None, **extra):
    warnings = list(warnings or [])
    payload = {
        "status": "ok",
        "step": step,
        "message_tr": message_tr,
        "next_command": next_command,
        "warnings_total": len(warnings),
        "warnings_shown": min(len(warnings), MAX_WARNINGS_SHOWN),
        "warnings": warnings[:MAX_WARNINGS_SHOWN],
    }
    payload.update(extra)
    _emit(payload)
    return 0


def fail(err):
    payload = {
        "status": "error",
        "step": getattr(err, "step", None),
        "code": err.code,
        "message_tr": err.message_tr,
        "hint_tr": err.hint_tr,
        "next_command": None,
    }
    payload.update(err.extra)
    _emit(payload)
    return 1
