# MARLIN Section 4 — Vessel Geometry Parameter System

Built exactly to the operator's Section 4 brief. This section creates the
structured, traceable input layer every later Rhino operation depends on. It
generates NO hull and calls NO Rhino.Compute.

## What was built

Strongly typed model `VesselGeometryParameters` (backend/app/services/vessel/models.py):

- project_id, units, hull_family
- Required dimensions: LOA, LWL, beam, draft, depth
- Optional dimensions: deadrise, transom_width, chine_height, bow_height

Every dimension is a `Measurement` carrying full traceability:
`value`, `unit`, `source` (enum), `locked`.

Allowed sources (`SourceType`): USER_SPECIFIED, AI_ESTIMATED, CALCULATED,
ENGINEER_VALIDATED. Hull family (`HullFamily`): MONOHULL, CATAMARAN, TRIMARAN,
PONTOON.

Units: length tokens m/meter(s)/metre(s), cm/centimeter(s), mm/millimeter(s),
ft/foot/feet, in/inch(es) — plus deg/degree(s) for deadrise. Aliases normalize
to canonical (m, cm, mm, ft, in, deg). Unsupported units are reported, never fixed.

## Validation (never silently "fixes" a number)

- LOA > 0; LWL > 0; Beam > 0; Draft > 0
- LWL <= LOA (compared in metres, so mixed units are handled correctly)
- Depth > Draft (compared in metres)
- Deadrise within 0–90 degrees (when supplied)
- vessel `units` and every measurement `unit` must be supported
- Missing required fields and malformed numerics are reported clearly
- Optional dimensions have their units validated only (no invented magnitude rule)

Error shape (HTTP 422), value-free:

    {"error": {"code": "VESSEL_VALIDATION_FAILED",
               "message": "Vessel geometry validation failed",
               "details": [{"field": "lwl", "code": "INVALID_RELATIONSHIP",
                            "message": "LWL must be less than or equal to LOA"}]},
     "request_id": "<server-owned id>"}

Codes: MISSING, NOT_A_NUMBER, OUT_OF_RANGE, INVALID_RELATIONSHIP,
UNSUPPORTED_UNIT, INVALID_VALUE. Messages never echo supplied values.

## API

`POST /api/vessel/validate`

1. Receives vessel geometry parameters.
2. Validates them.
3. Returns normalized structured data when valid (HTTP 200).
4. Returns clear validation errors when invalid (HTTP 422).
5. Does NOT call Rhino.Compute.

Success response (normalized to the vessel's display unit, plus SI metres):

    {"valid": true, "project_id": "MARLIN-001", "units": "m", "hull_family": "MONOHULL",
     "parameters": {"loa": {"value": 20.0, "unit": "m", "source": "USER_SPECIFIED",
                            "locked": true}, ...},
     "base_meters": {"loa": 20.0, "lwl": 18.5, "beam": 5.5, "draft": 1.2, "depth": 2.4}}

The body is parsed manually into the typed model so field-level and relational
failures share one clear, value-free error shape.

## Tests (brief's required cases, all present)

backend/tests/test_vessel_api.py:
- valid vessel (normalized output)            - unsupported units
- missing LOA                                 - unsupported measurement unit
- negative beam                               - malformed numeric input
- zero draft                                  - missing source
- LWL greater than LOA                        - invalid hull family
- depth less than draft                       - correlated errors, values not echoed
- validate makes NO Rhino call (stub records empty)

backend/tests/test_vessel_validation.py:
- unit aliases normalize                      - deadrise range
- cross-unit LWL/LOA comparison in metres     - optional dimensions accepted
- normalize converts to display unit          - source/hull-family enums enforced

## Actual execution evidence

| Slice | Observed RED | Subsequent GREEN |
|---|---|---|
| Models + validation + endpoint | collection error: app.services.vessel missing; API tests 404 | 20 passed (vessel files) |
| Public surface | 1 failed: isolation pinned the old surface | full suite 126 |

Final observed results:

    .venv-mvp/bin/python -m pytest -c backend/pytest.ini backend/tests
    126 passed in 22.62s

    .venv-mvp/bin/python docs/rhino-mvp/smoke.py
    SMOKE_EXIT=0 — both scenarios:
      unconfigured            [200,200,200,200,200,404,200]
      configured_unreachable  [200,200,200,200,200,404,200]
      (…, …, …, /api/rhino/status, /api/rhino/capabilities, unknown 404, /api/vessel/validate 200)
    secret-free logs, clean shutdown

    .venv-mvp/bin/python -m pip check
    No broken requirements found.

Legacy preservation: the 40 pre-existing backend/app + frontend files recorded in
.mvp-legacy-baseline.json are all unchanged (SHA-256 match). No Git was used.

## Note on numbering

An earlier agent-defined increment between Sections 3 and 4 (transport resilience:
bounded retry/backoff + configurable timeout) is kept as
docs/rhino-mvp/SECTION_3A_TRANSPORT_RESILIENCE.md so this operator Section 4 is
authoritative. No legacy behaviour changed by it.

## Files

Added:
- backend/app/services/vessel/{__init__.py, models.py, validation.py}
- backend/app/api/vessel.py
- backend/tests/test_vessel_api.py
- backend/tests/test_vessel_validation.py
- docs/rhino-mvp/SECTION_4.md (this file)

Modified:
- backend/app/core/http.py   (VESSEL_VALIDATION_FAILED handler)
- backend/app/mvp.py         (register vessel router)
- backend/tests/test_isolation.py (public surface now includes /api/vessel/validate)
- docs/rhino-mvp/smoke.py    (POST probe for /api/vessel/validate)

## Definition of done — met

- typed vessel model exists ✓
- validation works ✓
- /api/vessel/validate works ✓
- invalid values return useful errors ✓
- tests run ✓
- all tests pass (126) ✓

## Stop boundary

Section 4 complete. Stopping before Section 5. No hull generation, no
Rhino.Compute call, no Grasshopper, no AI, no Orca3D/analysis/compliance/
manufacturing. Real Rhino remains NOT TESTED.
