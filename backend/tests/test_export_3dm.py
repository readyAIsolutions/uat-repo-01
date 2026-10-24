import tempfile
import os
import rhino3dm
from fastapi.testclient import TestClient
from tests.stubs.rhino_stub import rhino_stub


def test_build_3dm_roundtrips_through_rhino3dm():
    from app.services.vessel.stations import build_station_plan
    from app.services.vessel.export_3dm import build_stations_3dm
    plan = build_station_plan(loa=20, beam=5.5, draft=1.2, depth=2.4, station_count=15)
    data = build_stations_3dm(plan)
    assert isinstance(data, bytes) and len(data) > 100
    with tempfile.NamedTemporaryFile(suffix=".3dm", delete=False) as f:
        f.write(data)
        path = f.name
    try:
        model = rhino3dm.File3dm.Read(path)
        assert model is not None
        assert len(model.Objects) >= 15  # 15 station curves (+ reference curves)
    finally:
        os.unlink(path)


def test_hull_writes_downloadable_3dm(monkeypatch, tmp_path):
    from app.mvp import create_app
    payload = {
        "project_id": "MARLIN-001", "units": "meters",
        "loa": {"value": 20, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
        "lwl": {"value": 18.5, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
        "beam": {"value": 5.5, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
        "draft": {"value": 1.2, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
        "depth": {"value": 2.4, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
        "hull_family": "MONOHULL", "station_count": 15,
    }
    with rhino_stub() as (server, base):
        monkeypatch.setenv("RHINO_COMPUTE_URL", base)
        monkeypatch.setenv("MARLIN_STORAGE_DIR", str(tmp_path))
        with TestClient(create_app()) as client:
            body = client.post("/api/vessel/hull", json=payload).json()
            ref = body["file_reference"]
            assert ref.startswith("/api/vessel/hull/3dm/")
            assert body["geometry_source"] == "marlin_parameters"
            assert body["file_bytes"] > 100
            download = client.get(ref)
            assert download.status_code == 200
            assert download.headers["content-type"] == "application/octet-stream"
            # the served bytes are a real .3dm
            local = tmp_path / ref.rsplit("/", 1)[1]
            assert local.is_file()
            assert rhino3dm.File3dm.Read(str(local)) is not None
            # path traversal is refused
            bad = client.get("/api/vessel/hull/3dm/..%2f..%2fpyproject.toml")
            assert bad.status_code in (404, 400)
