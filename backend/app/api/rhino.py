"""Public MVP Rhino routes.

Honest by construction: these routes only call the injected RhinoService. They
author no geometry locally, contact no node at import/startup time, and report
unconfigured/unreachable states plainly. Real Rhino is NOT tested here.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..services.rhino.contract import RhinoNotConfiguredError, RhinoService
from ..services.rhino.dependencies import get_rhino_service

router = APIRouter(prefix="/api/rhino", tags=["rhino"])

MAX_DIMENSION_M = 10000.0


class StatusResponse(BaseModel):
    configured: bool
    reachable: bool
    status: str
    status_code: int | None = None


class BoxRequest(BaseModel):
    width: float = Field(gt=0, le=MAX_DIMENSION_M)
    length: float = Field(gt=0, le=MAX_DIMENSION_M)
    height: float = Field(gt=0, le=MAX_DIMENSION_M)


class CapabilitiesResponse(BaseModel):
    real_rhino_tested: bool
    operations: dict[str, str]
    note: str


@router.get("/status", response_model=StatusResponse, response_model_exclude_none=True)
async def status(service: RhinoService = Depends(get_rhino_service)) -> dict:
    try:
        return await service.health_check()
    except RhinoNotConfiguredError:
        return {"configured": False, "reachable": False, "status": "unconfigured"}


@router.post("/box")
async def box(body: BoxRequest, service: RhinoService = Depends(get_rhino_service)) -> dict:
    return await service.create_box(body.width, body.length, body.height)


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def capabilities() -> dict:
    return {
        "real_rhino_tested": False,
        "operations": {
            "health_check": "available",
            "create_box": "available",
            "execute_grasshopper": "available",
            "create_geometry": "reserved",
        },
        "note": "Operations require RHINO_COMPUTE_URL; no live Rhino node was tested.",
    }
