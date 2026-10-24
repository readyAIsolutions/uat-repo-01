"""Section 8 — full-chain integration test for the MARLIN Rhino MVP.

Exercises the whole MVP chain through the ASGI app against a loopback
Rhino-shaped stub (NOT real Rhino): health -> rhino status -> validate ->
stations -> hull -> dimensions/errors -> failure handling.
"""
import copy
import json
import pytest
from fastapi.testclient import TestClient
from tests.stubs.rhino_stub import rhino_stub

CASE_A = {
    "project_id": "MARLIN-001", "units": "meters",
    "loa": {"value": 20, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "lwl": {"value": 18.5, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "beam": {"value": 5.5, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "draft": {"value": 1.2, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "depth": {"value": 2.4, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "hull_family": "MONOHULL", "station_count": 15,
}
CASE_C = {
    "project_id": "MARLIN-BAD", "units": "meters",
    "loa": {"value": 10, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "lwl": {"value": 12, "unit": "m", "source": "USER_SPECIFIED", "locked": True},  # > LOA
    "beam": {"value": 4, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "draft": {"value": 3, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "depth": {"value": 2, "unit": "m", "source": "USER_SPECIFIED", "locked": True},  # < draft
    "hull_family": "MONOHULL", "station_count": 15,
}


def _chain_responder(record):
    """Derive geometry from the requested dims so scaling (not hard-coding) is proven."""
    from tests.stubs.rhino_stub import _input_values, outputs
    if record["method"] != "POST" or not record["body"]:
        return 200, b"Healthy", 0   # GET /healthcheck connectivity probe
    v = _input_values(record)
    loa = float(v.get("loa", 20.0)); beam = float(v.get("beam", 5.5))
    draft = float(v.get("draft", 1.2)); depth = float(v.get("depth", 2.4))
    count = int(v.get("station_count", 15))
    measurements = {"loa": loa * 0.997, "beam": beam * 0.997, "draft": draft * 0.995,
                    "bounding_box": {"min": [0, -beam / 2, -draft],
                                     "max": [loa, beam / 2, depth - draft]},
                    "surface_count": 2, "naked_edges": 4, "invalid_trims": 0,
                    "self_intersections": 0, "normals_consistent": True,
                    "valid_surfaces": True, "symmetry": True, "sides": ["port", "starboard"]}
    return 200, outputs(stations=[f"curve-{i}" for i in range(count)],
                        surfaces=["port-1", "stbd-1"], sheer="sheer", bow="bow",
                        stern="stern", measurements=json.dumps(measurements)), 0


def _app(monkeypatch, base):
    from app.mvp import create_app
    monkeypatch.setenv("RHINO_COMPUTE_URL", base)
    return create_app()


def test_case_a_standard_vessel_full_chain(monkeypatch):
    with rhino_stub(_chain_responder) as (server, base):
        with TestClient(_app(monkeypatch, base)) as client:
            assert client.get("/health").json()["status"] == "ok"
            assert client.get("/api/rhino/status").json()["reachable"] is True
            assert client.post("/api/vessel/validate", json=CASE_A).status_code == 200
            stations = client.post("/api/vessel/stations", json=CASE_A).json()
            hull = client.post("/api/vessel/hull", json=CASE_A).json()
    assert stations["station_count"] == 15 and len(stations["curve_ids"]) == 15
    assert hull["status"] == "success"
    assert hull["surface_count"] == 2
    assert hull["validation"]["symmetry"] is True
    assert all(t["within_tolerance"] for t in hull["tolerances"].values())
    assert hull["actual_dimensions"]["loa"] != 20.0  # measured, not echoed


def test_case_b_smaller_vessel_scales(monkeypatch):
    small = copy.deepcopy(CASE_A)
    for f in ("loa", "lwl", "beam", "draft", "depth"):
        small[f]["value"] = round(small[f]["value"] * 0.5, 3)
    with rhino_stub(_chain_responder) as (server, base):
        with TestClient(_app(monkeypatch, base)) as client:
            client.post("/api/vessel/validate", json=small)
            hull = client.post("/api/vessel/hull", json=small).json()
    assert hull["status"] == "success"
    # ~half of Case A -> proves geometry derives from inputs, not hard-coding
    assert hull["actual_dimensions"]["loa"] == pytest.approx(10.0, abs=0.1)
    assert hull["requested_dimensions"]["beam"] == pytest.approx(2.75)


def test_case_c_invalid_vessel_rejected_before_rhino(monkeypatch):
    with rhino_stub(_chain_responder) as (server, base):
        with TestClient(_app(monkeypatch, base)) as client:
            validate = client.post("/api/vessel/validate", json=CASE_C)
            stations = client.post("/api/vessel/stations", json=CASE_C)
            hull = client.post("/api/vessel/hull", json=CASE_C)
    for response in (validate, stations, hull):
        assert response.status_code == 422
        codes = {d["field"]: d["code"] for d in response.json()["error"]["details"]}
        assert codes["lwl"] == "INVALID_RELATIONSHIP"      # LWL > LOA
        assert codes["depth"] == "INVALID_RELATIONSHIP"    # depth <= draft
    assert server.records == []  # never touched Rhino


@pytest.mark.parametrize("case,base", [("offline", "http://127.0.0.1:1")])
def test_rhino_unavailable_chain(monkeypatch, case, base):
    with TestClient(_app(monkeypatch, base)) as client:
        assert client.get("/api/rhino/status").json()["reachable"] is False
        assert client.post("/api/vessel/stations", json=CASE_A).status_code == 503
        hull = client.post("/api/vessel/hull", json=CASE_A)
    assert hull.status_code == 503
    assert hull.json()["error"]["code"] == "RHINO_UNAVAILABLE"


def test_unconfigured_rhino_chain():
    from app.mvp import create_app
    with TestClient(create_app()) as client:
        assert client.get("/api/rhino/status").json()["configured"] is False
        assert client.post("/api/vessel/hull", json=CASE_A).status_code == 503


def test_timeout_and_bad_data_fail_gracefully(monkeypatch):
    # timeout
    with rhino_stub(lambda r: (200, {"curves": []}, 0.5)) as (server, base):
        monkeypatch.setenv("RHINO_COMPUTE_URL", base)
        monkeypatch.setenv("RHINO_COMPUTE_TIMEOUT", "0.1")
        monkeypatch.setenv("RHINO_COMPUTE_MAX_ATTEMPTS", "1")
        from app.mvp import create_app
        with TestClient(create_app()) as client:
            assert client.post("/api/vessel/hull", json=CASE_A).status_code == 503
    # malformed loft geometry
    def bad(record):
        body = json.loads(record["body"])
        if body.get("definition") == "marlin_station_curves":
            return 200, {"curves": [{"id": "c0"}], "reference_curves": {}}, 0
        return 200, {"surfaces": []}, 0  # empty surfaces -> loft failure
    with rhino_stub(bad) as (server, base):
        monkeypatch.setenv("RHINO_COMPUTE_URL", base)
        monkeypatch.setenv("RHINO_COMPUTE_TIMEOUT", "10")
        monkeypatch.setenv("RHINO_COMPUTE_MAX_ATTEMPTS", "1")
        from app.mvp import create_app
        with TestClient(create_app()) as client:
            assert client.post("/api/vessel/hull", json=CASE_A).status_code == 502
