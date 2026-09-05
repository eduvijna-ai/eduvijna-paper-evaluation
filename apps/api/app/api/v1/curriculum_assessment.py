# ruff: noqa: B008
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require_permissions
from app.db.models import (
    AcademicYear,
    AnswerKey,
    AnswerKeyVersion,
    Assessment,
    AssessmentVersion,
    AuditEvent,
    ClassSection,
    Curriculum,
    CurriculumNode,
    CurriculumPrerequisite,
    Question,
    QuestionCurriculumMapping,
    QuestionVersion,
    Rubric,
    RubricCriterion,
    RubricVersion,
)
from app.db.session import get_db_session
from app.services.ai_proposals import unavailable
from app.services.assessment_transitions import validate_transition
from app.services.curriculum import (
    build_tree,
    ensure_parent_acyclic,
    ensure_prerequisite_acyclic,
)
from app.services.mark_reconciliation import reconcile_marks
from app.services.readiness import ensure_assessment_ready
from app.services.rubric_reconciliation import reconcile_rubric

router = APIRouter()
Db = Annotated[AsyncSession, Depends(get_db_session)]
Money = Annotated[Decimal, Field(max_digits=10, decimal_places=2, ge=0)]


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CurriculumIn(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    academic_framework: str | None = Field(default=None, max_length=255)
    version_label: str = Field(min_length=1, max_length=100)
    status: str = "active"


class CurriculumPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    academic_framework: str | None = None
    version_label: str | None = None
    status: str | None = None


class CurriculumOut(CurriculumIn, OrmModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class NodeIn(BaseModel):
    parent_id: uuid.UUID | None = None
    node_type: str
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    sequence: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"


class NodePatch(BaseModel):
    parent_id: uuid.UUID | None = None
    node_type: str | None = None
    name: str | None = None
    description: str | None = None
    sequence: int | None = None
    metadata: dict[str, Any] | None = None
    status: str | None = None


class PrerequisiteIn(BaseModel):
    prerequisite_node_id: uuid.UUID
    dependent_node_id: uuid.UUID
    relationship_type: str = Field(pattern="^(REQUIRED|RECOMMENDED)$")


class AssessmentIn(BaseModel):
    academic_year_id: uuid.UUID | None = None
    class_section_id: uuid.UUID | None = None
    curriculum_id: uuid.UUID
    subject_node_id: uuid.UUID | None = None
    code: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    assessment_type: str
    max_marks: Money
    duration_minutes: int | None = Field(default=None, ge=1)


class AssessmentPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    assessment_type: str | None = None
    max_marks: Money | None = None
    duration_minutes: int | None = Field(default=None, ge=1)


class AssessmentVersionIn(BaseModel):
    title: str
    instructions: str | None = None
    max_marks: Money
    question_paper_artifact_id: uuid.UUID | None = None


class QuestionIn(BaseModel):
    stable_code: str
    parent_question_version_id: uuid.UUID | None = None
    display_label: str
    sequence: int
    prompt_text: str
    max_marks: Money
    question_type: str
    scoring_mode: str = Field(pattern="^(LEAF_SCORABLE|CONTAINER_DERIVED)$")
    instructions: str | None = None


class QuestionPatch(BaseModel):
    parent_question_version_id: uuid.UUID | None = None
    display_label: str | None = None
    sequence: int | None = None
    prompt_text: str | None = None
    max_marks: Money | None = None
    question_type: str | None = None
    scoring_mode: str | None = Field(default=None, pattern="^(LEAF_SCORABLE|CONTAINER_DERIVED)$")
    instructions: str | None = None


class AnswerKeyVersionIn(BaseModel):
    assessment_version_id: uuid.UUID
    question_version_id: uuid.UUID
    answer_text: str
    structured_answer: dict[str, Any] | None = None
    source_type: str = Field(pattern="^(TEACHER|AI_PROPOSED|IMPORTED)$")
    status: str = Field(default="DRAFT", pattern="^(DRAFT|REVIEW_REQUIRED)$")


class AnswerKeyPatch(BaseModel):
    answer_text: str | None = None
    structured_answer: dict[str, Any] | None = None
    status: str | None = Field(default=None, pattern="^(DRAFT|REVIEW_REQUIRED)$")


class RubricIn(BaseModel):
    question_version_id: uuid.UUID
    title: str
    provenance: str = "TEACHER"


class RubricVersionIn(BaseModel):
    question_version_id: uuid.UUID
    source_type: str = "TEACHER"
    status: str = Field(default="DRAFT", pattern="^(DRAFT|REVIEW_REQUIRED)$")


class CriterionIn(BaseModel):
    criterion_code: str
    description: str
    max_marks: Money
    sequence: int
    scoring_mode: str = Field(pattern="^(ADDITIVE|DEDUCTIVE|ALL_OR_NOTHING)$")
    partial_credit_allowed: bool = False
    dependency_rule: dict[str, Any] | None = None
    ecf_policy: str = Field(default="NONE", pattern="^(NONE|ALLOW_METHOD_CREDIT|CUSTOM_REVIEW)$")
    unit_requirement: str | None = None
    precision_requirement: str | None = None
    required_reasoning: str | None = None
    accepted_equivalents: list[Any] = Field(default_factory=list)
    teacher_comment: str | None = None


class CriterionPatch(BaseModel):
    description: str | None = None
    max_marks: Money | None = None
    sequence: int | None = None
    scoring_mode: str | None = Field(default=None, pattern="^(ADDITIVE|DEDUCTIVE|ALL_OR_NOTHING)$")
    partial_credit_allowed: bool | None = None
    dependency_rule: dict[str, Any] | None = None
    ecf_policy: str | None = Field(
        default=None, pattern="^(NONE|ALLOW_METHOD_CREDIT|CUSTOM_REVIEW)$"
    )
    unit_requirement: str | None = None
    precision_requirement: str | None = None
    required_reasoning: str | None = None
    accepted_equivalents: list[Any] | None = None
    teacher_comment: str | None = None


class MappingIn(BaseModel):
    curriculum_node_id: uuid.UUID
    mapping_type: str = Field(pattern="^(PRIMARY|SECONDARY|LEARNING_OUTCOME|SKILL)$")
    weight: Money | None = None


class TransitionIn(BaseModel):
    to_status: str


async def _scoped[ModelT](
    db: AsyncSession, model: type[ModelT], item_id: uuid.UUID, tenant_id: uuid.UUID
) -> ModelT:
    columns = cast(Any, model)
    item = await db.scalar(
        select(model).where(columns.id == item_id, columns.tenant_id == tenant_id)
    )
    if item is None:
        raise HTTPException(404, "Resource not found")
    return item


async def _audit(
    db: AsyncSession, auth: AuthContext, entity: Any, action: str, payload: dict[str, Any]
) -> None:
    db.add(
        AuditEvent(
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            entity_type=entity.__class__.__name__,
            entity_id=entity.id,
            action=action,
            payload_json=payload,
        )
    )


async def _commit(db: AsyncSession) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Resource conflicts with an existing record") from exc


def _dump(item: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for attribute in inspect(item).mapper.column_attrs:
        result[attribute.columns[0].name] = getattr(item, attribute.key)
    return result


async def _validate_curriculum_node(
    db: AsyncSession, auth: AuthContext, curriculum_id: uuid.UUID, node_id: uuid.UUID
) -> CurriculumNode:
    node = await _scoped(db, CurriculumNode, node_id, auth.tenant_id)
    if node.curriculum_id != curriculum_id:
        raise HTTPException(404, "Resource not found")
    return node


@router.get("/curricula")
async def list_curricula(
    db: Db, auth: AuthContext = Depends(require_permissions("curriculum:read"))
) -> list[dict[str, Any]]:
    rows = await db.scalars(
        select(Curriculum).where(Curriculum.tenant_id == auth.tenant_id).order_by(Curriculum.code)
    )
    return [_dump(item) for item in rows]


@router.post("/curricula", status_code=201, response_model=CurriculumOut)
async def create_curriculum(
    payload: CurriculumIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("curriculum:manage")),
) -> Curriculum:
    item = Curriculum(tenant_id=auth.tenant_id, **payload.model_dump())
    db.add(item)
    await db.flush()
    await _audit(db, auth, item, "created", payload.model_dump(mode="json"))
    await _commit(db)
    return item


@router.get("/curricula/{curriculum_id}")
async def get_curriculum(
    curriculum_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("curriculum:read")),
) -> dict[str, Any]:
    return _dump(await _scoped(db, Curriculum, curriculum_id, auth.tenant_id))


@router.patch("/curricula/{curriculum_id}")
async def patch_curriculum(
    curriculum_id: uuid.UUID,
    payload: CurriculumPatch,
    db: Db,
    auth: AuthContext = Depends(require_permissions("curriculum:manage")),
) -> dict[str, Any]:
    item = await _scoped(db, Curriculum, curriculum_id, auth.tenant_id)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(item, key, value)
    await _audit(db, auth, item, "updated", payload.model_dump(exclude_unset=True, mode="json"))
    await _commit(db)
    await db.refresh(item)
    return _dump(item)


@router.get("/curricula/{curriculum_id}/tree")
async def curriculum_tree(
    curriculum_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("curriculum:read")),
) -> list[dict[str, Any]]:
    await _scoped(db, Curriculum, curriculum_id, auth.tenant_id)
    nodes = list(
        (
            await db.scalars(
                select(CurriculumNode).where(
                    CurriculumNode.tenant_id == auth.tenant_id,
                    CurriculumNode.curriculum_id == curriculum_id,
                )
            )
        ).all()
    )
    return build_tree(nodes)


