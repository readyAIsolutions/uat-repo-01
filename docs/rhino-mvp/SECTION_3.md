# MARLIN Rhino MVP — Section 3

## Scope note (read first)

No Section 3 brief was supplied. Section 1's brief forbade building subsequent
sections; the operator authorised forward progress ("go"). As in Section 2, the
agent defined this scope and stopped at its boundary. Scope is documented here
and is easy to adjust — no legacy behaviour changed.

Section 1 explicitly deferred exposing public Rhino routes ("Do not expose
/api/rhino/status or /api/rhino/box"). Section 3 delivers exactly that surface,
safely and honestly.

## What Section 3 is

The public MVP API surface, backed only by the injected RhinoService:

- `GET /api/rhino/status` — always 200, reports state honestly:
  unconfigured → `{configured:false, reachable:false, status:"unconfigured"}`;
  configured → the adapter's reachability probe result (ok / unreachable / error).
- `POST /api/rhino/box` — validated body `{width,length,height}` (each >0, ≤10000),
  calls `service.create_box(...)`, returns the transport round-trip result.
- `GET /api/rhino/capabilities` — honest, static: `real_rhino_tested:false`,
  health_check/create_box/execute_grasshopper "available", create_geometry "reserved".

Error mapping reuses Section 2 handlers: unconfigured→503 RHINO_NOT_CONFIGURED,
unreachable→503 RHINO_UNAVAILABLE, node error/invalid JSON→502 RHINO_REQUEST_FAILED,
validation→422 VALIDATION_ERROR. Every response carries a server-owned
X-Request-ID; inputs, headers, bodies and exception text are never echoed.

## Honesty boundary (unchanged in spirit)

- Real Rhino: **NOT TESTED**. No licensed node, no Grasshopper definition, no
  Orca3D, no geometry, no AI, no analysis/compliance/manufacturing.
- Routes author no geometry locally; they call the service and return its answer.
- No node is contacted at import or startup; construction stays network-free.
- `create_geometry` remains reserved and is never routed.

## Deliberate supersession of a Section 1 test

Section 1's `test_isolation.py::test_public_routes_only_health_and_docs` asserted
the public surface was exactly `{/health}` and that `/api/rhino/status` and
`/api/rhino/box` returned 404. Section 3 intentionally adds those routes, so the
test was renamed to `test_public_routes_are_the_documented_surface` and now pins
the exact new surface `{/health, /api/rhino/status, /api/rhino/box,
/api/rhino/capabilities}` — it still fails loudly if an unplanned route appears.

## Files added (relative to /home/nova/marlin-prod)

- backend/app/api/__init__.py
- backend/app/api/rhino.py                (public router + pydantic models)
- backend/tests/test_api_routes.py
- backend/tests/test_api_routes_edges.py
- docs/rhino-mvp/SECTION_3.md (this file)

Files modified:
- backend/app/mvp.py            (include the rhino router)
- backend/tests/test_isolation.py (supersession, documented inline)
- docs/rhino-mvp/smoke.py       (now also probes /api/rhino/status and /capabilities)

## Actual execution evidence

Test-first vertical slices:

| Slice | Observed RED | Subsequent GREEN |
|---|---|---|
| Public routes | 14 failed: routes missing (404) | 14 passed (after excluding None on the status model) |
| Isolation surface | 1 failed: public surface changed by design | full suite 84 |
| Edge/security | (added after green; passed first run) | full suite 90 |

Final observed result:

    .venv-mvp/bin/python -m pytest -c backend/pytest.ini backend/tests
    90 passed in 16.37s

Warnings are errors; no warning summary in the final run.

Live Uvicorn smoke (real process, two scenarios, exit 0):

    unconfigured           : /health 200, /docs 200, /openapi.json 200, /api/rhino/status 200, /api/rhino/capabilities 200, unknown 404
    configured_unreachable : /health 200, /docs 200, /openapi.json 200, /api/rhino/status 200, /api/rhino/capabilities 200, unknown 404

Both runs: secret-free logs, clean shutdown. The configured-unreachable run again
proves startup makes no probe and an unreachable node does not break the app.

    .venv-mvp/bin/python -m pip check
    No broken requirements found.

Legacy preservation: the 40 pre-existing backend/app + frontend files recorded in
.mvp-legacy-baseline.json are all unchanged (SHA-256 match). No Git was used.

## Stop boundary

Section 3 complete. No live Rhino was contacted or tested. No geometry authoring,
Grasshopper definition authoring, AI, Orca3D, analysis, compliance or
manufacturing was implemented. Subsequent sections remain unimplemented.
