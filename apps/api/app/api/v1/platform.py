# ruff: noqa: B008
import csv
import hashlib
import io
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import AuthContext, require_permissions
from app.core.config import Settings, get_settings
from app.core.security import AuthProvider, get_auth_provider, verify_password
from app.db.models import (
    AcademicYear,
    AuditEvent,
    ClassSection,
    Guardian,
    ImportSession,
    Institution,
    Permission,
    Role,
    RolePermission,
    Student,
    StudentGuardian,
    Tenant,
    User,
    UserRole,
)
from app.db.session import get_db_session

router = APIRouter()
Db = Annotated[AsyncSession, Depends(get_db_session)]


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: str
    password: str
    tenant_slug: str | None = None


class UserOut(OrmModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    display_name: str
    status: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class MeOut(UserOut):
    roles: list[str]
    permissions: list[str]


class InstitutionOut(OrmModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    name: str
    created_at: datetime
    updated_at: datetime


class AcademicYearIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    starts_on: date
    ends_on: date
    is_current: bool = False


class AcademicYearPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    starts_on: date | None = None
    ends_on: date | None = None
    is_current: bool | None = None


class AcademicYearOut(AcademicYearIn, OrmModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    institution_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ClassSectionIn(BaseModel):
    academic_year_id: uuid.UUID
    name: str = Field(min_length=1, max_length=100)
    grade_label: str = Field(min_length=1, max_length=100)


class ClassSectionPatch(BaseModel):
    academic_year_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    grade_label: str | None = Field(default=None, min_length=1, max_length=100)


class ClassSectionOut(ClassSectionIn, OrmModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    institution_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class StudentIn(BaseModel):
    student_code: str = Field(min_length=1, max_length=100)
    admission_number: str | None = Field(default=None, max_length=100)
    roll_number: str | None = Field(default=None, max_length=100)
    full_name: str = Field(min_length=1, max_length=255)
    class_section_id: uuid.UUID | None = None
    academic_year_id: uuid.UUID | None = None
    status: str = "active"


class StudentPatch(BaseModel):
    student_code: str | None = Field(default=None, min_length=1, max_length=100)
    admission_number: str | None = Field(default=None, max_length=100)
    roll_number: str | None = Field(default=None, max_length=100)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    class_section_id: uuid.UUID | None = None
    academic_year_id: uuid.UUID | None = None
    status: str | None = None


class StudentOut(StudentIn, OrmModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class GuardianIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=32)


class GuardianPatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=32)


class GuardianOut(GuardianIn, OrmModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class RelationshipIn(BaseModel):
    relationship_type: str = Field(min_length=1, max_length=64)


class StudentGuardianLinkOut(BaseModel):
    student_id: uuid.UUID
    guardian_id: uuid.UUID
    display_name: str
    email: str | None = None
    phone: str | None = None
    relationship_type: str


class CommitIn(BaseModel):
    import_session_id: uuid.UUID | None = None
    validation_token: uuid.UUID | None = None

    def session_id(self) -> uuid.UUID:
        value = self.import_session_id or self.validation_token
        if value is None:
            raise HTTPException(422, "import_session_id is required")
        return value


class ImportValidationOut(BaseModel):
    import_session_id: uuid.UUID
    status: str
    valid_row_count: int
    row_results: list[dict[str, Any]]
    expires_at: datetime


class ImportCommitOut(BaseModel):
    import_session_id: uuid.UUID
    status: str
    committed_count: int


def _validate_dates(starts_on: date, ends_on: date) -> None:
    if ends_on < starts_on:
        raise HTTPException(422, "ends_on must be on or after starts_on")


async def _institution(db: AsyncSession, tenant_id: uuid.UUID) -> Institution:
    item = await db.scalar(select(Institution).where(Institution.tenant_id == tenant_id))
    if item is None:
        raise HTTPException(404, "Institution not found")
    return item


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


async def _flush(db: AsyncSession) -> None:
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Resource conflicts with an existing record") from exc


async def _authorization_for_user(
    db: AsyncSession, user_id: uuid.UUID, tenant_id: uuid.UUID
) -> tuple[frozenset[str], frozenset[str]]:
    role_rows = (
        await db.execute(
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id, UserRole.tenant_id == tenant_id)
        )
    ).scalars()
    roles = frozenset(role_rows)
    permission_rows = (
        await db.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id, UserRole.tenant_id == tenant_id)
        )
    ).scalars()
    return roles, frozenset(permission_rows)


@router.post("/auth/login", response_model=TokenOut)
async def login(
    payload: LoginRequest, db: Db, provider: AuthProvider = Depends(get_auth_provider)
) -> TokenOut:
    query = (
        select(User)
        .join(Tenant, Tenant.id == User.tenant_id)
        .where(
            User.email == payload.email.strip().lower(),
            User.status == "active",
            Tenant.status == "active",
        )
    )
    if payload.tenant_slug:
        query = query.where(Tenant.slug == payload.tenant_slug)
    users = list((await db.execute(query)).scalars().all())
    if (
        len(users) != 1
        or not users[0].password_hash
        or not verify_password(payload.password, users[0].password_hash)
    ):
        raise HTTPException(401, "Invalid credentials")
    user = users[0]
    roles, permissions = await _authorization_for_user(db, user.id, user.tenant_id)
    context = AuthContext(user.id, user.tenant_id, roles, permissions)
    token, ttl = provider.issue_access_token(context)
    user.last_login_at = datetime.now(UTC)
    await db.commit()
    return TokenOut(access_token=token, expires_in=ttl, user=UserOut.model_validate(user))


@router.get("/auth/me", response_model=MeOut)
async def me(db: Db, auth: AuthContext = Depends(require_permissions())) -> MeOut:
    user = await _scoped(db, User, auth.user_id, auth.tenant_id)
    return MeOut(
        **UserOut.model_validate(user).model_dump(),
        roles=sorted(auth.roles),
        permissions=sorted(auth.permissions),
    )


@router.get("/institution", response_model=InstitutionOut)
async def get_institution(
    db: Db, auth: AuthContext = Depends(require_permissions("institution:read"))
) -> Institution:
    return await _institution(db, auth.tenant_id)


@router.get("/academic-years", response_model=list[AcademicYearOut])
async def list_academic_years(
    db: Db, auth: AuthContext = Depends(require_permissions("academic_year:read"))
) -> list[AcademicYear]:
    return list(
        (
            await db.execute(
                select(AcademicYear)
                .where(AcademicYear.tenant_id == auth.tenant_id)
                .order_by(AcademicYear.starts_on.desc())
            )
        ).scalars()
    )


@router.post("/academic-years", response_model=AcademicYearOut, status_code=201)
async def create_academic_year(
    payload: AcademicYearIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("academic_year:write")),
) -> AcademicYear:
    _validate_dates(payload.starts_on, payload.ends_on)
    institution = await _institution(db, auth.tenant_id)
    item = AcademicYear(
        tenant_id=auth.tenant_id, institution_id=institution.id, **payload.model_dump()
    )
    db.add(item)
    await _flush(db)
    await _audit(db, auth, item, "created", payload.model_dump(mode="json"))
    await _commit(db)
    return item


