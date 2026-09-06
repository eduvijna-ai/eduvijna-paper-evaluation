"""B3 submission ingestion, storage integrity, and identity review coverage."""

from __future__ import annotations

import io
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import select

from app.cli.seed_dev import ADMIN_EMAIL, ADMIN_PASSWORD, seed
from app.core.authorization import AuthContext
from app.core.config import get_settings
from app.core.security import JwtAuthProvider, hash_password
from app.db.models import PipelineJob, Submission, Tenant, User
from app.db.session import async_session_factory
from app.main import create_app
from app.services.page_normalization import PageNormalizationError, run_page_normalization
from app.services.storage import ObjectStorage, StorageImmutabilityError, raw_object_key
from app.services.upload_validation import sha256_bytes
from tests.test_a2_gate_matrix import _foundation
from tests.test_a2_review_fixes import _leaf_and_approve


def _png_bytes(color: tuple[int, int, int] = (200, 180, 160)) -> bytes:
    image = Image.new("RGB", (64, 96), color=color)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _pdf_bytes(pages: int = 2) -> bytes:
    import fitz

    doc = fitz.open()
    for index in range(pages):
        page = doc.new_page(width=200, height=280)
        page.insert_text((40, 60), f"B3 page {index + 1}")
    data = doc.tobytes()
    doc.close()
    return data


@asynccontextmanager
async def api_client() -> AsyncIterator[AsyncClient]:
    import os

    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
    os.environ["S3_ENDPOINT_URL"] = "http://127.0.0.1:19000"
    await seed()
    get_settings.cache_clear()
    from app.tasks.celery_app import celery_app

    celery_app.conf.task_always_eager = True
    ObjectStorage(get_settings()).ensure_bucket()
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        yield client


