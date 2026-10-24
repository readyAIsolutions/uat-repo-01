"""Prove Rhino.Compute-returned NURBS geometry is ingested into the .3dm.

A real NURBS/Brep is encoded EXACTLY as Rhino.Compute's geometry resolver does,
returned through the stub, and the resulting .3dm must contain it.
"""
import json
import rhino3dm
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


def _encoded_nurbs_brep():
    ps = rhino3dm.PlaneSurface(rhino3dm.Plane.WorldXY(), rhino3dm.Interval(0, 3), rhino3dm.Interval(0, 2))
    return rhino3dm.Brep.CreateFromSurface(ps).Encode()   # dict, as Compute returns it


def test_compute_returned_nurbs_is_ingested(monkeypatch, tmp_path):
    geoms = [_encoded_nurbs_brep(), _encoded_nurbs_brep()]

    def responder(record):
        v = _input_values(record)
        count = int(v.get("station_count", 15))
        meas = {"loa": 19.96, "beam": 5.48, "draft": 1.19,
                "bounding_box": {"min": [0, -2.74, -1.19], "max": [19.96, 2.74, 1.21]},
                "surface_count": 2, "valid_surfaces": True, "symmetry": True,
                "sides": ["port", "starboard"]}
        return 200, outputs(stations=[f"curve-{i}" for i in range(count)],
                            surfaces=geoms, measurements=json.dumps(meas)), 0

    from app.mvp import create_app
    with rhino_stub(responder) as (server, base):
        monkeypatch.setenv("RHINO_COMPUTE_URL", base)
        monkeypatch.setenv("MARLIN_STORAGE_DIR", str(tmp_path))
        with TestClient(create_app()) as client:
            body = client.post("/api/vessel/hull", json=VESSEL).json()

    assert body["nurbs_ingested"] is True
    assert body["geometry_source"] == "rhino_compute_nurbs"
    assert body["nurbs_ingested_count"] == 2

    local = tmp_path / body["file_reference"].rsplit("/", 1)[1]
    model = rhino3dm.File3dm.Read(str(local))
    assert model is not None                                   # .3dm reopened
    breps = [o for o in model.Objects if isinstance(getattr(o, "Geometry", None), rhino3dm.Brep)]
    assert len(breps) == 2                                     # the NURBS hull is INSIDE
