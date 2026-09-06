"""Celery task package."""

from app.tasks.celery_app import celery_app, enqueue_page_normalization, normalize_pages_task

__all__ = ["celery_app", "enqueue_page_normalization", "normalize_pages_task"]
