# ruff: noqa: B008
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash

from app.core.authorization import AuthContext
from app.core.config import Settings, get_settings

password_hasher = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)


class AuthProvider(Protocol):
    def issue_access_token(self, context: AuthContext) -> tuple[str, int]: ...

    def verify_access_token(self, token: str) -> AuthContext: ...


class JwtAuthProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if settings.auth_token_secret is None:
            raise ValueError("AUTH_TOKEN_SECRET is required")
        self.secret = settings.auth_token_secret

    def issue_access_token(self, context: AuthContext) -> tuple[str, int]:
        ttl = self.settings.auth_token_ttl_minutes * 60
        now = datetime.now(UTC)
        token = jwt.encode(
            {
                "sub": str(context.user_id),
                "tenant_id": str(context.tenant_id),
                "roles": sorted(context.roles),
                "permissions": sorted(context.permissions),
                "iat": now,
                "exp": now + timedelta(seconds=ttl),
                "typ": "access",
            },
            self.secret,
            algorithm=self.settings.auth_algorithm,
        )
        return token, ttl

    def verify_access_token(self, token: str) -> AuthContext:
        try:
            claims = jwt.decode(
                token,
                self.secret,
                algorithms=[self.settings.auth_algorithm],
                options={"require": ["sub", "tenant_id", "exp", "iat", "typ"]},
            )
            if claims["typ"] != "access":
                raise jwt.InvalidTokenError
            return AuthContext(
                user_id=UUID(claims["sub"]),
                tenant_id=UUID(claims["tenant_id"]),
                roles=frozenset(claims.get("roles", [])),
                permissions=frozenset(claims.get("permissions", [])),
            )
        except (jwt.InvalidTokenError, ValueError, KeyError) as exc:
            raise HTTPException(status_code=401, detail="Invalid authentication token") from exc


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    return password_hasher.verify(password, encoded)


def get_auth_provider(settings: Settings = Depends(get_settings)) -> AuthProvider:
    return JwtAuthProvider(settings)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    provider: AuthProvider = Depends(get_auth_provider),
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required")
    return provider.verify_access_token(credentials.credentials)
