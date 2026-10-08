"""B14 learning-plan prepare concurrency + idempotency regression (Issue #124)."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.cli.seed_dev import seed
from app.core.config import get_settings
from app.db.models import LearningPlanRun, MasteryEvidence
from app.db.session import async_session_factory
from app.main import create_app
from app.services.storage import ObjectStorage
from tests.test_b3_submission_ingestion import _headers
from tests.test_b7_publication_reports import _to_approved
from tests.test_b8_analytics_mastery import (
    _publish_approved,
    _ready_assessment_with_curriculum,
)
from tests.test_b9_learning_blueprint import _force_concept_weak


@asynccontextmanager
async def _learning_prepare_client() -> AsyncIterator[AsyncClient]:
    """API client; learning enqueue is patched in tests so runs stay QUEUED."""
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
    os.environ["S3_ENDPOINT_URL"] = "http://127.0.0.1:19000"
    os.environ["AI_PROVIDER_VISION"] = "fixed"
    os.environ["AI_PROVIDER_TEXT"] = "none"
    os.environ["APP_ENV"] = "test"
    await seed()
    get_settings.cache_clear()
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


@pytest.mark.asyncio
async def test_b14_concurrent_learning_prepare_is_idempotent() -> None:
    enqueue_calls = 0

    async def _fake_enqueue(**_kwargs: object) -> str:
        nonlocal enqueue_calls
        enqueue_calls += 1
        return f"celery-task-{enqueue_calls}"

    async with _learning_prepare_client() as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, student_id = await _to_approved(client, headers, data)
        await _publish_approved(client, headers, sid)
        curriculum_id = data["curriculum"]["id"]
        node_id = data["node"]["id"]
        await _force_concept_weak(
            student_id=student_id, curriculum_id=curriculum_id, node_id=node_id
        )

        path = f"/api/v1/learning/students/{student_id}/prepare"
        body = {"curriculum_id": curriculum_id}

        with patch(
            "app.tasks.celery_app.enqueue_learning_plan",
            new=AsyncMock(side_effect=_fake_enqueue),
        ):
            async def _prepare() -> dict:
                r = await client.post(path, headers=headers, json=body)
                assert r.status_code == 200, r.text
                return r.json()

            first, second = await asyncio.gather(_prepare(), _prepare())

        assert first["run_id"] == second["run_id"]
        assert first["version_number"] == second["version_number"]
        assert first["input_hash"] == second["input_hash"]
        assert first["algorithm_version"] == second["algorithm_version"]
        assert enqueue_calls == 1

        async with async_session_factory() as db:
            count = await db.scalar(
                select(func.count())
                .select_from(LearningPlanRun)
                .where(
                    LearningPlanRun.student_id == uuid.UUID(student_id),
                    LearningPlanRun.curriculum_id == uuid.UUID(curriculum_id),
                    LearningPlanRun.input_hash == first["input_hash"],
                    LearningPlanRun.algorithm_version == first["algorithm_version"],
                )
            )
            assert count == 1

        third = await client.post(path, headers=headers, json=body)
        assert third.status_code == 200, third.text
        assert third.json()["run_id"] == first["run_id"]
        assert enqueue_calls == 1

        foreign = await client.post(
            f"/api/v1/learning/students/{uuid.uuid4()}/prepare",
            headers=headers,
            json=body,
        )
        assert foreign.status_code == 404


@pytest.mark.asyncio
async def test_b14_learning_prepare_allocates_monotonic_versions() -> None:
    async with _learning_prepare_client() as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, student_id = await _to_approved(client, headers, data)
        await _publish_approved(client, headers, sid)
        curriculum_id = data["curriculum"]["id"]
        node_id = data["node"]["id"]
        await _force_concept_weak(
            student_id=student_id, curriculum_id=curriculum_id, node_id=node_id
        )

        path = f"/api/v1/learning/students/{student_id}/prepare"
        body = {"curriculum_id": curriculum_id}

        with patch(
            "app.tasks.celery_app.enqueue_learning_plan",
            new=AsyncMock(return_value="celery-task-1"),
        ):
            prep1 = await client.post(path, headers=headers, json=body)
        assert prep1.status_code == 200, prep1.text
        run_id_1 = prep1.json()["run_id"]
        version_1 = prep1.json()["version_number"]
        input_hash_1 = prep1.json()["input_hash"]

        async with async_session_factory() as db:
            evidence = await db.scalar(
                select(MasteryEvidence)
                .where(
                    MasteryEvidence.student_id == uuid.UUID(student_id),
                    MasteryEvidence.curriculum_id == uuid.UUID(curriculum_id),
                )
                .limit(1)
            )
            assert evidence is not None
            evidence.score_ratio = Decimal("0.111111")
            await db.commit()

        with patch(
            "app.tasks.celery_app.enqueue_learning_plan",
            new=AsyncMock(return_value="celery-task-2"),
        ):
            prep2 = await client.post(path, headers=headers, json=body)
        assert prep2.status_code == 200, prep2.text
        assert prep2.json()["run_id"] != run_id_1
        assert prep2.json()["version_number"] == version_1 + 1
        assert prep2.json()["input_hash"] != input_hash_1
