# MARLIN Rhino MVP — Section 3A: Transport Resilience (agent-defined interlude)

## Scope note (read first)

This was an agent-defined increment between Section 3 and the operator's Section 4
(no brief was supplied at the time). It is NOT the operator's Section 4 — the
operator's Section 4 is the Vessel Geometry Parameter System (see SECTION_4.md).
Nothing legacy changed; this is a pure transport hardening slice.

## What Section 4 is

Transport resilience for the Section 2 Rhino.Compute client — the piece real
Rhino nodes will need (nodes restart, warm up, and hiccup):

- Configurable request timeout: `RHINO_COMPUTE_TIMEOUT` (seconds, >0, ≤300, default 10).
- Bounded retries: `RHINO_COMPUTE_MAX_ATTEMPTS` (1–10, default 3).
- Optional exponential backoff: `RHINO_COMPUTE_BACKOFF_SECONDS` (0–60, default 0).

Retry policy (deterministic, documented):
- Retried: connection failures, timeouts, HTTP 5xx, HTTP 429.
- NOT retried: 4xx (except 429) and undecodable/invalid JSON — fail fast.
- Attempts are strictly bounded by `max_attempts`; the last failure is raised.
- The client's own default stays `max_attempts=1` (no retries) so direct-client
  unit tests are unchanged; the app factory wires the configured value (default 3).

## Honesty boundary (unchanged in spirit)

- Real Rhino: **NOT TESTED**. No licensed node, no Grasshopper definition, no
  Orca3D, no geometry, no AI, no analysis/compliance/manufacturing.
- Resilience is transport-only; it authors no geometry and invents no fallback.
- Backoff defaults to 0 so behaviour is deterministic and tests are fast; real
  deployments should set a non-zero value.

## Files added (relative to /home/nova/marlin-prod)

- backend/tests/test_transport_resilience.py
- backend/tests/test_settings_resilience.py
- docs/rhino-mvp/SECTION_4.md (this file)

Files modified:
- backend/app/core/config.py            (3 new bounded settings + allowed-name set)
- backend/app/services/rhino/client.py  (bounded retry loop, retryable-status rule, backoff)
- backend/app/mvp.py                    (factory passes timeout/attempts/backoff)
- backend/tests/conftest.py             (clear the new env vars between tests)
- backend/tests/stubs/rhino_stub.py     (tolerate client-side timeout disconnects)

## Actual execution evidence

Test-first vertical slices:

| Slice | Observed RED | Subsequent GREEN |
|---|---|---|
| Retry/backoff + timeout | client rejected `max_attempts`; 6 transport tests failed | transport tests passed |
| New settings | 8 failed: unknown settings/fields | full suite green |
| Factory wiring | (added after green; passed first run) | full suite 106 |

Final observed result:

    .venv-mvp/bin/python -m pytest -c backend/pytest.ini backend/tests
    106 passed in 21.41s

Warnings are errors; no warning summary in the final run.

Live Uvicorn smoke (real process, two scenarios, exit 0):

    unconfigured           : /health 200, /docs 200, /openapi.json 200, /api/rhino/status 200, /api/rhino/capabilities 200, unknown 404
    configured_unreachable : /health 200, /docs 200, /openapi.json 200, /api/rhino/status 200, /api/rhino/capabilities 200, unknown 404

    .venv-mvp/bin/python -m pip check
    No broken requirements found.

Legacy preservation: the 40 pre-existing backend/app + frontend files recorded in
.mvp-legacy-baseline.json are all unchanged (SHA-256 match). No Git was used.

## Stop boundary

Section 4 complete. No live Rhino was contacted or tested. No geometry authoring,
Grasshopper definition authoring, AI, Orca3D, analysis, compliance or
manufacturing was implemented. Subsequent sections remain unimplemented.
