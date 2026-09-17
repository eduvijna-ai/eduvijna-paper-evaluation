# ruff: noqa: E501
"""Deterministic tenant-isolated roster upsert for SIS / NRPS / public API."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ExternalRosterIdentity,
    Institution,
    RosterSyncRun,
    Student,
)
from app.services.audit import add_audit_event
from app.services.webhooks import record_outbound_event


def _student_public(student: Student) -> dict[str, Any]:
    return {
        "id": str(student.id),
        "student_code": student.student_code,
        "full_name": student.full_name,
        "status": student.status,
        "class_section_id": str(student.class_section_id) if student.class_section_id else None,
        "academic_year_id": str(student.academic_year_id) if student.academic_year_id else None,
    }


async def upsert_roster_members(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    provider_key: str,
    members: list[dict[str, Any]],
    actor_user_id: uuid.UUID | None = None,
    source: str = "SIS",
) -> RosterSyncRun:
    now = datetime.now(UTC)
    run = RosterSyncRun(
        tenant_id=tenant_id,
        provider_key=provider_key,
        status="RUNNING",
        started_at=now,
        summary_json={},
    )
    db.add(run)
    await db.flush()

    institution = await db.scalar(select(Institution).where(Institution.tenant_id == tenant_id))
    if institution is None:
        run.status = "FAILED"
        run.finished_at = datetime.now(UTC)
        run.summary_json = {"error": "institution_missing"}
        await db.flush()
        raise HTTPException(
            400, detail={"code": "institution_missing", "message": "Tenant institution missing"}
        )

    created = 0
    updated = 0
    inactivated = 0
    for member in members:
        external_id = str(member.get("external_stable_id") or "").strip()
        if not external_id:
            continue
        full_name = str(member.get("full_name") or "").strip() or external_id
        student_code = str(member.get("student_code") or external_id)[:100]
        status = str(member.get("status") or "ACTIVE").upper()
        if status not in {"ACTIVE", "INACTIVE"}:
            status = "ACTIVE"
        class_section_id = member.get("class_section_id")
        academic_year_id = member.get("academic_year_id")

        mapping = await db.scalar(
            select(ExternalRosterIdentity).where(
                ExternalRosterIdentity.tenant_id == tenant_id,
                ExternalRosterIdentity.provider_key == provider_key,
                ExternalRosterIdentity.external_stable_id == external_id,
            )
        )
        if mapping is None:
            student = Student(
                tenant_id=tenant_id,
                institution_id=institution.id,
                student_code=student_code,
                full_name=full_name[:255],
                status="active" if status == "ACTIVE" else "inactive",
                class_section_id=uuid.UUID(str(class_section_id)) if class_section_id else None,
                academic_year_id=uuid.UUID(str(academic_year_id)) if academic_year_id else None,
            )
            db.add(student)
            await db.flush()
            mapping = ExternalRosterIdentity(
                tenant_id=tenant_id,
                provider_key=provider_key,
                external_stable_id=external_id,
                student_id=student.id,
                class_section_id=student.class_section_id,
                academic_year_id=student.academic_year_id,
                source=source,
                status=status,
                first_seen_at=now,
                last_synced_at=now,
            )
            db.add(mapping)
            created += 1
        else:
            existing_student = await db.scalar(
                select(Student).where(
                    Student.id == mapping.student_id, Student.tenant_id == tenant_id
                )
            )
            if existing_student is None:
                continue
            student = existing_student
            student.full_name = full_name[:255]
            if class_section_id:
                student.class_section_id = uuid.UUID(str(class_section_id))
            if academic_year_id:
                student.academic_year_id = uuid.UUID(str(academic_year_id))
            if status == "INACTIVE":
                mapping.status = "INACTIVE"
                inactivated += 1
            else:
                mapping.status = "ACTIVE"
                student.status = "active"
            mapping.last_synced_at = now
            mapping.class_section_id = student.class_section_id
            mapping.academic_year_id = student.academic_year_id
            updated += 1
        await db.flush()

    run.status = "SUCCEEDED"
    run.finished_at = datetime.now(UTC)
    run.summary_json = {
        "created": created,
        "updated": updated,
        "inactivated": inactivated,
        "received": len(members),
    }
    await add_audit_event(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        entity_type="roster_sync_run",
        entity_id=run.id,
        action="roster_synced",
        after=run.summary_json,
    )
    await record_outbound_event(
        db,
        tenant_id=tenant_id,
        event_type="roster.sync.completed",
        source_entity_type="roster_sync_run",
        source_entity_id=run.id,
        payload={"provider_key": provider_key, **run.summary_json},
    )
    await db.flush()
    return run


async def sync_nrps_memberships(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    resource_link_id: uuid.UUID,
    settings: Any | None = None,
) -> RosterSyncRun:
    from app.core.config import get_settings
    from app.db.models import LtiResourceLink
    from app.services.b19_outbound import outbound_request
    from app.services.ssrf import validate_public_https_url

    cfg = settings or get_settings()
    link = await db.scalar(
        select(LtiResourceLink).where(
            LtiResourceLink.id == resource_link_id,
            LtiResourceLink.tenant_id == tenant_id,
        )
    )
    if link is None or not link.nrps_memberships_url:
        raise HTTPException(
            400, detail={"code": "nrps_unconfigured", "message": "NRPS memberships URL missing"}
        )
    allow_insecure = cfg.environment.lower() in {"local", "test"} or cfg.b19_test_providers_enabled
    validate_public_https_url(
        link.nrps_memberships_url, allow_insecure=allow_insecure, purpose="NRPS"
    )
    resp = await outbound_request("GET", link.nrps_memberships_url)
    if resp.status_code >= 400:
        raise HTTPException(400, detail={"code": "nrps_failed", "message": "NRPS fetch failed"})
    payload = resp.json()
    members = []
    for item in payload.get("members") or []:
        members.append(
            {
                "external_stable_id": str(item.get("user_id") or ""),
                "full_name": str(item.get("name") or item.get("user_id") or ""),
                "student_code": str(item.get("user_id") or "")[:100],
                "status": "ACTIVE" if str(item.get("status") or "Active") == "Active" else "INACTIVE",
            }
        )
    return await upsert_roster_members(
        db,
        tenant_id=tenant_id,
        provider_key=f"lti:{link.platform_id}",
        members=members,
        actor_user_id=actor_user_id,
        source="NRPS",
    )


def serialize_sync_run(run: RosterSyncRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "provider_key": run.provider_key,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "summary": run.summary_json or {},
    }