async def _headers(client: AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "tenant_slug": "demo"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _active_assessment(client: AsyncClient, headers: dict[str, str]) -> dict:
    data = await _foundation(client, headers, marks="10.00")
    await _leaf_and_approve(client, headers, data, marks="10.00")
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
async def test_upload_pdf_and_image_normalize_pages() -> None:
    async with api_client() as client:
        headers = await _headers(client)
        data = await _active_assessment(client, headers)
        assessment_id = data["assessment"]["id"]

        pdf = _pdf_bytes(2)
        upload = await client.post(
            "/api/v1/submissions",
            headers=headers,
            data={"assessment_id": assessment_id, "bundle_name": "pdf-bundle"},
            files={"file": ("sheet.pdf", pdf, "application/pdf")},
        )
        assert upload.status_code == 201, upload.text
        body = upload.json()
        assert body["storage_status"] == "AVAILABLE"
        assert body["source_content_sha256"] == sha256_bytes(pdf)
        assert body["workflow_state"] in {"UPLOADED", "PROCESSING", "IDENTITY_REVIEW"}

        # Eager Celery should finish normalization synchronously.
        detail = await client.get(f"/api/v1/submissions/{body['id']}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["workflow_state"] == "IDENTITY_REVIEW"
        assert detail.json()["page_count"] == 2
        assert detail.json()["identity_confidence"] == 0.0

        pages = await client.get(f"/api/v1/submissions/{body['id']}/pages", headers=headers)
        assert pages.status_code == 200
        assert len(pages.json()) == 2
        assert pages.json()[0]["page_index"] == 0

        image = _png_bytes()
        img_upload = await client.post(
            "/api/v1/submissions",
            headers=headers,
            data={"assessment_id": assessment_id},
            files={"file": ("page.png", image, "image/png")},
        )
        assert img_upload.status_code == 201, img_upload.text
        img_detail = await client.get(
            f"/api/v1/submissions/{img_upload.json()['id']}", headers=headers
        )
        assert img_detail.json()["page_count"] == 1


@pytest.mark.asyncio
async def test_upload_rejects_invalid_large_inactive_and_duplicates() -> None:
    async with api_client() as client:
        headers = await _headers(client)
        data = await _foundation(client, headers)
        draft_id = data["assessment"]["id"]
        active = await _active_assessment(client, headers)

        too_large = b"%PDF-1.4\n" + (b"x" * (get_settings().submission_upload_max_bytes + 1))
        assert (
            await client.post(
                "/api/v1/submissions",
                headers=headers,
                data={"assessment_id": active["assessment"]["id"]},
                files={"file": ("big.pdf", too_large, "application/pdf")},
            )
        ).status_code == 413

        disguised = b"not-a-real-pdf-or-image"
        assert (
            await client.post(
                "/api/v1/submissions",
                headers=headers,
                data={"assessment_id": active["assessment"]["id"]},
                files={"file": ("fake.pdf", disguised, "application/pdf")},
            )
        ).status_code == 400

        assert (
            await client.post(
                "/api/v1/submissions",
                headers=headers,
                data={"assessment_id": draft_id},
                files={"file": ("ok.pdf", _pdf_bytes(1), "application/pdf")},
            )
        ).status_code == 409

        pdf = _pdf_bytes(1)
        first = await client.post(
            "/api/v1/submissions",
            headers=headers,
            data={"assessment_id": active["assessment"]["id"]},
            files={"file": ("dup.pdf", pdf, "application/pdf")},
        )
        assert first.status_code == 201, first.text
        second = await client.post(
            "/api/v1/submissions",
            headers=headers,
            data={"assessment_id": active["assessment"]["id"]},
            files={"file": ("dup.pdf", pdf, "application/pdf")},
        )
        assert second.status_code == 409


@pytest.mark.asyncio
async def test_raw_storage_immutability_and_hash_mismatch() -> None:
    async with api_client() as client:
        headers = await _headers(client)
        data = await _active_assessment(client, headers)
        pdf = _pdf_bytes(1)
        upload = await client.post(
            "/api/v1/submissions",
            headers=headers,
            data={"assessment_id": data["assessment"]["id"]},
            files={"file": ("imm.pdf", pdf, "application/pdf")},
        )
        assert upload.status_code == 201, upload.text
        key = upload.json()["source_storage_key"]
        storage = ObjectStorage()
        with pytest.raises(StorageImmutabilityError):
            storage.put_raw_bytes(key=key, body=pdf, content_type="application/pdf")

        submission_id = uuid.UUID(upload.json()["id"])
        async with async_session_factory() as db:
            submission = await db.scalar(select(Submission).where(Submission.id == submission_id))
            assert submission is not None
            # Corrupt persisted hash to force integrity failure on re-run.
            submission.source_content_sha256 = "0" * 64
            job = await db.scalar(
                select(PipelineJob).where(PipelineJob.submission_id == submission_id)
            )
            assert job is not None
            job.status = "QUEUED"
            job.idempotency_key = f"page-norm:{submission_id}:retry"
            await db.commit()
            job_id = job.id
            tenant_id = submission.tenant_id

        with pytest.raises(PageNormalizationError):
            async with async_session_factory() as db:
                await run_page_normalization(
                    db,
                    tenant_id=tenant_id,
                    submission_id=submission_id,
                    job_id=job_id,
                )

        async with async_session_factory() as db:
            submission = await db.scalar(select(Submission).where(Submission.id == submission_id))
            assert submission is not None
            assert submission.workflow_state == "FAILED"


@pytest.mark.asyncio
async def test_page_normalization_retry_is_idempotent() -> None:
    async with api_client() as client:
        headers = await _headers(client)
        data = await _active_assessment(client, headers)
        upload = await client.post(
            "/api/v1/submissions",
            headers=headers,
            data={"assessment_id": data["assessment"]["id"]},
            files={"file": ("retry.pdf", _pdf_bytes(2), "application/pdf")},
        )
        assert upload.status_code == 201, upload.text
        submission_id = uuid.UUID(upload.json()["id"])
        async with async_session_factory() as db:
            tenant_id = await db.scalar(
                select(Submission.tenant_id).where(Submission.id == submission_id)
            )
            job = PipelineJob(
                tenant_id=tenant_id,
                submission_id=submission_id,
                stage="PAGE_NORMALIZATION",
                status="QUEUED",
                attempt=2,
                idempotency_key=f"page-norm:{submission_id}:v2",
            )
            db.add(job)
            await db.commit()
            await db.refresh(job)
            tenant_id = job.tenant_id
            job_id = job.id
            await run_page_normalization(
                db, tenant_id=tenant_id, submission_id=submission_id, job_id=job_id
            )
        pages = await client.get(f"/api/v1/submissions/{submission_id}/pages", headers=headers)
        assert len(pages.json()) == 2


@pytest.mark.asyncio
async def test_tenant_isolation_source_pages_identity_and_confirm() -> None:
    async with api_client() as client:
        headers = await _headers(client)
        data = await _active_assessment(client, headers)
        upload = await client.post(
            "/api/v1/submissions",
            headers=headers,
            data={"assessment_id": data["assessment"]["id"]},
            files={"file": ("iso.pdf", _pdf_bytes(1), "application/pdf")},
        )
        assert upload.status_code == 201, upload.text
        submission_id = upload.json()["id"]
        pages = await client.get(f"/api/v1/submissions/{submission_id}/pages", headers=headers)
        page_id = pages.json()[0]["id"]

        suffix = uuid.uuid4().hex[:8]
        async with async_session_factory() as db:
            tenant_b = Tenant(slug=f"b3-{suffix}", name="B3 Other")
            db.add(tenant_b)
            await db.flush()
            user_b = User(
                tenant_id=tenant_b.id,
                email=f"admin@{suffix}.local",
                display_name="Other",
                password_hash=hash_password(ADMIN_PASSWORD),
            )
            db.add(user_b)
            await db.commit()
            tenant_b_id = tenant_b.id
            user_b_id = user_b.id

        token_b, _ = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=user_b_id,
                tenant_id=tenant_b_id,
                roles=frozenset({"INSTITUTION_ADMIN"}),
                permissions=frozenset(
                    {"submission:read", "submission:upload", "submission:review"}
                ),
            )
        )
        headers_b = {"Authorization": f"Bearer {token_b}"}
        assert (
            await client.get(f"/api/v1/submissions/{submission_id}", headers=headers_b)
        ).status_code == 404
        assert (
            await client.get(f"/api/v1/submissions/{submission_id}/source", headers=headers_b)
        ).status_code == 404
        assert (
            await client.get(f"/api/v1/submission-pages/{page_id}/image", headers=headers_b)
        ).status_code == 404
        assert (
            await client.get(f"/api/v1/submissions/{submission_id}/identity", headers=headers_b)
        ).status_code == 404

        foreign_student = uuid.uuid4()
        confirm = await client.post(
            f"/api/v1/submissions/{submission_id}/identity/confirm",
            headers=headers,
            json={"student_id": str(foreign_student)},
        )
        assert confirm.status_code == 404


