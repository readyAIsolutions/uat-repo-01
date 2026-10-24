import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel


@pytest.mark.parametrize("kind,status,code", [("http", 403, "HTTP_ERROR"),
    ("validation", 422, "VALIDATION_ERROR"), ("missing", 404, "HTTP_ERROR")])
def test_safe_http_errors(kind, status, code):
    from app.mvp import create_app
    app = create_app()

    class Body(BaseModel):
        count: int

    @app.post("/validation")
    def validation(body: Body):
        return body

    @app.get("/http")
    def fail():
        raise HTTPException(403, "SECRET_SENTINEL", headers={"x-secret": "SECRET_SENTINEL"})

    with TestClient(app) as client:
        response = (client.post("/validation", json={"count": "SECRET_SENTINEL"})
                    if kind == "validation" else client.get("/" + kind))
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert "SECRET_SENTINEL" not in response.text + str(response.headers)
