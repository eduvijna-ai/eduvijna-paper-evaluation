"""B14 learning-plan prepare concurrency + idempotency regression (Issue #124)."""

from __future__ import annotations

import asyncio
import os
import time
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
from app.services import learning as learning_service
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


async def _published_weak_student(
    client: AsyncClient, headers: dict[str, str]
) -> tuple[dict, str, str, str]:
    data = await _ready_assessment_with_curriculum(client, headers)
    sid, student_id = await _to_approved(client, headers, data)
    await _publish_approved(client, headers, sid)
    curriculum_id = data["curriculum"]["id"]
    node_id = data["node"]["id"]
    await _force_concept_weak(
        student_id=student_id, curriculum_id=curriculum_id, node_id=node_id
    )
    return data, student_id, curriculum_id, sid


@pytest.mark.asyncio
async def test_b14_prepare_locks_before_input_snapshot() -> None:
    order: list[str] = []

    orig_lock = learning_service._lock_student_prepare_scope
    orig_hashes = learning_service._compute_current_hashes

    async def _track_lock(
        db: object, *, tenant_id: uuid.UUID, student_id: uuid.UUID
    ) -> object:
        order.append("lock")
        return await orig_lock(db, tenant_id=tenant_id, student_id=student_id)

    async def _track_hashes(
        db: object, *, tenant_id: uuid.UUID, student_id: uuid.UUID, curriculum_id: uuid.UUID
    ) -> tuple[str, str, str, object | None]:
        order.append("hash")
        return await orig_hashes(
            db,
            tenant_id=tenant_id,
            student_id=student_id,
            curriculum_id=curriculum_id,
        )

    async with _learning_prepare_client() as client:
        headers = await _headers(client)
        data, student_id, curriculum_id, _sid = await _published_weak_student(client, headers)
        with (
            patch.object(learning_service, "_lock_student_prepare_scope", side_effect=_track_lock),
            patch.object(learning_service, "_compute_current_hashes", side_effect=_track_hashes),
            patch(
                "app.tasks.celery_app.enqueue_learning_plan",
                new=AsyncMock(return_value="celery-task-order"),
            ),
        ):
            resp = await client.post(
                f"/api/v1/learning/students/{student_id}/prepare",
                headers=headers,
                json={"curriculum_id": curriculum_id},
            )
        assert resp.status_code == 200, resp.text
        assert order[:2] == ["lock", "hash"]


@pytest.mark.asyncio
async def test_b14_active_enqueue_claim_masks_marker_and_skips_dispatch() -> None:
    async with _learning_prepare_client() as client:
        headers = await _headers(client)
        _data, student_id, curriculum_id, _sid = await _published_weak_student(client, headers)
        path = f"/api/v1/learning/students/{student_id}/prepare"
        body = {"curriculum_id": curriculum_id}

        gate = asyncio.Event()
        enqueue_calls = 0

        async def _slow_enqueue(**_kwargs: object) -> str:
            nonlocal enqueue_calls
            enqueue_calls += 1
            await gate.wait()
            return "celery-task-slow"

        with patch(
            "app.tasks.celery_app.enqueue_learning_plan",
            new=AsyncMock(side_effect=_slow_enqueue),
        ):
            first = asyncio.create_task(client.post(path, headers=headers, json=body))
            await asyncio.sleep(0.05)
            second = await client.post(path, headers=headers, json=body)
            gate.set()
            first_resp = await first

        assert first_resp.status_code == 200, first_resp.text
        assert second.status_code == 200, second.text
        assert enqueue_calls == 1
        assert first_resp.json()["run_id"] == second.json()["run_id"]
        assert second.json()["celery_task_id"] is None
        assert not learning_service._is_enqueue_claim_token(
            second.json().get("celery_task_id")
        )


@pytest.mark.asyncio
async def test_b14_stale_enqueue_claim_is_reclaimed() -> None:
    async with _learning_prepare_client() as client:
        headers = await _headers(client)
        _data, student_id, curriculum_id, _sid = await _published_weak_student(client, headers)
        path = f"/api/v1/learning/students/{student_id}/prepare"
        body = {"curriculum_id": curriculum_id}

        with patch(
            "app.tasks.celery_app.enqueue_learning_plan",
            new=AsyncMock(return_value="celery-task-seed"),
        ):
            seeded = await client.post(path, headers=headers, json=body)
        assert seeded.status_code == 200, seeded.text
        run_id = uuid.UUID(seeded.json()["run_id"])
        stale_claim = f"{learning_service._ENQUEUE_CLAIM_PREFIX}{int(time.time()) - 30}__"

        async with async_session_factory() as db:
            run = await db.scalar(select(LearningPlanRun).where(LearningPlanRun.id == run_id))
            assert run is not None
            run.status = "QUEUED"
            run.celery_task_id = stale_claim
            await db.commit()

        enqueue_calls = 0

        async def _reclaim_enqueue(**_kwargs: object) -> str:
            nonlocal enqueue_calls
            enqueue_calls += 1
            return "celery-task-reclaimed"

        with patch(
            "app.tasks.celery_app.enqueue_learning_plan",
            new=AsyncMock(side_effect=_reclaim_enqueue),
        ):
            reclaimed = await client.post(path, headers=headers, json=body)

        assert reclaimed.status_code == 200, reclaimed.text
        assert enqueue_calls == 1
        assert reclaimed.json()["celery_task_id"] == "celery-task-reclaimed"
        async with async_session_factory() as db:
            run = await db.scalar(select(LearningPlanRun).where(LearningPlanRun.id == run_id))
            assert run is not None
            assert run.celery_task_id == "celery-task-reclaimed"


@pytest.mark.asyncio
async def test_b14_enqueue_failure_clears_claim_for_retry() -> None:
    async with _learning_prepare_client() as client:
        headers = await _headers(client)
        _data, student_id, curriculum_id, _sid = await _published_weak_student(client, headers)
        path = f"/api/v1/learning/students/{student_id}/prepare"
        body = {"curriculum_id": curriculum_id}

        with patch(
            "app.tasks.celery_app.enqueue_learning_plan",
            new=AsyncMock(side_effect=RuntimeError("enqueue failed")),
        ):
            failed = await client.post(path, headers=headers, json=body)
        assert failed.status_code == 200, failed.text
        assert failed.json()["celery_task_id"] is None
        assert failed.json()["enqueue_error"]

        with patch(
            "app.tasks.celery_app.enqueue_learning_plan",
            new=AsyncMock(return_value="celery-task-retry"),
        ):
            retry = await client.post(path, headers=headers, json=body)
        assert retry.status_code == 200, retry.text
        assert retry.json()["celery_task_id"] == "celery-task-retry"
