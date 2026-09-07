"""B10 authoring AI flows — parse, propose answer key/rubric, gates."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.cli.seed_dev import seed
from app.core.config import get_settings
from app.db.models import (
    AnswerKeyVersion,
    AuthoringAiRun,
    Question,
    QuestionVersion,
    RubricVersion,
    Tenant,
)
from app.db.session import async_session_factory
from app.main import create_app
from app.services.storage import ObjectStorage
from tests.test_a2_gate_matrix import _foundation, _headers


def _pdf_with_text(label: str = "1(a) Solve 2x + 3 = 7. [10 marks]") -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=400, height=560)
    page.insert_text((48, 72), label)
    data = doc.tobytes()
    doc.close()
    return data


@asynccontextmanager
async def api_client_authoring(
    *, authoring_provider: str = "fixed"
) -> AsyncIterator[AsyncClient]:
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
    os.environ["AI_PROVIDER_AUTHORING"] = authoring_provider
    os.environ["APP_ENV"] = "test"
    os.environ["S3_ENDPOINT_URL"] = "http://127.0.0.1:19000"
    os.environ["UPLOAD_SCANNER"] = "fixed"
    await seed()
    get_settings.cache_clear()
    ObjectStorage(get_settings()).ensure_bucket()
    # Ensure settings pick up env overrides for this process.
    assert get_settings().celery_task_always_eager is True
    assert get_settings().ai_provider_authoring == authoring_provider
    from app.tasks.celery_app import celery_app

    celery_app.conf.task_always_eager = True
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        yield client
    os.environ["AI_PROVIDER_AUTHORING"] = "none"
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "false"
    get_settings.cache_clear()
    celery_app.conf.task_always_eager = False


async def _upload_question_paper(
    client: AsyncClient, headers: dict[str, str], version_id: str, text: str | None = None
) -> None:
    pdf = _pdf_with_text(text or "1(a) Solve 2x + 3 = 7. [10 marks]")
    response = await client.post(
        f"/api/v1/assessment-versions/{version_id}/question-paper",
        headers=headers,
        files={"file": (f"paper-{uuid.uuid4().hex[:8]}.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 201, response.text


@pytest.mark.asyncio
async def test_b10_parse_edit_apply_questions() -> None:
    async with api_client_authoring(authoring_provider="fixed") as client:
        headers = await _headers(client)
        data = await _foundation(client, headers, marks="10.00")
        version_id = data["version_id"]
        await _upload_question_paper(client, headers, version_id)

        parse = await client.post(
            f"/api/v1/assessment-versions/{version_id}/question-paper/parse",
            headers=headers,
        )
        assert parse.status_code == 200, parse.text
        body = parse.json()
        assert body["status"] == "REVIEW_REQUIRED"
        assert body["operation"] == "PARSE_QUESTION_PAPER"
        run_id = body["id"]

        latest = await client.get(
            f"/api/v1/assessment-versions/{version_id}/authoring-ai-runs/latest"
            "?operation=PARSE_QUESTION_PAPER",
            headers=headers,
        )
        assert latest.status_code == 200, latest.text
        assert latest.json()["id"] == run_id
        assert latest.json()["status"] == "REVIEW_REQUIRED"

        roots = body["proposal_payload"]["roots"]
        assert roots[0]["stable_code"] == "Q1"
        assert roots[0]["children"][0]["stable_code"] == "Q1a"
        assert "2x + 3 = 7" in roots[0]["children"][0]["prompt_text"]

        # Edit leaf prompt then revalidate
        roots[0]["children"][0]["prompt_text"] = "Edited leaf prompt"
        edited = await client.put(
            f"/api/v1/authoring-ai-runs/{run_id}/question-tree-proposal",
            headers=headers,
            json={"roots": roots, "notes": "teacher edit"},
        )
        assert edited.status_code == 200, edited.text
        assert (
            edited.json()["proposal_payload"]["roots"][0]["children"][0]["prompt_text"]
            == "Edited leaf prompt"
        )

        applied = await client.post(
            f"/api/v1/authoring-ai-runs/{run_id}/apply-question-tree",
            headers=headers,
        )
        assert applied.status_code == 200, applied.text
        assert applied.json()["status"] == "SUCCEEDED"

        tree = await client.get(
            f"/api/v1/assessment-versions/{version_id}/questions", headers=headers
        )
        assert tree.status_code == 200
        assert len(tree.json()) == 1
        assert tree.json()[0]["children"][0]["prompt_text"] == "Edited leaf prompt"

        async with async_session_factory() as db:
            codes = set(
                (
                    await db.scalars(
                        select(Question.stable_code).where(
                            Question.assessment_id
                            == uuid.UUID(data["assessment"]["id"])
                        )
                    )
                ).all()
            )
            assert codes == {"Q1", "Q1a"}


@pytest.mark.asyncio
async def test_b10_none_provider_unavailable() -> None:
    async with api_client_authoring(authoring_provider="none") as client:
        headers = await _headers(client)
        data = await _foundation(client, headers, marks="10.00")
        await _upload_question_paper(client, headers, data["version_id"])
        response = await client.post(
            f"/api/v1/assessment-versions/{data['version_id']}/question-paper/parse",
            headers=headers,
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "AI_PROVIDER_UNAVAILABLE"

        # Legacy proposal path still controlled 503
        ak = await client.post(
            "/api/v1/ai/proposals/answer-key",
            headers=headers,
            json={"question_version_id": str(uuid.uuid4())},
        )
        assert ak.status_code == 503
        assert ak.json()["error"]["details"]["code"] == "AI_PROVIDER_UNAVAILABLE"


@pytest.mark.asyncio
async def test_b10_answer_key_and_rubric_ai_proposed_review() -> None:
    async with api_client_authoring(authoring_provider="fixed") as client:
        headers = await _headers(client)
        data = await _foundation(client, headers, marks="10.00")
        leaf = await client.post(
            f"/api/v1/assessment-versions/{data['version_id']}/questions",
            headers=headers,
            json={
                "stable_code": "Q1",
                "display_label": "1",
                "sequence": 1,
                "prompt_text": "2+2?",
                "max_marks": "10.00",
                "question_type": "SHORT",
                "scoring_mode": "LEAF_SCORABLE",
            },
        )
        assert leaf.status_code == 201, leaf.text
        qid = leaf.json()["id"]

        ak = await client.post(
            "/api/v1/ai/proposals/answer-key",
            headers=headers,
            json={
                "question_version_id": qid,
                "assessment_version_id": data["version_id"],
            },
        )
        assert ak.status_code == 200, ak.text
        assert ak.json()["status"] == "REVIEW_REQUIRED"
        assert ak.json()["answer_key_version_id"] is not None

        async with async_session_factory() as db:
            akv = await db.scalar(
                select(AnswerKeyVersion).where(
                    AnswerKeyVersion.id
                    == uuid.UUID(ak.json()["answer_key_version_id"])
                )
            )
            assert akv is not None
            assert akv.source_type == "AI_PROPOSED"
            assert akv.status == "REVIEW_REQUIRED"
            assert akv.status != "APPROVED"

        assessment = await client.get(
            f"/api/v1/assessments/{data['assessment']['id']}", headers=headers
        )
        assert assessment.json()["status"] == "RUBRIC_REVIEW"

        # Transition back to DRAFT so rubric propose can still mutate, then propose
        # (RUBRIC_REVIEW is editable for academic config)
        rub = await client.post(
            "/api/v1/ai/proposals/rubric",
            headers=headers,
            json={
                "question_version_id": qid,
                "assessment_version_id": data["version_id"],
            },
        )
        assert rub.status_code == 200, rub.text
        assert rub.json()["status"] == "REVIEW_REQUIRED"
        assert rub.json()["rubric_version_id"] is not None

        async with async_session_factory() as db:
            rv = await db.scalar(
                select(RubricVersion).where(
                    RubricVersion.id == uuid.UUID(rub.json()["rubric_version_id"])
                )
            )
            assert rv is not None
            assert rv.source_type == "AI_PROPOSED"
            assert rv.status == "REVIEW_REQUIRED"

        # READY blocked while AI proposals are only REVIEW_REQUIRED
        ready = await client.post(
            f"/api/v1/assessments/{data['assessment']['id']}/transition",
            headers=headers,
            json={"to_status": "READY"},
        )
        assert ready.status_code == 409

        # Approve materials then READY ok
        approved_key = await client.post(
            f"/api/v1/answer-key-versions/{ak.json()['answer_key_version_id']}/approve",
            headers=headers,
        )
        assert approved_key.status_code == 200, approved_key.text
        approved_rubric = await client.post(
            f"/api/v1/rubric-versions/{rub.json()['rubric_version_id']}/approve",
            headers=headers,
        )
        assert approved_rubric.status_code == 200, approved_rubric.text

        mapping = await client.post(
            f"/api/v1/question-versions/{qid}/curriculum-mappings",
            headers=headers,
            json={
                "curriculum_node_id": data["node"]["id"],
                "mapping_type": "PRIMARY",
                "weight": "1.00",
            },
        )
        assert mapping.status_code == 201, mapping.text

        ready_ok = await client.post(
            f"/api/v1/assessments/{data['assessment']['id']}/transition",
            headers=headers,
            json={"to_status": "READY"},
        )
        assert ready_ok.status_code == 200, ready_ok.text
        assert ready_ok.json()["status"] == "READY"


@pytest.mark.asyncio
async def test_b10_no_overwrite_teacher_material() -> None:
    async with api_client_authoring(authoring_provider="fixed") as client:
        headers = await _headers(client)
        data = await _foundation(client, headers)
        leaf = await client.post(
            f"/api/v1/assessment-versions/{data['version_id']}/questions",
            headers=headers,
            json={
                "stable_code": "Q1",
                "display_label": "1",
                "sequence": 1,
                "prompt_text": "q",
                "max_marks": "10.00",
                "question_type": "SHORT",
                "scoring_mode": "LEAF_SCORABLE",
            },
        )
        assert leaf.status_code == 201
        qid = leaf.json()["id"]
        teacher = await client.post(
            f"/api/v1/assessments/{data['assessment']['id']}/answer-key-versions",
            headers=headers,
            json={
                "assessment_version_id": data["version_id"],
                "question_version_id": qid,
                "answer_text": "teacher answer",
                "source_type": "TEACHER",
                "status": "DRAFT",
            },
        )
        assert teacher.status_code == 201, teacher.text

        blocked = await client.post(
            "/api/v1/ai/proposals/answer-key",
            headers=headers,
            json={
                "question_version_id": qid,
                "assessment_version_id": data["version_id"],
            },
        )
        assert blocked.status_code == 409
        assert (
            blocked.json()["error"]["code"] == "AUTHORING_MATERIAL_ALREADY_EXISTS"
        )


@pytest.mark.asyncio
async def test_b10_foreign_run_404() -> None:
    async with api_client_authoring(authoring_provider="fixed") as client:
        headers = await _headers(client)
        foreign = await client.get(
            f"/api/v1/authoring-ai-runs/{uuid.uuid4()}", headers=headers
        )
        assert foreign.status_code == 404

        # Cross-tenant: create run then query with other tenant shouldn't see it
        data = await _foundation(client, headers, marks="10.00")
        await _upload_question_paper(client, headers, data["version_id"])
        parse = await client.post(
            f"/api/v1/assessment-versions/{data['version_id']}/question-paper/parse",
            headers=headers,
        )
        assert parse.status_code == 200
        run_id = parse.json()["id"]

        async with async_session_factory() as db:
            other = Tenant(slug=f"b10-{uuid.uuid4().hex[:8]}", name="Other")
            db.add(other)
            await db.flush()
            run = await db.scalar(
                select(AuthoringAiRun).where(AuthoringAiRun.id == uuid.UUID(run_id))
            )
            assert run is not None
            # Tenant scoping is via auth context; foreign UUID of another tenant's run
            # is simulated by querying a run that doesn't belong to demo after rewrite.
            run.tenant_id = other.id
            await db.commit()

        missing = await client.get(
            f"/api/v1/authoring-ai-runs/{run_id}", headers=headers
        )
        assert missing.status_code == 404


@pytest.mark.asyncio
async def test_b10_mark_mismatch_review_blocking() -> None:
    async with api_client_authoring(authoring_provider="fixed") as client:
        headers = await _headers(client)
        data = await _foundation(client, headers, marks="10.00")
        await _upload_question_paper(client, headers, data["version_id"])
        parse = await client.post(
            f"/api/v1/assessment-versions/{data['version_id']}/question-paper/parse",
            headers=headers,
        )
        assert parse.status_code == 200
        run_id = parse.json()["id"]
        roots = parse.json()["proposal_payload"]["roots"]
        # Break leaf marks so they no longer sum to assessment max
        roots[0]["children"][0]["max_marks"] = "3.00"
        roots[0]["max_marks"] = "3.00"

        bad = await client.put(
            f"/api/v1/authoring-ai-runs/{run_id}/question-tree-proposal",
            headers=headers,
            json={"roots": roots},
        )
        assert bad.status_code == 422
        assert bad.json()["error"]["code"] == "QUESTION_TREE_MARKS_MISMATCH"

        # Apply still blocked if payload were somehow invalid — keep REVIEW_REQUIRED
        got = await client.get(
            f"/api/v1/authoring-ai-runs/{run_id}", headers=headers
        )
        assert got.json()["status"] == "REVIEW_REQUIRED"

        # Confirm original proposal still applies
        apply = await client.post(
            f"/api/v1/authoring-ai-runs/{run_id}/apply-question-tree",
            headers=headers,
        )
        assert apply.status_code == 200
        assert apply.json()["status"] == "SUCCEEDED"

        async with async_session_factory() as db:
            count = len(
                list(
                    (
                        await db.scalars(
                            select(QuestionVersion).where(
                                QuestionVersion.assessment_version_id
                                == uuid.UUID(data["version_id"])
                            )
                        )
                    ).all()
                )
            )
            assert count == 2
            reconcile = await client.get(
                f"/api/v1/assessment-versions/{data['version_id']}/marks/reconcile",
                headers=headers,
            )
            assert reconcile.json()["valid"] is True
            assert Decimal(reconcile.json()["leaf_marks_total"]) == Decimal("10.00")
