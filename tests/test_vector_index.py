"""Vector index: matrix construction, cosine scoring, and cache freshness."""

from __future__ import annotations

import numpy as np
import pytest
from sqlalchemy import delete, update

from app.db.models import ChunkEmbedding
from app.services.embedding_service import BaseEmbeddingService
from app.services.vector_index import (
    VectorIndex,
    get_vector_index,
    invalidate_vector_index,
)

from .conftest import add_chunk, add_document


def _index(vectors: list[list[float]]) -> VectorIndex:
    """A VectorIndex over already-normalized rows, ids 1..n in document 1..n."""
    matrix = np.asarray(vectors, dtype=np.float32)
    return VectorIndex(
        chunk_ids=np.arange(1, len(vectors) + 1, dtype=np.int64),
        document_ids=np.arange(1, len(vectors) + 1, dtype=np.int64),
        matrix=matrix,
        dimensions=matrix.shape[1],
    )


# --- cosine_scores -----------------------------------------------------------


def test_cosine_scores_ranks_rows_by_angle_to_the_query() -> None:
    half = float(np.sqrt(0.5))
    index = _index([[1.0, 0.0], [half, half], [0.0, 1.0]])

    scores = index.cosine_scores([1.0, 0.0])

    assert scores is not None
    assert np.argmax(scores) == 0
    assert scores[0] == pytest.approx(1.0)
    assert scores[1] == pytest.approx(half)
    assert scores[2] == pytest.approx(0.0, abs=1e-6)
    assert list(np.argsort(scores)[::-1]) == [0, 1, 2]


def test_cosine_scores_ignores_query_magnitude() -> None:
    index = _index([[1.0, 0.0], [0.0, 1.0]])

    unit = index.cosine_scores([1.0, 1.0])
    scaled = index.cosine_scores([1000.0, 1000.0])

    assert unit is not None and scaled is not None
    assert scaled == pytest.approx(unit)


def test_cosine_scores_returns_none_for_wrong_dimensions() -> None:
    index = _index([[1.0, 0.0], [0.0, 1.0]])

    assert index.cosine_scores([1.0, 0.0, 0.0]) is None
    assert index.cosine_scores([1.0]) is None


def test_cosine_scores_returns_none_for_a_zero_query() -> None:
    index = _index([[1.0, 0.0], [0.0, 1.0]])

    assert index.cosine_scores([0.0, 0.0]) is None


def test_cosine_scores_returns_none_for_a_non_vector_query() -> None:
    index = _index([[1.0, 0.0], [0.0, 1.0]])

    assert index.cosine_scores([[1.0, 0.0], [0.0, 1.0]]) is None


# --- cosine_scores_many ------------------------------------------------------


def test_cosine_scores_many_returns_one_column_per_query() -> None:
    index = _index([[1.0, 0.0], [0.0, 1.0]])

    scores = index.cosine_scores_many([[1.0, 0.0], [0.0, 1.0]])

    assert scores is not None
    assert scores.shape == (2, 2)
    assert scores[0][0] == pytest.approx(1.0)
    assert scores[1][1] == pytest.approx(1.0)
    assert scores[0][1] == pytest.approx(0.0, abs=1e-6)


def test_cosine_scores_many_drops_incompatible_queries() -> None:
    index = _index([[1.0, 0.0], [0.0, 1.0]])

    scores = index.cosine_scores_many([[1.0, 0.0, 0.0], [0.0, 1.0]])

    assert scores is not None
    # Only the 2-dimensional query survives, so there is a single column.
    assert scores.shape == (2, 1)
    assert scores[1][0] == pytest.approx(1.0)


def test_cosine_scores_many_returns_none_when_no_query_matches_dimensions() -> None:
    index = _index([[1.0, 0.0], [0.0, 1.0]])

    assert index.cosine_scores_many([[1.0, 0.0, 0.0]]) is None
    assert index.cosine_scores_many([]) is None


