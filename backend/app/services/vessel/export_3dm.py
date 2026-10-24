"""Real .3dm output via rhino3dm, including Rhino.Compute-returned NURBS.

MARLIN writes a genuine .3dm. It contains:
  * the actual NURBS geometry returned by Rhino.Compute (decoded via
    rhino3dm.CommonObject.Decode), and
  * MARLIN's reference geometry (station curves, baseline, centerline,
    design waterline) preserved for context.

If Rhino.Compute returns no decodable geometry, the file still contains the
reference geometry and the caller reports ``nurbs_ingested=False`` honestly.
"""
from __future__ import annotations

import json
import os
import tempfile

import rhino3dm


def _polyline(points):
    pts = [rhino3dm.Point3d(float(x), float(y), float(z)) for x, y, z in points]
    return rhino3dm.PolylineCurve(pts)


def decode_geometry(payload):
    """Decode a Rhino.Compute-returned geometry object (geometry-resolver JSON)."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            return None
    if not isinstance(payload, (dict, list)):
        return None
    try:
        # rhino3dm.CommonObject.Decode expects the geometry dict, not a string.
        return rhino3dm.CommonObject.Decode(payload)
    except Exception:
        return None


def add_geometry(model, payload) -> bool:
    """Add a decoded Compute geometry object to the model. Returns True if added."""
    obj = decode_geometry(payload)
    if obj is None:
        return False
    if isinstance(obj, rhino3dm.Brep):
        model.Objects.AddBrep(obj)
    elif isinstance(obj, rhino3dm.NurbsSurface) or isinstance(obj, rhino3dm.Surface):
        model.Objects.AddSurface(obj)
    elif isinstance(obj, rhino3dm.NurbsCurve) or isinstance(obj, rhino3dm.Curve):
        model.Objects.AddCurve(obj)
    elif isinstance(obj, rhino3dm.Mesh):
        model.Objects.AddMesh(obj)
    elif isinstance(obj, rhino3dm.Point):
        model.Objects.AddPoint(obj)
    else:
        return False
    return True


def _fill_reference(model, plan):
    for station in plan.get("stations", []):
        points = station.get("points") or []
        if len(points) >= 2:
            model.Objects.AddCurve(_polyline(points))
    for key in ("baseline", "centerline", "design_waterline"):
        ref = (plan.get("reference_curves") or {}).get(key)
        points = ref.get("points") if isinstance(ref, dict) else (ref or [])
        if points and len(points) >= 2:
            model.Objects.AddCurve(_polyline(points))


def _write_bytes(model) -> bytes:
    handle, path = tempfile.mkstemp(suffix=".3dm")
    os.close(handle)
    try:
        model.Write(path, 8)
        with open(path, "rb") as handle:
            return handle.read()
    finally:
        os.unlink(path)


def build_stations_3dm(plan: dict, *, model_units: str = "Meters") -> bytes:
    """Reference-only .3dm (station/reference curves) — no Rhino geometry."""
    model = rhino3dm.File3dm()
    _fill_reference(model, plan)
    return _write_bytes(model)


def build_hull_3dm(plan: dict, raw_geometry=None, *, model_units: str = "Meters"):
    """Build a .3dm with Rhino.Compute-returned NURBS + reference geometry.

    Returns ``(bytes, ingested_count)``. ``ingested_count`` is the number of
    Rhino.Compute geometry objects actually decoded and written.
    """
    model = rhino3dm.File3dm()
    ingested = 0
    for payload in (raw_geometry or []):
        if add_geometry(model, payload):
            ingested += 1
    _fill_reference(model, plan)
    return _write_bytes(model), ingested
