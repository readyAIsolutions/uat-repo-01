import pytest
from fastapi.testclient import TestClient
from tests.stubs.rhino_stub import rhino_stub


def _client(monkeypatch, base=None, key=None):
    from app.mvp import create_app
    if base is not None:
        monkeypatch.setenv("RHINO_COMPUTE_URL", base)
    if key is not None:
        monkeypatch.setenv("RHINO_COMPUTE_API_KEY", key)
    return TestClient(create_app())


def test_status_unconfigured_reports_honestly():
    with _client(None) as client:
        response = client.get("/api/rhino/status")
    assert response.status_code == 200
    assert response.json() == {"configured": False, "reachable": False, "status": "unconfigured"}


def test_status_configured_reachable(monkeypatch):
    with rhino_stub() as (server, base):
        with _client(monkeypatch, base=base) as client:
            response = client.get("/api/rhino/status")
    assert response.status_code == 200
    assert response.json() == {"configured": True, "reachable": True, "status": "ok"}


def test_status_configured_unreachable(monkeypatch):
    with _client(monkeypatch, base="http://127.0.0.1:1") as client:
        response = client.get("/api/rhino/status")
    assert response.status_code == 200
    assert response.json() == {"configured": True, "reachable": False, "status": "unreachable"}


def test_box_success_is_transport_round_trip(monkeypatch):
    import json

    def responder(record):
        body = json.loads(record["body"])
        assert body["pointer"] == "marlin_box"
        names = {v["ParamName"] for v in body["values"]}
        assert names == {"width", "length", "height"}
        return 200, {"values": [{"ParamName": "box", "InnerTree": {"{0}": [
            {"type": "System.String", "data": "node-output"}]}}], "warnings": [], "errors": []}, 0

    with rhino_stub(responder) as (server, base):
        with _client(monkeypatch, base=base) as client:
            response = client.post("/api/rhino/box",
                                   json={"width": 1.0, "length": 2.0, "height": 3.0})
    assert response.status_code == 200
    assert response.json()["source"] == "rhino-compute"
    assert response.json()["result"] == {"box": ["node-output"]}


def test_box_unconfigured_returns_503():
    with _client(None) as client:
        response = client.post("/api/rhino/box", json={"width": 1, "length": 2, "height": 3})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "RHINO_NOT_CONFIGURED"


def test_box_unreachable_returns_503(monkeypatch):
    with _client(monkeypatch, base="http://127.0.0.1:1") as client:
        response = client.post("/api/rhino/box", json={"width": 1, "length": 2, "height": 3})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "RHINO_UNAVAILABLE"


def test_box_node_error_returns_502(monkeypatch):
    with rhino_stub(lambda r: (500, {"error": "boom"}, 0)) as (server, base):
        with _client(monkeypatch, base=base) as client:
            response = client.post("/api/rhino/box", json={"width": 1, "length": 2, "height": 3})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "RHINO_REQUEST_FAILED"


@pytest.mark.parametrize("body", [
    {"width": 0, "length": 2, "height": 3},
    {"width": -1, "length": 2, "height": 3},
    {"width": 1, "length": 2},
    {"width": 1, "length": 2, "height": 99999},
    {"width": "SECRET_SENTINEL", "length": 2, "height": 3},
])
def test_box_validation_is_safe(body):
    with _client(None) as client:
        response = client.post("/api/rhino/box", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert "SECRET_SENTINEL" not in response.text


def test_capabilities_is_honest():
    with _client(None) as client:
        response = client.get("/api/rhino/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["real_rhino_tested"] is False
    assert payload["operations"]["create_geometry"] == "reserved"
    assert payload["operations"]["health_check"] == "available"


def test_box_uses_di_override(monkeypatch):
    from app.mvp import create_app
    from app.services.rhino.dependencies import get_rhino_service
    from tests.fakes.rhino import MockRhinoAdapter
    app = create_app()
    app.dependency_overrides[get_rhino_service] = lambda: MockRhinoAdapter()
    with TestClient(app) as client:
        response = client.post("/api/rhino/box", json={"width": 1, "length": 2, "height": 3})
    assert response.status_code == 200
    assert response.json() == {"mock": True, "geometry": None, "cad_files": []}
