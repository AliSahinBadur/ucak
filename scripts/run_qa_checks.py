"""Big Agent QA/search regression checks, scored as well as gated.

Three things this runner does beyond pass/fail:

**Portable document references.** Cases name a report, not a database id. A
`document_ref` / `expected_source_refs` / `expected_refs` entry is a report code
(`"2025-BIG-E-NVH-01"`), a `{"title_contains": [...]}` fragment list, or -- for
a file not migrated yet -- a legacy `{"document_id": 9}`, which the runner
reports as a portability hazard because it only resolves against one operator's
`data/app.db`.

**Statistical retrieval metrics.** The existing gate only asks whether the
sources came from the expected reports: a precision-only, all-or-nothing check
that cannot see a near miss or a rank regression. The ground truth for recall,
MRR and nDCG is already written in the case file, so the Haystack evaluators
(pure Python, no model, no key) score it. They are imported lazily: with
`haystack-ai` absent the gate still runs and the metrics section says why it is
missing.

**Both retrieval versions.** `v2` is the in-house stack, `v3` the Haystack
pipeline. Scoring the same cases through both is the point of keeping two
tracks: a regression that moves one and not the other localises itself.

Each run's summary is appended to `data/qa_runs/<timestamp>.json` so a
regression reads as a trend rather than a single "22 passed" line.

    python scripts/run_qa_checks.py
    python scripts/run_qa_checks.py --versions v2,v3 --k 5
    python scripts/run_qa_checks.py --no-metrics
"""

from __future__ import annotations

import argparse
import json
import logging
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import get_settings
from app.db.session import SessionLocal, init_db
from app.services.document_reference_service import (
    DocumentReferenceResolver,
    describe_reference,
    is_legacy_id_reference,
)
from app.services.haystack_retrieval_service import (
    HaystackRetrievalError,
    HaystackRetrievalService,
    HaystackUnavailableError,
)
from app.services.qa_service import QAService
from app.services.search_service import SearchService
from app.text.normalize import normalize_search_text
from app.version import APP_VERSION


DEFAULT_CASES_PATH = ROOT_DIR / "test_cases" / "qa_cases.json"
DEFAULT_VERSIONS = ("v2", "v3")
DEFAULT_K = 5


def normalize_text(value: str) -> str:
    return normalize_search_text(value)


def contains_all(text: str, expected_values: list[str]) -> list[str]:
    normalized_text = normalize_text(text)
    missing = []
    for expected in expected_values:
        if normalize_text(expected) not in normalized_text:
            missing.append(expected)
    return missing


def safe_print(value: str = "") -> None:
    print(value.encode("ascii", "backslashreplace").decode("ascii"))


# --- document references -----------------------------------------------------


def case_references(case: dict[str, Any], *keys: str) -> list[Any]:
    """Collect the references a case declares under any of `keys`, in order."""
    references: list[Any] = []
    for key in keys:
        value = case.get(key)
        if value is None:
            continue
        references.extend(value if isinstance(value, list) else [value])
    return references


def resolve_expected_ids(
    resolver: DocumentReferenceResolver,
    case: dict[str, Any],
    *keys: str,
) -> tuple[list[int], list[str]]:
    """Resolve a case's expected references; returns (ids, problems)."""
    ids: list[int] = []
    problems: list[str] = []
    for reference in case_references(case, *keys):
        resolution = resolver.resolve(reference)
        label = describe_reference(reference)
        if not resolution.found:
            problems.append(f"unresolved reference: {label}")
            continue
        if resolution.ambiguous:
            problems.append(f"ambiguous reference '{label}' matches {resolution.match_count} documents")
        ids.append(resolution.document_id)
    return list(dict.fromkeys(ids)), problems


def legacy_reference_labels(case: dict[str, Any]) -> list[str]:
    keys = ("document_ref", "document_id", "expected_source_refs", "expected_source_document_ids",
            "expected_refs", "expected_document_ids")
    return [
        describe_reference(reference)
        for reference in case_references(case, *keys)
        if is_legacy_id_reference(reference)
    ]


# --- retrieval ---------------------------------------------------------------


