"""B4 answer-region geometry and question mapping coverage."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.cli.seed_dev import ADMIN_EMAIL, ADMIN_PASSWORD, seed
from app.core.authorization import AuthContext
from app.core.config import get_settings
from app.core.security import JwtAuthProvider
from app.db.models import PipelineJob, Submission
from app.db.session import async_session_factory
from app.main import create_app
from app.services.storage import ObjectStorage
from tests.test_a2_gate_matrix import _foundation
from tests.test_a2_review_fixes import _leaf_and_approve
from tests.test_b3_submission_ingestion import _headers, _pdf_bytes


@asynccontextmanager
async def api_client() -> AsyncIterator[AsyncClient]:
    import os

    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
    os.environ["S3_ENDPOINT_URL"] = "http://127.0.0.1:19000"
    os.environ["AI_PROVIDER_VISION"] = "none"
    os.environ["AI_PROVIDER_TEXT"] = "none"
    await seed()
    get_settings.cache_clear()
    from app.tasks.celery_app import celery_app

    celery_app.conf.task_always_eager = True
    ObjectStorage(get_settings()).ensure_bucket()
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        yield client


async def _add_leaf(
    client: AsyncClient,
    headers: dict[str, str],
    data: dict,
    *,
    marks: str,
    sequence: int,
    label: str,
) -> dict:
    leaf = await client.post(
        f"/api/v1/assessment-versions/{data['version_id']}/questions",
        headers=headers,
        json={
            "stable_code": f"Q-{uuid.uuid4().hex[:6]}",
            "display_label": label,
            "sequence": sequence,
            "prompt_text": f"leaf {label}",
            "max_marks": marks,
            "question_type": "SHORT",
            "scoring_mode": "LEAF_SCORABLE",
        },
    )
    assert leaf.status_code == 201, leaf.text
    key = await client.post(
        f"/api/v1/assessments/{data['assessment']['id']}/answer-key-versions",
        headers=headers,
        json={
            "assessment_version_id": data["version_id"],
            "question_version_id": leaf.json()["id"],
            "answer_text": "ok",
            "source_type": "TEACHER",
            "status": "DRAFT",
        },
    )
    assert key.status_code == 201, key.text
    assert (
        await client.post(
            f"/api/v1/answer-key-versions/{key.json()['id']}/approve", headers=headers
        )
    ).status_code == 200
    rubric = await client.post(
        f"/api/v1/assessments/{data['assessment']['id']}/rubrics",
        headers=headers,
        json={
            "question_version_id": leaf.json()["id"],
            "title": f"R-{label}",
            "provenance": "TEACHER",
        },
    )
    assert rubric.status_code == 201, rubric.text
    rv = await client.post(
        f"/api/v1/rubrics/{rubric.json()['id']}/versions",
        headers=headers,
        json={
            "question_version_id": leaf.json()["id"],
            "source_type": "TEACHER",
            "status": "DRAFT",
        },
    )
    assert rv.status_code == 201, rv.text
    assert (
        await client.post(
            f"/api/v1/rubric-versions/{rv.json()['id']}/criteria",
            headers=headers,
            json={
                "criterion_code": "C1",
                "description": "correct",
                "max_marks": marks,
                "sequence": 1,
                "scoring_mode": "ADDITIVE",
                "partial_credit_allowed": True,
                "ecf_policy": "NONE",
            },
        )
    ).status_code == 201
    assert (
        await client.post(
            f"/api/v1/rubric-versions/{rv.json()['id']}/approve", headers=headers
        )
    ).status_code == 200
    return leaf.json()


async def _active_two_leaf_assessment(
    client: AsyncClient, headers: dict[str, str]
) -> dict:
    data = await _foundation(client, headers, marks="10.00")
    leaf_a = await _add_leaf(
        client, headers, data, marks="5.00", sequence=1, label="1"
    )
    leaf_b = await _add_leaf(
        client, headers, data, marks="5.00", sequence=2, label="2"
    )
    ready = await client.post(
        f"/api/v1/assessments/{data['assessment']['id']}/transition",
        headers=headers,
        json={"to_status": "READY"},
    )
    assert ready.status_code == 200, ready.text
    active = await client.post(
        f"/api/v1/assessments/{data['assessment']['id']}/transition",
        headers=headers,
        json={"to_status": "ACTIVE"},
    )
    assert active.status_code == 200, active.text
    data["leaf_a"] = leaf_a
    data["leaf_b"] = leaf_b
    return data


async def _ensure_student(client: AsyncClient, headers: dict[str, str]) -> str:
    years = await client.get("/api/v1/academic-years", headers=headers)
    sections = await client.get("/api/v1/class-sections", headers=headers)
    year_rows = years.json()
    section_rows = sections.json()
    section = next(
        s for s in section_rows if any(y["id"] == s["academic_year_id"] for y in year_rows)
    )
    created = await client.post(
        "/api/v1/students",
        headers=headers,
        json={
            "student_code": f"B4-{uuid.uuid4().hex[:6]}",
            "full_name": "B4 Student",
            "class_section_id": section["id"],
            "academic_year_id": section["academic_year_id"],
            "status": "active",
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def _upload_and_confirm(
    client: AsyncClient, headers: dict[str, str], assessment_id: str
) -> dict:
    upload = await client.post(
        "/api/v1/submissions",
        headers=headers,
        data={"assessment_id": assessment_id},
        files={"file": ("b4.pdf", _pdf_bytes(2), "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    submission_id = upload.json()["id"]
    student_id = await _ensure_student(client, headers)
    confirmed = await client.post(
        f"/api/v1/submissions/{submission_id}/identity/confirm",
        headers=headers,
        json={"student_id": student_id},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["workflow_state"] == "MAPPING_REVIEW"
    assert confirmed.json()["mapping_confidence"] == 0.0
    return confirmed.json()


@pytest.mark.asyncio
async def test_mapping_prepare_requires_confirmed_and_is_idempotent() -> None:
    async with api_client() as client:
        headers = await _headers(client)
        data = await _active_two_leaf_assessment(client, headers)
        upload = await client.post(
            "/api/v1/submissions",
            headers=headers,
            data={"assessment_id": data["assessment"]["id"]},
            files={"file": ("prep.pdf", _pdf_bytes(1), "application/pdf")},
        )
        sid = upload.json()["id"]
        bad = await client.post(f"/api/v1/submissions/{sid}/mapping/prepare", headers=headers)
        assert bad.status_code == 409

        student_id = await _ensure_student(client, headers)
        confirmed = await client.post(
            f"/api/v1/submissions/{sid}/identity/confirm",
            headers=headers,
            json={"student_id": student_id},
        )
        assert confirmed.json()["workflow_state"] == "MAPPING_REVIEW"

        again = await client.post(
            f"/api/v1/submissions/{sid}/mapping/prepare", headers=headers
        )
        assert again.status_code == 200
        assert again.json()["workflow_state"] == "MAPPING_REVIEW"

        async with async_session_factory() as db:
            jobs = list(
                (
                    await db.scalars(
                        select(PipelineJob).where(
                            PipelineJob.submission_id == uuid.UUID(sid),
                            PipelineJob.stage == "MAPPING",
                        )
                    )
                ).all()
            )
            assert len(jobs) == 1
            assert jobs[0].status == "SUCCEEDED"


@pytest.mark.asyncio
async def test_region_geometry_and_human_source_rules() -> None:
    async with api_client() as client:
        headers = await _headers(client)
        data = await _active_two_leaf_assessment(client, headers)
        submission = await _upload_and_confirm(
            client, headers, data["assessment"]["id"]
        )
        pages = await client.get(
            f"/api/v1/submissions/{submission['id']}/pages", headers=headers
        )
        page_id = pages.json()[0]["id"]

        created = await client.post(
            f"/api/v1/submission-pages/{page_id}/answer-regions",
            headers=headers,
            json={
                "label": "R1",
                "region_type": "ANSWER",
                "bbox": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.25},
            },
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["source_type"] == "HUMAN"
        assert body["detection_confidence"] == 0.0
        assert body["transcription"] is None
        assert body["transcription_confidence"] == 0.0

        assert (
            await client.post(
                f"/api/v1/submission-pages/{page_id}/answer-regions",
                headers=headers,
                json={
                    "label": "bad",
                    "region_type": "ANSWER",
                    "bbox": {"x": -0.1, "y": 0.1, "width": 0.2, "height": 0.2},
                },
            )
        ).status_code == 422
        assert (
            await client.post(
                f"/api/v1/submission-pages/{page_id}/answer-regions",
                headers=headers,
                json={
                    "label": "bad",
                    "region_type": "ANSWER",
                    "bbox": {"x": 0.1, "y": 0.1, "width": 0.0, "height": 0.2},
                },
            )
        ).status_code == 422
        assert (
            await client.post(
                f"/api/v1/submission-pages/{page_id}/answer-regions",
                headers=headers,
                json={
                    "label": "bad",
                    "region_type": "ANSWER",
                    "bbox": {"x": 0.8, "y": 0.8, "width": 0.3, "height": 0.3},
                },
            )
        ).status_code == 422


@pytest.mark.asyncio
async def test_mapping_upsert_confirm_finalize_and_continuation() -> None:
    async with api_client() as client:
        headers = await _headers(client)
        data = await _active_two_leaf_assessment(client, headers)
        submission = await _upload_and_confirm(
            client, headers, data["assessment"]["id"]
        )
        sid = submission["id"]
        source_hash = submission["source_content_sha256"]
        source_key = submission["source_storage_key"]

        workspace = await client.get(f"/api/v1/submissions/{sid}/mapping", headers=headers)
        assert workspace.status_code == 200, workspace.text
        payload = workspace.json()
        assert payload["assessment_version_id"] == submission["assessment_version_id"]
        assert payload["automated_region_detection_active"] is False
        assert payload["automated_mapping_active"] is False
        assert payload["completion"]["leaf_total"] == 2

        pages = payload["pages"]
        assert len(pages) == 2
        page0 = pages[0]["id"]
        page1 = pages[1]["id"]

        cont = await client.patch(
            f"/api/v1/submission-pages/{page1}",
            headers=headers,
            json={"is_continuation": True},
        )
        assert cont.status_code == 200
        assert cont.json()["is_continuation"] is True

        region_a = (
            await client.post(
                f"/api/v1/submission-pages/{page0}/answer-regions",
                headers=headers,
                json={
                    "label": "A1",
                    "region_type": "ANSWER",
                    "bbox": {"x": 0.05, "y": 0.05, "width": 0.4, "height": 0.2},
                },
            )
        ).json()
        region_b = (
            await client.post(
                f"/api/v1/submission-pages/{page1}/answer-regions",
                headers=headers,
                json={
                    "label": "A1-cont",
                    "region_type": "ANSWER",
                    "bbox": {"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.3},
                },
            )
        ).json()

        q1 = data["leaf_a"]["id"]
        q2 = data["leaf_b"]["id"]

        mapped = await client.put(
            f"/api/v1/submissions/{sid}/question-mappings/{q1}",
            headers=headers,
            json={
                "disposition": "ANSWERED",
                "region_ids": [region_a["id"], region_b["id"]],
            },
        )
        assert mapped.status_code == 200, mapped.text
        assert mapped.json()["mapping_state"] == "REVIEW_REQUIRED"
        assert mapped.json()["mapped_by"] == "HUMAN"
        assert mapped.json()["mapping_confidence"] == 0.0
        assert mapped.json()["region_ids"] == [region_a["id"], region_b["id"]]

        confirmed = await client.post(
            f"/api/v1/submissions/{sid}/question-mappings/{q1}/confirm",
            headers=headers,
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["mapping_state"] == "CONFIRMED"
        assert confirmed.json()["confirmed_by"] is not None

        # Editing a mapped region reopens confirmation
        patched = await client.patch(
            f"/api/v1/answer-regions/{region_a['id']}",
            headers=headers,
            json={"label": "A1-edited"},
        )
        assert patched.status_code == 200
        workspace2 = await client.get(f"/api/v1/submissions/{sid}/mapping", headers=headers)
        q1_mapping = next(
            m for m in workspace2.json()["mappings"] if m["question_version_id"] == q1
        )
        assert q1_mapping["mapping_state"] == "REVIEW_REQUIRED"

        assert (
            await client.post(
                f"/api/v1/submissions/{sid}/question-mappings/{q1}/confirm",
                headers=headers,
            )
        ).status_code == 200

        blank = await client.put(
            f"/api/v1/submissions/{sid}/question-mappings/{q2}",
            headers=headers,
            json={"disposition": "BLANK", "region_ids": []},
        )
        assert blank.status_code == 200
        assert (
            await client.post(
                f"/api/v1/submissions/{sid}/question-mappings/{q2}/confirm",
                headers=headers,
            )
        ).status_code == 200

        # Mapped region cannot be deleted
        assert (
            await client.delete(
                f"/api/v1/answer-regions/{region_a['id']}", headers=headers
            )
        ).status_code == 409

        # Incomplete finalize before blank was confirmed would fail — now complete
        finalized = await client.post(
            f"/api/v1/submissions/{sid}/mapping/finalize", headers=headers
        )
        assert finalized.status_code == 200, finalized.text
        assert finalized.json()["workflow_state"] == "READY_FOR_EVALUATION"
        assert finalized.json()["mapping_confidence"] == 0.0
        assert finalized.json()["source_content_sha256"] == source_hash
        assert finalized.json()["source_storage_key"] == source_key

        async with async_session_factory() as db:
            eval_jobs = list(
                (
                    await db.scalars(
                        select(PipelineJob).where(
                            PipelineJob.submission_id == uuid.UUID(sid),
                            PipelineJob.stage == "EVALUATION",
                        )
                    )
                ).all()
            )
            assert eval_jobs == []
            row = await db.scalar(select(Submission).where(Submission.id == uuid.UUID(sid)))
            assert row is not None
            assert row.source_content_sha256 == source_hash


@pytest.mark.asyncio
async def test_mapping_conflicts_permissions_and_cross_tenant() -> None:
    async with api_client() as client:
        headers = await _headers(client)
        data = await _active_two_leaf_assessment(client, headers)
        submission = await _upload_and_confirm(
            client, headers, data["assessment"]["id"]
        )
        sid = submission["id"]
        pages = (
            await client.get(f"/api/v1/submissions/{sid}/pages", headers=headers)
        ).json()
        region = (
            await client.post(
                f"/api/v1/submission-pages/{pages[0]['id']}/answer-regions",
                headers=headers,
                json={
                    "label": "shared",
                    "region_type": "ANSWER",
                    "bbox": {"x": 0.2, "y": 0.2, "width": 0.2, "height": 0.2},
                },
            )
        ).json()
        q1 = data["leaf_a"]["id"]
        q2 = data["leaf_b"]["id"]
        assert (
            await client.put(
                f"/api/v1/submissions/{sid}/question-mappings/{q1}",
                headers=headers,
                json={"disposition": "ANSWERED", "region_ids": [region["id"]]},
            )
        ).status_code == 200
        dup = await client.put(
            f"/api/v1/submissions/{sid}/question-mappings/{q2}",
            headers=headers,
            json={"disposition": "ANSWERED", "region_ids": [region["id"]]},
        )
        assert dup.status_code == 409

        ignored = (
            await client.post(
                f"/api/v1/submission-pages/{pages[0]['id']}/answer-regions",
                headers=headers,
                json={
                    "label": "ign",
                    "region_type": "ANSWER",
                    "bbox": {"x": 0.5, "y": 0.5, "width": 0.2, "height": 0.2},
                },
            )
        ).json()
        await client.patch(
            f"/api/v1/answer-regions/{ignored['id']}",
            headers=headers,
            json={"ignored": True},
        )
        assert (
            await client.put(
                f"/api/v1/submissions/{sid}/question-mappings/{q2}",
                headers=headers,
                json={"disposition": "ANSWERED", "region_ids": [ignored["id"]]},
            )
        ).status_code == 409

        # Wrong assessment version / foreign question
        other = await _foundation(client, headers, marks="10.00")
        await _leaf_and_approve(client, headers, other, marks="10.00")
        foreign_qv = (
            await client.get(
                f"/api/v1/assessment-versions/{other['version_id']}/questions",
                headers=headers,
            )
        ).json()[0]["id"]
        assert (
            await client.put(
                f"/api/v1/submissions/{sid}/question-mappings/{foreign_qv}",
                headers=headers,
                json={"disposition": "BLANK", "region_ids": []},
            )
        ).status_code == 404

        assert (await client.get(f"/api/v1/submissions/{sid}/mapping")).status_code == 401

        login = await client.post(
            "/api/v1/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "tenant_slug": "demo"},
        )
        context = JwtAuthProvider(get_settings()).verify_access_token(
            login.json()["access_token"]
        )
        read_only = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=context.user_id,
                tenant_id=context.tenant_id,
                roles=frozenset({"EVALUATOR"}),
                permissions=frozenset({"mapping:read", "submission:read"}),
            )
        )[0]
        ro_headers = {"Authorization": f"Bearer {read_only}"}
        assert (
            await client.get(f"/api/v1/submissions/{sid}/mapping", headers=ro_headers)
        ).status_code == 200
        assert (
            await client.post(
                f"/api/v1/submission-pages/{pages[0]['id']}/answer-regions",
                headers=ro_headers,
                json={
                    "label": "nope",
                    "region_type": "ANSWER",
                    "bbox": {"x": 0.1, "y": 0.1, "width": 0.1, "height": 0.1},
                },
            )
        ).status_code == 403

        foreign = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                roles=frozenset({"INSTITUTION_ADMIN"}),
                permissions=frozenset({"mapping:read", "mapping:review"}),
            )
        )[0]
        assert (
            await client.get(
                f"/api/v1/submissions/{sid}/mapping",
                headers={"Authorization": f"Bearer {foreign}"},
            )
        ).status_code == 404
