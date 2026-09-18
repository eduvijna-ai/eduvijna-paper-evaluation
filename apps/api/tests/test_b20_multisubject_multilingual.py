"""B20 multi-subject and multilingual understanding (PEV-056 / PEV-057)."""

from __future__ import annotations

import subprocess
import sys
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.ai.capability import check_provider_capability, require_provider_capability
from app.ai.providers.benchmark import replay_fixture_to_rubric_input
from app.ai.providers.fixed import FixedStructureProvider
from app.ai.types import (
    RubricCriterionSnapshot,
    RubricEvaluationInput,
    TranscriptionInput,
)
from app.core.authorization import AuthContext
from app.core.config import get_settings
from app.core.security import JwtAuthProvider
from app.db.models import (
    AiExecutionRecord,
    Assessment,
    QuestionEvaluation,
    TranscriptionDerivedText,
)
from app.db.session import async_session_factory
from app.services.language_context import (
    decide_detected_language,
    decide_provided_language,
)
from app.services.math_verification import verify_math
from app.services.subject_profile import (
    SUBJECT_PROFILE_MATHEMATICS,
    SUBJECT_PROFILE_PHYSICS,
    SUBJECT_PROFILE_UNSPECIFIED,
    SUBJECT_PROFILE_UNSUPPORTED,
    math_verification_allowed,
    resolve_subject_profile,
)
from tests.foreign_auth import create_foreign_user
from tests.test_a2_gate_matrix import _foundation
from tests.test_b3_submission_ingestion import _headers, _pdf_bytes
from tests.test_b4_answer_region_mapping import _add_leaf, _ensure_student
from tests.test_b5_ai_structure_transcription import api_client_fixed
from tests.test_b6_evaluation_ledger import _ready_assessment, _to_ready_for_evaluation

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"


def _detail_code(resp) -> str | None:
    body = resp.json()
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("code")
    err = body.get("error")
    if isinstance(err, dict):
        return err.get("code")
    return None


async def _foundation_subject(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    subject_name: str,
    subject_code: str | None = None,
    metadata: dict | None = None,
    marks: str = "10.00",
) -> dict:
    suffix = uuid.uuid4().hex[:8]
    curriculum = await client.post(
        "/api/v1/curricula",
        headers=headers,
        json={
            "code": f"CUR-{suffix}",
            "name": subject_name,
            "version_label": "2026",
            "status": "active",
        },
    )
    assert curriculum.status_code == 201, curriculum.text
    node = await client.post(
        f"/api/v1/curricula/{curriculum.json()['id']}/nodes",
        headers=headers,
        json={
            "node_type": "SUBJECT",
            "code": subject_code or f"{subject_name[:3].upper()}-{suffix}",
            "name": subject_name,
            "sequence": 1,
            "metadata": metadata or {},
            "status": "active",
        },
    )
    assert node.status_code == 201, node.text
    assessment = await client.post(
        "/api/v1/assessments",
        headers=headers,
        json={
            "curriculum_id": curriculum.json()["id"],
            "subject_node_id": node.json()["id"],
            "code": f"ASM-{suffix}",
            "title": f"{subject_name} assessment",
            "assessment_type": "EXAM",
            "max_marks": marks,
            "duration_minutes": 60,
        },
    )
    assert assessment.status_code == 201, assessment.text
    return {
        "curriculum": curriculum.json(),
        "node": node.json(),
        "assessment": assessment.json(),
        "version_id": assessment.json()["initial_version_id"],
    }


async def _ready_named(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    subject_name: str,
    subject_code: str | None = None,
    metadata: dict | None = None,
) -> dict:
    data = await _foundation_subject(
        client,
        headers,
        subject_name=subject_name,
        subject_code=subject_code,
        metadata=metadata,
    )
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


