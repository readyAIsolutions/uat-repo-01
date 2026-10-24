import copy
import json
import pytest
from fastapi.testclient import TestClient
from tests.stubs.rhino_stub import rhino_stub

VESSEL = {
    "project_id": "MARLIN-001", "units": "meters",
    "loa": {"value": 20, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "lwl": {"value": 18.5, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "beam": {"value": 5.5, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "draft": {"value": 1.2, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "depth": {"value": 2.4, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "hull_family": "MONOHULL",
}


def _curve_responder(record):
    """A real-Compute-shaped response: one station curve per requested station."""
    from tests.stubs.rhino_stub import _input_values, outputs
    count = int(_input_values(record).get("station_count", 15))
    return 200, outputs(stations=[f"curve-{i}" for i in range(count)],
                        baseline="ref-baseline", centerline="ref-centerline",
                        design_waterline="ref-dwl"), 0


def _app(monkeypatch, base=None, **env):
    from app.mvp import create_app
    if base is not None:
        monkeypatch.setenv("RHINO_COMPUTE_URL", base)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return create_app()


def test_valid_monohull_generates_stations(monkeypatch):
    with rhino_stub(_curve_responder) as (server, base):
        with TestClient(_app(monkeypatch, base)) as client:
            response = client.post("/api/vessel/stations", json=VESSEL)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["project_id"] == "MARLIN-001"
    assert body["station_count"] == 15
    assert body["geometry_version"] == 1
    assert body["hull_family"] == "MONOHULL"
    assert body["rhino_compute_used"] is True
    assert len(body["stations"]) == 15
    assert len(body["curve_ids"]) == 15
    assert body["reference_curve_ids"] == {
        "baseline": "ref-baseline", "centerline": "ref-centerline",
        "design_waterline": "ref-dwl"}
    assert server.records[0]["path"] == "/grasshopper"


def test_station_count_is_honored_and_defaulted(monkeypatch):
    with rhino_stub(_curve_responder) as (server, base):
        with TestClient(_app(monkeypatch, base)) as client:
            custom = client.post("/api/vessel/stations",
                                 json={**VESSEL, "station_count": 12}).json()
    assert custom["station_count"] == 12 and len(custom["curve_ids"]) == 12


@pytest.mark.parametrize("scale", [0.4, 3.0])
def test_small_and_large_vessels(monkeypatch, scale):
    def scaled(value):
        return {"value": round(value * scale, 3), "unit": "m",
                "source": "USER_SPECIFIED", "locked": True}

    payload = copy.deepcopy(VESSEL)
    payload["loa"] = scaled(20); payload["lwl"] = scaled(18)
    payload["beam"] = scaled(5.5); payload["draft"] = scaled(1.2)
    payload["depth"] = scaled(2.4)
    with rhino_stub(_curve_responder) as (server, base):
        with TestClient(_app(monkeypatch, base)) as client:
            response = client.post("/api/vessel/stations", json=payload)
    assert response.status_code == 200
    assert response.json()["station_count"] == 15


@pytest.mark.parametrize("mutate", ["loa_zero", "beam_negative", "depth_lt_draft"])
def test_invalid_dimensions_rejected_before_rhino(monkeypatch, mutate):
    payload = copy.deepcopy(VESSEL)
    if mutate == "loa_zero":
        payload["loa"]["value"] = 0
    elif mutate == "beam_negative":
        payload["beam"]["value"] = -1
    else:
        payload["depth"]["value"] = 1.0
    with rhino_stub(_curve_responder) as (server, base):
        with TestClient(_app(monkeypatch, base)) as client:
            response = client.post("/api/vessel/stations", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VESSEL_VALIDATION_FAILED"
    assert server.records == []  # rejected before any Rhino call


def test_unsupported_hull_family_rejected():
    payload = copy.deepcopy(VESSEL); payload["hull_family"] = "CATAMARAN"
    with TestClient(_app(None)) as client:
        response = client.post("/api/vessel/stations", json=payload)
    assert response.status_code == 422
    details = {d["field"]: d["code"] for d in response.json()["error"]["details"]}
    assert details["hull_family"] == "UNSUPPORTED_HULL_FAMILY"


@pytest.mark.parametrize("count", [9, 21])
def test_station_count_out_of_range(count):
    with TestClient(_app(None)) as client:
        response = client.post("/api/vessel/stations", json={**VESSEL, "station_count": count})
    assert response.status_code == 422
    details = {d["field"]: d["code"] for d in response.json()["error"]["details"]}
    assert details["station_count"] == "OUT_OF_RANGE"


def test_rhino_unavailable(monkeypatch):
    with TestClient(_app(monkeypatch, "http://127.0.0.1:1")) as client:
        response = client.post("/api/vessel/stations", json=VESSEL)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "RHINO_UNAVAILABLE"


def test_rhino_unconfigured():
    with TestClient(_app(None)) as client:
        response = client.post("/api/vessel/stations", json=VESSEL)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "RHINO_NOT_CONFIGURED"


def test_rhino_timeout(monkeypatch):
    with rhino_stub(lambda r: (200, {"curves": []}, 0.5)) as (server, base):
        with TestClient(_app(monkeypatch, base, RHINO_COMPUTE_TIMEOUT="0.1",
                             RHINO_COMPUTE_MAX_ATTEMPTS="1")) as client:
            response = client.post("/api/vessel/stations", json=VESSEL)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "RHINO_UNAVAILABLE"


def test_malformed_rhino_response(monkeypatch):
    with rhino_stub(lambda r: (200, {"unexpected": True}, 0)) as (server, base):
        with TestClient(_app(monkeypatch, base)) as client:
            response = client.post("/api/vessel/stations", json=VESSEL)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "RHINO_REQUEST_FAILED"
