from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if "BIG_AGENT_DATA_DIR" not in os.environ and (ROOT_DIR / "data_analiz" / "app.db").exists():
    os.environ["BIG_AGENT_DATA_DIR"] = str(ROOT_DIR / "data_analiz")
os.environ.setdefault("EMBEDDING_PROVIDER", "token-hash")

from sqlalchemy import select

from app.db.models import Document
from app.db.session import SessionLocal
from app.services.document_intelligence_service import DocumentIntelligenceService
from app.text.normalize import normalize_search_text


DEFAULT_CASES_PATH = ROOT_DIR / "test_cases" / "document_intelligence_cases.json"


class ControlledProvider:
    provider_name = "controlled-test"

    @staticmethod
    def is_available() -> bool:
        return True

    @staticmethod
    def generate(prompt: str, **_: Any) -> str:
        return "Kaynaklara dayali kontrollu test sentezi [K1]."


def normalize(value: str) -> str:
    return normalize_search_text(value)


def safe_print(value: str = "") -> None:
    print(value.encode("ascii", "backslashreplace").decode("ascii"))


def document_ids_for_titles(session, titles: list[str]) -> list[int]:
    if not titles:
        return []
    rows = session.execute(select(Document.id, Document.title).where(Document.title.in_(titles))).all()
    by_title = {str(row.title): int(row.id) for row in rows}
    return [by_title[title] for title in titles if title in by_title]


def check_case(service: DocumentIntelligenceService, session, case: dict[str, Any]) -> tuple[bool, str, float]:
    started_at = time.perf_counter()
    expected_intent = case.get("expected_intent")
    context_ids = document_ids_for_titles(session, case.get("context_titles", []))
    result = service.answer_question(
        case["question"],
        mode=case.get("mode", "keyword"),
        limit=int(case.get("limit", 5)),
        context_document_ids=context_ids,
    )
    elapsed = time.perf_counter() - started_at

    failures = []
    if expected_intent and service._detect_intent(case["question"]) != expected_intent:
        failures.append(f"intent={service._detect_intent(case['question'])}")

    must_find = bool(case.get("must_find_answer", True))
    if bool(result["answer_found"]) != must_find:
        failures.append(f"answer_found={result['answer_found']}")

    normalized_answer = normalize(str(result["answer"]))
    for expected in case.get("expected_contains", []):
        if normalize(expected) not in normalized_answer:
            failures.append(f"missing answer: {expected}")

    actual_titles = {str(source["document_title"]) for source in result["sources"]}
    expected_titles = set(case.get("expected_source_titles", []))
    if not expected_titles.issubset(actual_titles):
        failures.append("missing sources: " + ", ".join(sorted(expected_titles - actual_titles)))
    if case.get("only_expected_sources") and not actual_titles.issubset(expected_titles):
        failures.append("unexpected sources: " + ", ".join(sorted(actual_titles - expected_titles)))
    if len(actual_titles) < int(case.get("minimum_source_documents", 0)):
        failures.append(f"source document count={len(actual_titles)}")

    detail = (
        "; ".join(failures)
        if failures
        else f"intent={service._detect_intent(case['question'])}, sources={', '.join(sorted(actual_titles)) or '-'}"
    )
    return not failures, detail, elapsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Run general document intelligence regression checks.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--live-llm", action="store_true", help="Use the configured Ollama model instead of a test provider.")
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    passed = 0
    failed = 0
    with SessionLocal() as session:
        service = DocumentIntelligenceService(
            session,
            llm_provider=None if args.live_llm else ControlledProvider(),
        )
        for index, case in enumerate(cases, start=1):
            ok, detail, elapsed = check_case(service, session, case)
            status = "PASS" if ok else "FAIL"
            safe_print(f"[{status}] {index}. {case['name']} ({elapsed:.2f}s)")
            safe_print(f"       {detail}")
            passed += int(ok)
            failed += int(not ok)

    safe_print(f"\nSummary: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
