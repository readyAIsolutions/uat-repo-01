import pytest
from app.services.vessel.models import (
    HullFamily, Measurement, SourceType, VesselGeometryParameters)


def _m(value, unit="m", source="USER_SPECIFIED", locked=True):
    return {"value": value, "unit": unit, "source": source, "locked": locked}


def _params(**over):
    base = dict(project_id="P1", units="meters", loa=_m(20), lwl=_m(18), beam=_m(5),
                draft=_m(1), depth=_m(2), hull_family="MONOHULL")
    base.update(over)
    return base


def test_unit_aliases_normalize_to_canonical():
    from app.services.vessel.validation import canonical_unit
    assert canonical_unit("meters") == "m"
    assert canonical_unit("FEET") == "ft"
    assert canonical_unit("Foot") == "ft"
    assert canonical_unit("centimeters") == "cm"
    assert canonical_unit("cubits") is None


def test_cross_unit_relationship_is_compared_in_metres():
    from app.services.vessel.validation import validate_vessel
    # LOA 20 m, LWL 65 ft (=19.8 m) -> valid even though 65 > 20 numerically
    params = VesselGeometryParameters.model_validate(
        _params(lwl=_m(65, "ft"), loa=_m(20, "m")))
    assert validate_vessel(params) == []
    # LWL 66 ft (=20.1 m) > LOA 20 m -> invalid
    params = VesselGeometryParameters.model_validate(
        _params(lwl=_m(66, "ft"), loa=_m(20, "m")))
    codes = {i.field: i.code for i in validate_vessel(params)}
    assert codes["lwl"] == "INVALID_RELATIONSHIP"


def test_deadrise_range():
    from app.services.vessel.validation import validate_vessel
    ok = VesselGeometryParameters.model_validate(_params(deadrise=_m(15, "deg")))
    assert validate_vessel(ok) == []
    bad = VesselGeometryParameters.model_validate(_params(deadrise=_m(120, "deg")))
    codes = {i.field: i.code for i in validate_vessel(bad)}
    assert codes["deadrise"] == "OUT_OF_RANGE"


def test_optional_measurements_are_accepted():
    from app.services.vessel.validation import validate_vessel, normalize_vessel
    params = VesselGeometryParameters.model_validate(
        _params(transom_width=_m(4), chine_height=_m(0.8), bow_height=_m(1.4)))
    assert validate_vessel(params) == []
    normalized = normalize_vessel(params)
    assert normalized["parameters"]["transom_width"]["value"] == 4.0
    assert normalized["base_meters"]["bow_height"] == 1.4


def test_normalize_converts_to_display_unit():
    from app.services.vessel.validation import normalize_vessel
    params = VesselGeometryParameters.model_validate(
        _params(units="centimeters", loa=_m(20, "m")))
    normalized = normalize_vessel(params)
    assert normalized["units"] == "cm"
    assert normalized["parameters"]["loa"]["value"] == 2000.0
    assert normalized["base_meters"]["loa"] == 20.0


def test_source_types_are_enforced_by_the_model():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        VesselGeometryParameters.model_validate(_params(loa=_m(20, source="GUESSED")))
    assert set(s.value for s in SourceType) == {
        "USER_SPECIFIED", "AI_ESTIMATED", "CALCULATED", "ENGINEER_VALIDATED"}


def test_hull_families_exposed():
    assert "MONOHULL" in [h.value for h in HullFamily]