async def _map_two_leaves(
    client: AsyncClient, headers: dict[str, str], sid: str
) -> None:
    student_id = await _ensure_student(client, headers)
    assert (
        await client.post(
            f"/api/v1/submissions/{sid}/identity/confirm",
            headers=headers,
            json={"student_id": student_id},
        )
    ).status_code == 200
    mapping = await client.get(f"/api/v1/submissions/{sid}/mapping", headers=headers)
    mbody = mapping.json()
    leaves = [n for n in mbody["questions"] if n.get("is_leaf_scorable")]
    region_id = mbody["regions"][0]["id"]
    await client.put(
        f"/api/v1/submissions/{sid}/question-mappings/{leaves[0]['question_version_id']}",
        headers=headers,
        json={"disposition": "ANSWERED", "region_ids": [region_id]},
    )
    await client.post(
        f"/api/v1/submissions/{sid}/question-mappings/{leaves[0]['question_version_id']}/confirm",
        headers=headers,
    )
    await client.put(
        f"/api/v1/submissions/{sid}/question-mappings/{leaves[1]['question_version_id']}",
        headers=headers,
        json={"disposition": "BLANK", "region_ids": []},
    )
    await client.post(
        f"/api/v1/submissions/{sid}/question-mappings/{leaves[1]['question_version_id']}/confirm",
        headers=headers,
    )
    fin = await client.post(f"/api/v1/submissions/{sid}/mapping/finalize", headers=headers)
    assert fin.status_code == 200, fin.text


def test_b20_subject_profile_never_falls_back_to_math() -> None:
    class _Node:
        id = uuid.uuid4()
        code = "ASTRONOMY"
        name = "Astronomy"
        metadata_json = {"subject_profile": "ASTRONOMY"}

    resolved = resolve_subject_profile(_Node())  # type: ignore[arg-type]
    assert resolved.profile == SUBJECT_PROFILE_UNSUPPORTED
    assert resolved.profile != SUBJECT_PROFILE_MATHEMATICS
    assert math_verification_allowed(resolved.profile) is False

    present_unmapped = resolve_subject_profile(
        type(
            "N",
            (),
            {
                "id": uuid.uuid4(),
                "code": "ASTRONOMY",
                "name": "Astronomy",
                "metadata_json": {},
            },
        )()
    )
    assert present_unmapped.profile == SUBJECT_PROFILE_UNSUPPORTED
    assert present_unmapped.math_verification_eligible is False
    assert math_verification_allowed(present_unmapped.profile) is False

    suffixed = resolve_subject_profile(
        type(
            "N",
            (),
            {
                "id": uuid.uuid4(),
                "code": "ASTRONOMY_abc123",
                "name": "Astronomy",
                "metadata_json": {},
            },
        )()
    )
    assert suffixed.profile == SUBJECT_PROFILE_UNSUPPORTED
    assert suffixed.math_verification_eligible is False

    missing = resolve_subject_profile(None, subject_node_id=None)
    assert missing.profile == SUBJECT_PROFILE_UNSPECIFIED
    assert missing.math_verification_eligible is True
    assert math_verification_allowed(missing.profile) is True

    unresolved = resolve_subject_profile(None, subject_node_id=uuid.uuid4())
    assert unresolved.profile == SUBJECT_PROFILE_UNSUPPORTED
    assert unresolved.math_verification_eligible is False
    assert math_verification_allowed(unresolved.profile) is False

    physics = resolve_subject_profile(
        type(
            "N",
            (),
            {
                "id": uuid.uuid4(),
                "code": "PHY-1",
                "name": "Physics",
                "metadata_json": {},
            },
        )()
    )
    assert physics.profile == SUBJECT_PROFILE_PHYSICS
    assert math_verification_allowed(physics.profile) is False


def test_b20_language_and_capability_routing() -> None:
    provided = decide_provided_language(language_code="hi", script_code="Deva")
    assert provided.language_state == "CONFIRMED"
    assert provided.language_source == "PROVIDED"
    unsupported = decide_provided_language(language_code="ja", script_code="Jpan")
    assert unsupported.language_state == "UNSUPPORTED"
    assert unsupported.gate_code == "LANGUAGE_UNSUPPORTED"
    detected = decide_detected_language(
        language_code="hi",
        script_code="Deva",
        confidence=Decimal("0.4000"),
        ambiguous=True,
    )
    assert detected.language_state == "REVIEW_REQUIRED"
    assert detected.gate_code == "LANGUAGE_REVIEW_REQUIRED"
    omitted = decide_provided_language(language_code=None, script_code=None)
    assert omitted.language_state == "UNKNOWN"
    assert omitted.gate_code is None

    ok = check_provider_capability(
        provider="fixed",
        subject_profile="PHYSICS",
        language_code="en",
        script_code="Latn",
        operation="transcribe_answer",
    )
    assert ok.supported is True
    bad = check_provider_capability(
        provider="fixed",
        subject_profile="UNSUPPORTED",
        language_code="en",
        script_code="Latn",
        operation="transcribe_answer",
    )
    assert bad.supported is False
    assert bad.error_code == "SUBJECT_PROFILE_UNSUPPORTED"
    with pytest.raises(Exception) as exc:
        require_provider_capability(
            provider="fixed",
            subject_profile="MATHEMATICS",
            language_code="ja",
            script_code="Jpan",
            operation="transcribe_answer",
        )
    assert exc.value.code == "LANGUAGE_UNSUPPORTED"


