# MARLIN Section 6 — First Parametric NURBS Hull

Built to the operator's Section 6 brief. Flow: validated vessel parameters
(Section 4) → station curves (Section 5) → Rhino.Compute → first parametric NURBS
hull. MONOHULL only. No hydrostatics/stability/Orca3D/AI/CFD/structure/multi-hull.

## What Section 6 does

`POST /api/vessel/hull`

1. Validates Section 4 parameters (+ hull family MONOHULL + station_count 10–20)
   BEFORE any Rhino call.
2. Reuses Section 5 station logic — Rhino call #1: `marlin_station_curves`.
3. Rhino call #2: `marlin_hull_loft` — loft the station curves, mirror for the
   opposite side, join where appropriate; returns port/starboard surfaces, sheer
   line, bow/stern terminations and geometry measurements.
4. MARLIN inspects the returned geometry honestly and returns a structured
   result. It never claims fairness.

## Geometry inspection (what MARLIN measures from Rhino's result)

- surface validity (per-surface `valid`)
- port/starboard symmetry (both sides present + bounding box symmetric about y=0)
- requested vs actual LOA / beam / draft, with error % and within-tolerance
- naked edges, invalid trims, self-intersections (reported by Rhino)
- surface normals (consistency flag)
- bounding box, number of surfaces
- serialization/export reference (`file_reference`, e.g. a .3dm URI) when provided

### Prototype tolerances (as specified)

- LOA within 1%, Beam within 1%, Draft within 2%.

Each dimension reports `{requested_m, actual_m, error_percent, within_tolerance}`.

### Status semantics (bad geometry is NOT hidden)

- Rhino transport/shape problems (unavailable, timeout, malformed/missing
  surfaces, empty surfaces, missing measurements) → HTTP 503 / 502.
- Geometry-quality problems (invalid surfaces, symmetry failure, dimension
  outside tolerance) → **HTTP 200 with `status: "failed"`** and clear warnings +
  false validation flags. This surfaces a bad result rather than hiding it.

Every success/failure result carries a warnings list, always including:
`"Surface fairness not assessed: Rhino creating a surface does not make it fair."`

## HONEST LIMITATION (read this)

**No live Rhino.Compute node exists on this host** (Rhino is Windows-only and
licensed). Therefore the hull surfaces were **NOT created by real Rhino** here:

- The pipeline is exercised end-to-end against a **loopback Rhino-shaped stub**
  (mocked Rhino responses) — it proves MARLIN builds station curves, requests the
  loft, maps surfaces, measures dimensions, and handles failures correctly.
- `rhino_compute_used: true` is only returned after a real 200 from Rhino with
  surfaces. Without a node the endpoint returns 503/502 — it never fabricates hull
  geometry.
- The real acceptance on THE TEST VESSEL (20 m / 5.5 m / 1.2 m / MONOHULL / 15
  stations) is verified at the **pipeline + inspection level** with mocked Rhino
  geometry. Live NURBS creation remains unverified until a node is provisioned.

## Output (abridged, per brief shape)

    {"project_id":"MARLIN-001","status":"success","geometry_version":1,
     "hull_family":"MONOHULL","surface_count":2,
     "requested_dimensions":{"loa":20.0,"beam":5.5,"draft":1.2},
     "actual_dimensions":{"loa":19.96,"beam":5.48,"draft":1.19},
     "tolerances":{"loa":{...,"within_tolerance":true}, ...},
     "validation":{"valid_surfaces":true,"symmetry":true,"naked_edges":4},
     "curve_ids":[...], "surface_ids":["port-1","stbd-1"],
     "sheer_line_id":"sheer","bow_termination_id":"bow","stern_termination_id":"stern",
     "bounding_box":{...},"warnings":[...],"file_reference":"rhino://hull.3dm"}

## Tests (all required cases)

test_hull_inspect.py (unit): tolerance error %, success when within tolerance +
symmetric + valid, dimension-tolerance failure, symmetry failure, invalid surface
failure, fairness warning always present.

