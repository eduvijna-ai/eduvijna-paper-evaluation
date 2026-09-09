"""Pure B14 mastery delta helpers (comparison/projection only)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

DELTA_QUANT = Decimal("0.000001")


def compute_delta(baseline: Decimal | None, post: Decimal | None) -> Decimal | None:
    """Return post - baseline when both are non-null; otherwise None (not zero)."""
    if baseline is None or post is None:
        return None
    return (post - baseline).quantize(DELTA_QUANT, rounding=ROUND_HALF_UP)