@router.post("/curricula/{curriculum_id}/nodes", status_code=201)
async def create_curriculum_node(
    curriculum_id: uuid.UUID,
    payload: NodeIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("curriculum:manage")),
) -> dict[str, Any]:
    await _scoped(db, Curriculum, curriculum_id, auth.tenant_id)
    if payload.parent_id:
        parent = await _validate_curriculum_node(db, auth, curriculum_id, payload.parent_id)
        await ensure_parent_acyclic(db, tenant_id=auth.tenant_id, node_id=None, parent_id=parent.id)
    data = payload.model_dump()
    metadata = data.pop("metadata")
    item = CurriculumNode(
        tenant_id=auth.tenant_id,
        curriculum_id=curriculum_id,
        metadata_json=metadata,
        **data,
    )
    db.add(item)
    await db.flush()
    await _audit(db, auth, item, "created", payload.model_dump(mode="json"))
    await _commit(db)
    return _dump(item)


@router.patch("/curriculum-nodes/{node_id}")
async def patch_curriculum_node(
    node_id: uuid.UUID,
    payload: NodePatch,
    db: Db,
    auth: AuthContext = Depends(require_permissions("curriculum:manage")),
) -> dict[str, Any]:
    item = await _scoped(db, CurriculumNode, node_id, auth.tenant_id)
    changes = payload.model_dump(exclude_unset=True)
    if "parent_id" in changes:
        if changes["parent_id"]:
            await _validate_curriculum_node(db, auth, item.curriculum_id, changes["parent_id"])
        await ensure_parent_acyclic(
            db,
            tenant_id=auth.tenant_id,
            node_id=item.id,
            parent_id=changes["parent_id"],
        )
    if "metadata" in changes:
        changes["metadata_json"] = changes.pop("metadata")
    for key, value in changes.items():
        setattr(item, key, value)
    await _audit(db, auth, item, "updated", payload.model_dump(exclude_unset=True, mode="json"))
    await _commit(db)
    await db.refresh(item)
    return _dump(item)


