"""Module 10 — labelled DEVELOPMENT MOCK provider.

This provider does NOT run AI reconstruction. It builds a deterministic
placeholder mesh (a simple boat-like prism) purely so the full workflow
(upload -> job -> viewer -> download) can be exercised on machines without
a GPU or TRELLIS installation.

SAFETY RULES (enforced in code, not by convention):
- ``RECONSTRUCTION_PROVIDER=mock`` is refused whenever
  ``MARLIN_ENVIRONMENT=production``. The mock can NEVER run in production.
- Every job produced by the mock is flagged ``simulated=true`` and the API
  response carries an explicit "SIMULATED — NOT AI RECONSTRUCTION" banner.
- The mock NEVER claims to have run an AI engine.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from .contract import (
    JobMetadata,
    ReconstructionProvider,
)

TRUTH = {
    "simulated": True,
    "explanation": (
        "SIMULATED MESH — this job used the labelled development mock "
        "provider, not AI reconstruction. Enable the real engine "
        "(RECONSTRUCTION_PROVIDER=trellis) for genuine AI output."
    ),
}


class MockProvider(ReconstructionProvider):
    name = "mock"

    def is_configured(self) -> bool:
        return self.configuration_problem() is None

    def configuration_problem(self) -> str | None:
        return None  # the service refuses mock in production before here

    def reconstruct(
        self,
        image_paths: list[Path],
        work_dir: Path,
        *,
        timeout_seconds: float,
        metadata: JobMetadata | None = None,
    ) -> Path:
        """Build a fixed, labelled placeholder GLB via trimesh primitives."""
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        out = work_dir / "model.glb"

        tm_module = _trimesh()
        hull = tm_module.primitives.Box(extents=(6.0, 1.8, 0.6))
        hull.apply_translation((0.0, 0.0, -0.3))
        cabin = tm_module.primitives.Box(extents=(2.4, 1.0, 0.7))
        cabin.apply_translation((0.4, 0.0, 0.55))
        scene = tm_module.Scene([hull, cabin])
        # Label the geometry so any consumer can see it is simulated.
        scene.metadata.update(TRUTH)
        scene.export(str(out))
        meta_note = {
            **_note(metadata),
            **TRUTH,
            "provider": "mock",
        }
        (work_dir / "mock_provider.json").write_text(
            json.dumps(meta_note, indent=2))
        # Bake the banner into the GLB metadata too (survives export).
        try:
            gltf = tm_module.load(str(out), force="scene")
            gltf.metadata.update(TRUTH)
            gltf.export(str(out))
        except Exception:  # noqa: BLE001
            pass
        return out


def _note(metadata: JobMetadata | None) -> dict:
    if metadata is None:
        return {}
    return {
        "vessel_length_m": metadata.vessel_length_m,
        "vessel_beam_m": metadata.vessel_beam_m,
        "reference_note": metadata.reference_note,
    }


def _trimesh():
    import trimesh  # noqa: PLC0415
    return trimesh
