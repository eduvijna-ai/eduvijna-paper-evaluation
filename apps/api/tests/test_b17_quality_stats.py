"""Pure math fixtures for B17 quality_stats (PEV-048/049)."""

from __future__ import annotations

import math

from app.services.quality_stats import (
    UNDEFINED_VARIANCE,
    corrected_item_total_discrimination,
    difficulty_band,
    difficulty_index,
    discrimination_band,
    icc_a1,
    mean,
    pearson_correlation,
    population_std,
)


def test_mean_and_std_helpers() -> None:
    assert mean([]) is None
    assert mean([2.0, 4.0, 6.0]) == 4.0
    assert population_std([2.0, 4.0, 6.0]) == math.sqrt(
        ((2 - 4) ** 2 + (4 - 4) ** 2 + (6 - 4) ** 2) / 3
    )


def test_pearson_perfect_and_undefined() -> None:
    xs = [1.0, 2.0, 3.0, 4.0]
    ys = [2.0, 4.0, 6.0, 8.0]
    r, reason = pearson_correlation(xs, ys)
    assert reason is None
    assert r is not None
    assert abs(r - 1.0) < 1e-9

    r2, reason2 = pearson_correlation([1.0, 1.0, 1.0], [2.0, 3.0, 4.0])
    assert r2 is None
    assert reason2 == UNDEFINED_VARIANCE
    r3, _ = pearson_correlation([1.0], [2.0])
    assert r3 is None


def test_difficulty_index_and_bands() -> None:
    assert difficulty_index([0.0, 5.0, 10.0], 10.0) == 0.5
    assert difficulty_index([], 10.0) is None
    assert difficulty_index([1.0], 0.0) is None
    assert difficulty_band(0.2) == "HARD"
    assert difficulty_band(0.5) == "MODERATE"
    assert difficulty_band(0.8) == "EASY"
    assert difficulty_band(None) is None


def test_corrected_item_total_discrimination() -> None:
    item = [1.0, 2.0, 3.0, 4.0, 5.0]
    other = [2.0, 4.0, 6.0, 8.0, 10.0]
    totals = [a + b for a, b in zip(item, other, strict=True)]
    disc, reason = corrected_item_total_discrimination(item, totals)
    assert reason is None
    assert disc is not None
    assert abs(disc - 1.0) < 1e-9
    assert discrimination_band(0.1) == "LOW"
    assert discrimination_band(0.3) == "MODERATE"
    assert discrimination_band(0.5) == "HIGH"
    assert discrimination_band(None) is None


def test_icc_a1_perfect_agreement() -> None:
    matrix = [
        [5.0, 5.0],
        [3.0, 3.0],
        [4.0, 4.0],
    ]
    value, reason = icc_a1(matrix)
    assert reason is None
    assert value is not None
    assert abs(value - 1.0) < 1e-9


def test_icc_a1_hand_checkable_partial_agreement() -> None:
    # [[1, 2], [3, 4], [5, 6]] → ICC = 8/9
    matrix = [
        [1.0, 2.0],
        [3.0, 4.0],
        [5.0, 6.0],
    ]
    value, reason = icc_a1(matrix)
    assert reason is None
    assert value is not None
    assert abs(value - (8.0 / 9.0)) < 1e-9


def test_icc_a1_insufficient() -> None:
    assert icc_a1([[1.0, 2.0]])[0] is None
    assert icc_a1([[1.0], [2.0]])[0] is None
    assert icc_a1([])[0] is None