@router.post("/curricula/{curriculum_id}/prerequisites", status_code=201)
async def create_prerequisite(
    curriculum_id: uuid.UUID,
    payload: PrerequisiteIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("curriculum:manage")),
) -> dict[str, Any]:
    await _scoped(db, Curriculum, curriculum_id, auth.tenant_id)
    await _validate_curriculum_node(db, auth, curriculum_id, payload.prerequisite_node_id)
    await _validate_curriculum_node(db, auth, curriculum_id, payload.dependent_node_id)
    await ensure_prerequisite_acyclic(
        db,
        tenant_id=auth.tenant_id,
        curriculum_id=curriculum_id,
        prerequisite_id=payload.prerequisite_node_id,
        dependent_id=payload.dependent_node_id,
    )
    item = CurriculumPrerequisite(
        tenant_id=auth.tenant_id, curriculum_id=curriculum_id, **payload.model_dump()
    )
    db.add(item)
    await db.flush()
    await _audit(db, auth, item, "created", payload.model_dump(mode="json"))
    await _commit(db)
    return _dump(item)


@router.delete("/curriculum-prerequisites/{prerequisite_id}", status_code=204)
async def delete_prerequisite(
    prerequisite_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("curriculum:manage")),
) -> None:
    item = await _scoped(db, CurriculumPrerequisite, prerequisite_id, auth.tenant_id)
    await _audit(db, auth, item, "deleted", {})
    await db.delete(item)
    await db.commit()


async def _validate_assessment_refs(
    db: AsyncSession, auth: AuthContext, payload: AssessmentIn
) -> None:
    await _scoped(db, Curriculum, payload.curriculum_id, auth.tenant_id)
    if payload.subject_node_id:
        await _validate_curriculum_node(db, auth, payload.curriculum_id, payload.subject_node_id)
    if payload.academic_year_id:
        await _scoped(db, AcademicYear, payload.academic_year_id, auth.tenant_id)
    if payload.class_section_id:
        section = await _scoped(db, ClassSection, payload.class_section_id, auth.tenant_id)
        if payload.academic_year_id and section.academic_year_id != payload.academic_year_id:
            raise HTTPException(422, "Class section does not belong to academic year")


@router.get("/assessments")
async def list_assessments(
    db: Db, auth: AuthContext = Depends(require_permissions("assessment:read"))
) -> list[dict[str, Any]]:
    rows = await db.scalars(
        select(Assessment)
        .where(Assessment.tenant_id == auth.tenant_id)
        .order_by(Assessment.created_at.desc())
    )
    return [_dump(item) for item in rows]


