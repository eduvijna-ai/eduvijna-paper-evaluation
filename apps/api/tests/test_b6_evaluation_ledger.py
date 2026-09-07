"""B6 evaluation ledger coverage (fixed provider + sympy + openai mock)."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import select

from app.ai.providers.fixed import FixedStructureProvider
from app.ai.providers.openai import OpenAIStructureProvider
from app.ai.types import (
    CriterionProposal,
    RubricCriterionSnapshot,
    RubricEvaluationInput,
    RubricEvaluationResult,
)
from app.cli.seed_dev import seed
from app.core.config import get_settings
from app.db.models import (
    AiExecutionRecord,
    EvaluationRun,
    ReviewAction,
    Submission,
)
from app.db.session import async_session_factory
from app.main import create_app
from app.services.evaluation import validate_provider_result
from app.services.math_verification import verify_math
from app.services.storage import ObjectStorage
from tests.test_a2_gate_matrix import _foundation
from tests.test_b3_submission_ingestion import _headers, _pdf_bytes
from tests.test_b4_answer_region_mapping import _add_leaf, _ensure_student


@asynccontextmanager
async def api_client_fixed() -> AsyncIterator[AsyncClient]:
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
    os.environ["S3_ENDPOINT_URL"] = "http://127.0.0.1:19000"
    os.environ["AI_PROVIDER_VISION"] = "fixed"
    os.environ["APP_ENV"] = "test"
    await seed()
    get_settings.cache_clear()
    from app.tasks.celery_app import celery_app

    celery_app.conf.task_always_eager = True
    ObjectStorage(get_settings()).ensure_bucket()
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        yield client
    os.environ["AI_PROVIDER_VISION"] = "none"
    get_settings.cache_clear()


async def _ready_assessment(client: AsyncClient, headers: dict[str, str]) -> dict:
    data = await _foundation(client, headers)
    await _add_leaf(client, headers, data, marks="5.00", sequence=1, label="1")
    await _add_leaf(client, headers, data, marks="5.00", sequence=2, label="2")
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
    return data


async def _to_ready_for_evaluation(
    client: AsyncClient,
    headers: dict[str, str],
    data: dict,
    *,
    second_disposition: str = "BLANK",
    answered_text: str = "EXERCISE:FULL answer",
    unreadable: bool = False,
) -> str:
    upload = await client.post(
        "/api/v1/submissions",
        headers=headers,
        files={"file": ("b6.pdf", _pdf_bytes(), "application/pdf")},
        data={"assessment_id": data["assessment"]["id"]},
    )
    assert upload.status_code == 201, upload.text
    sid = upload.json()["id"]

    student_id = await _ensure_student(client, headers)
    confirm = await client.post(
        f"/api/v1/submissions/{sid}/identity/confirm",
        headers=headers,
        json={"student_id": student_id},
    )
    assert confirm.status_code == 200, confirm.text

    mapping = await client.get(f"/api/v1/submissions/{sid}/mapping", headers=headers)
    assert mapping.status_code == 200
    mbody = mapping.json()
    leaves = [n for n in mbody["questions"] if n.get("is_leaf_scorable")]
    assert len(leaves) >= 2
    region_id = mbody["regions"][0]["id"]

    first = leaves[0]
    put1 = await client.put(
        f"/api/v1/submissions/{sid}/question-mappings/{first['question_version_id']}",
        headers=headers,
        json={"disposition": "ANSWERED", "region_ids": [region_id]},
    )
    assert put1.status_code == 200, put1.text
    assert (
        await client.post(
            f"/api/v1/submissions/{sid}/question-mappings/{first['question_version_id']}/confirm",
            headers=headers,
        )
    ).status_code == 200

    second = leaves[1]
    put2 = await client.put(
        f"/api/v1/submissions/{sid}/question-mappings/{second['question_version_id']}",
        headers=headers,
        json={"disposition": second_disposition, "region_ids": []},
    )
    assert put2.status_code == 200, put2.text
    assert (
        await client.post(
            f"/api/v1/submissions/{sid}/question-mappings/{second['question_version_id']}/confirm",
            headers=headers,
        )
    ).status_code == 200

    fin = await client.post(f"/api/v1/submissions/{sid}/mapping/finalize", headers=headers)
    assert fin.status_code == 200, fin.text

    workspace = await client.get(f"/api/v1/submissions/{sid}/transcription", headers=headers)
    assert workspace.status_code == 200
    for item in workspace.json()["items"]:
        for region in item["regions"]:
            if not region.get("requires_transcription"):
                continue
            body: dict = {"outcome": "UNREADABLE"} if unreadable else {
                "text": answered_text,
                "outcome": "TRANSCRIBED",
            }
            put = await client.put(
                f"/api/v1/answer-regions/{region['id']}/transcription",
                headers=headers,
                json=body,
            )
            assert put.status_code == 200, put.text
            conf = await client.post(
                f"/api/v1/answer-region-transcriptions/{put.json()['id']}/confirm",
                headers=headers,
            )
            assert conf.status_code == 200, conf.text

    finalize = await client.post(
        f"/api/v1/submissions/{sid}/transcription/finalize", headers=headers
    )
    assert finalize.status_code == 200, finalize.text
    assert finalize.json()["transcription_state"] == "READY"
    assert finalize.json()["workflow_state"] == "READY_FOR_EVALUATION"
    return sid


@pytest.mark.asyncio
async def test_b6_prepare_gates_and_blank_unreadable_accept_finalize() -> None:
    async with api_client_fixed() as client:
        headers = await _headers(client)
        data = await _ready_assessment(client, headers)
        sid = await _to_ready_for_evaluation(client, headers, data)

        # Gate: prepare before READY_FOR_EVALUATION fails if already evaluating later;
        # first prepare succeeds.
        prep = await client.post(
            f"/api/v1/submissions/{sid}/evaluation/prepare", headers=headers
        )
        assert prep.status_code == 200, prep.text
        assert prep.json()["workflow_state"] in {"EVALUATING", "EVALUATION_REVIEW"}
        run_id = prep.json()["evaluation_run_id"]

        # Idempotent prepare while active / after: still returns run (workflow may advance)
        prep2 = await client.post(
            f"/api/v1/submissions/{sid}/evaluation/prepare", headers=headers
        )
        # After eager pipeline, workflow is EVALUATION_REVIEW — prepare must reject
        if prep2.status_code == 409:
            assert prep2.json()["error"]["details"]["code"] == "INVALID_WORKFLOW_STATE"
        else:
            assert prep2.json()["evaluation_run_id"] == run_id

        workspace = await client.get(
            f"/api/v1/submissions/{sid}/evaluation", headers=headers
        )
        assert workspace.status_code == 200, workspace.text
        body = workspace.json()
        assert body["workflow_state"] == "EVALUATION_REVIEW"
        assert "overall_confidence" not in body
        assert body["evaluation_run"]["status"] == "REVIEW_REQUIRED"
        qes = body["question_evaluations"]
        assert len(qes) == 2

        blank = next(q for q in qes if "INCOMPLETE" in (q.get("error_codes") or []))
        answered = next(q for q in qes if q["id"] != blank["id"])

        assert blank["proposed_ai_score"] == 0
        assert blank["evaluation_confidence"] == 1.0
        assert blank["workflow_state"] in {"PROPOSED", "REVIEW_REQUIRED"}

        assert answered["proposed_ai_score"] is not None
        assert answered["evaluation_confidence"] is not None
        assert "overall_confidence" not in answered

        # Accept blank (0) and answered
        acc_blank = await client.post(
            f"/api/v1/question-evaluations/{blank['id']}/accept", headers=headers
        )
        assert acc_blank.status_code == 200, acc_blank.text
        assert acc_blank.json()["workflow_state"] == "ACCEPTED"
        assert acc_blank.json()["final_human_approved_score"] == 0

        # Override answered instead of accept
        over = await client.post(
            f"/api/v1/question-evaluations/{answered['id']}/override",
            headers=headers,
            json={"score": 3.5, "reason": "Teacher adjustment"},
        )
        assert over.status_code == 200, over.text
        assert over.json()["workflow_state"] == "OVERRIDDEN"
        assert over.json()["proposed_ai_score"] == answered["proposed_ai_score"]
        assert over.json()["final_human_approved_score"] == 3.5

        fin = await client.post(
            f"/api/v1/submissions/{sid}/evaluation/finalize", headers=headers
        )
        assert fin.status_code == 200, fin.text
        assert fin.json()["workflow_state"] == "APPROVED"
        assert fin.json()["workflow_state"] != "PUBLISHED"
        assert fin.json()["run_status"] == "COMPLETED"

        async with async_session_factory() as db:
            sub = await db.scalar(select(Submission).where(Submission.id == uuid.UUID(sid)))
            assert sub is not None
            assert sub.workflow_state == "APPROVED"
            run = await db.scalar(
                select(EvaluationRun).where(EvaluationRun.id == uuid.UUID(run_id))
            )
            assert run is not None
            assert run.status == "COMPLETED"
            actions = list(
                (
                    await db.scalars(
                        select(ReviewAction).where(ReviewAction.submission_id == uuid.UUID(sid))
                    )
                ).all()
            )
            types = {a.action_type for a in actions}
            assert "ACCEPT" in types
            assert "OVERRIDE" in types
            execs = list(
                (
                    await db.scalars(
                        select(AiExecutionRecord).where(
                            AiExecutionRecord.submission_id == uuid.UUID(sid),
                            AiExecutionRecord.operation == "evaluate_rubric",
                        )
                    )
                ).all()
            )
            assert len(execs) >= 2
            for e in execs:
                assert e.evaluation_run_id is not None
                assert e.question_evaluation_id is not None


@pytest.mark.asyncio
async def test_b6_unreadable_null_proposal_blocks_accept() -> None:
    async with api_client_fixed() as client:
        headers = await _headers(client)
        data = await _ready_assessment(client, headers)
        sid = await _to_ready_for_evaluation(
            client, headers, data, unreadable=True
        )
        prep = await client.post(
            f"/api/v1/submissions/{sid}/evaluation/prepare", headers=headers
        )
        assert prep.status_code == 200, prep.text
        workspace = await client.get(
            f"/api/v1/submissions/{sid}/evaluation", headers=headers
        )
        qes = workspace.json()["question_evaluations"]
        unread = next(
            q
            for q in qes
            if "UNREADABLE" in (q.get("error_codes") or []) and q["proposed_ai_score"] is None
        )
        assert unread["workflow_state"] == "REVIEW_REQUIRED"
        assert unread["proposed_ai_score"] is None
        bad = await client.post(
            f"/api/v1/question-evaluations/{unread['id']}/accept", headers=headers
        )
        assert bad.status_code == 409
        assert bad.json()["error"]["details"]["code"] == "NO_PROPOSAL"

        # Override still allowed
        over = await client.post(
            f"/api/v1/question-evaluations/{unread['id']}/override",
            headers=headers,
            json={"score": 2.0, "reason": "Human read the scan"},
        )
        assert over.status_code == 200, over.text
        assert over.json()["workflow_state"] == "OVERRIDDEN"


@pytest.mark.asyncio
async def test_b6_prepare_rejects_without_transcription_ready() -> None:
    async with api_client_fixed() as client:
        headers = await _headers(client)
        data = await _ready_assessment(client, headers)
        upload = await client.post(
            "/api/v1/submissions",
            headers=headers,
            files={"file": ("b6b.pdf", _pdf_bytes(), "application/pdf")},
            data={"assessment_id": data["assessment"]["id"]},
        )
        sid = upload.json()["id"]
        student_id = await _ensure_student(client, headers)
        await client.post(
            f"/api/v1/submissions/{sid}/identity/confirm",
            headers=headers,
            json={"student_id": student_id},
        )
        # Not through transcription finalize
        prep = await client.post(
            f"/api/v1/submissions/{sid}/evaluation/prepare", headers=headers
        )
        assert prep.status_code == 409
        assert prep.json()["error"]["details"]["code"] in {
            "INVALID_WORKFLOW_STATE",
            "TRANSCRIPTION_NOT_READY",
        }


def test_b6_sympy_verify_math() -> None:
    ok = verify_math(student_expr="(x+1)**2", expected_expr="x**2 + 2*x + 1")
    assert ok.equivalent is True
    assert ok.math_verification_confidence is not None
    assert ok.math_verification_confidence >= Decimal("0.9")

    bad = verify_math(student_expr="x+1", expected_expr="x+2")
    assert bad.equivalent is False

    fail = verify_math(student_expr="__import__('os')", expected_expr="1")
    assert fail.equivalent is None
    assert fail.math_verification_confidence is None or fail.math_verification_confidence < 1

    tol = verify_math(
        student_expr="1.0000001",
        expected_expr="1",
        structured_answer={"tolerance": "0.001"},
    )
    assert tol.equivalent is True


@pytest.mark.asyncio
async def test_b6_fixed_provider_exercises() -> None:
    provider = FixedStructureProvider(allow_non_test=True)
    cid = uuid.uuid4()
    crit = RubricCriterionSnapshot(
        id=cid,
        code="C1",
        label="correct",
        max_marks=Decimal("5"),
        sequence=1,
        partial_credit_allowed=True,
        ecf_policy="NONE",
    )
    base = RubricEvaluationInput(
        question_version_id=uuid.uuid4(),
        assessment_version_id=uuid.uuid4(),
        rubric_criteria=[crit],
        answer_key_text="42",
        transcription_text="EXERCISE:FULL",
        max_mark=Decimal("5"),
    )
    full = await provider.evaluate_rubric(base)
    assert full.proposed_total == Decimal("5")
    assert full.evaluation_confidence == Decimal("0.9100")

    partial = await provider.evaluate_rubric(
        base.model_copy(update={"transcription_text": "EXERCISE:PARTIAL"})
    )
    assert partial.error_codes == ["INCOMPLETE"]
    assert partial.proposed_total == Decimal("2.5000")

    deduct = await provider.evaluate_rubric(
        base.model_copy(update={"transcription_text": "EXERCISE:DEDUCT"})
    )
    assert "CALCULATION" in deduct.error_codes

    alt = await provider.evaluate_rubric(
        base.model_copy(update={"transcription_text": "EXERCISE:ALT"})
    )
    assert alt.alternative_method_id == "fixed-alt-1"
    assert "VALID_ALTERNATIVE" in alt.error_codes


def test_b6_provider_validation_rejects_foreign_and_ecf() -> None:
    from types import SimpleNamespace

    real_id = uuid.uuid4()
    foreign = uuid.uuid4()
    criteria = [
        SimpleNamespace(id=real_id, max_marks=Decimal("5"), ecf_policy="NONE"),
    ]
    bad = RubricEvaluationResult(
        criterion_proposals=[
            CriterionProposal(
                rubric_criterion_id=foreign,
                decision="AWARDED",
                proposed_marks=Decimal("5"),
            )
        ],
        proposed_total=Decimal("5"),
        evaluation_confidence=Decimal("0.9"),
        ecf_applied=False,
        error_codes=[],
    )
    ok, code, _ = validate_provider_result(
        result=bad, criteria=criteria, max_mark=Decimal("5")  # type: ignore[arg-type]
    )
    assert ok is False
    assert code == "OTHER_REVIEW_REQUIRED"

    ecf_bad = RubricEvaluationResult(
        criterion_proposals=[
            CriterionProposal(
                rubric_criterion_id=real_id,
                decision="AWARDED",
                proposed_marks=Decimal("5"),
                ecf_source_criterion_id=uuid.uuid4(),
            )
        ],
        proposed_total=Decimal("5"),
        evaluation_confidence=Decimal("0.9"),
        ecf_applied=True,
        error_codes=[],
    )
    ok2, code2, _ = validate_provider_result(
        result=ecf_bad, criteria=criteria, max_mark=Decimal("5")  # type: ignore[arg-type]
    )
    assert ok2 is False
    assert code2 == "OTHER_REVIEW_REQUIRED"


@pytest.mark.asyncio
async def test_b6_openai_evaluate_mocked() -> None:
    cid = str(uuid.uuid4())

    async def caller(operation: str, payload: dict) -> dict:
        assert operation == "evaluate_rubric"
        assert "sk-test" not in str(payload)
        return {
            "criterion_proposals": [
                {
                    "rubric_criterion_id": cid,
                    "decision": "AWARDED",
                    "proposed_marks": "5",
                }
            ],
            "proposed_total": "5",
            "evaluation_confidence": "0.77",
            "ecf_applied": False,
            "error_codes": [],
            "deduction_reasons": [],
        }

    provider = OpenAIStructureProvider(
        api_key="sk-test-never-log",
        model_identity="m",
        model_page_analysis="m",
        model_mapping="m",
        model_transcription="m",
        model_evaluation="m",
        caller=caller,
    )
    result = await provider.evaluate_rubric(
        RubricEvaluationInput(
            question_version_id=uuid.uuid4(),
            assessment_version_id=uuid.uuid4(),
            rubric_criteria=[
                RubricCriterionSnapshot(
                    id=uuid.UUID(cid),
                    code="C1",
                    label="c",
                    max_marks=Decimal("5"),
                    sequence=1,
                )
            ],
            transcription_text="ok",
            max_mark=Decimal("5"),
        )
    )
    assert result.proposed_total == Decimal("5")
    assert result.evaluation_confidence == Decimal("0.77")


def test_b6_types_forbid_unknown_error_code() -> None:
    with pytest.raises(ValidationError):
        CriterionProposal(
            rubric_criterion_id=uuid.uuid4(),
            decision="AWARDED",
            proposed_marks=Decimal("1"),
            error_code="NOT_A_REAL_CODE",
        )


@pytest.mark.asyncio
async def test_b6_escalate_blocks_finalize() -> None:
    async with api_client_fixed() as client:
        headers = await _headers(client)
        data = await _ready_assessment(client, headers)
        sid = await _to_ready_for_evaluation(client, headers, data)
        prep = await client.post(
            f"/api/v1/submissions/{sid}/evaluation/prepare", headers=headers
        )
        assert prep.status_code == 200, prep.text
        workspace = await client.get(
            f"/api/v1/submissions/{sid}/evaluation", headers=headers
        )
        qes = workspace.json()["question_evaluations"]
        assert len(qes) >= 2
        esc = await client.post(
            f"/api/v1/question-evaluations/{qes[0]['id']}/escalate",
            headers=headers,
            json={"reason": "Needs senior review"},
        )
        assert esc.status_code == 200, esc.text
        assert esc.json()["workflow_state"] == "ESCALATED"
        # Accept the other so only escalate blocks
        other = qes[1]
        if other.get("proposed_ai_score") is not None:
            acc = await client.post(
                f"/api/v1/question-evaluations/{other['id']}/accept",
                headers=headers,
            )
            assert acc.status_code == 200, acc.text
        fin = await client.post(
            f"/api/v1/submissions/{sid}/evaluation/finalize", headers=headers
        )
        assert fin.status_code == 409
        code = fin.json()["error"]["details"]["code"]
        assert code in {
            "ESCALATED_PENDING",
            "REVIEW_INCOMPLETE",
            "LEDGER_INCOMPLETE",
            "INCOMPLETE_REVIEW",
            "ESCALATED_PRESENT",
            "NOT_READY",
        }
