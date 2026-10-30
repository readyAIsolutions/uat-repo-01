"""Module 10 — reconstruction job store and lifecycle.

Jobs persist as JSON files under ``<storage>/reconstruction/<job_id>/`` so a
restart of the API does not lose in-flight or finished jobs. File layout:

    <job_id>/
        meta.json           full job record (status, warnings, metrics)
        images/<n>_<name>   original uploads (secure, extension-checked)
        model.glb           provider's original mesh output
        export.glb          validated/exported GLB (may equal model.glb)
        export.obj          exported OBJ (sidecar .mtl optional)
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid
from pathlib import Path

from .contract import (
    TERMINAL_STATUSES,
    JobMetadata,
    JobNotFound,
    JobStatus,
    ReconstructionJob,
    ReconstructionError,
)

_JOB_ID_RE = re.compile(r"^[a-f0-9-]{36}$")


class JobStore:
    """Thread-safe, JSON-persisted job registry."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    # -- paths ---------------------------------------------------------
    def job_dir(self, job_id: str) -> Path:
        if not _JOB_ID_RE.match(job_id):
            raise JobNotFound(job_id)
        return self.root / job_id

    def images_dir(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "images"

    def meta_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "meta.json"

    def result_path(self, job_id: str) -> Path | None:
        job = self.get(job_id)
        if not job.result_model:
            return None
        return self.job_dir(job_id) / job.result_model

    def export_path(self, job_id: str, kind: str) -> Path | None:
        job = self.get(job_id)
        name = job.exported_glb if kind == "glb" else job.exported_obj
        if not name:
            return None
        return self.job_dir(job_id) / name

    # -- lifecycle -------------------------------------------------------
    def create(self, *, metadata: JobMetadata | None = None) -> ReconstructionJob:
        job_id = str(uuid.uuid4())
        job = ReconstructionJob(id=job_id, status=JobStatus.QUEUED,
                                metadata=metadata or JobMetadata())
        with self._lock:
            self.job_dir(job_id).mkdir(parents=True, exist_ok=True)
            self.images_dir(job_id).mkdir(parents=True, exist_ok=True)
            self._write(job)
        return job

    def get(self, job_id: str) -> ReconstructionJob:
        with self._lock:
            path = self.meta_path(job_id)
            if not path.is_file():
                raise JobNotFound(job_id)
            try:
                return ReconstructionJob.from_dict(json.loads(path.read_text()))
            except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                raise JobNotFound(job_id) from None

    def list(self, limit: int = 50) -> list[ReconstructionJob]:
        with self._lock:
            jobs = []
            for meta in sorted(self.root.glob("*/meta.json"),
                               key=lambda p: p.stat().st_mtime, reverse=True):
                try:
                    jobs.append(ReconstructionJob.from_dict(
                        json.loads(meta.read_text())))
                except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                    continue
                if len(jobs) >= limit:
                    break
            return jobs

    def transition(self, job_id: str, status: JobStatus,
                   *, error: str | None = None,
                   provider: str | None = None,
                   provider_model: str | None = None,
                   warnings: list[str] | None = None,
                   result_model: str | None = None,
                   exported_glb: str | None = None,
                   exported_obj: str | None = None,
                   output_bytes: int | None = None,
                   vertex_count: int | None = None,
                   triangle_count: int | None = None,
                   simulated: bool | None = None) -> ReconstructionJob:
        """Apply a state change and persist. Returns the updated job."""
        with self._lock:
            job = self.get(job_id)
            now = time.time()
            # Invariants: a terminal job never changes; a canceled job can
            # only stay canceled (protects against worker/cancel races).
            if job.status in TERMINAL_STATUSES and status is not job.status:
                return job
            if job.status is JobStatus.CANCELED and status is not JobStatus.CANCELED:
                return job
            job.status = status
            job.updated_at = now
            if status is JobStatus.PROCESSING and job.started_at is None:
                job.started_at = now
            if status in TERMINAL_STATUSES:
                job.finished_at = now
            if error is not None:
                job.error = error
            if provider is not None:
                job.provider = provider
            if provider_model is not None:
                job.provider_model = provider_model
            if warnings is not None:
                job.warnings = list(warnings)
            if result_model is not None:
                job.result_model = result_model
            if exported_glb is not None:
                job.exported_glb = exported_glb
            if exported_obj is not None:
                job.exported_obj = exported_obj
            if output_bytes is not None:
                job.output_bytes = output_bytes
            if vertex_count is not None:
                job.vertex_count = vertex_count
            if triangle_count is not None:
                job.triangle_count = triangle_count
            if simulated is not None:
                job.simulated = simulated
            self._write(job)
            return job

    def set_images(self, job_id: str,
                   images: list) -> ReconstructionJob:
        """Persist stored image records on a queued job."""
        with self._lock:
            job = self.get(job_id)
            job.images = list(images)
            job.updated_at = time.time()
            self._write(job)
            return job

    def add_warning(self, job_id: str, warning: str) -> ReconstructionJob:
        with self._lock:
            job = self.get(job_id)
            job.warnings.append(warning)
            job.updated_at = time.time()
            self._write(job)
            return job

    def delete(self, job_id: str) -> None:
        with self._lock:
            self.get(job_id)  # raises if unknown
            import shutil
            shutil.rmtree(self.job_dir(job_id), ignore_errors=True)

    def _write(self, job: ReconstructionJob) -> None:
        payload = json.dumps(job.to_dict(), indent=2, sort_keys=True)
        tmp = self.meta_path(job.id).with_suffix(".json.tmp")
        tmp.write_text(payload)
        tmp.replace(self.meta_path(job.id))