@router.post("/assessments", status_code=201)
async def create_assessment(
    payload: AssessmentIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:manage")),
) -> dict[str, Any]:
    await _validate_assessment_refs(db, auth, payload)
    item = Assessment(
        tenant_id=auth.tenant_id,
        created_by=auth.user_id,
        status="DRAFT",
        **payload.model_dump(),
    )
    db.add(item)
    await db.flush()
    version = AssessmentVersion(
        tenant_id=auth.tenant_id,
        assessment_id=item.id,
        version_number=1,
        title=item.title,
        instructions=None,
        max_marks=item.max_marks,
        status="DRAFT",
        created_by=auth.user_id,
    )
    db.add(version)
    await _audit(db, auth, item, "created", payload.model_dump(mode="json"))
    await _commit(db)
    result = _dump(item)
    result["initial_version_id"] = version.id
    return result


@router.get("/assessments/{assessment_id}")
async def get_assessment(
    assessment_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:read")),
) -> dict[str, Any]:
    return _dump(await _scoped(db, Assessment, assessment_id, auth.tenant_id))


@router.patch("/assessments/{assessment_id}")
async def patch_assessment(
    assessment_id: uuid.UUID,
    payload: AssessmentPatch,
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:manage")),
) -> dict[str, Any]:
    item = await _scoped(db, Assessment, assessment_id, auth.tenant_id)
    if item.status != "DRAFT":
        raise HTTPException(409, "Only DRAFT assessments can be edited")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await _audit(db, auth, item, "updated", payload.model_dump(exclude_unset=True, mode="json"))
    await _commit(db)
    await db.refresh(item)
    return _dump(item)


@router.get("/assessments/{assessment_id}/versions")
async def list_assessment_versions(
    assessment_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:read")),
) -> list[dict[str, Any]]:
    await _scoped(db, Assessment, assessment_id, auth.tenant_id)
    rows = await db.scalars(
        select(AssessmentVersion)
        .where(
            AssessmentVersion.tenant_id == auth.tenant_id,
            AssessmentVersion.assessment_id == assessment_id,
        )
        .order_by(AssessmentVersion.version_number)
    )
    return [_dump(item) for item in rows]


@router.post("/assessments/{assessment_id}/versions", status_code=201)
async def create_assessment_version(
    assessment_id: uuid.UUID,
    payload: AssessmentVersionIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:manage")),
) -> dict[str, Any]:
    assessment = await _scoped(db, Assessment, assessment_id, auth.tenant_id)
    if assessment.status != "DRAFT":
        raise HTTPException(409, "New versions require a DRAFT assessment")
    latest = await db.scalar(
        select(func.max(AssessmentVersion.version_number)).where(
            AssessmentVersion.assessment_id == assessment.id
        )
    )
    item = AssessmentVersion(
        tenant_id=auth.tenant_id,
        assessment_id=assessment.id,
        version_number=(latest or 0) + 1,
        status="DRAFT",
        created_by=auth.user_id,
        **payload.model_dump(),
    )
    db.add(item)
    await db.flush()
    await _audit(db, auth, item, "created", payload.model_dump(mode="json"))
    await _commit(db)
    return _dump(item)


@router.post("/assessments/{assessment_id}/transition")
async def transition_assessment(
    assessment_id: uuid.UUID,
    payload: TransitionIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:approve")),
) -> dict[str, Any]:
    assessment = await _scoped(db, Assessment, assessment_id, auth.tenant_id)
    target = payload.to_status.upper()
    validate_transition(assessment.status, target)
    if target == "READY":
        version = await db.scalar(
            select(AssessmentVersion)
            .where(
                AssessmentVersion.tenant_id == auth.tenant_id,
                AssessmentVersion.assessment_id == assessment.id,
            )
            .order_by(AssessmentVersion.version_number.desc())
        )
        if version is None:
            raise HTTPException(409, "Assessment has no version")
        await ensure_assessment_ready(db, tenant_id=auth.tenant_id, assessment_version=version)
    old = assessment.status
    assessment.status = target
    await _audit(db, auth, assessment, "transitioned", {"from": old, "to": target})
    await _commit(db)
    await db.refresh(assessment)
    return _dump(assessment)


@router.get("/assessment-versions/{version_id}/questions")
async def question_tree(
    version_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:read")),
) -> list[dict[str, Any]]:
    await _scoped(db, AssessmentVersion, version_id, auth.tenant_id)
    rows = list(
        (
            await db.scalars(
                select(QuestionVersion)
                .where(
                    QuestionVersion.tenant_id == auth.tenant_id,
                    QuestionVersion.assessment_version_id == version_id,
                )
                .order_by(QuestionVersion.sequence)
            )
        ).all()
    )
    children: dict[uuid.UUID | None, list[QuestionVersion]] = {}
    for row in rows:
        children.setdefault(row.parent_question_version_id, []).append(row)

    def serialize(item: QuestionVersion) -> dict[str, Any]:
        value = _dump(item)
        value["children"] = [serialize(child) for child in children.get(item.id, [])]
        return value

    return [serialize(root) for root in children.get(None, [])]


