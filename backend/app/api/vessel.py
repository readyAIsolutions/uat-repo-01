"""Vessel endpoints (Sections 4–6).

Section 4: POST /api/vessel/validate  — validate + normalize parameters.
Section 5: POST /api/vessel/stations  — parameters -> Rhino -> station curves.
Section 6: POST /api/vessel/hull      — station curves -> Rhino -> NURBS hull.

Validation runs BEFORE any Rhino call. Rhino availability failures surface
honestly (503/502); geometry-quality failures return status "failed" (200) and
are never hidden.
"""
from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from pydantic import ValidationError

from ..services.rhino.contract import RhinoService
from ..services.rhino.dependencies import get_rhino_service
from ..services.vessel.hull import generate_hull


def _storage_dir(request) -> str:
    settings = getattr(request.app.state, "settings", None)
    return getattr(settings, "marlin_storage_dir", "storage")
from ..services.vessel.models import VesselGeometryParameters
from ..services.vessel.stations import (
    DEFAULT_STATION_COUNT,
    STATION_COUNT_MAX,
    STATION_COUNT_MIN,
    SUPPORTED_HULL_FAMILIES,
    generate_stations,
)
from ..services.vessel.validation import (
    Issue,
    VesselValidationError,
    issues_from_validation_error,
    normalize_vessel,
    validate_vessel,
)

router = APIRouter(prefix="/api/vessel", tags=["vessel"])


def _parse(payload: Any) -> VesselGeometryParameters:
    if not isinstance(payload, dict):
        raise VesselValidationError([Issue("body", "INVALID_VALUE",
                                           "Request body must be a JSON object")])
    try:
        return VesselGeometryParameters.model_validate(payload)
    except ValidationError as error:
        raise VesselValidationError(issues_from_validation_error(error)) from None


def _station_count(payload: dict) -> int:
    value = payload.get("station_count", DEFAULT_STATION_COUNT)
    if isinstance(value, bool) or not isinstance(value, int):
        raise VesselValidationError([Issue("station_count", "INVALID_VALUE",
                                           "station_count must be an integer")])
    if not (STATION_COUNT_MIN <= value <= STATION_COUNT_MAX):
        raise VesselValidationError([Issue(
            "station_count", "OUT_OF_RANGE",
            f"station_count must be between {STATION_COUNT_MIN} and {STATION_COUNT_MAX}")])
    return value


def _validated(payload: Any):
    count = _station_count(payload)
    params = _parse(payload)
    issues = list(validate_vessel(params))
    if params.hull_family.value not in SUPPORTED_HULL_FAMILIES:
        issues.append(Issue("hull_family", "UNSUPPORTED_HULL_FAMILY",
                            "Only MONOHULL is supported"))
    if issues:
        raise VesselValidationError(issues)  # reject before calling Rhino
    return params, count


@router.post("/validate")
async def validate(payload: Any = Body(...)) -> dict:
    params = _parse(payload)
    issues = validate_vessel(params)
    if issues:
        raise VesselValidationError(issues)
    return normalize_vessel(params)


@router.post("/stations")
async def stations(payload: Any = Body(...),
                   rhino: RhinoService = Depends(get_rhino_service)) -> dict:
    params, count = _validated(payload)
    return await generate_stations(params, count, rhino)


@router.post("/hull")
async def hull(payload: Any = Body(...),
               rhino: RhinoService = Depends(get_rhino_service),
               request: Request = None) -> dict:
    params, count = _validated(payload)
    return await generate_hull(params, count, rhino, _storage_dir(request))


@router.get("/hull/3dm/{name}", include_in_schema=True)
async def download_3dm(name: str, request: Request):
    """Serve a MARLIN-authored .3dm. Path-traversal safe; .3dm only."""
    import pathlib

    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    base = pathlib.Path(_storage_dir(request)).resolve()
    target = (base / name).resolve()
    if base != target.parent and base not in target.parents:
        raise HTTPException(status_code=404, detail="not found")
    if target.suffix != ".3dm" or not target.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(target, media_type="application/octet-stream", filename=name)
