"""Parametric NURBS hull generation + inspection (Section 6).

MARLIN computes parameters locally; the hull surfaces are created by
Rhino.Compute. MARLIN then inspects the returned geometry honestly: it reports
measured dimensions, tolerance errors, symmetry and surface validity, and it
never claims a surface is "fair" just because Rhino created it.
"""
from __future__ import annotations

from ..rhino.errors import RhinoRequestError
from .stations import GEOMETRY_VERSION, generate_stations
from .validation import measurement_meters

HULL_LOFT_DEFINITION = "marlin_hull_loft"
TOLERANCES = {"loa": 1.0, "beam": 1.0, "draft": 2.0}  # prototype acceptance %
FAIRNESS_WARNING = "Surface fairness not assessed: Rhino creating a surface does not make it fair."


def _tolerance_check(requested: float, actual: float, percent: float) -> dict:
    error_percent = (abs(actual - requested) / requested * 100.0) if requested else 0.0
    return {
        "requested_m": round(requested, 6),
        "actual_m": round(actual, 6),
        "error_percent": round(error_percent, 4),
        "within_tolerance": error_percent <= percent,
    }


def _bbox_symmetric(bbox) -> bool:
    try:
        min_v, max_v = bbox["min"], bbox["max"]
        return abs(min_v[1] + max_v[1]) <= 1e-3 * max(1.0, abs(max_v[1]))
    except (KeyError, TypeError, IndexError):
        return False


def inspect_hull(params, station_count, station_result, loft) -> dict:
    if (not isinstance(loft, dict) or not isinstance(loft.get("surfaces"), list)
            or not loft["surfaces"]):
        raise RhinoRequestError(200, reason="loft_failed")
    measurements = loft.get("measurements")
    if not isinstance(measurements, dict):
        raise RhinoRequestError(200, reason="malformed_response")

    dims = {f: measurement_meters(getattr(params, f))
            for f in ("loa", "beam", "draft")}
    surfaces = [s for s in loft["surfaces"] if isinstance(s, dict)]
    required = ("loa", "beam", "draft")
    if not all(key in measurements for key in required):
        raise RhinoRequestError(200, reason="malformed_response")
    try:
        actual = {k: float(measurements[k]) for k in required}
        naked_edges = int(measurements.get("naked_edges", 0))
    except (TypeError, ValueError):
        raise RhinoRequestError(200, reason="malformed_response") from None

    tolerances = {k: _tolerance_check(dims[k], actual[k], TOLERANCES[k])
                  for k in ("loa", "beam", "draft")}
    within = all(t["within_tolerance"] for t in tolerances.values())
    sides = {s.get("side") for s in surfaces}
    valid_surfaces = all(bool(s.get("valid")) for s in surfaces)
    bbox = measurements.get("bounding_box") or {}
    symmetry = _bbox_symmetric(bbox) and {"port", "starboard"} <= sides

    warnings = [FAIRNESS_WARNING]
    if naked_edges:
        warnings.append(f"{naked_edges} naked edge(s) reported by Rhino")
    if measurements.get("invalid_trims"):
        warnings.append("Invalid trims reported by Rhino")
    if measurements.get("self_intersections"):
        warnings.append("Self-intersections reported by Rhino")
    if not valid_surfaces:
        warnings.append("One or more surfaces reported invalid by Rhino")
    if not symmetry:
        warnings.append("Port/starboard symmetry check failed")
    for key, check in tolerances.items():
        if not check["within_tolerance"]:
            warnings.append(f"{key.upper()} outside tolerance: "
                            f"{check['error_percent']}% > {TOLERANCES[key]}%")

    status = "success" if (valid_surfaces and symmetry and within) else "failed"
    return {
        "project_id": params.project_id,
        "status": status,
        "geometry_version": GEOMETRY_VERSION,
        "hull_family": params.hull_family.value,
        "units": params.units,
        "station_count": station_count,
        "surface_count": len(surfaces),
        "requested_dimensions": {k: round(dims[k], 6) for k in ("loa", "beam", "draft")},
        "actual_dimensions": {k: round(actual[k], 6) for k in ("loa", "beam", "draft")},
        "tolerances": tolerances,
        "validation": {"valid_surfaces": valid_surfaces, "symmetry": symmetry,
                       "naked_edges": naked_edges},
        "curve_ids": station_result["curve_ids"],
        "surface_ids": [s.get("id") for s in surfaces],
        "sheer_line_id": (loft.get("sheer_line") or {}).get("id"),
        "bow_termination_id": (loft.get("bow_termination") or {}).get("id"),
        "stern_termination_id": (loft.get("stern_termination") or {}).get("id"),
        "bounding_box": bbox,
        "rhino_compute_used": True,
        "warnings": warnings,
        "errors": [],
        "file_reference": loft.get("file_reference"),
    }


