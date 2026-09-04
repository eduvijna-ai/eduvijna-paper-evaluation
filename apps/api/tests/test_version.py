from fastapi.testclient import TestClient

from app.core.config import get_settings


def test_version(client: TestClient) -> None:
    settings = get_settings()
    response = client.get("/api/v1/system/version")
    assert response.status_code == 200
    assert response.json() == {
        "application": settings.application,
        "environment": settings.environment,
        "git_sha": settings.git_sha,
        "api_version": settings.api_version,
    }
