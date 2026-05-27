from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import SessionLocal
from app.services.qa_service import QAService
from app.services.search_service import SearchService


DEFAULT_CASES_PATH = ROOT_DIR / "test_cases" / "qa_cases.json"


def normalize_text(value: str) -> str:
    translated = value.casefold().translate(
        str.maketrans(
            {
                "ı": "i",
                "ğ": "g",
                "ü": "u",
                "ş": "s",
                "ö": "o",
                "ç": "c",
                "İ": "i",
            }
        )
    )
    normalized = unicodedata.normalize("NFKD", translated)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def contains_all(text: str, expected_values: list[str]) -> list[str]:
    normalized_text = normalize_text(text)
    missing = []
    for expected in expected_values:
        if normalize_text(expected) not in normalized_text:
            missing.append(expected)
    return missing


def safe_print(value: str = "") -> None:
    print(value.encode("ascii", "backslashreplace").decode("ascii"))


def run_qa_case(case: dict[str, Any], qa_service: QAService) -> tuple[bool, str, float]:
    started_at = time.perf_counter()
    answer = qa_service.answer_question(
        question=case["question"],
        mode=case.get("mode", "hybrid"),
        limit=int(case.get("limit", 5)),
        document_id=case.get("document_id"),
    )
    elapsed = time.perf_counter() - started_at

    failures = []
    if case.get("must_find_answer", True) and not answer["answer_found"]:
        failures.append("answer_found=false")

    missing = contains_all(answer["answer"], case.get("expected_contains", []))
    if missing:
        failures.append(f"missing answer text: {', '.join(missing)}")

    expected_source_document_ids = set(case.get("expected_source_document_ids", []))
    if expected_source_document_ids:
        actual_source_document_ids = {int(source["document_id"]) for source in answer["sources"]}
        if not actual_source_document_ids.issubset(expected_source_document_ids):
            failures.append(
                "unexpected source document ids: "
                + ", ".join(str(value) for value in sorted(actual_source_document_ids))
            )

    summary = answer["answer"].replace("\n", " / ")
    if len(summary) > 180:
        summary = summary[:177].rstrip() + "..."
    return not failures, "; ".join(failures) or summary, elapsed


def run_search_case(case: dict[str, Any], search_service: SearchService) -> tuple[bool, str, float]:
    started_at = time.perf_counter()
    mode = case.get("mode", "hybrid")
    limit = int(case.get("limit", 5))
    if mode == "keyword":
        results = search_service.keyword_search(case["query"], limit=limit)
    elif mode == "semantic":
        results = search_service.semantic_search(case["query"], limit=limit)
    else:
        results = search_service.hybrid_search(case["query"], limit=limit)
    elapsed = time.perf_counter() - started_at

    failures = []
    if not results:
        failures.append("no results")

    expected_document_ids = set(case.get("expected_document_ids", []))
    if expected_document_ids:
        actual_document_ids = {int(result["document_id"]) for result in results}
        if not expected_document_ids.intersection(actual_document_ids):
            failures.append(
                "missing expected document ids: "
                + ", ".join(str(value) for value in sorted(expected_document_ids))
            )

    combined_text = " ".join(
        f"{result.get('document_title', '')} {result.get('section_title', '')} {result.get('chunk_text', '')}"
        for result in results
    )
    missing = contains_all(combined_text, case.get("expected_contains", []))
    if missing:
        failures.append(f"missing result text: {', '.join(missing)}")

    summary = ", ".join(
        f"{result['document_id']}:{result['document_title']}:{result['match_type']}"
        for result in results[:3]
    )
    return not failures, "; ".join(failures) or summary, elapsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Big Agent QA/search regression checks.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    passed = 0
    failed = 0

    with SessionLocal() as session:
        qa_service = QAService(session)
        search_service = SearchService(session)
        for index, case in enumerate(cases, start=1):
            case_type = case.get("type", "qa")
            if case_type == "search":
                ok, detail, elapsed = run_search_case(case, search_service)
            else:
                ok, detail, elapsed = run_qa_case(case, qa_service)

            status = "PASS" if ok else "FAIL"
            safe_print(f"[{status}] {index}. {case['name']} ({elapsed:.2f}s)")
            safe_print(f"       {detail}")
            if ok:
                passed += 1
            else:
                failed += 1

    safe_print(f"\nSummary: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
