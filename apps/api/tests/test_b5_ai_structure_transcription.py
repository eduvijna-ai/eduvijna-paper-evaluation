"""B5 AI structure + transcription coverage (fixed provider)."""

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
    IdentityExtractionInput,
    NormalizedBBox,
    TranscriptionInput,
    TranscriptionResult,
)
from app.cli.seed_dev import seed
from app.core.config import get_settings
from app.db.models import AiExecutionRecord, AnswerRegion, PipelineJob, Submission
from app.db.session import async_session_factory
from app.main import create_app
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


@pytest.mark.asyncio
async def test_b5_fixed_provider_identity_mapping_transcription() -> None:
    async with api_client_fixed() as client:
        headers = await _headers(client)
        data = await _ready_assessment(client, headers)

        upload = await client.post(
            "/api/v1/submissions",
            headers=headers,
            files={"file": ("b5.pdf", _pdf_bytes(), "application/pdf")},
            data={"assessment_id": data["assessment"]["id"]},
        )
        assert upload.status_code == 201, upload.text
        sid = upload.json()["id"]

        detail = await client.get(f"/api/v1/submissions/{sid}", headers=headers)
        assert detail.status_code == 200
        body = detail.json()
        assert body["workflow_state"] == "IDENTITY_REVIEW"
        assert body["name_detected"] == "Fixed Student"
        assert float(body["identity_confidence"]) == pytest.approx(0.82)

        identity = await client.get(f"/api/v1/submissions/{sid}/identity", headers=headers)
        assert identity.status_code == 200
        id_body = identity.json()
        assert id_body["automated_matching_active"] is True
        assert id_body["detected"]["name"] == "Fixed Student"

        students = await client.get("/api/v1/students", headers=headers)
        assert students.status_code == 200
        student_id = await _ensure_student(client, headers)
        confirm = await client.post(
            f"/api/v1/submissions/{sid}/identity/confirm",
            headers=headers,
            json={"student_id": student_id},
        )
        assert confirm.status_code == 200, confirm.text
        # Human confirm must not rewrite AI identity confidence to 1.0
        assert float(confirm.json()["identity_confidence"]) == pytest.approx(0.82)

        mapping = await client.get(f"/api/v1/submissions/{sid}/mapping", headers=headers)
        assert mapping.status_code == 200
        mbody = mapping.json()
        assert mbody["automated_region_detection_active"] is True
        assert len(mbody["regions"]) >= 1
        assert any(r["source_type"] == "AI" for r in mbody["regions"])

        leaves = [n for n in mbody["questions"] if n.get("is_leaf_scorable")]
        assert len(leaves) >= 2
        # First leaf ANSWERED with first region; second BLANK (region uniqueness).
        first = leaves[0]
        region_id = mbody["regions"][0]["id"]
        put1 = await client.put(
            f"/api/v1/submissions/{sid}/question-mappings/{first['question_version_id']}",
            headers=headers,
            json={"disposition": "ANSWERED", "region_ids": [region_id]},
        )
        assert put1.status_code == 200, put1.text
        conf1 = await client.post(
            f"/api/v1/submissions/{sid}/question-mappings/{first['question_version_id']}/confirm",
            headers=headers,
        )
        assert conf1.status_code == 200, conf1.text

        second = leaves[1]
        put2 = await client.put(
            f"/api/v1/submissions/{sid}/question-mappings/{second['question_version_id']}",
            headers=headers,
            json={"disposition": "BLANK", "region_ids": []},
        )
        assert put2.status_code == 200, put2.text
        conf2 = await client.post(
            f"/api/v1/submissions/{sid}/question-mappings/{second['question_version_id']}/confirm",
            headers=headers,
        )
        assert conf2.status_code == 200, conf2.text

        fin = await client.post(
            f"/api/v1/submissions/{sid}/mapping/finalize", headers=headers
        )
        assert fin.status_code == 200, fin.text
        assert fin.json()["workflow_state"] == "READY_FOR_EVALUATION"

        detail2 = await client.get(f"/api/v1/submissions/{sid}", headers=headers)
        assert detail2.json()["transcription_state"] == "REVIEW_REQUIRED"

        workspace = await client.get(
            f"/api/v1/submissions/{sid}/transcription", headers=headers
        )
        assert workspace.status_code == 200
        w = workspace.json()
        assert w["automated_transcription_active"] is True

        edited = False
        for item in w["items"]:
            for region in item["regions"]:
                if not region.get("requires_transcription"):
                    continue
                if not edited:
                    put = await client.put(
                        f"/api/v1/answer-regions/{region['id']}/transcription",
                        headers=headers,
                        json={
                            "text": "Human-corrected transcription",
                            "outcome": "TRANSCRIBED",
                        },
                    )
                    assert put.status_code == 200
                    assert put.json()["source_type"] == "HUMAN"
                    assert put.json()["transcription_confidence"] is None
                    conf_id = put.json()["id"]
                    edited = True
                else:
                    active = region.get("active_transcription") or region.get(
                        "latest_ai_proposal"
                    )
                    assert active is not None
                    conf_id = active["id"]
                conf = await client.post(
                    f"/api/v1/answer-region-transcriptions/{conf_id}/confirm",
                    headers=headers,
                )
                assert conf.status_code == 200, conf.text

        finalize = await client.post(
            f"/api/v1/submissions/{sid}/transcription/finalize", headers=headers
        )
        assert finalize.status_code == 200, finalize.text
        assert finalize.json()["transcription_state"] == "READY"
        assert finalize.json()["evaluation_enqueued"] is False
        assert finalize.json()["workflow_state"] == "READY_FOR_EVALUATION"

        async with async_session_factory() as db:
            execs = list(
                (
                    await db.scalars(
                        select(AiExecutionRecord).where(
                            AiExecutionRecord.submission_id == uuid.UUID(sid)
                        )
                    )
                ).all()
            )
            ops = {e.operation for e in execs}
            assert "extract_student_identity" in ops
            assert "analyze_page" in ops
            assert "map_answer_regions" in ops
            assert "transcribe_answer" in ops
            for e in execs:
                assert e.input_hash
                if e.operation == "transcribe_answer":
                    assert "character_count" in e.response_summary
                    assert "output_hash" in e.response_summary
                    assert "Fixed transcription for" not in str(e.response_summary)
            assert (
                await db.scalars(
                    select(PipelineJob).where(
                        PipelineJob.submission_id == uuid.UUID(sid),
                        PipelineJob.stage == "EVALUATION",
                    )
                )
            ).all() == []
            sub = await db.scalar(select(Submission).where(Submission.id == uuid.UUID(sid)))
            assert sub is not None
            cropped = list(
                (
                    await db.scalars(
                        select(AnswerRegion).where(AnswerRegion.crop_storage_key.is_not(None))
                    )
                ).all()
            )
            assert any(
                r.crop_storage_key
                and "/derived/" in r.crop_storage_key
                and "/raw/" not in r.crop_storage_key
                for r in cropped
            )


