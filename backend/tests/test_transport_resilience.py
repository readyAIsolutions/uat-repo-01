import pytest
from tests.stubs.rhino_stub import rhino_stub

OK = {"reachable": True, "status_code": 200, "healthy": True}


def _client(base, **kw):
    from app.services.rhino.client import RhinoComputeClient
    return RhinoComputeClient(base, **kw)


async def test_retries_timeout_then_succeeds():
    state = {"n": 0}

    def responder(record):
        state["n"] += 1
        return (200, b"Healthy", 0.5) if state["n"] == 1 else (200, b"Healthy", 0)

    with rhino_stub(responder) as (server, base):
        result = await _client(base, timeout=0.2, max_attempts=3).health()
    assert result == OK
    assert len(server.records) == 2


async def test_retries_5xx_then_succeeds():
    state = {"n": 0}

    def responder(record):
        state["n"] += 1
        return (503, {"e": 1}, 0) if state["n"] == 1 else (200, b"Healthy", 0)

    with rhino_stub(responder) as (server, base):
        result = await _client(base, max_attempts=3).health()
    assert result == OK
    assert len(server.records) == 2


async def test_does_not_retry_4xx():
    from app.services.rhino.errors import RhinoRequestError
    with rhino_stub(lambda r: (400, {"e": 1}, 0)) as (server, base):
        with pytest.raises(RhinoRequestError) as caught:
            await _client(base, max_attempts=5).health()
    assert caught.value.status_code == 400
    assert len(server.records) == 1


async def test_max_attempts_respected_on_persistent_failure():
    from app.services.rhino.errors import RhinoRequestError
    with rhino_stub(lambda r: (500, {"e": 1}, 0)) as (server, base):
        with pytest.raises(RhinoRequestError):
            await _client(base, max_attempts=2).health()
    assert len(server.records) == 2


async def test_persistent_timeout_raises_unavailable_after_attempts():
    from app.services.rhino.errors import RhinoUnavailableError
    with rhino_stub(lambda r: (200, b"Healthy", 0.5)) as (server, base):
        with pytest.raises(RhinoUnavailableError):
            await _client(base, timeout=0.15, max_attempts=2).health()
    assert len(server.records) == 2


async def test_default_is_single_attempt():
    from app.services.rhino.errors import RhinoRequestError
    with rhino_stub(lambda r: (500, {"e": 1}, 0)) as (server, base):
        with pytest.raises(RhinoRequestError):
            await _client(base).health()
    assert len(server.records) == 1


def test_factory_wires_max_attempts_from_settings(monkeypatch):
    from fastapi.testclient import TestClient
    from app.mvp import create_app
    with rhino_stub(lambda r: (503, {"e": 1}, 0)) as (server, base):
        monkeypatch.setenv("RHINO_COMPUTE_URL", base)
        monkeypatch.setenv("RHINO_COMPUTE_MAX_ATTEMPTS", "2")
        with TestClient(create_app()) as client:
            response = client.get("/api/rhino/status")
    assert response.json()["status"] == "error"
    assert response.json()["status_code"] == 503
    assert len(server.records) == 2


def test_factory_wires_timeout_from_settings(monkeypatch):
    from fastapi.testclient import TestClient
    from app.mvp import create_app
    with rhino_stub(lambda r: (200, b"Healthy", 0.4)) as (server, base):
        monkeypatch.setenv("RHINO_COMPUTE_URL", base)
        monkeypatch.setenv("RHINO_COMPUTE_TIMEOUT", "0.1")
        monkeypatch.setenv("RHINO_COMPUTE_MAX_ATTEMPTS", "1")
        with TestClient(create_app()) as client:
            response = client.get("/api/rhino/status")
    assert response.json() == {"configured": True, "reachable": False, "status": "unreachable"}
