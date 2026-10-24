# MARLIN Section 8 — Full Rhino MVP Integration Test & Hardening

Scope honoured: NO major new features. This section adds the integration test
layer and a hardening pass over Sections 1–7, and reports the final state.

## What Section 8 adds

### Full-chain integration test — backend/tests/test_integration_rhino_mvp.py
Drives the entire MVP chain through the ASGI app against a loopback Rhino-shaped
stub (NOT real Rhino): health → rhino status → validate → stations → hull →
dimensions/errors → failure handling.

- Case A (standard 20 m monohull): chain succeeds; 15 stations; hull status
  success; 2 surfaces; symmetry true; all dims within tolerance; actual LOA is
  measured (≠ 20.0), not echoed.
- Case B (smaller vessel, ×0.5): geometry scales from the inputs
  (actual LOA ≈ 10 m) — proves no hard-coded dimensions.
- Case C (deliberately invalid: LWL>LOA and depth≤draft): rejected with 422
  before Rhino; **zero** Rhino calls (server.records == []).
- Rhino offline (127.0.0.1:1): status reachable=false; stations/hull → 503
  RHINO_UNAVAILABLE.
- Rhino unconfigured: status configured=false; hull → 503.
- Timeout → 503; malformed/empty loft geometry → 502. Fails gracefully, no crash.

### Live Rhino.Compute integration tests — backend/tests/test_live_rhino.py
Four tests (status connected, box, station curves, NURBS hull) that run ONLY when
`RHINO_COMPUTE_URL` is configured; they SKIP otherwise and are NOT counted as
passed. Provisioning a node immediately yields real, verified Rhino geometry.

### UI state contract test — backend/tests/test_ui.py::test_ui_declares_required_states
Asserts the UI declares the required states (NOT_STARTED/VALIDATING/VALID/INVALID/
GENERATING/SUCCESS/FAILED; Rhino CHECKING/CONNECTED/DISCONNECTED/ERROR), gates
generation on validation, and starts generate buttons disabled.

### Hardening / code review pass (findings)
- Reviewed for duplicated logic, dead code, hard-coded values/URLs/credentials,
  bare `except:`, stray `print()` in app code, missing timeouts, weak exception
  handling, mock leakage into production mode.
- Results: no duplicate top-level defs; no bare excepts; no `print()` in app;
  no hard-coded secrets (scan clean). All Rhino HTTP goes through timeouts and
  bounded retries. Mocks live only under tests/ (tests/fakes, tests/stubs) and
  docs/rhino-mvp/stub_rhino.py — never in the app runtime.
- One defect found and fixed during the pass: the integration stub responder
  crashed on an empty-bodied GET `/rhino/` connectivity probe → guarded.
- Note: TODO/FIXME markers exist only inside the vendored three.module.js
  (third-party) — not project code.

## Final test run

    .venv-mvp/bin/python -m pytest -c backend/pytest.ini backend/tests
    182 passed, 5 skipped, 0 failed in 38.80s

Skipped (all real-Rhino; NOT counted as passed):
- test_live_rhino.py::test_live_status_connected / test_live_box /
  test_live_station_curves / test_live_nurbs_hull
- test_stations_acceptance.py::test_live_rhino_integration

No frontend (Node/Jest) test suite exists; the Section 7 UI is covered by
backend tests + a real browser run (Section 7 evidence).

    .venv-mvp/bin/python docs/rhino-mvp/smoke.py   -> SMOKE_EXIT=0
    Legacy: 40 pre-existing backend/app + frontend files SHA-256 unchanged. No Git.

## Required outputs

- Total automated tests: 187 collected (182 passed, 5 skipped, 0 failed).
- Real Rhino tests run / passed / failed: 0 / 0 / 0 (none run — no node).
- Rhino operations successfully verified (real): NONE.
- Geometry successfully produced (real): NO.
- NURBS hull verified: NO.
- .3dm output verified: NO.
- Browser workflow verified: YES (against the stub; Section 7).
- Mock-only functionality: all Rhino HTTP round-trips, box, station curves,
  hull loft + measured surfaces/dimensions.
- Remaining bugs: none known in mocked paths.
- Remaining blockers: no licensed Rhino.Compute node reachable (external).
- Security concerns: none found (no secrets exposed; key redacted).
- Technical debt: S2/S3 response-key divergence from the newer briefs; no
  frontend test harness; docs numbering anomaly (SECTION_3A_TRANSPORT_RESILIENCE).
- Recommended next phase: provision the Rhino node → run test_live_rhino.py →
  then OpenAI/vessel-manifest/concept-image integration.

## Cases A/B/C recorded

CASE | INPUT                                   | EXPECTED                | ACTUAL                                   | RESULT
A    | 20 / 18.5 / 5.5 / 1.2 / 2.4, MONOHULL,15| valid→stations→hull ok  | valid; 15 stations; success; dims in tol | PASS (stub)
B    | ×0.5 of A                               | valid; scaled geometry  | success; actual LOA ≈10 m (scaled)       | PASS (stub)
C    | 10 / 12 / 4 / 3 / 2                     | rejected pre-Rhino      | 422 (lwl & depth INVALID_RELATIONSHIP); 0 Rhino calls | PASS

## FINAL PASS CONDITION (honest)

The MVP chain (UI → dimensions → validation → backend → Rhino → stations → NURBS
hull → measure → UI) is BUILT and runs end-to-end against a stub. The single link
not yet real is **Rhino.Compute** — no node is available on this host. Therefore:

    MARLIN RHINO MVP: NOT PASSED as a real-Rhino system.
                       Fully working prototype, BLOCKED on a Rhino.Compute node.

## STOP

Section 8 complete. No further development begun.