def ranked_document_ids(results: list[dict]) -> list[int]:
    """Document ids in retrieval order, deduplicated on first appearance.

    Retrieval ranks chunks; the metrics below are document-level, so the rank of
    a document is the rank of its best chunk.
    """
    ordered: list[int] = []
    for result in results:
        document_id = int(result.get("document_id") or 0)
        if document_id and document_id not in ordered:
            ordered.append(document_id)
    return ordered


def run_qa_case(
    case: dict[str, Any],
    qa_service: QAService,
    document_id: int | None,
    retrieval_version: str,
) -> tuple[dict, float]:
    started_at = time.perf_counter()
    answer = qa_service.answer_question(
        question=case["question"],
        mode=case.get("mode", "hybrid"),
        limit=int(case.get("limit", 5)),
        document_id=document_id,
        retrieval_version=retrieval_version,
    )
    elapsed = time.perf_counter() - started_at
    return answer, elapsed


def run_search_case(
    case: dict[str, Any],
    search_service: SearchService,
    haystack_service: HaystackRetrievalService,
    retrieval_version: str,
) -> tuple[list[dict], float]:
    started_at = time.perf_counter()
    mode = case.get("mode", "hybrid")
    limit = int(case.get("limit", 5))
    if retrieval_version == "v3":
        results = haystack_service.retrieve(case["query"], mode=mode, limit=limit)
    elif mode == "keyword":
        results = search_service.keyword_search(case["query"], limit=limit)
    elif mode == "semantic":
        results = search_service.semantic_search(case["query"], limit=limit)
    else:
        results = search_service.hybrid_search(case["query"], limit=limit)
    return results, time.perf_counter() - started_at


def check_qa_case(case: dict[str, Any], answer: dict, expected_ids: list[int]) -> tuple[list[str], str]:
    failures = []
    if case.get("must_find_answer", True) and not answer["answer_found"]:
        failures.append("answer_found=false")

    missing = contains_all(answer["answer"], case.get("expected_contains", []))
    if missing:
        failures.append(f"missing answer text: {', '.join(missing)}")

    if expected_ids:
        actual_ids = {int(source["document_id"]) for source in answer["sources"]}
        if not actual_ids.issubset(set(expected_ids)):
            failures.append(
                "unexpected source document ids: "
                + ", ".join(str(value) for value in sorted(actual_ids - set(expected_ids)))
            )

    summary = answer["answer"].replace("\n", " / ")
    if len(summary) > 180:
        summary = summary[:177].rstrip() + "..."
    return failures, summary


