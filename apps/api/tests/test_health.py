from collections.abc import AsyncIterator
from typing import Any

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


def test_ready_with_available_database() -> None:
    application: FastAPI = create_app()

    async def override_session() -> AsyncIterator[ReadySession]:
        yield ReadySession()

    application.dependency_overrides[get_db_session] = override_session
    with TestClient(application) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