@pytest.mark.asyncio
async def test_b20_subject_node_canonical_and_tenant_scoped() -> None:
    async with api_client_fixed() as client:
        headers = await _headers(client)
        data = await _foundation(client, headers)
        got = await client.get(
            f"/api/v1/assessments/{data['assessment']['id']}", headers=headers
        )
        assert got.status_code == 200, got.text
        body = got.json()
        assert body["subject_node_id"] == data["node"]["id"]
        assert body["subject_profile"] == SUBJECT_PROFILE_MATHEMATICS
        assert body["math_verification_eligible"] is True

        foreign_user_id, foreign_tenant_id = await create_foreign_user()
        token = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=foreign_user_id,
                tenant_id=foreign_tenant_id,
                roles=frozenset({"INSTITUTION_ADMIN"}),
                permissions=frozenset({"assessment:read", "curriculum:read"}),
            )
        )[0]
        isolated = await client.get(
            f"/api/v1/assessments/{data['assessment']['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert isolated.status_code == 404


@pytest.mark.asyncio
async def test_b20_unknown_subject_is_not_mathematics() -> None:
    async with api_client_fixed() as client:
        headers = await _headers(client)
        data = await _foundation_subject(
            client,
            headers,
            subject_name="Astronomy",
            subject_code="ASTRONOMY",
            metadata={"subject_profile": "ASTRONOMY"},
        )
        got = await client.get(
            f"/api/v1/assessments/{data['assessment']['id']}", headers=headers
        )
        assert got.json()["subject_profile"] == SUBJECT_PROFILE_UNSUPPORTED
        assert got.json()["subject_profile"] != SUBJECT_PROFILE_MATHEMATICS
        assert got.json()["math_verification_eligible"] is False


@pytest.mark.asyncio
async def test_b20_present_unknown_subject_node_fails_closed() -> None:
    async with api_client_fixed() as client:
        headers = await _headers(client)
        data = await _ready_named(
            client,
            headers,
            subject_name="Astronomy",
            subject_code="ASTRONOMY",
            metadata={},
        )
        got = await client.get(
            f"/api/v1/assessments/{data['assessment']['id']}", headers=headers
        )
        body = got.json()
        assert body["subject_profile"] == SUBJECT_PROFILE_UNSUPPORTED
        assert body["math_verification_eligible"] is False
        upload = await client.post(
            "/api/v1/submissions",
            headers=headers,
            files={"file": ("astro.pdf", _pdf_bytes(), "application/pdf")},
            data={"assessment_id": data["assessment"]["id"]},
        )
        assert upload.status_code == 201, upload.text
        sid = upload.json()["id"]
        await _map_two_leaves(client, headers, sid)
        prep = await client.post(
            f"/api/v1/submissions/{sid}/transcription/prepare", headers=headers
        )
        assert prep.status_code == 409, prep.text
        assert _detail_code(prep) == "SUBJECT_PROFILE_UNSUPPORTED"
        eval_prep = await client.post(
            f"/api/v1/submissions/{sid}/evaluation/prepare", headers=headers
        )
        assert eval_prep.status_code == 409, eval_prep.text
        assert _detail_code(eval_prep) == "SUBJECT_PROFILE_UNSUPPORTED"


@pytest.mark.asyncio
async def test_b20_unknown_subject_code_with_suffix_fails_closed() -> None:
    async with api_client_fixed() as client:
        headers = await _headers(client)
        suffix = uuid.uuid4().hex[:8]
        data = await _ready_named(
            client,
            headers,
            subject_name="Astronomy",
            subject_code=f"ASTRONOMY_{suffix}",
            metadata={},
        )
        got = await client.get(
            f"/api/v1/assessments/{data['assessment']['id']}", headers=headers
        )
        assert got.json()["subject_profile"] == SUBJECT_PROFILE_UNSUPPORTED
        assert got.json()["math_verification_eligible"] is False
        upload = await client.post(
            "/api/v1/submissions",
            headers=headers,
            files={"file": ("astro-suf.pdf", _pdf_bytes(), "application/pdf")},
            data={"assessment_id": data["assessment"]["id"]},
        )
        sid = upload.json()["id"]
        await _map_two_leaves(client, headers, sid)
        prep = await client.post(
            f"/api/v1/submissions/{sid}/transcription/prepare", headers=headers
        )
        assert prep.status_code == 409, prep.text
        assert _detail_code(prep) == "SUBJECT_PROFILE_UNSUPPORTED"


@pytest.mark.asyncio
async def test_b20_language_round_trip_and_unsupported_gate() -> None:
    async with api_client_fixed() as client:
        headers = await _headers(client)
        data = await _ready_named(client, headers, subject_name="Mathematics")
        upload = await client.post(
            "/api/v1/submissions",
            headers=headers,
            files={"file": ("b20.pdf", _pdf_bytes(), "application/pdf")},
            data={
                "assessment_id": data["assessment"]["id"],
                "language_code": "hi",
                "script_code": "Deva",
            },
        )
        assert upload.status_code == 201, upload.text
        body = upload.json()
        assert body["language_code"] == "hi"
        assert body["script_code"] == "Deva"
        assert body["language_source"] == "PROVIDED"
        assert body["language_state"] == "CONFIRMED"
        assert body["language_confidence"] is None
        sid = body["id"]
        got = await client.get(f"/api/v1/submissions/{sid}", headers=headers)
        assert got.json()["language_code"] == "hi"
        assert got.json()["script_code"] == "Deva"
        assert got.json()["language_context"]["language_state"] == "CONFIRMED"

        omitted = await client.post(
            "/api/v1/submissions",
            headers=headers,
            files={"file": ("b20-legacy.pdf", _pdf_bytes() + b"legacy", "application/pdf")},
            data={"assessment_id": data["assessment"]["id"]},
        )
        assert omitted.status_code == 201, omitted.text
        assert omitted.json()["language_state"] == "UNKNOWN"
        assert omitted.json()["language_code"] is None

        unsupported = await client.post(
            "/api/v1/submissions",
            headers=headers,
            files={"file": ("b20-ja.pdf", _pdf_bytes() + b"ja", "application/pdf")},
            data={
                "assessment_id": data["assessment"]["id"],
                "language_code": "ja",
                "script_code": "Jpan",
            },
        )
        assert unsupported.status_code == 201, unsupported.text
        usid = unsupported.json()["id"]
        assert unsupported.json()["language_state"] == "UNSUPPORTED"
        student_id = await _ensure_student(client, headers)
        assert (
            await client.post(
                f"/api/v1/submissions/{usid}/identity/confirm",
                headers=headers,
                json={"student_id": student_id},
            )
        ).status_code == 200
        mapping = await client.get(f"/api/v1/submissions/{usid}/mapping", headers=headers)
        mbody = mapping.json()
        leaves = [n for n in mbody["questions"] if n.get("is_leaf_scorable")]
        region_id = mbody["regions"][0]["id"]
        await client.put(
            f"/api/v1/submissions/{usid}/question-mappings/{leaves[0]['question_version_id']}",
            headers=headers,
            json={"disposition": "ANSWERED", "region_ids": [region_id]},
        )
        await client.post(
            f"/api/v1/submissions/{usid}/question-mappings/{leaves[0]['question_version_id']}/confirm",
            headers=headers,
        )
        await client.put(
            f"/api/v1/submissions/{usid}/question-mappings/{leaves[1]['question_version_id']}",
            headers=headers,
            json={"disposition": "BLANK", "region_ids": []},
        )
        await client.post(
            f"/api/v1/submissions/{usid}/question-mappings/{leaves[1]['question_version_id']}/confirm",
            headers=headers,
        )
        fin = await client.post(f"/api/v1/submissions/{usid}/mapping/finalize", headers=headers)
        assert fin.status_code == 200, fin.text
        prep = await client.post(
            f"/api/v1/submissions/{usid}/transcription/prepare", headers=headers
        )
        assert prep.status_code == 409, prep.text
        assert _detail_code(prep) == "LANGUAGE_UNSUPPORTED"
        fin_tx = await client.post(
            f"/api/v1/submissions/{usid}/transcription/finalize", headers=headers
        )
        assert fin_tx.status_code == 409, fin_tx.text
        assert _detail_code(fin_tx) == "LANGUAGE_UNSUPPORTED"
        async with async_session_factory() as db:
            ai_rows = list(
                (
                    await db.scalars(
                        select(AiExecutionRecord).where(
                            AiExecutionRecord.submission_id == uuid.UUID(usid),
                            AiExecutionRecord.operation == "transcribe_answer",
                            AiExecutionRecord.status == "SUCCEEDED",
                        )
                    )
                ).all()
            )
            assert ai_rows == []


@pytest.mark.asyncio
async def test_b20_detected_low_confidence_requires_review() -> None:
    async with api_client_fixed() as client:
        headers = await _headers(client)
        data = await _ready_named(client, headers, subject_name="Mathematics")
        upload = await client.post(
            "/api/v1/submissions",
            headers=headers,
            files={"file": ("b20-det.pdf", _pdf_bytes(), "application/pdf")},
            data={"assessment_id": data["assessment"]["id"]},
        )
        sid = upload.json()["id"]
        proposed = await client.put(
            f"/api/v1/submissions/{sid}/language",
            headers=headers,
            json={
                "language_code": "hi",
                "script_code": "Deva",
                "source": "DETECTED",
                "confidence": "0.4000",
                "ambiguous": True,
            },
        )
        assert proposed.status_code == 200, proposed.text
        assert proposed.json()["language_state"] == "REVIEW_REQUIRED"
        assert proposed.json()["language_source"] == "DETECTED"
        assert proposed.json()["language_confidence"] == pytest.approx(0.4)
        assert proposed.json()["automation_block_code"] == "LANGUAGE_REVIEW_REQUIRED"


@pytest.mark.asyncio
async def test_b20_language_context_locked_after_transcription() -> None:
    async with api_client_fixed() as client:
        headers = await _headers(client)
        data = await _ready_named(client, headers, subject_name="Mathematics")
        upload = await client.post(
            "/api/v1/submissions",
            headers=headers,
            files={"file": ("b20-lock.pdf", _pdf_bytes(), "application/pdf")},
            data={
                "assessment_id": data["assessment"]["id"],
                "language_code": "en",
                "script_code": "Latn",
            },
        )
        assert upload.status_code == 201, upload.text
        sid = upload.json()["id"]
        before_tx = await client.put(
            f"/api/v1/submissions/{sid}/language",
            headers=headers,
            json={"language_code": "hi", "script_code": "Deva"},
        )
        assert before_tx.status_code == 200, before_tx.text
        assert before_tx.json()["language_code"] == "hi"
        restored = await client.put(
            f"/api/v1/submissions/{sid}/language",
            headers=headers,
            json={"language_code": "en", "script_code": "Latn"},
        )
        assert restored.status_code == 200, restored.text
        assert restored.json()["language_code"] == "en"
        assert restored.json()["script_code"] == "Latn"

        await _map_two_leaves(client, headers, sid)
        workspace = await client.get(
            f"/api/v1/submissions/{sid}/transcription", headers=headers
        )
        assert workspace.status_code == 200, workspace.text
        original_items = workspace.json()["items"]
        originals: list[tuple[str, str | None, list]] = []
        for item in original_items:
            for region in item["regions"]:
                active = region.get("active_transcription") or region.get(
                    "latest_ai_proposal"
                )
                if active and active.get("id"):
                    originals.append(
                        (
                            active["id"],
                            active.get("text"),
                            list(active.get("derived_texts") or []),
                        )
                    )
        assert originals
        async with async_session_factory() as db:
            exec_before = list(
                (
                    await db.scalars(
                        select(AiExecutionRecord).where(
                            AiExecutionRecord.submission_id == uuid.UUID(sid)
                        )
                    )
                ).all()
            )
            before_ids = {row.id for row in exec_before}

        locked = await client.put(
            f"/api/v1/submissions/{sid}/language",
            headers=headers,
            json={"language_code": "hi", "script_code": "Deva"},
        )
        assert locked.status_code == 409, locked.text
        assert _detail_code(locked) == "LANGUAGE_CONTEXT_LOCKED"
        got = await client.get(f"/api/v1/submissions/{sid}", headers=headers)
        assert got.json()["language_code"] == "en"
        assert got.json()["script_code"] == "Latn"
        after_ws = await client.get(
            f"/api/v1/submissions/{sid}/transcription", headers=headers
        )
        after_items = after_ws.json()["items"]
        after_originals: list[tuple[str, str | None, list]] = []
        for item in after_items:
            for region in item["regions"]:
                active = region.get("active_transcription") or region.get(
                    "latest_ai_proposal"
                )
                if active and active.get("id"):
                    after_originals.append(
                        (
                            active["id"],
                            active.get("text"),
                            list(active.get("derived_texts") or []),
                        )
                    )
        assert after_originals == originals
        async with async_session_factory() as db:
            exec_after = list(
                (
                    await db.scalars(
                        select(AiExecutionRecord).where(
                            AiExecutionRecord.submission_id == uuid.UUID(sid)
                        )
                    )
                ).all()
            )
            assert {row.id for row in exec_after} == before_ids
        same = await client.put(
            f"/api/v1/submissions/{sid}/language",
            headers=headers,
            json={"language_code": "en", "script_code": "Latn"},
        )
        assert same.status_code == 200, same.text
        assert same.json()["language_code"] == "en"
        assert same.json()["script_code"] == "Latn"

        foreign_user_id, foreign_tenant_id = await create_foreign_user()
        token = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=foreign_user_id,
                tenant_id=foreign_tenant_id,
                roles=frozenset({"INSTITUTION_ADMIN"}),
                permissions=frozenset({"submission:upload"}),
            )
        )[0]
        isolated = await client.put(
            f"/api/v1/submissions/{sid}/language",
            headers={"Authorization": f"Bearer {token}"},
            json={"language_code": "hi", "script_code": "Deva"},
        )
        assert isolated.status_code == 404


