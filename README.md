# MARLIN — Rhino Compute MVP (9 modules)

Working MARLIN Rhino MVP: a Python/FastAPI service that takes validated vessel
geometry and produces parametric NURBS hull geometry by driving a licensed
**Rhino.Compute** node (real Rhino 8 running on Windows) plus real `.3dm` export
via `rhino3dm`. Contains **only** the 9 Rhino modules — the legacy full-stack
app (`app/main.py`, Next.js frontend, SQL/email/compliance stack) is deliberately
excluded.

## The 9 modules (docs/rhino-mvp/SECTION_*.md)

1. **Section 1** — isolated MVP core (app factory, config, logging, Rhino contract)
2. **Section 2** — Rhino.Compute service layer + adapter selection
3. **Section 3 / 3A** — transport client & resilience (retry/backoff/error gates)
4. **Section 4** — vessel geometry parameter system (validated inputs)
5. **Section 5** — parametric station-curve generator (math)
6. **Section 6** — first parametric NURBS hull via Rhino.Compute
7. **Section 7** — minimum working UI (same-origin static screen)
8. **Section 8** — full integration test + hardening (live-Green suite)
9. **Section 9** — real Rhino.Compute correction gate + real `.3dm` (rhino3dm)

## Layout

```
backend/
  app/
    mvp.py          # entrypoint: uvicorn "app.mvp:create_app" --factory (port 8011)
    core/           # config + safe-request middleware
    services/rhino/ # Rhino.Compute adapter (unconfigured/configured/client)
    services/vessel/# geometry models, validation, stations, hull, .3dm export
    api/            # /api/rhino/* and /api/vessel/* routers
    ui/             # Section 7 static UI (index.html, three.js)
  tests/            # 187 passed / 6 skipped (live-Rhino skipped, no node)
  requirements-mvp-dev.txt
rhino/marlin_hull.py  # server-side Grasshopper "definition pointer" helper
docs/rhino-mvp/       # per-section build docs + smoke.py + stub_rhino.py
Dockerfile / docker-compose.yml / *.bat  # build & one-click Windows run
```

## Run it (Linux/dev — no live Rhino needed)

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-mvp-dev.txt
uvicorn "app.mvp:create_app" --factory --host 0.0.0.0 --port 8011
```

With no `RHINO_COMPUTE_URL` set, the app boots on the **unconfigured** adapter
(no network I/O) and serves full geometry validation + the UI:
`http://localhost:8011/` (UI), `/health`, `/api/vessel/*`, `/api/rhino/status`.

## Point it at the real Rhino.Compute node (Dell/Windows)

Set `RHINO_COMPUTE_URL` to the node's LAN address (e.g. `http://192.168.1.50:6500`)
— **not** `localhost` from a different machine. The adapter then turns validated
vessel params into station curves → NURBS hull on the node → real `.3dm`.

## Tests

```bash
cd backend && . .venv/bin/activate && python -m pytest
# 187 passed, 6 skipped  (skips = "no live Rhino.Compute node configured")
```

The 6 skipped tests only run when a real, licensed Rhino.Compute node is
reachable — they never fake geometry.