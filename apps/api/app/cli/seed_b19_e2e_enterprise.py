# ruff: noqa: E501
"""Deterministic B19 real-E2E enterprise identity seed (CI / local only)."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from app.cli.seed_dev import ADMIN_EMAIL
from app.core.authorization import PERMISSION_CODES, ROLE_PERMISSION_MAP
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import (
    Assessment,
    AssessmentVersion,
    Curriculum,
    EvaluationRun,
    Institution,
    LtiResourceLink,
    Permission,
    PublishedResult,
    Role,
    RolePermission,
    Student,
    Submission,
    Tenant,
    User,
    UserRole,
)
from app.db.session import async_session_factory
from app.services.b19_test_providers import saml_idp_cert_pem
from app.services.enterprise_identity import create_provider
from app.services.lti import create_lti_platform

ASSESSMENT_CODE = "B19-E2E-ENT"
ISO_SLUG = "b19-iso"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def seed_b19_e2e_enterprise() -> dict[str, str]:
    settings = get_settings()
    public = settings.public_base_url.rstrip("/")
    internal = (settings.b19_test_internal_base_url or public).rstrip("/")
    async with async_session_factory() as db:
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == "demo"))
        if tenant is None:
            raise RuntimeError("demo tenant missing; run seed_dev first")
        admin = await db.scalar(
            select(User).where(User.tenant_id == tenant.id, User.email == ADMIN_EMAIL)
        )
        if admin is None:
            raise RuntimeError("demo admin missing; run seed_dev first")
        institution = await db.scalar(
            select(Institution).where(Institution.tenant_id == tenant.id, Institution.code == "DEMO")
        )
        if institution is None:
            raise RuntimeError("demo institution missing")

        oidc = await db.scalar(
            select(User).where(User.tenant_id == tenant.id, User.email == "sso.oidc@demo.eduvijna.local")
        )
        if oidc is None:
            oidc = User(
                tenant_id=tenant.id,
                email="sso.oidc@demo.eduvijna.local",
                display_name="OIDC SSO User",
                password_hash=hash_password("DemoUser!2026"),
                status="active",
            )
            db.add(oidc)
            await db.flush()
        teacher_role = await db.scalar(
            select(Role).where(Role.tenant_id == tenant.id, Role.code == "TEACHER")
        )
        if teacher_role is not None:
            existing_role = await db.scalar(
                select(UserRole).where(
                    UserRole.user_id == oidc.id, UserRole.role_id == teacher_role.id
                )
            )
            if existing_role is None:
                db.add(
                    UserRole(tenant_id=tenant.id, user_id=oidc.id, role_id=teacher_role.id)
                )

        existing = await db.scalar(
            select(Assessment).where(
                Assessment.tenant_id == tenant.id, Assessment.code == ASSESSMENT_CODE
            )
        )
        if existing is None:
            curriculum = Curriculum(
                tenant_id=tenant.id,
                code="B19-CUR",
                name="B19 Curriculum",
                version_label="2026",
                status="active",
            )
            db.add(curriculum)
            await db.flush()
            assessment = Assessment(
                tenant_id=tenant.id,
                curriculum_id=curriculum.id,
                code=ASSESSMENT_CODE,
                title="B19 E2E Assessment",
                assessment_type="EXAM",
                max_marks=Decimal("20.00"),
                status="ACTIVE",
                created_by=admin.id,
            )
            db.add(assessment)
            await db.flush()
            version = AssessmentVersion(
                tenant_id=tenant.id,
                assessment_id=assessment.id,
                version_number=1,
                title="B19 v1",
                max_marks=Decimal("20.00"),
                status="DRAFT",
                created_by=admin.id,
            )
            db.add(version)
            await db.flush()
            student = Student(
                tenant_id=tenant.id,
                institution_id=institution.id,
                student_code="B19-E2E-STU",
                full_name="B19 E2E Student",
                status="active",
            )
            db.add(student)
            await db.flush()
            digest = _sha("b19-e2e-source")
            submission = Submission(
                tenant_id=tenant.id,
                assessment_id=assessment.id,
                assessment_version_id=version.id,
                student_id=student.id,
                workflow_state="PUBLISHED",
                student_match_state="CONFIRMED",
                source_storage_key=f"b19-e2e/{digest}.pdf",
                source_content_sha256=digest,
                original_filename="b19-e2e.pdf",
                mime_type="application/pdf",
                byte_size=128,
                storage_status="AVAILABLE",
                page_count=1,
                uploaded_by=admin.id,
                uploaded_at=datetime.now(UTC),
            )
            db.add(submission)
            await db.flush()
            run = EvaluationRun(
                tenant_id=tenant.id,
                submission_id=submission.id,
                assessment_id=assessment.id,
                assessment_version_id=version.id,
                run_number=1,
                run_kind="INITIAL",
                status="COMPLETED",
                provider="fixed",
                model="b19-e2e",
            )
            db.add(run)
            await db.flush()
            generated = PublishedResult(
                tenant_id=tenant.id,
                submission_id=submission.id,
                student_id=student.id,
                assessment_id=assessment.id,
                assessment_version_id=version.id,
                evaluation_run_id=run.id,
                version_number=1,
                status="GENERATED",
                ledger_snapshot_hash="1" * 64,
                total_score=Decimal("10.00"),
                max_total_score=Decimal("20.00"),
            )
            published = PublishedResult(
                tenant_id=tenant.id,
                submission_id=submission.id,
                student_id=student.id,
                assessment_id=assessment.id,
                assessment_version_id=version.id,
                evaluation_run_id=run.id,
                version_number=2,
                status="PUBLISHED",
                ledger_snapshot_hash="2" * 64,
                total_score=Decimal("18.00"),
                max_total_score=Decimal("20.00"),
            )
            superseded = PublishedResult(
                tenant_id=tenant.id,
                submission_id=submission.id,
                student_id=student.id,
                assessment_id=assessment.id,
                assessment_version_id=version.id,
                evaluation_run_id=run.id,
                version_number=3,
                status="SUPERSEDED",
                ledger_snapshot_hash="3" * 64,
                total_score=Decimal("9.00"),
                max_total_score=Decimal("20.00"),
            )
            db.add_all([generated, published, superseded])
            await db.flush()
            published_id = published.id
            generated_id = generated.id
            superseded_id = superseded.id
            assessment_id = assessment.id
        else:
            published_row = await db.scalar(
                select(PublishedResult).where(
                    PublishedResult.tenant_id == tenant.id,
                    PublishedResult.assessment_id == existing.id,
                    PublishedResult.status == "PUBLISHED",
                )
            )
            generated_row = await db.scalar(
                select(PublishedResult).where(
                    PublishedResult.tenant_id == tenant.id,
                    PublishedResult.assessment_id == existing.id,
                    PublishedResult.status == "GENERATED",
                )
            )
            superseded_row = await db.scalar(
                select(PublishedResult).where(
                    PublishedResult.tenant_id == tenant.id,
                    PublishedResult.assessment_id == existing.id,
                    PublishedResult.status == "SUPERSEDED",
                )
            )
            assert published_row is not None
            published_id = published_row.id
            generated_id = generated_row.id if generated_row else published_row.id
            superseded_id = superseded_row.id if superseded_row else published_row.id
            assessment_id = existing.id

        from app.db.models import EnterpriseIdentityProvider, LtiPlatform

        oidc_provider = await db.scalar(
            select(EnterpriseIdentityProvider).where(
                EnterpriseIdentityProvider.tenant_id == tenant.id,
                EnterpriseIdentityProvider.name == "B19 Test OIDC",
            )
        )
        if oidc_provider is None:
            oidc_provider = await create_provider(
                db,
                tenant_id=tenant.id,
                actor_user_id=admin.id,
                name="B19 Test OIDC",
                protocol="OIDC",
                issuer="https://b19-test.example/oidc",
                client_id="oidc-client",
                client_secret="oidc-secret",
                authorization_endpoint=f"{public}/api/v1/b19-test/oidc/authorize",
                token_endpoint=f"{internal}/api/v1/b19-test/oidc/token",
                jwks_uri=f"{internal}/api/v1/b19-test/oidc/jwks",
                jit_enabled=False,
                account_linking_policy="VERIFIED_EMAIL_EXPLICIT",
            )
        saml_provider = await db.scalar(
            select(EnterpriseIdentityProvider).where(
                EnterpriseIdentityProvider.tenant_id == tenant.id,
                EnterpriseIdentityProvider.name == "B19 Test SAML",
            )
        )
        if saml_provider is None:
            saml_provider = await create_provider(
                db,
                tenant_id=tenant.id,
                actor_user_id=admin.id,
                name="B19 Test SAML",
                protocol="SAML",
                issuer="https://b19-test.example/saml",
                entity_id=f"{public}/saml/sp",
                sso_url=f"{public}/api/v1/b19-test/saml/sso",
                saml_idp_cert=saml_idp_cert_pem(),
                jit_enabled=True,
            )
        lti = await db.scalar(
            select(LtiPlatform).where(
                LtiPlatform.tenant_id == tenant.id,
                LtiPlatform.issuer == "https://b19-test.example/lti",
                LtiPlatform.client_id == "lti-client",
                LtiPlatform.deployment_id == "deploy-1",
            )
        )
        if lti is None:
            lti = await create_lti_platform(
                db,
                tenant_id=tenant.id,
                actor_user_id=admin.id,
                name="B19 Test LTI",
                issuer="https://b19-test.example/lti",
                client_id="lti-client",
                deployment_id="deploy-1",
                auth_login_url=f"{public}/api/v1/b19-test/lti/authorize",
                token_url=f"{internal}/api/v1/b19-test/lti/token",
                jwks_url=f"{internal}/api/v1/b19-test/lti/jwks",
                role_mapping_json={
                    "http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor": "TEACHER"
                },
            )
        link = await db.scalar(
            select(LtiResourceLink).where(
                LtiResourceLink.tenant_id == tenant.id, LtiResourceLink.platform_id == lti.id
            )
        )
        if link is None:
            link = LtiResourceLink(
                platform_id=lti.id,
                tenant_id=tenant.id,
                context_id="ctx-1",
                resource_link_id="res-1",
                assessment_id=assessment_id,
                ags_lineitem_url=f"{internal}/api/v1/b19-test/ags/lineitems/1",
                nrps_memberships_url=f"{internal}/api/v1/b19-test/nrps/memberships",
            )
            db.add(link)
            await db.flush()
        else:
            link.assessment_id = assessment_id
            if not link.ags_lineitem_url:
                link.ags_lineitem_url = f"{internal}/api/v1/b19-test/ags/lineitems/1"
            if not link.nrps_memberships_url:
                link.nrps_memberships_url = f"{internal}/api/v1/b19-test/nrps/memberships"

        from app.core.integration_crypto import encrypt_secret
        from app.db.models import ExternalRosterIdentity, WebhookEndpoint

        student_row = await db.scalar(
            select(Student).where(
                Student.tenant_id == tenant.id, Student.student_code == "B19-E2E-STU"
            )
        )
        if student_row is not None:
            roster = await db.scalar(
                select(ExternalRosterIdentity).where(
                    ExternalRosterIdentity.tenant_id == tenant.id,
                    ExternalRosterIdentity.provider_key == f"lti:{lti.id}",
                    ExternalRosterIdentity.external_stable_id == "nrps-student-1",
                )
            )
            if roster is None:
                now = datetime.now(UTC)
                db.add(
                    ExternalRosterIdentity(
                        tenant_id=tenant.id,
                        provider_key=f"lti:{lti.id}",
                        external_stable_id="nrps-student-1",
                        student_id=student_row.id,
                        source="NRPS",
                        status="ACTIVE",
                        first_seen_at=now,
                        last_synced_at=now,
                    )
                )

        hook_secret = settings.b19_test_webhook_signing_secret or "b19-deterministic-webhook-secret"
        hook_dest = (
            "http://test/api/v1/b19-test/webhook-receiver"
            if settings.environment.lower() == "test"
            else "http://api:8000/api/v1/b19-test/webhook-receiver"
        )
        hook = await db.scalar(
            select(WebhookEndpoint).where(
                WebhookEndpoint.tenant_id == tenant.id,
                WebhookEndpoint.name == "B19 Test Webhook",
            )
        )
        if hook is None:
            db.add(
                WebhookEndpoint(
                    tenant_id=tenant.id,
                    name="B19 Test Webhook",
                    destination_url=hook_dest,
                    encrypted_signing_secret=encrypt_secret(hook_secret, settings),
                    event_types_json=[
                        "result.published",
                        "identity.user.provisioned",
                        "identity.user.deactivated",
                        "roster.sync.completed",
                    ],
                    enabled=True,
                )
            )

        scim_held = await db.scalar(
            select(User).where(
                User.tenant_id == tenant.id, User.email == "scim.held@demo.eduvijna.local"
            )
        )
        if scim_held is None:
            scim_held = User(
                tenant_id=tenant.id,
                email="scim.held@demo.eduvijna.local",
                display_name="SCIM Held User",
                password_hash=hash_password("DemoUser!2026"),
                status="active",
                auth_version=1,
            )
            db.add(scim_held)

        iso = await db.scalar(select(Tenant).where(Tenant.slug == ISO_SLUG))
        if iso is None:
            iso = Tenant(slug=ISO_SLUG, name="B19 Isolation", status="active")
            db.add(iso)
            await db.flush()
            db.add(Institution(tenant_id=iso.id, code="B19ISO", name="B19 Iso"))
        iso_user = await db.scalar(
            select(User).where(
                User.tenant_id == iso.id, User.email == "admin@b19-iso.eduvijna.local"
            )
        )
        if iso_user is None:
            iso_user = User(
                tenant_id=iso.id,
                email="admin@b19-iso.eduvijna.local",
                display_name="B19 Iso Admin",
                password_hash=hash_password("DemoAdmin!2026"),
                status="active",
            )
            db.add(iso_user)
            await db.flush()
        else:
            iso_user.password_hash = hash_password("DemoAdmin!2026")
            iso_user.status = "active"
        permissions: dict[str, Permission] = {}
        for code in PERMISSION_CODES:
            permission = await db.scalar(select(Permission).where(Permission.code == code))
            if permission is None:
                permission = Permission(code=code, name=code.replace(":", " ").title())
                db.add(permission)
                await db.flush()
            permissions[code] = permission
        admin_role = await db.scalar(
            select(Role).where(Role.tenant_id == iso.id, Role.code == "INSTITUTION_ADMIN")
        )
        if admin_role is None:
            admin_role = Role(
                tenant_id=iso.id,
                code="INSTITUTION_ADMIN",
                name="Institution Admin",
                is_system=True,
            )
            db.add(admin_role)
            await db.flush()
            for permission_code in ROLE_PERMISSION_MAP.get("INSTITUTION_ADMIN", frozenset()):
                db.add(
                    RolePermission(
                        role_id=admin_role.id,
                        permission_id=permissions[permission_code].id,
                    )
                )
        existing_iso_role = await db.scalar(
            select(UserRole).where(UserRole.user_id == iso_user.id, UserRole.role_id == admin_role.id)
        )
        if existing_iso_role is None:
            db.add(UserRole(tenant_id=iso.id, user_id=iso_user.id, role_id=admin_role.id))
        await db.commit()
        return {
            "assessment_id": str(assessment_id),
            "published_result_id": str(published_id),
            "generated_result_id": str(generated_id),
            "superseded_result_id": str(superseded_id),
            "oidc_provider_id": str(oidc_provider.id),
            "saml_provider_id": str(saml_provider.id),
            "lti_platform_id": str(lti.id),
            "lti_resource_link_id": str(link.id),
            "student_id": str(student_row.id) if student_row is not None else "",
        }


if __name__ == "__main__":
    print(asyncio.run(seed_b19_e2e_enterprise()))
