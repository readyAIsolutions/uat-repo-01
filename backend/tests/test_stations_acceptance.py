"""Real acceptance test (local math) + live-Rhino integration test.

The local acceptance test runs against real code with mocked Rhino responses.
The live integration test only runs when a real RHINO_COMPUTE_URL is configured;
it is SKIPPED otherwise (no node on this host) and never fakes Rhino geometry.
"""
import copy
import json
import os
import pytest
from fastapi.testclient import TestClient

VESSEL_20M = {
    "project_id": "MARLIN-001", "units": "meters",
    "loa": {"value": 20, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "lwl": {"value": 18.5, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "beam": {"value": 5.5, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "draft": {"value": 1.2, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "depth": {"value": 2.4, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "hull_family": "MONOHULL", "station_count": 15,
}


def _curve_responder(record):
    from tests.stubs.rhino_stub import _input_values, outputs
    count = int(_input_values(record).get("station_count", 15))
    return 200, outputs(stations=[f"curve-{i}" for i in range(count)],
                        baseline="b", centerline="c", design_waterline="w"), 0


def test_acceptance_20m_geometry(monkeypatch):
    from app.mvp import create_app
    from tests.stubs.rhino_stub import rhino_stub
    with rhino_stub(_curve_responder) as (server, base):
        monkeypatch.setenv("RHINO_COMPUTE_URL", base)
        with TestClient(create_app()) as client:
            response = client.post("/api/vessel/stations", json=VESSEL_20M)
    assert response.status_code == 200
    body = response.json()

    # exactly 15 station positions, spanning full LOA
    assert body["station_count"] == 15 == len(body["stations"])
    xs = [s["x"] for s in body["stations"]]
    assert xs[0] == pytest.approx(0.0) and xs[-1] == pytest.approx(20.0)
    assert xs[-1] - xs[0] == pytest.approx(20.0, abs=0.01)

    # max station width approximates the requested beam, at midship
    beams = [s["local_beam"] for s in body["stations"]]
    assert max(beams) == pytest.approx(5.5, abs=0.05)
    assert beams.index(max(beams)) == 7           # midship
    assert beams[0] > beams[-1]                   # bow narrows

    # vertical extent reflects draft and depth; symmetry correct
    bb = body["bounding_box"]
    assert bb["min"][2] == pytest.approx(-1.2, abs=0.01)     # lowest reaches draft
    assert bb["max"][2] == pytest.approx(1.2, abs=0.01)      # sheer reaches depth-draft
    assert bb["min"][1] == pytest.approx(-2.75, abs=0.01)    # symmetric about centerline
    assert bb["max"][1] == pytest.approx(2.75, abs=0.01)

    # Rhino.Compute was actually invoked
    assert body["rhino_compute_used"] is True
    assert len(server.records) == 1
    sent = json.loads(server.records[0]["body"])
    assert sent["pointer"] == "marlin_station_curves"
    assert {v["ParamName"] for v in sent["values"]} >= {"loa", "beam", "draft", "depth", "station_count"}


@pytest.mark.skipif(not os.environ.get("RHINO_COMPUTE_URL"),
                    reason="no live Rhino.Compute node configured (Rhino is Windows/licensed)")
def test_live_rhino_integration():
    from app.mvp import create_app
    with TestClient(create_app()) as client:
        response = client.post("/api/vessel/stations", json=VESSEL_20M)
    assert response.status_code == 200
    body = response.json()
    assert body["rhino_compute_used"] is True
    assert len(body["curve_ids"]) == 15
