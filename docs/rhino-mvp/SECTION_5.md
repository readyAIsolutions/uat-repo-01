# MARLIN Section 5 — Parametric Station Curve Generator

Built to the operator's Section 5 brief. Validated vessel parameters (Section 4)
→ Rhino.Compute → mathematically controlled station curves. No hull surface is
lofted (Section 6's job).

## What Section 5 does

`POST /api/vessel/stations`

1. Accepts Section 4 vessel parameters (+ optional `station_count`, default 15,
   allowed 10–20).
2. Validates everything BEFORE any Rhino call (Section 4 rules + hull family +
   station count).
3. Computes station parameter values locally (deterministic math).
4. Has **Rhino.Compute create the actual station curves** via the injected
   RhinoService (`execute_grasshopper`, definition `marlin_station_curves`).
5. Returns structured metadata, curve references and bounding information.

Only `hull_family = MONOHULL` is supported (others rejected with
`UNSUPPORTED_HULL_FAMILY`). Planing/catamaran/trimaran are not added.

### Station math (deterministic, smooth, not hand-coded)

- Normalized x: 0.0 = stern, 1.0 = bow. Station x = t·LOA → spans full LOA.
- `shape_factor(t)`: smooth two-half sine/cosine blend. stern 0.62, **midship
  exactly 1.00 (widest)**, bow 0.10. C1-continuous at midship (zero slope).
- `local_beam = beam · shape_factor(t)`.
- Section: symmetric half-section from keel (0, −draft) to sheer
  (half_beam, depth − draft), mirrored to port. Vertical extent = depth;
  lowest point = −draft; widest = beam at midship.
- Reference curves: baseline (y=0, z=−draft), centerline (y=0, z=0),
  design_waterline (z=0 across ±beam/2 at midship).

### Rhino payload / result

Request to Rhino.Compute (`/grasshopper`): definition + algo inputs
(loa, beam, draft, depth, station_count, waterline_z, stations[], reference_curves[]).
Expected response: `{curves:[{id}...], reference_curves:{baseline,centerline,design_waterline}}`.
A response without a `curves` list is treated as malformed → 502.

### Success response (abridged)

    {"project_id":"MARLIN-001","status":"success","station_count":15,
     "geometry_version":1,"hull_family":"MONOHULL","units":"m",
     "loa":20.0,"lwl":18.5,"beam":5.5,"draft":1.2,"depth":2.4,
     "rhino_compute_used":true,
     "stations":[{"index","x","local_beam","shape_factor","points"}] ,
     "curve_ids":[...], "reference_curve_ids":{...},
     "bounding_box":{"min":[0,-2.75,-1.2],"max":[20,2.75,1.2]},
     "warnings":[],"errors":[]}

## HONEST LIMITATION (read this)

**There is no live Rhino.Compute node on this host** (Rhino is Windows-only and
licensed). Therefore:

- The station curves were **NOT created by real Rhino** in this environment.
- The unit/integration tests exercise the full pipeline against a **loopback
  Rhino-shaped stub** (mocked Rhino responses) — they prove MARLIN computes the
  parameters, calls Rhino correctly, maps the response, and handles failures.
- The locally computed station parameters ARE real and deterministic and are
  fully verified by the acceptance test.
- `rhino_compute_used: true` is only returned on a real 200 from Rhino with a
  `curves` list. Without a node the endpoint returns 503 (NOT_CONFIGURED /
  UNAVAILABLE) or 502 (malformed) — it never fabricates Rhino geometry.
- The live Rhino integration test (`test_live_rhino_integration`) is
  **SKIPPED** here (no `RHINO_COMPUTE_URL`); it runs automatically once a
  licensed node is provisioned.

## Tests

Unit (local math): shape factor endpoints/midship/smoothness; station span;
max beam at midship; symmetry; draft/depth vertical extent; bounding box;
reference curves.

API + errors (mocked Rhino): valid 20 m monohull; station_count honored/defaulted;
small (×0.4) and large (×3.0) vessels; invalid LOA; negative beam; depth<draft;
unsupported hull family; station_count out of range; Rhino unavailable; Rhino
unconfigured; Rhino timeout; malformed Rhino response; rejected-before-Rhino
(no Rhino call on invalid input).

Acceptance (20 m) — all verified:
- exactly 15 station positions spanning the full LOA
- max station width ≈ requested beam (5.5), at midship
- lowest geometry ≈ −draft (−1.2); sheer ≈ depth−draft (1.2)
- symmetric about centerline (±2.75)
- bow narrows; midship widest
- Rhino.Compute was actually invoked (stub recorded 1 `/grasshopper` POST)

## Actual execution evidence

| Slice | Observed RED | Subsequent GREEN |
|---|---|---|
| Station math + API + acceptance | collection error: app.services.vessel.stations missing; API 404 | 22 passed, 1 skipped |
| Public surface | isolation pinned old surface | full suite 148 passed, 1 skipped |

    .venv-mvp/bin/python -m pytest -c backend/pytest.ini backend/tests
    148 passed, 1 skipped in 28.08s

    .venv-mvp/bin/python docs/rhino-mvp/smoke.py   # SMOKE_EXIT=0
      unconfigured           : ... /api/vessel/validate 200, /api/vessel/stations 503 RHINO_NOT_CONFIGURED
      configured_unreachable : ... /api/vessel/validate 200, /api/vessel/stations 503 RHINO_UNAVAILABLE

    .venv-mvp/bin/python -m pip check -> No broken requirements found.
    Legacy: 40 pre-existing backend/app + frontend files SHA-256 unchanged. No Git used.

## FILES CREATED

- backend/app/services/vessel/stations.py
- backend/tests/test_stations_math.py
- backend/tests/test_stations_api.py
- backend/tests/test_stations_acceptance.py
- docs/rhino-mvp/SECTION_5.md (this file)

## FILES MODIFIED

- backend/app/api/vessel.py            (POST /api/vessel/stations)
- backend/app/services/vessel/validation.py (measurement_meters helper)
- backend/tests/test_isolation.py      (public surface += /api/vessel/stations)
- docs/rhino-mvp/smoke.py              (live stations probe)

## ENDPOINTS CREATED

- POST /api/vessel/stations

## RHINO OPERATIONS USED

- `RhinoService.execute_grasshopper(definition="marlin_station_curves", inputs)`
  → `RhinoComputeClient.run_grasshopper` → `POST {RHINO_COMPUTE_URL}/grasshopper`.

## TESTS RUN / PASSED / FAILED

- 149 collected: **148 passed, 1 skipped** (live-Rhino integration; no node), 0 failed.

## REAL RHINO RESULT

- Not run — no live Rhino.Compute node available. Reported honestly; no fake
  geometry claimed. Provision a node and set RHINO_COMPUTE_URL to run
  `test_live_rhino_integration` and get real NURBS station curves.

## KNOWN ISSUES

- No live Rhino node → real curve creation unverified in this environment.
- `.3dm`/preview-geometry export not produced (requires the Rhino node); the
  endpoint returns curve references + station parameter definitions instead.

## GEOMETRY LIMITATIONS

- Single hull family (MONOHULL); no planing/catamaran/trimaran.
- Deliberately simple controlled section shape, not a real yacht hull.
- Station section is a symmetric keel→sheer curve; no chine/flare/tumblehome.
- Reference curves are simple 2-point lines; DWL represented athwartships at midship.
- No hull surface lofted (by design — Section 6).

## Definition of done — met (with the live-node caveat)

- /api/vessel/stations exists ✓
- accepts Section 4 vessel data ✓
- Rhino.Compute creates the curves — **pipeline built & verified against a
  Rhino-shaped stub; NOT verified against a real node (none available)** ⚠
- station count controlled (10–20) ✓
- geometry roughly matches LOA/beam/draft/depth ✓ (verified by acceptance test)
- unit tests pass ✓
- real Rhino integration test — present, skipped without a node ⚠
- errors handled clearly (503/502/422) ✓
- output reusable by Section 6 (station definitions + curve refs) ✓

## STOP

Section 5 complete. STOPPING. No hull surface lofted. Section 6 not begun.
