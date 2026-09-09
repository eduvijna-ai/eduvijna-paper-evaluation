"""B7 publication reports + annotated paper coverage."""

from __future__ import annotations

import hashlib
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal

import fitz
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.ai.providers.narrative import FixedNarrativeProvider
from app.ai.providers.openai import OpenAIStructureProvider
from app.ai.types import (
    ParentNarrativeInput,
    ParentNarrativeResult,
    StudentNarrativeInput,
    StudentNarrativeResult,
)
from app.cli.seed_dev import seed
from app.core.config import get_settings
from app.db.models import Annotation, PublishedResult, QuestionEvaluation, Submission, Tenant
from app.db.session import async_session_factory
from app.main import create_app
from app.services.storage import ObjectStorage
from tests.test_b3_submission_ingestion import _headers
from tests.test_b6_evaluation_ledger import (
    _ready_assessment,
    _to_ready_for_evaluation,
)


@asynccontextmanager
async def api_client_publication(
    *, text_provider: str = "fixed"
) -> AsyncIterator[AsyncClient]:
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
    os.environ["S3_ENDPOINT_URL"] = "http://127.0.0.1:19000"
    os.environ["AI_PROVIDER_VISION"] = "fixed"
    os.environ["AI_PROVIDER_TEXT"] = text_provider
    os.environ["APP_ENV"] = "test"
    await seed()
    get_settings.cache_clear()
    from app.tasks.celery_app import celery_app

    celery_app.conf.task_always_eager = True
    ObjectStorage(get_settings()).ensure_bucket()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=create_app()), base_url="http://test"
        ) as client:
            yield client
    finally:
        os.environ["AI_PROVIDER_VISION"] = "none"
        os.environ["AI_PROVIDER_TEXT"] = "none"
        get_settings.cache_clear()


async def _to_approved(
    client: AsyncClient,
    headers: dict[str, str],
    data: dict,
    *,
    override_answered: Decimal | None = Decimal("3.5"),
) -> tuple[str, str]:
    """Reach APPROVED via B6 helpers. Returns (submission_id, student_id)."""
    sid = await _to_ready_for_evaluation(client, headers, data)
    # Capture student from identity confirm path
    sub_get = await client.get(f"/api/v1/submissions/{sid}", headers=headers)
    assert sub_get.status_code == 200, sub_get.text
    student_id = sub_get.json().get("student_id")

    prep = await client.post(
        f"/api/v1/submissions/{sid}/evaluation/prepare", headers=headers
    )
    assert prep.status_code == 200, prep.text

    workspace = await client.get(
        f"/api/v1/submissions/{sid}/evaluation", headers=headers
    )
    assert workspace.status_code == 200, workspace.text
    qes = workspace.json()["question_evaluations"]
    blank = next(q for q in qes if "INCOMPLETE" in (q.get("error_codes") or []))
    answered = next(q for q in qes if q["id"] != blank["id"])

    acc = await client.post(
        f"/api/v1/question-evaluations/{blank['id']}/accept", headers=headers
    )
    assert acc.status_code == 200, acc.text

    if override_answered is not None:
        over = await client.post(
            f"/api/v1/question-evaluations/{answered['id']}/override",
            headers=headers,
            json={"score": float(override_answered), "reason": "Teacher adjustment"},
        )
        assert over.status_code == 200, over.text
    else:
        acc2 = await client.post(
            f"/api/v1/question-evaluations/{answered['id']}/accept", headers=headers
        )
        assert acc2.status_code == 200, acc2.text

    fin = await client.post(
        f"/api/v1/submissions/{sid}/evaluation/finalize", headers=headers
    )
    assert fin.status_code == 200, fin.text
    assert fin.json()["workflow_state"] == "APPROVED"
    return sid, student_id


