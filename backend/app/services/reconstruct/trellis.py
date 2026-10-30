"""Module 10 — TRELLIS (Microsoft) provider adapter.

Runs the official TRELLIS image-to-3D pipeline as an ISOLATED subprocess:

    RECONSTRUCTION_TRELLIS_PYTHON  -> python of the TRELLIS env (conda)
    reconstruction/trellis_entrypoint.py <job_dir> <image>... [--model NAME]

The API process never imports trellis/pytorch; the heavy CUDA stack lives in
the TRELLIS environment (typically on the GPU workstation / Dell). The adapter:

- reports honestly when the TRELLIS interpreter is missing/unusable,
- streams the subprocess output into the job log,
- treats non-zero exit / JSON parse failure / missing GLB as real failures,
- NEVER fabricates a mesh.

Live facts verified from https://github.com/microsoft/TRELLIS (README):
- pipeline: ``TrellisImageTo3DPipeline.from_pretrained("microsoft/TRELLIS-image-large")``
- single image:   ``pipeline.run(image)``
- multi-view:     ``pipeline.run_multi_image([images])``  (tuning-free)
- GLB export:     ``postprocessing_utils.to_glb(gaussian, mesh, ...)``
- requires Linux + NVIDIA GPU >= 16GB VRAM (verified on A100/A6000).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from ...core.env import env_flag
from .contract import (
    JobMetadata,
    InvalidGeometryError,
    ProviderAuthError,
    ProviderRejected,
    ProviderTimeout,
    ReconstructionProvider,
)

DEFAULT_MODEL = "microsoft/TRELLIS-image-large"


class TrellisProvider(ReconstructionProvider):
    name = "trellis"

    def __init__(self, *, python: str | None = None,
                 model: str = DEFAULT_MODEL,
                 entrypoint: Path | None = None):
        self.python = python or env_flag("RECONSTRUCTION_TRELLIS_PYTHON")
        self.model = model or env_flag("RECONSTRUCTION_TRELLIS_MODEL") or DEFAULT_MODEL
        # entrypoint resolves relative to the repo root by default.
        if entrypoint is None:
            repo_root = Path(__file__).resolve().parents[4]  # backend/app/services/reconstruct -> repo root
            entrypoint = repo_root / "reconstruction" / "trellis_entrypoint.py"
        self.entrypoint = Path(entrypoint)

    def is_configured(self) -> bool:
        return self.configuration_problem() is None

    def configuration_problem(self) -> str | None:
        if not self.python:
            return ("TRELLIS not configured: set RECONSTRUCTION_TRELLIS_PYTHON "
                    "to the python of the TRELLIS conda env (GPU workstation)")
        if not Path(self.python).is_file():
            return f"TRELLIS python not found: {self.python}"
        if not self.entrypoint.is_file():
            return f"TRELLIS entrypoint missing: {self.entrypoint}"
        return None

    def reconstruct(
        self,
        image_paths: list[Path],
        work_dir: Path,
        *,
        timeout_seconds: float,
        metadata: JobMetadata | None = None,
    ) -> Path:
        problem = self.configuration_problem()
        if problem:
            raise ProviderAuthError(problem) if "not configured" in problem \
                else ProviderTimeout(problem)
        # Keep it honest: configuration_problem covers missing pieces.
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        log_path = work_dir / "provider.log"

        cmd = [
            self.python, str(self.entrypoint),
            "--job-dir", str(work_dir),
            "--model", self.model,
            *[str(p) for p in image_paths],
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=str(work_dir),
            )
        except subprocess.TimeoutExpired as exc:
            log_path.write_text(f"TIMEOUT after {timeout_seconds}s\n")
            raise ProviderTimeout(
                f"TRELLIS did not finish within {timeout_seconds:g}s "
                f"(GPU job may need more time; see provider.log)") from exc

        log_path.write_text(f"cmd: {' '.join(cmd)}\nexit={proc.returncode}\n"
                            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}")

        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-8:]
            detail = "\n".join(tail)
            if "auth" in detail.lower() or "license" in detail.lower() \
                    or "forbidden" in detail.lower() or "401" in detail:
                raise ProviderAuthError(
                    f"TRELLIS rejected credentials/license:\n{detail}")
            raise ProviderRejected(
                f"TRELLIS exited {proc.returncode}:\n{detail}")

        # Parse JSON summary the entrypoint printed.
        try:
            summary = json.loads(proc.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            summary = {}
        out_name = summary.get("output_glb")
        if not out_name:
            raise InvalidGeometryError(
                "TRELLIS reported no output GLB (see provider.log)")

        out_path = work_dir / out_name
        if not out_path.is_file() or out_path.stat().st_size == 0:
            raise InvalidGeometryError(
                f"TRELLIS output missing/empty: {out_path}")
        return out_path


def available_python_candidates() -> list[str]:
    """Interpreters that might host TRELLIS (for the capabilities endpoint)."""
    cands = [
        env_flag("RECONSTRUCTION_TRELLIS_PYTHON"),
        shutil.which("python"),
        shutil.which("python3"),
    ]
    return [c for c in cands if c]
