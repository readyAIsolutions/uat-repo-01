# Module 9 — Final Acceptance Gate (Dell)

## .3dm now ingests the real Rhino.Compute NURBS — DONE (mock-verified)
`app/services/vessel/export_3dm.py`:
- `decode_geometry()` uses `rhino3dm.CommonObject.Decode(<geometry dict>)` on the
  geometry Rhino.Compute returns (geometry-resolver JSON).
- `build_hull_3dm(plan, raw_geometry)` adds the decoded NURBS/Brep/Mesh/Curve to
  the File3dm AND preserves reference geometry (stations/centerline/waterline).
- The hull response reports honestly:
  geometry_source = "rhino_compute_nurbs" | "marlin_parameters",
  nurbs_ingested = true|false, nurbs_ingested_count = N.
- Test `test_hull_3dm_ingest.py` encodes a REAL rhino3dm Brep the way Compute does,
  drives it through the API, and asserts the reopened .3dm CONTAINS the surfaces.

## Report fields (fill on the Dell)
NURBS surfaces returned by Rhino.Compute = ___
NURBS surfaces written into .3dm = ___
.3dm reopened successfully = ___
surface count in reopened file = ___
actual file path = ___

## Route actually used
RHINOPYTHON / HOPS  (`rhino/marlin_hull.py`).
There is NO compiled `MARLIN_HULL.gh` — do not assume one exists.
Remaining Windows step to make a .gh (if you want the pure-Grasshopper route):
 1. Open Grasshopper on the Dell, add the Hops component
    (Params > Util > Hops) pointing at `rhino/marlin_hull.py`'s server, OR
    rebuild the same inputs/outputs with native GH components.
 2. Wire inputs: loa,lwl,beam,draft,depth,station_count,deadrise,transom_width,
    chine_height,bow_height ; outputs: stations,baseline,centerline,
    design_waterline,surfaces,sheer,bow,stern,measurements.
 3. Save as `MARLIN_HULL.gh` and set `RHINO_HULL_DEFINITION` to its server-side path.

## Freeze checklist (MARLIN v0.1)
[x] ordinary automated tests pass (187 passed, 6 skipped)
[ ] real Dell Rhino.Compute test passes
[ ] real NURBS hull returned
[ ] real NURBS hull written into .3dm (code done; live unproven)
[ ] reopened .3dm verifies the hull (code done; live unproven)
[ ] Docker stack starts on Dell
[ ] MARLIN desktop launcher starts the app
[ ] UI opens; Rhino status connected
[ ] test hull generated from the running app
