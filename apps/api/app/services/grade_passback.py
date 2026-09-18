# ruff: noqa: E501
"""LTI AGS grade passback from current PUBLISHED PublishedResult only."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import (
    ExternalRosterIdentity,
    GradePassback,
    LtiPlatform,
    LtiResourceLink,
    PublishedResult,
    Student,
)
from app.services.audit import add_audit_event
from app.services.b19_outbound import outbound_request
from app.services.lti import issue_lti_client_assertion
from app.services.ssrf import validate_public_https_url


def serialize_passback(row: GradePassback) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "lti_platform_id": str(row.lti_platform_id),
        "resource_link_id": str(row.resource_link_id),
        "published_result_id": str(row.published_result_id),
        "published_result_version": row.published_result_version,
        "external_user_id": row.external_user_id,
        "lineitem_url": row.lineitem_url,
        "score": str(row.score),
        "max_score": str(row.max_score),
        "idempotency_key": row.idempotency_key,
        "state": row.state,
        "attempts": row.attempts,
        "latest_error": row.latest_error,
        "delivered_at": row.delivered_at.isoformat() if row.delivered_at else None,
    }


async def request_grade_passback(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    published_result_id: uuid.UUID,
    resource_link_id: uuid.UUID,
    external_user_id: str | None = None,
    requested_score: Decimal | None = None,
    settings: Settings | None = None,
) -> GradePassback:
    cfg = settings or get_settings()
    if requested_score is not None:
        raise HTTPException(
            400,
            detail={
                "code": "score_override_forbidden",
                "message": "Score must be derived from the published result",
            },
        )
    published = await db.scalar(
        select(PublishedResult).where(
            PublishedResult.id == published_result_id,
            PublishedResult.tenant_id == tenant_id,
        )
    )
    if published is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Published result not found"})
    if published.status != "PUBLISHED":
        raise HTTPException(
            400,
            detail={
                "code": "unpublished_result",
                "message": f"Result status {published.status} cannot be passed back",
            },
        )
    link = await db.scalar(
        select(LtiResourceLink).where(
            LtiResourceLink.id == resource_link_id,
            LtiResourceLink.tenant_id == tenant_id,
        )
    )
    if link is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Resource link not found"})
    platform = await db.scalar(
        select(LtiPlatform).where(
            LtiPlatform.id == link.platform_id, LtiPlatform.tenant_id == tenant_id
        )
    )
    if platform is None or not platform.enabled:
        raise HTTPException(400, detail={"code": "platform_disabled", "message": "LTI platform disabled"})
    if link.assessment_id is None or link.assessment_id != published.assessment_id:
        raise HTTPException(
            400,
            detail={
                "code": "resource_mismatch",
                "message": "Resource link is not associated with this published result",
            },
        )
    if published.student_id is None:
        raise HTTPException(
            400,
            detail={"code": "student_unbound", "message": "Published result has no student"},
        )
    student = await db.scalar(
        select(Student).where(Student.id == published.student_id, Student.tenant_id == tenant_id)
    )
    if student is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Student not found"})
    if (
        link.class_section_id is not None
        and student.class_section_id is not None
        and link.class_section_id != student.class_section_id
    ):
        raise HTTPException(
            400,
            detail={"code": "context_mismatch", "message": "Class/context association mismatch"},
        )
    mapping = await db.scalar(
        select(ExternalRosterIdentity).where(
            ExternalRosterIdentity.tenant_id == tenant_id,
            ExternalRosterIdentity.provider_key == f"lti:{platform.id}",
            ExternalRosterIdentity.student_id == published.student_id,
            ExternalRosterIdentity.status == "ACTIVE",
        )
    )
    if mapping is None:
        raise HTTPException(
            400,
            detail={"code": "learner_unmapped", "message": "No validated roster mapping for student"},
        )
    derived_external_id = mapping.external_stable_id
    if external_user_id and external_user_id != derived_external_id:
        raise HTTPException(
            400,
            detail={
                "code": "learner_mismatch",
                "message": "Caller cannot choose an arbitrary external learner",
            },
        )
    external_user_id = derived_external_id
    lineitem = link.ags_lineitem_url
    if not lineitem:
        raise HTTPException(
            400, detail={"code": "ags_unconfigured", "message": "AGS lineitem missing"}
        )
    idempotency_key = f"{published.id}:{published.version_number}:{external_user_id}"
    existing = await db.scalar(
        select(GradePassback).where(
            GradePassback.tenant_id == tenant_id,
            GradePassback.idempotency_key == idempotency_key,
        )
    )
    if existing is not None and existing.state == "DELIVERED":
        return existing

    row = existing or GradePassback(
        tenant_id=tenant_id,
        lti_platform_id=platform.id,
        resource_link_id=link.id,
        published_result_id=published.id,
        published_result_version=published.version_number,
        external_user_id=external_user_id,
        lineitem_url=lineitem,
        score=published.total_score,
        max_score=published.max_total_score,
        idempotency_key=idempotency_key,
        state="PENDING",
    )
    if existing is None:
        db.add(row)
        await db.flush()

    allow_insecure = (
        cfg.environment.lower() in {"local", "test"} or cfg.b19_test_providers_enabled
    )
    validate_public_https_url(lineitem, allow_insecure=allow_insecure, purpose="AGS")
    token = await _ags_access_token(platform, cfg)
    score_url = lineitem.rstrip("/") + "/scores"
    payload = {
        "userId": external_user_id,
        "scoreGiven": float(published.total_score),
        "scoreMaximum": float(published.max_total_score),
        "activityProgress": "Completed",
        "gradingProgress": "FullyGraded",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    row.attempts += 1
    try:
        resp = await outbound_request(
            "POST",
            score_url,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/vnd.ims.lis.v1.score+json",
            },
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"ags_http_{resp.status_code}")
        row.state = "DELIVERED"
        row.delivered_at = datetime.now(UTC)
        row.latest_error = None
    except Exception as exc:
        row.state = "FAILED"
        row.latest_error = exc.__class__.__name__
    await db.flush()
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="grade_passback",
        entity_id=row.id,
        action="passback_attempted",
        after=serialize_passback(row),
    )
    return row


async def _ags_access_token(platform: LtiPlatform, settings: Settings) -> str:
    assertion = issue_lti_client_assertion(platform, settings)
    allow_insecure = (
        settings.environment.lower() in {"local", "test"} or settings.b19_test_providers_enabled
    )
    validate_public_https_url(platform.token_url, allow_insecure=allow_insecure, purpose="LTI token")
    resp = await outbound_request(
        "POST",
        platform.token_url,
        data={
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
            "scope": "https://purl.imsglobal.org/spec/lti-ags/scope/score",
        },
    )
    if resp.status_code >= 400:
        raise HTTPException(
            400, detail={"code": "ags_token_failed", "message": "AGS token request failed"}
        )
    return str(resp.json().get("access_token") or "")
