"""Golden-set regression for the deterministic report review rules.

Cases live in `test_cases/report_review_cases.json` and are keyed by **report
code**, never by database id. A case names `2025-BIG-e-NVH-01` and
`DocumentReferenceResolver` resolves it through the report catalog, falling back
to a compacted match on the document title and file name -- the same resolution
`run_qa_checks.py` uses, so both golden sets mean the same thing by "this
report".

A case whose document is absent is reported as SKIP, not FAIL -- an operator
with a partial corpus should still get a signal from the rules they can run.

The runner is deterministic: `analyze_documents` executes the rule catalog and
nothing else, so this needs no LLM, no embeddings and no network.

    python scripts/run_report_review_checks.py
    python scripts/run_report_review_checks.py --precision
    python scripts/run_report_review_checks.py --precision-only --min-decisions 5
"""

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
os.environ.setdefault("REPORT_LLM_ENABLED", "false")

from sqlalchemy import func, select

from app.config import get_settings
from app.db.models import Document
from app.db.session import SessionLocal, init_db
from app.services.document_reference_service import (
    DocumentReferenceResolver,
    describe_reference,
    is_legacy_id_reference,
)
from app.services.report_review_service import ReportReviewService


DEFAULT_CASES_PATH = ROOT_DIR / "test_cases" / "report_review_cases.json"

SKIPPED = "skipped"


def safe_print(value: str = "") -> None:
    print(value.encode("ascii", "backslashreplace").decode("ascii"))


def case_reference(case: dict[str, Any]) -> dict:
    """The portable reference a case names, in resolver form."""
    if case.get("document_ref"):
        return dict(case["document_ref"])
    report_code = str(case.get("report_code") or "").strip()
    if not report_code:
        raise ValueError(f"Case '{case.get('name')}' names no document.")
    return {"report_code": report_code}


def run_case(
    service: ReportReviewService,
    resolver: DocumentReferenceResolver,
    case: dict[str, Any],
) -> tuple[bool | None, str, float]:
    """Returns (passed, detail, elapsed); passed is None when the case skipped."""
    started_at = time.perf_counter()
    reference = case_reference(case)
    label = describe_reference(reference)
    resolution = resolver.resolve(reference)
    document: Document | None = resolution.document
    if document is None:
        elapsed = time.perf_counter() - started_at
        return None, f"document not in this database: {label}", elapsed

    failures_prefix: list[str] = []
    if resolution.ambiguous:
        failures_prefix.append(f"ambiguous reference '{label}' matches {resolution.match_count} documents")
    if is_legacy_id_reference(reference):
        failures_prefix.append(f"reference '{label}' is pinned to a database id and is not portable")

    review = service.analyze_documents([int(document.id)], profile=str(case.get("profile", "auto")))
    elapsed = time.perf_counter() - started_at
    if not review["documents"]:
        return False, f"review produced no result for {document.title}", elapsed

    result = review["documents"][0]
    statuses = {check["rule_id"]: check["status"] for check in result["checks"]}
    findings_by_rule: dict[str, int] = {}
    for finding in result["findings"]:
        findings_by_rule[finding["rule_id"]] = findings_by_rule.get(finding["rule_id"], 0) + 1

    failures: list[str] = list(failures_prefix)

    expected_profile = case.get("expect_profile")
    if expected_profile and result["profile"] != expected_profile:
        failures.append(f"profile={result['profile']} (expected {expected_profile})")

    for rule_id in case.get("expect_rules_present", []):
        if rule_id not in statuses:
            failures.append(f"{rule_id}: rule not active for profile '{result['profile']}'")
        elif not findings_by_rule.get(rule_id):
            failures.append(f"{rule_id}: expected a finding, got status '{statuses[rule_id]}'")

    for rule_id in case.get("expect_rules_absent", []):
        if findings_by_rule.get(rule_id):
            failures.append(f"{rule_id}: expected no finding, got {findings_by_rule[rule_id]}")

    for rule_id, expected_status in (case.get("expect_status") or {}).items():
        actual_status = statuses.get(rule_id)
        if actual_status is None:
            failures.append(f"{rule_id}: rule not active for profile '{result['profile']}'")
        elif actual_status != expected_status:
            failures.append(f"{rule_id}: status={actual_status} (expected {expected_status})")

    minimum_findings = int(case.get("minimum_findings", 0))
    if len(result["findings"]) < minimum_findings:
        failures.append(f"findings={len(result['findings'])} (expected >= {minimum_findings})")

    detail = "; ".join(failures) or (
        f"{document.title} [{result['profile']}] "
        f"checks={len(result['checks'])}, findings={len(result['findings'])}"
    )
    return not failures, detail, elapsed


