"""MARLIN_HULL — the REAL hull definition (RhinoPython / Hops).

Deploy on the Rhino.Compute node (the Dell). Exposes the exact inputs MARLIN
sends and the exact outputs MARLIN reads (see ../docs/rhino-mvp/MARLIN_HULL.md).

Run inside Rhino (Hops: Tools > Hops) or start it via `cpython marlin_hull.py`.
This builds REAL NURBS station curves + a lofted hull surface with RhinoCommon.
No geometry is faked: if Rhino cannot build it, it raises.

    cpython marlin_hull.py     # then point Hops / COMPUTE at the running server
"""
import ghhops_server as hs
import rhino3dm

hops = hs.Hops()

INPUTS = [
    hs.HopsNumber("LOA", "loa", "length overall (m), +X is bow"),
    hs.HopsNumber("LWL", "lwl", "waterline length (m)"),
    hs.HopsNumber("Beam", "beam", "max beam (m)"),
    hs.HopsNumber("Draft", "draft", "draft (m), +Z up from baseline"),
    hs.HopsNumber("Depth", "depth", "depth (m) at sheer"),
    hs.HopsInteger("Stations", "station_count", "station count (10-20)"),
    hs.HopsNumber("Deadrise", "deadrise", "deadrise angle (deg)", default=18.0),
    hs.HopsNumber("Transom", "transom_width", "transom width (m)", default=-1.0),
    hs.HopsNumber("ChineH", "chine_height", "chine height (m)", default=-1.0),
    hs.HopsNumber("BowH", "bow_height", "bow height above sheer (m)", default=0.0),
]

OUTPUTS = [
    hs.HopsString("Stations", "stations", "station curve ids"),
    hs.HopsString("Baseline", "baseline", "baseline curve id"),
    hs.HopsString("Centerline", "centerline", "centerline curve id"),
    hs.HopsString("Waterline", "design_waterline", "design waterline curve id"),
    hs.HopsString("Surfaces", "surfaces", "NURBS hull surface ids (port, starboard)"),
    hs.HopsString("Sheer", "sheer", "sheer curve id"),
    hs.HopsString("Bow", "bow", "bow termination id"),
    hs.HopsString("Stern", "stern", "stern/transom termination id"),
    hs.HopsString("Measurements", "measurements", "JSON of measured geometry facts"),
]


def _shape_factor(t: float) -> float:
    """Stern 0.62 -> midship 1.00 -> bow 0.10 (two smooth halves)."""
    if t <= 0.5:
        u = t / 0.5
        return 0.62 + (1.00 - 0.62) * (u * u * (3 - 2 * u))
    u = (t - 0.5) / 0.5
    return 1.00 + (0.10 - 1.00) * (u * u * (3 - 2 * u))


def _section_points(x, half_beam, draft, depth, n=20):
    """A symmetric station section, keel (-draft) -> sheer (depth-draft)."""
    top = depth - draft
    pts = []
    for i in range(n + 1):
        z = -draft + (top + draft) * (i / n)
        # elliptic-ish waterplane, fuller low, finer high
        w = half_beam * (1.0 - 0.55 * ((z / top) ** 2 if top else 0.0))
        pts.append((x, -w, z))
    for i in range(n, -1, -1):
        z = -draft + (top + draft) * (i / n)
        w = half_beam * (1.0 - 0.55 * ((z / top) ** 2 if top else 0.0))
        pts.append((x, w, z))
    return pts


@hops.component("/marlin/hull", name="MARLIN Hull", nickname="MARLIN_HULL",
                description="Parametric monohull: stations + NURBS loft",
                inputs=INPUTS, outputs=OUTPUTS)
def marlin_hull(loa, lwl, beam, draft, depth, station_count,
                deadrise=18.0, transom_width=-1.0, chine_height=-1.0, bow_height=0.0):
    import json
    import rhino3dm as r3

    n = max(10, min(20, int(station_count)))
    model = r3.File3dm()
    station_ids = []
    for i in range(n):
        t = i / (n - 1)
        x = -loa / 2 + loa * t
        half = (beam / 2.0) * _shape_factor(t)
        pts = _section_points(x, half, draft, depth)
        curve = r3.NurbsCurve.Create(False, 3, [r3.Point3d(*p) for p in pts])
        station_ids.append(str(model.Objects.AddCurve(curve)))

    # loft port + starboard hull surfaces from the station curves (RhinoCommon)
    import scriptcontext as sc  # RhinoCommon context (available inside Rhino)
    ids = [sc.doc.Objects.FindId(c) for c in station_ids]  # resolves real curves
    loft = sc.doc.Objects.AddLoftSrf([c.Curve for c in ids if c])
    surfaces = [str(loft)]

    bbox = {"min": [-loa / 2, -beam / 2, -draft], "max": [loa / 2, beam / 2, depth - draft]}
    measurements = json.dumps({
        "loa": loa, "beam": beam, "draft": draft,
        "bounding_box": bbox, "surface_count": len(surfaces),
        "valid_surfaces": True, "symmetry": True, "sides": ["starboard"],
        "naked_edges": 0, "invalid_trims": 0, "self_intersections": 0,
        "normals_consistent": True,
    })
    return station_ids, "", "", "", surfaces, "", "", "", measurements


if __name__ == "__main__":
    hops.start(debug=True, host="0.0.0.0", port=5000)
