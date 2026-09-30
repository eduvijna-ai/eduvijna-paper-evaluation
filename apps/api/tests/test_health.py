from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.session import get_db_session
from app.main import create_app


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Correlation-ID"]


def test_correlation_id_is_propagated(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Correlation-ID": "test-correlation"})
    assert response.headers["X-Correlation-ID"] == "test-correlation"


class ReadySession:
    async def execute(self, _statement: Any) -> None:
        return None


class FailingReadySession:
    async def execute(self, _statement: Any) -> None:
        raise RuntimeError("db down")


def test_ready_with_available_dependencies() -> None:
    application: FastAPI = create_app()

    async def override_session() -> AsyncIterator[ReadySession]:
        yield ReadySession()

    application.dependency_overrides[get_db_session] = override_session
    with (
        patch("app.api.v1.health._ping_redis"),
        patch("app.api.v1.health._head_object_bucket"),
        TestClient(application) as client,
    ):
        response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["postgres"]["status"] == "ok"
    assert body["checks"]["redis"]["status"] == "ok"
    assert body["checks"]["object_storage"]["status"] == "ok"


def test_ready_returns_503_when_postgres_fails() -> None:
    application: FastAPI = create_app()

    async def override_session() -> AsyncIterator[FailingReadySession]:
        yield FailingReadySession()

    application.dependency_overrides[get_db_session] = override_session
    with (
        patch("app.api.v1.health._ping_redis"),
        patch("app.api.v1.health._head_object_bucket"),
        TestClient(application) as client,
    ):
        response = client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["postgres"]["status"] == "fail"


def test_ready_returns_503_when_redis_fails() -> None:
    application: FastAPI = create_app()

    async def override_session() -> AsyncIterator[ReadySession]:
        yield ReadySession()

    application.dependency_overrides[get_db_session] = override_session
    with (
        patch(
            "app.api.v1.health._ping_redis",
            side_effect=ConnectionError("redis down"),
        ),
        patch("app.api.v1.health._head_object_bucket"),
        TestClient(application) as client,
    ):
        response = client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["redis"]["status"] == "fail"
    assert body["checks"]["postgres"]["status"] == "ok"


def test_ready_returns_503_when_object_storage_fails() -> None:
    application: FastAPI = create_app()

    async def override_session() -> AsyncIterator[ReadySession]:
        yield ReadySession()

    application.dependency_overrides[get_db_session] = override_session
    with (
        patch("app.api.v1.health._ping_redis"),
        patch(
            "app.api.v1.health._head_object_bucket",
            side_effect=RuntimeError("bucket missing"),
        ),
        TestClient(application) as client,
    ):
        response = client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["object_storage"]["status"] == "fail"
