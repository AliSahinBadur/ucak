"""SearchService against a real (tiny) corpus, with token-hash embeddings.

`seed_corpus` gives three Turkish reports -- durability, NVH and thermal -- so
each query below has exactly one document it should reach and two it should not.
"""

from __future__ import annotations

from sqlalchemy import delete

from app.db.models import ChunkEmbedding
from app.services.search_service import SearchService
from app.services.vector_index import invalidate_vector_index

from .conftest import add_chunk, add_document


def _documents(results: list[dict]) -> list[int]:
    return [item["document_id"] for item in results]


# --- keyword_search ----------------------------------------------------------


def test_keyword_search_finds_the_document_that_owns_the_term(db_session, seed_corpus) -> None:
    service = SearchService(db_session)

    results = service.keyword_search("yorulma", limit=5)

    assert _documents(results) == [seed_corpus["durability"].id]
    assert results[0]["match_type"] == "keyword"
    assert results[0]["keyword_score"] > 0.0
    assert results[0]["semantic_score"] == 0.0
    assert "yorulma" in results[0]["chunk_text"].casefold()


def test_keyword_search_matches_through_turkish_folding(db_session, seed_corpus) -> None:
    service = SearchService(db_session)

    results = service.keyword_search("titreşim", limit=5)

    assert _documents(results) == [seed_corpus["nvh"].id]


def test_keyword_search_returns_nothing_for_an_absent_term(db_session, seed_corpus) -> None:
    service = SearchService(db_session)

    assert service.keyword_search("hidrojen yakit hucresi", limit=5) == []


def test_keyword_search_returns_nothing_for_a_blank_query(db_session, seed_corpus) -> None:
    service = SearchService(db_session)

    assert service.keyword_search("   ", limit=5) == []


def test_keyword_search_honours_a_document_scope(db_session, seed_corpus) -> None:
    service = SearchService(db_session)

    results = service.keyword_search("olcum", limit=5, document_ids=[seed_corpus["nvh"].id])

    assert _documents(results) == [seed_corpus["nvh"].id]


def test_keyword_search_short_circuits_on_a_scope_that_normalizes_to_empty(db_session, seed_corpus) -> None:
    service = SearchService(db_session)

    assert service.keyword_search("olcum", limit=5, document_ids=[0, -1]) == []


def test_keyword_search_returns_one_chunk_per_document_by_default(db_session, seed_corpus) -> None:
    service = SearchService(db_session)

    default_results = service.keyword_search("yorulma", limit=5)
    widened = service.keyword_search("yorulma", limit=5, max_results_per_document=2)

    durability_id = seed_corpus["durability"].id
    assert _documents(default_results).count(durability_id) == 1
    assert _documents(widened).count(durability_id) == 2


def test_keyword_search_respects_the_limit(db_session, seed_corpus) -> None:
    service = SearchService(db_session)

    assert len(service.keyword_search("olcum", limit=1)) == 1


# --- semantic_search ---------------------------------------------------------


def test_semantic_search_reaches_the_matching_document(db_session, seed_corpus) -> None:
    service = SearchService(db_session)

    results = service.semantic_search("radyator sicakligi", limit=5)

    assert _documents(results) == [seed_corpus["thermal"].id]
    assert results[0]["match_type"] == "semantic"
    assert results[0]["semantic_score"] >= SearchService.MIN_SEMANTIC_SCORE
    assert results[0]["keyword_score"] == 0.0


def test_semantic_search_honours_a_document_scope(db_session, seed_corpus) -> None:
    service = SearchService(db_session)

    scoped = service.semantic_search(
        "radyator sicakligi", limit=5, document_ids=[seed_corpus["nvh"].id]
    )

    assert scoped == []


def test_semantic_search_is_empty_without_any_embeddings(db_session, seed_corpus) -> None:
    db_session.execute(delete(ChunkEmbedding))
    db_session.commit()
    invalidate_vector_index()
    service = SearchService(db_session)

    assert service.semantic_search("radyator sicakligi", limit=5) == []


def test_semantic_search_is_empty_for_a_query_with_no_signal(db_session, seed_corpus) -> None:
    service = SearchService(db_session)

    # Punctuation alone yields no tokens, so the token-hash vector is all zeros.
    assert service.semantic_search("...", limit=5) == []


def test_semantic_search_works_on_the_v1_retrieval_path(db_session, seed_corpus) -> None:
    service = SearchService(db_session)

    results = service.semantic_search("radyator sicakligi", limit=5, retrieval_version="v1")

    assert _documents(results) == [seed_corpus["thermal"].id]


