from fastapi import HTTPException

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"RUBRIC_REVIEW", "READY"}),
    "RUBRIC_REVIEW": frozenset({"DRAFT", "READY"}),
    "READY": frozenset({"ACTIVE", "DRAFT"}),
    "ACTIVE": frozenset({"CLOSED"}),
    "CLOSED": frozenset({"ARCHIVED"}),
    "ARCHIVED": frozenset(),
}


def validate_transition(current: str, target: str) -> None:
    """DRAFT→READY is allowed only after readiness validation by the caller."""
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise HTTPException(409, f"Invalid assessment transition: {current} -> {target}")
