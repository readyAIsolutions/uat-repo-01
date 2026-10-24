import pytest
from app.core.config import load_settings, ConfigurationError


@pytest.mark.parametrize("field,value", [
    ("RHINO_COMPUTE_TIMEOUT", "0"), ("RHINO_COMPUTE_TIMEOUT", "-1"),
    ("RHINO_COMPUTE_TIMEOUT", "999"),
    ("RHINO_COMPUTE_MAX_ATTEMPTS", "0"), ("RHINO_COMPUTE_MAX_ATTEMPTS", "99"),
    ("RHINO_COMPUTE_BACKOFF_SECONDS", "-1"), ("RHINO_COMPUTE_BACKOFF_SECONDS", "SECRET_SENTINEL"),
])
def test_invalid_resilience_settings_fail_safely(field, value, monkeypatch):
    monkeypatch.setenv(field, value)
    with pytest.raises(ConfigurationError) as caught:
        load_settings()
    assert field in str(caught.value)
    assert "SECRET_SENTINEL" not in str(caught.value)


def test_resilience_defaults():
    settings = load_settings()
    assert settings.rhino_compute_timeout == 10.0
    assert settings.rhino_compute_max_attempts == 3
    assert settings.rhino_compute_backoff_seconds == 0.0
