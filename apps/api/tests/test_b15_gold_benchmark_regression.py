"""B15 gold benchmark + AI regression coverage (PEV-058/059)."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.ai.providers.benchmark import (
    MODEL_INVALID,
    MODEL_PASS,
    MODEL_REGRESS,
    FixedBenchmarkProvider,
)
from app.core.authorization import AuthContext
from app.core.config import get_settings
from app.core.security import JwtAuthProvider
from app.db.models import (
    AuditEvent,
    MasteryEvidence,
    PublishedResult,
    QuestionEvaluation,
    Tenant,
)
from app.db.session import async_session_factory
from app.services.benchmark import (
    B15_DEFAULT_THRESHOLDS,
    aggregate_regression_metrics,
    compare_case_output,
    evaluate_release_gate,
)
from tests.test_b3_submission_ingestion import _headers
from tests.test_b7_publication_reports import _to_approved, api_client_publication
from tests.test_b8_analytics_mastery import (
    _publish_approved,
    _ready_assessment_with_curriculum,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "b15" / "synthetic_gold_case.json"


def test_b15_default_thresholds_documented() -> None:
    assert B15_DEFAULT_THRESHOLDS["profile_code"] == "B15_DEFAULT_V1"
    assert B15_DEFAULT_THRESHOLDS["algorithm_version"] == "B15_V1"
    assert B15_DEFAULT_THRESHOLDS["max_missing_output_rate"] == 0.0
    assert B15_DEFAULT_THRESHOLDS["min_exact_score_agreement_rate"] == 1.0


def test_b15_metric_aggregation_unit() -> None:
    """Pure unit tests for missing / score / taxonomy / safety metric math."""
    empty = aggregate_regression_metrics([])
    assert empty["passed"] is False
    assert empty["verdict"] == "FAIL"
    assert empty["missing_output_rate"] == 1.0

    missing_row = compare_case_output(
        expected_final_marks=Decimal("3"),
        expected_max_marks=Decimal("5"),
        expected_error_codes=["E1"],
        actual_marks=None,
        actual_error_codes=None,
        missing_output=True,
    )
    missing_agg = aggregate_regression_metrics([missing_row])
    assert missing_agg["missing_output_rate"] == 1.0
    assert missing_agg["mean_abs_score_error"] == 0.0
    assert missing_agg["passed"] is False

    mismatch = compare_case_output(
        expected_final_marks=Decimal("3"),
        expected_max_marks=Decimal("5"),
        expected_error_codes=["E1"],
        actual_marks=Decimal("4"),
        actual_error_codes=["E2"],
        missing_output=False,
    )
    assert mismatch["exact_score_match"] is False
    assert mismatch["taxonomy_match"] is False
    assert mismatch["score_abs_error"] == Decimal("1")
    score_agg = aggregate_regression_metrics([mismatch])
    assert score_agg["exact_score_agreement_rate"] == 0.0
    assert score_agg["taxonomy_agreement_rate"] == 0.0
    assert score_agg["passed"] is False

    safety = compare_case_output(
        expected_final_marks=Decimal("3"),
        expected_max_marks=Decimal("5"),
        expected_error_codes=["E1"],
        actual_marks=Decimal("6"),
        actual_error_codes=["E1"],
        missing_output=False,
    )
    assert safety["safety_invariant_failed"] is True
    safety_agg = aggregate_regression_metrics([safety])
    assert safety_agg["safety_invariant_failure_rate"] == 1.0
    assert safety_agg["passed"] is False

    pass_row = compare_case_output(
        expected_final_marks=Decimal("3.5"),
        expected_max_marks=Decimal("5"),
        expected_error_codes=["E1"],
        actual_marks=Decimal("3.5"),
        actual_error_codes=["E1"],
        missing_output=False,
    )
    pass_agg = aggregate_regression_metrics([pass_row])
    assert pass_agg["passed"] is True
    assert pass_agg["verdict"] == "PASS"
    assert pass_agg["taxonomy_agreement_rate"] == 1.0

    # taxonomy applicable = 0 → rate 1.0
    no_tax = {
        "missing_output": False,
        "score_abs_error": Decimal("0"),
        "exact_score_match": True,
        "taxonomy_match": None,
        "safety_invariant_failed": False,
    }
    tax_agg = aggregate_regression_metrics([no_tax])
    assert tax_agg["taxonomy_agreement_rate"] == 1.0
    assert tax_agg["taxonomy_applicable_count"] == 0


def test_b15_fixed_provider_models_and_fixture() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    case = payload["cases"][0]
    fixture = case["replay_fixture"]
    expected = Decimal(case["expected_final_marks"])
    max_marks = Decimal(case["expected_max_marks"])
    codes = list(case["expected_error_codes"])

    passed = FixedBenchmarkProvider(model=MODEL_PASS).evaluate_gold_case(
        fixture,
        expected_final_marks=expected,
        expected_max_marks=max_marks,
        expected_error_codes=codes,
    )
    assert passed.marks == expected
    assert passed.error_codes == codes

    regress = FixedBenchmarkProvider(model=MODEL_REGRESS).evaluate_gold_case(
        fixture,
        expected_final_marks=expected,
        expected_max_marks=max_marks,
        expected_error_codes=codes,
    )
    assert regress.marks != expected
    assert regress.error_codes != codes

    invalid = FixedBenchmarkProvider(model=MODEL_INVALID).evaluate_gold_case(
        fixture,
        expected_final_marks=expected,
        expected_max_marks=max_marks,
        expected_error_codes=codes,
    )
    assert invalid.marks is not None and invalid.marks > max_marks


async def _eligible_qe(
    client, headers: dict[str, str], published_result_id: str
) -> dict:
    async with async_session_factory() as db:
        pr = await db.scalar(
            select(PublishedResult).where(
                PublishedResult.id == uuid.UUID(published_result_id)
            )
        )
        assert pr is not None
        qe = await db.scalar(
            select(QuestionEvaluation)
            .where(
                QuestionEvaluation.evaluation_run_id == pr.evaluation_run_id,
                QuestionEvaluation.workflow_state.in_(["ACCEPTED", "OVERRIDDEN"]),
                QuestionEvaluation.final_human_approved_score.is_not(None),
            )
            .limit(1)
        )
        assert qe is not None
        return {
            "published_result_id": str(pr.id),
            "question_evaluation_id": str(qe.id),
            "expected_final_marks": float(qe.final_human_approved_score),
            "expected_max_marks": float(qe.max_mark),
            "expected_error_codes": list(qe.error_codes or []),
        }


async def _create_locked_version(
    client, headers: dict[str, str], *, code: str
) -> dict:
    data = await _ready_assessment_with_curriculum(client, headers)
    sid, _student_id = await _to_approved(client, headers, data)
    prid = await _publish_approved(client, headers, sid)
    gold = await _eligible_qe(client, headers, prid)

    ds = await client.post(
        "/api/v1/quality/benchmark-datasets",
        headers=headers,
        json={"code": code, "title": f"Gold {code}", "description": "B15"},
    )
    assert ds.status_code == 200, ds.text
    dataset = ds.json()

    ver = await client.post(
        f"/api/v1/quality/benchmark-datasets/{dataset['id']}/versions",
        headers=headers,
        json={},
    )
    assert ver.status_code == 200, ver.text
    version = ver.json()
    assert version["status"] == "DRAFT"
    assert version["threshold_profile_snapshot"]["profile_code"] == "B15_DEFAULT_V1"

    case = await client.post(
        f"/api/v1/quality/benchmark-versions/{version['id']}/cases",
        headers=headers,
        json={
            "published_result_id": gold["published_result_id"],
            "question_evaluation_id": gold["question_evaluation_id"],
        },
    )
    assert case.status_code == 200, case.text

    locked = await client.post(
        f"/api/v1/quality/benchmark-versions/{version['id']}/lock",
        headers=headers,
    )
    assert locked.status_code == 200, locked.text
    assert locked.json()["status"] == "LOCKED"

    return {
        "data": data,
        "sid": sid,
        "prid": prid,
        "gold": gold,
        "dataset": dataset,
        "version": locked.json(),
        "case": case.json(),
    }


def _run_body(model: str, *, idempotency_key: str | None = None) -> dict:
    body: dict = {
        "candidate_provider": "fixed",
        "candidate_model": model,
        "candidate_model_version": "B15_V1",
        "candidate_prompt_template_version": "fixed-benchmark-v1",
        "candidate_config": {},
    }
    if idempotency_key is not None:
        body["idempotency_key"] = idempotency_key
    return body


@pytest.mark.asyncio
async def test_b15_dataset_version_lifecycle() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ds = await client.post(
            "/api/v1/quality/benchmark-datasets",
            headers=headers,
            json={"code": "LIFE-01", "title": "Lifecycle"},
        )
        assert ds.status_code == 200, ds.text
        dataset_id = ds.json()["id"]

        listed = await client.get(
            "/api/v1/quality/benchmark-datasets", headers=headers
        )
        assert listed.status_code == 200
        assert any(item["id"] == dataset_id for item in listed.json()["items"])

        got = await client.get(
            f"/api/v1/quality/benchmark-datasets/{dataset_id}", headers=headers
        )
        assert got.status_code == 200
        assert got.json()["code"] == "LIFE-01"

        v1 = await client.post(
            f"/api/v1/quality/benchmark-datasets/{dataset_id}/versions",
            headers=headers,
            json={},
        )
        assert v1.status_code == 200, v1.text
        assert v1.json()["version_number"] == 1
        v2 = await client.post(
            f"/api/v1/quality/benchmark-datasets/{dataset_id}/versions",
            headers=headers,
            json={},
        )
        assert v2.status_code == 200, v2.text
        assert v2.json()["version_number"] == 2

        versions = await client.get(
            f"/api/v1/quality/benchmark-datasets/{dataset_id}/versions",
            headers=headers,
        )
        assert versions.status_code == 200
        assert len(versions.json()["items"]) == 2


@pytest.mark.asyncio
async def test_b15_eligible_sources_require_published_human_final() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _ = await _to_approved(client, headers, data)

        ds = await client.post(
            "/api/v1/quality/benchmark-datasets",
            headers=headers,
            json={"code": "ELIG-01", "title": "Eligible"},
        )
        assert ds.status_code == 200, ds.text
        ver = await client.post(
            f"/api/v1/quality/benchmark-datasets/{ds.json()['id']}/versions",
            headers=headers,
            json={},
        )
        assert ver.status_code == 200, ver.text
        version_id = ver.json()["id"]

        before = await client.get(
            f"/api/v1/quality/benchmark-versions/{version_id}/eligible-sources",
            headers=headers,
        )
        assert before.status_code == 200, before.text
        before_pr_ids = {
            item["published_result_id"] for item in before.json()["items"]
        }

        prid = await _publish_approved(client, headers, sid)
        assert prid not in before_pr_ids

        after = await client.get(
            f"/api/v1/quality/benchmark-versions/{version_id}/eligible-sources",
            headers=headers,
        )
        assert after.status_code == 200, after.text
        items = after.json()["items"]
        assert any(i["published_result_id"] == prid for i in items)
        match = next(i for i in items if i["published_result_id"] == prid)
        assert len(match["question_evaluations"]) >= 1
        for qe in match["question_evaluations"]:
            assert qe["workflow_state"] in {"ACCEPTED", "OVERRIDDEN"}
            assert qe["final_human_approved_score"] is not None


@pytest.mark.asyncio
async def test_b15_add_case_freezes_gold_and_duplicate_idempotent() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _ = await _to_approved(client, headers, data)
        prid = await _publish_approved(client, headers, sid)
        gold = await _eligible_qe(client, headers, prid)

        ds = await client.post(
            "/api/v1/quality/benchmark-datasets",
            headers=headers,
            json={"code": "CASE-01", "title": "Cases"},
        )
        ver = await client.post(
            f"/api/v1/quality/benchmark-datasets/{ds.json()['id']}/versions",
            headers=headers,
            json={},
        )
        version_id = ver.json()["id"]
        body = {
            "published_result_id": gold["published_result_id"],
            "question_evaluation_id": gold["question_evaluation_id"],
        }
        first = await client.post(
            f"/api/v1/quality/benchmark-versions/{version_id}/cases",
            headers=headers,
            json=body,
        )
        assert first.status_code == 200, first.text
        case = first.json()
        assert case["expected_final_marks"] == gold["expected_final_marks"]
        assert case["expected_max_marks"] == gold["expected_max_marks"]
        assert "student" not in json.dumps(case["replay_fixture"]).lower()
        assert "criterion_snapshot" in case["replay_fixture"]

        second = await client.post(
            f"/api/v1/quality/benchmark-versions/{version_id}/cases",
            headers=headers,
            json=body,
        )
        assert second.status_code == 200, second.text
        assert second.json()["id"] == case["id"]


@pytest.mark.asyncio
async def test_b15_lock_immutability_and_idempotent() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _create_locked_version(client, headers, code="LOCK-01")
        version_id = ctx["version"]["id"]
        case_id = ctx["case"]["id"]

        again = await client.post(
            f"/api/v1/quality/benchmark-versions/{version_id}/lock",
            headers=headers,
        )
        assert again.status_code == 200, again.text
        assert again.json()["content_hash"] == ctx["version"]["content_hash"]

        add = await client.post(
            f"/api/v1/quality/benchmark-versions/{version_id}/cases",
            headers=headers,
            json={
                "published_result_id": ctx["gold"]["published_result_id"],
                "question_evaluation_id": ctx["gold"]["question_evaluation_id"],
            },
        )
        assert add.status_code == 409
        add_body = add.json()
        add_code = add_body.get("error", {}).get("code") or (
            add_body.get("detail") or {}
        ).get("code")
        assert add_code == "BENCHMARK_VERSION_LOCKED"

        remove = await client.delete(
            f"/api/v1/quality/benchmark-versions/{version_id}/cases/{case_id}",
            headers=headers,
        )
        assert remove.status_code == 409
        remove_body = remove.json()
        remove_code = remove_body.get("error", {}).get("code") or (
            remove_body.get("detail") or {}
        ).get("code")
        assert remove_code == "BENCHMARK_VERSION_LOCKED"

@pytest.mark.asyncio
async def test_b15_tenant_isolation_404() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _create_locked_version(client, headers, code="TEN-01")
        foreign = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                roles=frozenset({"INSTITUTION_ADMIN"}),
                permissions=frozenset({"quality:read", "quality:manage"}),
            )
        )[0]
        foreign_headers = {"Authorization": f"Bearer {foreign}"}
        for path in (
            f"/api/v1/quality/benchmark-datasets/{ctx['dataset']['id']}",
            f"/api/v1/quality/benchmark-versions/{ctx['version']['id']}",
            f"/api/v1/quality/regression-runs/{uuid.uuid4()}",
        ):
            resp = await client.get(path, headers=foreign_headers)
            assert resp.status_code == 404, path


@pytest.mark.asyncio
async def test_b15_permissions_403_without_quality() -> None:
    async with api_client_publication(text_provider="none") as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@demo.eduvijna.local",
                "password": "DemoAdmin!2026",
                "tenant_slug": "demo",
            },
        )
        assert login.status_code == 200, login.text
        context = JwtAuthProvider(get_settings()).verify_access_token(
            login.json()["access_token"]
        )
        no_quality = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=context.user_id,
                tenant_id=context.tenant_id,
                roles=frozenset({"EVALUATOR"}),
                permissions=frozenset({"evaluation:read"}),
            )
        )[0]
        denied_headers = {"Authorization": f"Bearer {no_quality}"}
        listed = await client.get(
            "/api/v1/quality/benchmark-datasets", headers=denied_headers
        )
        assert listed.status_code == 403
        created = await client.post(
            "/api/v1/quality/benchmark-datasets",
            headers=denied_headers,
            json={"code": "NOPE", "title": "Nope"},
        )
        assert created.status_code == 403


@pytest.mark.asyncio
async def test_b15_regression_pass_fixed_benchmark_pass() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _create_locked_version(client, headers, code="PASS-01")
        run = await client.post(
            f"/api/v1/quality/benchmark-versions/{ctx['version']['id']}/regression-runs",
            headers=headers,
            json=_run_body(MODEL_PASS),
        )
        assert run.status_code == 200, run.text
        body = run.json()
        assert body["status"] == "PASSED"
        assert body["verdict"] == "PASS"

        gate = await client.get(
            f"/api/v1/quality/regression-runs/{body['id']}/gate",
            headers=headers,
        )
        assert gate.status_code == 200, gate.text
        assert gate.json()["passed"] is True
        assert gate.json()["verdict"] == "PASS"


@pytest.mark.asyncio
async def test_b15_regression_fail_regress_and_gate() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _create_locked_version(client, headers, code="FAIL-01")
        run = await client.post(
            f"/api/v1/quality/benchmark-versions/{ctx['version']['id']}/regression-runs",
            headers=headers,
            json=_run_body(MODEL_REGRESS),
        )
        assert run.status_code == 200, run.text
        body = run.json()
        assert body["status"] == "FAILED"
        assert body["verdict"] == "FAIL"

        gate = await client.get(
            f"/api/v1/quality/regression-runs/{body['id']}/gate",
            headers=headers,
        )
        assert gate.status_code == 200, gate.text
        assert gate.json()["passed"] is False
        assert gate.json()["verdict"] == "FAIL"


@pytest.mark.asyncio
async def test_b15_invalid_output_safety_fail() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _create_locked_version(client, headers, code="SAFE-01")
        run = await client.post(
            f"/api/v1/quality/benchmark-versions/{ctx['version']['id']}/regression-runs",
            headers=headers,
            json=_run_body(MODEL_INVALID),
        )
        assert run.status_code == 200, run.text
        body = run.json()
        assert body["status"] == "FAILED"
        assert body["aggregate_metrics"]["safety_invariant_failure_rate"] == 1.0

        results = await client.get(
            f"/api/v1/quality/regression-runs/{body['id']}/case-results",
            headers=headers,
        )
        assert results.status_code == 200, results.text
        assert results.json()["items"][0]["safety_invariant_failed"] is True


@pytest.mark.asyncio
async def test_b15_idempotent_run_start() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _create_locked_version(client, headers, code="IDEM-01")
        key = f"idem-{uuid.uuid4().hex}"
        first = await client.post(
            f"/api/v1/quality/benchmark-versions/{ctx['version']['id']}/regression-runs",
            headers=headers,
            json=_run_body(MODEL_PASS, idempotency_key=key),
        )
        assert first.status_code == 200, first.text
        second = await client.post(
            f"/api/v1/quality/benchmark-versions/{ctx['version']['id']}/regression-runs",
            headers=headers,
            json=_run_body(MODEL_PASS, idempotency_key=key),
        )
        assert second.status_code == 200, second.text
        assert second.json()["id"] == first.json()["id"]


@pytest.mark.asyncio
async def test_b15_regression_does_not_mutate_ledger_or_mastery() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _create_locked_version(client, headers, code="ISO-01")

        async with async_session_factory() as db:
            tenant_id = (
                await db.scalar(select(Tenant.id).where(Tenant.slug == "demo"))
            )
            assert tenant_id is not None
            before_qe = int(
                await db.scalar(
                    select(func.count())
                    .select_from(QuestionEvaluation)
                    .where(QuestionEvaluation.tenant_id == tenant_id)
                )
                or 0
            )
            before_pr = int(
                await db.scalar(
                    select(func.count())
                    .select_from(PublishedResult)
                    .where(PublishedResult.tenant_id == tenant_id)
                )
                or 0
            )
            before_me = int(
                await db.scalar(
                    select(func.count())
                    .select_from(MasteryEvidence)
                    .where(MasteryEvidence.tenant_id == tenant_id)
                )
                or 0
            )
            qe_before = await db.scalar(
                select(QuestionEvaluation).where(
                    QuestionEvaluation.id
                    == uuid.UUID(ctx["gold"]["question_evaluation_id"])
                )
            )
            assert qe_before is not None
            score_before = qe_before.final_human_approved_score
            updated_before = qe_before.updated_at

        run = await client.post(
            f"/api/v1/quality/benchmark-versions/{ctx['version']['id']}/regression-runs",
            headers=headers,
            json=_run_body(MODEL_REGRESS),
        )
        assert run.status_code == 200, run.text

        async with async_session_factory() as db:
            tenant_id = (
                await db.scalar(select(Tenant.id).where(Tenant.slug == "demo"))
            )
            assert tenant_id is not None
            after_qe = int(
                await db.scalar(
                    select(func.count())
                    .select_from(QuestionEvaluation)
                    .where(QuestionEvaluation.tenant_id == tenant_id)
                )
                or 0
            )
            after_pr = int(
                await db.scalar(
                    select(func.count())
                    .select_from(PublishedResult)
                    .where(PublishedResult.tenant_id == tenant_id)
                )
                or 0
            )
            after_me = int(
                await db.scalar(
                    select(func.count())
                    .select_from(MasteryEvidence)
                    .where(MasteryEvidence.tenant_id == tenant_id)
                )
                or 0
            )
            qe_after = await db.scalar(
                select(QuestionEvaluation).where(
                    QuestionEvaluation.id
                    == uuid.UUID(ctx["gold"]["question_evaluation_id"])
                )
            )
            assert qe_after is not None
            assert after_qe == before_qe
            assert after_pr == before_pr
            assert after_me == before_me
            assert qe_after.final_human_approved_score == score_before
            assert qe_after.updated_at == updated_before


@pytest.mark.asyncio
async def test_b15_audit_events_present() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _create_locked_version(client, headers, code="AUD-01")
        run = await client.post(
            f"/api/v1/quality/benchmark-versions/{ctx['version']['id']}/regression-runs",
            headers=headers,
            json=_run_body(MODEL_PASS),
        )
        assert run.status_code == 200, run.text
        run_id = uuid.UUID(run.json()["id"])
        await client.get(
            f"/api/v1/quality/regression-runs/{run_id}/gate",
            headers=headers,
        )

        async with async_session_factory() as db:
            actions = set(
                (
                    await db.scalars(
                        select(AuditEvent.action).where(
                            AuditEvent.action.in_(
                                [
                                    "benchmark_dataset_created",
                                    "benchmark_version_created",
                                    "benchmark_case_added",
                                    "benchmark_version_locked",
                                    "benchmark_regression_started",
                                    "benchmark_regression_completed",
                                    "benchmark_gate_evaluated",
                                ]
                            )
                        )
                    )
                ).all()
            )
        assert "benchmark_dataset_created" in actions
        assert "benchmark_version_created" in actions
        assert "benchmark_case_added" in actions
        assert "benchmark_version_locked" in actions
        assert "benchmark_regression_started" in actions
        assert "benchmark_regression_completed" in actions
        assert "benchmark_gate_evaluated" in actions


@pytest.mark.asyncio
async def test_b15_cli_gate_exit_code() -> None:
    import subprocess
    import sys
    from pathlib import Path

    api_root = Path(__file__).resolve().parents[1]

    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _create_locked_version(client, headers, code="CLI-01")
        pass_run = await client.post(
            f"/api/v1/quality/benchmark-versions/{ctx['version']['id']}/regression-runs",
            headers=headers,
            json=_run_body(MODEL_PASS),
        )
        assert pass_run.status_code == 200, pass_run.text
        fail_run = await client.post(
            f"/api/v1/quality/benchmark-versions/{ctx['version']['id']}/regression-runs",
            headers=headers,
            json=_run_body(MODEL_REGRESS),
        )
        assert fail_run.status_code == 200, fail_run.text

        pass_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.cli.regression_gate",
                "--run-id",
                pass_run.json()["id"],
            ],
            cwd=str(api_root),
            capture_output=True,
            text=True,
            check=False,
        )
        fail_proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.cli.regression_gate",
                "--run-id",
                fail_run.json()["id"],
            ],
            cwd=str(api_root),
            capture_output=True,
            text=True,
            check=False,
        )
        assert pass_proc.returncode == 0, pass_proc.stdout + pass_proc.stderr
        assert fail_proc.returncode == 1, fail_proc.stdout + fail_proc.stderr

        async with async_session_factory() as db:
            tenant_id = await db.scalar(
                select(Tenant.id).where(Tenant.slug == "demo")
            )
            assert tenant_id is not None
            verdict = await evaluate_release_gate(
                db,
                tenant_id=tenant_id,
                run_id=uuid.UUID(pass_run.json()["id"]),
            )
            assert verdict["passed"] is True


def test_b15_candidate_routing_uses_registry_abstraction() -> None:
    from app.ai.providers.benchmark import (
        EvaluationBenchmarkAdapter,
        FixedBenchmarkProvider,
        is_ci_fixture_candidate,
    )
    from app.ai.registry import get_benchmark_candidate_executor

    assert is_ci_fixture_candidate(
        candidate_provider="fixed", candidate_model=MODEL_PASS
    )
    fixture = get_benchmark_candidate_executor(
        candidate_provider="fixed", candidate_model=MODEL_PASS
    )
    assert isinstance(fixture, FixedBenchmarkProvider)

    get_settings.cache_clear()
    # api_client_publication sets vision=fixed; mirror that for unit resolve
    import os

    os.environ["AI_PROVIDER_VISION"] = "fixed"
    get_settings.cache_clear()
    try:
        configured = get_benchmark_candidate_executor(
            candidate_provider="fixed",
            candidate_model="fixed-structure",
        )
        assert isinstance(configured, EvaluationBenchmarkAdapter)
        assert configured.provider_name == "fixed"
    finally:
        os.environ["AI_PROVIDER_VISION"] = "none"
        get_settings.cache_clear()


def test_b15_unsupported_and_unconfigured_candidates() -> None:
    import os

    from app.ai.providers.benchmark import BenchmarkCandidateError
    from app.ai.registry import get_benchmark_candidate_executor

    os.environ["AI_PROVIDER_VISION"] = "none"
    get_settings.cache_clear()
    with pytest.raises(BenchmarkCandidateError) as unconfigured:
        get_benchmark_candidate_executor(
            candidate_provider="openai",
            candidate_model="gpt-4o-mini",
        )
    assert unconfigured.value.code == "BENCHMARK_CANDIDATE_UNCONFIGURED"

    os.environ["AI_PROVIDER_VISION"] = "fixed"
    get_settings.cache_clear()
    try:
        with pytest.raises(BenchmarkCandidateError) as mismatch:
            get_benchmark_candidate_executor(
                candidate_provider="openai",
                candidate_model="gpt-4o-mini",
            )
        assert mismatch.value.code == "BENCHMARK_CANDIDATE_UNSUPPORTED"
    finally:
        os.environ["AI_PROVIDER_VISION"] = "none"
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_b15_threshold_profile_runtime_validation() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ds = await client.post(
            "/api/v1/quality/benchmark-datasets",
            headers=headers,
            json={"code": "THR-01", "title": "Thresholds"},
        )
        assert ds.status_code == 200, ds.text
        dataset_id = ds.json()["id"]

        missing = await client.post(
            f"/api/v1/quality/benchmark-datasets/{dataset_id}/versions",
            headers=headers,
            json={
                "threshold_profile_snapshot": {
                    "profile_code": "CUSTOM",
                    # missing required fields
                }
            },
        )
        assert missing.status_code == 422, missing.text

        extra = await client.post(
            f"/api/v1/quality/benchmark-datasets/{dataset_id}/versions",
            headers=headers,
            json={
                "threshold_profile_snapshot": {
                    **B15_DEFAULT_THRESHOLDS,
                    "unknown_field": True,
                }
            },
        )
        assert extra.status_code == 422, extra.text

        negative = await client.post(
            f"/api/v1/quality/benchmark-datasets/{dataset_id}/versions",
            headers=headers,
            json={
                "threshold_profile_snapshot": {
                    **B15_DEFAULT_THRESHOLDS,
                    "score_tolerance": -0.1,
                }
            },
        )
        assert negative.status_code == 422, negative.text

        out_of_range = await client.post(
            f"/api/v1/quality/benchmark-datasets/{dataset_id}/versions",
            headers=headers,
            json={
                "threshold_profile_snapshot": {
                    **B15_DEFAULT_THRESHOLDS,
                    "max_missing_output_rate": 1.5,
                }
            },
        )
        assert out_of_range.status_code == 422, out_of_range.text

        custom = {
            "profile_code": "CUSTOM_LOOSE_V1",
            "algorithm_version": "B15_V1",
            "max_missing_output_rate": 0.1,
            "max_mean_abs_score_error": 2.0,
            "min_exact_score_agreement_rate": 0.5,
            "min_taxonomy_agreement_rate": 0.5,
            "max_safety_invariant_failure_rate": 0.1,
            "score_tolerance": 0.25,
        }
        ok = await client.post(
            f"/api/v1/quality/benchmark-datasets/{dataset_id}/versions",
            headers=headers,
            json={"threshold_profile_snapshot": custom},
        )
        assert ok.status_code == 200, ok.text
        assert ok.json()["threshold_profile_snapshot"] == custom

        defaulted = await client.post(
            f"/api/v1/quality/benchmark-datasets/{dataset_id}/versions",
            headers=headers,
            json={},
        )
        assert defaulted.status_code == 200, defaulted.text
        assert (
            defaulted.json()["threshold_profile_snapshot"]["profile_code"]
            == "B15_DEFAULT_V1"
        )


@pytest.mark.asyncio
async def test_b15_configured_evaluation_provider_path_isolated() -> None:
    """Configured candidate uses EvaluationAIProvider via registry; no ledger writes."""
    from app.db.models import AiExecutionRecord, CriterionEvaluation

    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _create_locked_version(client, headers, code="CFG-01")

        async with async_session_factory() as db:
            tenant_id = await db.scalar(
                select(PublishedResult.tenant_id).where(
                    PublishedResult.id == uuid.UUID(ctx["prid"])
                )
            )
            assert tenant_id is not None
            before_qe = int(
                await db.scalar(
                    select(func.count())
                    .select_from(QuestionEvaluation)
                    .where(QuestionEvaluation.tenant_id == tenant_id)
                )
                or 0
            )
            before_pr = int(
                await db.scalar(
                    select(func.count())
                    .select_from(PublishedResult)
                    .where(PublishedResult.tenant_id == tenant_id)
                )
                or 0
            )
            before_ce = int(
                await db.scalar(
                    select(func.count())
                    .select_from(CriterionEvaluation)
                    .where(CriterionEvaluation.tenant_id == tenant_id)
                )
                or 0
            )
            before_me = int(
                await db.scalar(
                    select(func.count())
                    .select_from(MasteryEvidence)
                    .where(MasteryEvidence.tenant_id == tenant_id)
                )
                or 0
            )
            before_ai = int(
                await db.scalar(
                    select(func.count())
                    .select_from(AiExecutionRecord)
                    .where(
                        AiExecutionRecord.tenant_id == tenant_id,
                        AiExecutionRecord.operation == "gold_benchmark_evaluate",
                    )
                )
                or 0
            )

        run = await client.post(
            f"/api/v1/quality/benchmark-versions/{ctx['version']['id']}/regression-runs",
            headers=headers,
            json={
                "candidate_provider": "fixed",
                "candidate_model": "fixed-structure",
                "candidate_model_version": "B11_V1",
                "candidate_prompt_template_version": "fixed-structure-evaluate_rubric-v1",
                "candidate_config": {"path": "evaluation_provider"},
            },
        )
        assert run.status_code == 200, run.text
        body = run.json()
        assert body["candidate_provider"] == "fixed"
        assert body["candidate_model"] == "fixed-structure"
        assert body["status"] in {"PASSED", "FAILED"}
        assert body["verdict"] in {"PASS", "FAIL"}

        unsupported = await client.post(
            f"/api/v1/quality/benchmark-versions/{ctx['version']['id']}/regression-runs",
            headers=headers,
            json={
                "candidate_provider": "openai",
                "candidate_model": "gpt-4o-mini",
                "candidate_model_version": "x",
                "candidate_prompt_template_version": "x",
            },
        )
        assert unsupported.status_code == 409, unsupported.text
        err = unsupported.json()
        code = (
            err.get("error", {}).get("code")
            or (err.get("detail") or {}).get("code")
        )
        assert code in {
            "BENCHMARK_CANDIDATE_UNSUPPORTED",
            "BENCHMARK_CANDIDATE_UNCONFIGURED",
        }

        async with async_session_factory() as db:
            after_qe = int(
                await db.scalar(
                    select(func.count())
                    .select_from(QuestionEvaluation)
                    .where(QuestionEvaluation.tenant_id == tenant_id)
                )
                or 0
            )
            after_pr = int(
                await db.scalar(
                    select(func.count())
                    .select_from(PublishedResult)
                    .where(PublishedResult.tenant_id == tenant_id)
                )
                or 0
            )
            after_ce = int(
                await db.scalar(
                    select(func.count())
                    .select_from(CriterionEvaluation)
                    .where(CriterionEvaluation.tenant_id == tenant_id)
                )
                or 0
            )
            after_me = int(
                await db.scalar(
                    select(func.count())
                    .select_from(MasteryEvidence)
                    .where(MasteryEvidence.tenant_id == tenant_id)
                )
                or 0
            )
            after_ai = int(
                await db.scalar(
                    select(func.count())
                    .select_from(AiExecutionRecord)
                    .where(
                        AiExecutionRecord.tenant_id == tenant_id,
                        AiExecutionRecord.operation == "gold_benchmark_evaluate",
                    )
                )
                or 0
            )
            record = await db.scalar(
                select(AiExecutionRecord)
                .where(
                    AiExecutionRecord.tenant_id == tenant_id,
                    AiExecutionRecord.operation == "gold_benchmark_evaluate",
                )
                .order_by(AiExecutionRecord.created_at.desc())
            )
        assert after_qe == before_qe
        assert after_pr == before_pr
        assert after_ce == before_ce
        assert after_me == before_me
        assert after_ai == before_ai + 1
        assert record is not None
        assert record.provider == "fixed"
        assert record.model is not None
        assert record.model_version is not None
        assert record.prompt_template_version is not None
