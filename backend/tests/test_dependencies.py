from fastapi import Depends
from fastapi.testclient import TestClient
from tests.fakes.rhino import MockRhinoAdapter


def test_two_adapters_without_changing_routes(monkeypatch):
    from app.mvp import create_app
    from app.services.rhino.dependencies import get_rhino_service
    from app.services.rhino.contract import RhinoService
    # Section 2 supersedes the Section 1 rule: a configured URL now selects the
    # real (transport) adapter, so an unreachable node yields RHINO_UNAVAILABLE
    # rather than RHINO_NOT_CONFIGURED. Loopback port 1 is refused instantly.
    monkeypatch.setenv("RHINO_COMPUTE_URL", "http://127.0.0.1:1")
    app = create_app()

    @app.get("/test-only/box")
    async def box(service: RhinoService = Depends(get_rhino_service)):
        return await service.create_box(1, 2, 3)

    with TestClient(app) as client:
        response = client.get("/test-only/box")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "RHINO_UNAVAILABLE"
        assert response.json()["request_id"] == response.headers["x-request-id"]
        app.dependency_overrides[get_rhino_service] = lambda: MockRhinoAdapter()
        assert client.get("/test-only/box").json() == {"mock": True, "geometry": None, "cad_files": []}
        app.dependency_overrides.clear()
        assert client.get("/test-only/box").status_code == 503
        app.state.rhino_service = MockRhinoAdapter()
        assert client.get("/test-only/box").json()["mock"] is True
