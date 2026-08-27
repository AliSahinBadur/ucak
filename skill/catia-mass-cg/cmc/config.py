"""Workspace layout and small JSON helpers.

Workspace (default: cwd, override with CMC_HOME):

    workspace/
      units_profile.json        produced by `calibrate`, machine-specific
      transform_profile.json    CATIA -> Adams, project-specific
      subassembly_map.json      bucket patterns, project-specific
      memory.sqlite             revision memory
      state.json                last run id (so `--run last` works)
      runs/<run_id>/
        meta.json
        components.json
        rollup.json
        diff.json
        preview.txt
        approval.json
        export.cmd
"""

import datetime
import json
import os
import pathlib

RUN_ID_FMT = "%Y-%m-%dT%H-%M-%S"


def home():
    return pathlib.Path(os.environ.get("CMC_HOME", os.getcwd())).resolve()


def runs_dir():
    return home() / "runs"


def run_dir(run_id):
    return runs_dir() / run_id


def new_run_id():
    return datetime.datetime.now().strftime(RUN_ID_FMT)


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path, default=None):
    path = pathlib.Path(path)
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, data):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return path


def set_last_run(run_id):
    write_json(home() / "state.json", {"last_run": run_id})


def resolve_run(run_id):
    """Accept an explicit id, or 'last'."""
    if run_id and run_id != "last":
        return run_id
    state = read_json(home() / "state.json", {})
    return state.get("last_run")
