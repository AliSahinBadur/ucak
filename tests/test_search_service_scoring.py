"""SearchService scoring and gating, exercised without a database.

Every function here is pure over strings and dicts, so it needs no session --
`SearchService(None)` is enough for the two instance methods involved.
"""

from __future__ import annotations

import pytest

from app.services.search_service import SearchService
from app.text.normalize import tokenize


DUR_ITEM = {
    "document_title": "2025-BIG-E-DUR-01 Dayanim Testi Raporu",
    "file_name": "2025-BIG-E-DUR-01-dayanim.pdf",
}
NVH_ITEM = {
    "document_title": "2024-BIG-E-NVH-07 Titresim Raporu",
    "file_name": "2024-BIG-E-NVH-07-titresim.pdf",
}


def profile_for(query: str) -> dict:
    return SearchService._query_profile(query, tokenize(query))


# --- _keyword_score ----------------------------------------------------------


def test_keyword_score_rewards_a_matching_chunk_and_zeroes_an_unrelated_one() -> None:
    query = "dayanim testi"
    tokens = tokenize(query)

    hit = SearchService._keyword_score(
        query=query,
        tokens=tokens,
        chunk_text="Dayanim testi kapsaminda yorulma olcumleri yapilmistir.",
        document_title="2025-BIG-E-DUR-01 Dayanim Testi Raporu",
        file_name="2025-BIG-E-DUR-01-dayanim.pdf",
    )
    miss = SearchService._keyword_score(
        query=query,
        tokens=tokens,
        chunk_text="Motor bolmesi sicaklik dagilimi CFD ile incelenmistir.",
        document_title="Termal Analiz Ozeti",
        file_name="termal-analiz-ozeti.pdf",
    )

    assert hit > 0.0
    assert miss == 0.0


def test_keyword_score_is_zero_without_tokens() -> None:
    assert SearchService._keyword_score(query="", tokens=[], chunk_text="herhangi bir metin") == 0.0


def test_keyword_score_matches_across_turkish_folding() -> None:
    # "titresim" must find "titreşim" -- normalize_search_text folds s-cedilla to s.
    score = SearchService._keyword_score(
        query="titresim",
        tokens=["titresim"],
        chunk_text="Kabin titreşim seviyeleri olculmustur.",
    )

    assert score > 0.0


def test_keyword_score_rewards_a_whole_phrase_over_scattered_tokens() -> None:
    query = "yorulma olcumu"
    tokens = tokenize(query)

    phrase = SearchService._keyword_score(
        query=query, tokens=tokens, chunk_text="Sasi yorulma olcumu tamamlandi."
    )
    scattered = SearchService._keyword_score(
        query=query, tokens=tokens, chunk_text="Yorulma degerleri ayri, olcumu ayri raporlandi."
    )

    assert phrase > scattered > 0.0


def test_keyword_score_penalises_a_missing_specific_token() -> None:
    both = SearchService._keyword_score(
        query="sasi yorulma",
        tokens=["sasi", "yorulma"],
        chunk_text="Sasi yorulma olcumleri yapildi.",
    )
    one = SearchService._keyword_score(
        query="sasi yorulma",
        tokens=["sasi", "yorulma"],
        chunk_text="Sasi gerinim olcumleri yapildi.",
    )

    assert both > one


def test_keyword_score_reads_the_title_and_file_name_not_only_the_chunk() -> None:
    score = SearchService._keyword_score(
        query="dayanim",
        tokens=["dayanim"],
        chunk_text="Olcum sonuclari tabloda verilmistir.",
        document_title="Dayanim Testi Raporu",
        file_name="dayanim.pdf",
    )

    assert score > 0.0


# --- _passes_required_token_gate --------------------------------------------


def test_token_gate_requires_at_least_one_core_token() -> None:
    assert SearchService._passes_required_token_gate(["dayanim"], "Dayanim testi raporu") is True
    assert SearchService._passes_required_token_gate(["dayanim"], "Termal analiz ozeti") is False


def test_token_gate_requires_the_year_when_a_core_token_is_present() -> None:
    assert SearchService._passes_required_token_gate(["2025", "dayanim"], "2025 Dayanim Raporu") is True
    assert SearchService._passes_required_token_gate(["2025", "dayanim"], "2024 Dayanim Raporu") is False


def test_token_gate_lets_purely_generic_queries_through() -> None:
    # "rapor"/"nedir" are generic, so there is no core token to gate on.
    assert SearchService._passes_required_token_gate(["rapor", "nedir"], "alakasiz metin") is True


# --- _best_token_match_score -------------------------------------------------


