from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.version import APP_VERSION


def safe_print(value: str = "") -> None:
    print(value.encode("ascii", "backslashreplace").decode("ascii"))


def request_json(base_url: str, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = Request(f"{base_url.rstrip('/')}{path}", data=body, headers=headers, method=method)
    with urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def request_text(base_url: str, path: str) -> str:
    request = Request(f"{base_url.rstrip('/')}{path}", headers={"Accept": "text/html"}, method="GET")
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def normalize(value: str) -> str:
    return value.casefold().replace("\u0131", "i").replace("\u0130", "i")


def chat(base_url: str, message: str, assistant_mode: str) -> dict[str, Any]:
    return request_json(
        base_url,
        "POST",
        "/chat",
        {
            "message": message,
            "assistant_mode": assistant_mode,
            "mode": "hybrid",
            "limit": 5,
        },
    )


def check(name: str, ok: bool, detail: str) -> bool:
    status = "PASS" if ok else "FAIL"
    safe_print(f"[{status}] {name}: {detail}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Big_Agent smoke checks against a running app.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    started_at = time.perf_counter()
    failures = 0

    try:
        health = request_json(args.base_url, "GET", "/health")
        failures += not check("health", health.get("version") == APP_VERSION, f"server={health.get('version')} expected={APP_VERSION}")

        html = request_text(args.base_url, "/")
        ui_ok = f"v{APP_VERSION}" in html and "chatAssistantMode" in html and "otomatik" in html
        failures += not check("ui", ui_ok, "version badge and chat mode selector present")

        auto_math = chat(args.base_url, "4 + 4", "auto")
        auto_math_ok = auto_math.get("embedding_provider", "").startswith("chat-llm") and "8" in str(auto_math.get("answer", ""))
        failures += not check("chat auto math", auto_math_ok, auto_math.get("embedding_provider", ""))

        auto_identity = chat(args.base_url, "adam misin", "auto")
        identity_answer = normalize(str(auto_identity.get("answer", "")))
        identity_ok = auto_identity.get("embedding_provider") == "chat-direct" and "insan degilim" in identity_answer
        failures += not check("chat identity", identity_ok, auto_identity.get("embedding_provider", ""))

        auto_report = chat(args.base_url, "BIG-E konfor raporunda hangi parkurlar var?", "auto")
        report_answer = normalize(str(auto_report.get("answer", "")))
        report_ok = (
            auto_report.get("embedding_provider", "").startswith("sentence-transformers")
            and "otoban" in report_answer
            and len(auto_report.get("sources", [])) > 0
        )
        failures += not check("chat auto report rag", report_ok, auto_report.get("embedding_provider", ""))

        report_math = chat(args.base_url, "4 + 4", "report")
        report_math_ok = report_math.get("embedding_provider", "").startswith("sentence-transformers")
        failures += not check("chat report mode stays rag", report_math_ok, report_math.get("embedding_provider", ""))

        duplicates = request_json(args.base_url, "GET", "/duplicates?limit=5")
        duplicate_ok = "items" in duplicates and "total" in duplicates
        failures += not check("duplicates endpoint", duplicate_ok, ", ".join(sorted(duplicates.keys())))

        catalog_path = "/catalog/search?" + urlencode({"query": "BIG-E", "limit": 3})
        catalog = request_json(args.base_url, "GET", catalog_path)
        catalog_ok = "results" in catalog
        failures += not check("catalog search endpoint", catalog_ok, ", ".join(sorted(catalog.keys())))

        storage = request_json(args.base_url, "GET", "/storage/check")
        storage_ok = "missing_files" in storage or "issues" in storage or "healthy_documents" in storage
        failures += not check("storage check endpoint", storage_ok, ", ".join(sorted(storage.keys())))

    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        failures += 1
        safe_print(f"[FAIL] smoke runner: {exc}")

    elapsed = time.perf_counter() - started_at
    safe_print("")
    if failures:
        safe_print(f"Smoke summary: {failures} failed ({elapsed:.2f}s)")
        return 1
    safe_print(f"Smoke summary: all pass ({elapsed:.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
