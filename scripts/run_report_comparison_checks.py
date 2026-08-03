from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if "BIG_AGENT_DATA_DIR" not in os.environ and (ROOT_DIR / "data_analiz" / "app.db").exists():
    os.environ["BIG_AGENT_DATA_DIR"] = str(ROOT_DIR / "data_analiz")
os.environ.setdefault("EMBEDDING_PROVIDER", "token-hash")
os.environ.setdefault("CHAT_LLM_ENABLED", "false")

from sqlalchemy import select
from pypdf import PdfReader

from app.db.models import Document
from app.db.session import SessionLocal
from app.services.embedding_service import TokenHashEmbeddingService
from app.services.llm_provider import DisabledLLMProvider
from app.services.report_comparison_service import ReportComparisonService


def safe_print(value: str) -> None:
    print(value.encode("ascii", "backslashreplace").decode("ascii"))


def require_document(session, title: str) -> Document:
    document = session.scalar(select(Document).where(Document.title == title))
    if document is None:
        raise RuntimeError(f"Test document is missing: {title}")
    return document


def check(name: str, condition: bool, detail: str) -> bool:
    safe_print(f"[{'PASS' if condition else 'FAIL'}] {name}: {detail}")
    return condition


def main() -> int:
    passed = 0
    failed = 0
    with tempfile.TemporaryDirectory() as temp_dir, SessionLocal() as session:
        service = ReportComparisonService(
            session,
            embedding_service=TokenHashEmbeddingService(),
            llm_provider=DisabledLLMProvider(),
            temp_dir=temp_dir,
            cache_dir=temp_dir,
        )
        nvh_left = require_document(session, "2025-BIG-e-NVH-01")
        nvh_right = require_document(session, "2025-BIG-e-NVH-02")
        structural_left = require_document(session, "2025-BIG-e-DUR-02")
        structural_right = require_document(session, "2025-BIG-e-DUR-03")

        related = service.compare(
            {"document_id": nvh_left.id},
            {"document_id": nvh_right.id},
            use_llm=False,
        )
        ok = check(
            "related reports",
            related["similarity_count"] >= 3 and related["difference_count"] >= 1,
            f"similarities={related['similarity_count']}, differences={related['difference_count']}",
        )
        passed += int(ok)
        failed += int(not ok)

        evidence_items = related["similarities"] + related["differences"]
        evidence_ok = all(
            item["left"]["excerpt"]
            and item["right"]["excerpt"]
            and item["left"]["document_title"]
            and item["right"]["document_title"]
            for item in evidence_items
        )
        ok = check("source evidence", evidence_ok, f"items={len(evidence_items)}")
        passed += int(ok)
        failed += int(not ok)

        comparison_id = related["comparison_id"]
        left_preview_path = Path(temp_dir) / "pdf" / f"{comparison_id}-left.pdf"
        highlighted_annotations = 0
        if left_preview_path.exists():
            preview_reader = PdfReader(str(left_preview_path))
            highlighted_annotations = sum(
                1
                for page in preview_reader.pages
                for annotation in (page.get("/Annots") or [])
                if annotation.get_object().get("/Subtype") == "/Highlight"
            )
        highlighted_items = [
            item
            for item in evidence_items
            if item.get("highlight_color") and item.get("highlight_number")
        ]
        ok = check(
            "colored PDF previews",
            (
                related["left_pdf"]["available"]
                and related["right_pdf"]["available"]
                and related["left_pdf"]["highlighted_passages"] >= 1
                and related["right_pdf"]["highlighted_passages"] >= 1
                and highlighted_annotations >= 1
                and bool(highlighted_items)
            ),
            (
                f"left={related['left_pdf']['highlighted_passages']}, "
                f"right={related['right_pdf']['highlighted_passages']}, "
                f"annotations={highlighted_annotations}"
            ),
        )
        passed += int(ok)
        failed += int(not ok)

        different = service.compare(
            {"document_id": structural_left.id},
            {"document_id": structural_right.id},
            use_llm=False,
        )
        ok = check(
            "different reports",
            different["difference_count"] >= 2,
            f"differences={different['difference_count']}",
        )
        passed += int(ok)
        failed += int(not ok)

        source_path = Path(nvh_left.file_path)
        temporary = service.store_temporary_upload(nvh_left.file_name, source_path.read_bytes())
        exact_copy = service.compare(
            {"upload_token": temporary["upload_token"]},
            {"document_id": nvh_left.id},
            use_llm=False,
        )
        ok = check(
            "temporary exact copy",
            exact_copy["similarity_count"] >= 3 and exact_copy["difference_count"] == 0,
            f"similarities={exact_copy['similarity_count']}, differences={exact_copy['difference_count']}",
        )
        passed += int(ok)
        failed += int(not ok)

        same_source_rejected = False
        try:
            service.compare(
                {"document_id": nvh_left.id},
                {"document_id": nvh_left.id},
                use_llm=False,
            )
        except ValueError:
            same_source_rejected = True
        ok = check("same source rejected", same_source_rejected, "expected ValueError")
        passed += int(ok)
        failed += int(not ok)

    safe_print(f"Summary: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