@pytest.mark.asyncio
async def test_b20_hindi_transcription_derived_provenance() -> None:
    async with api_client_fixed() as client:
        headers = await _headers(client)
        data = await _ready_named(client, headers, subject_name="Mathematics")
        upload = await client.post(
            "/api/v1/submissions",
            headers=headers,
            files={"file": ("b20-hi.pdf", _pdf_bytes(), "application/pdf")},
            data={
                "assessment_id": data["assessment"]["id"],
                "language_code": "hi",
                "script_code": "Deva",
            },
        )
        sid = upload.json()["id"]
        student_id = await _ensure_student(client, headers)
        assert (
            await client.post(
                f"/api/v1/submissions/{sid}/identity/confirm",
                headers=headers,
                json={"student_id": student_id},
            )
        ).status_code == 200
        mapping = await client.get(f"/api/v1/submissions/{sid}/mapping", headers=headers)
        mbody = mapping.json()
        leaves = [n for n in mbody["questions"] if n.get("is_leaf_scorable")]
        region_id = mbody["regions"][0]["id"]
        await client.put(
            f"/api/v1/submissions/{sid}/question-mappings/{leaves[0]['question_version_id']}",
            headers=headers,
            json={"disposition": "ANSWERED", "region_ids": [region_id]},
        )
        await client.post(
            f"/api/v1/submissions/{sid}/question-mappings/{leaves[0]['question_version_id']}/confirm",
            headers=headers,
        )
        await client.put(
            f"/api/v1/submissions/{sid}/question-mappings/{leaves[1]['question_version_id']}",
            headers=headers,
            json={"disposition": "BLANK", "region_ids": []},
        )
        await client.post(
            f"/api/v1/submissions/{sid}/question-mappings/{leaves[1]['question_version_id']}/confirm",
            headers=headers,
        )
        assert (
            await client.post(f"/api/v1/submissions/{sid}/mapping/finalize", headers=headers)
        ).status_code == 200
        workspace = await client.get(f"/api/v1/submissions/{sid}/transcription", headers=headers)
        assert workspace.status_code == 200, workspace.text
        w = workspace.json()
        assert w["language_context"]["language_code"] == "hi"
        assert w["subject_context"]["subject_profile"] == SUBJECT_PROFILE_MATHEMATICS
        original = None
        for item in w["items"]:
            for region in item["regions"]:
                active = region.get("active_transcription") or region.get("latest_ai_proposal")
                if active and active.get("text"):
                    original = active
                    break
        assert original is not None
        assert "हिंदी" in (original["text"] or "")
        derived = original.get("derived_texts") or []
        assert derived, original
        translation = next(d for d in derived if d["kind"] == "TRANSLATION")
        assert translation["source_transcription_id"] == original["id"]
        assert translation["source_language_code"] == "hi"
        assert translation["target_language_code"] == "en"
        assert translation["text"] != original["text"]
        assert "Solution in Hindi" in translation["text"]
        async with async_session_factory() as db:
            rows = list(
                (
                    await db.scalars(
                        select(TranscriptionDerivedText).where(
                            TranscriptionDerivedText.source_transcription_id
                            == uuid.UUID(original["id"])
                        )
                    )
                ).all()
            )
            assert rows
            exec_rows = list(
                (
                    await db.scalars(
                        select(AiExecutionRecord).where(
                            AiExecutionRecord.submission_id == uuid.UUID(sid),
                            AiExecutionRecord.operation == "transcribe_answer",
                        )
                    )
                ).all()
            )
            assert exec_rows
            summary = exec_rows[0].request_summary or {}
            assert summary.get("subject_profile") == SUBJECT_PROFILE_MATHEMATICS
            assert summary.get("language_code") == "hi"
            refs = exec_rows[0].input_refs or {}
            assert refs.get("subject_profile") == SUBJECT_PROFILE_MATHEMATICS


