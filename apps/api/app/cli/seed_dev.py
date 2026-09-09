import asyncio
from datetime import date

from sqlalchemy import select

from app.core.authorization import PERMISSION_CODES, ROLE_CODES, ROLE_PERMISSION_MAP
from app.core.security import hash_password
from app.db.models import (
    AcademicYear,
    ClassSection,
    Institution,
    Permission,
    Role,
    RolePermission,
    Tenant,
    User,
    UserRole,
)
from app.db.session import async_session_factory

ADMIN_EMAIL = "admin@demo.eduvijna.local"
ADMIN_PASSWORD = "DemoAdmin!2026"
DEMO_USER_PASSWORD = "DemoUser!2026"

# B16.1 enterprise ops demo users (idempotent; demo seed CLI only).
ENTERPRISE_DEMO_USERS: tuple[tuple[str, str, str], ...] = (
    ("evaluator-a@demo.eduvijna.local", "Demo Evaluator A", "EVALUATOR"),
    ("evaluator-b@demo.eduvijna.local", "Demo Evaluator B", "EVALUATOR"),
    ("moderator@demo.eduvijna.local", "Demo Moderator", "MODERATOR"),
    ("hod@demo.eduvijna.local", "Demo HOD", "HOD"),
)


async def seed() -> None:
    async with async_session_factory() as db:
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == "demo"))
        if tenant is None:
            tenant = Tenant(slug="demo", name="EduVijna Demo")
            db.add(tenant)
            await db.flush()
        institution = await db.scalar(
            select(Institution).where(
                Institution.tenant_id == tenant.id, Institution.code == "DEMO"
            )
        )
        if institution is None:
            institution = Institution(tenant_id=tenant.id, code="DEMO", name="Demo Institution")
            db.add(institution)
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
            role = await db.scalar(
                select(Role).where(Role.tenant_id == tenant.id, Role.code == code)
            )
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
            select(User).where(User.tenant_id == tenant.id, User.email == ADMIN_EMAIL)
        )
        if user is None:
            user = User(
                tenant_id=tenant.id,
                email=ADMIN_EMAIL,
                display_name="Demo Administrator",
                password_hash=hash_password(ADMIN_PASSWORD),
            )
            db.add(user)
            await db.flush()
        elif not user.password_hash:
            user.password_hash = hash_password(ADMIN_PASSWORD)
        assignment = await db.scalar(
            select(UserRole).where(
                UserRole.user_id == user.id,
                UserRole.role_id == roles["INSTITUTION_ADMIN"].id,
            )
        )
        if assignment is None:
            db.add(
                UserRole(
                    tenant_id=tenant.id,
                    user_id=user.id,
                    role_id=roles["INSTITUTION_ADMIN"].id,
                )
            )

        for email, display_name, role_code in ENTERPRISE_DEMO_USERS:
            enterprise_user = await db.scalar(
                select(User).where(User.tenant_id == tenant.id, User.email == email)
            )
            if enterprise_user is None:
                enterprise_user = User(
                    tenant_id=tenant.id,
                    email=email,
                    display_name=display_name,
                    password_hash=hash_password(DEMO_USER_PASSWORD),
                )
                db.add(enterprise_user)
                await db.flush()
                db.add(
                    UserRole(
                        tenant_id=tenant.id,
                        user_id=enterprise_user.id,
                        role_id=roles[role_code].id,
                    )
                )
                print(f"Seeded enterprise user {email} ({role_code})")

        year = await db.scalar(
            select(AcademicYear).where(
                AcademicYear.tenant_id == tenant.id, AcademicYear.name == "2026-27"
            )
        )
        if year is None:
            year = AcademicYear(
                tenant_id=tenant.id,
                institution_id=institution.id,
                name="2026-27",
                starts_on=date(2026, 6, 1),
                ends_on=date(2027, 5, 31),
                is_current=True,
            )
            db.add(year)
            await db.flush()
        section = await db.scalar(
            select(ClassSection).where(
                ClassSection.tenant_id == tenant.id,
                ClassSection.academic_year_id == year.id,
                ClassSection.name == "A",
            )
        )
        if section is None:
            db.add(
                ClassSection(
                    tenant_id=tenant.id,
                    institution_id=institution.id,
                    academic_year_id=year.id,
                    name="A",
                    grade_label="Grade 10",
                )
            )
        await db.commit()
        print(f"Seeded tenant demo; login {ADMIN_EMAIL} / {ADMIN_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed())