@router.get("/academic-years/{item_id}", response_model=AcademicYearOut)
async def get_academic_year(
    item_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("academic_year:read")),
) -> AcademicYear:
    return await _scoped(db, AcademicYear, item_id, auth.tenant_id)


@router.patch("/academic-years/{item_id}", response_model=AcademicYearOut)
async def patch_academic_year(
    item_id: uuid.UUID,
    payload: AcademicYearPatch,
    db: Db,
    auth: AuthContext = Depends(require_permissions("academic_year:write")),
) -> AcademicYear:
    item = await _scoped(db, AcademicYear, item_id, auth.tenant_id)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(item, key, value)
    _validate_dates(item.starts_on, item.ends_on)
    await _audit(db, auth, item, "updated", payload.model_dump(exclude_unset=True, mode="json"))
    await _commit(db)
    await db.refresh(item)
    return item


async def _validate_section_refs(
    db: AsyncSession, auth: AuthContext, year_id: uuid.UUID
) -> AcademicYear:
    return await _scoped(db, AcademicYear, year_id, auth.tenant_id)


@router.get("/class-sections", response_model=list[ClassSectionOut])
async def list_class_sections(
    db: Db, auth: AuthContext = Depends(require_permissions("class_section:read"))
) -> list[ClassSection]:
    return list(
        (
            await db.execute(
                select(ClassSection)
                .where(ClassSection.tenant_id == auth.tenant_id)
                .order_by(ClassSection.grade_label, ClassSection.name)
            )
        ).scalars()
    )