test_hull_api.py (API, mocked Rhino): standard valid hull; small (×0.5) and large
(×2.5) hulls; dimension tolerance failure → status "failed"; symmetry failure →
status "failed"; station-generation failure → 502; invalid geometry response →
502; malformed geometry → 502; loft operation failure (empty surfaces) → 502;
Rhino unavailable → 503; Rhino timeout → 503; invalid input rejected before Rhino
(no Rhino calls); unsupported hull family → 422; 20 m acceptance test.

## Actual execution evidence

| Slice | Observed RED | Subsequent GREEN |
|---|---|---|
| Hull service + endpoint | import error: app.services.vessel.hull missing | hull files passed |
| Malformed measurements | 1 failed: missing-key dict treated as zero dims | full suite 168 passed, 1 skipped |

    .venv-mvp/bin/python -m pytest -c backend/pytest.ini backend/tests
    168 passed, 1 skipped in 35.39s

    .venv-mvp/bin/python docs/rhino-mvp/smoke.py    # SMOKE_EXIT=0
      unconfigured           : ... /api/vessel/hull 503 RHINO_NOT_CONFIGURED
      configured_unreachable : ... /api/vessel/hull 503 RHINO_UNAVAILABLE

    .venv-mvp/bin/python -m pip check -> No broken requirements found.
    Legacy: 40 pre-existing backend/app + frontend files SHA-256 unchanged. No Git used.

## FILES CREATED

- backend/app/services/vessel/hull.py
- backend/tests/test_hull_inspect.py
- backend/tests/test_hull_api.py
- docs/rhino-mvp/SECTION_6.md (this file)

## FILES MODIFIED

- backend/app/api/vessel.py      (POST /api/vessel/hull; shared validation helper)
- backend/tests/test_isolation.py (public surface += /api/vessel/hull)
- docs/rhino-mvp/smoke.py        (live hull probe)

## ENDPOINTS CREATED

- POST /api/vessel/hull

## RHINO OPERATIONS USED

- `execute_grasshopper("marlin_station_curves", station_inputs)` → station curves.
- `execute_grasshopper("marlin_hull_loft", {station_curve_ids, mirror:true, join:true, dims})`
  → port/starboard NURBS surfaces + sheer/bow/stern terminations + measurements.
- Both go through `RhinoComputeClient.run_grasshopper` → `POST {URL}/grasshopper`.

## TESTS RUN / PASSED / FAILED

- 169 collected: **168 passed, 1 skipped** (live-Rhino integration; no node), 0 failed.

## REAL RHINO RESULT

- Not run — no live Rhino.Compute node available. Reported honestly; no hull
  geometry fabricated. Provision a node + set RHINO_COMPUTE_URL to create the
  actual NURBS hull.

## KNOWN ISSUES

- No live Rhino node → real NURBS hull creation unverified in this environment.
- `.3dm` is returned as a `file_reference` when Rhino supplies one; no local
  .3dm is written without the node.

## GEOMETRY LIMITATIONS

- MONOHULL only; single-section-shape station curves (no chine/flare/tumblehome).
- Loft/mirror/join are Rhino-side operations; fairness is not assessed.
- Prototype tolerances (1%/1%/2%) — not production naval-architecture tolerances.
- No hydrostatics/stability/CFD/structural/Orca3D (later sections).

## Definition of done

- /api/vessel/hull exists ✓
- reuses Sections 4–5 data/logic ✓
- Rhino.Compute creates the hull — **pipeline built & verified against a
  Rhino-shaped stub; NOT verified against a real node (none available)** ⚠
- geometry inspected + dimension errors reported, bad results return a failed
  state (never hidden) ✓
- unit/integration/error tests pass ✓
- output reusable downstream (curve_ids, surface_ids, boundaries, bbox) ✓

## STOP

Section 6 complete. STOPPING. No hydrostatics, stability, CFD, Orca3D or
structural work begun. No further sections started.