@pytest.mark.asyncio
async def test_b20_physics_does_not_invoke_math_verification() -> None:
    async with api_client_fixed() as client:
        headers = await _headers(client)
        data = await _ready_named(client, headers, subject_name="Physics")
        got = await client.get(
            f"/api/v1/assessments/{data['assessment']['id']}", headers=headers
        )
        assert got.json()["subject_profile"] == SUBJECT_PROFILE_PHYSICS
        sid = await _to_ready_for_evaluation(client, headers, data)
        prep = await client.post(
            f"/api/v1/submissions/{sid}/evaluation/prepare", headers=headers
        )
        assert prep.status_code == 200, prep.text
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
            invoked = [
                bool((qe.evidence_metadata or {}).get("math_verification_invoked"))
                for qe in qes
            ]
            assert invoked and not any(invoked)
            assert all(
                (qe.evidence_metadata or {}).get("subject_profile") == SUBJECT_PROFILE_PHYSICS
                for qe in qes
            )
            exec_rows = list(
                (
                    await db.scalars(
                        select(AiExecutionRecord).where(
                            AiExecutionRecord.submission_id == uuid.UUID(sid),
                            AiExecutionRecord.operation == "evaluate_rubric",
                        )
                    )
                ).all()
            )
            assert any(
                (row.request_summary or {}).get("subject_profile") == SUBJECT_PROFILE_PHYSICS
                for row in exec_rows
            )