def test_best_token_match_scores_exact_then_compact_then_fuzzy() -> None:
    exact = SearchService._best_token_match_score("dayanim", "dayanim testi", {"dayanim", "testi"})
    compact = SearchService._best_token_match_score("dur01", "2025-big-e-dur-01", {"dur", "01"})
    fuzzy = SearchService._best_token_match_score(
        "kalibrasyon", "kalibrasyom testi", {"kalibrasyom", "testi"}
    )

    assert exact == 1.0
    assert compact == pytest.approx(0.96)
    assert fuzzy == pytest.approx(0.78)
    assert exact > compact > fuzzy > 0.0


def test_best_token_match_gives_up_on_short_unmatched_tokens() -> None:
    # Below 5 characters there is no fuzzy fallback at all.
    assert SearchService._best_token_match_score("test", "tost yapildi", {"tost"}) == 0.0


# --- _query_profile / _query_report_key -------------------------------------


def test_query_profile_splits_year_identity_and_report_key() -> None:
    profile = profile_for("2025-BIG-E-DUR-01 raporu")

    assert profile["year_tokens"] == ["2025"]
    assert profile["report_key"] == "2025bigedur01"
    assert profile["is_report_lookup"] is True
    assert profile["strict_identity"] is True
    # Generic ("raporu"), year and single-character tokens are excluded.
    assert profile["identity_tokens"] == ["big", "dur", "01"]


def test_query_profile_stays_loose_for_a_topic_question() -> None:
    profile = profile_for("titresim olcumu")

    assert profile["year_tokens"] == []
    assert profile["report_key"] == ""
    assert profile["is_report_lookup"] is False
    assert profile["strict_identity"] is False


def test_query_report_key_only_fires_on_a_report_code() -> None:
    assert SearchService._query_report_key("2025-BIG-E-DUR-01 raporunun sonucu nedir?") == "2025bigedur01"
    assert SearchService._query_report_key("dayanim testi") == ""
    assert SearchService._query_report_key("") == ""


# --- _metadata_match_score ---------------------------------------------------


def test_metadata_score_rejects_a_document_that_lacks_the_report_code() -> None:
    query = "2025-BIG-E-DUR-01 raporu"

    assert SearchService._metadata_match_score(query, profile_for(query), DUR_ITEM, "") is not None
    assert SearchService._metadata_match_score(query, profile_for(query), NVH_ITEM, "") is None


def test_metadata_score_rejects_a_report_lookup_whose_subject_is_absent() -> None:
    query = "titresim raporu"

    assert SearchService._metadata_match_score(query, profile_for(query), NVH_ITEM, "") is not None
    assert SearchService._metadata_match_score(query, profile_for(query), DUR_ITEM, "") is None


def test_metadata_score_rejects_a_year_mismatch_under_strict_identity() -> None:
    query = "2023 dayanim raporu"

    assert SearchService._metadata_match_score(query, profile_for(query), DUR_ITEM, "") is None


def test_metadata_score_keeps_a_loose_query_at_zero_rather_than_rejecting_it() -> None:
    # No report key, no lookup word: nothing to gate on, so the item survives
    # with no bonus instead of being filtered out.
    query = "gurultu"

    assert SearchService._metadata_match_score(query, profile_for(query), DUR_ITEM, "") == 0.0


def test_metadata_score_reads_linked_catalog_text_as_well_as_the_title() -> None:
    query = "titresim raporu"

    without_catalog = SearchService._metadata_match_score(query, profile_for(query), DUR_ITEM, "")
    with_catalog = SearchService._metadata_match_score(
        query, profile_for(query), DUR_ITEM, "2025-BIG-E-DUR-01 Titresim ve Dayanim NVH"
    )

    assert without_catalog is None
    assert with_catalog is not None and with_catalog > 0.0


def test_metadata_score_follows_token_aliases() -> None:
    query = "guvenlik raporu"
    item = {"document_title": "SAFE Emniyet Raporu", "file_name": "safe.pdf"}

    assert SearchService._metadata_match_score(query, profile_for(query), item, "") is not None


def test_metadata_token_present_accepts_aliases_and_compacted_codes() -> None:
    assert SearchService._metadata_token_present("guvenlik", "safety raporu", {"safety", "raporu"}) is True
    assert SearchService._metadata_token_present("dur01", "2025-big-e-dur-01", {"dur", "01"}) is True
    assert SearchService._metadata_token_present("termal", "titresim raporu", {"titresim", "raporu"}) is False


# --- _passes_report_title_coverage ------------------------------------------


