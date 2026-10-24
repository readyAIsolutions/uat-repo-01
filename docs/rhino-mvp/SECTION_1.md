# MARLIN Rhino MVP — Section 1 only

## Scope and honesty

This is an isolated FastAPI foundation, not the legacy production CAD pipeline.
Real Rhino: **NOT TESTED**. No Rhino HTTP client, outbound Rhino request, geometry
implementation, Grasshopper execution, AI, Orca3D, analysis, compliance, or
manufacturing was added. No future section is declared working.

The default service is UnconfiguredRhinoAdapter. Every contract operation raises
RhinoNotConfiguredError (RHINO_NOT_CONFIGURED), even when a URL/key is provided
and even in production. No production mock selection or CAD fallback exists in
this MVP.

> SUPERSEDED BY SECTION 2 (2026-10-03): the "even when a URL is provided" rule
> applied to Section 1 only. Section 2 adds config-driven selection — a set
> RHINO_COMPUTE_URL now selects the real transport adapter (see SECTION_2.md).
> The no-network-at-startup and no-local-geometry guarantees still hold.

Test-only mock adapters return explicitly marked metadata, geometry=null,
and cad_files=[]; they do not produce fake CAD files.

The only application endpoint is GET /health:

    {"status":"ok","service":"marlin-rhino-mvp"}

This is process health, NOT evidence of Rhino connectivity. Standard /docs,
/redoc, /docs/oauth2-redirect and /openapi.json remain available. There are no
/api/rhino/status, /api/rhino/box or geometry routes. Test routes exist only in tests.

## Install and test

From /home/nova/marlin-prod:

    python3 -m venv .venv-mvp
    .venv-mvp/bin/python -m pip install -r backend/requirements-mvp-dev.txt
    .venv-mvp/bin/python -m pytest -c backend/pytest.ini backend/tests
    .venv-mvp/bin/python -m pip check
    .venv-mvp/bin/python docs/rhino-mvp/smoke.py

The existing .venv-prod and backend/requirements.txt are not modified. The pinned
FastAPI/Pydantic generation follows the supplied Section 1 brief, not a claim
that these are the latest or security-hardened deployment versions. A dependency
security/update review is still necessary before public deployment.

## Start (isolated, local only)

    cd /home/nova/marlin-prod
    .venv-mvp/bin/python -m uvicorn app.mvp:create_app --factory --app-dir backend --host 127.0.0.1 --port 8011 --no-access-log

Use --no-access-log: Uvicorn's normal access logger includes raw URLs and query
strings. The MVP provides its own safe JSON request logger. Do not run this MVP
with TRACE logging, debugging middleware, or an unredacted reverse-proxy access
log and assume request privacy is preserved.

The smoke script starts a real Uvicorn process on an OS-assigned loopback port,
checks readiness and endpoints, checks server logs for a sentinel secret, and
stops the process. It does not leave a server running and makes no Rhino requests.

## Deterministic configuration

- MARLIN_ENVIRONMENT: development (default), test, production.
- MARLIN_LOG_LEVEL: DEBUG, INFO (default), WARNING, ERROR, CRITICAL; uppercase.
- RHINO_COMPUTE_URL: optional HTTP(S) URL; blank means unset; reserved for later.
- RHINO_COMPUTE_API_KEY: optional SecretStr; blank means unset; reserved for later.
- No current-directory .env search, implicit env-file loading, or settings cache.
- create_app(env_file=...) / load_settings(env_file=...) require an existing
  absolute file path when supplied. UTF-8 is required. Relative/missing paths fail.
- Environment variables override explicit env-file values, then defaults apply.
- Unrelated legacy env-file keys are ignored. Root .env.example retains legacy
  entries; its Rhino URL is intentionally blank and its keys are unique.
- Legacy ENVIRONMENT does not select MARLIN_ENVIRONMENT.

For an explicit env file without changing precedence, from the repository root:

    PYTHONPATH=backend .venv-mvp/bin/python -c 'import uvicorn; from app.mvp import create_app; uvicorn.run(create_app(env_file="/home/nova/marlin-prod/.env"), host="127.0.0.1", port=8011, access_log=False)'

The file must exist; it is not created or populated with real credentials here.
Use load_settings/create_app as the safe configuration boundary. Invalid settings
raise ConfigurationError with allowed field names only and no chained raw
exception. Settings repr omits both Rhino fields, and SecretStr masks the API key.
Do not serialize arbitrary settings models or raw Pydantic errors into logs:
hide_input_in_errors controls the human-readable error, not every error API.

## Errors, logging, lifecycle, and dependency injection

Each HTTP request receives a fresh server-owned UUID hex X-Request-ID. Incoming
IDs are deliberately ignored, including UUID-looking values. Error JSON includes
request_id and error.code/message. HTTP exception details/headers, validation
inputs, exception strings, request bodies, raw paths/query strings and arbitrary
methods are not copied into MVP logs or error bodies.