@router.post("/class-sections", response_model=ClassSectionOut, status_code=201)
async def create_class_section(
    payload: ClassSectionIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("class_section:write")),
) -> ClassSection:
    await _validate_section_refs(db, auth, payload.academic_year_id)
    institution = await _institution(db, auth.tenant_id)
    item = ClassSection(
        tenant_id=auth.tenant_id, institution_id=institution.id, **payload.model_dump()
    )
    db.add(item)
    await _flush(db)
    await _audit(db, auth, item, "created", payload.model_dump(mode="json"))
    await _commit(db)
    return item


@router.get("/class-sections/{item_id}", response_model=ClassSectionOut)
async def get_class_section(
    item_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("class_section:read")),
) -> ClassSection:
    return await _scoped(db, ClassSection, item_id, auth.tenant_id)


@router.patch("/class-sections/{item_id}", response_model=ClassSectionOut)
async def patch_class_section(
    item_id: uuid.UUID,
    payload: ClassSectionPatch,
    db: Db,
    auth: AuthContext = Depends(require_permissions("class_section:write")),
) -> ClassSection:
    item = await _scoped(db, ClassSection, item_id, auth.tenant_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("academic_year_id"):
        await _validate_section_refs(db, auth, changes["academic_year_id"])
    for key, value in changes.items():
        setattr(item, key, value)
    await _audit(db, auth, item, "updated", payload.model_dump(exclude_unset=True, mode="json"))
    await _commit(db)
    await db.refresh(item)
    return item


async def _validate_student_refs(
    db: AsyncSession,
    auth: AuthContext,
    year_id: uuid.UUID | None,
    section_id: uuid.UUID | None,
) -> None:
    if year_id is None and section_id is None:
        return
    if year_id is None or section_id is None:
        raise HTTPException(422, "Academic year and class section must be provided together")
    await _scoped(db, AcademicYear, year_id, auth.tenant_id)
    section = await _scoped(db, ClassSection, section_id, auth.tenant_id)
    if section.academic_year_id != year_id:
        raise HTTPException(422, "Class section does not belong to academic year")


@router.post("/students/import/validate", response_model=ImportValidationOut)
async def validate_import(
    db: Db,
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_permissions("student:import")),
    settings: Settings = Depends(get_settings),
) -> ImportValidationOut:
    content = await file.read(settings.student_import_max_bytes + 1)
    if len(content) > settings.student_import_max_bytes:
        raise HTTPException(413, "CSV exceeds configured size limit")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(422, "CSV must be UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text))
    required_headers = [
        "student_code",
        "admission_number",
        "roll_number",
        "full_name",
        "academic_year",
        "class_section",
    ]
    if reader.fieldnames != required_headers:
        raise HTTPException(422, f"CSV headers must be: {','.join(required_headers)}")
    rows = list(reader)
    if len(rows) > settings.student_import_max_rows:
        raise HTTPException(413, "CSV exceeds configured row limit")
    institution = await _institution(db, auth.tenant_id)
    years = {
        x.name: x
        for x in (
            await db.execute(select(AcademicYear).where(AcademicYear.tenant_id == auth.tenant_id))
        ).scalars()
    }
    sections = {
        (x.academic_year_id, x.name): x
        for x in (
            await db.execute(select(ClassSection).where(ClassSection.tenant_id == auth.tenant_id))
        ).scalars()
    }
    existing_codes = set(
        (
            await db.execute(
                select(Student.student_code).where(
                    Student.tenant_id == auth.tenant_id,
                    Student.institution_id == institution.id,
                )
            )
        ).scalars()
    )
    existing_rolls = {
        (class_section_id, roll_number)
        for class_section_id, roll_number in (
            await db.execute(
                select(Student.class_section_id, Student.roll_number).where(
                    Student.tenant_id == auth.tenant_id,
                    Student.class_section_id.is_not(None),
                    Student.roll_number.is_not(None),
                )
            )
        ).all()
    }
    seen_codes: set[str] = set()
    seen_rolls: set[tuple[uuid.UUID, str]] = set()
    results: list[dict[str, Any]] = []
    for number, raw in enumerate(rows, 2):
        row = {key: (value or "").strip() for key, value in raw.items()}
        outcome = "VALID"
        reason_code: str | None = None
        year = years.get(row["academic_year"])
        section = sections.get((year.id, row["class_section"])) if year else None
        roll = row["roll_number"]
        if (
            not row["student_code"]
            or not row["full_name"]
            or not row["academic_year"]
            or not row["class_section"]
        ):
            outcome = "MISSING_REQUIRED_FIELD"
        elif (
            len(row["student_code"]) > 100
            or len(row["admission_number"]) > 100
            or len(roll) > 100
            or len(row["full_name"]) > 255
        ):
            outcome = "INVALID"
        elif row["student_code"] in seen_codes:
            outcome = "DUPLICATE_IN_FILE"
            reason_code = "STUDENT_CODE_DUPLICATE_IN_FILE"
        elif row["student_code"] in existing_codes:
            outcome = "DUPLICATE_EXISTING"
            reason_code = "STUDENT_CODE_DUPLICATE_EXISTING"
        elif year is None or section is None:
            outcome = "UNKNOWN_CLASS"
        elif roll and (section.id, roll) in seen_rolls:
            outcome = "DUPLICATE_IN_FILE"
            reason_code = "CLASS_ROLL_DUPLICATE_IN_FILE"
        elif roll and (section.id, roll) in existing_rolls:
            outcome = "DUPLICATE_EXISTING"
            reason_code = "CLASS_ROLL_DUPLICATE_EXISTING"
        if row["student_code"]:
            seen_codes.add(row["student_code"])
        if outcome == "VALID" and section is not None and roll:
            seen_rolls.add((section.id, roll))
        entry: dict[str, Any] = {
            "row": number,
            "outcome": outcome,
            "data": row,
            "academic_year_id": str(year.id) if year else None,
            "class_section_id": str(section.id) if section else None,
        }
        if reason_code is not None:
            entry["reason_code"] = reason_code
        results.append(entry)
    expires = datetime.now(UTC) + timedelta(minutes=30)
    session = ImportSession(
        tenant_id=auth.tenant_id,
        institution_id=institution.id,
        created_by_user_id=auth.user_id,
        status="VALIDATED",
        row_results=results,
        valid_row_count=sum(x["outcome"] == "VALID" for x in results),
        expires_at=expires,
        content_hash=hashlib.sha256(content).hexdigest(),
    )
    db.add(session)
    await db.commit()
    return ImportValidationOut(
        import_session_id=session.id,
        status=session.status,
        valid_row_count=session.valid_row_count,
        row_results=results,
        expires_at=expires,
    )


@router.post("/students/import/commit", response_model=ImportCommitOut)
async def commit_import(
    payload: CommitIn, db: Db, auth: AuthContext = Depends(require_permissions("student:import"))
) -> ImportCommitOut:
    session = await db.scalar(
        select(ImportSession)
        .where(
            ImportSession.id == payload.session_id(),
            ImportSession.tenant_id == auth.tenant_id,
        )
        .with_for_update()
    )
    if session is None:
        raise HTTPException(404, "Resource not found")
    if session.status == "COMMITTED":
        return ImportCommitOut(
            import_session_id=session.id,
            status=session.status,
            committed_count=session.valid_row_count,
        )
    now = datetime.now(UTC)
    if session.status == "VALIDATED" and session.expires_at <= now:
        session.status = "EXPIRED"
        await db.commit()
        raise HTTPException(
            409,
            {
                "code": "IMPORT_SESSION_EXPIRED",
                "message": "The validated import session has expired.",
            },
        )
    if session.status != "VALIDATED":
        raise HTTPException(
            409,
            {
                "code": "IMPORT_SESSION_INVALID",
                "message": "The import session is not available for commit.",
            },
        )
    for result in session.row_results:
        if result["outcome"] != "VALID":
            continue
        row = result["data"]
        db.add(
            Student(
                tenant_id=auth.tenant_id,
                institution_id=session.institution_id,
                student_code=row["student_code"],
                admission_number=row["admission_number"] or None,
                roll_number=row["roll_number"] or None,
                full_name=row["full_name"],
                academic_year_id=uuid.UUID(result["academic_year_id"]),
                class_section_id=uuid.UUID(result["class_section_id"]),
                status="active",
            )
        )
    session.status = "COMMITTED"
    session.committed_at = now
    await _audit(db, auth, session, "committed", {"valid_row_count": session.valid_row_count})
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            409,
            {
                "code": "STUDENT_IMPORT_CONFLICT",
                "message": (
                    "Roster data changed after validation. Revalidate the CSV before importing."
                ),
            },
        ) from exc
    return ImportCommitOut(
        import_session_id=session.id, status=session.status, committed_count=session.valid_row_count
    )