@router.post("/assessment-versions/{version_id}/questions", status_code=201)
async def create_question(
    version_id: uuid.UUID,
    payload: QuestionIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:manage")),
) -> dict[str, Any]:
    version = await _scoped(db, AssessmentVersion, version_id, auth.tenant_id)
    assessment = await _scoped(db, Assessment, version.assessment_id, auth.tenant_id)
    if assessment.status != "DRAFT" or version.status != "DRAFT":
        raise HTTPException(409, "Questions can only be added to DRAFT assessments")
    if payload.parent_question_version_id:
        parent = await _scoped(
            db, QuestionVersion, payload.parent_question_version_id, auth.tenant_id
        )
        if parent.assessment_version_id != version.id:
            raise HTTPException(404, "Parent question not found")
    question = await db.scalar(
        select(Question).where(
            Question.tenant_id == auth.tenant_id,
            Question.assessment_id == assessment.id,
            Question.stable_code == payload.stable_code,
        )
    )
    if question is None:
        question = Question(
            tenant_id=auth.tenant_id,
            assessment_id=assessment.id,
            stable_code=payload.stable_code,
        )
        db.add(question)
        await db.flush()
    data = payload.model_dump(exclude={"stable_code"})
    item = QuestionVersion(
        tenant_id=auth.tenant_id,
        assessment_version_id=version.id,
        question_id=question.id,
        **data,
    )
    db.add(item)
    await db.flush()
    await _audit(db, auth, item, "created", payload.model_dump(mode="json"))
    await _commit(db)
    return _dump(item)


@router.patch("/question-versions/{question_version_id}")
async def patch_question(
    question_version_id: uuid.UUID,
    payload: QuestionPatch,
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:manage")),
) -> dict[str, Any]:
    item = await _scoped(db, QuestionVersion, question_version_id, auth.tenant_id)
    version = await _scoped(db, AssessmentVersion, item.assessment_version_id, auth.tenant_id)
    assessment = await _scoped(db, Assessment, version.assessment_id, auth.tenant_id)
    if assessment.status != "DRAFT" or version.status != "DRAFT":
        raise HTTPException(409, "Questions can only be edited in DRAFT")
    changes = payload.model_dump(exclude_unset=True)
    parent_id = changes.get("parent_question_version_id")
    if parent_id:
        if parent_id == item.id:
            raise HTTPException(409, "A question cannot parent itself")
        parent = await _scoped(db, QuestionVersion, parent_id, auth.tenant_id)
        if parent.assessment_version_id != version.id:
            raise HTTPException(404, "Parent question not found")
        current: uuid.UUID | None = parent.id
        while current:
            if current == item.id:
                raise HTTPException(409, "Question parent cycle detected")
            ancestor = await _scoped(db, QuestionVersion, current, auth.tenant_id)
            current = ancestor.parent_question_version_id
    for key, value in changes.items():
        setattr(item, key, value)
    await _audit(db, auth, item, "updated", payload.model_dump(exclude_unset=True, mode="json"))
    await _commit(db)
    await db.refresh(item)
    return _dump(item)


@router.delete("/question-versions/{question_version_id}", status_code=204)
async def delete_question(
    question_version_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:manage")),
) -> None:
    item = await _scoped(db, QuestionVersion, question_version_id, auth.tenant_id)
    version = await _scoped(db, AssessmentVersion, item.assessment_version_id, auth.tenant_id)
    assessment = await _scoped(db, Assessment, version.assessment_id, auth.tenant_id)
    if assessment.status != "DRAFT" or version.status != "DRAFT":
        raise HTTPException(409, "Questions can only be deleted in DRAFT")
    await _audit(db, auth, item, "deleted", {})
    await db.delete(item)
    await _commit(db)


@router.get("/assessment-versions/{version_id}/marks/reconcile")
async def reconcile_assessment_marks(
    version_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:read")),
) -> dict[str, Any]:
    version = await _scoped(db, AssessmentVersion, version_id, auth.tenant_id)
    questions = list(
        (
            await db.scalars(
                select(QuestionVersion).where(
                    QuestionVersion.tenant_id == auth.tenant_id,
                    QuestionVersion.assessment_version_id == version.id,
                )
            )
        ).all()
    )
    valid, total = reconcile_marks(questions, version.max_marks)
    return {"valid": valid, "leaf_marks_total": total, "assessment_max_marks": version.max_marks}


async def _answer_key_for(
    db: AsyncSession, auth: AuthContext, assessment_id: uuid.UUID
) -> AnswerKey:
    await _scoped(db, Assessment, assessment_id, auth.tenant_id)
    item = await db.scalar(
        select(AnswerKey).where(
            AnswerKey.tenant_id == auth.tenant_id,
            AnswerKey.assessment_id == assessment_id,
        )
    )
    if item is None:
        item = AnswerKey(tenant_id=auth.tenant_id, assessment_id=assessment_id)
        db.add(item)
        await db.flush()
    return item