@pytest.mark.asyncio
async def test_b7_prepare_generate_publish_consumer_gates() -> None:
    async with api_client_publication(text_provider="fixed") as client:
        headers = await _headers(client)
        data = await _ready_assessment(client, headers)
        sid, student_id = await _to_approved(client, headers, data)
        assessment_id = data["assessment"]["id"]

        # Consumer 404 before publish
        before = await client.get(
            f"/api/v1/submissions/{sid}/published-result", headers=headers
        )
        assert before.status_code == 404

        prep = await client.post(
            f"/api/v1/submissions/{sid}/publication/prepare", headers=headers
        )
        assert prep.status_code == 200, prep.text
        body = prep.json()
        assert body["workflow_state"] == "APPROVED"  # never auto-publish
        prid = body["published_result_id"]

        # Eager pipeline → GENERATED
        workspace = await client.get(
            f"/api/v1/submissions/{sid}/publication", headers=headers
        )
        assert workspace.status_code == 200, workspace.text
        latest = workspace.json()["latest"]
        assert latest is not None
        assert latest["status"] == "GENERATED"
        assert latest["id"] == prid
        assert workspace.json()["workflow_state"] == "APPROVED"

        # Annotations use final scores only (override 3.5 visible)
        anns = workspace.json()["annotations"]
        assert anns
        mark_anns = [a for a in anns if a["annotation_type"] == "MARK"]
        assert mark_anns
        finals = {
            a["payload"].get("final_marks")
            for a in mark_anns
            if a["payload"].get("final_marks") is not None
        }
        assert 3.5 in finals or Decimal("3.5") in {Decimal(str(x)) for x in finals}
        for a in anns:
            assert "proposed_ai_score" not in (a.get("payload") or {})

        # Idempotent prepare for same snapshot
        prep2 = await client.post(
            f"/api/v1/submissions/{sid}/publication/prepare", headers=headers
        )
        assert prep2.status_code == 200, prep2.text
        assert prep2.json()["published_result_id"] == prid

        # Preview reports while GENERATED
        for audience in ("student", "parent", "teacher"):
            prev = await client.get(
                f"/api/v1/publication-results/{prid}/reports/{audience}",
                headers=headers,
            )
            assert prev.status_code == 200, prev.text
            payload = prev.json()
            assert payload["ledger_snapshot_hash"]
            if audience == "student":
                assert payload["narrative_source"] == "FIXED"
                assert "proposed_ai_score" not in str(payload)
                for q in payload["questions"]:
                    assert "proposed_ai_score" not in q
                    assert q["final_score"] is not None
            if audience == "parent":
                assert payload["total_score"] is not None
            if audience == "teacher":
                assert any(q["final_score"] == 3.5 for q in payload["questions"])

        # Still 404 for consumers
        mid = await client.get(
            f"/api/v1/submissions/{sid}/published-result", headers=headers
        )
        assert mid.status_code == 404
        aud = await client.get(
            f"/api/v1/reports/student/{student_id}/assessments/{assessment_id}",
            headers=headers,
        )
        assert aud.status_code == 404

        # PDF artifacts
        for atype in (
            "ANNOTATED_PDF",
            "STUDENT_REPORT_PDF",
            "PARENT_REPORT_PDF",
            "TEACHER_REPORT_PDF",
        ):
            art = await client.get(
                f"/api/v1/publication-results/{prid}/artifacts/{atype}",
                headers=headers,
            )
            assert art.status_code == 200, art.text
            assert art.headers["content-type"].startswith("application/pdf")
            assert art.content.startswith(b"%PDF")
            doc = fitz.open(stream=art.content, filetype="pdf")
            try:
                assert doc.page_count >= 1
            finally:
                doc.close()
            digest = hashlib.sha256(art.content).hexdigest()
            info = latest["artifacts"][atype]
            assert info["sha256"] == digest

        # Manual COMMENT while GENERATED
        page_id = workspace.json()["annotations"][0]["submission_page_id"]
        man = await client.post(
            f"/api/v1/publication-results/{prid}/annotations",
            headers=headers,
            json={
                "annotation_type": "COMMENT",
                "submission_page_id": page_id,
                "x": 0.1,
                "y": 0.1,
                "width": 0.2,
                "height": 0.05,
                "payload": {"text": "Nice attempt"},
            },
        )
        assert man.status_code == 200, man.text
        assert man.json()["source_type"] == "HUMAN"

        # Score mutation forbidden
        bad = await client.post(
            f"/api/v1/publication-results/{prid}/annotations",
            headers=headers,
            json={
                "annotation_type": "COMMENT",
                "submission_page_id": page_id,
                "x": 0.2,
                "y": 0.2,
                "width": 0.1,
                "height": 0.05,
                "payload": {"final_marks": 99},
            },
        )
        assert bad.status_code == 409

        # Publish
        pub = await client.post(
            f"/api/v1/publication-results/{prid}/publish", headers=headers
        )
        assert pub.status_code == 200, pub.text
        assert pub.json()["status"] == "PUBLISHED"

        after = await client.get(
            f"/api/v1/submissions/{sid}/published-result", headers=headers
        )
        assert after.status_code == 200, after.text
        assert after.json()["status"] == "PUBLISHED"

        for audience in ("student", "parent", "teacher"):
            r = await client.get(
                f"/api/v1/reports/{audience}/{student_id}/assessments/{assessment_id}",
                headers=headers,
            )
            assert r.status_code == 200, r.text

        # Immutable when PUBLISHED
        imm = await client.post(
            f"/api/v1/publication-results/{prid}/annotations",
            headers=headers,
            json={
                "annotation_type": "HIGHLIGHT",
                "submission_page_id": page_id,
                "x": 0.3,
                "y": 0.3,
                "width": 0.1,
                "height": 0.05,
                "payload": {"text": "nope"},
            },
        )
        assert imm.status_code == 409
        regen = await client.post(
            f"/api/v1/publication-results/{prid}/regenerate", headers=headers
        )
        assert regen.status_code == 409

        sub = await client.get(f"/api/v1/submissions/{sid}", headers=headers)
        assert sub.json()["workflow_state"] == "PUBLISHED"


