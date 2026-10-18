"""Tests for the judging helpers: quote check, Cohen's kappa, dispute rule and vote aggregation."""

import math

import pytest
from pydantic import ValidationError

from src.rag.judging import Verdict, cohen_kappa, final_score, is_disputed, quote_found


def test_quote_found_ignores_case_quotes_and_whitespace() -> None:
    page = "Never walk, swim, or drive through floodwaters.\nTurn Around, Don’t Drown!"
    assert quote_found("never walk, swim, or drive  through floodwaters.", page)
    assert quote_found("Turn around, dont drown!", page)
    assert not quote_found("Walk through floodwater carefully.", page)
    assert not quote_found("", page)


def test_quote_found_accepts_slightly_trimmed_long_quote() -> None:
    page = "Evacuate immediately if authorities tell you to do so and follow the designated routes out."
    assert quote_found("Evacuate immediately if authorities tell you to do so and follow the designated", page)


def test_cohen_kappa_perfect_chance_and_partial() -> None:
    assert cohen_kappa([0, 1, 2, 1], [0, 1, 2, 1]) == 1.0
    assert math.isclose(cohen_kappa([1, 1, 0, 0], [1, 0, 1, 0]), 0.0)
    assert 0 < cohen_kappa([1, 1, 1, 0, 0], [1, 1, 0, 0, 0]) < 1


def test_verdict_rejects_out_of_range_score() -> None:
    assert Verdict(score=2, quote="x", reason="r").score == 2
    with pytest.raises(ValidationError):
        Verdict(score=3)


def test_dispute_rule() -> None:
    assert not is_disputed(2, 2)
    assert is_disputed(1, 2)  # any score difference goes to the tie-breaker
    assert is_disputed(None, 0)  # invalid vote (e.g. invented quote)


def test_final_score_aggregation() -> None:
    assert final_score([2, 2]) == 2
    assert final_score([0, 2, 2]) == 2  # majority with the tie-breaker
    assert final_score([0, 1, 2]) == 1  # median
    assert final_score([None, 2, 0]) == 0  # two valid votes that differ: the lower one
    assert final_score([None, None, None]) is None
