"""Minimal Celery application factory.

Celery is deliberately not an API dependency yet. Install it with the worker
package when task implementations are introduced.
"""

import os
from typing import Any


def create_celery_app() -> Any:
    """Create the worker application using Redis-backed environment settings."""
    try:
        from celery import Celery
    except ImportError as exc:
        raise RuntimeError("Install Celery before starting EduVijna workers") from exc

    app = Celery("eduvijna")
    app.config_from_object(
        {
            "broker_url": os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
            "result_backend": os.getenv(
                "CELERY_RESULT_BACKEND", "redis://redis:6379/1"
            ),
            "task_serializer": "json",
            "result_serializer": "json",
            "accept_content": ["json"],
        }
    )
    return app