@router.get("/assessments/{assessment_id}/answer-key-versions")
async def list_answer_key_versions(
    assessment_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:read")),
) -> list[dict[str, Any]]:
    await _scoped(db, Assessment, assessment_id, auth.tenant_id)
    key = await db.scalar(
        select(AnswerKey).where(
            AnswerKey.tenant_id == auth.tenant_id,
            AnswerKey.assessment_id == assessment_id,
        )
    )
    if key is None:
        return []
    rows = await db.scalars(
        select(AnswerKeyVersion)
        .where(
            AnswerKeyVersion.tenant_id == auth.tenant_id,
            AnswerKeyVersion.answer_key_id == key.id,
        )
        .order_by(AnswerKeyVersion.version_number)
    )
    return [_dump(item) for item in rows]


@router.post("/assessments/{assessment_id}/answer-key-versions", status_code=201)
async def create_answer_key_version(
    assessment_id: uuid.UUID,
    payload: AnswerKeyVersionIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:manage")),
) -> dict[str, Any]:
    key = await _answer_key_for(db, auth, assessment_id)
    version = await _scoped(db, AssessmentVersion, payload.assessment_version_id, auth.tenant_id)
    question = await _scoped(db, QuestionVersion, payload.question_version_id, auth.tenant_id)
    if version.assessment_id != assessment_id or question.assessment_version_id != version.id:
        raise HTTPException(404, "Question or assessment version not found")
    active = await db.scalar(
        select(AnswerKeyVersion).where(
            AnswerKeyVersion.answer_key_id == key.id,
            AnswerKeyVersion.question_version_id == question.id,
            AnswerKeyVersion.status.in_(["DRAFT", "REVIEW_REQUIRED", "APPROVED"]),
        )
    )
    if active:
        if active.status == "APPROVED":
            active.status = "SUPERSEDED"
        else:
            raise HTTPException(409, "An editable answer key version already exists")
    latest = await db.scalar(
        select(func.max(AnswerKeyVersion.version_number)).where(
            AnswerKeyVersion.answer_key_id == key.id
        )
    )
    item = AnswerKeyVersion(
        tenant_id=auth.tenant_id,
        answer_key_id=key.id,
        version_number=(latest or 0) + 1,
        created_by=auth.user_id,
        **payload.model_dump(),
    )
    db.add(item)
    await db.flush()
    await _audit(db, auth, item, "created", payload.model_dump(mode="json"))
    await _commit(db)
    return _dump(item)


@router.patch("/answer-key-versions/{version_id}")
async def patch_answer_key_version(
    version_id: uuid.UUID,
    payload: AnswerKeyPatch,
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:manage")),
) -> dict[str, Any]:
    item = await _scoped(db, AnswerKeyVersion, version_id, auth.tenant_id)
    if item.status in {"APPROVED", "SUPERSEDED"}:
        raise HTTPException(409, "Approved answer keys are immutable; create a new version")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await _audit(db, auth, item, "updated", payload.model_dump(exclude_unset=True, mode="json"))
    await _commit(db)
    await db.refresh(item)
    return _dump(item)


@router.post("/answer-key-versions/{version_id}/approve")
async def approve_answer_key(
    version_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:approve")),
) -> dict[str, Any]:
    item = await _scoped(db, AnswerKeyVersion, version_id, auth.tenant_id)
    if item.status not in {"DRAFT", "REVIEW_REQUIRED"}:
        raise HTTPException(409, "Answer key version cannot be approved")
    item.status = "APPROVED"
    item.approved_by = auth.user_id
    item.approved_at = datetime.now(UTC)
    await _audit(db, auth, item, "approved", {})
    await _commit(db)
    await db.refresh(item)
    return _dump(item)


@router.post("/assessments/{assessment_id}/rubrics", status_code=201)
async def create_rubric(
    assessment_id: uuid.UUID,
    payload: RubricIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("rubric:manage")),
) -> dict[str, Any]:
    await _scoped(db, Assessment, assessment_id, auth.tenant_id)
    question = await _scoped(db, QuestionVersion, payload.question_version_id, auth.tenant_id)
    version = await _scoped(db, AssessmentVersion, question.assessment_version_id, auth.tenant_id)
    if version.assessment_id != assessment_id:
        raise HTTPException(404, "Question not found")
    item = Rubric(tenant_id=auth.tenant_id, assessment_id=assessment_id, **payload.model_dump())
    db.add(item)
    await db.flush()
    await _audit(db, auth, item, "created", payload.model_dump(mode="json"))
    await _commit(db)
    return _dump(item)


@router.get("/assessments/{assessment_id}/rubrics")
async def list_rubrics(
    assessment_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("rubric:read")),
) -> list[dict[str, Any]]:
    await _scoped(db, Assessment, assessment_id, auth.tenant_id)
    rows = await db.scalars(
        select(Rubric).where(
            Rubric.tenant_id == auth.tenant_id, Rubric.assessment_id == assessment_id
        )
    )
    return [_dump(item) for item in rows]


