from fastapi import Depends
from fastapi.testclient import TestClient
from tests.stubs.rhino_stub import rhino_stub


def _app_with_health_route():
    from app.mvp import create_app
    from app.services.rhino.contract import RhinoService
    from app.services.rhino.dependencies import get_rhino_service
    app = create_app()

    @app.get("/test-only/rhino-health")
    async def rhino_health(service: RhinoService = Depends(get_rhino_service)):
        return await service.health_check()

    return app


def test_no_url_selects_unconfigured_adapter():
    from app.services.rhino.unconfigured import UnconfiguredRhinoAdapter
    app = _app_with_health_route()
    assert isinstance(app.state.rhino_service, UnconfiguredRhinoAdapter)
    with TestClient(app) as client:
        response = client.get("/test-only/rhino-health")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "RHINO_NOT_CONFIGURED"


def test_url_selects_configured_adapter(monkeypatch):
    from app.services.rhino.configured import ConfiguredRhinoAdapter
    with rhino_stub() as (server, base):
        monkeypatch.setenv("RHINO_COMPUTE_URL", base)
        app = _app_with_health_route()
        assert isinstance(app.state.rhino_service, ConfiguredRhinoAdapter)
        with TestClient(app) as client:
            # constructing the app must NOT have probed the node
            assert server.records == []
            response = client.get("/test-only/rhino-health")
        assert response.status_code == 200
        assert response.json() == {"configured": True, "reachable": True, "status": "ok"}
        assert len(server.records) == 1


def test_url_but_unreachable_is_reported_not_crashed(monkeypatch):
    monkeypatch.setenv("RHINO_COMPUTE_URL", "http://127.0.0.1:1")
    app = _app_with_health_route()
    with TestClient(app) as client:
        response = client.get("/test-only/rhino-health")
    assert response.status_code == 200
    assert response.json() == {"configured": True, "reachable": False, "status": "unreachable"}


def test_api_key_flows_from_settings_to_client(monkeypatch):
    with rhino_stub() as (server, base):
        monkeypatch.setenv("RHINO_COMPUTE_URL", base)
        monkeypatch.setenv("RHINO_COMPUTE_API_KEY", "SECRET_SENTINEL")
        app = _app_with_health_route()
        with TestClient(app) as client:
            client.get("/test-only/rhino-health")
        assert server.records[0]["headers"]["rhinocomputekey"] == "SECRET_SENTINEL"