@router.get("/students", response_model=list[StudentOut])
async def list_students(
    db: Db, auth: AuthContext = Depends(require_permissions("student:read"))
) -> list[Student]:
    return list(
        (
            await db.execute(
                select(Student)
                .where(Student.tenant_id == auth.tenant_id)
                .order_by(Student.full_name)
            )
        ).scalars()
    )


@router.post("/students", response_model=StudentOut, status_code=201)
async def create_student(
    payload: StudentIn, db: Db, auth: AuthContext = Depends(require_permissions("student:write"))
) -> Student:
    await _validate_student_refs(db, auth, payload.academic_year_id, payload.class_section_id)
    institution = await _institution(db, auth.tenant_id)
    item = Student(tenant_id=auth.tenant_id, institution_id=institution.id, **payload.model_dump())
    db.add(item)
    await _flush(db)
    await _audit(db, auth, item, "created", payload.model_dump(mode="json"))
    await _commit(db)
    return item


@router.get("/students/{item_id}", response_model=StudentOut)
async def get_student(
    item_id: uuid.UUID, db: Db, auth: AuthContext = Depends(require_permissions("student:read"))
) -> Student:
    return await _scoped(db, Student, item_id, auth.tenant_id)


@router.patch("/students/{item_id}", response_model=StudentOut)
async def patch_student(
    item_id: uuid.UUID,
    payload: StudentPatch,
    db: Db,
    auth: AuthContext = Depends(require_permissions("student:write")),
) -> Student:
    item = await _scoped(db, Student, item_id, auth.tenant_id)
    changes = payload.model_dump(exclude_unset=True)
    year_id = changes.get("academic_year_id", item.academic_year_id)
    section_id = changes.get("class_section_id", item.class_section_id)
    if year_id is None or section_id is None:
        raise HTTPException(422, "academic_year_id and class_section_id are required")
    await _validate_student_refs(db, auth, year_id, section_id)
    for key, value in changes.items():
        setattr(item, key, value)
    await _audit(db, auth, item, "updated", payload.model_dump(exclude_unset=True, mode="json"))
    await _commit(db)
    await db.refresh(item)
    return item