marlin.mvp emits JSON with event, allowlisted method, registered route template
(or <unmatched>), status and request_id. Its configured threshold is per app;
root logging handlers are not cleared. The app does not reconfigure unrelated
library loggers. HTTP/validation/500 responses are safe and correlated. A typed
RhinoNotConfiguredError maps to 503 on a caller's route (no such public MVP route).

The lifespan records local startup/shutdown state only and performs no external
initialization. The factory imports no legacy main/database/engine module.

Routes use Depends(get_rhino_service), whose return type is RhinoService Protocol.
The factory selects the unavailable adapter; callers never import adapter
internals. Tests replace it using app.dependency_overrides or app.state.rhino_service
without editing route logic. Protocol operation arguments are provisional; no
future geometry validation or file format is implemented in this section.

Streaming/WebSockets, auth, CORS and deployment TLS are not MVP capabilities.
Once a response is started, middleware cannot replace it with a JSON error;
future streaming support needs a separate safe disconnect/error design.

## Actual execution evidence

Observed test-first vertical slices (each targeted RED was followed by minimal
implementation and a whole-suite GREEN):

| Slice | Observed RED | Subsequent whole-suite GREEN |
|---|---|---|
| Health factory | 1 failed: app.mvp missing | 1 passed |
| Settings defaults/env | 1 failed: app.core missing | 2 passed |
| Explicit env file/safe config errors | 1 failed: load_settings absent | 3 passed |
| Factory config/lifespan | 1 failed: app.state.settings absent | 4 passed |
| Unexpected error safety | 1 failed: non-JSON 500 | 5 passed |
| HTTP/validation error envelope | 3 failed: missing error envelope | 8 passed |
| Structured request logging | 1 failed: no request records | 9 passed |
| Unconfigured service contract | 4 failed: services module absent | 13 passed |
| Dependency replacement | 1 failed: dependency module absent | 14 passed |

Additional edge/security/isolation tests then passed without implementation
changes: 38 passed in 1.05s. An additional four-case error/log matrix and import
ordering cleanup produced the final observed result:

    .venv-mvp/bin/python -m pytest -c backend/pytest.ini backend/tests
    42 passed in 1.06s

Warnings are treated as errors; no warning summary in the final run.

One initial setup issue was NOT a behavior RED: the unpinned newest AnyIO emitted
a BlockingPortal deprecation from this older Starlette TestClient, stopping test
collection under warnings-as-errors. Pinning compatible anyio==4.6.2.post1 and
starlette==0.38.6 resolved it on the first correction. pytest-asyncio fixture loop
scope was explicitly configured before tests. No twice-failed implementation
problem required escalation.

Live Uvicorn smoke output (exit 0):

    /health        200
    /docs          200
    /openapi.json  200
    unknown route 404 (safe correlated JSON)
    secret_free_logs: true
    server_stopped: true

    .venv-mvp/bin/python -m pip check
    No broken requirements found.

A clean subprocess test blocks outbound socket connection/DNS calls and forbidden
legacy/DB/AI/Rhino imports before importing/starting app.mvp and exercising health.
That isolation test passed. No live DB or Rhino was needed.

Before implementation, SHA-256 hashes were recorded for 40 preexisting backend/app
and frontend source/config files (excluding generated caches, node_modules, .next).
All 40 still match, including empty backend/app/__init__.py, main.py, models.py and
rhino_engine.py. Evidence: .mvp-legacy-baseline.json. Root .env.example has 19 unique
keys. No Git repository was initialized and no commit or push was made.

## File inventory

All paths below are relative to /home/nova/marlin-prod.

New application files:
- backend/app/mvp.py
- backend/app/core/__init__.py
- backend/app/core/config.py
- backend/app/core/http.py
- backend/app/services/__init__.py
- backend/app/services/rhino/__init__.py
- backend/app/services/rhino/contract.py
- backend/app/services/rhino/dependencies.py
- backend/app/services/rhino/unconfigured.py

New tests:
- backend/tests/__init__.py
- backend/tests/conftest.py
- backend/tests/fakes/__init__.py
- backend/tests/fakes/rhino.py
- backend/tests/test_mvp.py
- backend/tests/test_settings.py
- backend/tests/test_config_loading.py
- backend/tests/test_lifecycle.py
- backend/tests/test_errors.py
- backend/tests/test_http_failures.py
- backend/tests/test_logging.py
- backend/tests/test_rhino.py
- backend/tests/test_dependencies.py
- backend/tests/test_settings_edges.py
- backend/tests/test_isolation.py
- backend/tests/test_security_edges.py
- backend/tests/test_error_log_matrix.py

Setup/docs/evidence:
- backend/requirements-mvp.txt (resumed and completed; compatible transitive pins)
- backend/requirements-mvp-dev.txt (created by the prior run; retained)
- backend/pytest.ini (resumed; explicit asyncio fixture scope)
- .venv-mvp/ (isolated environment; not a source artifact)
- .env.example (only Section 1 block/Rhino default updated)
- .mvp-legacy-baseline.json
- docs/rhino-mvp/SECTION_1.md
- docs/rhino-mvp/smoke.py

Stop boundary: Section 1 complete. Real Rhino and all subsequent sections remain
unimplemented and untested in this isolated MVP.
