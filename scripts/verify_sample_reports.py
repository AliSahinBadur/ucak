"""Ingest the synthetic corpus into a throwaway database and print its findings.

This is the check that `generate_sample_reports.py` produced what it claims:
each report's planted defect should appear, and the clean ones should stay
quiet. It never touches the real database -- it builds its own SQLite file in a
temp directory and deletes it on the way out.

    python scripts/verify_sample_reports.py
    python scripts/verify_sample_reports.py --keep     # leave the temp db behind
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sys
import tempfile


BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Must be set before anything under `app` is imported: the engine is built from
# Settings at import time and get_settings() is cached.
_TEMP_DIR = Path(tempfile.mkdtemp(prefix="syn-verify-"))
os.environ["BIG_AGENT_DATA_DIR"] = str(_TEMP_DIR)
os.environ["EMBEDDING_BACKEND"] = "token-hash"
os.environ["LLM_ENABLED"] = "false"
os.environ["CHAT_LLM_ENABLED"] = "false"
os.environ["REPORT_LLM_ENABLED"] = "false"

from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.ingest_service import IngestService  # noqa: E402
from app.services.report_review_service import ReportReviewService  # noqa: E402

sys.path.remove(str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scripts"))
from generate_sample_reports import REPORTS  # noqa: E402


STATUS_MARK = {"fail": "FAIL", "needs_review": "review", "pass": "pass", "not_applicable": "n/a"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, default=BASE_DIR / "sample_reports")
    parser.add_argument("--keep", action="store_true", help="do not delete the temp database")
    args = parser.parse_args()

    if not args.dir.is_dir():
        print(f"! {args.dir} not found - run scripts/generate_sample_reports.py first")
        return 2

    expectations = {report["code"]: report["expect"] for report in REPORTS}

    init_db()
    problems = 0
    with SessionLocal() as session:
        ingest = IngestService(session)
        review = ReportReviewService(session)

        for path in sorted(args.dir.iterdir()):
            if path.suffix.lower() not in {".pdf", ".docx", ".pptx"}:
                continue
            result = ingest.ingest(path, original_file_name=path.name)
            document_id = int(result["document_id"])
            if result.get("status") == "duplicate":
                print(f"\n{path.name}\n  duplicate of document {document_id} - not re-ingested")
                continue

            analysis = review.analyze_documents([document_id])
            document = analysis["documents"][0]
            findings = document["findings"]
            expected = expectations.get(path.stem, "")

            print(f"\n{path.name}  [profile: {document['profile']}, pages: {document['page_count']}]")
            if expected:
                print(f"  expected: {expected}")
            if not findings:
                print("  findings: none")
            for finding in findings:
                mark = STATUS_MARK.get(finding["status"], finding["status"])
                page = finding["page_start"] or "-"
                print(f"  [{mark:6}] {finding['rule_id']:34} p{page}  {finding['severity']}")

            quiet_expected = expected.startswith("clean") or "resolved" in expected
            if quiet_expected and findings:
                problems += 1
                print("  !! expected no findings")
            if expected and not quiet_expected and not findings:
                problems += 1
                print("  !! expected a finding, got none")

    if not args.keep:
        shutil.rmtree(_TEMP_DIR, ignore_errors=True)
    else:
        print(f"\ntemp database kept at {_TEMP_DIR}")

    print(f"\n{'OK - every report matched its expectation' if not problems else f'{problems} report(s) did not match'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
