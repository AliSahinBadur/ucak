from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.api_models import ReportComparisonMultiRequest, ReportComparisonMultiResponse
from app.main import app
from app.services.report_comparison_service import (
    ComparisonChunk,
    ComparisonDocument,
    ReportComparisonService,
)


def _document(index: int) -> ComparisonDocument:
    return ComparisonDocument(
        source_ref=f"document:{index}",
        title=f"Doküman {index}",
        file_name=f"dokuman-{index}.pdf",
        source_path=Path(f"dokuman-{index}.pdf"),
        content_hash=f"hash-{index}",
        document_id=index,
        temporary=False,
        chunks=[
            ComparisonChunk(
                key=f"chunk-{index}",
                page_start=1,
                page_end=1,
                section_title="Sonuç",
                text="Teknik değerlendirme sonucu uygundur.",
                vector=[1.0],
            )
        ],
    )


def _pair_result(service: ReportComparisonService, left: ComparisonDocument, right: ComparisonDocument) -> dict:
    empty_pdf = {
        "available": False,
        "url": None,
        "file_name": "",
        "highlighted_passages": 0,
        "reason": "Test kaynağı",
    }
    return {
        "comparison_id": f"{'0' * 62}{left.document_id}{right.document_id}",
        "left": service._document_payload(left),
        "right": service._document_payload(right),
        "left_pdf": {**empty_pdf, "file_name": left.file_name},
        "right_pdf": {**empty_pdf, "file_name": right.file_name},
        "similarities": [],
        "differences": [],
        "similarity_count": 0,
        "difference_count": 0,
        "matched_pair_count": 0,
        "coverage": 0.5,
        "embedding_provider": "test-embedding",
        "generation_provider": "deterministic",
        "llm_used": False,
        "cache_hit": False,
    }


def _service(monkeypatch: pytest.MonkeyPatch, documents: list[ComparisonDocument]):
    service = object.__new__(ReportComparisonService)
    service.embedding_service = SimpleNamespace(provider_name="test-embedding")
    resolved: list[int] = []
    compared: list[tuple[int, int]] = []

    def resolve(source: dict) -> ComparisonDocument:
        index = int(source["document_id"])
        resolved.append(index)
        return next(document for document in documents if document.document_id == index)

    def compare(left: ComparisonDocument, right: ComparisonDocument, *, use_llm: bool) -> dict:
        assert use_llm is False
        compared.append((int(left.document_id or 0), int(right.document_id or 0)))
        return _pair_result(service, left, right)

    monkeypatch.setattr(service, "_resolve_source", resolve)
    monkeypatch.setattr(service, "_compare_documents", compare)
    return service, resolved, compared


def test_multi_request_has_no_arbitrary_document_cap() -> None:
    payload = ReportComparisonMultiRequest(
        sources=[{"document_id": index} for index in range(1, 101)]
    )
    assert len(payload.sources) == 100
    assert payload.mode == "reference"


def test_reference_mode_resolves_each_source_once_and_preserves_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    documents = [_document(index) for index in range(1, 5)]
    service, resolved, compared = _service(monkeypatch, documents)

    result = service.compare_many(
        [{"document_id": index} for index in range(1, 5)],
        mode="reference",
        reference_index=2,
        use_llm=False,
    )

    assert resolved == [1, 2, 3, 4]
    assert compared == [(3, 1), (3, 2), (3, 4)]
    assert [item["document_id"] for item in result["documents"]] == [1, 2, 3, 4]
    assert result["comparison_count"] == 3
    assert result["reference_index"] == 2
    ReportComparisonMultiResponse.model_validate(result)


def test_all_pairs_mode_builds_each_unique_pair_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    documents = [_document(index) for index in range(1, 5)]
    service, resolved, compared = _service(monkeypatch, documents)

    result = service.compare_many(
        [{"document_id": index} for index in range(1, 5)],
        mode="all_pairs",
        use_llm=False,
    )

    assert resolved == [1, 2, 3, 4]
    assert compared == [(1, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 4)]
    assert result["comparison_count"] == 6
    assert [item["pair_key"] for item in result["comparisons"]] == [
        "0:1",
        "0:2",
        "0:3",
        "1:2",
        "1:3",
        "2:3",
    ]


def test_multi_comparison_rejects_duplicate_resolved_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate = _document(1)
    service = object.__new__(ReportComparisonService)
    service.embedding_service = SimpleNamespace(provider_name="test-embedding")
    monkeypatch.setattr(service, "_resolve_source", lambda source: duplicate)

    with pytest.raises(ValueError, match="birden fazla"):
        service.compare_many(
            [{"document_id": 1}, {"document_id": 1}],
            use_llm=False,
        )


def test_old_pair_endpoint_and_new_multi_endpoint_are_both_published() -> None:
    paths = app.openapi()["paths"]
    assert "post" in paths["/report-comparison"]
    assert "post" in paths["/report-comparison/multi"]
