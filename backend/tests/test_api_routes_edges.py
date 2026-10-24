import pytest
from fastapi.testclient import TestClient
from tests.stubs.rhino_stub import rhino_stub


def _app(monkeypatch, base=None):
    from app.mvp import create_app
    if base is not None:
        monkeypatch.setenv("RHINO_COMPUTE_URL", base)
    return create_app()


def test_status_has_correlation_id():
    with TestClient(_app(None)) as client:
        response = client.get("/api/rhino/status")
    assert response.headers["x-request-id"] == response.json().get("request_id", response.headers["x-request-id"])
    assert len(response.headers["x-request-id"]) == 32


def test_box_non_json_body_is_safe():
    with TestClient(_app(None)) as client:
        response = client.post("/api/rhino/box", content="SECRET_SENTINEL",
                               headers={"Content-Type": "text/plain"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "SECRET_SENTINEL" not in response.text


def test_box_boundary_values(monkeypatch):
    with rhino_stub() as (server, base):
        with TestClient(_app(monkeypatch, base=base)) as client:
            ok = client.post("/api/rhino/box", json={"width": 10000, "length": 1, "height": 1})
            too_big = client.post("/api/rhino/box", json={"width": 10000.1, "length": 1, "height": 1})
    assert ok.status_code == 200
    assert too_big.status_code == 422


def test_box_node_invalid_json_is_502(monkeypatch):
    with rhino_stub(lambda r: (200, b"not json", 0)) as (server, base):
        with TestClient(_app(monkeypatch, base=base)) as client:
            response = client.post("/api/rhino/box", json={"width": 1, "length": 2, "height": 3})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "RHINO_REQUEST_FAILED"


def test_capabilities_has_correlation_and_no_secrets():
    with TestClient(_app(None)) as client:
        response = client.get("/api/rhino/capabilities?key=SECRET_SENTINEL",
                              headers={"Authorization": "SECRET_SENTINEL"})
    assert response.status_code == 200
    assert "SECRET_SENTINEL" not in response.text
    assert len(response.headers["x-request-id"]) == 32


def test_extra_fields_are_ignored_not_echoed(monkeypatch):
    with rhino_stub() as (server, base):
        with TestClient(_app(monkeypatch, base=base)) as client:
            response = client.post("/api/rhino/box",
                                   json={"width": 1, "length": 2, "height": 3,
                                         "note": "SECRET_SENTINEL"})
    assert response.status_code == 200
    assert "SECRET_SENTINEL" not in response.text