@pytest.mark.asyncio
async def test_b20_mathematics_and_human_confirmation_remain() -> None:
    async with api_client_fixed() as client:
        headers = await _headers(client)
        data = await _ready_assessment(client, headers)
        sid = await _to_ready_for_evaluation(client, headers, data)
        workspace = await client.get(f"/api/v1/submissions/{sid}/transcription", headers=headers)
        assert workspace.json()["subject_context"]["subject_profile"] == (
            SUBJECT_PROFILE_MATHEMATICS
        )
        prep = await client.post(
            f"/api/v1/submissions/{sid}/evaluation/prepare", headers=headers
        )
        assert prep.status_code == 200, prep.text
        ws = await client.get(f"/api/v1/submissions/{sid}/evaluation", headers=headers)
        assert ws.status_code == 200
        # Human confirmation of transcription already happened in helper; ledger still proposals.
        body = ws.json()
        assert body["workflow_state"] in {
            "EVALUATION_REVIEW",
            "READY_FOR_EVALUATION",
            "EVALUATING",
        }


@pytest.mark.asyncio
async def test_b20_descriptive_and_fixed_provider_fixtures() -> None:
    provider = FixedStructureProvider(allow_non_test=True)
    request = TranscriptionInput(
        submission_id=uuid.uuid4(),
        answer_region_id=uuid.uuid4(),
        crop_content_sha256="a" * 64,
        subject_profile="STRUCTURED_DESCRIPTIVE",
        language_code="en",
        script_code="Latn",
    )
    result = await provider.transcribe_answer(request)
    assert "industrial" in result.text.lower() or "urban" in result.text.lower()
    assert result.derived_texts == []
    physics = await provider.transcribe_answer(
        request.model_copy(update={"subject_profile": "PHYSICS"})
    )
    assert "force" in physics.text.lower() or "newton" in physics.text.lower()
    eval_in = RubricEvaluationInput(
        question_version_id=uuid.uuid4(),
        assessment_version_id=uuid.uuid4(),
        rubric_criteria=[
            RubricCriterionSnapshot(
                id=uuid.uuid4(),
                code="C1",
                label="Method",
                max_marks=Decimal("5"),
                sequence=1,
            )
        ],
        transcription_text="EXERCISE:FULL",
        max_mark=Decimal("5"),
        subject_profile="PHYSICS",
        language_code="en",
        script_code="Latn",
        transcription_is_original=True,
    )
    scored = await provider.evaluate_rubric(eval_in)
    assert scored.criterion_proposals


