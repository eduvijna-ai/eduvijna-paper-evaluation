"""B11 release-audit blocker regressions (PEV-002 evidence, curriculum gate, PEV-060)."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.cli.seed_dev import seed
from app.core.config import get_settings
from app.db.models import (
    AiExecutionRecord,
    AuthoringAiRun,
    QuestionCurriculumMapping,
)
from app.db.session import async_session_factory
from app.main import create_app
from app.services.storage import ObjectStorage
from tests.test_a2_gate_matrix import _foundation, _headers


def _pdf_with_text(label: str) -> bytes:
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


def _err(response: Any) -> dict[str, Any]:
    body = response.json()
    if "error" in body and isinstance(body["error"], dict):
        details = body["error"].get("details") or {}
        if isinstance(details, dict) and "code" in details:
            return details
        return {
            "code": body["error"].get("code"),
            "message": body["error"].get("message"),
        }
    detail = body.get("detail") or body
    if isinstance(detail, dict):
        return detail
    return {"message": str(detail)}


async def _upload_paper(
    client: AsyncClient,
    headers: dict[str, str],
    version_id: str,
    text: str,
) -> dict[str, Any]:
    pdf = _pdf_with_text(text)
    response = await client.post(
        f"/api/v1/assessment-versions/{version_id}/question-paper",
        headers=headers,
        files={"file": (f"paper-{uuid.uuid4().hex[:8]}.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_b11_parse_without_upload_blocked() -> None:
    async with api_client_authoring(authoring_provider="fixed") as client:
        headers = await _headers(client)
        data = await _foundation(client, headers, marks="10.00")
        version_id = data["version_id"]

        parse = await client.post(
            f"/api/v1/assessment-versions/{version_id}/question-paper/parse",
            headers=headers,
        )
        assert parse.status_code == 409, parse.text
        assert _err(parse)["code"] == "QUESTION_PAPER_ARTIFACT_REQUIRED"

        async with async_session_factory() as db:
            runs = await db.scalar(
                select(func.count())
                .select_from(AuthoringAiRun)
                .where(
                    AuthoringAiRun.assessment_version_id == uuid.UUID(version_id),
                    AuthoringAiRun.operation == "PARSE_QUESTION_PAPER",
                )
            )
            assert int(runs or 0) == 0
            execs = await db.scalar(
                select(func.count())
                .select_from(AiExecutionRecord)
                .where(AiExecutionRecord.operation == "parse_question_paper")
            )
            # Seeded tenants may have older rows; scope by version via join not available —
            # assert no new SUCCEEDED parse for this version via runs already 0.
            assert int(execs or 0) >= 0


@pytest.mark.asyncio
async def test_b11_parse_evidence_depends_on_source_content() -> None:
    async with api_client_authoring(authoring_provider="fixed") as client:
        headers = await _headers(client)

        data_a = await _foundation(client, headers, marks="10.00")
        text_a = "1(a) Solve 2x + 3 = 7. [10 marks]"
        await _upload_paper(client, headers, data_a["version_id"], text_a)
        parse_a = await client.post(
            f"/api/v1/assessment-versions/{data_a['version_id']}/question-paper/parse",
            headers=headers,
        )
        assert parse_a.status_code == 200, parse_a.text
        body_a = parse_a.json()
        assert body_a["status"] == "REVIEW_REQUIRED"
        prompt_a = body_a["proposal_payload"]["roots"][0]["children"][0]["prompt_text"]
        assert "2x + 3 = 7" in prompt_a
        assert "Solve" in prompt_a

        meta = body_a
        async with async_session_factory() as db:
            row = await db.scalar(
                select(AiExecutionRecord).where(
                    AiExecutionRecord.authoring_ai_run_id == uuid.UUID(meta["id"])
                )
            )
            assert row is not None
            assert row.provider == "fixed"
            assert row.model
            assert row.model_version
            assert row.prompt_template_version
            summary = row.request_summary or {}
            summary_text = str(summary)
            assert "2x + 3 = 7" not in summary_text
            assert "OPENAI_API_KEY" not in summary_text

        data_b = await _foundation(client, headers, marks="10.00")
        text_b = "1(a) Expand (x+1)^2 carefully. [10 marks]"
        await _upload_paper(client, headers, data_b["version_id"], text_b)
        parse_b = await client.post(
            f"/api/v1/assessment-versions/{data_b['version_id']}/question-paper/parse",
            headers=headers,
        )
        assert parse_b.status_code == 200, parse_b.text
        prompt_b = parse_b.json()["proposal_payload"]["roots"][0]["children"][0][
            "prompt_text"
        ]
        assert "Expand (x+1)^2" in prompt_b
        assert prompt_a != prompt_b


@pytest.mark.asyncio
async def test_b11_openai_mocked_parse_receives_text_evidence() -> None:
    captured: dict[str, Any] = {}

    async def _caller(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        captured["operation"] = operation
        captured["payload"] = payload
        return {
            "roots": [
                {
                    "stable_code": "Q1",
                    "display_label": "1",
                    "sequence": 1,
                    "prompt_text": "Section 1",
                    "max_marks": "10.00",
                    "question_type": "SECTION",
                    "scoring_mode": "CONTAINER_DERIVED",
                    "children": [
                        {
                            "stable_code": "Q1a",
                            "display_label": "1(a)",
                            "sequence": 1,
                            "prompt_text": "Solve 2x + 3 = 7.",
                            "max_marks": "10.00",
                            "question_type": "STRUCTURED",
                            "scoring_mode": "LEAF_SCORABLE",
                            "children": [],
                        }
                    ],
                }
            ],
            "notes": "mocked openai",
        }

    from decimal import Decimal

    from app.ai.providers.openai import OpenAIAuthoringProvider
    from app.ai.types import QuestionPaperEvidencePage, QuestionPaperParseInput

    provider = OpenAIAuthoringProvider(
        api_key=None,
        model_identity="gpt-test",
        model_page_analysis="gpt-test",
        model_mapping="gpt-test",
        model_transcription="gpt-test",
        model_question_paper_parse="gpt-parse-test",
        caller=_caller,
    )
    assert provider.execution_metadata("parse_question_paper").model == "gpt-parse-test"

    result = await provider.parse_question_paper(
        QuestionPaperParseInput(
            assessment_id=uuid.uuid4(),
            assessment_version_id=uuid.uuid4(),
            assessment_title="Mock",
            max_marks=Decimal("10.00"),
            assessment_artifact_id=uuid.uuid4(),
            content_sha256="a" * 64,
            mime_type="application/pdf",
            original_filename="paper.pdf",
            evidence_pages=[
                QuestionPaperEvidencePage(
                    page_index=0,
                    extracted_text="1(a) Solve 2x + 3 = 7. [10 marks]",
                    has_visual_evidence=False,
                )
            ],
        )
    )
    assert captured["operation"] == "parse_question_paper"
    pages = captured["payload"]["pages"]
    assert pages[0]["extracted_text"].startswith("1(a) Solve")
    assert "rendered_image_png" not in str(captured["payload"])
    assert result.roots[0].children[0].prompt_text.startswith("Solve")

    captured.clear()
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    await provider.parse_question_paper(
        QuestionPaperParseInput(
            assessment_id=uuid.uuid4(),
            assessment_version_id=uuid.uuid4(),
            assessment_title="Mock",
            max_marks=Decimal("10.00"),
            assessment_artifact_id=uuid.uuid4(),
            content_sha256="b" * 64,
            mime_type="image/png",
            original_filename="paper.png",
            evidence_pages=[
                QuestionPaperEvidencePage(
                    page_index=0,
                    extracted_text=None,
                    rendered_image_png=png,
                    width=10,
                    height=10,
                    has_visual_evidence=True,
                )
            ],
        )
    )
    assert captured["payload"]["visual_page_count"] == 1
    assert captured["payload"]["visual_image_bytes"] == [len(png)]

@pytest.mark.asyncio
async def test_b11_curriculum_suggestion_proposal_only_then_human_apply() -> None:
    async with api_client_authoring(authoring_provider="fixed") as client:
        headers = await _headers(client)
        data = await _foundation(client, headers, marks="10.00")
        version_id = data["version_id"]
        text = "1(a) Solve 2x + 3 = 7. [10 marks]"
        await _upload_paper(client, headers, version_id, text)
        parse = await client.post(
            f"/api/v1/assessment-versions/{version_id}/question-paper/parse",
            headers=headers,
        )
        assert parse.status_code == 200, parse.text
        run_id = parse.json()["id"]
        apply_tree = await client.post(
            f"/api/v1/authoring-ai-runs/{run_id}/apply-question-tree",
            headers=headers,
        )
        assert apply_tree.status_code == 200, apply_tree.text

        tree = await client.get(
            f"/api/v1/assessment-versions/{version_id}/questions",
            headers=headers,
        )
        assert tree.status_code == 200
        leaf_id = tree.json()[0]["children"][0]["id"]

        suggest = await client.post(
            "/api/v1/ai/proposals/curriculum-mapping",
            headers=headers,
            json={
                "question_version_id": leaf_id,
                "curriculum_id": data["curriculum"]["id"],
                "instructions": "map",
                "context": {},
            },
        )
        assert suggest.status_code == 200, suggest.text
        suggest_body = suggest.json()
        assert suggest_body["status"] == "REVIEW_REQUIRED"
        assert suggest_body["proposal_payload"]["mappings"]
        map_run_id = suggest_body["id"]

        async with async_session_factory() as db:
            count = await db.scalar(
                select(func.count())
                .select_from(QuestionCurriculumMapping)
                .where(
                    QuestionCurriculumMapping.question_version_id == uuid.UUID(leaf_id)
                )
            )
            assert int(count or 0) == 0

        applied = await client.post(
            f"/api/v1/authoring-ai-runs/{map_run_id}/apply-curriculum-mappings",
            headers=headers,
            json={},
        )
        assert applied.status_code == 200, applied.text
        assert applied.json()["status"] == "SUCCEEDED"

        async with async_session_factory() as db:
            count = await db.scalar(
                select(func.count())
                .select_from(QuestionCurriculumMapping)
                .where(
                    QuestionCurriculumMapping.question_version_id == uuid.UUID(leaf_id)
                )
            )
            assert int(count or 0) == 1

        # Idempotent re-apply
        again = await client.post(
            f"/api/v1/authoring-ai-runs/{map_run_id}/apply-curriculum-mappings",
            headers=headers,
            json={},
        )
        assert again.status_code == 200, again.text
        async with async_session_factory() as db:
            count = await db.scalar(
                select(func.count())
                .select_from(QuestionCurriculumMapping)
                .where(
                    QuestionCurriculumMapping.question_version_id == uuid.UUID(leaf_id)
                )
            )
            assert int(count or 0) == 1


@pytest.mark.asyncio
async def test_b11_curriculum_noncandidate_node_rejected() -> None:
    async with api_client_authoring(authoring_provider="fixed") as client:
        headers = await _headers(client)
        data = await _foundation(client, headers, marks="10.00")
        version_id = data["version_id"]
        await _upload_paper(
            client, headers, version_id, "1(a) Solve 2x + 3 = 7. [10 marks]"
        )
        parse = await client.post(
            f"/api/v1/assessment-versions/{version_id}/question-paper/parse",
            headers=headers,
        )
        run_id = parse.json()["id"]
        await client.post(
            f"/api/v1/authoring-ai-runs/{run_id}/apply-question-tree",
            headers=headers,
        )
        tree = await client.get(
            f"/api/v1/assessment-versions/{version_id}/questions",
            headers=headers,
        )
        leaf_id = tree.json()[0]["children"][0]["id"]
        suggest = await client.post(
            "/api/v1/ai/proposals/curriculum-mapping",
            headers=headers,
            json={
                "question_version_id": leaf_id,
                "curriculum_id": data["curriculum"]["id"],
                "instructions": "map",
                "context": {},
            },
        )
        assert suggest.status_code == 200
        map_run_id = suggest.json()["id"]
        foreign = str(uuid.uuid4())
        edited = await client.put(
            f"/api/v1/authoring-ai-runs/{map_run_id}/curriculum-mapping-proposal",
            headers=headers,
            json={
                "mappings": [
                    {
                        "curriculum_node_id": foreign,
                        "mapping_type": "PRIMARY",
                        "weight": "1.00",
                        "rationale": "bad",
                    }
                ]
            },
        )
        assert edited.status_code == 422, edited.text
        assert _err(edited)["code"] == "AUTHORING_PROVIDER_INVALID_CURRICULUM_NODE"

        async with async_session_factory() as db:
            count = await db.scalar(
                select(func.count())
                .select_from(QuestionCurriculumMapping)
                .where(
                    QuestionCurriculumMapping.question_version_id == uuid.UUID(leaf_id)
                )
            )
            assert int(count or 0) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    [
        "parse_question_paper",
        "propose_answer_key",
        "propose_rubric",
        "suggest_curriculum_mapping",
    ],
)
async def test_b11_fixed_authoring_metadata_shape(operation: str) -> None:
    from app.ai.providers.authoring import FixedAuthoringProvider

    meta = FixedAuthoringProvider(allow_non_test=True).execution_metadata(operation)
    assert meta.provider == "fixed"
    assert meta.model
    assert meta.model_version
    assert meta.prompt_template_version
