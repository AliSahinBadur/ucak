"""Embedding provider contract: serialization, similarity and the token-hash fallback.

`serialize`/`deserialize` are the boundary the whole retrieval stack sits on --
`vector_index` decodes every row through them, and the corpus still contains
JSON-text vectors written before the BLOB migration.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from app.services.embedding_service import (
    BaseEmbeddingService,
    TokenHashEmbeddingService,
    build_embedding_service,
)


# --- serialize / deserialize -------------------------------------------------


def test_serialize_round_trips_through_float32() -> None:
    vector = [0.25, -0.5, 0.125]

    restored = BaseEmbeddingService.deserialize(BaseEmbeddingService.serialize(vector))

    assert restored == pytest.approx(vector)


def test_serialize_produces_four_bytes_per_value() -> None:
    assert len(BaseEmbeddingService.serialize([1.0, 2.0, 3.0])) == 12


def test_deserialize_accepts_legacy_json_text() -> None:
    assert BaseEmbeddingService.deserialize("[1.0, 2.0]") == [1.0, 2.0]


def test_deserialize_accepts_legacy_json_handed_back_as_bytes() -> None:
    payload = json.dumps([1.5, -2.5]).encode("utf-8")

    assert BaseEmbeddingService.deserialize(payload) == [1.5, -2.5]


def test_deserialize_treats_empty_payloads_as_no_vector() -> None:
    assert BaseEmbeddingService.deserialize(None) == []
    assert BaseEmbeddingService.deserialize(b"") == []
    assert BaseEmbeddingService.deserialize("") == []


def test_deserialize_rejects_a_truncated_binary_payload() -> None:
    # Three bytes is not a whole number of float32 values; vector_index relies on
    # this raising so it can skip the row instead of corrupting the matrix.
    with pytest.raises(ValueError):
        BaseEmbeddingService.deserialize(b"\x01\x02\x03")


def test_deserialize_reads_a_memoryview_from_the_driver() -> None:
    payload = BaseEmbeddingService.serialize([1.0, 0.0])

    assert BaseEmbeddingService.deserialize(memoryview(payload)) == pytest.approx([1.0, 0.0])


# --- cosine_similarity / has_signal -----------------------------------------


def test_cosine_similarity_spans_identical_orthogonal_and_opposite() -> None:
    assert BaseEmbeddingService.cosine_similarity([1.0, 0.0], [2.0, 0.0]) == pytest.approx(1.0)
    assert BaseEmbeddingService.cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert BaseEmbeddingService.cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_similarity_is_zero_for_unusable_inputs() -> None:
    assert BaseEmbeddingService.cosine_similarity([], [1.0]) == 0.0
    assert BaseEmbeddingService.cosine_similarity([1.0], []) == 0.0
    assert BaseEmbeddingService.cosine_similarity([1.0, 0.0], [1.0]) == 0.0
    assert BaseEmbeddingService.cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_has_signal_only_rejects_an_all_zero_vector() -> None:
    assert BaseEmbeddingService.has_signal([0.0, 0.1]) is True
    assert BaseEmbeddingService.has_signal([-0.5]) is True
    assert BaseEmbeddingService.has_signal([0.0, 0.0]) is False
    assert BaseEmbeddingService.has_signal([]) is False


def test_tokenize_folds_case_and_keeps_turkish_letters() -> None:
    # Dotted capital I casefolds to "i" plus a combining dot; the combining mark
    # is not a word character, so only the base letter survives the split.
    assert BaseEmbeddingService.tokenize("Dayanım TESTİ raporu") == ["dayanım", "testi", "raporu"]
    assert BaseEmbeddingService.tokenize("2025-BIG-E-DUR-01") == ["2025", "big", "e", "dur", "01"]
    assert BaseEmbeddingService.tokenize("   ") == []


# --- TokenHashEmbeddingService ----------------------------------------------


def test_token_hash_vectors_are_deterministic() -> None:
    service = TokenHashEmbeddingService()

    assert service.embed_text("dayanim testi") == service.embed_text("dayanim testi")


def test_token_hash_vectors_are_unit_length() -> None:
    vector = TokenHashEmbeddingService().embed_text("dayanim testi raporu")

    assert math.sqrt(sum(value * value for value in vector)) == pytest.approx(1.0)


def test_token_hash_dimension_is_configurable_and_respected() -> None:
    assert len(TokenHashEmbeddingService().embed_text("metin")) == 256
    assert len(TokenHashEmbeddingService(dimensions=32).embed_text("metin")) == 32


def test_token_hash_returns_a_signal_free_vector_for_text_without_tokens() -> None:
    service = TokenHashEmbeddingService(dimensions=8)

    vector = service.embed_text("...")

    assert vector == [0.0] * 8
    assert service.has_signal(vector) is False


def test_token_hash_is_a_bag_of_words() -> None:
    service = TokenHashEmbeddingService()

    assert service.embed_text("dayanim testi") == service.embed_text("testi dayanim")


def test_token_hash_separates_unrelated_texts() -> None:
    service = TokenHashEmbeddingService()

    similarity = service.cosine_similarity(
        service.embed_text("radyator sicakligi"), service.embed_text("koltuk rayi titresimi")
    )

    assert similarity < 0.2


def test_token_hash_query_and_document_roles_share_one_encoder() -> None:
    service = TokenHashEmbeddingService()
    text = "yorulma olcumleri"

    assert service.embed_query(text) == service.embed_document(text) == service.embed_text(text)


def test_token_hash_vectors_survive_the_storage_round_trip(tmp_path) -> None:  # noqa: ARG001
    service = TokenHashEmbeddingService()
    vector = service.embed_text("gerinim olcer verileri")

    restored = service.deserialize(service.serialize(vector))

    assert np.asarray(restored, dtype=np.float32) == pytest.approx(
        np.asarray(vector, dtype=np.float32)
    )


# --- provider selection ------------------------------------------------------


def test_build_embedding_service_honours_the_configured_backend_and_caches_it() -> None:
    service = build_embedding_service()

    assert service.provider_name == "token-hash-v1"
    assert build_embedding_service() is service
