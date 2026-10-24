import pytest


@pytest.fixture(autouse=True)
def clean_mvp_environment(monkeypatch):
    import tempfile
    for name in ("MARLIN_ENVIRONMENT", "MARLIN_LOG_LEVEL", "RHINO_COMPUTE_URL",
                 "RHINO_COMPUTE_API_KEY", "RHINO_COMPUTE_TIMEOUT",
                 "RHINO_COMPUTE_MAX_ATTEMPTS", "RHINO_COMPUTE_BACKOFF_SECONDS",
                 "RHINO_STATION_DEFINITION", "RHINO_HULL_DEFINITION",
                 "RHINO_BOX_DEFINITION", "MARLIN_STORAGE_DIR"):
        monkeypatch.delenv(name, raising=False)
    # keep generated .3dm files out of the repo during tests
    monkeypatch.setenv("MARLIN_STORAGE_DIR", tempfile.mkdtemp(prefix="marlin-store-"))
