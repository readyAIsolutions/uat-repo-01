def test_settings_defaults_and_environment(monkeypatch):
    from app.core.config import Settings
    assert Settings().environment == "development"
    assert Settings().log_level == "INFO"
    assert Settings().rhino_compute_url is None
    monkeypatch.setenv("MARLIN_ENVIRONMENT", "production")
    assert Settings().environment == "production"
