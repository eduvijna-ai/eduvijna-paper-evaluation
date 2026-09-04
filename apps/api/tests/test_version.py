from fastapi.testclient import TestClient


def test_version(client: TestClient) -> None:
    response = client.get("/api/v1/system/version")
    assert response.status_code == 200
    assert response.json() == {
        "application": "eduvijna-paper-evaluation",
        "environment": "local",
        "git_sha": "unknown",
        "api_version": "0.1.0",
    }