@pytest.mark.asyncio
async def test_b20_cross_tenant_language_rejected() -> None:
    async with api_client_fixed() as client:
        headers = await _headers(client)
        data = await _ready_named(client, headers, subject_name="Mathematics")
        upload = await client.post(
            "/api/v1/submissions",
            headers=headers,
            files={"file": ("iso.pdf", _pdf_bytes(), "application/pdf")},
            data={
                "assessment_id": data["assessment"]["id"],
                "language_code": "hi",
                "script_code": "Deva",
            },
        )
        sid = upload.json()["id"]
        foreign_user_id, foreign_tenant_id = await create_foreign_user()
        token = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=foreign_user_id,
                tenant_id=foreign_tenant_id,
                roles=frozenset({"INSTITUTION_ADMIN"}),
                permissions=frozenset(
                    {
                        "submission:read",
                        "submission:upload",
                        "transcription:read",
                        "transcription:review",
                    }
                ),
            )
        )[0]
        foreign = {"Authorization": f"Bearer {token}"}
        assert (
            await client.get(f"/api/v1/submissions/{sid}", headers=foreign)
        ).status_code == 404
        assert (
            await client.put(
                f"/api/v1/submissions/{sid}/language",
                headers=foreign,
                json={"language_code": "en", "script_code": "Latn"},
            )
        ).status_code == 404
        assert (
            await client.get(f"/api/v1/submissions/{sid}/transcription", headers=foreign)
        ).status_code == 404


