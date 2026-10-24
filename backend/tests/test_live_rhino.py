"""Section 8 — live Rhino.Compute integration tests.

These run ONLY when a real Rhino.Compute node is configured (RHINO_COMPUTE_URL).
Without a node they SKIP and are NOT counted as passed. They exist so that
provisioning a node immediately produces real, verified Rhino geometry.
"""
import os
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("RHINO_COMPUTE_URL"),
    reason="no live Rhino.Compute node configured (Rhino is Windows/licensed)")

VESSEL = {
    "project_id": "MARLIN-LIVE", "units": "meters",
    "loa": {"value": 20, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "lwl": {"value": 18.5, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "beam": {"value": 5.5, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "draft": {"value": 1.2, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "depth": {"value": 2.4, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "hull_family": "MONOHULL", "station_count": 15,
}


def _client():
    from app.mvp import create_app
    return TestClient(create_app())


def test_live_status_connected():
    with _client() as client:
        assert client.get("/api/rhino/status").json()["reachable"] is True


def test_live_box():
    with _client() as client:
        response = client.post("/api/rhino/box", json={"width": 4, "length": 10, "height": 2})
    assert response.status_code == 200


def test_live_station_curves():
    with _client() as client:
        body = client.post("/api/vessel/stations", json=VESSEL).json()
    assert body["rhino_compute_used"] is True
    assert len(body["curve_ids"]) == 15


def test_live_nurbs_hull():
    with _client() as client:
        body = client.post("/api/vessel/hull", json=VESSEL).json()
    assert body["status"] == "success"
    assert body["surface_count"] >= 2
    assert all(t["within_tolerance"] for t in body["tolerances"].values())


def test_live_hull_writes_real_3dm():
    """The live chain must produce a real, downloadable .3dm file."""
    import rhino3dm
    with _client() as client:
        body = client.post("/api/vessel/hull", json=VESSEL).json()
        ref = body["file_reference"]
        assert ref and ref.startswith("/api/vessel/hull/3dm/")
        download = client.get(ref)
        assert download.status_code == 200
    import pathlib
    local = pathlib.Path(body["file_reference"].rsplit("/", 1)[1])
    assert rhino3dm.File3dm.Read(str(local)) is not None
