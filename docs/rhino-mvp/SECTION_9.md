# MARLIN Section 9 — Real Rhino.Compute Correction Gate

Objective: make the Rhino layer speak the OFFICIAL Rhino.Compute contract instead
of the behaviour of the local test stub. Corrections verified against official
McNeel sources (developer.rhino3d.com + the compute.rhino3d source). Nothing here
is fabricated.

## What was corrected (doc-verified)

1. Health probe — was `GET /rhino/` (invented). Now `GET /healthcheck` (plus
   `/version`, `/validate`, `/io`) on the Compute base URL, e.g.
   `http://localhost:6500` (developer.rhino3d.com/guides/compute/development).

2. API key header — was `Authorization: Bearer <key>` (wrong). Now
   `RhinoComputeKey: <key>` (src/rhino.compute/ApiKeyMiddleware.cs, constant
   `API_KEY_NAME = "RhinoComputeKey"`). Sent on every request when a key is set.

3. Grasshopper invocation — was `POST /grasshopper {"definition": "...", "algo": {...}}`
   (a stub convention). Now the official `Schema` body
   (src/compute.geometry/IO/Schema.cs): `pointer` (server-side `.gh` path) or
   `algo` (base64 `.gh`), plus `values` (a DataTree per input), `modelunits`,
   `cachesolve`. The response is read via `values`/`warnings`/`errors`.
   `app/services/rhino/compute_schema.py` builds `values` and normalizes outputs.

4. Cross-request geometry IDs — removed. The hull path was two solves that passed
   curve IDs from one to the next (unsafe: Compute is stateless). Now ONE
   self-contained solve per request; the hull definition builds its own stations
   and returns surfaces + measurements directly.

5. Definition names are now CONFIG (server-side pointers), not hard-coded fake
   identifiers: `RHINO_STATION_DEFINITION`, `RHINO_HULL_DEFINITION`,
   `RHINO_BOX_DEFINITION`.

6. `file_reference` — no longer fabricated (`rhino://stub/hull.3dm`). It is now
   `None` unless a real file exists.

7. UI asset defect — the distributed ZIP omitted `backend/app/ui/vendor/`
   (`three.module.js`, `OrbitControls.js`), so `test_static_assets_are_served`
   returned 404 from the ZIP. The repo always had them; the packaging did not.
   Rebuilt the code ZIP to INCLUDE `backend/app/ui/vendor/` (verified: both files
   present). `test_ui.py` passes in the repo (8/8).

## Tests

Mocked (stub now emulates the REAL contract — `/healthcheck` text, `/version`,
`/grasshopper` Schema):
- test_rhino_client.py, test_rhino_client_edges.py, test_configured_adapter.py,
  test_rhino_adapter_edges.py, test_adapter_selection.py, test_transport_resilience.py
- test_stations_api.py, test_stations_acceptance.py, test_hull_api.py,
  test_integration_rhino_mvp.py, test_api_routes.py

Real Rhino (skipped without a node; NOT counted as passed):
- test_live_rhino.py (status/box/stations/hull), test_stations_acceptance live.

Result:

    .venv-mvp/bin/python -m pytest -c backend/pytest.ini backend/tests
    184 passed, 5 skipped in 36.46s

smoke OK; legacy 40/40 SHA-256 unchanged; no Git.

## Still required for a REAL Rhino pass (needs your node + a .gh)

- A real `MARLIN_HULL.gh` (or RhinoCommon/Hops definition) exposing the inputs
  MARLIN sends (`loa, lwl, beam, draft, depth, station_count, deadrise,
  transom_width, chine_height, bow_height`) and the outputs MARLIN reads
  (`stations`, `surfaces`, `sheer`, `bow`, `stern`, `measurements`).
  MARLIN computes the parameter VALUES locally; the .gh must build the geometry.
- Real `.3dm` output. The code no longer fakes a file reference; a real writer
  (rhino3dm) + a safe download endpoint is the next step, using the geometry the
  node actually returns.
- Run `test_live_rhino.py` with `RHINO_COMPUTE_URL` set, and confirm the
  `values` DataTree serialization against the installed Compute version.

## Known limitations

- The `values`/DataTree serialization is implemented to the documented schema but
  is only fully validated against a live node.
- Naval parameters (deadrise/transom_width/chine_height/bow_height) are now
  PASSED to the definition; they affect geometry only once the .gh uses them.

## Files

Added: backend/app/services/rhino/compute_schema.py, docs/rhino-mvp/SECTION_9.md
Modified: backend/app/services/rhino/{client,configured}.py,
  backend/app/services/vessel/{stations,hull}.py, backend/app/core/config.py,
  backend/app/mvp.py, backend/tests/stubs/rhino_stub.py + 11 test files.
