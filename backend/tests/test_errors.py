from fastapi.testclient import TestClient


def test_unexpected_error_is_safe_and_correlated(caplog):
    from app.mvp import create_app
    app = create_app()

    @app.get("/explode")
    def explode():
        raise RuntimeError("SECRET_SENTINEL")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/explode?token=SECRET_SENTINEL",
                              headers={"X-Request-ID": "SECRET_SENTINEL"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    cid = response.headers["X-Request-ID"]
    assert response.json()["request_id"] == cid
    assert cid != "SECRET_SENTINEL"
    assert "SECRET_SENTINEL" not in response.text
