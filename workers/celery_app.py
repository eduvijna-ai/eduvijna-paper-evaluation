"""Minimal Celery application factory.

Prefer importing `app.tasks.celery_app` from the API package. This module remains
as a compatibility shim for older worker docs.
"""

from typing import Any


def create_celery_app() -> Any:
    from app.tasks.celery_app import create_celery_app as _create

    return _create()