def test_report_title_coverage_needs_three_quarters_of_the_core_tokens() -> None:
    tokens = tokenize("dayanim yorulma testi sasi")

    assert SearchService._passes_report_title_coverage(tokens, "dayanim yorulma testi sasi raporu") is True
    assert SearchService._passes_report_title_coverage(tokens, "sadece dayanim") is False


def test_report_title_coverage_does_not_apply_below_three_core_tokens() -> None:
    assert SearchService._passes_report_title_coverage(tokenize("dayanim testi"), "alakasiz") is True


# --- _limit_results_per_document ---------------------------------------------


def _rows(document_ids: list[int]) -> list[dict]:
    return [{"id": index, "document_id": doc} for index, doc in enumerate(document_ids, start=1)]


def test_limit_results_keeps_one_chunk_per_document_by_default() -> None:
    service = SearchService(None)

    limited = service._limit_results_per_document(_rows([1, 1, 1, 2, 2, 3]), 10)

    assert [item["id"] for item in limited] == [1, 4, 6]


def test_limit_results_honours_an_explicit_per_document_cap() -> None:
    service = SearchService(None)

    limited = service._limit_results_per_document(_rows([1, 1, 1, 2, 2, 3]), 10, max_results_per_document=2)

    assert [item["id"] for item in limited] == [1, 2, 4, 5, 6]


def test_limit_results_stops_at_the_overall_limit() -> None:
    service = SearchService(None)

    limited = service._limit_results_per_document(_rows([1, 1, 1, 2, 2, 3]), 3, max_results_per_document=2)

    assert [item["id"] for item in limited] == [1, 2, 4]


def test_per_document_cap_is_clamped_into_one_to_limit() -> None:
    service = SearchService(None)
    rows = _rows([1, 1, 1, 2, 2, 3])

    assert [item["id"] for item in service._limit_results_per_document(rows, 1, max_results_per_document=5)] == [1]
    assert [item["id"] for item in service._limit_results_per_document(rows, 10, max_results_per_document=0)] == [1, 4, 6]


def test_limit_results_does_not_group_rows_without_a_document_id() -> None:
    service = SearchService(None)

    limited = service._limit_results_per_document([{"id": 1, "document_id": 0}, {"id": 2, "document_id": 0}], 10)

    assert [item["id"] for item in limited] == [1, 2]


# --- small pure helpers ------------------------------------------------------


def test_lexical_rerank_score_is_clamped_to_the_unit_interval() -> None:
    strong = SearchService._lexical_rerank_score(
        "dayanim testi",
        tokenize("dayanim testi"),
        {
            "chunk_text": "dayanim testi dayanim testi",
            "document_title": "Dayanim Testi Raporu",
            "file_name": "dayanim.pdf",
            "section_title": None,
        },
    )
    absent = SearchService._lexical_rerank_score(
        "dayanim", ["dayanim"], {"chunk_text": "termal", "document_title": "", "file_name": ""}
    )

    assert strong == 1.0
    assert absent == 0.0


def test_token_overlap_ratio_counts_distinct_tokens() -> None:
    assert SearchService._token_overlap_ratio(["a", "b"], "a c") == pytest.approx(0.5)
    assert SearchService._token_overlap_ratio(["a", "a"], "a") == pytest.approx(1.0)
    assert SearchService._token_overlap_ratio([], "a") == 0.0


def test_shorten_text_collapses_whitespace_and_ellipsises() -> None:
    assert SearchService._shorten_text("  cok   bosluklu   metin  ") == "cok bosluklu metin"

    shortened = SearchService._shorten_text("a " * 200, 20)

    assert len(shortened) <= 20
    assert shortened.endswith("...")


def test_normalize_document_ids_dedupes_and_drops_junk() -> None:
    assert SearchService._normalize_document_ids([3, 3, "4", 0, -1, None, "x"]) == [3, 4]
    assert SearchService._normalize_document_ids(None) == []
    assert SearchService._normalize_document_ids([]) == []


def test_normalize_retrieval_version_defaults_to_v2() -> None:
    assert SearchService._normalize_retrieval_version("V1") == "v1"
    assert SearchService._normalize_retrieval_version(" v1 ") == "v1"
    assert SearchService._normalize_retrieval_version(None) == "v2"
    assert SearchService._normalize_retrieval_version("anything") == "v2"


def test_embedding_provider_name_stays_lazy_until_the_service_is_built() -> None:
    service = SearchService(None)

    assert service.embedding_provider_name() == "keyword-only"

    assert service.embedding_service.provider_name == "token-hash-v1"
    assert service.embedding_provider_name() == "token-hash-v1"