def announce_corpus(session) -> int:
    """Say which database is being read, and how much is in it.

    BIG_AGENT_DATA_DIR is an environment variable, so a shell that set it for
    one run silently redirects every later one. Printing the path turns "no
    such table" into an obvious wrong-folder problem.
    """
    document_count = session.scalar(select(func.count()).select_from(Document)) or 0
    safe_print(f"Data directory: {get_settings().DATA_DIR}")
    safe_print(f"Documents in corpus: {document_count}")
    if not document_count:
        safe_print(
            "This corpus is empty. Ingest reports first, or point BIG_AGENT_DATA_DIR "
            "at the folder the app is using."
        )
    return int(document_count)


def print_precision_table(service: ReportReviewService, minimum_decisions: int | None) -> None:
    report = service.rule_precision_report(minimum_decisions=minimum_decisions)
    summary = report["summary"]
    safe_print("")
    safe_print(
        f"Per-rule precision over {summary['decided']} decided findings "
        f"({summary['confirmed']} confirmed, {summary['dismissed']} dismissed, "
        f"{summary['open']} still open); threshold {report['minimum_decisions']} decisions."
    )
    safe_print(f"{'rule_id':<34} {'prec':>6} {'conf':>5} {'dism':>5} {'open':>5} {'docs':>5}  status")
    safe_print("-" * 78)
    for rule in report["rules"]:
        precision = "-" if rule["precision"] is None else f"{rule['precision'] * 100:.0f}%"
        status = rule["status"]
        if not rule["in_catalog"]:
            status += " (retired)"
        safe_print(
            f"{rule['rule_id']:<34} {precision:>6} {rule['confirmed']:>5} {rule['dismissed']:>5} "
            f"{rule['open']:>5} {rule['documents']:>5}  {status}"
        )
    safe_print(
        f"\n{summary['measured']} rule(s) measured, {summary['insufficient_data']} "
        f"below the decision threshold, {summary['retired']} no longer in the catalog."
    )
    if summary["measured"]:
        worst = next(rule for rule in report["rules"] if rule["status"] == "measured")
        safe_print(
            f"Lowest confirm rate: {worst['rule_id']} at {worst['precision'] * 100:.0f}% "
            f"over {worst['decided']} decisions."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run report review rule regression checks.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument(
        "--precision",
        action="store_true",
        help="Also print the per-rule precision table from recorded human decisions.",
    )
    parser.add_argument(
        "--precision-only",
        action="store_true",
        help="Print only the precision table and skip the golden cases.",
    )
    parser.add_argument(
        "--min-decisions",
        type=int,
        default=None,
        help="Decisions a rule needs before its precision is reported (default: service setting).",
    )
    args = parser.parse_args()

    # The app runs init_db() at startup; a script reading the same database has
    # to do the same, or a fresh data directory fails on a missing table.
    init_db()

    with SessionLocal() as session:
        service = ReportReviewService(session)
        resolver = DocumentReferenceResolver(session)
        announce_corpus(session)

        if args.precision_only:
            print_precision_table(service, args.min_decisions)
            return 0

        cases = json.loads(args.cases.read_text(encoding="utf-8"))
        passed = 0
        failed = 0
        skipped = 0
        for index, case in enumerate(cases, start=1):
            ok, detail, elapsed = run_case(service, resolver, case)
            status = "SKIP" if ok is None else ("PASS" if ok else "FAIL")
            safe_print(f"[{status}] {index}. {case['name']} ({elapsed:.2f}s)")
            safe_print(f"       {detail}")
            if ok is None:
                skipped += 1
            elif ok:
                passed += 1
            else:
                failed += 1

        safe_print(f"\nSummary: {passed} passed, {failed} failed, {skipped} skipped")
        if args.precision:
            print_precision_table(service, args.min_decisions)

        if failed:
            return 1
        if not passed:
            # Every case skipped is not a green run; it means the corpus this
            # file describes is not in the database being checked.
            safe_print("\nNo case document was found in this database; nothing was verified.")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