@pytest.mark.asyncio
async def test_identity_confirm_unmatched_and_permissions() -> None:
    async with api_client() as client:
        headers = await _headers(client)
        data = await _active_assessment(client, headers)
        upload = await client.post(
            "/api/v1/submissions",
            headers=headers,
            data={"assessment_id": data["assessment"]["id"]},
            files={"file": ("id.pdf", _pdf_bytes(1), "application/pdf")},
        )
        assert upload.status_code == 201, upload.text
        submission_id = upload.json()["id"]

        identity = await client.get(
            f"/api/v1/submissions/{submission_id}/identity", headers=headers
        )
        assert identity.status_code == 200
        assert identity.json()["automated_matching_active"] is False
        assert identity.json()["submission"]["identity_confidence"] == 0.0
        candidates = identity.json()["candidates"]
        assert isinstance(candidates, list)

        # Ensure at least one student exists in demo seed years/sections from platform tests —
        # create one if roster empty.
        if not candidates:
            years = await client.get("/api/v1/academic-years", headers=headers)
            sections = await client.get("/api/v1/class-sections", headers=headers)
            year_id = years.json()[0]["id"]
            section_id = sections.json()[0]["id"]
            created = await client.post(
                "/api/v1/students",
                headers=headers,
                json={
                    "student_code": f"B3-{uuid.uuid4().hex[:6]}",
                    "full_name": "B3 Student",
                    "class_section_id": section_id,
                    "academic_year_id": year_id,
                    "status": "active",
                },
            )
            assert created.status_code == 201, created.text
            identity = await client.get(
                f"/api/v1/submissions/{submission_id}/identity", headers=headers
            )
            candidates = identity.json()["candidates"]
        assert candidates
        student_id = candidates[0]["student_id"]

        confirmed = await client.post(
            f"/api/v1/submissions/{submission_id}/identity/confirm",
            headers=headers,
            json={"student_id": student_id},
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["student_match_state"] == "CONFIRMED"
        assert confirmed.json()["workflow_state"] == "MAPPING_REVIEW"
        assert confirmed.json()["student_id"] == student_id
        assert confirmed.json()["mapping_confidence"] == 0.0

        unmatched = await client.post(
            f"/api/v1/submissions/{submission_id}/identity/unmatched",
            headers=headers,
        )
        assert unmatched.status_code == 200
        assert unmatched.json()["student_match_state"] == "UNMATCHED"
        assert unmatched.json()["workflow_state"] == "IDENTITY_REVIEW"
        assert unmatched.json()["student_id"] is None

        assert (await client.get("/api/v1/submissions")).status_code == 401
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "tenant_slug": "demo"},
        )
        context = JwtAuthProvider(get_settings()).verify_access_token(
            login.json()["access_token"]
        )
        denied, _ = JwtAuthProvider(get_settings()).issue_access_token(
            AuthContext(
                user_id=context.user_id,
                tenant_id=context.tenant_id,
                roles=frozenset({"STUDENT"}),
                permissions=frozenset(),
            )
        )
        assert (
            await client.get(
                "/api/v1/submissions",
                headers={"Authorization": f"Bearer {denied}"},
            )
        ).status_code == 403


@pytest.mark.asyncio
async def test_cross_tenant_assessment_upload_is_404() -> None:
    async with api_client() as client:
        headers = await _headers(client)
        assert (
            await client.post(
                "/api/v1/submissions",
                headers=headers,
                data={"assessment_id": str(uuid.uuid4())},
                files={"file": ("x.pdf", _pdf_bytes(1), "application/pdf")},
            )
        ).status_code == 404


def test_raw_object_key_is_tenant_prefixed() -> None:
    tenant = uuid.uuid4()
    key = raw_object_key(tenant, "abc123def456", "paper.pdf")
    assert key.startswith(f"{tenant}/raw/")
    assert key.endswith(".pdf")