def test_cosine_scores_many_survives_a_zero_query_without_dividing_by_zero() -> None:
    index = _index([[1.0, 0.0], [0.0, 1.0]])

    scores = index.cosine_scores_many([[0.0, 0.0], [1.0, 0.0]])

    assert scores is not None
    assert np.all(scores[:, 0] == 0.0)
    assert scores[0][1] == pytest.approx(1.0)


# --- loading from the database ----------------------------------------------


def test_index_is_none_when_no_embeddings_exist(db_session) -> None:
    document = add_document(db_session, "Bos Rapor")
    add_chunk(db_session, document, "Govde metni", embedding=None)
    db_session.commit()

    assert get_vector_index(db_session) is None


def test_rows_align_with_their_chunk_and_document_ids(db_session) -> None:
    left = add_document(db_session, "Sol Rapor")
    right = add_document(db_session, "Sag Rapor")
    left_chunk = add_chunk(db_session, left, "sol", embedding=[1.0, 0.0])
    right_chunk = add_chunk(db_session, right, "sag", embedding=[0.0, 1.0])
    db_session.commit()

    index = get_vector_index(db_session)

    assert index is not None
    assert list(index.chunk_ids) == [left_chunk.id, right_chunk.id]
    assert list(index.document_ids) == [left.id, right.id]
    assert index.dimensions == 2
    # Row i really is chunk_ids[i]'s vector.
    scores = index.cosine_scores([1.0, 0.0])
    assert scores is not None
    assert index.chunk_ids[int(np.argmax(scores))] == left_chunk.id


def test_stored_vectors_are_l2_normalized_on_load(db_session) -> None:
    document = add_document(db_session, "Olcekli Rapor")
    add_chunk(db_session, document, "buyuk", embedding=[3.0, 4.0])
    db_session.commit()

    index = get_vector_index(db_session)

    assert index is not None
    assert float(np.linalg.norm(index.matrix[0])) == pytest.approx(1.0)
    assert index.matrix[0] == pytest.approx([0.6, 0.8])


def test_zero_norm_vectors_are_dropped_from_the_matrix(db_session) -> None:
    document = add_document(db_session, "Karisik Rapor")
    signal_chunk = add_chunk(db_session, document, "sinyal", embedding=[1.0, 0.0])
    add_chunk(db_session, document, "sessiz", chunk_order=2, embedding=[0.0, 0.0])
    db_session.commit()

    index = get_vector_index(db_session)

    assert index is not None
    assert list(index.chunk_ids) == [signal_chunk.id]


def test_index_is_none_when_every_vector_is_zero(db_session) -> None:
    document = add_document(db_session, "Sessiz Rapor")
    add_chunk(db_session, document, "sessiz", embedding=[0.0, 0.0])
    db_session.commit()

    assert get_vector_index(db_session) is None


def test_mixed_dimensions_keep_the_dominant_dimension(db_session) -> None:
    document = add_document(db_session, "Gecis Raporu")
    two_dim_a = add_chunk(db_session, document, "iki-a", embedding=[1.0, 0.0])
    two_dim_b = add_chunk(db_session, document, "iki-b", chunk_order=2, embedding=[0.0, 1.0])
    add_chunk(db_session, document, "uc", chunk_order=3, embedding=[1.0, 0.0, 0.0])
    db_session.commit()

    index = get_vector_index(db_session)

    assert index is not None
    assert index.dimensions == 2
    assert list(index.chunk_ids) == [two_dim_a.id, two_dim_b.id]


def test_undecodable_payloads_are_skipped_rather_than_failing_the_load(db_session) -> None:
    document = add_document(db_session, "Bozuk Rapor")
    good_chunk = add_chunk(db_session, document, "saglam", embedding=[1.0, 0.0])
    # Three bytes is not a whole number of float32 values.
    add_chunk(db_session, document, "bozuk", chunk_order=2, embedding=b"\x01\x02\x03")
    db_session.commit()

    index = get_vector_index(db_session)

    assert index is not None
    assert list(index.chunk_ids) == [good_chunk.id]


