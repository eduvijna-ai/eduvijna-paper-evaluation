"""UAT critical-path regression coverage (class sections, upload, ANY_N)."""

from __future__ import annotations

import io
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from app.ai.fixtures.maths_iib_uat import build_maths_iib_proposal
from app.db.models import QuestionVersion
from app.services.authoring_ai import validate_question_tree
from app.services.choice_groups import find_choice_group_over_attempts
from app.services.mark_reconciliation import reconcile_marks
from tests.test_b3_submission_ingestion import _active_assessment, _headers, api_client


def _png_bytes() -> bytes:
    image = Image.new("RGB", (64, 96), color=(200, 180, 160))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_class_section_same_name_different_grades() -> None:
    async with api_client() as client:
        headers = await _headers(client)
        years = await client.get("/api/v1/academic-years", headers=headers)
        year_id = years.json()[0]["id"]
        section_name = f"A-{uuid.uuid4().hex[:6]}"
        g10 = await client.post(
            "/api/v1/class-sections",
            headers=headers,
            json={
                "academic_year_id": year_id,
                "name": section_name,
                "grade_label": "Grade 10",
            },
        )
        assert g10.status_code == 201, g10.text
        g12 = await client.post(
            "/api/v1/class-sections",
            headers=headers,
            json={
                "academic_year_id": year_id,
                "name": section_name,
                "grade_label": "Grade 12",
            },
        )
        assert g12.status_code == 201, g12.text
        dup = await client.post(
            "/api/v1/class-sections",
            headers=headers,
            json={
                "academic_year_id": year_id,
                "name": section_name,
                "grade_label": "Grade 12",
            },
        )
        assert dup.status_code == 409
        assert dup.json()["error"]["code"] == "CLASS_SECTION_CONFLICT"


@pytest.mark.asyncio
async def test_submission_upload_enqueue_failure_still_persists() -> None:
    async with api_client() as client:
        headers = await _headers(client)
        data = await _active_assessment(client, headers)
        with patch(
            "app.api.v1.submissions.enqueue_page_normalization",
            new=AsyncMock(side_effect=RuntimeError("broker down")),
        ):
            upload = await client.post(
                "/api/v1/submissions",
                headers=headers,
                data={"assessment_id": data["assessment"]["id"]},
                files={"file": ("enqueue-fail.png", _png_bytes(), "image/png")},
            )
        assert upload.status_code == 201, upload.text
        body = upload.json()
        assert body["pipeline_enqueue_error"]
        assert body["id"]


@pytest.mark.asyncio
async def test_maths_iib_fixture_reconciles_to_75() -> None:
    proposal = build_maths_iib_proposal()
    validate_question_tree(proposal.roots, assessment_max_marks=Decimal("75.00"))
    fake_rows: list[QuestionVersion] = []

    def qv(**kwargs: object) -> QuestionVersion:
        row = QuestionVersion(
            tenant_id=uuid.uuid4(),
            assessment_version_id=uuid.uuid4(),
            question_id=uuid.uuid4(),
            display_label=str(kwargs.get("display_label", "")),
            sequence=int(kwargs.get("sequence", 1)),
            prompt_text="p",
            max_marks=Decimal(str(kwargs.get("max_marks", "0"))),
            question_type="STRUCTURED",
            scoring_mode=str(kwargs.get("scoring_mode", "LEAF_SCORABLE")),
            selection_mode=str(kwargs.get("selection_mode", "ALL")),
            selection_count=kwargs.get("selection_count"),
            parent_question_version_id=kwargs.get("parent_question_version_id"),
        )
        row.id = uuid.uuid4()
        fake_rows.append(row)
        return row

    sec_a = qv(
        display_label="A",
        max_marks="20",
        scoring_mode="CONTAINER_DERIVED",
        selection_mode="ALL",
        sequence=1,
    )
    for i in range(10):
        qv(
            display_label=str(i + 1),
            max_marks="2",
            parent_question_version_id=sec_a.id,
            sequence=i + 1,
        )
    sec_b = qv(
        display_label="B",
        max_marks="20",
        scoring_mode="CONTAINER_DERIVED",
        selection_mode="ANY_N",
        selection_count=5,
        sequence=2,
    )
    for i in range(7):
        qv(
            display_label=str(11 + i),
            max_marks="4",
            parent_question_version_id=sec_b.id,
            sequence=i + 1,
        )
    sec_c = qv(
        display_label="C",
        max_marks="35",
        scoring_mode="CONTAINER_DERIVED",
        selection_mode="ANY_N",
        selection_count=5,
        sequence=3,
    )
    for i in range(7):
        qv(
            display_label=str(18 + i),
            max_marks="7",
            parent_question_version_id=sec_c.id,
            sequence=i + 1,
        )

    ok, total = reconcile_marks(fake_rows, Decimal("75.00"))
    assert ok, total
    assert total == Decimal("75.00")


def test_choice_group_over_attempt_blocks() -> None:
    parent_id = uuid.uuid4()
    leaf_ids = [uuid.uuid4() for _ in range(3)]
    questions = [
        SimpleNamespace(
            id=parent_id,
            parent_question_version_id=None,
            sequence=1,
            scoring_mode="CONTAINER_DERIVED",
            max_marks=Decimal("8"),
            selection_mode="ANY_N",
            selection_count=1,
            display_label="B",
        ),
        *[
            SimpleNamespace(
                id=leaf_ids[i],
                parent_question_version_id=parent_id,
                sequence=i + 1,
                scoring_mode="LEAF_SCORABLE",
                max_marks=Decimal("4"),
                selection_mode="ALL",
                selection_count=None,
                display_label=f"Q{i}",
            )
            for i in range(3)
        ],
    ]
    mappings = {
        leaf_ids[0]: SimpleNamespace(disposition="ANSWERED"),
        leaf_ids[1]: SimpleNamespace(disposition="ANSWERED"),
        leaf_ids[2]: SimpleNamespace(disposition="BLANK"),
    }
    violations = find_choice_group_over_attempts(questions, mappings)
    assert len(violations) == 1
    assert violations[0].answered_count == 2
