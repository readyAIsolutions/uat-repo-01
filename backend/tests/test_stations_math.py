import math
import pytest
from app.services.vessel.stations import (
    STERN_BEAM_RATIO, BOW_BEAM_RATIO, build_station_plan, shape_factor)


def test_shape_factor_endpoints_and_midship():
    assert shape_factor(0.0) == pytest.approx(STERN_BEAM_RATIO)
    assert shape_factor(0.5) == pytest.approx(1.0)
    assert shape_factor(1.0) == pytest.approx(BOW_BEAM_RATIO)
    assert shape_factor(0.5) >= shape_factor(0.0) >= shape_factor(1.0)


def test_shape_factor_is_smooth_and_symmetric_about_midship_peak():
    xs = [i / 100 for i in range(101)]
    ys = [shape_factor(x) for x in xs]
    assert max(ys) == pytest.approx(1.0)
    assert ys.index(max(ys)) == 50  # widest exactly at midship
    # no jumps: bounded step for a 0.01 grid
    assert max(abs(ys[i + 1] - ys[i]) for i in range(100)) < 0.05


def test_station_positions_span_full_loa():
    plan = build_station_plan(loa=20.0, beam=5.5, draft=1.2, depth=2.4, station_count=15)
    xs = [s["x"] for s in plan["stations"]]
    assert len(xs) == 15
    assert xs[0] == pytest.approx(0.0)
    assert xs[-1] == pytest.approx(20.0)
    assert xs == sorted(xs)


def test_max_local_beam_equals_beam_and_is_widest_at_midship():
    plan = build_station_plan(loa=20.0, beam=5.5, draft=1.2, depth=2.4, station_count=15)
    beams = [s["local_beam"] for s in plan["stations"]]
    assert max(beams) == pytest.approx(5.5)
    assert beams.index(max(beams)) == 7  # midship for 15 stations
    assert beams[0] > beams[-1]  # bow narrower than stern


def test_sections_are_symmetric_and_reach_draft_and_depth():
    plan = build_station_plan(loa=20.0, beam=5.5, draft=1.2, depth=2.4, station_count=15)
    for station in plan["stations"]:
        pts = station["points"]
        assert pts[0][1] == pytest.approx(-pts[-1][1])  # port/starboard symmetric
        ys = [p[1] for p in pts]
        assert min(ys) == pytest.approx(-max(ys))
        zs = [p[2] for p in pts]
        assert min(zs) == pytest.approx(-1.2)          # keel reaches draft
        assert max(zs) == pytest.approx(2.4 - 1.2)     # sheer reaches depth-draft
        assert min(ys) == pytest.approx(-station["local_beam"] / 2)


def test_bounding_box_matches_dimensions():
    plan = build_station_plan(loa=20.0, beam=5.5, draft=1.2, depth=2.4, station_count=15)
    bb = plan["bounding_box"]
    assert bb["min"] == pytest.approx([0.0, -2.75, -1.2])
    assert bb["max"] == pytest.approx([20.0, 2.75, 1.2])


def test_reference_curves_present():
    plan = build_station_plan(loa=20.0, beam=5.5, draft=1.2, depth=2.4, station_count=15)
    refs = plan["reference_curves"]
    assert set(refs) == {"baseline", "centerline", "design_waterline"}
    assert refs["baseline"][0][2] == pytest.approx(-1.2)   # baseline at keel
    assert refs["design_waterline"][0][2] == pytest.approx(0.0)  # DWL at z=0
