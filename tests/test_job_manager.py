"""In-process background job manager: lifecycle, progress, errors and pruning."""

from __future__ import annotations

import threading
import time

import pytest

from app.services.job_manager import JobContext, JobManager, get_job_manager


def _await(manager: JobManager, job_id: str, timeout_seconds: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        payload = manager.get(job_id)
        assert payload is not None
        if payload["status"] in {"succeeded", "failed"}:
            return payload
        time.sleep(0.01)
    raise AssertionError(f"Job {job_id} did not finish within {timeout_seconds}s")


@pytest.fixture
def manager() -> JobManager:
    return JobManager()


def test_submit_returns_a_queued_record_with_an_id(manager) -> None:
    submitted = manager.submit("demo", lambda context: {"ok": True})

    assert submitted["kind"] == "demo"
    assert submitted["job_id"]
    assert submitted["status"] in {"queued", "running", "succeeded"}
    assert submitted["created_at"]
    assert submitted["result"] in (None, {"ok": True})


def test_a_successful_job_stores_its_result(manager) -> None:
    submitted = manager.submit("demo", lambda context: {"chunks_seen": 7})

    finished = _await(manager, submitted["job_id"])

    assert finished["status"] == "succeeded"
    assert finished["result"] == {"chunks_seen": 7}
    assert finished["error"] is None
    assert finished["started_at"] and finished["finished_at"]


def test_a_failing_job_records_the_error_message(manager) -> None:
    def explode(context: JobContext) -> dict:
        raise RuntimeError("disk dolu")

    finished = _await(manager, manager.submit("demo", explode)["job_id"])

    assert finished["status"] == "failed"
    assert finished["error"] == "disk dolu"
    assert finished["result"] is None
    assert finished["finished_at"]


def test_a_failure_with_no_message_falls_back_to_the_exception_type(manager) -> None:
    def explode(context: JobContext) -> dict:
        raise ValueError()

    finished = _await(manager, manager.submit("demo", explode)["job_id"])

    assert finished["status"] == "failed"
    assert finished["error"] == "ValueError"


def test_progress_updates_are_visible_while_the_job_runs(manager) -> None:
    reported = threading.Event()
    release = threading.Event()

    def slow(context: JobContext) -> dict:
        context.set_progress(3, 10, "chunk")
        reported.set()
        release.wait(timeout=5.0)
        return {}

    submitted = manager.submit("demo", slow)
    assert reported.wait(timeout=5.0)

    running = manager.get(submitted["job_id"])
    assert running["status"] == "running"
    assert running["progress"] == {"done": 3, "total": 10, "message": "chunk"}

    release.set()
    finished = _await(manager, submitted["job_id"])

    # Success completes the bar even if the runner stopped reporting early.
    assert finished["progress"]["done"] == 10


def test_progress_values_are_clamped_to_zero(manager) -> None:
    def negative(context: JobContext) -> dict:
        context.set_progress(-5, -1, "bozuk")
        return {}

    finished = _await(manager, manager.submit("demo", negative)["job_id"])

    assert finished["progress"] == {"done": 0, "total": 0, "message": "bozuk"}


def test_progress_for_an_unknown_job_is_ignored(manager) -> None:
    JobContext(manager, "yok-boyle-bir-is").set_progress(1, 2, "x")

    assert manager.get("yok-boyle-bir-is") is None


def test_get_returns_none_for_an_unknown_job(manager) -> None:
    assert manager.get("yok") is None


def test_list_returns_newest_first_and_honours_the_limit(manager) -> None:
    job_ids = [manager.submit(f"demo-{index}", lambda context: {})["job_id"] for index in range(3)]
    for job_id in job_ids:
        _await(manager, job_id)

    listed = manager.list(limit=10)
    assert [item["job_id"] for item in listed] == list(reversed(job_ids))

    assert [item["job_id"] for item in manager.list(limit=2)] == list(reversed(job_ids))[:2]


def test_finished_jobs_are_pruned_once_the_tracking_cap_is_exceeded(manager) -> None:
    manager.MAX_TRACKED_JOBS = 2
    first = manager.submit("demo", lambda context: {})["job_id"]
    _await(manager, first)
    second = manager.submit("demo", lambda context: {})["job_id"]
    _await(manager, second)

    third = manager.submit("demo", lambda context: {})["job_id"]
    _await(manager, third)

    assert manager.get(first) is None
    assert manager.get(second) is not None
    assert manager.get(third) is not None


def test_payload_shape_is_stable(manager) -> None:
    finished = _await(manager, manager.submit("demo", lambda context: {})["job_id"])

    assert set(finished) == {
        "job_id",
        "kind",
        "status",
        "created_at",
        "started_at",
        "finished_at",
        "progress",
        "result",
        "error",
    }


def test_get_job_manager_is_a_process_wide_singleton() -> None:
    assert get_job_manager() is get_job_manager()