# --- hybrid_search -----------------------------------------------------------


def test_hybrid_search_labels_a_result_hit_by_both_paths(db_session, seed_corpus) -> None:
    service = SearchService(db_session)

    results = service.hybrid_search("dayanim testi", limit=5)

    assert _documents(results) == [seed_corpus["durability"].id]
    assert results[0]["match_type"] == "hybrid"
    assert results[0]["keyword_score"] > 0.0
    assert results[0]["semantic_score"] > 0.0
    assert results[0]["combined_score"] > 0.0


def test_hybrid_search_falls_back_to_keyword_ranking_without_embeddings(db_session, seed_corpus) -> None:
    db_session.execute(delete(ChunkEmbedding))
    db_session.commit()
    invalidate_vector_index()
    service = SearchService(db_session)

    results = service.hybrid_search("dayanim testi", limit=5)

    assert _documents(results) == [seed_corpus["durability"].id]
    assert results[0]["match_type"] == "keyword"


def test_hybrid_search_returns_nothing_for_an_absent_term(db_session, seed_corpus) -> None:
    service = SearchService(db_session)

    assert service.hybrid_search("hidrojen yakit hucresi", limit=5) == []


def test_hybrid_search_ranks_the_report_code_owner_first(db_session, seed_corpus) -> None:
    service = SearchService(db_session)

    results = service.hybrid_search("2025-BIG-E-DUR-01 raporu", limit=5)

    assert results
    assert results[0]["document_id"] == seed_corpus["durability"].id
    # The metadata rerank pass adds its own score component to the winner.
    assert results[0]["metadata_score"] > 0.0


# --- report_search -----------------------------------------------------------


def test_report_search_returns_document_level_hits(db_session, seed_corpus) -> None:
    service = SearchService(db_session)

    results = service.report_search("titresim", limit=5)

    assert _documents(results) == [seed_corpus["nvh"].id]
    assert results[0]["document_title"] == "2024-BIG-E-NVH-07 Titresim ve Gurultu Raporu"


def test_report_search_needs_a_query(db_session, seed_corpus) -> None:
    service = SearchService(db_session)

    assert service.report_search("   ", limit=5) == []
    assert service.report_search("...", limit=5) == []


# --- similar documents / availability ---------------------------------------


def test_similar_documents_excludes_the_source_document(db_session, seed_corpus) -> None:
    service = SearchService(db_session)
    results = service.keyword_search("yorulma", limit=5)

    similar = service.similar_documents_for_results(results, limit=3)

    source_ids = set(_documents(results))
    assert similar
    assert not source_ids.intersection(item["document_id"] for item in similar)
    assert all(item["top_excerpt"] for item in similar)


def test_similar_documents_is_empty_without_results(db_session, seed_corpus) -> None:
    service = SearchService(db_session)

    assert service.similar_documents_for_results([], limit=3) == []


def test_similar_documents_is_empty_when_sources_have_no_embeddings(db_session, seed_corpus) -> None:
    service = SearchService(db_session)
    results = service.keyword_search("yorulma", limit=5)
    db_session.execute(delete(ChunkEmbedding))
    db_session.commit()
    invalidate_vector_index()

    assert service.similar_documents_for_results(results, limit=3) == []


def test_semantic_available_tracks_the_embedding_table(db_session, seed_corpus) -> None:
    service = SearchService(db_session)
    assert service.semantic_available() is True

    db_session.execute(delete(ChunkEmbedding))
    db_session.commit()

    assert service.semantic_available() is False


def test_semantic_available_is_false_for_a_corpus_with_no_chunks(db_session) -> None:
    add_document(db_session, "Bos Rapor")
    db_session.commit()

    assert SearchService(db_session).semantic_available() is False


def test_search_ignores_chunks_whose_document_was_never_embedded(db_session, seed_corpus) -> None:
    unembedded = add_document(db_session, "Gomulmemis Rapor", file_name="gomulmemis.pdf")
    add_chunk(db_session, unembedded, "Radyator cikis sicakligi burada da geciyor.", embedding=None)
    db_session.commit()
    invalidate_vector_index()
    service = SearchService(db_session)

    assert unembedded.id in _documents(service.keyword_search("radyator", limit=5))
    assert unembedded.id not in _documents(service.semantic_search("radyator sicakligi", limit=5))
