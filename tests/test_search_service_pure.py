from __future__ import annotations

from app.services.search_service import SearchService


def test_is_near_token_true_for_single_character_typo() -> None:
    assert SearchService._is_near_token("kalibrasyon", "kalibrasyom") is True


def test_is_near_token_false_for_different_first_character() -> None:
    assert SearchService._is_near_token("kalite", "malite") is False


def test_is_near_token_false_when_length_diff_exceeds_one() -> None:
    assert SearchService._is_near_token("test", "testing") is False


def test_is_near_token_false_for_short_words_even_if_close() -> None:
    # min length < 5 is rejected outright regardless of edit distance
    assert SearchService._is_near_token("test", "tost") is False


def test_is_near_token_true_for_identical_words() -> None:
    assert SearchService._is_near_token("raporlar", "raporlar") is True


def test_is_near_token_allows_distance_two_for_longer_words() -> None:
    assert SearchService._is_near_token("dogrulama", "dogrulanma") is True
