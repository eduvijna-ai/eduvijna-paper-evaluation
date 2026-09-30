"""Shared list pagination clamps for production-safe bounds."""


def clamp_limit(limit: int | None = None, *, default: int = 100, maximum: int = 500) -> int:
    """Return a page size between 1 and ``maximum`` (default when unset)."""
    if limit is None:
        return default
    return max(1, min(int(limit), maximum))


def clamp_offset(offset: int | None = None) -> int:
    """Return a non-negative offset (0 when unset)."""
    if offset is None:
        return 0
    return max(0, int(offset))