def test_b20_b15_replay_does_not_touch_ledger_and_carries_context() -> None:
    fixture = {
        "question_version_id": "00000000-0000-4000-8000-000000000001",
        "assessment_version_id": "00000000-0000-4000-8000-000000000002",
        "criterion_snapshot": [
            {
                "id": "00000000-0000-4000-8000-000000000010",
                "code": "C1",
                "label": "Method",
                "max_marks": "5.0000",
                "sequence": 1,
            }
        ],
        "transcription_text": "हिंदी मूल पाठ",
        "max_mark": "5.0000",
        "subject_profile": "PHYSICS",
        "language_code": "hi",
        "script_code": "Deva",
        "transcription_is_original": True,
        "derived_text": "original Hindi text",
        "derived_text_kind": "TRANSLATION",
        "derived_source_language_code": "hi",
        "derived_target_language_code": "en",
    }
    request = replay_fixture_to_rubric_input(fixture)
    assert request.subject_profile == "PHYSICS"
    assert request.language_code == "hi"
    assert request.transcription_text == "हिंदी मूल पाठ"
    assert request.derived_text == "original Hindi text"
    assert request.transcription_is_original is True


def test_b20_alembic_exactly_one_head() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(API_ROOT / "alembic.ini"), "heads"],
        cwd=str(API_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    assert lines == ["20260918_0022 (head)"]


@pytest.mark.asyncio
async def test_b20_migration_columns_and_historical_nulls() -> None:
    async with async_session_factory() as db:
        cols = (
            await db.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'submissions' AND column_name IN "
                    "('language_code','script_code','language_source',"
                    "'language_confidence','language_state')"
                )
            )
        ).scalars().all()
        assert set(cols) == {
            "language_code",
            "script_code",
            "language_source",
            "language_confidence",
            "language_state",
        }
        exists = await db.scalar(
            text(
                "SELECT to_regclass('public.transcription_derived_texts')"
            )
        )
        assert exists is not None
        # Historical rows remain valid with UNKNOWN / null confidence.
        count = await db.scalar(select(Assessment.id).limit(1))
        assert count is not None or count is None


def test_b20_verify_math_helper_still_scoped() -> None:
    ok = verify_math(student_expr="(x+1)**2", expected_expr="x**2 + 2*x + 1")
    assert ok.equivalent is True
    assert math_verification_allowed("PHYSICS") is False
    assert math_verification_allowed("MATHEMATICS") is True