@router.get("/guardians", response_model=list[GuardianOut])
async def list_guardians(
    db: Db, auth: AuthContext = Depends(require_permissions("guardian:read"))
) -> list[Guardian]:
    return list(
        (
            await db.execute(
                select(Guardian)
                .where(Guardian.tenant_id == auth.tenant_id)
                .order_by(Guardian.display_name)
            )
        ).scalars()
    )


@router.post("/guardians", response_model=GuardianOut, status_code=201)
async def create_guardian(
    payload: GuardianIn, db: Db, auth: AuthContext = Depends(require_permissions("guardian:write"))
) -> Guardian:
    item = Guardian(tenant_id=auth.tenant_id, **payload.model_dump())
    db.add(item)
    await _flush(db)
    await _audit(db, auth, item, "created", payload.model_dump(mode="json"))
    await _commit(db)
    return item


@router.get("/guardians/{item_id}", response_model=GuardianOut)
async def get_guardian(
    item_id: uuid.UUID, db: Db, auth: AuthContext = Depends(require_permissions("guardian:read"))
) -> Guardian:
    return await _scoped(db, Guardian, item_id, auth.tenant_id)


@router.patch("/guardians/{item_id}", response_model=GuardianOut)
async def patch_guardian(
    item_id: uuid.UUID,
    payload: GuardianPatch,
    db: Db,
    auth: AuthContext = Depends(require_permissions("guardian:write")),
) -> Guardian:
    item = await _scoped(db, Guardian, item_id, auth.tenant_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await _audit(db, auth, item, "updated", payload.model_dump(exclude_unset=True, mode="json"))
    await _commit(db)
    await db.refresh(item)
    return item


@router.get(
    "/students/{student_id}/guardians",
    response_model=list[StudentGuardianLinkOut],
)
async def list_student_guardians(
    student_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("guardian:read")),
) -> list[StudentGuardianLinkOut]:
    await _scoped(db, Student, student_id, auth.tenant_id)
    rows = (
        await db.execute(
            select(StudentGuardian, Guardian)
            .join(Guardian, Guardian.id == StudentGuardian.guardian_id)
            .where(
                StudentGuardian.tenant_id == auth.tenant_id,
                StudentGuardian.student_id == student_id,
                Guardian.tenant_id == auth.tenant_id,
            )
            .order_by(Guardian.display_name)
        )
    ).all()
    return [
        StudentGuardianLinkOut(
            student_id=link.student_id,
            guardian_id=guardian.id,
            display_name=guardian.display_name,
            email=guardian.email,
            phone=guardian.phone,
            relationship_type=link.relationship_type,
        )
        for link, guardian in rows
    ]


