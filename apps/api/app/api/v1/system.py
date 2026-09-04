from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(prefix="/system", tags=["system"])


class VersionResponse(BaseModel):
    application: str
    environment: str
    git_sha: str
    api_version: str


@router.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    settings = get_settings()
    return VersionResponse(
        application=settings.application,
        environment=settings.environment,
        git_sha=settings.git_sha,
        api_version=settings.api_version,
    )
