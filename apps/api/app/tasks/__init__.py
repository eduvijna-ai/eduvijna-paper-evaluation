"""Celery task package."""

from app.tasks.celery_app import (
    celery_app,
    enqueue_analytics,
    enqueue_evaluation,
    enqueue_identity_extraction,
    enqueue_mapping_preparation,
    enqueue_page_normalization,
    enqueue_publication,
    enqueue_transcription,
    analytics_task,
    evaluation_task,
    identity_extraction_task,
    normalize_pages_task,
    prepare_mapping_task,
    publication_task,
    transcription_task,
)

__all__ = [
    "analytics_task",
    "celery_app",
    "enqueue_analytics",
    "enqueue_evaluation",
    "enqueue_identity_extraction",
    "enqueue_mapping_preparation",
    "enqueue_page_normalization",
    "enqueue_publication",
    "enqueue_transcription",
    "evaluation_task",
    "identity_extraction_task",
    "normalize_pages_task",
    "prepare_mapping_task",
    "publication_task",
    "transcription_task",
]
