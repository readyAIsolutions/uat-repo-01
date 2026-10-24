# MARLIN Section 7 — Minimum Working User Interface

Built to the operator's Section 7 brief. A single functional screen that drives
the whole prototype: user → MARLIN API → Rhino.Compute → hull geometry → result.
Function first; no OpenAI/image-gen/Orca3D/hydrostatics/stability/CFD/compliance/
manufacturing.

## What Section 7 is

A same-origin, lightweight UI served by the isolated MVP itself (no CORS, no
browser secrets, legacy frontend untouched):

- `GET /`        → the MARLIN screen (index.html)
- `GET /ui/*`    → app.js, styles.css, vendored Three.js (from the existing
                   frontend/node_modules — vendored, not modified)

### Inputs
Project Name, LOA, LWL, Beam, Draft, Depth, Hull Family (MONOHULL only),
Station Count (10–20, default 15).

### Buttons
CHECK RHINO · VALIDATE · GENERATE STATIONS · GENERATE HULL · VIEW MODEL · OPEN RESULT.

### Results/status area shows
Rhino connection, validation status, project ID, geometry version, station count,
hull status, requested vs actual dimensions with error % and within-tolerance,
warnings, errors, and the result/file reference.

### States
Validation: NOT_STARTED / VALIDATING / VALID / INVALID.
Hull: NOT_STARTED / GENERATING / SUCCESS / FAILED.
Rhino: CHECKING / CONNECTED / DISCONNECTED / ERROR.

### Guardrails
- Generative buttons are disabled until validation is VALID.
- All buttons disable while a job runs.
- Rhino offline shows "Rhino.Compute unavailable" (not a vague failure).
- API calls time out via AbortController → "API timeout".
- The browser never receives or sends the Rhino API key.

### 3D viewer
Three.js (vendored, same-origin) renders the station curves MARLIN computed as
green 3D lines, orbit/zoom via OrbitControls. It is explicitly labelled
"Preview only — the Rhino .3dm result is the CAD source of truth."

## Verified end-to-end in a real browser (screenshots taken)

Ran the MVP with a local Rhino-shaped stub (`docs/rhino-mvp/stub_rhino.py`, NOT
Rhino) and drove the actual UI:

1. Page loaded; Generate buttons disabled at rest.
2. CHECK RHINO → `CONNECTED`.
3. VALIDATE (MARLIN TEST 001, 20/18.5/5.5/1.2/2.4, MONOHULL, 15) → `VALID`;
   Generate buttons enabled.
4. GENERATE STATIONS → "15 created".
5. GENERATE HULL → Hull status `success`; dimensions table:
   LOA 20 → 19.96 (0.2%, within tol.), Beam 5.5 → 5.484 (0.2909%, within tol.),
   Draft 1.2 → 1.188 (1%, within tol.); warnings shown (fairness not assessed;
   4 naked edges); result reference `rhino://stub/hull.3dm`; 3D preview rendered
   the 15 station curves.
6. Guardrail: set LOA=0 → VALIDATE → `INVALID` with field-level messages
   ("loa: LOA must be greater than 0", "lwl: LWL must be less than or equal to
   LOA"); GENERATE STATIONS + GENERATE HULL disabled. No secrets in the DOM.
7. Rhino offline: stopped the stub → CHECK RHINO → `DISCONNECTED`; GENERATE HULL →
   `FAILED` with "Rhino.Compute unavailable".

Server logs for the run (secret-free): validate 200, stations 200, hull 200,
validate 422 (invalid input), hull 503 (offline).

## HONEST LIMITATION (unchanged)

There is no live Rhino.Compute node on this host. The browser workflow above was
run against a **local Rhino-shaped stub**, not Rhino. It proves the UI, API
wiring, guardrails, error handling and preview all work; the real NURBS hull still
requires a licensed node. No hull geometry was fabricated as Rhino output.

## API-level tests (pytest)

backend/tests/test_ui.py:
- page loads with every control present
- static assets served; app.js wires all four endpoints
- `/` and `/ui/*` are absent from the OpenAPI surface (exact surface pinned)
- no secrets reach the browser (HTML/JS/status all clean with the key set)
- AbortController timeout wiring + clear "Rhino.Compute unavailable" message
- backend validation error shape {field, code, message}
- Rhino-offline reported honestly via /api/rhino/status

(The brief's functional cases — valid/invalid input, generate stations/hull,
button disabling, Rhino offline, API timeout, dimension values, no secrets — are
covered here plus the browser run above.)

## Actual execution evidence

    .venv-mvp/bin/python -m pytest -c backend/pytest.ini backend/tests
    175 passed, 1 skipped in 36.31s      (was 168/1 after Section 6)

    .venv-mvp/bin/python docs/rhino-mvp/smoke.py   # SMOKE_EXIT=0
    .venv-mvp/bin/python -m pip check              # No broken requirements found.
    Legacy: 40 pre-existing backend/app + frontend files SHA-256 unchanged. No Git.

## Files (relative to /home/nova/marlin-prod)

Created:
- backend/app/ui/index.html
- backend/app/ui/app.js
- backend/app/ui/styles.css
- backend/app/ui/vendor/three.module.js   (vendored from frontend/node_modules)
- backend/app/ui/vendor/OrbitControls.js  (vendored)
- backend/tests/test_ui.py
- docs/rhino-mvp/stub_rhino.py            (local Rhino-shaped stub, test helper)
- docs/rhino-mvp/SECTION_7.md (this file)

Modified:
- backend/app/mvp.py  (serve `/` and mount `/ui`; kept out of the OpenAPI surface)

## Definition of done

- one MARLIN screen with the specified inputs/buttons ✓
- results/status area with all specified fields ✓
- clear states + guardrails (invalid → generate disabled; offline → clear msg) ✓
- basic Three.js viewer (preview, labelled non-authoritative) ✓
- full workflow runnable without a terminal ✓ (verified in a real browser)
- tests pass ✓
- no secrets in the browser ✓

## STOP

Section 7 complete. STOPPING. No further sections begun.