async def generate_hull(params, station_count: int, rhino, storage_dir: str | None = None) -> dict:
    """ONE self-contained Rhino.Compute solve -> NURBS hull -> honest inspection.

    No cross-request geometry IDs: the hull definition builds its own stations and
    returns the surfaces + measurements directly (Rhino.Compute is stateless).
    """
    import json as _json

    from ..rhino.errors import RhinoRequestError
    from .stations import id_of, vessel_inputs

    definition = getattr(rhino, "hull_definition", HULL_LOFT_DEFINITION)
    outputs = await rhino.execute_grasshopper(definition, vessel_inputs(params, station_count))
    if not isinstance(outputs, dict):
        raise RhinoRequestError(200, reason="malformed_response")
    surfaces_out = outputs.get("surfaces")
    if not isinstance(surfaces_out, list) or not surfaces_out:
        raise RhinoRequestError(200, reason="loft_failed")
    meas_raw = (outputs.get("measurements") or [None])[0]
    if isinstance(meas_raw, str):
        try:
            measurements = _json.loads(meas_raw)
        except ValueError:
            raise RhinoRequestError(200, reason="malformed_response") from None
    elif isinstance(meas_raw, dict):
        measurements = meas_raw
    else:
        raise RhinoRequestError(200, reason="malformed_response")
    count = max(len(surfaces_out), int(measurements.get("surface_count", 0) or 0))
    valid = bool(measurements.get("valid_surfaces", True))
    sides = measurements.get("sides") or ["port", "starboard"]
    surfaces = [{"id": id_of(surfaces_out[i]) or f"surface-{i}",
                 "side": sides[i] if i < len(sides) else f"side-{i}", "valid": valid}
                for i in range(count)]
    loft = {
        "surfaces": surfaces,
        "measurements": measurements,
        "sheer_line": {"id": id_of((outputs.get("sheer") or [None])[0])},
        "bow_termination": {"id": id_of((outputs.get("bow") or [None])[0])},
        "stern_termination": {"id": id_of((outputs.get("stern") or [None])[0])},
        "file_reference": None,
    }
    station_result = {"curve_ids": outputs.get("stations") or []}
    result = inspect_hull(params, station_count, station_result, loft)
    _write_3dm(params, station_count, result, storage_dir, raw_geometry=surfaces_out)
    return result


def _write_3dm(params, station_count: int, result: dict, storage_dir: str | None,
               raw_geometry=None) -> None:
    """Write a real .3dm: Rhino.Compute NURBS (if returned) + reference geometry."""
    import pathlib
    import re
    import uuid

    from .export_3dm import build_hull_3dm
    from .stations import build_station_plan

    dims = {f: measurement_meters(getattr(params, f)) for f in ("loa", "beam", "draft", "depth")}
    plan = build_station_plan(loa=dims["loa"], beam=dims["beam"], draft=dims["draft"],
                              depth=dims["depth"], station_count=station_count)
    data, ingested = build_hull_3dm(plan, raw_geometry)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(params.project_id))[:40] or "hull"
    name = f"{safe}-v{result['geometry_version']}-{uuid.uuid4().hex[:8]}.3dm"
    if storage_dir:
        directory = pathlib.Path(storage_dir)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_bytes(data)
    result["file_reference"] = f"/api/vessel/hull/3dm/{name}"
    result["file_bytes"] = len(data)
    # honest: did we actually ingest Rhino.Compute NURBS geometry?
    result["geometry_source"] = "rhino_compute_nurbs" if ingested else "marlin_parameters"
    result["nurbs_ingested"] = ingested > 0
    result["nurbs_ingested_count"] = ingested
