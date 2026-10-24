import pytest
from app.services.vessel.models import VesselGeometryParameters
from app.services.vessel import hull


def _params(**over):
    def m(v):
        return {"value": v, "unit": "m", "source": "USER_SPECIFIED", "locked": True}
    base = dict(project_id="P1", units="meters", loa=m(20), lwl=m(18.5), beam=m(5.5),
                draft=m(1.2), depth=m(2.4), hull_family="MONOHULL")
    base.update(over)
    return VesselGeometryParameters.model_validate(base)


def _loft(loa=19.96, beam=5.48, draft=1.19, miny=-2.74, maxy=2.74,
          surfaces=None, **meas):
    surfaces = surfaces if surfaces is not None else [
        {"id": "p", "side": "port", "valid": True},
        {"id": "s", "side": "starboard", "valid": True}]
    measurements = {"loa": loa, "beam": beam, "draft": draft,
                    "bounding_box": {"min": [0.0, miny, -draft], "max": [loa, maxy, 1.21]},
                    "naked_edges": 4}
    measurements.update(meas)
    return {"surfaces": surfaces, "measurements": measurements,
            "sheer_line": {"id": "sheer"}, "bow_termination": {"id": "bow"},
            "stern_termination": {"id": "stern"}, "file_reference": None}


def _station_result():
    return {"curve_ids": ["c0", "c1"], "reference_curve_ids":
            {"baseline": "b", "centerline": "c", "design_waterline": "w"}}


def test_tolerance_check_reports_error_percent():
    check = hull._tolerance_check(5.5, 5.47, 1.0)
    assert check["error_percent"] == pytest.approx(0.5455, abs=0.001)
    assert check["within_tolerance"] is True
    assert hull._tolerance_check(20.0, 18.0, 1.0)["within_tolerance"] is False


def test_inspect_success_when_within_tolerance_symmetric_and_valid():
    result = hull.inspect_hull(_params(), 15, _station_result(), _loft())
    assert result["status"] == "success"
    assert result["validation"] == {"valid_surfaces": True, "symmetry": True, "naked_edges": 4}
    assert result["surface_count"] == 2
    assert result["requested_dimensions"]["beam"] == 5.5
    assert result["actual_dimensions"]["beam"] == 5.48
    assert all(t["within_tolerance"] for t in result["tolerances"].values())


def test_inspect_fails_on_dimension_tolerance_failure():
    result = hull.inspect_hull(_params(), 15, _station_result(), _loft(loa=18.0))
    assert result["status"] == "failed"
    assert result["tolerances"]["loa"]["within_tolerance"] is False
    assert any("LOA outside tolerance" in w for w in result["warnings"])


def test_inspect_fails_on_symmetry_failure():
    result = hull.inspect_hull(_params(), 15, _station_result(), _loft(miny=-2.74, maxy=2.10))
    assert result["status"] == "failed"
    assert result["validation"]["symmetry"] is False
    assert any("symmetry" in w.lower() for w in result["warnings"])


def test_inspect_fails_on_invalid_surface():
    surfaces = [{"id": "p", "side": "port", "valid": False},
                {"id": "s", "side": "starboard", "valid": True}]
    result = hull.inspect_hull(_params(), 15, _station_result(), _loft(surfaces=surfaces))
    assert result["status"] == "failed"
    assert result["validation"]["valid_surfaces"] is False


def test_inspect_always_warns_about_fairness():
    result = hull.inspect_hull(_params(), 15, _station_result(), _loft())
    assert hull.FAIRNESS_WARNING in result["warnings"]
