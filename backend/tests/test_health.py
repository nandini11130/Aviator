from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoints_return_ok():
    with TestClient(app) as client:
        for path in ("/health", "/healthz"):
            response = client.get(path)

            assert response.status_code == 200
            assert response.json()["status"] == "ok"
