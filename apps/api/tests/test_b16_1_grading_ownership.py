"""B16.1 Blocker A — grading ownership on authoritative B6 review mutations."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.core.authorization import ROLE_PERMISSION_MAP, AuthContext
from app.core.config import get_settings
from app.core.security import JwtAuthProvider
from tests.test_b3_submission_ingestion import _headers
from tests.test_b6_evaluation_ledger import _ready_assessment, _to_ready_for_evaluation
from tests.test_b7_publication_reports import api_client_publication
from tests.test_b16_enterprise_ops import (
    _auth_context,
    _create_role_user,
    _detail_code,
)


async def _pool_with_two_evaluators(
    client: AsyncClient,
    headers: dict[str, str],
    data: dict,
    *,
    tenant_id: uuid.UUID,
) -> tuple[str, uuid.UUID, dict[str, str], uuid.UUID, dict[str, str]]:
    eval_a_id, eval_a_headers = await _create_role_user(
        tenant_id=tenant_id, role_code="EVALUATOR", email_prefix="own-a"
    )
    eval_b_id, eval_b_headers = await _create_role_user(
        tenant_id=tenant_id, role_code="EVALUATOR", email_prefix="own-b"
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
    pool_id = pool.json()["id"]
    for uid in (eval_a_id, eval_b_id):
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
    return pool_id, eval_a_id, eval_a_headers, eval_b_id, eval_b_headers


async def _allocate_run(
    client: AsyncClient, headers: dict[str, str], pool_id: str, data: dict
) -> tuple[str, list[dict]]:
    sid = await _to_ready_for_evaluation(client, headers, data)
    prep = await client.post(
        f"/api/v1/submissions/{sid}/evaluation/prepare", headers=headers
    )
    assert prep.status_code == 200, prep.text
    workspace = await client.get(
        f"/api/v1/submissions/{sid}/evaluation", headers=headers
    )
    assert workspace.status_code == 200, workspace.text
    run_id = workspace.json()["evaluation_run"]["id"]
    alloc = await client.post(
        f"/api/v1/operations/grading-pools/{pool_id}/allocate",
        headers=headers,
        json={"evaluation_run_id": run_id},
    )
    assert alloc.status_code == 200, alloc.text
    items = alloc.json()["items"]
    assert len(items) >= 2
    return sid, items


@pytest.mark.asyncio
async def test_b16_1_assigned_evaluator_can_review_own_qe() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment(client, headers)
        ctx = await _auth_context(headers)
        pool_id, eval_a_id, eval_a_headers, eval_b_id, eval_b_headers = (
            await _pool_with_two_evaluators(
                client, headers, data, tenant_id=ctx.tenant_id
            )
        )
        _sid, items = await _allocate_run(client, headers, pool_id, data)

        a_item = next(i for i in items if i["assigned_evaluator_id"] == str(eval_a_id))
        b_item = next(i for i in items if i["assigned_evaluator_id"] == str(eval_b_id))

        start_a = await client.post(
            f"/api/v1/operations/grading/work-items/{a_item['id']}/start",
            headers=eval_a_headers,
        )
        assert start_a.status_code == 200, start_a.text

        accept_a = await client.post(
            f"/api/v1/question-evaluations/{a_item['question_evaluation_id']}/accept",
            headers=eval_a_headers,
        )
        assert accept_a.status_code == 200, accept_a.text
        assert accept_a.json()["workflow_state"] == "ACCEPTED"

        # Feedback on own assignment
        fb = await client.post(
            f"/api/v1/question-evaluations/{a_item['question_evaluation_id']}/feedback",
            headers=eval_a_headers,
            json={"feedback": "Looks correct after review"},
        )
        assert fb.status_code == 200, fb.text

        # Escalation path on a fresh QE owned by B — first prove B can escalate own
        start_b = await client.post(
            f"/api/v1/operations/grading/work-items/{b_item['id']}/start",
            headers=eval_b_headers,
        )
        assert start_b.status_code == 200, start_b.text
        esc = await client.post(
            f"/api/v1/question-evaluations/{b_item['question_evaluation_id']}/escalate",
            headers=eval_b_headers,
            json={"reason": "Needs second opinion"},
        )
        assert esc.status_code == 200, esc.text
        assert esc.json()["workflow_state"] == "ESCALATED"


@pytest.mark.asyncio
async def test_b16_1_cross_assignment_b6_accept_and_override_forbidden() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment(client, headers)
        ctx = await _auth_context(headers)
        pool_id, eval_a_id, eval_a_headers, eval_b_id, _eval_b_headers = (
            await _pool_with_two_evaluators(
                client, headers, data, tenant_id=ctx.tenant_id
            )
        )
        _sid, items = await _allocate_run(client, headers, pool_id, data)
        b_item = next(i for i in items if i["assigned_evaluator_id"] == str(eval_b_id))
        qe_b = b_item["question_evaluation_id"]

        # Critical: direct B6 endpoint, not grading work-item API
        bypass_accept = await client.post(
            f"/api/v1/question-evaluations/{qe_b}/accept",
            headers=eval_a_headers,
        )
        assert bypass_accept.status_code == 403, bypass_accept.text
        assert _detail_code(bypass_accept) == "GRADING_ASSIGNMENT_FORBIDDEN"

        bypass_override = await client.post(
            f"/api/v1/question-evaluations/{qe_b}/override",
            headers=eval_a_headers,
            json={"score": "1.00", "reason": "Cross-assignment bypass attempt"},
        )
        assert bypass_override.status_code == 403, bypass_override.text
        assert _detail_code(bypass_override) == "GRADING_ASSIGNMENT_FORBIDDEN"

        bypass_feedback = await client.post(
            f"/api/v1/question-evaluations/{qe_b}/feedback",
            headers=eval_a_headers,
            json={"feedback": "Should not land"},
        )
        assert bypass_feedback.status_code == 403, bypass_feedback.text
        assert _detail_code(bypass_feedback) == "GRADING_ASSIGNMENT_FORBIDDEN"

        bypass_escalate = await client.post(
            f"/api/v1/question-evaluations/{qe_b}/escalate",
            headers=eval_a_headers,
            json={"reason": "Should not escalate"},
        )
        assert bypass_escalate.status_code == 403, bypass_escalate.text
        assert _detail_code(bypass_escalate) == "GRADING_ASSIGNMENT_FORBIDDEN"

        # Ordinary teacher (evaluation:review + grading:manage) is not governance override
        _teacher_id, teacher_headers = await _create_role_user(
            tenant_id=ctx.tenant_id, role_code="TEACHER", email_prefix="teach-bypass"
        )
        teacher_bypass = await client.post(
            f"/api/v1/question-evaluations/{qe_b}/accept",
            headers=teacher_headers,
        )
        assert teacher_bypass.status_code == 403, teacher_bypass.text
        assert _detail_code(teacher_bypass) == "GRADING_ASSIGNMENT_FORBIDDEN"

        assert eval_a_id != eval_b_id


@pytest.mark.asyncio
async def test_b16_1_governance_override_and_legacy_and_tenant() -> None:
    async with api_client_publication() as client:
        headers = await _headers(client)
        data = await _ready_assessment(client, headers)
        ctx = await _auth_context(headers)
        pool_id, _eval_a_id, _eval_a_headers, eval_b_id, _eval_b_headers = (
            await _pool_with_two_evaluators(
                client, headers, data, tenant_id=ctx.tenant_id
            )
        )
        _sid, items = await _allocate_run(client, headers, pool_id, data)
        b_item = next(i for i in items if i["assigned_evaluator_id"] == str(eval_b_id))
        qe_b = b_item["question_evaluation_id"]

        # INSTITUTION_ADMIN has grading governance role + grading:manage
        gov_accept = await client.post(
            f"/api/v1/question-evaluations/{qe_b}/accept",
            headers=headers,
        )
        assert gov_accept.status_code == 200, gov_accept.text
        assert gov_accept.json()["workflow_state"] == "ACCEPTED"

        # HOD with grading:manage can also override a different QE on a fresh run
        data2 = await _ready_assessment(client, headers)
        pool2, _a2, _ah2, b2_id, _bh2 = await _pool_with_two_evaluators(
            client, headers, data2, tenant_id=ctx.tenant_id
        )
        _sid2, items2 = await _allocate_run(client, headers, pool2, data2)
        qe2 = next(i for i in items2 if i["assigned_evaluator_id"] == str(b2_id))[
            "question_evaluation_id"
        ]
        _hod_id, hod_headers = await _create_role_user(
            tenant_id=ctx.tenant_id, role_code="HOD", email_prefix="hod-gov"
        )
        hod_override = await client.post(
            f"/api/v1/question-evaluations/{qe2}/override",
            headers=hod_headers,
            json={"score": "2.00", "reason": "Governance correction"},
        )
        assert hod_override.status_code == 200, hod_override.text
        assert hod_override.json()["workflow_state"] == "OVERRIDDEN"

        # Legacy path: no governing work item → original B6 permissions apply
        data3 = await _ready_assessment(client, headers)
        sid3 = await _to_ready_for_evaluation(client, headers, data3)
        prep3 = await client.post(
            f"/api/v1/submissions/{sid3}/evaluation/prepare", headers=headers
        )
        assert prep3.status_code == 200, prep3.text
        workspace3 = await client.get(
            f"/api/v1/submissions/{sid3}/evaluation", headers=headers
        )
        qe_legacy = workspace3.json()["question_evaluations"][0]["id"]
        legacy_accept = await client.post(
            f"/api/v1/question-evaluations/{qe_legacy}/accept",
            headers=headers,
        )
        assert legacy_accept.status_code == 200, legacy_accept.text

        # Tenant isolation: foreign tenant cannot discover the QE
        foreign_token, _ = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                roles=frozenset({"INSTITUTION_ADMIN"}),
                permissions=ROLE_PERMISSION_MAP["INSTITUTION_ADMIN"],
            )
        )
        foreign_headers = {"Authorization": f"Bearer {foreign_token}"}
        foreign = await client.post(
            f"/api/v1/question-evaluations/{qe_b}/accept",
            headers=foreign_headers,
        )
        assert foreign.status_code == 404, foreign.text
        assert _detail_code(foreign) == "NOT_FOUND"
