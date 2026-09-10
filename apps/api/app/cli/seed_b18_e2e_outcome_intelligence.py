"""Deterministic B18 real-E2E outcome intelligence seed (CI / local only).

Creates assessment code B18-E2E-OUTCOME with ≥20 current PUBLISHED human-final
results, known transcription patterns forming ≥2 clusters, and known scores for
exact CO/PO marks-weighted attainment math.

Not used by production runtime. Idempotent by assessment code.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli.seed_dev import ADMIN_EMAIL, ADMIN_PASSWORD
from app.core.authorization import PERMISSION_CODES, ROLE_CODES, ROLE_PERMISSION_MAP
from app.core.security import hash_password
from app.db.models import (
    AnswerKey,
    AnswerKeyVersion,
    Assessment,
    AssessmentVersion,
    Curriculum,
    CurriculumNode,
    EvaluationRun,
    Institution,
    Permission,
    PublishedResult,
    Question,
    QuestionEvaluation,
    QuestionVersion,
    Role,
    RolePermission,
    Rubric,
    RubricCriterion,
    RubricVersion,
    Student,
    Submission,
    SubmissionPage,
    Tenant,
    User,
    UserRole,
)
from app.db.session import async_session_factory
from app.services.storage import ObjectStorage, derived_page_key

ASSESSMENT_CODE = "B18-E2E-OUTCOME"
PAGE_WIDTH = 200
PAGE_HEIGHT = 280


def _blank_page_png() -> bytes:
    """Minimal white PNG so real publication prepare can render annotated PDFs."""
    buf = io.BytesIO()
    Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT), color=(255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


async def _ensure_submission_page(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission_id: uuid.UUID,
    storage: ObjectStorage,
    png: bytes,
) -> None:
    existing = await db.scalar(
        select(SubmissionPage).where(
            SubmissionPage.tenant_id == tenant_id,
            SubmissionPage.submission_id == submission_id,
            SubmissionPage.page_index == 0,
        )
    )
    if existing is not None:
        return
    key = derived_page_key(tenant_id, submission_id, 0)
    storage.ensure_bucket()
    storage.put_derived_bytes(key=key, body=png, content_type="image/png")
    db.add(
        SubmissionPage(
            tenant_id=tenant_id,
            submission_id=submission_id,
            page_index=0,
            image_storage_key=key,
            width=PAGE_WIDTH,
            height=PAGE_HEIGHT,
            is_continuation=False,
        )
    )
CURRICULUM_CODE = "B18-E2E-CUR"
COHORT_SIZE = 20
MAX_MARK = Decimal("5.00")
ISO_TENANT_SLUG = "b18-iso"
ISO_ADMIN_EMAIL = "admin@b18-iso.eduvijna.local"

# Two known answer patterns that should form distinct clusters under fixed embeddings.
PATTERN_A = "photosynthesis converts light energy into chemical energy using chlorophyll"
PATTERN_B = "respiration releases energy from glucose through glycolysis and mitochondria"

# Deterministic COSINE_GRAPH_V1 expectation at threshold 0.75 with FixedEmbeddingProvider:
# PATTERN_A (indices 0..9) and PATTERN_B (indices 10..19) → exactly 2 clusters of 10.
EXPECTED_CLUSTER_COUNT = 2
EXPECTED_CLUSTER_MEMBER_COUNTS = (10, 10)


async def _ensure_isolation_tenant(db: AsyncSession) -> dict[str, str]:
    """Second tenant used by real E2E cross-tenant 404 assertions."""
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == ISO_TENANT_SLUG))
    if tenant is None:
        tenant = Tenant(slug=ISO_TENANT_SLUG, name="B18 Isolation Tenant")
        db.add(tenant)
        await db.flush()

    permissions: dict[str, Permission] = {}
    for code in PERMISSION_CODES:
        permission = await db.scalar(select(Permission).where(Permission.code == code))
        if permission is None:
            permission = Permission(code=code, name=code.replace(":", " ").title())
            db.add(permission)
            await db.flush()
        permissions[code] = permission

    roles: dict[str, Role] = {}
    for code in ROLE_CODES:
        role = await db.scalar(select(Role).where(Role.tenant_id == tenant.id, Role.code == code))
        if role is None:
            role = Role(
                tenant_id=tenant.id,
                code=code,
                name=code.replace("_", " ").title(),
                is_system=True,
            )
            db.add(role)
            await db.flush()
        roles[code] = role
        for permission_code in ROLE_PERMISSION_MAP.get(code, frozenset()):
            exists = await db.scalar(
                select(RolePermission).where(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id == permissions[permission_code].id,
                )
            )
            if exists is None:
                db.add(
                    RolePermission(
                        role_id=role.id,
                        permission_id=permissions[permission_code].id,
                    )
                )

    user = await db.scalar(
        select(User).where(User.tenant_id == tenant.id, User.email == ISO_ADMIN_EMAIL)
    )
    if user is None:
        user = User(
            tenant_id=tenant.id,
            email=ISO_ADMIN_EMAIL,
            display_name="B18 Isolation Admin",
            password_hash=hash_password(ADMIN_PASSWORD),
        )
        db.add(user)
        await db.flush()
    elif not user.password_hash:
        user.password_hash = hash_password(ADMIN_PASSWORD)

    admin_role = roles["INSTITUTION_ADMIN"]
    link = await db.scalar(
        select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == admin_role.id)
    )
    if link is None:
        db.add(UserRole(tenant_id=tenant.id, user_id=user.id, role_id=admin_role.id))

    institution = await db.scalar(
        select(Institution).where(Institution.tenant_id == tenant.id, Institution.code == "B18ISO")
    )
    if institution is None:
        db.add(Institution(tenant_id=tenant.id, code="B18ISO", name="B18 Isolation Institution"))

    await db.flush()
    return {
        "iso_tenant_id": str(tenant.id),
        "iso_admin_email": ISO_ADMIN_EMAIL,
        "iso_tenant_slug": ISO_TENANT_SLUG,
    }


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _pattern_for(index: int) -> str:
    return PATTERN_A if index < 10 else PATTERN_B


def _score_for(index: int) -> Decimal:
    # Deterministic scores for exact attainment math (Q1 only mapped by seed docs).
    # First 10 (pattern A): score = 4; last 10 (pattern B): score = 2
    return Decimal("4.00") if index < 10 else Decimal("2.00")


async def seed_b18_e2e_outcome_intelligence() -> dict[str, str]:
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
            select(Institution).where(
                Institution.tenant_id == tenant.id, Institution.code == "DEMO"
            )
        )
        if institution is None:
            raise RuntimeError("demo institution missing; run seed_dev first")

        existing = await db.scalar(
            select(Assessment).where(
                Assessment.tenant_id == tenant.id, Assessment.code == ASSESSMENT_CODE
            )
        )
        if existing is not None:
            version = await db.scalar(
                select(AssessmentVersion)
                .where(
                    AssessmentVersion.tenant_id == tenant.id,
                    AssessmentVersion.assessment_id == existing.id,
                )
                .order_by(AssessmentVersion.version_number.asc())
            )
            assert version is not None
            count = await db.scalar(
                select(func.count())
                .select_from(PublishedResult)
                .where(
                    PublishedResult.tenant_id == tenant.id,
                    PublishedResult.assessment_version_id == version.id,
                    PublishedResult.status == "PUBLISHED",
                )
            )
            if (count or 0) >= COHORT_SIZE:
                storage = ObjectStorage()
                png = _blank_page_png()
                subs = list(
                    (
                        await db.scalars(
                            select(Submission).where(
                                Submission.tenant_id == tenant.id,
                                Submission.assessment_id == existing.id,
                            )
                        )
                    ).all()
                )
                for sub in subs:
                    await _ensure_submission_page(
                        db,
                        tenant_id=tenant.id,
                        submission_id=sub.id,
                        storage=storage,
                        png=png,
                    )
                iso = await _ensure_isolation_tenant(db)
                await db.commit()
                print(
                    f"B18 E2E cohort already present: assessment={existing.id} "
                    f"version={version.id} published={count}"
                )
                return {
                    "assessment_id": str(existing.id),
                    "assessment_version_id": str(version.id),
                    "published_count": str(count),
                    **iso,
                }
            raise RuntimeError(
                f"B18-E2E-OUTCOME exists with incomplete cohort "
                f"(published={count}, need>={COHORT_SIZE}); delete and re-seed"
            )

        curriculum = Curriculum(
            tenant_id=tenant.id,
            code=CURRICULUM_CODE,
            name="B18 E2E Curriculum",
            version_label="2026",
            status="active",
        )
        db.add(curriculum)
        await db.flush()
        db.add(
            CurriculumNode(
                tenant_id=tenant.id,
                curriculum_id=curriculum.id,
                node_type="TOPIC",
                code="B18-NODE-1",
                name="B18 Topic",
                sequence=1,
                status="active",
            )
        )
        await db.flush()

        assessment = Assessment(
            tenant_id=tenant.id,
            curriculum_id=curriculum.id,
            code=ASSESSMENT_CODE,
            title="B18 E2E Outcome Assessment",
            assessment_type="EXAM",
            max_marks=Decimal("10.00"),
            status="ACTIVE",
            created_by=admin.id,
        )
        db.add(assessment)
        await db.flush()
        version = AssessmentVersion(
            tenant_id=tenant.id,
            assessment_id=assessment.id,
            version_number=1,
            title="B18 E2E v1",
            max_marks=Decimal("10.00"),
            status="DRAFT",
            created_by=admin.id,
        )
        db.add(version)
        await db.flush()

        answer_key = AnswerKey(tenant_id=tenant.id, assessment_id=assessment.id)
        db.add(answer_key)
        await db.flush()

        q_meta: list[dict[str, object]] = []
        for idx, code in enumerate(("Q1", "Q2"), start=1):
            question = Question(
                tenant_id=tenant.id,
                assessment_id=assessment.id,
                stable_code=code,
            )
            db.add(question)
            await db.flush()
            qv = QuestionVersion(
                tenant_id=tenant.id,
                assessment_version_id=version.id,
                question_id=question.id,
                display_label=str(idx),
                sequence=idx,
                prompt_text=f"B18 E2E question {idx}",
                max_marks=MAX_MARK,
                question_type="SHORT",
                scoring_mode="LEAF_SCORABLE",
                parent_question_version_id=None,
            )
            db.add(qv)
            await db.flush()
            akv = AnswerKeyVersion(
                tenant_id=tenant.id,
                answer_key_id=answer_key.id,
                assessment_version_id=version.id,
                question_version_id=qv.id,
                version_number=idx,
                answer_text=f"answer-{idx}",
                source_type="TEACHER",
                status="APPROVED",
                created_by=admin.id,
            )
            db.add(akv)
            await db.flush()
            rubric = Rubric(
                tenant_id=tenant.id,
                assessment_id=assessment.id,
                question_version_id=qv.id,
                title=f"Rubric {code}",
                provenance="TEACHER",
            )
            db.add(rubric)
            await db.flush()
            rv = RubricVersion(
                tenant_id=tenant.id,
                rubric_id=rubric.id,
                question_version_id=qv.id,
                version_number=1,
                status="APPROVED",
                source_type="TEACHER",
                created_by=admin.id,
            )
            db.add(rv)
            await db.flush()
            db.add(
                RubricCriterion(
                    tenant_id=tenant.id,
                    rubric_version_id=rv.id,
                    criterion_code=f"C{idx}",
                    description=f"Criterion {idx}",
                    max_marks=MAX_MARK,
                    sequence=1,
                    scoring_mode="ADDITIVE",
                    ecf_policy="NONE",
                )
            )
            q_meta.append(
                {
                    "question_id": question.id,
                    "question_version_id": qv.id,
                    "rubric_version_id": rv.id,
                    "answer_key_version_id": akv.id,
                }
            )

        student = Student(
            tenant_id=tenant.id,
            institution_id=institution.id,
            student_code="B18-E2E-STU",
            full_name="B18 E2E Student",
            status="active",
        )
        db.add(student)
        await db.flush()

        storage = ObjectStorage()
        page_png = _blank_page_png()

        for i in range(COHORT_SIZE):
            digest = _sha(f"b18-e2e-{ASSESSMENT_CODE}-{i}")
            pattern = _pattern_for(i)
            score_q1 = _score_for(i)
            score_q2 = Decimal("3.00")
            sub = Submission(
                tenant_id=tenant.id,
                assessment_id=assessment.id,
                assessment_version_id=version.id,
                student_id=student.id,
                workflow_state="PUBLISHED",
                student_match_state="CONFIRMED",
                identity_confidence=Decimal("1.0000"),
                mapping_confidence=Decimal("1.0000"),
                transcription_state="READY",
                source_storage_key=f"b18-e2e/{digest}.pdf",
                source_content_sha256=digest,
                original_filename=f"b18-e2e-{i}.pdf",
                mime_type="application/pdf",
                byte_size=128,
                storage_status="AVAILABLE",
                page_count=1,
                uploaded_by=admin.id,
                uploaded_at=datetime.now(UTC),
            )
            db.add(sub)
            await db.flush()
            await _ensure_submission_page(
                db,
                tenant_id=tenant.id,
                submission_id=sub.id,
                storage=storage,
                png=page_png,
            )
            run = EvaluationRun(
                tenant_id=tenant.id,
                submission_id=sub.id,
                assessment_id=assessment.id,
                assessment_version_id=version.id,
                run_number=1,
                run_kind="INITIAL",
                status="COMPLETED",
                provider="fixed",
                model="b18-e2e",
            )
            db.add(run)
            await db.flush()
            scores = [score_q1, score_q2]
            for meta, score in zip(q_meta, scores, strict=True):
                # Inline transcription text on refs for clustering (no AnswerRegion needed).
                db.add(
                    QuestionEvaluation(
                        tenant_id=tenant.id,
                        evaluation_run_id=run.id,
                        submission_id=sub.id,
                        student_id=student.id,
                        assessment_id=assessment.id,
                        assessment_version_id=version.id,
                        question_id=meta["question_id"],
                        question_version_id=meta["question_version_id"],
                        rubric_version_id=meta["rubric_version_id"],
                        answer_key_version_id=meta["answer_key_version_id"],
                        max_mark=MAX_MARK,
                        final_human_approved_score=score,
                        proposed_ai_score=score,
                        workflow_state="ACCEPTED",
                        ledger_version=1,
                        criterion_snapshot=[],
                        transcription_refs=[{"text": pattern}],
                        evidence_metadata={
                            "b18_e2e": True,
                            "transcription_text": pattern,
                            "pattern_group": "A" if i < 10 else "B",
                        },
                    )
                )
            total = score_q1 + score_q2
            db.add(
                PublishedResult(
                    tenant_id=tenant.id,
                    submission_id=sub.id,
                    student_id=student.id,
                    assessment_id=assessment.id,
                    assessment_version_id=version.id,
                    evaluation_run_id=run.id,
                    version_number=1,
                    status="PUBLISHED",
                    ledger_snapshot_hash=digest,
                    total_score=total,
                    max_total_score=Decimal("10.00"),
                    published_at=datetime.now(UTC),
                )
            )

        iso = await _ensure_isolation_tenant(db)
        await db.commit()
        print(
            f"Seeded B18 E2E cohort assessment={assessment.id} "
            f"version={version.id} published={COHORT_SIZE}"
        )
        return {
            "assessment_id": str(assessment.id),
            "assessment_version_id": str(version.id),
            "question_id": str(q_meta[0]["question_id"]),
            "published_count": str(COHORT_SIZE),
            **iso,
        }


if __name__ == "__main__":
    asyncio.run(seed_b18_e2e_outcome_intelligence())
