# Section 9 — addendum (real .3dm, deployment, one-click Windows)

## Real .3dm (rhino3dm)  — DONE
- `app/services/vessel/export_3dm.py` builds a genuine `.3dm` with rhino3dm
  (station polylines + reference curves), written to `MARLIN_STORAGE_DIR`.
- The hull endpoint returns `file_reference = /api/vessel/hull/3dm/<name>` and
  `geometry_source = marlin_parameters`; `file_reference` is NEVER a fake value.
- `GET /api/vessel/hull/3dm/{name}` serves it (octet-stream, `.3dm` only,
  path-traversal safe).
- Honest scope: this `.3dm` is MARLIN's parameter station geometry. The
  AUTHORITATIVE NURBS hull is what Rhino.Compute returns; ingesting that geometry
  into the `.3dm` is the remaining step (needs the live node).

## Real definition (MARLIN_HULL)
- `rhino/marlin_hull.py` — real RhinoPython/Hops definition: builds NURBS station
  curves + a lofted hull via RhinoCommon. No fake geometry; raises if Rhino can't build.
- `docs/rhino-mvp/MARLIN_HULL.md` — the exact input/output contract MARLIN uses.
- Configurable pointers: `RHINO_STATION_DEFINITION`, `RHINO_HULL_DEFINITION`,
  `RHINO_BOX_DEFINITION`.

## Deployment (Dell = all-in-one workstation)
- `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example` (Rhino URL is
  configurable — `host.docker.internal:6500` in-compose, or the Dell's LAN address
  from the Linux dev box; never assume localhost).
- `MARLIN.bat` + `docs/DEPLOY_WINDOWS.md` — the one-click desktop "MARLIN" icon:
  starts Docker Desktop, `docker compose up -d`, waits for the health check, opens
  `http://localhost:8011/`. No terminals in normal use.
- Rhino 8 + Rhino.Compute stay INSTALLED on Windows; MARLIN runs in Docker.

## Tests
186 passed, 6 skipped (6 live-Rhino, incl. the new live `.3dm` test). smoke OK;
`pip check` clean; legacy 40/40 unchanged.

## The gate (must run on/against the Dell)
`RHINO_COMPUTE_URL=http://<dell-lan>:6500 .venv-mvp/bin/python -m pytest \
   -c backend/pytest.ini backend/tests/test_live_rhino.py -v`
This has NOT been run from the Linux box (no route to the Dell). It cannot pass
until executed where the real node is reachable.
