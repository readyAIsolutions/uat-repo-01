"""Isolated MARLIN Rhino MVP, Section 1 only."""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .core.config import load_settings
from .services.rhino.unconfigured import UnconfiguredRhinoAdapter


def _build_rhino_service(settings):
    """Pick an adapter from config. Construction performs NO network I/O."""
    if settings.rhino_compute_url is None:
        return UnconfiguredRhinoAdapter()
    from .services.rhino.client import RhinoComputeClient
    from .services.rhino.configured import ConfiguredRhinoAdapter
    api_key = (settings.rhino_compute_api_key.get_secret_value()
               if settings.rhino_compute_api_key else None)
    client = RhinoComputeClient(
        str(settings.rhino_compute_url), api_key=api_key,
        timeout=settings.rhino_compute_timeout,
        max_attempts=settings.rhino_compute_max_attempts,
        backoff=settings.rhino_compute_backoff_seconds)
    return ConfiguredRhinoAdapter(
        client,
        station_definition=settings.rhino_station_definition,
        hull_definition=settings.rhino_hull_definition,
        box_definition=settings.rhino_box_definition)
from .core.http import SafeRequestMiddleware, install_error_handlers
from .api.rhino import router as rhino_router
from .api.vessel import router as vessel_router


UI_DIR = Path(__file__).resolve().parent / "ui"


def create_app(*, env_file: str | Path | None = None) -> FastAPI:
    settings = load_settings(env_file=env_file)

    @asynccontextmanager
    async def lifespan(app):
        app.state.started = True
        try:
            yield
        finally:
            app.state.started = False

    app = FastAPI(title="MARLIN Rhino MVP", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.rhino_service = _build_rhino_service(settings)
    app.state.started = False
    install_error_handlers(app)
    app.include_router(rhino_router)
    app.include_router(vessel_router)
    app.add_middleware(SafeRequestMiddleware, log_level=settings.log_level)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "marlin-rhino-mvp"}

    # Section 7: same-origin functional UI (kept out of the OpenAPI surface).
    if UI_DIR.is_dir():
        app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")

        @app.get("/", include_in_schema=False)
        async def ui_index():
            return FileResponse(UI_DIR / "index.html")

    return app
