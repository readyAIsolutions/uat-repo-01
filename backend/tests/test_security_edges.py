import json
import logging
import re
import pytest
from fastapi.testclient import TestClient
from app.mvp import create_app


@pytest.mark.parametrize("inbound", ["", "SECRET_SENTINEL", "x" * 4000, "a" * 32])
def test_server_owned_unique_ids(inbound):
    with TestClient(create_app()) as client:
        one = client.get("/health", headers={"X-Request-ID": inbound})
        two = client.get("/health", headers={"X-Request-ID": inbound})
    assert re.fullmatch(r"[0-9a-f]{32}", one.headers["x-request-id"])
    assert one.headers["x-request-id"] not in (inbound, two.headers["x-request-id"])


def test_unusual_method_and_error_logs_never_echo_input(caplog):
    with caplog.at_level(logging.DEBUG, logger="marlin.mvp"):
        with TestClient(create_app()) as client:
            response = client.request("SECRET_SENTINEL", "/SECRET_SENTINEL?key=SECRET_SENTINEL",
                                      content="SECRET_SENTINEL")
    records = [r for r in caplog.records if r.name == "marlin.mvp"]
    assert len(records) == 1
    assert json.loads(records[0].getMessage())["method"] == "OTHER"
    assert "SECRET_SENTINEL" not in records[0].getMessage() + response.text


def test_log_threshold_is_per_app(monkeypatch, caplog):
    monkeypatch.setenv("MARLIN_LOG_LEVEL", "ERROR")
    app = create_app()

    @app.get("/fail")
    def fail():
        raise RuntimeError("SECRET_SENTINEL")

    with caplog.at_level(logging.DEBUG, logger="marlin.mvp"):
        with TestClient(app) as client:
            client.get("/health")
            client.get("/fail")
    records = [r for r in caplog.records if r.name == "marlin.mvp"]
    assert len(records) == 1
    assert json.loads(records[0].getMessage())["status"] == 500
    assert records[0].exc_info is None


async def test_all_mock_outputs_are_explicit():
    from tests.fakes.rhino import MockRhinoAdapter
    from app.services.rhino.contract import RhinoService
    mock = MockRhinoAdapter()
    assert isinstance(mock, RhinoService)
    assert await mock.health_check() == {"mock": True, "connected": False}
    for result in [await mock.create_box(1, 2, 3), await mock.create_geometry({}),
                   await mock.execute_grasshopper("unused", {})]:
        assert result == {"mock": True, "geometry": None, "cad_files": []}
