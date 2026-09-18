# ruff: noqa: B008
"""Machine / SCIM credential FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.integration_credentials import authenticate_integration_credential
from app.services.integration_rate_limit import check_integration_rate_limit

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class IntegrationAuthContext:
    credential_id: UUID
    tenant_id: UUID
    scopes: frozenset[str]


def require_integration_scopes(
    *required: str,
) -> Callable[..., Awaitable[IntegrationAuthContext]]:
    async def dependency(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
        db: AsyncSession = Depends(get_db_session),
        settings: Settings = Depends(get_settings),
    ) -> IntegrationAuthContext:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(
                status_code=401,
                detail={"code": "invalid_credentials", "message": "Invalid integration credential"},
            )
        cred = await authenticate_integration_credential(
            db,
            raw_secret=credentials.credentials,
            required_scopes=set(required) if required else None,
        )
        check_integration_rate_limit(
            tenant_id=cred.tenant_id, credential_id=cred.id, settings=settings
        )
        return IntegrationAuthContext(
            credential_id=cred.id,
            tenant_id=cred.tenant_id,
            scopes=frozenset(str(s) for s in (cred.scopes_json or [])),
        )

    return dependency
