import pytest
from fastapi.testclient import TestClient
from app.mvp import create_app


@pytest.mark.parametrize("name,status,code", [
    ("unavailable", 503, "RHINO_UNAVAILABLE"),
    ("request", 502, "RHINO_REQUEST_FAILED"),
    ("capability", 501, "RHINO_CAPABILITY_UNAVAILABLE"),
])
def test_typed_rhino_errors_map_to_safe_responses(name, status, code):
    from app.services.rhino import errors
    app = create_app()

    @app.get("/boom")
    def boom():
        if name == "unavailable":
            raise errors.RhinoUnavailableError("SECRET_SENTINEL")
        if name == "request":
            raise errors.RhinoRequestError(500)
        raise errors.RhinoCapabilityUnavailableError("SECRET_SENTINEL")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom?token=SECRET_SENTINEL")
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert "SECRET_SENTINEL" not in response.text
