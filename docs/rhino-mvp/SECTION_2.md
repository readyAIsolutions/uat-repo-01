# MARLIN Rhino MVP — Section 2

## Scope note (read first)

No Section 2 brief was supplied (only /tmp/marlin-section1-brief.txt existed).
Section 1's brief forbade building subsequent sections. After the operator
repeatedly authorised forward progress ("next", "continue"), the agent defined
Section 2 as the natural next slice and stopped at its boundary. This scope is
documented here and is trivially adjustable — it changes no legacy behaviour.

## What Section 2 is

Real Rhino.Compute HTTP **transport** plus a config-selected adapter:

- `RhinoComputeClient` — httpx transport to a Rhino.Compute node (Bearer auth,
  timeouts, typed errors). Transport only.
- `ConfiguredRhinoAdapter` — implements the Section 1 `RhinoService` contract:
  `health_check()` (real reachability probe), `create_box()` and
  `execute_grasshopper()` (transport round-trips that send parameters and return
  the node's answer).
- Factory selection: `RHINO_COMPUTE_URL` present → `ConfiguredRhinoAdapter`;
  absent → `UnconfiguredRhinoAdapter` (unchanged Section 1 default).
- Safe error mapping: RHINO_UNAVAILABLE→503, RHINO_REQUEST_FAILED→502,
  RHINO_CAPABILITY_UNAVAILABLE→501, RHINO_NOT_CONFIGURED→503.

## Honesty boundary (unchanged in spirit)

- Real Rhino: **NOT TESTED**. No licensed node, no Grasshopper definition, no
  Orca3D, no geometry, no AI, no analysis/compliance/manufacturing.
- The client authors **no geometry locally** and invents **no fallback hull**.
  It sends parameters and returns what the node says.
- `create_geometry()` (arbitrary geometry authoring) is **reserved** and raises
  `RhinoCapabilityUnavailableError` **without making a request**.
- App construction performs **no network I/O** (no startup probe), proven live.
- Secrets: the API key is held privately, never in `repr()`, error text or logs.

## Deliberate supersession of a Section 1 rule

Section 1 stated that even with a URL supplied the default stays unconfigured.
Section 2 supersedes that: a configured URL now selects the real adapter. The
Section 1 test `test_dependencies.py::test_two_adapters_without_changing_routes`
was updated to expect RHINO_UNAVAILABLE (unreachable loopback node) instead of
RHINO_NOT_CONFIGURED, and its comment records why. Its real intent — dependency
replacement without editing route logic — is preserved. See SECTION_1.md note.

## Files added (relative to /home/nova/marlin-prod)

- backend/app/services/rhino/errors.py      (typed errors)
- backend/app/services/rhino/client.py      (httpx transport)
- backend/app/services/rhino/configured.py  (config-selected adapter)
- backend/tests/stubs/__init__.py
- backend/tests/stubs/rhino_stub.py         (TEST-ONLY loopback node stub)
- backend/tests/test_rhino_client.py
- backend/tests/test_configured_adapter.py
- backend/tests/test_adapter_selection.py
- backend/tests/test_rhino_error_handlers.py
- backend/tests/test_rhino_client_edges.py
- backend/tests/test_rhino_adapter_edges.py
- docs/rhino-mvp/SECTION_2.md (this file)

Files modified:
- backend/app/mvp.py            (config-driven adapter selection; no startup I/O)
- backend/app/core/http.py      (handlers for the new typed errors)
- backend/app/services/rhino/contract.py (execute_grasshopper inputs optional)
- backend/tests/stubs/... /test_rhino_client_edges.py (see above)
- backend/tests/test_dependencies.py (supersession, documented inline)
- backend/requirements-mvp.txt  (httpx promoted to runtime)
- backend/requirements-mvp-dev.txt (httpx removed from dev)
- docs/rhino-mvp/smoke.py       (two live scenarios)

## Actual execution evidence

Test-first vertical slices (each targeted RED followed by minimal implementation):

| Slice | Observed RED | Subsequent GREEN |
|---|---|---|
| Transport client | 5 failed: app.services.rhino.client missing | 5 passed |
| Configured adapter | 7 failed: configured module missing | 7 passed; full suite 54 |
| Adapter selection + error handlers | 6 failed: wrong selection / unhandled typed errors | full suite 61 |
| Edge/security | 1 failed: execute_grasshopper required inputs | full suite 70 |

Final observed result:

    .venv-mvp/bin/python -m pytest -c backend/pytest.ini backend/tests
    70 passed

Warnings are errors; no warning summary in the final run.

Live Uvicorn smoke (real process, two scenarios, exit 0):

    unconfigured            : /health 200, /docs 200, /openapi.json 200, unknown 404, secret-free logs, stopped
    configured_unreachable  : /health 200, /docs 200, /openapi.json 200, unknown 404, secret-free logs, stopped

The configured-unreachable run proves startup makes no probe and an unreachable
node does not break the app.

    .venv-mvp/bin/python -m pip check
    No broken requirements found.

Legacy preservation: the 40 pre-existing backend/app + frontend files recorded in
.mvp-legacy-baseline.json are all unchanged (SHA-256 match). No Git was used.

## Stop boundary

Section 2 complete. No live Rhino was contacted or tested. No geometry authoring,
Grasshopper definition authoring, AI, Orca3D, analysis, compliance or
manufacturing was implemented. Subsequent sections remain unimplemented.