@router.post("/rubrics/{rubric_id}/versions", status_code=201)
async def create_rubric_version(
    rubric_id: uuid.UUID,
    payload: RubricVersionIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("rubric:manage")),
) -> dict[str, Any]:
    rubric = await _scoped(db, Rubric, rubric_id, auth.tenant_id)
    question = await _scoped(db, QuestionVersion, payload.question_version_id, auth.tenant_id)
    if rubric.question_version_id != question.id:
        raise HTTPException(404, "Question not found")
    active = await db.scalar(
        select(RubricVersion).where(
            RubricVersion.rubric_id == rubric.id,
            RubricVersion.question_version_id == question.id,
            RubricVersion.status.in_(["DRAFT", "REVIEW_REQUIRED", "APPROVED"]),
        )
    )
    if active:
        if active.status == "APPROVED":
            active.status = "SUPERSEDED"
        else:
            raise HTTPException(409, "An editable rubric version already exists")
    latest = await db.scalar(
        select(func.max(RubricVersion.version_number)).where(RubricVersion.rubric_id == rubric.id)
    )
    item = RubricVersion(
        tenant_id=auth.tenant_id,
        rubric_id=rubric.id,
        version_number=(latest or 0) + 1,
        created_by=auth.user_id,
        **payload.model_dump(),
    )
    db.add(item)
    await db.flush()
    await _audit(db, auth, item, "created", payload.model_dump(mode="json"))
    await _commit(db)
    return _dump(item)


@router.patch("/rubric-versions/{version_id}")
async def patch_rubric_version(
    version_id: uuid.UUID,
    payload: RubricVersionIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("rubric:manage")),
) -> dict[str, Any]:
    item = await _scoped(db, RubricVersion, version_id, auth.tenant_id)
    if item.status in {"APPROVED", "SUPERSEDED"}:
        raise HTTPException(409, "Approved rubrics are immutable; create a new version")
    item.status = payload.status
    item.source_type = payload.source_type
    await _audit(db, auth, item, "updated", payload.model_dump(mode="json"))
    await _commit(db)
    await db.refresh(item)
    return _dump(item)


@router.post("/rubric-versions/{version_id}/criteria", status_code=201)
async def create_criterion(
    version_id: uuid.UUID,
    payload: CriterionIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("rubric:manage")),
) -> dict[str, Any]:
    version = await _scoped(db, RubricVersion, version_id, auth.tenant_id)
    if version.status in {"APPROVED", "SUPERSEDED"}:
        raise HTTPException(409, "Approved rubrics are immutable")
    item = RubricCriterion(
        tenant_id=auth.tenant_id, rubric_version_id=version.id, **payload.model_dump()
    )
    db.add(item)
    await db.flush()
    await _audit(db, auth, item, "created", payload.model_dump(mode="json"))
    await _commit(db)
    return _dump(item)


@router.get("/rubric-versions/{version_id}/criteria")
async def list_criteria(
    version_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("rubric:read")),
) -> list[dict[str, Any]]:
    await _scoped(db, RubricVersion, version_id, auth.tenant_id)
    rows = await db.scalars(
        select(RubricCriterion)
        .where(
            RubricCriterion.tenant_id == auth.tenant_id,
            RubricCriterion.rubric_version_id == version_id,
        )
        .order_by(RubricCriterion.sequence)
    )
    return [_dump(item) for item in rows]


@router.patch("/rubric-criteria/{criterion_id}")
async def patch_criterion(
    criterion_id: uuid.UUID,
    payload: CriterionPatch,
    db: Db,
    auth: AuthContext = Depends(require_permissions("rubric:manage")),
) -> dict[str, Any]:
    item = await _scoped(db, RubricCriterion, criterion_id, auth.tenant_id)
    version = await _scoped(db, RubricVersion, item.rubric_version_id, auth.tenant_id)
    if version.status in {"APPROVED", "SUPERSEDED"}:
        raise HTTPException(409, "Approved rubrics are immutable")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await _audit(db, auth, item, "updated", payload.model_dump(exclude_unset=True, mode="json"))
    await _commit(db)
    await db.refresh(item)
    return _dump(item)


@router.delete("/rubric-criteria/{criterion_id}", status_code=204)
async def delete_criterion(
    criterion_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("rubric:manage")),
) -> None:
    item = await _scoped(db, RubricCriterion, criterion_id, auth.tenant_id)
    version = await _scoped(db, RubricVersion, item.rubric_version_id, auth.tenant_id)
    if version.status in {"APPROVED", "SUPERSEDED"}:
        raise HTTPException(409, "Approved rubrics are immutable")
    await _audit(db, auth, item, "deleted", {})
    await db.delete(item)
    await _commit(db)


