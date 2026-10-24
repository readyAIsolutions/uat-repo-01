"""Domain validation + normalization for vessel geometry (Section 4).

All messages are fixed templates: they never echo supplied values. Validation
never silently fixes a number — it reports the problem.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from pydantic import ValidationError

from .models import HullFamily, Measurement, SourceType, VesselGeometryParameters

_LENGTH_UNIT_FACTORS = {"m": 1.0, "cm": 0.01, "mm": 0.001, "ft": 0.3048, "in": 0.0254}
_UNIT_ALIASES = {
    "m": "m", "meter": "m", "meters": "m", "metre": "m", "metres": "m",
    "cm": "cm", "centimeter": "cm", "centimeters": "cm",
    "mm": "mm", "millimeter": "mm", "millimeters": "mm",
    "ft": "ft", "foot": "ft", "feet": "ft",
    "in": "in", "inch": "in", "inches": "in",
    "deg": "deg", "degree": "deg", "degrees": "deg",
}
SUPPORTED_UNITS = tuple(sorted(_LENGTH_UNIT_FACTORS))
DEADRISE_MIN = 0.0
DEADRISE_MAX = 90.0

_LENGTH_FIELDS = ("loa", "lwl", "beam", "draft", "depth",
                  "transom_width", "chine_height", "bow_height")
_LABELS = {
    "project_id": "Project ID", "units": "Units", "loa": "LOA", "lwl": "LWL",
    "beam": "Beam", "draft": "Draft", "depth": "Depth", "deadrise": "Deadrise",
    "transom_width": "Transom width", "chine_height": "Chine height",
    "bow_height": "Bow height", "hull_family": "Hull family", "body": "Request body",
}
_ENUM_ALLOWED = {
    "source": [s.value for s in SourceType],
    "hull_family": [h.value for h in HullFamily],
}
_NUMERIC_ERROR_TYPES = {
    "float_parsing", "int_parsing", "float_type", "int_type", "decimal_parsing",
    "finite_number", "greater_than", "less_than", "greater_than_equal", "less_than_equal",
}


@dataclass(frozen=True)
class Issue:
    field: str
    code: str
    message: str

    def as_dict(self) -> dict:
        return asdict(self)


class VesselValidationError(ValueError):
    """Raised with a list of value-free Issue dicts; mapped to HTTP 422."""

    def __init__(self, issues) -> None:
        self.issues = [i.as_dict() if isinstance(i, Issue) else i for i in issues]
        super().__init__("vessel geometry validation failed")


def canonical_unit(token) -> str | None:
    if not isinstance(token, str):
        return None
    return _UNIT_ALIASES.get(token.strip().lower())


def _label(field: str) -> str:
    parts = field.split(".")
    base = _LABELS.get(parts[0], parts[0])
    return base if len(parts) == 1 else f"{base} {parts[-1]}"


def _to_meters(measurement: Measurement, canonical: str) -> float:
    return measurement.value * _LENGTH_UNIT_FACTORS[canonical]


def measurement_meters(measurement: Measurement) -> float:
    """Value of a length measurement expressed in metres (assumes a valid unit)."""
    return _to_meters(measurement, canonical_unit(measurement.unit))


def validate_vessel(params: VesselGeometryParameters) -> list[Issue]:
    issues: list[Issue] = []

    if canonical_unit(params.units) is None:
        issues.append(Issue("units", "UNSUPPORTED_UNIT",
                            "Units must be one of: " + ", ".join(SUPPORTED_UNITS)))

    canonical = {f: canonical_unit(getattr(params, f).unit)
                 for f in _LENGTH_FIELDS if getattr(params, f) is not None}
    for field, unit in canonical.items():
        if unit is None:
            issues.append(Issue(f"{field}.unit", "UNSUPPORTED_UNIT",
                                f"{_label(field)} unit must be one of: "
                                + ", ".join(SUPPORTED_UNITS)))

    for field in ("loa", "lwl", "beam", "draft"):
        unit = canonical.get(field)
        if unit and _to_meters(getattr(params, field), unit) <= 0:
            issues.append(Issue(field, "OUT_OF_RANGE",
                                f"{_label(field)} must be greater than 0"))

    depth_unit, draft_unit = canonical.get("depth"), canonical.get("draft")
    if depth_unit:
        if _to_meters(params.depth, depth_unit) <= 0:
            issues.append(Issue("depth", "OUT_OF_RANGE", "Depth must be greater than 0"))
        elif draft_unit and _to_meters(params.depth, depth_unit) <= _to_meters(params.draft, draft_unit):
            issues.append(Issue("depth", "INVALID_RELATIONSHIP",
                                "Depth must be greater than draft"))

    loa_unit, lwl_unit = canonical.get("loa"), canonical.get("lwl")
    if loa_unit and lwl_unit and _to_meters(params.lwl, lwl_unit) > _to_meters(params.loa, loa_unit):
        issues.append(Issue("lwl", "INVALID_RELATIONSHIP",
                            "LWL must be less than or equal to LOA"))

    if params.deadrise is not None:
        if canonical_unit(params.deadrise.unit) != "deg":
            issues.append(Issue("deadrise.unit", "UNSUPPORTED_UNIT",
                                "Deadrise unit must be degrees (deg)"))
        elif not (DEADRISE_MIN <= params.deadrise.value <= DEADRISE_MAX):
            issues.append(Issue("deadrise", "OUT_OF_RANGE",
                                f"Deadrise must be between {DEADRISE_MIN:g} and "
                                f"{DEADRISE_MAX:g} degrees"))

    return issues


def normalize_vessel(params: VesselGeometryParameters) -> dict:
    display = canonical_unit(params.units) or params.units
    parameters: dict[str, dict] = {}
    base_meters: dict[str, float] = {}
    for field in _LENGTH_FIELDS:
        measurement = getattr(params, field)
        if measurement is None:
            continue
        unit = canonical_unit(measurement.unit)
        if unit is None:
            continue
        meters = _to_meters(measurement, unit)
        base_meters[field] = meters
        parameters[field] = {
            "value": meters / _LENGTH_UNIT_FACTORS[display],
            "unit": display,
            "source": measurement.source.value,
            "locked": measurement.locked,
        }
    if params.deadrise is not None:
        parameters["deadrise"] = {
            "value": params.deadrise.value, "unit": "deg",
            "source": params.deadrise.source.value, "locked": params.deadrise.locked,
        }
    return {
        "valid": True,
        "project_id": params.project_id,
        "units": display,
        "hull_family": params.hull_family.value,
        "parameters": parameters,
        "base_meters": base_meters,
    }


def issues_from_validation_error(error: ValidationError) -> list[Issue]:
    issues: list[Issue] = []
    for item in error.errors(include_input=False, include_url=False):
        loc = [str(part) for part in item["loc"]]
        field = ".".join(loc)
        etype = item["type"]
        if etype == "missing":
            code, message = "MISSING", f"{_label(field)} is required"
        elif etype in _NUMERIC_ERROR_TYPES:
            code, message = "NOT_A_NUMBER", f"{_label(field)} must be a number"
        elif etype == "enum":
            allowed = _ENUM_ALLOWED.get(loc[-1], [])
            code = "INVALID_VALUE"
            message = f"{_label(field)} must be one of: " + ", ".join(allowed)
        else:
            code, message = "INVALID_VALUE", f"{_label(field)} is invalid"
        issues.append(Issue(field, code, message))
    return issues
