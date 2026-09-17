# ruff: noqa: B008
"""SCIM 2.0 Users surface authenticated by integration credentials."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.services.integration_auth import IntegrationAuthContext, require_integration_scopes
from app.services.scim import (
    resource_types,
    scim_create_user,
    scim_get_user,
    scim_list_users,
    scim_patch_user,
    scim_replace_user,
    service_provider_config,
)
from app.services.webhooks import deliver_due_webhooks

router = APIRouter(tags=["enterprise-identity"])
Db = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/scim/v2/ServiceProviderConfig")
async def scim_spc() -> dict[str, Any]:
    return service_provider_config()


@router.get("/scim/v2/ResourceTypes")
async def scim_resource_types() -> dict[str, Any]:
    return resource_types()


@router.get("/scim/v2/Schemas")
async def scim_schemas() -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": 1,
        "Resources": [{"id": "urn:ietf:params:scim:schemas:core:2.0:User", "name": "User"}],
    }


@router.get("/scim/v2/Users")
async def list_users(
    db: Db,
    filter: str | None = Query(default=None),
    startIndex: int = 1,
    count: int = 100,
    auth: IntegrationAuthContext = Depends(require_integration_scopes("scim")),
) -> dict[str, Any]:
    return await scim_list_users(
        db, tenant_id=auth.tenant_id, filter_expr=filter, start_index=startIndex, count=count
    )


@router.post("/scim/v2/Users", status_code=201)
async def create_user(
    payload: dict[str, Any],
    db: Db,
    auth: IntegrationAuthContext = Depends(require_integration_scopes("scim")),
) -> dict[str, Any]:
    result = await scim_create_user(db, tenant_id=auth.tenant_id, payload=payload)
    await db.commit()
    await deliver_due_webhooks(db)
    await db.commit()
    return result


@router.get("/scim/v2/Users/{user_id}")
async def get_user(
    user_id: uuid.UUID,
    db: Db,
    auth: IntegrationAuthContext = Depends(require_integration_scopes("scim")),
) -> dict[str, Any]:
    return await scim_get_user(db, tenant_id=auth.tenant_id, user_id=user_id)


@router.put("/scim/v2/Users/{user_id}")
async def replace_user(
    user_id: uuid.UUID,
    payload: dict[str, Any],
    db: Db,
    auth: IntegrationAuthContext = Depends(require_integration_scopes("scim")),
) -> dict[str, Any]:
    result = await scim_replace_user(db, tenant_id=auth.tenant_id, user_id=user_id, payload=payload)
    await db.commit()
    await deliver_due_webhooks(db)
    await db.commit()
    return result


@router.patch("/scim/v2/Users/{user_id}")
async def patch_user(
    user_id: uuid.UUID,
    payload: dict[str, Any],
    db: Db,
    auth: IntegrationAuthContext = Depends(require_integration_scopes("scim")),
) -> dict[str, Any]:
    result = await scim_patch_user(db, tenant_id=auth.tenant_id, user_id=user_id, payload=payload)
    await db.commit()
    await deliver_due_webhooks(db)
    await db.commit()
    return result