@router.get("/rubric-versions/{version_id}/reconcile")
async def reconcile_rubric_version(
    version_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("rubric:read")),
) -> dict[str, Any]:
    version = await _scoped(db, RubricVersion, version_id, auth.tenant_id)
    question = await _scoped(db, QuestionVersion, version.question_version_id, auth.tenant_id)
    criteria = list(
        (
            await db.scalars(
                select(RubricCriterion).where(
                    RubricCriterion.tenant_id == auth.tenant_id,
                    RubricCriterion.rubric_version_id == version.id,
                )
            )
        ).all()
    )
    valid, total = reconcile_rubric(criteria, question.max_marks)
    return {"valid": valid, "additive_total": total, "question_max_marks": question.max_marks}


@router.post("/rubric-versions/{version_id}/approve")
async def approve_rubric(
    version_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("rubric:approve")),
) -> dict[str, Any]:
    item = await _scoped(db, RubricVersion, version_id, auth.tenant_id)
    if item.status not in {"DRAFT", "REVIEW_REQUIRED"}:
        raise HTTPException(409, "Rubric version cannot be approved")
    question = await _scoped(db, QuestionVersion, item.question_version_id, auth.tenant_id)
    criteria = list(
        (
            await db.scalars(
                select(RubricCriterion).where(
                    RubricCriterion.tenant_id == auth.tenant_id,
                    RubricCriterion.rubric_version_id == item.id,
                )
            )
        ).all()
    )
    valid, _ = reconcile_rubric(criteria, question.max_marks)
    if not valid:
        raise HTTPException(409, "Rubric marks do not reconcile")
    item.status = "APPROVED"
    item.approved_by = auth.user_id
    item.approved_at = datetime.now(UTC)
    await _audit(db, auth, item, "approved", {})
    await _commit(db)
    await db.refresh(item)
    return _dump(item)


@router.post("/question-versions/{question_version_id}/curriculum-mappings", status_code=201)
async def create_mapping(
    question_version_id: uuid.UUID,
    payload: MappingIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("curriculum:manage")),
) -> dict[str, Any]:
    question = await _scoped(db, QuestionVersion, question_version_id, auth.tenant_id)
    node = await _scoped(db, CurriculumNode, payload.curriculum_node_id, auth.tenant_id)
    version = await _scoped(db, AssessmentVersion, question.assessment_version_id, auth.tenant_id)
    assessment = await _scoped(db, Assessment, version.assessment_id, auth.tenant_id)
    if node.curriculum_id != assessment.curriculum_id:
        raise HTTPException(422, "Curriculum node does not belong to assessment curriculum")
    item = QuestionCurriculumMapping(
        tenant_id=auth.tenant_id,
        question_version_id=question.id,
        **payload.model_dump(),
    )
    db.add(item)
    await db.flush()
    await _audit(db, auth, item, "created", payload.model_dump(mode="json"))
    await _commit(db)
    return _dump(item)


@router.get("/question-versions/{question_version_id}/curriculum-mappings")
async def list_mappings(
    question_version_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("curriculum:read")),
) -> list[dict[str, Any]]:
    await _scoped(db, QuestionVersion, question_version_id, auth.tenant_id)
    rows = await db.scalars(
        select(QuestionCurriculumMapping).where(
            QuestionCurriculumMapping.tenant_id == auth.tenant_id,
            QuestionCurriculumMapping.question_version_id == question_version_id,
        )
    )
    return [_dump(item) for item in rows]


@router.delete("/question-curriculum-mappings/{mapping_id}", status_code=204)
async def delete_mapping(
    mapping_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("curriculum:manage")),
) -> None:
    item = await _scoped(db, QuestionCurriculumMapping, mapping_id, auth.tenant_id)
    await _audit(db, auth, item, "deleted", {})
    await db.delete(item)
    await _commit(db)


@router.post("/ai/proposals/answer-key")
async def propose_answer_key(
    payload: dict[str, Any],
    db: Db,
    auth: AuthContext = Depends(require_permissions("assessment:manage")),
) -> Response:
    await unavailable(db, tenant_id=auth.tenant_id, operation="propose_answer_key", request=payload)
    raise AssertionError("unreachable")


@router.post("/ai/proposals/rubric")
async def propose_rubric(
    payload: dict[str, Any],
    db: Db,
    auth: AuthContext = Depends(require_permissions("rubric:manage")),
) -> Response:
    await unavailable(db, tenant_id=auth.tenant_id, operation="propose_rubric", request=payload)
    raise AssertionError("unreachable")


@router.post("/ai/proposals/curriculum-mapping")
async def suggest_curriculum_mapping(
    payload: dict[str, Any],
    db: Db,
    auth: AuthContext = Depends(require_permissions("curriculum:manage")),
) -> Response:
    await unavailable(
        db,
        tenant_id=auth.tenant_id,
        operation="suggest_curriculum_mapping",
        request=payload,
    )
    raise AssertionError("unreachable")
