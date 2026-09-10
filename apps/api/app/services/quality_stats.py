"""B17 deterministic statistics helpers (PEV-048 / PEV-049).

Pure functions only — no DB I/O. Float conversion happens at this boundary;
callers persist Decimal scores and round API floats for display.

Formulas (algorithm versions):
- Difficulty / facility: mean(score / max_mark) ∈ [0, 1]; higher = easier.
- Discrimination: corrected item–total Pearson (item vs total excluding item),
  method tag CORRECTED_ITEM_TOTAL_PEARSON_V1.
- ICC: absolute-agreement, single-measure, two-way (ICC(A,1) / McGraw & Wong),
  method tag ICC_A1_V1.
"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Sequence

UNDEFINED_VARIANCE = "UNDEFINED_VARIANCE"
INSUFFICIENT_PAIRS = "INSUFFICIENT_PAIRS"


def _as_float(value: Decimal | float | int) -> float:
    return float(value)


def mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def population_std(values: Sequence[float]) -> float | None:
    """Population standard deviation (divide by n). None if n < 1."""
    if not values:
        return None
    m = sum(values) / len(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / len(values))


def sample_variance(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None
    m = sum(values) / len(values)
    return sum((v - m) ** 2 for v in values) / (len(values) - 1)


def pearson_correlation(
    xs: Sequence[float], ys: Sequence[float]
) -> tuple[float | None, str | None]:
    """Pearson r. Returns (value, reason) where reason is set when undefined."""
    if len(xs) != len(ys):
        raise ValueError("pearson_correlation requires equal-length sequences")
    n = len(xs)
    if n < 2:
        return None, INSUFFICIENT_PAIRS
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if den_x == 0.0 or den_y == 0.0:
        return None, UNDEFINED_VARIANCE
    return num / (den_x * den_y), None


def difficulty_index(
    scores: Sequence[Decimal | float | int],
    max_mark: Decimal | float | int,
) -> float | None:
    """Facility index: mean(score/max_mark). Higher = easier."""
    max_f = _as_float(max_mark)
    if max_f <= 0 or not scores:
        return None
    ratios = [_as_float(s) / max_f for s in scores]
    return mean(ratios)


def corrected_item_total_discrimination(
    item_scores: Sequence[Decimal | float | int],
    total_scores_including_item: Sequence[Decimal | float | int],
) -> tuple[float | None, str | None]:
    """Corrected item–total Pearson: item vs (total − item).

    Method: CORRECTED_ITEM_TOTAL_PEARSON_V1.
    """
    if len(item_scores) != len(total_scores_including_item):
        raise ValueError("item and total sequences must match")
    xs = [_as_float(s) for s in item_scores]
    ys = [
        _as_float(t) - _as_float(x)
        for t, x in zip(total_scores_including_item, item_scores, strict=True)
    ]
    return pearson_correlation(xs, ys)


def icc_a1(matrix: Sequence[Sequence[float]]) -> tuple[float | None, str | None]:
    """ICC(A,1) two-way absolute agreement, single measure.

    ``matrix[i][j]`` = rating of case i by rater j.
    Requires ≥2 cases and ≥2 raters with a complete rectangular matrix.
    """
    if not matrix:
        return None, INSUFFICIENT_PAIRS
    n = len(matrix)  # cases (targets)
    k = len(matrix[0])  # raters
    if n < 2 or k < 2:
        return None, INSUFFICIENT_PAIRS
    if any(len(row) != k for row in matrix):
        raise ValueError("icc_a1 requires a complete rectangular matrix")

    grand = sum(sum(row) for row in matrix) / (n * k)
    row_means = [sum(row) / k for row in matrix]
    col_means = [sum(matrix[i][j] for i in range(n)) / n for j in range(k)]

    ss_rows = k * sum((rm - grand) ** 2 for rm in row_means)
    ss_cols = n * sum((cm - grand) ** 2 for cm in col_means)
    ss_total = sum((matrix[i][j] - grand) ** 2 for i in range(n) for j in range(k))
    ss_err = ss_total - ss_rows - ss_cols

    df_rows = n - 1
    df_cols = k - 1
    df_err = df_rows * df_cols
    if df_err <= 0:
        return None, UNDEFINED_VARIANCE

    ms_rows = ss_rows / df_rows
    ms_cols = ss_cols / df_cols
    ms_err = ss_err / df_err

    denom = ms_rows + (k - 1) * ms_err + (k / n) * (ms_cols - ms_err)
    if denom == 0.0:
        return None, UNDEFINED_VARIANCE
    # If all ratings identical, agreement is perfect.
    if ss_total == 0.0:
        return 1.0, None
    return (ms_rows - ms_err) / denom, None


def difficulty_band(index: float | None) -> str | None:
    """Product heuristic bands — not accreditation standards."""
    if index is None:
        return None
    if index < 0.3:
        return "HARD"
    if index < 0.7:
        return "MODERATE"
    return "EASY"


def discrimination_band(index: float | None) -> str | None:
    """Product heuristic bands — not accreditation standards."""
    if index is None:
        return None
    if index < 0.2:
        return "LOW"
    if index < 0.4:
        return "MODERATE"
    return "HIGH"


def score_tolerance(max_mark: Decimal | float | int) -> Decimal:
    """max(0.5 mark, 5% of max mark)."""
    max_d = Decimal(str(max_mark))
    pct = (max_d * Decimal("0.05")).quantize(Decimal("0.0001"))
    floor = Decimal("0.5")
    return floor if floor >= pct else pct
