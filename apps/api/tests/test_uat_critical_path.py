"""UAT critical-path regression coverage (class sections, upload, ANY_N)."""

from __future__ import annotations

import io
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image
from sqlalchemy import text

from app.ai.fixtures.maths_iib_uat import build_maths_iib_proposal
from app.api.v1.submissions import PIPELINE_ENQUEUE_FAILED_PUBLIC_MESSAGE
from app.db.models import QuestionVersion
from app.db.session import async_session_factory
from app.services.authoring_ai import validate_question_tree
from app.services.choice_groups import find_choice_group_over_attempts
from app.services.mark_reconciliation import reconcile_marks
from tests.test_b3_submission_ingestion import (
    _active_assessment,
    _headers,
    _pdf_bytes,
    api_client,
)

_SENSITIVE_ENQUEUE_EXCEPTION = (
    "redis://admin:SECRET_TOKEN@broker.internal:6379/0 connection refused"
)


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
async def test_class_section_migration_unique_includes_grade_label() -> None:
    async with async_session_factory() as db:
        row = await db.scalar(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE indexname = 'uq_class_sections_scope_grade_name'"
            )
        )
        assert row is not None
        assert "grade_label" in row


@pytest.mark.asyncio
async def test_duplicate_submission_source_is_domain_409_not_500() -> None:
    """Re-uploading the same bytes must not surface as an unhandled 500."""
    async with api_client() as client:
        headers = await _headers(client)
        data = await _active_assessment(client, headers)
        pdf = _pdf_bytes(1)
        first = await client.post(
            "/api/v1/submissions",
            headers=headers,
            data={"assessment_id": data["assessment"]["id"]},
            files={"file": ("dup.pdf", pdf, "application/pdf")},
        )
        assert first.status_code == 201, first.text
        duplicate = await client.post(
            "/api/v1/submissions",
            headers=headers,
            data={"assessment_id": data["assessment"]["id"]},
            files={"file": ("dup.pdf", pdf, "application/pdf")},
        )
        assert duplicate.status_code == 409, duplicate.text
        assert duplicate.json()["error"]["code"] == "DUPLICATE_SUBMISSION_SOURCE"


@pytest.mark.asyncio
async def test_submission_upload_enqueue_failure_still_persists() -> None:
    async with api_client() as client:
        headers = await _headers(client)
        data = await _active_assessment(client, headers)
        with patch(
            "app.api.v1.submissions.enqueue_page_normalization",
            new=AsyncMock(
                side_effect=RuntimeError(_SENSITIVE_ENQUEUE_EXCEPTION),
            ),
        ):
            upload = await client.post(
                "/api/v1/submissions",
                headers=headers,
                data={"assessment_id": data["assessment"]["id"]},
                files={"file": ("enqueue-fail.png", _png_bytes(), "image/png")},
            )
        assert upload.status_code == 201, upload.text
        body = upload.json()
        assert body["pipeline_enqueue_error"] == PIPELINE_ENQUEUE_FAILED_PUBLIC_MESSAGE
        assert _SENSITIVE_ENQUEUE_EXCEPTION not in upload.text
        assert body["pipeline_job_status"] == "FAILED"
        assert body["id"]
        submission_id = body["id"]
        job_id = body["pipeline_job_id"]
        async with async_session_factory() as db:
            from app.db.models import PipelineJob

            job = await db.get(PipelineJob, uuid.UUID(job_id))
            assert job is not None
            assert job.finished_at is not None
            assert job.error_code == "PIPELINE_ENQUEUE_FAILED"
            assert _SENSITIVE_ENQUEUE_EXCEPTION not in (job.error_detail or "")
        detail = await client.get(
            f"/api/v1/submissions/{submission_id}", headers=headers
        )
        assert detail.status_code == 200
        assert detail.json()["pipeline_enqueue_error"] == PIPELINE_ENQUEUE_FAILED_PUBLIC_MESSAGE
        assert _SENSITIVE_ENQUEUE_EXCEPTION not in detail.text


@pytest.mark.asyncio
async def test_get_submission_masks_legacy_raw_enqueue_error_detail() -> None:
    """Older rows may contain raw broker text; GET must not leak it."""
    async with api_client() as client:
        headers = await _headers(client)
        data = await _active_assessment(client, headers)
        with patch(
            "app.api.v1.submissions.enqueue_page_normalization",
            new=AsyncMock(
                side_effect=RuntimeError(_SENSITIVE_ENQUEUE_EXCEPTION),
            ),
        ):
            upload = await client.post(
                "/api/v1/submissions",
                headers=headers,
                data={"assessment_id": data["assessment"]["id"]},
                files={"file": ("legacy-leak.png", _png_bytes(), "image/png")},
            )
        assert upload.status_code == 201, upload.text
        submission_id = upload.json()["id"]
        job_id = upload.json()["pipeline_job_id"]
        async with async_session_factory() as db:
            from app.db.models import PipelineJob

            job = await db.get(PipelineJob, uuid.UUID(job_id))
            assert job is not None
            job.error_detail = _SENSITIVE_ENQUEUE_EXCEPTION
            await db.commit()
        detail = await client.get(
            f"/api/v1/submissions/{submission_id}", headers=headers
        )
        assert detail.status_code == 200
        assert detail.json()["pipeline_enqueue_error"] == PIPELINE_ENQUEUE_FAILED_PUBLIC_MESSAGE
        assert _SENSITIVE_ENQUEUE_EXCEPTION not in detail.text


