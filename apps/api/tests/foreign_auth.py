"""Real foreign-tenant users for isolation tests after B19 JWT existence checks."""

from __future__ import annotations

import uuid

from app.core.security import hash_password
from app.db.models import Tenant, User
from app.db.session import async_session_factory


async def create_foreign_user() -> tuple[uuid.UUID, uuid.UUID]:
    suffix = uuid.uuid4().hex[:12]
    async with async_session_factory() as db:
        tenant = Tenant(slug=f"iso-{suffix}", name="Isolation Tenant")
        db.add(tenant)
        await db.flush()
        user = User(
            tenant_id=tenant.id,
            email=f"admin@{suffix}.eduvijna.local",
            display_name="Isolation Admin",
            password_hash=hash_password("IsoAdmin!2026"),
            status="active",
            auth_version=1,
        )
        db.add(user)
        await db.commit()
        return user.id, tenant.id
