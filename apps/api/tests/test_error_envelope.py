from fastapi.testclient import TestClient


def test_not_found_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/does-not-exist", headers={"X-Correlation-ID": "error-test"})
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "http_404",
            "message": "Not Found",
            "correlation_id": "error-test",
            "details": None,
        }
    }