@pytest.mark.asyncio
async def test_b7_stale_snapshot_blocks_publish() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment(client, headers)
        sid, _ = await _to_approved(client, headers, data)

        prep = await client.post(
            f"/api/v1/submissions/{sid}/publication/prepare", headers=headers
        )
        assert prep.status_code == 200, prep.text
        prid = prep.json()["published_result_id"]

        workspace = await client.get(
            f"/api/v1/submissions/{sid}/publication", headers=headers
        )
        assert workspace.json()["latest"]["status"] == "GENERATED"

        # Mutate ledger final score directly → stale snapshot on publish
        async with async_session_factory() as db:
            qes = list(
                (
                    await db.scalars(
                        select(QuestionEvaluation).where(
                            QuestionEvaluation.submission_id == uuid.UUID(sid)
                        )
                    )
                ).all()
            )
            assert qes
            qes[0].final_human_approved_score = Decimal("0.25")
            await db.commit()

        pub = await client.post(
            f"/api/v1/publication-results/{prid}/publish", headers=headers
        )
        assert pub.status_code == 409
        assert pub.json()["error"]["details"]["code"] == "STALE_SNAPSHOT"


@pytest.mark.asyncio
async def test_b7_tenant_isolation() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment(client, headers)
        sid, _ = await _to_approved(client, headers, data)
        prep = await client.post(
            f"/api/v1/submissions/{sid}/publication/prepare", headers=headers
        )
        assert prep.status_code == 200
        prid = prep.json()["published_result_id"]

        # Foreign UUID → 404
        other = uuid.uuid4()
        r = await client.get(
            f"/api/v1/publication-results/{other}/reports/student", headers=headers
        )
        assert r.status_code == 404

        async with async_session_factory() as db:
            foreign = Tenant(slug=f"b7-other-{uuid.uuid4().hex[:8]}", name="Other")
            db.add(foreign)
            await db.flush()
            # Point published result at other tenant via raw update is blocked by query scope;
            # accessing with current auth against a crafted other-tenant row:
            row = await db.scalar(
                select(PublishedResult).where(PublishedResult.id == uuid.UUID(prid))
            )
            assert row is not None
            row.tenant_id = foreign.id
            await db.commit()

        r2 = await client.get(
            f"/api/v1/publication-results/{prid}/reports/student", headers=headers
        )
        assert r2.status_code == 404

        art = await client.get(
            f"/api/v1/publication-results/{prid}/artifacts/ANNOTATED_PDF",
            headers=headers,
        )
        assert art.status_code == 404