@pytest.mark.asyncio
async def test_submission_retry_enqueue_failure_returns_safe_message_only() -> None:
    mock_enqueue = AsyncMock(side_effect=RuntimeError(_SENSITIVE_ENQUEUE_EXCEPTION))
    async with api_client() as client:
        headers = await _headers(client)
        data = await _active_assessment(client, headers)
        with patch(
            "app.api.v1.submissions.enqueue_page_normalization",
            new=mock_enqueue,
        ):
            upload = await client.post(
                "/api/v1/submissions",
                headers=headers,
                data={"assessment_id": data["assessment"]["id"]},
                files={"file": ("retry-fail.png", _png_bytes(), "image/png")},
            )
        assert upload.status_code == 201, upload.text
        submission_id = upload.json()["id"]
        retry = await client.post(
            f"/api/v1/submissions/{submission_id}/retry-page-normalization",
            headers=headers,
        )
        assert retry.status_code == 200, retry.text
        assert retry.json()["pipeline_enqueue_error"] == PIPELINE_ENQUEUE_FAILED_PUBLIC_MESSAGE
        assert _SENSITIVE_ENQUEUE_EXCEPTION not in retry.text
        assert retry.json()["pipeline_job_status"] == "FAILED"


@pytest.mark.asyncio
async def test_submission_enqueue_retry_recovers_without_reupload() -> None:
    mock_enqueue = AsyncMock(side_effect=RuntimeError(_SENSITIVE_ENQUEUE_EXCEPTION))
    async with api_client() as client:
        headers = await _headers(client)
        data = await _active_assessment(client, headers)
        with patch(
            "app.api.v1.submissions.enqueue_page_normalization",
            new=mock_enqueue,
        ):
            upload = await client.post(
                "/api/v1/submissions",
                headers=headers,
                data={"assessment_id": data["assessment"]["id"]},
                files={"file": ("retry-me.png", _png_bytes(), "image/png")},
            )
        assert upload.status_code == 201, upload.text
        submission_id = upload.json()["id"]
        mock_enqueue.side_effect = None
        mock_enqueue.return_value = "task-recovered"
        retry = await client.post(
            f"/api/v1/submissions/{submission_id}/retry-page-normalization",
            headers=headers,
        )
        assert retry.status_code == 200, retry.text
        assert not retry.json().get("pipeline_enqueue_error")
        detail = await client.get(
            f"/api/v1/submissions/{submission_id}", headers=headers
        )
        assert detail.status_code == 200
        assert detail.json().get("pipeline_job_status") in {"QUEUED", "RUNNING", "SUCCEEDED"}


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


def test_choice_group_nested_branch_single_attempt_ok() -> None:
    parent_id = uuid.uuid4()
    option_a = uuid.uuid4()
    leaf_a1, leaf_a2 = uuid.uuid4(), uuid.uuid4()
    option_b = uuid.uuid4()
    leaf_b1 = uuid.uuid4()
    questions = [
        SimpleNamespace(
            id=parent_id,
            parent_question_version_id=None,
            sequence=1,
            scoring_mode="CONTAINER_DERIVED",
            max_marks=Decimal("8"),
            selection_mode="ANY_N",
            selection_count=1,
            display_label="G",
        ),
        SimpleNamespace(
            id=option_a,
            parent_question_version_id=parent_id,
            sequence=1,
            scoring_mode="CONTAINER_DERIVED",
            max_marks=Decimal("4"),
            selection_mode="ALL",
            selection_count=None,
            display_label="A",
        ),
        SimpleNamespace(
            id=leaf_a1,
            parent_question_version_id=option_a,
            sequence=1,
            scoring_mode="LEAF_SCORABLE",
            max_marks=Decimal("2"),
            selection_mode="ALL",
            selection_count=None,
            display_label="a1",
        ),
        SimpleNamespace(
            id=leaf_a2,
            parent_question_version_id=option_a,
            sequence=2,
            scoring_mode="LEAF_SCORABLE",
            max_marks=Decimal("2"),
            selection_mode="ALL",
            selection_count=None,
            display_label="a2",
        ),
        SimpleNamespace(
            id=option_b,
            parent_question_version_id=parent_id,
            sequence=2,
            scoring_mode="LEAF_SCORABLE",
            max_marks=Decimal("4"),
            selection_mode="ALL",
            selection_count=None,
            display_label="B",
        ),
        SimpleNamespace(
            id=leaf_b1,
            parent_question_version_id=option_b,
            sequence=1,
            scoring_mode="LEAF_SCORABLE",
            max_marks=Decimal("4"),
            selection_mode="ALL",
            selection_count=None,
            display_label="b1",
        ),
    ]
    compliant = {
        leaf_a1: SimpleNamespace(disposition="ANSWERED"),
        leaf_a2: SimpleNamespace(disposition="ANSWERED"),
        leaf_b1: SimpleNamespace(disposition="BLANK"),
    }
    assert find_choice_group_over_attempts(questions, compliant) == []
    over = {
        leaf_a1: SimpleNamespace(disposition="ANSWERED"),
        leaf_a2: SimpleNamespace(disposition="ANSWERED"),
        leaf_b1: SimpleNamespace(disposition="ANSWERED"),
    }
    violations = find_choice_group_over_attempts(questions, over)
    assert len(violations) == 1
    assert violations[0].answered_count == 2
