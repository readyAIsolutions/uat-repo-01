"""Deterministic station-curve parameter math (Section 5).

Local math computes parameter values; the actual NURBS curves are created by
Rhino.Compute (via the injected RhinoService). This module never claims Rhino
geometry — it builds the plan sent to Rhino and the metadata used to verify the
returned result.
"""
from __future__ import annotations

import math

from .validation import measurement_meters

STERN_BEAM_RATIO = 0.62
BOW_BEAM_RATIO = 0.10
SECTION_SAMPLES = 11
SECTION_POWER = 0.6
STATION_COUNT_MIN = 10
STATION_COUNT_MAX = 20
DEFAULT_STATION_COUNT = 15
GEOMETRY_VERSION = 1
RHINO_STATION_DEFINITION = "marlin_station_curves"
SUPPORTED_HULL_FAMILIES = ("MONOHULL",)


def shape_factor(t: float) -> float:
    """Smooth beam distribution in [0,1]: 0 = stern, 0.5 = midship (widest), 1 = bow."""
    if t <= 0.5:
        u = t / 0.5
        return STERN_BEAM_RATIO + (1.0 - STERN_BEAM_RATIO) * math.sin(math.pi * u / 2)
    v = (t - 0.5) / 0.5
    return BOW_BEAM_RATIO + (1.0 - BOW_BEAM_RATIO) * math.cos(math.pi * v / 2)


def _section_points(x: float, half_beam: float, draft: float, depth: float) -> list:
    """Symmetric station section as 3D points [x, y, z] (port sheer -> keel -> starboard sheer)."""
    half = []
    for k in range(SECTION_SAMPLES):
        s = k / (SECTION_SAMPLES - 1)
        y = half_beam * (s ** SECTION_POWER)
        z = -draft + s * depth
        half.append((y, z))
    full = [(-y, z) for (y, z) in reversed(half)] + half[1:]
    return [[round(x, 6), round(y, 6), round(z, 6)] for (y, z) in full]


def build_station_plan(*, loa: float, beam: float, draft: float, depth: float,
                       station_count: int) -> dict:
    stations = []
    for i in range(station_count):
        t = i / (station_count - 1)
        local_beam = shape_factor(t) * beam
        stations.append({
            "index": i,
            "x": round(t * loa, 6),
            "local_beam": round(local_beam, 6),
            "shape_factor": round(shape_factor(t), 6),
            "points": _section_points(t * loa, local_beam / 2, draft, depth),
        })
    max_half = beam / 2
    bounding_box = {
        "min": [0.0, round(-max_half, 6), round(-draft, 6)],
        "max": [round(loa, 6), round(max_half, 6), round(depth - draft, 6)],
    }
    reference_curves = {
        "baseline": [[0.0, 0.0, round(-draft, 6)], [round(loa, 6), 0.0, round(-draft, 6)]],
        "centerline": [[0.0, 0.0, 0.0], [round(loa, 6), 0.0, 0.0]],
        "design_waterline": [[round(loa / 2, 6), round(-max_half, 6), 0.0],
                             [round(loa / 2, 6), round(max_half, 6), 0.0]],
    }
    return {"stations": stations, "bounding_box": bounding_box,
            "reference_curves": reference_curves}


def id_of(value) -> str | None:
    """Extract an object id from a normalized compute output value."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("id")
    return None


def vessel_inputs(params, station_count: int) -> dict:
    """Vessel parameters passed to a Rhino.Compute Grasshopper definition."""
    dims = {f: measurement_meters(getattr(params, f))
            for f in ("loa", "lwl", "beam", "draft", "depth")}
    inputs = {"loa": dims["loa"], "lwl": dims["lwl"], "beam": dims["beam"],
              "draft": dims["draft"], "depth": dims["depth"],
              "station_count": station_count, "model_units": "Meters"}
    for name, measurement in (("deadrise", params.deadrise), ("transom_width", params.transom_width),
                              ("chine_height", params.chine_height), ("bow_height", params.bow_height)):
        if measurement is not None:
            inputs[name] = measurement.value
    return inputs


async def generate_stations(params, station_count: int, rhino) -> dict:
    """Local parameter plan -> ONE self-contained Rhino.Compute solve -> station curves."""
    from ..rhino.errors import RhinoRequestError

    dims = {f: measurement_meters(getattr(params, f))
            for f in ("loa", "lwl", "beam", "draft", "depth")}
    plan = build_station_plan(loa=dims["loa"], beam=dims["beam"], draft=dims["draft"],
                              depth=dims["depth"], station_count=station_count)
    definition = getattr(rhino, "station_definition", RHINO_STATION_DEFINITION)
    outputs = await rhino.execute_grasshopper(definition, vessel_inputs(params, station_count))
    if not isinstance(outputs, dict) or not isinstance(outputs.get("stations"), list):
        raise RhinoRequestError(200, reason="malformed_response")
    curve_ids = [id_of(c) for c in outputs["stations"]]
    if not curve_ids or any(c is None for c in curve_ids):
        raise RhinoRequestError(200, reason="malformed_response")
    reference_curve_ids = {name: (id_of((outputs.get(name) or [None])[0]))
                           for name in ("baseline", "centerline", "design_waterline")}
    return {
        "project_id": params.project_id,
        "status": "success",
        "station_count": station_count,
        "geometry_version": GEOMETRY_VERSION,
        "hull_family": params.hull_family.value,
        "units": params.units,
        "loa": round(dims["loa"], 6), "lwl": round(dims["lwl"], 6),
        "beam": round(dims["beam"], 6), "draft": round(dims["draft"], 6),
        "depth": round(dims["depth"], 6),
        "rhino_compute_used": True,
        "stations": plan["stations"],
        "curve_ids": curve_ids,
        "reference_curve_ids": reference_curve_ids,
        "bounding_box": plan["bounding_box"],
        "warnings": [],
        "errors": [],
    }