def test_b5_bbox_and_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        NormalizedBBox(x=0.9, y=0.9, width=0.2, height=0.2)
    with pytest.raises(ValidationError):
        TranscriptionResult(
            text="x",
            segments=[],
            transcription_confidence=Decimal("1.5"),
            unreadable=False,
        )


@pytest.mark.asyncio
async def test_openai_adapter_mocked() -> None:
    async def caller(operation: str, payload: dict) -> dict:
        assert "sk-test" not in str(payload)
        if operation == "transcription":
            return {
                "text": "mocked",
                "latex": None,
                "segments": [{"text": "mocked"}],
                "transcription_confidence": "0.5",
                "unreadable": False,
            }
        raise AssertionError(operation)

    provider = OpenAIStructureProvider(
        api_key="sk-test-never-log",
        model_identity="m",
        model_page_analysis="m",
        model_mapping="m",
        model_transcription="m",
        caller=caller,
    )
    result = await provider.transcribe_answer(
        TranscriptionInput(
            submission_id=uuid.uuid4(),
            answer_region_id=uuid.uuid4(),
            crop_content_sha256="a" * 64,
        )
    )
    assert result.text == "mocked"

    async def bad_caller(operation: str, payload: dict) -> dict:
        return {
            "text": "x",
            "segments": [],
            "transcription_confidence": "9",
            "unreadable": False,
        }

    bad = OpenAIStructureProvider(
        api_key="sk-test",
        model_identity="m",
        model_page_analysis="m",
        model_mapping="m",
        model_transcription="m",
        caller=bad_caller,
    )
    with pytest.raises(ValidationError):
        await bad.transcribe_answer(
            TranscriptionInput(
                submission_id=uuid.uuid4(),
                answer_region_id=uuid.uuid4(),
                crop_content_sha256="b" * 64,
            )
        )


@pytest.mark.asyncio
async def test_fixed_provider_deterministic() -> None:
    provider = FixedStructureProvider(allow_non_test=True)
    req = IdentityExtractionInput(
        submission_id=uuid.uuid4(),
        page_id=uuid.uuid4(),
        roster_hints=[{"student_id": str(uuid.uuid4()), "name": "A", "roll": "1"}],
    )
    a = await provider.extract_student_identity(req)
    b = await provider.extract_student_identity(req)
    assert a.extracted_name == b.extracted_name == "Fixed Student"
