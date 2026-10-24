import pytest


def test_explicit_absolute_env_file_and_safe_failure(tmp_path, monkeypatch):
    from app.core.config import load_settings, ConfigurationError
    file = tmp_path / ".env"
    file.write_text("MARLIN_ENVIRONMENT=test\nRHINO_COMPUTE_API_KEY=SECRET_SENTINEL\n")
    monkeypatch.chdir(tmp_path)
    assert load_settings().environment == "development"
    settings = load_settings(env_file=file)
    assert settings.environment == "test"
    assert "SECRET_SENTINEL" not in repr(settings)
    monkeypatch.setenv("MARLIN_ENVIRONMENT", "production")
    assert load_settings(env_file=file).environment == "production"
    monkeypatch.setenv("MARLIN_ENVIRONMENT", "SECRET_SENTINEL")
    with pytest.raises(ConfigurationError) as caught:
        load_settings(env_file=file)
    assert "SECRET_SENTINEL" not in str(caught.value)
    assert "MARLIN_ENVIRONMENT" in str(caught.value)