@router.post("/students/{student_id}/guardians/{guardian_id}", status_code=201)
async def link_guardian(
    student_id: uuid.UUID,
    guardian_id: uuid.UUID,
    payload: RelationshipIn,
    db: Db,
    auth: AuthContext = Depends(require_permissions("guardian:write")),
) -> dict[str, Any]:
    student = await _scoped(db, Student, student_id, auth.tenant_id)
    await _scoped(db, Guardian, guardian_id, auth.tenant_id)
    link = StudentGuardian(
        tenant_id=auth.tenant_id,
        student_id=student_id,
        guardian_id=guardian_id,
        relationship_type=payload.relationship_type,
    )
    db.add(link)
    await _flush(db)
    await _audit(
        db,
        auth,
        student,
        "guardian_linked",
        {"guardian_id": str(guardian_id), "relationship_type": payload.relationship_type},
    )
    await _commit(db)
    return {
        "student_id": student_id,
        "guardian_id": guardian_id,
        "relationship_type": payload.relationship_type,
    }


@router.delete("/students/{student_id}/guardians/{guardian_id}", status_code=204)
async def unlink_guardian(
    student_id: uuid.UUID,
    guardian_id: uuid.UUID,
    db: Db,
    auth: AuthContext = Depends(require_permissions("guardian:write")),
) -> None:
    student = await _scoped(db, Student, student_id, auth.tenant_id)
    link = await db.scalar(
        select(StudentGuardian).where(
            StudentGuardian.tenant_id == auth.tenant_id,
            StudentGuardian.student_id == student_id,
            StudentGuardian.guardian_id == guardian_id,
        )
    )
    if link is None:
        raise HTTPException(404, "Guardian link not found")
    await db.delete(link)
    await _audit(db, auth, student, "guardian_unlinked", {"guardian_id": str(guardian_id)})
    await db.commit()