@pytest.mark.asyncio
async def test_b7_narrative_rules_fallback_and_openai_mock() -> None:
    # none → RULES_FALLBACK
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        data = await _ready_assessment(client, headers)
        sid, _ = await _to_approved(client, headers, data)
        prep = await client.post(
            f"/api/v1/submissions/{sid}/publication/prepare", headers=headers
        )
        assert prep.status_code == 200, prep.text
        prid = prep.json()["published_result_id"]
        prev = await client.get(
            f"/api/v1/publication-results/{prid}/reports/student", headers=headers
        )
        assert prev.status_code == 200, prev.text
        assert prev.json()["narrative_source"] == "RULES_FALLBACK"
        assert prev.json()["status"] if "status" in prev.json() else True
        workspace = await client.get(
            f"/api/v1/submissions/{sid}/publication", headers=headers
        )
        assert workspace.json()["latest"]["status"] == "GENERATED"
        assert workspace.json()["workflow_state"] == "APPROVED"

    # Fixed provider unit
    fixed = FixedNarrativeProvider(allow_non_test=True)
    student = await fixed.generate_student_explanation(
        StudentNarrativeInput(
            assessment_title="Quiz",
            student_display_name="Ada",
            questions=[],
        )
    )
    assert student.strengths
    parent = await fixed.generate_parent_summary(
        ParentNarrativeInput(
            assessment_title="Quiz",
            student_display_name="Ada",
            performance_overview="mixed",
        )
    )
    assert parent.next_step

    # OpenAI injectable caller
    async def caller(operation: str, payload: dict) -> dict:
        if operation == "generate_student_explanation":
            return {
                "strengths": ["Clear working"],
                "areas_for_improvement": ["Check signs"],
                "next_steps": ["Retry Q2"],
                "question_narratives": [],
            }
        return {
            "what_went_well": ["Effort"],
            "what_to_practice": ["Fractions"],
            "how_family_can_help": ["Quiet time"],
            "next_step": "Practice nightly",
            "score_summary": "A plain summary",
        }

    openai = OpenAIStructureProvider(
        api_key=None,
        model_identity="m",
        model_page_analysis="m",
        model_mapping="m",
        model_transcription="m",
        model_student_report="m-student",
        model_parent_report="m-parent",
        caller=caller,
    )
    sn = await openai.generate_student_explanation(
        StudentNarrativeInput(
            assessment_title="Quiz",
            student_display_name="Ada",
            questions=[],
        )
    )
    assert isinstance(sn, StudentNarrativeResult)
    assert sn.strengths == ["Clear working"]
    pn = await openai.generate_parent_summary(
        ParentNarrativeInput(
            assessment_title="Quiz",
            student_display_name="Ada",
        )
    )
    assert isinstance(pn, ParentNarrativeResult)
    assert pn.next_step == "Practice nightly"


@pytest.mark.asyncio
async def test_b7_regenerate_new_version() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment(client, headers)
        sid, _ = await _to_approved(client, headers, data)
        prep = await client.post(
            f"/api/v1/submissions/{sid}/publication/prepare", headers=headers
        )
        prid = prep.json()["published_result_id"]
        workspace = await client.get(
            f"/api/v1/submissions/{sid}/publication", headers=headers
        )
        assert workspace.json()["latest"]["status"] == "GENERATED"
        assert workspace.json()["latest"]["version_number"] == 1

        regen = await client.post(
            f"/api/v1/publication-results/{prid}/regenerate", headers=headers
        )
        assert regen.status_code == 200, regen.text
        assert regen.json()["version_number"] == 2
        assert regen.json()["supersedes_result_id"] == prid

        workspace2 = await client.get(
            f"/api/v1/submissions/{sid}/publication", headers=headers
        )
        assert workspace2.json()["latest"]["status"] == "GENERATED"
        assert workspace2.json()["latest"]["version_number"] == 2
        assert len(workspace2.json()["versions"]) >= 2


@pytest.mark.asyncio
async def test_b7_db_annotations_final_not_proposed() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment(client, headers)
        sid, _ = await _to_approved(
            client, headers, data, override_answered=Decimal("4.0")
        )
        prep = await client.post(
            f"/api/v1/submissions/{sid}/publication/prepare", headers=headers
        )
        prid = uuid.UUID(prep.json()["published_result_id"])

        async with async_session_factory() as db:
            qes = list(
                (
                    await db.scalars(
                        select(QuestionEvaluation).where(
                            QuestionEvaluation.submission_id == uuid.UUID(sid)
                        )
                    )
                ).all()
            )
            for qe in qes:
                assert qe.final_human_approved_score is not None
            anns = list(
                (
                    await db.scalars(
                        select(Annotation).where(Annotation.published_result_id == prid)
                    )
                ).all()
            )
            assert anns
            for a in anns:
                assert a.source_type == "LEDGER"
                payload = a.payload or {}
                assert "proposed_ai_score" not in payload
                if a.annotation_type == "MARK" and payload.get("final_marks") == 4.0:
                    break
            else:
                # At least one mark should carry the override
                mark_vals = [
                    (a.payload or {}).get("final_marks")
                    for a in anns
                    if a.annotation_type == "MARK"
                ]
                assert 4.0 in mark_vals

            sub = await db.scalar(
                select(Submission).where(Submission.id == uuid.UUID(sid))
            )
            assert sub is not None
            assert sub.workflow_state == "APPROVED"
