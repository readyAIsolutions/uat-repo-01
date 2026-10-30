"""Module 10 — GENUINE LIVE reconstruction test.

This test runs the REAL TRELLIS engine against a real boat photograph and is
SKIPPED unless the operator opts in:

    RECONSTRUCTION_RUN_LIVE=1 RECONSTRUCTION_TRELLIS_PYTHON=<trellis env python> \\
        .venv-m10/bin/pytest backend/tests/test_reconstruct_live.py -v

It is the ONLY place Module 10 claims real AI reconstruction, and it asserts
hard facts (non-empty mesh, real GLB magic, vertex counts). If this test is
skipped, Module 10's acceptance condition "real engine processed an image"
is NOT satisfied — review the final report for how to run it on the Dell.
"""
from __future__ import annotations

import os
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RECONSTRUCTION_RUN_LIVE") != "1",
    reason=("live AI reconstruction requires opt-in "
            "(RECONSTRUCTION_RUN_LIVE=1) plus a TRELLIS/GPU host"))


def _trellis_python() -> str:
    python = os.environ.get("RECONSTRUCTION_TRELLIS_PYTHON", "")
    if not python or not Path(python).is_file():
        pytest.skip("RECONSTRUCTION_TRELLIS_PYTHON not set / not found")
    return python


def _sample_boat_image() -> Path:
    p = Path(os.environ.get("RECONSTRUCTION_SAMPLE_IMAGE", ""))
    if not p.is_file():
        # Fall back to demo/ if present (added by the demo step).
        default = Path(__file__).resolve().parents[2] / "demo" / "boat_photo.jpg"
        if default.is_file():
            return default
        pytest.skip("no sample boat image (set RECONSTRUCTION_SAMPLE_IMAGE)")
    return p


def test_real_trellis_reconstructs_boat(tmp_path):
    """The acceptance gate: photograph -> real TRELLIS -> nonempty GLB."""
    from app.services.reconstruct.trellis import TrellisProvider

    image = _sample_boat_image()
    python = _trellis_python()
    provider = TrellisProvider(python=python)
    problem = provider.configuration_problem()
    assert problem is None, f"TRELLIS misconfigured: {problem}"

    result = provider.reconstruct(
        [image], tmp_path,
        timeout_seconds=float(os.environ.get(
            "RECONSTRUCTION_LIVE_TIMEOUT", "1800")),
    )
    assert result.is_file()
    assert result.stat().st_size > 0
    assert result.read_bytes()[:4] == b"glTF", "output is not a real GLB"

    from app.services.reconstruct.meshes import inspect_mesh
    inspection = inspect_mesh(result)  # raises if unusable
    assert inspection.vertex_count > 0
    assert inspection.triangle_count > 0

    # Full export integrity on the live output.
    from app.services.reconstruct.meshes import export_download_formats
    glb, obj = export_download_formats(result, tmp_path)
    assert glb.is_file() and obj.is_file()

    print(json.dumps({
        "live": True,
        "engine": "trellis",
        "image": str(image),
        "vertices": inspection.vertex_count,
        "triangles": inspection.triangle_count,
        "size_m": round(inspection.size_m, 3),
        "glb": str(result),
    }, indent=2))
