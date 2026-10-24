"""Strongly typed vessel geometry input models (Section 4).

Field-local checks (types, enums, finiteness) live here. Relational and unit
rules live in validation.py so their messages stay human-readable and never echo
supplied values.
"""
from __future__ import annotations

from enum import Enum
from math import isfinite

from pydantic import BaseModel, ConfigDict, field_validator


class SourceType(str, Enum):
    USER_SPECIFIED = "USER_SPECIFIED"
    AI_ESTIMATED = "AI_ESTIMATED"
    CALCULATED = "CALCULATED"
    ENGINEER_VALIDATED = "ENGINEER_VALIDATED"


class HullFamily(str, Enum):
    MONOHULL = "MONOHULL"
    CATAMARAN = "CATAMARAN"
    TRIMARAN = "TRIMARAN"
    PONTOON = "PONTOON"


class Measurement(BaseModel):
    """A single dimension with full traceability."""

    model_config = ConfigDict(extra="ignore")

    value: float
    unit: str
    source: SourceType
    locked: bool = False

    @field_validator("value")
    @classmethod
    def _finite(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("measurement must be a finite number")
        return value


class VesselGeometryParameters(BaseModel):
    """The first essential vessel dimensions. Optional dimensions may be omitted."""

    model_config = ConfigDict(extra="ignore")

    project_id: str
    units: str
    loa: Measurement
    lwl: Measurement
    beam: Measurement
    draft: Measurement
    depth: Measurement
    hull_family: HullFamily
    deadrise: Measurement | None = None
    transom_width: Measurement | None = None
    chine_height: Measurement | None = None
    bow_height: Measurement | None = None
