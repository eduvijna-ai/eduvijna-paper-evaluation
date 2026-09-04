import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://eduvijna:eduvijna_local_dev_only@localhost:15432/eduvijna",
)
os.environ.setdefault("AUTH_TOKEN_SECRET", "test-only-secret-not-for-production")

from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def client() -> Iterator[TestClient]:
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
