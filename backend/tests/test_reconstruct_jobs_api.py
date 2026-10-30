"""Module 10 tests (3, 4, 8): jobs API end-to-end via the labelled mock.

These exercise the REAL API + REAL job store + REAL mesh pipeline with the
development mock provider. Every job produced here carries simulated=true —
that is the honest distinction between mocked and real AI reconstruction.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from .reconstruct_helpers import make_image


@pytest.fixture()
def mock_client(monkeypatch):
    monkeypatch.setenv("RECONSTRUCTION_PROVIDER", "mock")
    from app.mvp import create_app
    with TestClient(create_app()) as client:
        yield client


def _slow_provider(client, delay=5.0):
    """Swap in a provider that sleeps, so lifecycle tests are deterministic."""
    from app.services.reconstruct.contract import ReconstructionProvider
    import time as _t

    class Slow(ReconstructionProvider):
        name = "slow"

        def is_configured(self):
            return True

        def configuration_problem(self):
            return None

        def reconstruct(self, image_paths, work_dir, *, timeout_seconds,
                        metadata=None):
            _t.sleep(delay)
            from pathlib import Path
            from .reconstruct_helpers import make_glb
            p = Path(work_dir) / "model.glb"
            p.write_bytes(make_glb())
            return p

    service = client.app.state.reconstruction_service
    service._provider = Slow()  # noqa: SLF001
    return service


def _files(*names):
    files = []
    for n in names:
        if n.endswith(".png"):
            fmt, ctype = "PNG", "image/png"
        elif n.endswith(".webp"):
            fmt, ctype = "WEBP", "image/webp"
        else:
            fmt, ctype = "JPEG", "image/jpeg"
        files.append(("images", (n, make_image(fmt), ctype)))
    return files


def _wait_success(client, job_id, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/reconstruct/jobs/{job_id}").json()
        if body["status"] == "succeeded":
            return body
        if body["status"] in ("failed", "canceled"):
            pytest.fail(f"job ended {body['status']}: {body.get('error')}")
        time.sleep(0.1)
    pytest.fail("job did not finish in time")


# -- 3. multiple-image handling ---------------------------------------------
def test_multi_image_job_succeeds_and_is_labelled_simulated(mock_client):
    r = mock_client.post(
        "/api/reconstruct/jobs",
        files=_files("bow.jpg", "side.jpg", "stern.png"))
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["status"] == "queued"
    assert len(job["images"]) == 3
    assert {i["format"] for i in job["images"]} == {"JPEG", "PNG"}

    done = _wait_success(mock_client, job["id"])
    assert done["simulated"] is True
    assert done["provider"] == "mock"
    assert any("SIMULATED" in w for w in done["warnings"])
    assert done["vertex_count"] > 0 and done["triangle_count"] > 0
    assert done["result_model"] == "model.glb"
    assert done["exported_glb"] and done["exported_obj"]


def test_single_image_job_succeeds(mock_client):
    r = mock_client.post("/api/reconstruct/jobs",
                         files=_files("boat.jpg"))
    assert r.status_code == 201
    done = _wait_success(mock_client, r.json()["id"])
    assert done["vertex_count"] > 0


def test_mixed_formats_all_accepted(mock_client):
    img_b = make_image("JPEG")
    img_p = make_image("PNG")
    img_w = make_image("WEBP")
    r = mock_client.post("/api/reconstruct/jobs", files=[
        ("images", ("a.jpg", img_b, "image/jpeg")),
        ("images", ("b.png", img_p, "image/png")),
        ("images", ("c.webp", img_w, "image/webp")),
    ])
    assert r.status_code == 201, r.text
    assert {i["format"] for i in r.json()["images"]} == {"JPEG", "PNG", "WEBP"}


def test_reference_metadata_is_preserved(mock_client):
    r = mock_client.post(
        "/api/reconstruct/jobs",
        files=_files("boat.jpg"),
        data={"vessel_length_m": "12.5", "vessel_beam_m": "4.2",
              "reference_note": "measured at gunwale"})
    assert r.status_code == 201
    job = r.json()
    assert job["metadata"]["vessel_length_m"] == 12.5
    assert job["metadata"]["vessel_beam_m"] == 4.2
    assert job["metadata"]["reference_note"] == "measured at gunwale"


def test_too_many_images_rejected(mock_client):
    files = _files(*[f"f{i}.jpg" for i in range(11)])
    r = mock_client.post("/api/reconstruct/jobs", files=files)
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "IMAGE_LIMIT_EXCEEDED"


def test_no_images_rejected(mock_client):
    r = mock_client.post("/api/reconstruct/jobs")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "IMAGES_REQUIRED"


def test_one_bad_file_among_good_rejects_whole_submission(mock_client):
    files = [("images", ("good.jpg", make_image("JPEG"), "image/jpeg")),
             ("images", ("evil.txt", b"not an image", "text/plain"))]
    r = mock_client.post("/api/reconstruct/jobs", files=files)
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "IMAGE_VALIDATION_FAILED"
    details = body["error"]["details"]
    assert any("magic" in p or "extension" in p or "not a JPEG" in p
               for p in details)


def test_oversized_upload_rejected(mock_client):
    big = b"\xff\xd8\xff" + b"\x00" * (11 * 1024 * 1024)
    r = mock_client.post("/api/reconstruct/jobs",
                         files=[("images", ("huge.jpg", big, "image/jpeg"))])
    assert r.status_code == 422


# -- 4. job creation + lifecycle --------------------------------------------
def test_capabilities_reports_mock_and_simulation_flag(mock_client):
    body = mock_client.get("/api/reconstruct/capabilities").json()
    assert body["provider"] == "mock"
    assert body["configured"] is True
    assert body["simulated_available"] is True


def test_production_refuses_mock_submission(monkeypatch):
    """The labelled mock can NEVER accept jobs in production."""
    monkeypatch.setenv("MARLIN_ENVIRONMENT", "production")
    monkeypatch.setenv("RECONSTRUCTION_PROVIDER", "mock")
    from app.mvp import create_app
    with TestClient(create_app()) as client:
        caps = client.get("/api/reconstruct/capabilities").json()
        assert caps["configured"] is False
        r = client.post("/api/reconstruct/jobs", files=_files("a.jpg"))
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"


def test_unconfigured_trellis_refuses_submission(monkeypatch):
    monkeypatch.setenv("RECONSTRUCTION_PROVIDER", "trellis")
    monkeypatch.delenv("RECONSTRUCTION_TRELLIS_PYTHON", raising=False)
    from app.mvp import create_app
    with TestClient(create_app()) as client:
        r = client.post("/api/reconstruct/jobs", files=_files("a.jpg"))
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"


def test_unknown_job_404(mock_client):
    assert mock_client.get(
        "/api/reconstruct/jobs/00000000-0000-0000-0000-000000000000"
    ).status_code == 404


def test_cancel_queued_job(mock_client):
    _slow_provider(mock_client)
    r = mock_client.post("/api/reconstruct/jobs", files=_files("a.jpg"))
    job_id = r.json()["id"]
    c = mock_client.post(f"/api/reconstruct/jobs/{job_id}/cancel")
    assert c.status_code == 200
    assert c.json()["status"] == "canceled"


def test_cancel_terminal_job_conflict(mock_client):
    r = mock_client.post("/api/reconstruct/jobs", files=_files("a.jpg"))
    job_id = r.json()["id"]
    done = _wait_success(mock_client, job_id)
    assert done["status"] == "succeeded"
    c = mock_client.post(f"/api/reconstruct/jobs/{job_id}/cancel")
    assert c.status_code == 409


# -- 8. model retrieval ------------------------------------------------------
def test_export_downloads_are_valid(mock_client):
    r = mock_client.post("/api/reconstruct/jobs", files=_files("boat.jpg"))
    job_id = r.json()["id"]
    _wait_success(mock_client, job_id)

    glb = mock_client.get(
        f"/api/reconstruct/jobs/{job_id}/export", params={"format": "glb"})
    assert glb.status_code == 200
    assert glb.content[:4] == b"glTF"  # real GLB magic

    obj = mock_client.get(
        f"/api/reconstruct/jobs/{job_id}/export", params={"format": "obj"})
    assert obj.status_code == 200
    assert obj.content.startswith((b"o ", b"#", b"v "))

    orig = mock_client.get(f"/api/reconstruct/jobs/{job_id}/model")
    assert orig.status_code == 200
    assert orig.content[:4] == b"glTF"


def test_download_invalid_format_rejected(mock_client):
    r = mock_client.post("/api/reconstruct/jobs", files=_files("a.jpg"))
    job_id = r.json()["id"]
    _wait_success(mock_client, job_id)
    assert mock_client.get(f"/api/reconstruct/jobs/{job_id}/export",
                           params={"format": "stl"}).status_code == 422


def test_download_before_success_conflict(mock_client):
    _slow_provider(mock_client)
    r = mock_client.post("/api/reconstruct/jobs", files=_files("a.jpg"))
    job_id = r.json()["id"]
    got = mock_client.get(f"/api/reconstruct/jobs/{job_id}/export",
                          params={"format": "glb"})
    assert got.status_code == 409


def test_stored_image_preview_served(mock_client):
    r = mock_client.post("/api/reconstruct/jobs", files=_files("bow.jpg"))
    job_id = r.json()["id"]
    img = mock_client.get(f"/api/reconstruct/jobs/{job_id}/images/0")
    assert img.status_code == 200
    assert img.headers["content-type"].startswith("image/")


def test_job_list_returns_recent_jobs(mock_client):
    mock_client.post("/api/reconstruct/jobs", files=_files("a.jpg"))
    body = mock_client.get("/api/reconstruct/jobs").json()
    assert body["count"] >= 1
    assert all("id" in j for j in body["jobs"])
