import copy
import json
import pytest
from fastapi.testclient import TestClient
from tests.stubs.rhino_stub import rhino_stub, outputs, _input_values

VESSEL = {
    "project_id": "MARLIN-001", "units": "meters",
    "loa": {"value": 20, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "lwl": {"value": 18.5, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "beam": {"value": 5.5, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "draft": {"value": 1.2, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "depth": {"value": 2.4, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "hull_family": "MONOHULL", "station_count": 15,
}


def _meas(**over):
    m = {"loa": 19.96, "beam": 5.48, "draft": 1.19,
         "bounding_box": {"min": [0.0, -2.74, -1.19], "max": [19.96, 2.74, 1.21]},
         "surface_count": 2, "naked_edges": 4, "invalid_trims": 0,
         "self_intersections": 0, "normals_consistent": True,
         "valid_surfaces": True, "symmetry": True, "sides": ["port", "starboard"]}
    m.update(over)
    return m


def _responder(*, malformed=False, surfaces=None, measurements=None):
    def responder(record):
        if malformed:
            return 200, outputs(nonsense="x"), 0
        v = _input_values(record)
        count = int(v.get("station_count", 15))
        surfs = surfaces if surfaces is not None else ["port-1", "stbd-1"]
        meas = measurements if measurements is not None else _meas()
        return 200, outputs(stations=[f"curve-{i}" for i in range(count)],
                            surfaces=surfs, sheer="sheer", bow="bow", stern="stern",
                            measurements=json.dumps(meas)), 0
    return responder


def _app(monkeypatch, base=None, **env):
    from app.mvp import create_app
    if base is not None:
        monkeypatch.setenv("RHINO_COMPUTE_URL", base)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return create_app()


def test_standard_hull_success(monkeypatch):
    with rhino_stub() as (server, base):
        with TestClient(_app(monkeypatch, base)) as client:
            response = client.post("/api/vessel/hull", json=VESSEL)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["project_id"] == "MARLIN-001"
    assert body["hull_family"] == "MONOHULL"
    assert body["surface_count"] == 2
    assert set(body["requested_dimensions"]) == {"loa", "beam", "draft"}
    assert body["validation"] == {"valid_surfaces": True, "symmetry": True, "naked_edges": 4}
    assert body["surface_ids"] == ["port-1", "stbd-1"]
    assert body["sheer_line_id"] == "sheer"
    assert body["file_reference"].startswith("/api/vessel/hull/3dm/")  # a REAL .3dm
    assert body["geometry_source"] == "marlin_parameters"
    assert body["geometry_version"] == 1
    # ONE self-contained solve (no cross-request geometry IDs)
    assert [json.loads(r["body"])["pointer"] for r in server.records] == ["marlin_hull"]


@pytest.mark.parametrize("scale", [0.5, 2.5])
def test_small_and_large_hulls(monkeypatch, scale):
    payload = copy.deepcopy(VESSEL)
    for f in ("loa", "lwl", "beam", "draft", "depth"):
        payload[f]["value"] = round(payload[f]["value"] * scale, 3)
    with rhino_stub() as (server, base):
        with TestClient(_app(monkeypatch, base)) as client:
            response = client.post("/api/vessel/hull", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_dimension_tolerance_failure_returns_failed_state(monkeypatch):
    with rhino_stub(_responder(measurements=_meas(loa=18.0))) as (server, base):
        with TestClient(_app(monkeypatch, base)) as client:
            body = client.post("/api/vessel/hull", json=VESSEL).json()
    assert body["status"] == "failed"
    assert body["tolerances"]["loa"]["within_tolerance"] is False


def test_symmetry_failure_returns_failed_state(monkeypatch):
    meas = _meas(bounding_box={"min": [0.0, -2.74, -1.19], "max": [19.96, 2.10, 1.21]})
    with rhino_stub(_responder(measurements=meas)) as (server, base):
        with TestClient(_app(monkeypatch, base)) as client:
            body = client.post("/api/vessel/hull", json=VESSEL).json()
    assert body["status"] == "failed"
    assert body["validation"]["symmetry"] is False


def test_invalid_surface_returns_failed_state(monkeypatch):
    with rhino_stub(_responder(measurements=_meas(valid_surfaces=False))) as (server, base):
        with TestClient(_app(monkeypatch, base)) as client:
            body = client.post("/api/vessel/hull", json=VESSEL).json()
    assert body["status"] == "failed"
    assert body["validation"]["valid_surfaces"] is False


@pytest.mark.parametrize("kwargs", [
    {"malformed": True},                        # malformed geometry (no surfaces)
    {"surfaces": []},                           # loft operation failure
    {"measurements": {"unexpected": True}},     # invalid geometry response
])
def test_bad_loft_responses(monkeypatch, kwargs):
    with rhino_stub(_responder(**kwargs)) as (server, base):
        with TestClient(_app(monkeypatch, base)) as client:
            response = client.post("/api/vessel/hull", json=VESSEL)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "RHINO_REQUEST_FAILED"


def test_rhino_unavailable(monkeypatch):
    with TestClient(_app(monkeypatch, "http://127.0.0.1:1")) as client:
        response = client.post("/api/vessel/hull", json=VESSEL)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "RHINO_UNAVAILABLE"


def test_rhino_timeout(monkeypatch):
    with rhino_stub(lambda r: (200, b"Healthy", 0.5)) as (server, base):
        with TestClient(_app(monkeypatch, base, RHINO_COMPUTE_TIMEOUT="0.1",
                             RHINO_COMPUTE_MAX_ATTEMPTS="1")) as client:
            response = client.post("/api/vessel/hull", json=VESSEL)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "RHINO_UNAVAILABLE"


def test_invalid_input_rejected_before_rhino(monkeypatch):
    payload = copy.deepcopy(VESSEL); payload["beam"]["value"] = -1
    with rhino_stub() as (server, base):
        with TestClient(_app(monkeypatch, base)) as client:
            response = client.post("/api/vessel/hull", json=payload)
    assert response.status_code == 422
    assert server.records == []


def test_unsupported_hull_family_rejected():
    payload = copy.deepcopy(VESSEL); payload["hull_family"] = "TRIMARAN"
    with TestClient(_app(None)) as client:
        response = client.post("/api/vessel/hull", json=payload)
    assert response.status_code == 422
    details = {d["field"]: d["code"] for d in response.json()["error"]["details"]}
    assert details["hull_family"] == "UNSUPPORTED_HULL_FAMILY"


def test_acceptance_20m_hull(monkeypatch):
    with rhino_stub() as (server, base):
        with TestClient(_app(monkeypatch, base)) as client:
            body = client.post("/api/vessel/hull", json=VESSEL).json()
    assert body["status"] == "success"
    assert body["surface_count"] == 2
    assert all(t["within_tolerance"] for t in body["tolerances"].values())
    assert body["validation"]["valid_surfaces"] is True
    assert body["validation"]["symmetry"] is True
    assert len(body["curve_ids"]) == 15
