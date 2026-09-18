"""Deterministic subject-profile projection from Assessment.subject_node_id.

This is not an independent subject identity. The canonical anchor remains
``CurriculumNode`` via ``Assessment.subject_node_id``. Unknown profiles never
silently become Mathematics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.db.models import CurriculumNode

SUBJECT_PROFILE_MATHEMATICS = "MATHEMATICS"
SUBJECT_PROFILE_PHYSICS = "PHYSICS"
SUBJECT_PROFILE_CHEMISTRY = "CHEMISTRY"
SUBJECT_PROFILE_STATISTICS = "STATISTICS"
SUBJECT_PROFILE_ACCOUNTING = "ACCOUNTING"
SUBJECT_PROFILE_STRUCTURED_DESCRIPTIVE = "STRUCTURED_DESCRIPTIVE"
SUBJECT_PROFILE_UNSPECIFIED = "UNSPECIFIED"
SUBJECT_PROFILE_UNSUPPORTED = "UNSUPPORTED"

KNOWN_SUBJECT_PROFILES: frozenset[str] = frozenset(
    {
        SUBJECT_PROFILE_MATHEMATICS,
        SUBJECT_PROFILE_PHYSICS,
        SUBJECT_PROFILE_CHEMISTRY,
        SUBJECT_PROFILE_STATISTICS,
        SUBJECT_PROFILE_ACCOUNTING,
        SUBJECT_PROFILE_STRUCTURED_DESCRIPTIVE,
    }
)

# UNSPECIFIED is Mathematics-compatible only for genuine legacy rows with no
# subject_node_id. A present CurriculumNode that does not map to a known
# profile is UNSUPPORTED and never Math-eligible.
MATH_VERIFICATION_PROFILES: frozenset[str] = frozenset(
    {
        SUBJECT_PROFILE_MATHEMATICS,
        SUBJECT_PROFILE_UNSPECIFIED,
    }
)

_ALIAS_TO_PROFILE: dict[str, str] = {
    "MATH": SUBJECT_PROFILE_MATHEMATICS,
    "MATHEMATICS": SUBJECT_PROFILE_MATHEMATICS,
    "MATHEMATICAL": SUBJECT_PROFILE_MATHEMATICS,
    "PHY": SUBJECT_PROFILE_PHYSICS,
    "PHYS": SUBJECT_PROFILE_PHYSICS,
    "PHYSICS": SUBJECT_PROFILE_PHYSICS,
    "CHEM": SUBJECT_PROFILE_CHEMISTRY,
    "CHEMISTRY": SUBJECT_PROFILE_CHEMISTRY,
    "STAT": SUBJECT_PROFILE_STATISTICS,
    "STATS": SUBJECT_PROFILE_STATISTICS,
    "STATISTICS": SUBJECT_PROFILE_STATISTICS,
    "ACC": SUBJECT_PROFILE_ACCOUNTING,
    "ACCT": SUBJECT_PROFILE_ACCOUNTING,
    "ACCOUNTING": SUBJECT_PROFILE_ACCOUNTING,
    "DESC": SUBJECT_PROFILE_STRUCTURED_DESCRIPTIVE,
    "DESCRIPTIVE": SUBJECT_PROFILE_STRUCTURED_DESCRIPTIVE,
    "STRUCTURED_DESCRIPTIVE": SUBJECT_PROFILE_STRUCTURED_DESCRIPTIVE,
    "ENGLISH": SUBJECT_PROFILE_STRUCTURED_DESCRIPTIVE,
    "HISTORY": SUBJECT_PROFILE_STRUCTURED_DESCRIPTIVE,
    "CIVICS": SUBJECT_PROFILE_STRUCTURED_DESCRIPTIVE,
    "GEOGRAPHY": SUBJECT_PROFILE_STRUCTURED_DESCRIPTIVE,
}


def _normalize_token(value: str | None) -> str:
    if not value:
        return ""
    token = value.strip().upper().replace("-", "_").replace(" ", "_")
    while "__" in token:
        token = token.replace("__", "_")
    return token.strip("_")


def _token_without_suffix(token: str) -> str:
    if "-" in token:
        token = token.split("-", 1)[0]
    if "_" in token:
        head, tail = token.split("_", 1)
        if len(tail) <= 12 and tail.isalnum():
            return head
    return token


def profile_from_token(raw: str | None) -> str | None:
    token = _normalize_token(raw)
    if not token:
        return None
    if token in KNOWN_SUBJECT_PROFILES:
        return token
    if token in _ALIAS_TO_PROFILE:
        return _ALIAS_TO_PROFILE[token]
    stripped = _token_without_suffix(token)
    if stripped in _ALIAS_TO_PROFILE:
        return _ALIAS_TO_PROFILE[stripped]
    return None


@dataclass(frozen=True, slots=True)
class SubjectProfileResolution:
    profile: str
    subject_node_id: str | None
    subject_node_code: str | None
    subject_node_name: str | None
    source: str
    math_verification_eligible: bool

    def as_public_dict(self) -> dict[str, Any]:
        return {
            "subject_profile": self.profile,
            "subject_node_id": self.subject_node_id,
            "subject_node_code": self.subject_node_code,
            "subject_node_name": self.subject_node_name,
            "subject_profile_source": self.source,
            "math_verification_eligible": self.math_verification_eligible,
        }

    def routing_dict(self) -> dict[str, str | None]:
        return {
            "subject_profile": self.profile,
            "subject_node_id": self.subject_node_id,
            "subject_node_code": self.subject_node_code,
        }


def resolve_subject_profile(
    node: CurriculumNode | None,
    *,
    subject_node_id: Any | None = None,
) -> SubjectProfileResolution:
    """Project a bounded profile from the canonical curriculum subject node."""
    raw_id = str(subject_node_id).strip() if subject_node_id else None
    if raw_id in {"", "None"}:
        raw_id = None
    node_id = str(node.id) if node is not None else raw_id
    if node is None:
        if node_id:
            return SubjectProfileResolution(
                profile=SUBJECT_PROFILE_UNSUPPORTED,
                subject_node_id=node_id,
                subject_node_code=None,
                subject_node_name=None,
                source="SUBJECT_NODE_UNRESOLVED",
                math_verification_eligible=False,
            )
        return SubjectProfileResolution(
            profile=SUBJECT_PROFILE_UNSPECIFIED,
            subject_node_id=None,
            subject_node_code=None,
            subject_node_name=None,
            source="MISSING_SUBJECT_NODE",
            math_verification_eligible=True,
        )

    metadata = node.metadata_json if isinstance(node.metadata_json, dict) else {}
    explicit = metadata.get("subject_profile")
    if isinstance(explicit, str) and explicit.strip():
        mapped = profile_from_token(explicit)
        if mapped is None:
            return SubjectProfileResolution(
                profile=SUBJECT_PROFILE_UNSUPPORTED,
                subject_node_id=str(node.id),
                subject_node_code=node.code,
                subject_node_name=node.name,
                source="METADATA_UNSUPPORTED",
                math_verification_eligible=False,
            )
        return SubjectProfileResolution(
            profile=mapped,
            subject_node_id=str(node.id),
            subject_node_code=node.code,
            subject_node_name=node.name,
            source="METADATA",
            math_verification_eligible=mapped in MATH_VERIFICATION_PROFILES,
        )

    for candidate in (node.code, node.name):
        mapped = profile_from_token(candidate)
        if mapped is not None:
            return SubjectProfileResolution(
                profile=mapped,
                subject_node_id=str(node.id),
                subject_node_code=node.code,
                subject_node_name=node.name,
                source="NODE_CODE_OR_NAME",
                math_verification_eligible=mapped in MATH_VERIFICATION_PROFILES,
            )

    return SubjectProfileResolution(
        profile=SUBJECT_PROFILE_UNSUPPORTED,
        subject_node_id=str(node.id),
        subject_node_code=node.code,
        subject_node_name=node.name,
        source="UNMAPPED_NODE",
        math_verification_eligible=False,
    )


def math_verification_allowed(profile: str | None) -> bool:
    return (profile or SUBJECT_PROFILE_UNSPECIFIED) in MATH_VERIFICATION_PROFILES
