"""B15.1 benchmark candidate identity binding regression coverage."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import func, select

from app.ai.providers.benchmark import BenchmarkCandidateError, MODEL_PASS
from app.ai.registry import (
    get_benchmark_candidate_identity,
    get_benchmark_candidate_executor,
    validate_benchmark_candidate_identity,
)
from app.core.config import get_settings
from app.db.models import AiExecutionRecord, BenchmarkRegressionRun
from app.db.session import async_session_factory
from tests.test_b15_gold_benchmark_regression import _create_locked_version
from tests.test_b3_submission_ingestion import _headers
from tests.test_b7_publication_reports import api_client_publication


def _set_fixed_provider() -> None:
    os.environ["AI_PROVIDER_VISION"] = "fixed"
    get_settings.cache_clear()


def _reset_provider() -> None:
    os.environ["AI_PROVIDER_VISION"] = "none"
    get_settings.cache_clear()


def test_b151_fixture_identity_is_canonical() -> None:
    identity = validate_benchmark_candidate_identity(
        candidate_provider="fixed",
        candidate_model=MODEL_PASS,
        candidate_model_version="B15_V1",
        candidate_prompt_template_version="fixed-benchmark-v1",
    )
    assert identity.provider == "fixed"
    assert identity.model == MODEL_PASS
    assert identity.model_version == "B15_V1"
    assert identity.prompt_template_version == "fixed-benchmark-v1"


def test_b151_configured_identity_matches_executable_provider() -> None:
    _set_fixed_provider()
    try:
        identity = get_benchmark_candidate_identity(
            candidate_provider="fixed",
            candidate_model="fixed-structure",
        )
        assert identity.provider == "fixed"
        assert identity.model == "fixed-structure"
        assert identity.model_version == "B11_V1"
        assert identity.prompt_template_version == "fixed-structure-evaluate_rubric-v1"

        validated = validate_benchmark_candidate_identity(
            candidate_provider="fixed",
            candidate_model="fixed-structure",
            candidate_model_version="B11_V1",
            candidate_prompt_template_version="fixed-structure-evaluate_rubric-v1",
        )
        assert validated == identity
    finally:
        _reset_provider()


def test_b151_configured_model_claim_cannot_differ_from_actual() -> None:
    _set_fixed_provider()
    try:
        with pytest.raises(BenchmarkCandidateError) as excinfo:
            get_benchmark_candidate_executor(
                candidate_provider="fixed",
                candidate_model="claimed-model-b",
            )
        assert excinfo.value.code == "BENCHMARK_CANDIDATE_IDENTITY_MISMATCH"
        assert "fixed-structure" in excinfo.value.message
    finally:
        _reset_provider()


@pytest.mark.parametrize(
    ("model_version", "prompt_version"),
    [
        ("claimed-version-b", "fixed-structure-evaluate_rubric-v1"),
        ("B11_V1", "claimed-template-b"),
    ],
)
def test_b151_configured_version_or_template_claim_rejected(
    model_version: str, prompt_version: str
) -> None:
    _set_fixed_provider()
    try:
        with pytest.raises(BenchmarkCandidateError) as excinfo:
            validate_benchmark_candidate_identity(
                candidate_provider="fixed",
                candidate_model="fixed-structure",
                candidate_model_version=model_version,
                candidate_prompt_template_version=prompt_version,
            )
        assert excinfo.value.code == "BENCHMARK_CANDIDATE_IDENTITY_MISMATCH"
    finally:
        _reset_provider()


@pytest.mark.asyncio
async def test_b151_api_persists_only_canonical_identity_and_rejects_false_claims() -> None:
    async with api_client_publication(text_provider="none") as client:
        headers = await _headers(client)
        ctx = await _create_locked_version(client, headers, code="IDENTITY-01")
        version_id = ctx["version"]["id"]

        canonical_body = {
            "candidate_provider": "fixed",
            "candidate_model": "fixed-structure",
            "candidate_model_version": "B11_V1",
            "candidate_prompt_template_version": "fixed-structure-evaluate_rubric-v1",
            "candidate_config": {"path": "evaluation_provider"},
        }
        run_response = await client.post(
            f"/api/v1/quality/benchmark-versions/{version_id}/regression-runs",
            headers=headers,
            json=canonical_body,
        )
        assert run_response.status_code == 200, run_response.text
        run = run_response.json()
        assert run["candidate_provider"] == canonical_body["candidate_provider"]
        assert run["candidate_model"] == canonical_body["candidate_model"]
        assert run["candidate_model_version"] == canonical_body["candidate_model_version"]
        assert (
            run["candidate_prompt_template_version"]
            == canonical_body["candidate_prompt_template_version"]
        )

        results = await client.get(
            f"/api/v1/quality/regression-runs/{run['id']}/case-results",
            headers=headers,
        )
        assert results.status_code == 200, results.text
        result_items = results.json()["items"]
        assert result_items
        ai_record_id = result_items[0]["ai_execution_record_id"]
        assert ai_record_id is not None

        async with async_session_factory() as db:
            record = await db.scalar(
                select(AiExecutionRecord).where(
                    AiExecutionRecord.id == uuid.UUID(ai_record_id)
                )
            )
            assert record is not None
            assert record.provider == run["candidate_provider"]
            assert record.model == run["candidate_model"]
            assert record.model_version == run["candidate_model_version"]
            assert (
                record.prompt_template_version
                == run["candidate_prompt_template_version"]
            )
            before_runs = int(
                await db.scalar(
                    select(func.count())
                    .select_from(BenchmarkRegressionRun)
                    .where(
                        BenchmarkRegressionRun.dataset_version_id
                        == uuid.UUID(version_id)
                    )
                )
                or 0
            )

        false_claims = [
            {**canonical_body, "candidate_model": "claimed-model-b"},
            {**canonical_body, "candidate_model_version": "claimed-version-b"},
            {
                **canonical_body,
                "candidate_prompt_template_version": "claimed-template-b",
            },
        ]
        for body in false_claims:
            response = await client.post(
                f"/api/v1/quality/benchmark-versions/{version_id}/regression-runs",
                headers=headers,
                json=body,
            )
            assert response.status_code == 409, response.text
            payload = response.json()
            code = payload.get("error", {}).get("code") or (
                payload.get("detail") or {}
            ).get("code")
            assert code == "BENCHMARK_CANDIDATE_IDENTITY_MISMATCH"

        async with async_session_factory() as db:
            after_runs = int(
                await db.scalar(
                    select(func.count())
                    .select_from(BenchmarkRegressionRun)
                    .where(
                        BenchmarkRegressionRun.dataset_version_id
                        == uuid.UUID(version_id)
                    )
                )
                or 0
            )
        assert after_runs == before_runs
