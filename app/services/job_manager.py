from __future__ import annotations

import logging
import threading
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Callable


logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"succeeded", "failed"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class JobRecord:
    id: str
    kind: str
    status: str = "queued"  # queued | running | succeeded | failed
    created_at: datetime = field(default_factory=_utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress_done: int = 0
    progress_total: int = 0
    progress_message: str = ""
    result: dict | None = None
    error: str | None = None

    def to_payload(self) -> dict:
        return {
            "job_id": self.id,
            "kind": self.kind,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "progress": {
                "done": self.progress_done,
                "total": self.progress_total,
                "message": self.progress_message,
            },
            "result": self.result,
            "error": self.error,
        }


class JobContext:
    """Handed to a job runner so it can report progress."""

    def __init__(self, manager: "JobManager", job_id: str) -> None:
        self._manager = manager
        self._job_id = job_id

    def set_progress(self, done: int, total: int, message: str = "") -> None:
        self._manager._set_progress(self._job_id, done, total, message)


class JobManager:
    """In-process background jobs for long-running work (ingest, reindex, scans).

    Jobs run on a single dedicated worker thread instead of Starlette's request
    threadpool, so slow work cannot exhaust the pool and stall the app — and
    SQLite only allows one writer at a time anyway, so heavy write jobs are
    better off serialized.
    """

    MAX_TRACKED_JOBS = 100

    def __init__(self, max_workers: int = 1) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="bg-job")
        self._jobs: OrderedDict[str, JobRecord] = OrderedDict()
        self._lock = threading.Lock()

    def submit(self, kind: str, runner: Callable[[JobContext], dict]) -> dict:
        job = JobRecord(id=uuid.uuid4().hex, kind=kind)
        with self._lock:
            self._jobs[job.id] = job
            self._prune_locked()
        self._executor.submit(self._run, job.id, runner)
        with self._lock:
            return job.to_payload()

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.to_payload() if job else None

    def list(self, limit: int = 20) -> list[dict]:
        with self._lock:
            records = list(self._jobs.values())[-limit:]
            return [record.to_payload() for record in reversed(records)]

    def _run(self, job_id: str, runner: Callable[[JobContext], dict]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = "running"
            job.started_at = _utc_now()
        try:
            result = runner(JobContext(self, job_id))
        except Exception as exc:
            logger.exception("Background job %s (%s) failed.", job_id, job.kind)
            with self._lock:
                job.status = "failed"
                job.error = str(exc) or type(exc).__name__
                job.finished_at = _utc_now()
            return
        with self._lock:
            job.status = "succeeded"
            job.result = result
            job.finished_at = _utc_now()
            if job.progress_total:
                job.progress_done = job.progress_total

    def _set_progress(self, job_id: str, done: int, total: int, message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.progress_done = max(0, int(done))
            job.progress_total = max(0, int(total))
            job.progress_message = message

    def _prune_locked(self) -> None:
        finished = [job_id for job_id, job in self._jobs.items() if job.status in TERMINAL_STATUSES]
        overflow = len(self._jobs) - self.MAX_TRACKED_JOBS
        for job_id in finished[:max(overflow, 0)]:
            del self._jobs[job_id]


@lru_cache(maxsize=1)
def get_job_manager() -> JobManager:
    return JobManager()
