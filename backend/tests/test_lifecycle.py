from fastapi.testclient import TestClient


def test_factory_validates_and_lifespan_tracks_readiness(monkeypatch):
    from app.mvp import create_app
    from app.core.config import ConfigurationError
    import pytest
    monkeypatch.setenv("MARLIN_ENVIRONMENT", "test")
    app = create_app()
    assert app.state.settings.environment == "test"
    assert app.state.started is False
    with TestClient(app) as client:
        assert app.state.started is True
        assert client.get("/health").status_code == 200
    assert app.state.started is False
    monkeypatch.setenv("MARLIN_ENVIRONMENT", "bad")
    with pytest.raises(ConfigurationError):
        create_app()