def check_search_case(
    case: dict[str, Any], results: list[dict], expected_ids: list[int]
) -> tuple[list[str], str]:
    failures = []
    if not results:
        failures.append("no results")

    if expected_ids:
        actual_ids = {int(result["document_id"]) for result in results}
        if not set(expected_ids).intersection(actual_ids):
            failures.append(
                "missing expected document ids: "
                + ", ".join(str(value) for value in sorted(expected_ids))
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
    return failures, summary


# --- statistical metrics (Haystack, optional) --------------------------------


def load_evaluators() -> tuple[dict | None, str]:
    """Import the Haystack evaluators lazily; returns (evaluators, reason)."""
    # The evaluators warn once per case that retrieved nothing. That is already
    # visible as a FAIL and in the recall number, and the warnings interleave
    # with the gate output, so keep them out of the report.
    logging.getLogger("haystack").setLevel(logging.ERROR)
    try:
        from haystack.components.evaluators import (
            DocumentMRREvaluator,
            DocumentNDCGEvaluator,
            DocumentRecallEvaluator,
        )
        from haystack.components.evaluators.document_recall import RecallMode
    except ImportError as exc:
        return None, f"haystack-ai is not installed ({exc})"

    field = "meta.document_id"
    return (
        {
            # MULTI_HIT is recall proper: the share of expected reports found,
            # not merely whether one of them was.
            "recall": DocumentRecallEvaluator(
                mode=RecallMode.MULTI_HIT, document_comparison_field=field
            ),
            "mrr": DocumentMRREvaluator(document_comparison_field=field),
            "ndcg": DocumentNDCGEvaluator(document_comparison_field=field),
        },
        "",
    )


def score_retrieval(
    evaluators: dict,
    samples: list[tuple[list[int], list[int]]],
    k: int,
) -> dict[str, float]:
    """Score (expected_ids, ranked_ids) pairs with the Haystack evaluators."""
    from haystack.dataclasses import Document as HaystackDocument

    def wrap(document_ids: list[int]) -> list[HaystackDocument]:
        return [
            HaystackDocument(content=str(document_id), meta={"document_id": int(document_id)})
            for document_id in document_ids
        ]

    ground_truth = [wrap(expected) for expected, _ranked in samples]
    retrieved = [wrap(ranked[:k]) for _expected, ranked in samples]
    return {
        name: round(float(evaluator.run(ground_truth, retrieved)["score"]), 4)
        for name, evaluator in evaluators.items()
    }


# --- reporting ---------------------------------------------------------------


def print_metrics_table(metrics_by_version: dict[str, dict], k: int) -> None:
    safe_print("")
    safe_print(f"Retrieval metrics over cases with expected documents (k={k}):")
    safe_print(f"{'version':<10} {'cases':>6} {'recall@k':>10} {'MRR':>8} {'nDCG':>8}  provider")
    safe_print("-" * 62)
    for version, entry in metrics_by_version.items():
        if entry.get("error"):
            safe_print(f"{version:<10} {'-':>6} {'-':>10} {'-':>8} {'-':>8}  {entry['error']}")
            continue
        scores = entry["scores"]
        safe_print(
            f"{version:<10} {entry['scored_cases']:>6} {scores['recall'] * 100:>9.1f}% "
            f"{scores['mrr']:>8.3f} {scores['ndcg']:>8.3f}  {entry.get('provider', '-')}"
        )
    versions = [v for v, e in metrics_by_version.items() if not e.get("error")]
    if len(versions) > 1:
        left, right = versions[0], versions[1]
        deltas = {
            name: metrics_by_version[right]["scores"][name] - metrics_by_version[left]["scores"][name]
            for name in ("recall", "mrr", "ndcg")
        }
        safe_print(
            f"\n{right} vs {left}: recall {deltas['recall']:+.3f}, "
            f"MRR {deltas['mrr']:+.3f}, nDCG {deltas['ndcg']:+.3f}. "
            "A move in one track only points at that track, not at the corpus."
        )


def persist_run(payload: dict) -> Path:
    runs_dir = get_settings().DATA_DIR / "qa_runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = runs_dir / f"{stamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Big Agent QA/search regression checks.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument(
        "--versions",
        default=",".join(DEFAULT_VERSIONS),
        help="Comma-separated retrieval versions to score (default: v2,v3).",
    )
    parser.add_argument("--k", type=int, default=DEFAULT_K, help="Cutoff for recall@k (default: 5).")
    parser.add_argument("--no-metrics", action="store_true", help="Run the pass/fail gate only.")
    parser.add_argument("--no-persist", action="store_true", help="Do not write data/qa_runs/.")
    args = parser.parse_args()

    versions = [item.strip() for item in args.versions.split(",") if item.strip()]
    gate_version = versions[0] if versions else "v2"
    cases = json.loads(args.cases.read_text(encoding="utf-8"))

    evaluators: dict | None = None
    evaluator_error = "metrics disabled with --no-metrics"
    if not args.no_metrics:
        evaluators, evaluator_error = load_evaluators()

    passed = 0
    failed = 0
    case_records: list[dict] = []
    samples_by_version: dict[str, list[tuple[list[int], list[int]]]] = {v: [] for v in versions}
    version_errors: dict[str, str] = {}
    legacy_cases: list[str] = []

    # Same reason as run_report_review_checks.py: match the app's startup so a
    # fresh data directory does not fail on a missing table.
    init_db()

    with SessionLocal() as session:
        qa_service = QAService(session)
        search_service = SearchService(session)
        haystack_service = HaystackRetrievalService(session)
        resolver = DocumentReferenceResolver(session)

        for index, case in enumerate(cases, start=1):
            case_type = case.get("type", "qa")
            legacy_labels = legacy_reference_labels(case)
            if legacy_labels:
                legacy_cases.append(case["name"])

            scope_ids, scope_problems = resolve_expected_ids(resolver, case, "document_ref", "document_id")
            expected_ids, expected_problems = resolve_expected_ids(
                resolver,
                case,
                "expected_source_refs",
                "expected_source_document_ids",
                "expected_refs",
                "expected_document_ids",
            )
            problems = scope_problems + expected_problems

            record: dict[str, Any] = {"name": case["name"], "type": case_type, "versions": {}}
            failures_by_version: dict[str, list[str]] = {}
            summary_by_version: dict[str, str] = {}

            for version in versions:
                if version in version_errors:
                    continue
                try:
                    if case_type == "search":
                        results, elapsed = run_search_case(
                            case, search_service, haystack_service, version
                        )
                        failures, summary = check_search_case(case, results, expected_ids)
                        ranked = ranked_document_ids(results)
                    else:
                        answer, elapsed = run_qa_case(
                            case, qa_service, scope_ids[0] if scope_ids else None, version
                        )
                        failures, summary = check_qa_case(case, answer, expected_ids)
                        ranked = ranked_document_ids(answer["sources"])
                except (HaystackUnavailableError, HaystackRetrievalError) as exc:
                    version_errors[version] = str(exc).strip() or "Haystack retrieval unavailable"
                    continue

                failures_by_version[version] = failures
                summary_by_version[version] = summary
                record["versions"][version] = {
                    "failures": failures,
                    "elapsed_seconds": round(elapsed, 4),
                    "ranked_document_ids": ranked[: args.k],
                }
                if expected_ids:
                    samples_by_version[version].append((expected_ids, ranked))

            # The pass/fail gate stays on one version so its meaning does not
            # change when a second track is scored alongside it.
            gate_failures = list(problems) + failures_by_version.get(gate_version, [])
            ok = not gate_failures
            status = "PASS" if ok else "FAIL"
            safe_print(f"[{status}] {index}. {case['name']}")
            detail = "; ".join(gate_failures) or summary_by_version.get(gate_version, "")
            safe_print(f"       {detail}")
            for version in versions[1:]:
                if version in failures_by_version and failures_by_version[version] != failures_by_version.get(
                    gate_version, []
                ):
                    other = "; ".join(failures_by_version[version]) or "ok"
                    safe_print(f"       [{version}] {other}")

            record["passed"] = ok
            record["problems"] = problems
            record["expected_document_ids"] = expected_ids
            case_records.append(record)
            passed += int(ok)
            failed += int(not ok)

        metrics_by_version: dict[str, dict] = {}
        for version in versions:
            if version in version_errors:
                metrics_by_version[version] = {"error": version_errors[version]}
                continue
            samples = samples_by_version[version]
            if evaluators is None:
                metrics_by_version[version] = {"error": evaluator_error}
            elif not samples:
                metrics_by_version[version] = {"error": "no case declares expected documents"}
            else:
                metrics_by_version[version] = {
                    "scored_cases": len(samples),
                    "scores": score_retrieval(evaluators, samples, args.k),
                    "provider": (
                        haystack_service.provider_name
                        if version == "v3"
                        else search_service.embedding_service.provider_name
                    ),
                }

    safe_print(f"\nSummary: {passed} passed, {failed} failed (gate: {gate_version})")
    if legacy_cases:
        safe_print(
            f"WARNING: {len(legacy_cases)} case(s) still pinned to a database id and will not "
            "resolve on another machine: " + ", ".join(legacy_cases[:5])
        )
    print_metrics_table(metrics_by_version, args.k)

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "app_version": APP_VERSION,
        "python": platform.python_version(),
        "cases_file": str(args.cases),
        "k": args.k,
        "gate_version": gate_version,
        "versions": versions,
        "summary": {"passed": passed, "failed": failed, "cases": len(cases)},
        "legacy_id_cases": legacy_cases,
        "metrics": metrics_by_version,
        "cases": case_records,
    }
    if not args.no_persist:
        path = persist_run(payload)
        safe_print(f"\nRun summary written to {path}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
