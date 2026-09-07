"""B10 assessment artifact upload, scanner hook, and storage ordering."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.cli.seed_dev import ADMIN_EMAIL, ADMIN_PASSWORD, seed
from app.core.config import get_settings
from app.main import create_app
from app.services.storage import ObjectStorage
from app.services.upload_scanner import (
    FixedUploadScanner,
    NoneUploadScanner,
    UploadScanResult,
    get_upload_scanner,
)
from app.services.upload_validation import sha256_bytes
from tests.test_a2_gate_matrix import _foundation


def _pdf_bytes(label: str = "B10 paper") -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=200, height=280)
    page.insert_text((40, 60), label)
    data = doc.tobytes()
    doc.close()
    return data


@asynccontextmanager
async def api_client(**env: str) -> AsyncIterator[AsyncClient]:
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
    os.environ["S3_ENDPOINT_URL"] = "http://127.0.0.1:19000"
    for key, value in env.items():
        os.environ[key] = value
    await seed()
    get_settings.cache_clear()
    ObjectStorage(get_settings()).ensure_bucket()
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        yield client
    get_settings.cache_clear()


async def _headers(client: AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "tenant_slug": "demo"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


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
    return body.get("detail") or body


@pytest.mark.asyncio
async def test_question_paper_upload_pdf_succeeds() -> None:
    async with api_client(UPLOAD_SCANNER="fixed") as client:
        headers = await _headers(client)
        data = await _foundation(client, headers)
        version_id = data["version_id"]
        pdf = _pdf_bytes("valid paper")

        upload = await client.post(
            f"/api/v1/assessment-versions/{version_id}/question-paper",
            headers=headers,
            files={"file": ("paper.pdf", pdf, "application/pdf")},
        )
        assert upload.status_code == 201, upload.text
        body = upload.json()
        assert body["artifact_type"] == "QUESTION_PAPER"
        assert body["mime_type"] == "application/pdf"
        assert body["content_sha256"] == sha256_bytes(pdf)
        assert body["security_scan_status"] == "CLEAN"
        assert "/assessment-sources/" in body["storage_key"]
        assert ObjectStorage().exists(body["storage_key"])


@pytest.mark.asyncio
async def test_malware_rejected_does_not_write_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []

    class RejectingScanner(FixedUploadScanner):
        async def scan(
            self, *, filename: str, mime_type: str, content: bytes
        ) -> UploadScanResult:
            order.append("scan")
            return UploadScanResult(status="REJECTED", detail="filename_marker")

    original_put = ObjectStorage.put_assessment_source_bytes

    def spy_put(
        self: ObjectStorage, *, key: str, body: bytes, content_type: str
    ) -> Any:
        order.append("storage")
        return original_put(self, key=key, body=body, content_type=content_type)

    monkeypatch.setattr(
        "app.services.assessment_artifacts.get_upload_scanner",
        lambda settings=None: RejectingScanner(),
    )
    monkeypatch.setattr(ObjectStorage, "put_assessment_source_bytes", spy_put)

    async with api_client(UPLOAD_SCANNER="fixed") as client:
        headers = await _headers(client)
        data = await _foundation(client, headers)
        version_id = data["version_id"]
        pdf = _pdf_bytes("malware bait")

        upload = await client.post(
            f"/api/v1/assessment-versions/{version_id}/question-paper",
            headers=headers,
            files={"file": ("malware-sheet.pdf", pdf, "application/pdf")},
        )
        assert upload.status_code == 422, upload.text
        assert _err(upload)["code"] == "MALWARE_DETECTED"
        assert order == ["scan"]
        assert "storage" not in order

        from sqlalchemy import select

        from app.db.models import AssessmentVersion
        from app.db.session import async_session_factory

        async with async_session_factory() as db:
            version = await db.scalar(
                select(AssessmentVersion).where(
                    AssessmentVersion.id == uuid.UUID(version_id)
                )
            )
            assert version is not None
            assert version.question_paper_artifact_id is None


@pytest.mark.asyncio
async def test_none_scanner_never_reports_clean() -> None:
    os.environ["UPLOAD_SCANNER"] = "none"
    get_settings.cache_clear()
    scanner = get_upload_scanner(get_settings())
    assert isinstance(scanner, NoneUploadScanner)
    result = await scanner.scan(
        filename="ok.pdf", mime_type="application/pdf", content=b"%PDF-1.4"
    )
    assert result.status == "NOT_CONFIGURED"
    assert result.status != "CLEAN"

    async with api_client(UPLOAD_SCANNER="none") as client:
        headers = await _headers(client)
        data = await _foundation(client, headers)
        pdf = _pdf_bytes("none scanner")
        upload = await client.post(
            f"/api/v1/assessment-versions/{data['version_id']}/question-paper",
            headers=headers,
            files={"file": ("paper.pdf", pdf, "application/pdf")},
        )
        assert upload.status_code == 201, upload.text
        assert upload.json()["security_scan_status"] == "NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_foreign_version_returns_404() -> None:
    async with api_client(UPLOAD_SCANNER="fixed") as client:
        headers = await _headers(client)
        await _foundation(client, headers)
        missing = uuid.uuid4()
        upload = await client.post(
            f"/api/v1/assessment-versions/{missing}/question-paper",
            headers=headers,
            files={"file": ("paper.pdf", _pdf_bytes(), "application/pdf")},
        )
        assert upload.status_code == 404
        assert _err(upload)["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_structure_exists_returns_409() -> None:
    async with api_client(UPLOAD_SCANNER="fixed") as client:
        headers = await _headers(client)
        data = await _foundation(client, headers, marks="10.00")
        version_id = data["version_id"]
        created = await client.post(
            f"/api/v1/assessment-versions/{version_id}/questions",
            headers=headers,
            json={
                "stable_code": f"Q-{uuid.uuid4().hex[:6]}",
                "display_label": "1",
                "sequence": 1,
                "prompt_text": "Compute",
                "max_marks": "10.00",
                "question_type": "SHORT_ANSWER",
                "scoring_mode": "LEAF_SCORABLE",
            },
        )
        assert created.status_code == 201, created.text

        upload = await client.post(
            f"/api/v1/assessment-versions/{version_id}/question-paper",
            headers=headers,
            files={"file": ("paper.pdf", _pdf_bytes(), "application/pdf")},
        )
        assert upload.status_code == 409, upload.text
        assert _err(upload)["code"] == "QUESTION_PAPER_STRUCTURE_EXISTS"


@pytest.mark.asyncio
async def test_scanner_runs_before_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []

    class SpyScanner(FixedUploadScanner):
        async def scan(
            self, *, filename: str, mime_type: str, content: bytes
        ) -> UploadScanResult:
            order.append("scan")
            return await super().scan(
                filename=filename, mime_type=mime_type, content=content
            )

    original_put = ObjectStorage.put_assessment_source_bytes

    def spy_put(
        self: ObjectStorage, *, key: str, body: bytes, content_type: str
    ) -> Any:
        order.append("storage")
        return original_put(self, key=key, body=body, content_type=content_type)

    monkeypatch.setattr(
        "app.services.assessment_artifacts.get_upload_scanner",
        lambda settings=None: SpyScanner(),
    )
    monkeypatch.setattr(ObjectStorage, "put_assessment_source_bytes", spy_put)

    async with api_client(UPLOAD_SCANNER="fixed") as client:
        headers = await _headers(client)
        data = await _foundation(client, headers)
        upload = await client.post(
            f"/api/v1/assessment-versions/{data['version_id']}/question-paper",
            headers=headers,
            files={"file": ("paper.pdf", _pdf_bytes(), "application/pdf")},
        )
        assert upload.status_code == 201, upload.text
        assert order == ["scan", "storage"]


@pytest.mark.asyncio
async def test_submission_malware_rejected_before_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_a2_review_fixes import _leaf_and_approve

    order: list[str] = []

    class RejectScanner:
        async def scan(
            self, *, filename: str, mime_type: str, content: bytes
        ) -> UploadScanResult:
            order.append("scan")
            return UploadScanResult(status="REJECTED", detail="test")

    original_put = ObjectStorage.put_raw_bytes

    def spy_put(self: ObjectStorage, *, key: str, body: bytes, content_type: str) -> Any:
        order.append("storage")
        return original_put(self, key=key, body=body, content_type=content_type)

    monkeypatch.setattr(
        "app.api.v1.submissions.get_upload_scanner",
        lambda settings=None: RejectScanner(),
    )
    monkeypatch.setattr(ObjectStorage, "put_raw_bytes", spy_put)

    async with api_client(UPLOAD_SCANNER="fixed") as client:
        headers = await _headers(client)
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

        upload = await client.post(
            "/api/v1/submissions",
            headers=headers,
            data={"assessment_id": data["assessment"]["id"]},
            files={"file": ("sheet.pdf", _pdf_bytes(), "application/pdf")},
        )
        assert upload.status_code == 422, upload.text
        assert _err(upload)["code"] == "MALWARE_DETECTED"
        assert order == ["scan"]
        assert "storage" not in order
