"""Module 10 tests (9, 10): invalid-geometry rejection + export integrity."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.reconstruct.contract import InvalidGeometryError
from app.services.reconstruct.meshes import (
    export_download_formats,
    export_glb,
    export_obj,
    inspect_mesh,
)

from .reconstruct_helpers import make_glb, make_image


def _write_glb(tmp_path, name="model.glb") -> Path:
    p = tmp_path / name
    p.write_bytes(make_glb())
    return p


@pytest.fixture()
def workdir(tmp_path):
    return tmp_path


# -- 9. invalid geometry rejection ------------------------------------------
def test_inspect_reports_real_mesh_metrics(workdir):
    m = inspect_mesh(_write_glb(workdir))
    assert m.vertex_count > 0
    assert m.triangle_count > 0
    assert m.size_m > 0
    assert m.bounds[0][0] <= m.bounds[1][0]


def test_inspect_rejects_empty_file(workdir):
    empty = workdir / "empty.glb"
    empty.write_bytes(b"")
    with pytest.raises(InvalidGeometryError) as exc:
        inspect_mesh(empty)
    assert "cannot read" in str(exc.value)


def test_inspect_rejects_garbage_bytes(workdir):
    garbage = workdir / "junk.glb"
    garbage.write_bytes(b"glTF" + b"\x00" * 8 + b"nonsense")
    with pytest.raises(InvalidGeometryError):
        inspect_mesh(garbage)


def test_inspect_rejects_text_as_glb(workdir):
    txt = workdir / "fake.glb"
    txt.write_text("this is not a 3d model at all")
    with pytest.raises(InvalidGeometryError):
        inspect_mesh(txt)


def test_inspect_rejects_zero_geometry(workdir):
    import trimesh
    empty_mesh = trimesh.Trimesh(vertices=[], faces=[])
    p = workdir / "empty_mesh.glb"
    p.write_bytes(trimesh.exchange.gltf.export_glb(empty_mesh))
    with pytest.raises(InvalidGeometryError) as exc:
        inspect_mesh(p)
    assert "empty" in str(exc.value)


def test_service_rejects_invalid_provider_output(workdir, monkeypatch):
    """Worker must fail the job when the provider returns garbage."""
    from app.services.reconstruct.contract import JobMetadata, ReconstructionProvider
    from app.services.reconstruct.service import ReconstructionService

    class GarbageProvider(ReconstructionProvider):
        name = "garbage"

        def is_configured(self):
            return True

        def configuration_problem(self):
            return None

        def reconstruct(self, image_paths, work_dir, *, timeout_seconds,
                        metadata=None):
            p = Path(work_dir) / "model.glb"
            p.write_bytes(b"glTF not really")
            return p

    service = ReconstructionService(storage_dir=workdir, environment="development")
    service._provider = GarbageProvider()  # noqa: SLF001
    from app.services.reconstruct.validation import UploadedFile
    job = service.create_job([UploadedFile("a.jpg", make_image("JPEG"))])[0]
    service.start(job["id"])
    import time
    deadline = time.time() + 15
    while time.time() < deadline:
        j = service.jobs.get(job["id"])
        if j.status.value == "failed":
            assert "cannot read" in (j.error or "")
            return
        time.sleep(0.05)
    pytest.fail("job did not fail as expected")


# -- 10. exported model integrity --------------------------------------------
def test_export_glb_reopens_and_passes_inspection(workdir):
    src = _write_glb(workdir)
    dst = export_glb(src, workdir / "export.glb")
    assert dst.is_file() and dst.stat().st_size > 0
    assert dst.read_bytes()[:4] == b"glTF"
    m = inspect_mesh(dst)  # re-open = integrity proof
    assert m.vertex_count > 0


def test_export_obj_reopens(workdir):
    src = _write_glb(workdir)
    dst = export_obj(src, workdir / "export.obj")
    assert dst.is_file()
    text = dst.read_text()
    assert "v " in text and ("f " in text or "o " in text)


def test_export_formats_are_derived_not_original(workdir):
    src = _write_glb(workdir)
    glb, obj = export_download_formats(src, workdir)
    assert glb.name == "export.glb" and obj.name == "export.obj"
    # original untouched
    assert src.name == "model.glb" and src.exists()


def test_export_from_garbage_raises(workdir):
    junk = workdir / "junk.glb"
    junk.write_bytes(b"glTF\x00 garbage")
    with pytest.raises(InvalidGeometryError):
        export_glb(junk, workdir / "x.glb")
    with pytest.raises(InvalidGeometryError):
        export_obj(junk, workdir / "x.obj")
