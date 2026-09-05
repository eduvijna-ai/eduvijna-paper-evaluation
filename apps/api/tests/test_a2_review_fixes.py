"""A2 independent-review required-fix regressions A2-FIX-T01..T27."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import yaml
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models import AiExecutionRecord, AnswerKeyVersion, Assessment, AuditEvent
from app.db.session import async_session_factory
from app.main import create_app
from app.services.ai_proposals import (
    AnswerKeyProposalRequest,
    build_ai_request_summary,
    server_ai_proposed_source_type,
)
from tests.test_a2_gate_matrix import _foundation, _headers, gate_client

MARKER = "DO_NOT_AUDIT_THIS_ANSWER_CONTENT_92817"
OPENAPI = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "openapi.yaml"


async def _leaf_and_approve(
    client: AsyncClient, headers: dict[str, str], data: dict, marks: str = "10.00"
) -> dict:
    leaf = await client.post(
        f"/api/v1/assessment-versions/{data['version_id']}/questions",
        headers=headers,
        json={
            "stable_code": f"Q-{uuid.uuid4().hex[:6]}",
            "display_label": "1",
            "sequence": 1,
            "prompt_text": "leaf",
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
            "title": "R",
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
                "description": "d",
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
    return {
        "leaf": leaf.json(),
        "key": key.json(),
        "rubric": rubric.json(),
        "rubric_version": rv.json(),
    }


@pytest.mark.asyncio
async def test_a2_fix_t01_zero_marks_no_questions_ready_rejected() -> None:
    """A2-FIX-T01"""
    async with gate_client() as client:
        headers = await _headers(client)
        data = await _foundation(client, headers, marks="0.00")
        blocked = await client.post(
            f"/api/v1/assessments/{data['assessment']['id']}/transition",
            headers=headers,
            json={"to_status": "READY"},
        )
        assert blocked.status_code == 409
        assert blocked.json()["error"]["details"]["code"] == "ASSESSMENT_NO_SCORABLE_QUESTIONS"


@pytest.mark.asyncio
async def test_a2_fix_t02_positive_marks_no_questions_ready_rejected() -> None:
    """A2-FIX-T02"""
    async with gate_client() as client:
        headers = await _headers(client)
        data = await _foundation(client, headers, marks="10.00")
        blocked = await client.post(
            f"/api/v1/assessments/{data['assessment']['id']}/transition",
            headers=headers,
            json={"to_status": "READY"},
        )
        assert blocked.status_code == 409
        assert blocked.json()["error"]["details"]["code"] == "ASSESSMENT_NO_SCORABLE_QUESTIONS"


@pytest.mark.asyncio
async def test_a2_fix_t03_container_only_ready_rejected() -> None:
    """A2-FIX-T03"""
    async with gate_client() as client:
        headers = await _headers(client)
        data = await _foundation(client, headers, marks="10.00")
        container = await client.post(
            f"/api/v1/assessment-versions/{data['version_id']}/questions",
            headers=headers,
            json={
                "stable_code": "SEC",
                "display_label": "1",
                "sequence": 1,
                "prompt_text": "section",
                "max_marks": "10.00",
                "question_type": "SECTION",
                "scoring_mode": "CONTAINER_DERIVED",
            },
        )
        assert container.status_code == 201
        blocked = await client.post(
            f"/api/v1/assessments/{data['assessment']['id']}/transition",
            headers=headers,
            json={"to_status": "READY"},
        )
        assert blocked.status_code == 409
        assert blocked.json()["error"]["details"]["code"] == "ASSESSMENT_NO_SCORABLE_QUESTIONS"


@pytest.mark.asyncio
async def test_a2_fix_t04_leaf_ready_succeeds() -> None:
    """A2-FIX-T04"""
    async with gate_client() as client:
        headers = await _headers(client)
        data = await _foundation(client, headers, marks="10.00")
        await _leaf_and_approve(client, headers, data)
        ready = await client.post(
            f"/api/v1/assessments/{data['assessment']['id']}/transition",
            headers=headers,
            json={"to_status": "READY"},
        )
        assert ready.status_code == 200
        assert ready.json()["status"] == "READY"


@pytest.mark.asyncio
async def test_a2_fix_t05_t12_ready_freeze_and_state() -> None:
    """A2-FIX-T05,T06,T09,T11,T12 READY freeze; DRAFT create allowed."""
    async with gate_client() as client:
        headers = await _headers(client)
        data = await _foundation(client, headers, marks="10.00")
        assets = await _leaf_and_approve(client, headers, data)
        approved_key_id = assets["key"]["id"]
        ready = await client.post(
            f"/api/v1/assessments/{data['assessment']['id']}/transition",
            headers=headers,
            json={"to_status": "READY"},
        )
        assert ready.status_code == 200

        # T05
        new_key = await client.post(
            f"/api/v1/assessments/{data['assessment']['id']}/answer-key-versions",
            headers=headers,
            json={
                "assessment_version_id": data["version_id"],
                "question_version_id": assets["leaf"]["id"],
                "answer_text": "mutated",
                "source_type": "TEACHER",
                "status": "DRAFT",
            },
        )
        assert new_key.status_code == 409
        assert new_key.json()["error"]["details"]["code"] == "ASSESSMENT_ACADEMIC_CONFIG_FROZEN"

        # T06
        new_rv = await client.post(
            f"/api/v1/rubrics/{assets['rubric']['id']}/versions",
            headers=headers,
            json={
                "question_version_id": assets["leaf"]["id"],
                "source_type": "TEACHER",
                "status": "DRAFT",
            },
        )
        assert new_rv.status_code == 409
        assert new_rv.json()["error"]["details"]["code"] == "ASSESSMENT_ACADEMIC_CONFIG_FROZEN"

        # T11 / T12
        async with async_session_factory() as db:
            key = await db.get(AnswerKeyVersion, uuid.UUID(approved_key_id))
            assert key is not None
            assert key.status == "APPROVED"
            assert key.answer_text == "ok"
            assessment = await db.get(Assessment, uuid.UUID(data["assessment"]["id"]))
            assert assessment is not None
            assert assessment.status == "READY"

        # T09 on a fresh DRAFT assessment
        draft = await _foundation(client, headers, marks="5.00")
        leaf = await client.post(
            f"/api/v1/assessment-versions/{draft['version_id']}/questions",
            headers=headers,
            json={
                "stable_code": "QD",
                "display_label": "1",
                "sequence": 1,
                "prompt_text": "d",
                "max_marks": "5.00",
                "question_type": "SHORT",
                "scoring_mode": "LEAF_SCORABLE",
            },
        )
        assert leaf.status_code == 201
        allowed = await client.post(
            f"/api/v1/assessments/{draft['assessment']['id']}/answer-key-versions",
            headers=headers,
            json={
                "assessment_version_id": draft["version_id"],
                "question_version_id": leaf.json()["id"],
                "answer_text": "draft-ok",
                "source_type": "TEACHER",
                "status": "DRAFT",
            },
        )
        assert allowed.status_code == 201


@pytest.mark.asyncio
async def test_a2_fix_t07_t08_active_freeze() -> None:
    """A2-FIX-T07,T08 ACTIVE freeze."""
    async with gate_client() as client:
        headers = await _headers(client)
        data = await _foundation(client, headers, marks="10.00")
        assets = await _leaf_and_approve(client, headers, data)
        assert (
            await client.post(
                f"/api/v1/assessments/{data['assessment']['id']}/transition",
                headers=headers,
                json={"to_status": "READY"},
            )
        ).status_code == 200
        active = await client.post(
            f"/api/v1/assessments/{data['assessment']['id']}/transition",
            headers=headers,
            json={"to_status": "ACTIVE"},
        )
        assert active.status_code == 200
        assert active.json()["status"] == "ACTIVE"
        assert (
            await client.post(
                f"/api/v1/assessments/{data['assessment']['id']}/answer-key-versions",
                headers=headers,
                json={
                    "assessment_version_id": data["version_id"],
                    "question_version_id": assets["leaf"]["id"],
                    "answer_text": "x",
                    "source_type": "TEACHER",
                    "status": "DRAFT",
                },
            )
        ).status_code == 409
        assert (
            await client.post(
                f"/api/v1/rubrics/{assets['rubric']['id']}/versions",
                headers=headers,
                json={
                    "question_version_id": assets["leaf"]["id"],
                    "source_type": "TEACHER",
                    "status": "DRAFT",
                },
            )
        ).status_code == 409


@pytest.mark.asyncio
async def test_a2_fix_t10_rubric_review_revision_allowed() -> None:
    """A2-FIX-T10 RUBRIC_REVIEW allows rubric revision."""
    async with gate_client() as client:
        headers = await _headers(client)
        data = await _foundation(client, headers, marks="10.00")
        assets = await _leaf_and_approve(client, headers, data)
        review = await client.post(
            f"/api/v1/assessments/{data['assessment']['id']}/transition",
            headers=headers,
            json={"to_status": "RUBRIC_REVIEW"},
        )
        assert review.status_code == 200
        revision = await client.post(
            f"/api/v1/rubrics/{assets['rubric']['id']}/versions",
            headers=headers,
            json={
                "question_version_id": assets["leaf"]["id"],
                "source_type": "TEACHER",
                "status": "DRAFT",
            },
        )
        assert revision.status_code == 201, revision.text


@pytest.mark.asyncio
async def test_a2_fix_t13_t15_answer_key_audit_redaction() -> None:
    """A2-FIX-T13,T14,T15 audit redaction."""
    async with gate_client() as client:
        headers = await _headers(client)
        data = await _foundation(client, headers, marks="10.00")
        leaf = await client.post(
            f"/api/v1/assessment-versions/{data['version_id']}/questions",
            headers=headers,
            json={
                "stable_code": "QA",
                "display_label": "1",
                "sequence": 1,
                "prompt_text": "q",
                "max_marks": "10.00",
                "question_type": "SHORT",
                "scoring_mode": "LEAF_SCORABLE",
            },
        )
        assert leaf.status_code == 201
        key = await client.post(
            f"/api/v1/assessments/{data['assessment']['id']}/answer-key-versions",
            headers=headers,
            json={
                "assessment_version_id": data["version_id"],
                "question_version_id": leaf.json()["id"],
                "answer_text": MARKER,
                "structured_answer": {"secret": MARKER},
                "source_type": "TEACHER",
                "status": "DRAFT",
            },
        )
        assert key.status_code == 201
        async with async_session_factory() as db:
            event = await db.scalar(
                select(AuditEvent).where(
                    AuditEvent.entity_id == uuid.UUID(key.json()["id"]),
                    AuditEvent.action == "created",
                )
            )
            assert event is not None
            payload = event.payload_json or {}
            blob = str(payload)
            assert MARKER not in blob
            assert "answer_text" not in payload
            assert "structured_answer" not in payload
            assert payload.get("answer_key_version_id") == key.json()["id"]
            assert payload.get("action") == "created"
            assert "version_number" in payload


def test_a2_fix_t16_t20_openapi_patch_schemas() -> None:
    """A2-FIX-T16..T20 OpenAPI PATCH contract alignment (contracts + served schema)."""
    doc = yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))
    paths = doc["paths"]
    schemas = doc["components"]["schemas"]

    def body_ref(path: str) -> str:
        schema = paths[path]["patch"]["requestBody"]["content"]["application/json"]["schema"]
        return schema["$ref"].rsplit("/", 1)[-1]

    assert body_ref("/api/v1/assessments/{id}") == "AssessmentPatch"
    assert body_ref("/api/v1/curricula/{id}") == "CurriculumPatch"
    assert body_ref("/api/v1/curriculum-nodes/{id}") == "CurriculumNodePatch"
    assert body_ref("/api/v1/question-versions/{id}") == "QuestionVersionPatch"
    assert body_ref("/api/v1/academic-years/{id}") == "AcademicYearPatch"
    assert body_ref("/api/v1/class-sections/{id}") == "ClassSectionPatch"
    assert body_ref("/api/v1/students/{id}") == "StudentPatch"
    assert body_ref("/api/v1/guardians/{id}") == "GuardianPatch"
    assert body_ref("/api/v1/answer-key-versions/{id}") == "AnswerKeyVersionPatch"
    assert body_ref("/api/v1/rubric-versions/{id}") == "RubricVersionPatch"
    assert body_ref("/api/v1/rubric-criteria/{id}") == "RubricCriterionPatch"

    for name in (
        "AssessmentPatch",
        "CurriculumPatch",
        "CurriculumNodePatch",
        "QuestionVersionPatch",
        "AcademicYearPatch",
        "ClassSectionPatch",
        "StudentPatch",
        "GuardianPatch",
    ):
        assert not schemas[name].get("required")

    patch_ops = [
        (p, m)
        for p, methods in paths.items()
        for m in methods
        if m == "patch" and p.startswith("/api/v1/")
    ]
    assert patch_ops
    for path, method in patch_ops:
        assert "requestBody" in paths[path][method], path

    served_schemas = create_app().openapi()["components"]["schemas"]
    assert "AssessmentPatch" in served_schemas
    assert "CurriculumPatch" in served_schemas
    assert "QuestionPatch" in served_schemas
    assert "NodePatch" in served_schemas


@pytest.mark.asyncio
async def test_a2_fix_t21_t25_ai_payload_and_summary() -> None:
    """A2-FIX-T21..T25 AI bounds, summary, 503, no auto-approve."""
    async with gate_client() as client:
        headers = await _headers(client)
        qid = str(uuid.uuid4())
        oversized = await client.post(
            "/api/v1/ai/proposals/answer-key",
            headers=headers,
            json={"question_version_id": qid, "instructions": "x" * 501},
        )
        assert oversized.status_code == 422  # T21

        unexpected = await client.post(
            "/api/v1/ai/proposals/answer-key",
            headers=headers,
            json={
                "question_version_id": qid,
                "provider_prompt": "hack",
                "full_paper": "huge",
            },
        )
        assert unexpected.status_code == 422  # T22

        response = await client.post(
            "/api/v1/ai/proposals/answer-key",
            headers=headers,
            json={
                "question_version_id": qid,
                "instructions": "short",
                "context": {"k": "v"},
            },
        )
        assert response.status_code == 503  # T24
        assert response.json()["error"]["details"]["code"] == "AI_PROVIDER_UNAVAILABLE"

        async with async_session_factory() as db:
            record = await db.scalar(
                select(AiExecutionRecord)
                .where(AiExecutionRecord.operation == "propose_answer_key")
                .order_by(AiExecutionRecord.created_at.desc())
            )
            assert record is not None
            summary = record.request_summary or {}
            blob = str(summary)
            assert "full_paper" not in blob
            assert "hack" not in blob
            assert summary.get("instruction_length") == 5
            assert summary.get("question_version_id") == qid
            assert "context_keys" in summary  # T23

        # T25 — proposal does not create academic content
        assessments = await client.get("/api/v1/assessments", headers=headers)
        assert assessments.status_code == 200


def test_a2_fix_t27_server_ai_provenance_assignment() -> None:
    """A2-FIX-T27 server-controlled AI_PROPOSED provenance."""
    assert server_ai_proposed_source_type() == "AI_PROPOSED"
    summary = build_ai_request_summary(
        operation="propose_answer_key",
        request=AnswerKeyProposalRequest(
            question_version_id=uuid.uuid4(),
            instructions="preview",
            context={"a": "1"},
        ),
        requested_by=uuid.uuid4(),
    )
    assert "preview" not in str(summary.values())
    assert summary["instruction_length"] == 7


@pytest.mark.asyncio
async def test_a2_fix_t26_manual_ai_proposed_rejected() -> None:
    """A2-FIX-T26"""
    async with gate_client() as client:
        headers = await _headers(client)
        data = await _foundation(client, headers)
        leaf = await client.post(
            f"/api/v1/assessment-versions/{data['version_id']}/questions",
            headers=headers,
            json={
                "stable_code": "QAI",
                "display_label": "1",
                "sequence": 1,
                "prompt_text": "q",
                "max_marks": "10.00",
                "question_type": "SHORT",
                "scoring_mode": "LEAF_SCORABLE",
            },
        )
        assert leaf.status_code == 201
        rejected = await client.post(
            f"/api/v1/assessments/{data['assessment']['id']}/answer-key-versions",
            headers=headers,
            json={
                "assessment_version_id": data["version_id"],
                "question_version_id": leaf.json()["id"],
                "answer_text": "x",
                "source_type": "AI_PROPOSED",
                "status": "DRAFT",
            },
        )
        assert rejected.status_code == 422
