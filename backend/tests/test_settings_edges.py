import traceback
import pytest
from pydantic import ValidationError
from app.core.config import Settings, load_settings, ConfigurationError


@pytest.mark.parametrize("environment", ["development", "test", "production"])
def test_environment_options(environment, monkeypatch):
    monkeypatch.setenv("MARLIN_ENVIRONMENT", environment)
    assert load_settings().environment == environment


@pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
def test_log_levels(level, monkeypatch):
    monkeypatch.setenv("MARLIN_LOG_LEVEL", level)
    assert load_settings().log_level == level


@pytest.mark.parametrize("field,value", [("MARLIN_ENVIRONMENT", "SECRET_SENTINEL"),
    ("MARLIN_LOG_LEVEL", "SECRET_SENTINEL"), ("RHINO_COMPUTE_URL", "SECRET_SENTINEL"),
    ("RHINO_COMPUTE_URL", "file:///SECRET_SENTINEL")])
def test_invalid_settings_do_not_leak(field, value, monkeypatch):
    monkeypatch.setenv(field, value)
    with pytest.raises(ConfigurationError) as caught:
        load_settings()
    assert field in str(caught.value)
    assert caught.value.__context__ is None
    assert "SECRET_SENTINEL" not in "".join(traceback.format_exception(caught.value))
    with pytest.raises(ValidationError) as raw:
        Settings()
    assert "SECRET_SENTINEL" not in str(raw.value)


def test_secret_representation_and_blank_fields(monkeypatch):
    monkeypatch.setenv("RHINO_COMPUTE_API_KEY", "SECRET_SENTINEL")
    monkeypatch.setenv("RHINO_COMPUTE_URL", "https://host.invalid/?token=SECRET_SENTINEL")
    settings = load_settings()
    assert "SECRET_SENTINEL" not in repr(settings)
    assert "SECRET_SENTINEL" not in str(settings.rhino_compute_api_key)
    assert settings.rhino_compute_api_key.get_secret_value() == "SECRET_SENTINEL"
    monkeypatch.setenv("RHINO_COMPUTE_API_KEY", "")
    monkeypatch.setenv("RHINO_COMPUTE_URL", "")
    assert load_settings().rhino_compute_api_key is None
    assert load_settings().rhino_compute_url is None


def test_env_file_paths_are_explicit(tmp_path):
    with pytest.raises(ConfigurationError):
        load_settings(env_file=".env")
    with pytest.raises(ConfigurationError):
        load_settings(env_file=tmp_path / "missing")
    with pytest.raises(ConfigurationError):
        load_settings(env_file=tmp_path)
    bad = tmp_path / "bad.env"
    bad.write_bytes(b"\xff")
    with pytest.raises(ConfigurationError, match="Unable to read"):
        load_settings(env_file=bad)


def test_factory_env_file_and_unrelated_legacy_keys(tmp_path):
    from app.mvp import create_app
    file = tmp_path / ".env"
    file.write_text("MARLIN_ENVIRONMENT=test\nDATABASE_URL=unused\n")
    assert create_app(env_file=file).state.settings.environment == "test"
