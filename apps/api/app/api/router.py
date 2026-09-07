from fastapi import APIRouter

from app.api.v1 import (
    analytics,
    authoring,
    authoring_ai,
    authoring_read,
    curriculum_assessment,
    evaluation,
    health,
    learning,
    mapping,
    platform,
    publication,
    submissions,
    system,
    transcription,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(system.router, prefix="/api/v1")
api_router.include_router(platform.router, prefix="/api/v1")
api_router.include_router(curriculum_assessment.router, prefix="/api/v1")
api_router.include_router(authoring.router, prefix="/api/v1")
api_router.include_router(authoring_ai.router, prefix="/api/v1")
api_router.include_router(authoring_read.router, prefix="/api/v1")
api_router.include_router(submissions.router, prefix="/api/v1")
api_router.include_router(mapping.router, prefix="/api/v1")
api_router.include_router(transcription.router, prefix="/api/v1")
api_router.include_router(evaluation.router, prefix="/api/v1")
api_router.include_router(publication.router, prefix="/api/v1")
api_router.include_router(analytics.router, prefix="/api/v1")
api_router.include_router(learning.router, prefix="/api/v1")
