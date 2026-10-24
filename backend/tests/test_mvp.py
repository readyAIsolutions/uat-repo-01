from fastapi.testclient import TestClient


def test_health():
    from app.mvp import create_app
    with TestClient(create_app()) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "marlin-rhino-mvp"}
