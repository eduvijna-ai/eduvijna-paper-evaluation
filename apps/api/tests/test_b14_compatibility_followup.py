import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.api.v1.curriculum_assessment import AssessmentIn
from app.api.v1.reassessment import ReassessmentInstantiateIn
from app.db.models.curriculum_assessment import Assessment

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = REPO_ROOT / "database" / "migrations" / "versions"
MIGRATION_0014 = MIGRATIONS / "20260908_0014_b14_reassessment_mastery_update.py"
MIGRATION_0015 = MIGRATIONS / "20260908_0015_b14_assessment_type_compatibility.py"


def _instantiate_item() -> dict[str, object]:
    return {
        "improvement_assessment_item_id": str(uuid.uuid4()),
        "prompt_text": "Solve the reassessment question.",
        "max_marks": "5.00",
    }


def test_general_assessment_contract_still_accepts_non_exam_type() -> None:
    payload = AssessmentIn.model_validate(
        {
            "curriculum_id": str(uuid.uuid4()),
            "code": "QUIZ-1",
            "title": "Diagnostic quiz",
            "assessment_type": "QUIZ",
            "max_marks": "10.00",
        }
    )

    assert payload.assessment_type == "QUIZ"


def test_assessment_model_has_no_b14_global_type_constraint() -> None:
    constraint_names = {
        constraint.name
        for constraint in Assessment.__table__.constraints
        if constraint.name is not None
    }

    assert "ck_assessments_assessment_type" not in constraint_names


def test_corrected_b14_migration_does_not_restrict_existing_assessment_types() -> None:
    migration = MIGRATION_0014.read_text(encoding="utf-8")

    assert "WHERE assessment_type IS DISTINCT FROM 'EXAM'" not in migration
    assert "assessment_type IN ('EXAM','IMPROVEMENT_REASSESSMENT')" not in migration


def test_b14_cleanup_migration_safely_removes_legacy_constraint() -> None:
    migration = MIGRATION_0015.read_text(encoding="utf-8")

    assert 'down_revision: str | None = "20260908_0014"' in migration
    assert "DROP CONSTRAINT IF EXISTS" in migration
    assert "ck_assessments_assessment_type" in migration


@pytest.mark.parametrize("extra_location", ["request", "item"])
def test_reassessment_instantiate_rejects_extra_fields(extra_location: str) -> None:
    item = _instantiate_item()
    payload: dict[str, object] = {"items": [item]}
    if extra_location == "request":
        payload["unexpected"] = True
    else:
        item["unexpected"] = True

    with pytest.raises(ValidationError) as exc_info:
        ReassessmentInstantiateIn.model_validate(payload)

    assert "extra_forbidden" in str(exc_info.value)