def test_legacy_json_text_embeddings_still_load(db_session) -> None:
    document = add_document(db_session, "Eski Rapor")
    chunk = add_chunk(db_session, document, "eski", embedding=b"[1.0, 0.0]")
    db_session.commit()

    index = get_vector_index(db_session)

    assert index is not None
    assert list(index.chunk_ids) == [chunk.id]
    assert index.matrix[0] == pytest.approx([1.0, 0.0])


# --- cache freshness ---------------------------------------------------------


def test_repeated_reads_return_the_same_cached_object(db_session) -> None:
    document = add_document(db_session, "Onbellek Raporu")
    add_chunk(db_session, document, "metin", embedding=[1.0, 0.0])
    db_session.commit()

    assert get_vector_index(db_session) is get_vector_index(db_session)


def test_stamp_notices_an_inserted_embedding(db_session) -> None:
    document = add_document(db_session, "Buyuyen Rapor")
    add_chunk(db_session, document, "ilk", embedding=[1.0, 0.0])
    db_session.commit()
    assert get_vector_index(db_session).chunk_ids.size == 1

    add_chunk(db_session, document, "ikinci", chunk_order=2, embedding=[0.0, 1.0])
    db_session.commit()

    # No invalidate() call: the (count, max id, sum of ids) stamp alone must catch this.
    assert get_vector_index(db_session).chunk_ids.size == 2


def test_stamp_notices_a_deleted_embedding(db_session) -> None:
    document = add_document(db_session, "Kuculen Rapor")
    keep = add_chunk(db_session, document, "kalan", embedding=[1.0, 0.0])
    drop = add_chunk(db_session, document, "silinen", chunk_order=2, embedding=[0.0, 1.0])
    db_session.commit()
    assert get_vector_index(db_session).chunk_ids.size == 2

    db_session.execute(delete(ChunkEmbedding).where(ChunkEmbedding.chunk_id == drop.id))
    db_session.commit()

    assert list(get_vector_index(db_session).chunk_ids) == [keep.id]


def test_stamp_notices_the_last_embedding_disappearing(db_session) -> None:
    document = add_document(db_session, "Silinecek Rapor")
    add_chunk(db_session, document, "tek", embedding=[1.0, 0.0])
    db_session.commit()
    assert get_vector_index(db_session) is not None

    db_session.execute(delete(ChunkEmbedding))
    db_session.commit()

    assert get_vector_index(db_session) is None


def test_in_place_rebuild_is_invisible_to_the_stamp_and_needs_invalidate(db_session) -> None:
    """Pins the mk2 6.6 limitation: identical chunk ids produce an identical stamp.

    EmbeddingReindexService.rebuild deletes every row and re-inserts with the
    same chunk_id values, so (count, max id, sum of ids) is unchanged even though
    every vector is different. Correctness therefore rests entirely on the
    explicit invalidate_vector_index() call the rebuild makes, which is what this
    test documents. If the stamp ever gains a version counter, the stale
    assertion below is the one that should flip.
    """
    document = add_document(db_session, "Yeniden Kurulan Rapor")
    chunk = add_chunk(db_session, document, "metin", embedding=[1.0, 0.0])
    db_session.commit()
    assert get_vector_index(db_session).matrix[0] == pytest.approx([1.0, 0.0])

    db_session.execute(
        update(ChunkEmbedding)
        .where(ChunkEmbedding.chunk_id == chunk.id)
        .values(embedding=BaseEmbeddingService.serialize([0.0, 1.0]))
    )
    db_session.commit()

    # Stale: same count, same max id, same id sum, so the cache is reused.
    assert get_vector_index(db_session).matrix[0] == pytest.approx([1.0, 0.0])

    invalidate_vector_index()

    assert get_vector_index(db_session).matrix[0] == pytest.approx([0.0, 1.0])


def test_invalidate_forces_a_reload_even_when_nothing_changed(db_session) -> None:
    document = add_document(db_session, "Tazelenen Rapor")
    add_chunk(db_session, document, "metin", embedding=[1.0, 0.0])
    db_session.commit()
    first = get_vector_index(db_session)

    invalidate_vector_index()
    second = get_vector_index(db_session)

    assert first is not second
    assert list(first.chunk_ids) == list(second.chunk_ids)
