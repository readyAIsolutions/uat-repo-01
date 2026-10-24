# MARLIN_HULL — definition I/O contract

MARLIN computes parameter VALUES; the Grasshopper/Rhino definition builds the
GEOMETRY. MARLIN sends a definition **pointer** (a `.gh` on the Compute node) or
**algo** (base64 `.gh`), plus `values`, and reads named outputs back.

## Inputs (MARLIN -> definition), one DataTree entry each
| name             | type  | notes                                   |
|------------------|-------|-----------------------------------------|
| loa              | float | metres                                  |
| lwl              | float | metres                                  |
| beam             | float | metres                                  |
| draft            | float | metres                                  |
| depth            | float | metres                                  |
| station_count    | int   | 10-20 (default 15)                      |
| deadrise         | float | deg (optional; MUST affect geometry)    |
| transom_width    | float | metres (optional; MUST affect geometry) |
| chine_height     | float | metres (optional; MUST affect geometry) |
| bow_height       | float | metres (optional; MUST affect geometry) |

## Outputs (definition -> MARLIN)
| name              | contents                                            |
|-------------------|-----------------------------------------------------|
| stations          | station curve ids (stern -> bow)                    |
| baseline/centerline/design_waterline | reference curve ids              |
| surfaces          | NURBS hull surface ids (port, starboard)            |
| sheer / bow / stern | termination ids                                   |
| measurements      | JSON string: loa,beam,draft,bounding_box,surface_count,valid_surfaces,symmetry,sides,naked_edges,invalid_trims,self_intersections,normals_consistent |

## One self-contained solve
The definition builds its own stations and returns surfaces + measurements in a
SINGLE solve. MARLIN never relies on geometry ids surviving between requests
(Rhino.Compute is stateless).

## Deploy on the Dell
1. Put `rhino/marlin_hull.py` where Rhino can run it (Hops).
2. `cpython marlin_hull.py` (or start via Hops), or wrap the logic in
   `MARLIN_HULL.gh` and set `RHINO_HULL_DEFINITION` to its server-side path.
3. Set `RHINO_COMPUTE_URL`/`MARLIN_RHINO_URL` and, if used, `RHINO_COMPUTE_API_KEY`.
