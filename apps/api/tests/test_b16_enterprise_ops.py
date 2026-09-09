"""B16 enterprise grading, moderation, and grievance coverage."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.authorization import ROLE_PERMISSION_MAP, AuthContext
from app.core.config import get_settings
from app.core.security import JwtAuthProvider, hash_password
from app.db.models import (
    EvaluationRun,
    QuestionEvaluation,
    ReviewAction,
    Role,
    User,
    UserRole,
)
from app.db.session import async_session_factory
from tests.test_b3_submission_ingestion import _headers
from tests.test_b6_evaluation_ledger import _ready_assessment, _to_ready_for_evaluation
from tests.test_b7_publication_reports import _to_approved, api_client_publication


def _detail_code(resp) -> str | None:
    body = resp.json()
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("code")
    err = body.get("error")
    if isinstance(err, dict):
        return err.get("code")
    return None


async def _auth_context(headers: dict[str, str]) -> AuthContext:
    token = headers["Authorization"].removeprefix("Bearer ").strip()
    return JwtAuthProvider(get_settings()).verify_access_token(token)


async def _create_role_user(
    *,
    tenant_id: uuid.UUID,
    role_code: str,
    email_prefix: str,
) -> tuple[uuid.UUID, dict[str, str]]:
    suffix = uuid.uuid4().hex[:8]
    async with async_session_factory() as db:
        role = await db.scalar(
            select(Role).where(Role.tenant_id == tenant_id, Role.code == role_code)
        )
        assert role is not None, role_code
        user = User(
            tenant_id=tenant_id,
            email=f"{email_prefix}-{suffix}@demo.eduvijna.local",
            display_name=f"{role_code} {suffix}",
            password_hash=hash_password("DemoUser!2026"),
        )
        db.add(user)
        await db.flush()
        db.add(
            UserRole(
                tenant_id=tenant_id,
                user_id=user.id,
                role_id=role.id,
            )
        )
        await db.commit()
        user_id = user.id

    token, _ = JwtAuthProvider(get_settings()).issue_access_token(
        AuthContext(
            user_id=user_id,
            tenant_id=tenant_id,
            roles=frozenset({role_code}),
            permissions=ROLE_PERMISSION_MAP.get(role_code, frozenset()),
        )
    )
    return user_id, {"Authorization": f"Bearer {token}"}


async def _publish(client: AsyncClient, headers: dict[str, str], sid: str) -> str:
    prep = await client.post(
        f"/api/v1/submissions/{sid}/publication/prepare", headers=headers
    )
    assert prep.status_code == 200, prep.text
    prid = prep.json()["published_result_id"]
    pub = await client.post(
        f"/api/v1/publication-results/{prid}/publish", headers=headers
    )
    assert pub.status_code == 200, pub.text
    assert pub.json()["status"] == "PUBLISHED"
    return prid


async def _review_all_and_finalize(
    client: AsyncClient, headers: dict[str, str], sid: str
) -> dict:
    workspace = await client.get(
        f"/api/v1/submissions/{sid}/evaluation", headers=headers
    )
    assert workspace.status_code == 200, workspace.text
    for qe in workspace.json()["question_evaluations"]:
        if qe["workflow_state"] in {"ACCEPTED", "OVERRIDDEN"}:
            continue
        acc = await client.post(
            f"/api/v1/question-evaluations/{qe['id']}/accept", headers=headers
        )
        assert acc.status_code == 200, acc.text
    fin = await client.post(
        f"/api/v1/submissions/{sid}/evaluation/finalize", headers=headers
    )
    assert fin.status_code == 200, fin.text
    return fin.json()


async def _activate_moderation_policy(
    client: AsyncClient,
    headers: dict[str, str],
    data: dict,
    *,
    stages: list[dict] | None = None,
) -> str:
    stages = stages or [
        {"stage_order": 1, "required_role": "MODERATOR", "label": "Moderator"},
        {"stage_order": 2, "required_role": "HOD", "label": "HOD"},
    ]
    created = await client.post(
        "/api/v1/operations/moderation-policies",
        headers=headers,
        json={
            "assessment_id": data["assessment"]["id"],
            "assessment_version_id": data["version_id"],
            "stages": stages,
        },
    )
    assert created.status_code == 200, created.text
    policy_id = created.json()["id"]
    activated = await client.post(
        f"/api/v1/operations/moderation-policies/{policy_id}/activate",
        headers=headers,
    )
    assert activated.status_code == 200, activated.text
    return policy_id


@pytest.mark.asyncio
async def test_b16_pool_lifecycle_invalid_member_allocate_progress() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment(client, headers)
        ctx = await _auth_context(headers)
        eval_id, eval_headers = await _create_role_user(
            tenant_id=ctx.tenant_id, role_code="EVALUATOR", email_prefix="eval"
        )

        pool = await client.post(
            "/api/v1/operations/grading-pools",
            headers=headers,
            json={
                "assessment_id": data["assessment"]["id"],
                "assessment_version_id": data["version_id"],
                "allocation_strategy": "ROUND_ROBIN",
            },
        )
        assert pool.status_code == 200, pool.text
        assert pool.json()["status"] == "DRAFT"
        pool_id = pool.json()["id"]

        async with async_session_factory() as db:
            student_role = await db.scalar(
                select(Role).where(
                    Role.tenant_id == ctx.tenant_id, Role.code == "STUDENT"
                )
            )
            assert student_role is not None
            student = User(
                tenant_id=ctx.tenant_id,
                email=f"student-{uuid.uuid4().hex[:8]}@demo.local",
                display_name="Student",
                password_hash=hash_password("x"),
            )
            db.add(student)
            await db.flush()
            db.add(
                UserRole(
                    tenant_id=ctx.tenant_id,
                    user_id=student.id,
                    role_id=student_role.id,
                )
            )
            await db.commit()
            student_id = student.id

        bad_member = await client.post(
            f"/api/v1/operations/grading-pools/{pool_id}/members",
            headers=headers,
            json={"user_id": str(student_id)},
        )
        assert bad_member.status_code in {400, 409}, bad_member.text
        assert _detail_code(bad_member) == "INVALID_MEMBER_ROLE"

        for uid in (ctx.user_id, eval_id):
            mem = await client.post(
                f"/api/v1/operations/grading-pools/{pool_id}/members",
                headers=headers,
                json={"user_id": str(uid)},
            )
            assert mem.status_code == 200, mem.text

        act = await client.post(
            f"/api/v1/operations/grading-pools/{pool_id}/activate", headers=headers
        )
        assert act.status_code == 200, act.text
        assert act.json()["status"] == "ACTIVE"

        sid = await _to_ready_for_evaluation(client, headers, data)
        prep = await client.post(
            f"/api/v1/submissions/{sid}/evaluation/prepare", headers=headers
        )
        assert prep.status_code == 200, prep.text
        workspace = await client.get(
            f"/api/v1/submissions/{sid}/evaluation", headers=headers
        )
        run_id = workspace.json()["evaluation_run"]["id"]

        alloc1 = await client.post(
            f"/api/v1/operations/grading-pools/{pool_id}/allocate",
            headers=headers,
            json={"evaluation_run_id": run_id},
        )
        assert alloc1.status_code == 200, alloc1.text
        items1 = alloc1.json()["items"]
        assert len(items1) >= 1

        alloc2 = await client.post(
            f"/api/v1/operations/grading-pools/{pool_id}/allocate",
            headers=headers,
            json={"evaluation_run_id": run_id},
        )
        assert alloc2.status_code == 200, alloc2.text
        assert alloc2.json()["items"] == []

        progress = await client.get(
            f"/api/v1/operations/grading-pools/{pool_id}/progress", headers=headers
        )
        assert progress.status_code == 200, progress.text
        assert progress.json()["counts"]["QUEUED"] == len(items1)

        my_queue = await client.get(
            "/api/v1/operations/grading/my-queue", headers=eval_headers
        )
        assert my_queue.status_code == 200, my_queue.text
        eval_items = my_queue.json()["items"]
        assert eval_items

        foreign_item = next(
            i for i in items1 if i["assigned_evaluator_id"] != str(eval_id)
        )
        blocked = await client.post(
            f"/api/v1/operations/grading/work-items/{foreign_item['id']}/start",
            headers=eval_headers,
        )
        assert blocked.status_code == 409, blocked.text
        assert _detail_code(blocked) == "FORBIDDEN"

        own = eval_items[0]
        started = await client.post(
            f"/api/v1/operations/grading/work-items/{own['id']}/start",
            headers=eval_headers,
        )
        assert started.status_code == 200, started.text
        assert started.json()["status"] == "IN_PROGRESS"

        closed = await client.post(
            f"/api/v1/operations/grading-pools/{pool_id}/close", headers=headers
        )
        assert closed.status_code == 200, closed.text
        assert closed.json()["status"] == "CLOSED"


@pytest.mark.asyncio
async def test_b16_moderation_multi_stage_separation_return_legacy() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment(client, headers)
        ctx = await _auth_context(headers)
        _mod_id, mod_headers = await _create_role_user(
            tenant_id=ctx.tenant_id, role_code="MODERATOR", email_prefix="mod"
        )
        _hod_id, hod_headers = await _create_role_user(
            tenant_id=ctx.tenant_id, role_code="HOD", email_prefix="hod"
        )

        await _activate_moderation_policy(client, headers, data)

        sid = await _to_ready_for_evaluation(client, headers, data)
        prep = await client.post(
            f"/api/v1/submissions/{sid}/evaluation/prepare", headers=headers
        )
        assert prep.status_code == 200, prep.text
        workspace = await client.get(
            f"/api/v1/submissions/{sid}/evaluation", headers=headers
        )
        for qe in workspace.json()["question_evaluations"]:
            acc = await client.post(
                f"/api/v1/question-evaluations/{qe['id']}/accept", headers=headers
            )
            assert acc.status_code == 200, acc.text

        async with async_session_factory() as db:
            review_count_before = await db.scalar(
                select(func.count())
                .select_from(ReviewAction)
                .where(ReviewAction.submission_id == uuid.UUID(sid))
            )

        fin = await client.post(
            f"/api/v1/submissions/{sid}/evaluation/finalize", headers=headers
        )
        assert fin.status_code == 200, fin.text
        assert fin.json()["workflow_state"] == "MODERATION_REVIEW"

        cases = await client.get("/api/v1/operations/moderation-cases", headers=headers)
        assert cases.status_code == 200, cases.text
        case = next(c for c in cases.json()["items"] if c["submission_id"] == sid)
        case_id = case["id"]

        self_token = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=ctx.user_id,
                tenant_id=ctx.tenant_id,
                roles=frozenset({"INSTITUTION_ADMIN", "MODERATOR"}),
                permissions=ROLE_PERMISSION_MAP["INSTITUTION_ADMIN"],
            )
        )[0]
        self_headers = {"Authorization": f"Bearer {self_token}"}
        blocked = await client.post(
            f"/api/v1/operations/moderation-cases/{case_id}/decide",
            headers=self_headers,
            json={"decision": "APPROVE"},
        )
        assert blocked.status_code == 409, blocked.text
        assert _detail_code(blocked) == "SEPARATION_OF_DUTIES"

        returned = await client.post(
            f"/api/v1/operations/moderation-cases/{case_id}/decide",
            headers=mod_headers,
            json={"decision": "RETURN", "reason": "Please recheck Q1"},
        )
        assert returned.status_code == 200, returned.text
        assert returned.json()["status"] == "RETURNED"

        async with async_session_factory() as db:
            review_count_after = await db.scalar(
                select(func.count())
                .select_from(ReviewAction)
                .where(ReviewAction.submission_id == uuid.UUID(sid))
            )
            assert review_count_after == review_count_before

        sub = await client.get(f"/api/v1/submissions/{sid}", headers=headers)
        assert sub.json()["workflow_state"] == "EVALUATION_REVIEW"
        fin2 = await client.post(
            f"/api/v1/submissions/{sid}/evaluation/finalize", headers=headers
        )
        assert fin2.status_code == 200, fin2.text
        assert fin2.json()["workflow_state"] == "MODERATION_REVIEW"

        case_get = await client.get(
            f"/api/v1/operations/moderation-cases/{case_id}", headers=headers
        )
        assert case_get.status_code == 200, case_get.text
        assert case_get.json()["status"] == "PENDING"

        s1 = await client.post(
            f"/api/v1/operations/moderation-cases/{case_id}/decide",
            headers=mod_headers,
            json={"decision": "APPROVE"},
        )
        assert s1.status_code == 200, s1.text
        assert s1.json()["status"] == "PENDING"
        assert s1.json()["current_stage_order"] == 2

        s2 = await client.post(
            f"/api/v1/operations/moderation-cases/{case_id}/decide",
            headers=hod_headers,
            json={"decision": "APPROVE"},
        )
        assert s2.status_code == 200, s2.text
        assert s2.json()["status"] == "APPROVED"
        sub3 = await client.get(f"/api/v1/submissions/{sid}", headers=headers)
        assert sub3.json()["workflow_state"] == "APPROVED"

        data2 = await _ready_assessment(client, headers)
        sid2, _ = await _to_approved(client, headers, data2)
        sub2 = await client.get(f"/api/v1/submissions/{sid2}", headers=headers)
        assert sub2.json()["workflow_state"] == "APPROVED"


@pytest.mark.asyncio
async def test_b16_grievance_accept_reject_supersede_analytics_tenant() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment(client, headers)
        sid, student_id = await _to_approved(client, headers, data)
        original_prid = await _publish(client, headers, sid)

        async with async_session_factory() as db:
            original_run = await db.scalar(
                select(EvaluationRun)
                .where(EvaluationRun.submission_id == uuid.UUID(sid))
                .order_by(EvaluationRun.run_number.desc())
            )
            assert original_run is not None
            original_run_id = original_run.id
            original_run_number = original_run.run_number
            original_qes = list(
                (
                    await db.scalars(
                        select(QuestionEvaluation).where(
                            QuestionEvaluation.evaluation_run_id == original_run.id
                        )
                    )
                ).all()
            )
            original_qe_snapshot = [
                (
                    q.id,
                    q.final_human_approved_score,
                    q.reviewed_by,
                    q.approved_snapshot_hash,
                )
                for q in original_qes
            ]

        g_reject = await client.post(
            "/api/v1/operations/grievances",
            headers=headers,
            json={
                "published_result_id": original_prid,
                "requester_reference": "parent-ref-1",
                "reason": "Marking dispute",
            },
        )
        assert g_reject.status_code == 200, g_reject.text
        reject_id = g_reject.json()["id"]
        rejected = await client.post(
            f"/api/v1/operations/grievances/{reject_id}/reject",
            headers=headers,
            json={"decision_reason": "Out of window"},
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["status"] == "REJECTED"

        async with async_session_factory() as db:
            for qid, score, reviewed_by, snap in original_qe_snapshot:
                qe = await db.get(QuestionEvaluation, qid)
                assert qe is not None
                assert qe.final_human_approved_score == score
                assert qe.reviewed_by == reviewed_by
                assert qe.approved_snapshot_hash == snap
            run = await db.get(EvaluationRun, original_run_id)
            assert run is not None
            assert run.run_number == original_run_number
            assert run.status == "COMPLETED"

        g_accept = await client.post(
            "/api/v1/operations/grievances",
            headers=headers,
            json={
                "published_result_id": original_prid,
                "requester_reference": "parent-ref-2",
                "reason": "Request recheck",
            },
        )
        assert g_accept.status_code == 200, g_accept.text
        accept_id = g_accept.json()["id"]
        accepted = await client.post(
            f"/api/v1/operations/grievances/{accept_id}/accept",
            headers=headers,
            json={"decision_reason": "Valid concern"},
        )
        assert accepted.status_code == 200, accepted.text
        body = accepted.json()
        assert body["status"] == "RE_EVALUATING"
        assert body["reevaluation_run_id"]
        new_run_id = uuid.UUID(body["reevaluation_run_id"])

        async with async_session_factory() as db:
            new_run = await db.get(EvaluationRun, new_run_id)
            assert new_run is not None
            assert new_run.run_number == original_run_number + 1
            assert new_run.run_kind == "RE_EVALUATION"
            assert new_run.supersedes_run_id == original_run_id
            assert str(new_run.grievance_case_id) == accept_id

            orig = await db.get(EvaluationRun, original_run_id)
            assert orig is not None
            assert orig.run_number == original_run_number
            assert orig.status == "SUPERSEDED"
            for qid, score, reviewed_by, snap in original_qe_snapshot:
                qe = await db.get(QuestionEvaluation, qid)
                assert qe is not None
                assert qe.final_human_approved_score == score
                assert qe.reviewed_by == reviewed_by
                assert qe.approved_snapshot_hash == snap

            new_qes = list(
                (
                    await db.scalars(
                        select(QuestionEvaluation).where(
                            QuestionEvaluation.evaluation_run_id == new_run_id
                        )
                    )
                ).all()
            )
            assert len(new_qes) == len(original_qe_snapshot)
            for qe in new_qes:
                assert qe.final_human_approved_score is None
                assert qe.reviewed_by is None
                assert qe.reviewed_at is None
                assert qe.approved_snapshot_hash is None

        fin = await _review_all_and_finalize(client, headers, sid)
        assert fin["workflow_state"] == "APPROVED"
        new_prid = await _publish(client, headers, sid)

        workspace = await client.get(
            f"/api/v1/submissions/{sid}/publication", headers=headers
        )
        assert workspace.status_code == 200, workspace.text
        latest = workspace.json()["latest"]
        assert latest["id"] == new_prid
        assert latest["status"] == "PUBLISHED"
        assert latest.get("supersedes_result_id") == original_prid

        async with async_session_factory() as db:
            from app.db.models import PublishedResult

            prior = await db.get(PublishedResult, uuid.UUID(original_prid))
            assert prior is not None
            assert prior.status == "SUPERSEDED"
            current = await db.get(PublishedResult, uuid.UUID(new_prid))
            assert current is not None
            assert current.status == "PUBLISHED"

        analytics = await client.get(
            f"/api/v1/analytics/assessments/{data['assessment']['id']}",
            headers=headers,
        )
        assert analytics.status_code == 200, analytics.text
        assert analytics.json()["published_attempt_count"] == 1

        student_analytics = await client.get(
            f"/api/v1/analytics/students/{student_id}",
            headers=headers,
        )
        assert student_analytics.status_code == 200, student_analytics.text
        assert student_analytics.json()["published_attempt_count"] == 1

        foreign = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                roles=frozenset({"INSTITUTION_ADMIN"}),
                permissions=ROLE_PERMISSION_MAP["INSTITUTION_ADMIN"],
            )
        )[0]
        foreign_headers = {"Authorization": f"Bearer {foreign}"}
        for path in (
            f"/api/v1/operations/grading-pools/{uuid.uuid4()}",
            f"/api/v1/operations/moderation-cases/{uuid.uuid4()}",
            f"/api/v1/operations/grievances/{accept_id}",
        ):
            resp = await client.get(path, headers=foreign_headers)
            assert resp.status_code == 404, path
