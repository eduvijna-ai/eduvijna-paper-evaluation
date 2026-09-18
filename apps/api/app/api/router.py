from fastapi import APIRouter

from app.api.integration_v1 import router as integration_v1_router
from app.api.v1 import (
    analytics,
    authoring,
    authoring_ai,
    authoring_read,
    b19_test,
    benchmark,
    curriculum_assessment,
    enterprise_ops,
    evaluation,
    health,
    integrations,
    learning,
    lti_api,
    mapping,
    outcome_intelligence,
    platform,
    publication,
    quality,
    reassessment,
    resources,
    scim_api,
    sso,
    submissions,
    system,
    transcription,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(system.router, prefix="/api/v1")
api_router.include_router(platform.router, prefix="/api/v1")
api_router.include_router(integrations.router, prefix="/api/v1")
api_router.include_router(sso.router, prefix="/api/v1")
api_router.include_router(b19_test.router, prefix="/api/v1")
api_router.include_router(scim_api.router)
api_router.include_router(lti_api.router)
api_router.include_router(integration_v1_router)
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
api_router.include_router(resources.router, prefix="/api/v1")
api_router.include_router(reassessment.router, prefix="/api/v1")
api_router.include_router(benchmark.router, prefix="/api/v1")
api_router.include_router(quality.router, prefix="/api/v1")
api_router.include_router(outcome_intelligence.router, prefix="/api/v1")
api_router.include_router(enterprise_ops.router, prefix="/api/v1")
