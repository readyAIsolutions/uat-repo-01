"""Module 10 — reconstruction service (orchestration).

Wires uploads -> jobs -> provider -> validation -> exports, and answers the
status/download endpoints. Work runs on a daemon thread per job so the API
stays responsive; the job row is persisted after every transition.

Honesty rules baked in here:
- provider selection reads RECONSTRUCTION_PROVIDER (trellis | mock).
- mock is REFUSED in production (MARLIN_ENVIRONMENT=production).
- a job can only reach "succeeded" after the mesh passed real validation.
- provider original output is preserved untouched; exports are derived.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from ...core.env import env_flag, env_float, env_int
from .contract import (
    JobMetadata,
    JobStatus,
    ProviderTimeout,
    ReconstructionError,
    ReconstructionProvider,
)
from .jobs import JobStore
from .meshes import export_download_formats, inspect_mesh
from .mock_provider import MockProvider
from .trellis import TrellisProvider
from .validation import UploadedFile, validate_image

DEFAULT_MAX_IMAGES = 10
DEFAULT_MAX_IMAGE_MB = 10
DEFAULT_TIMEOUT_S = 900.0


class ProviderNotAllowed(ReconstructionError):
    """Chosen provider is not permitted in this environment."""


class ReconstructionService:
    def __init__(self, *, storage_dir: str | Path,
                 environment: str = "development",
                 provider_name: str | None = None,
                 max_images: int = DEFAULT_MAX_IMAGES,
                 max_image_bytes: int = DEFAULT_MAX_IMAGE_MB * 1024 * 1024,
                 timeout_seconds: float = DEFAULT_TIMEOUT_S):
        self.environment = environment
        self.max_images = max_images
        self.max_image_bytes = max_image_bytes
        self.timeout_seconds = timeout_seconds
        self.storage_dir = Path(storage_dir)
        self.jobs = JobStore(self.storage_dir / "reconstruction")
        self._provider_name = provider_name or env_flag("RECONSTRUCTION_PROVIDER") \
            or "trellis"
        self._provider: ReconstructionProvider | None = None
        self._threads: dict[str, threading.Thread] = {}

    # -- provider ---------------------------------------------------------
    def provider(self) -> ReconstructionProvider:
        if self._provider is None:
            self._provider = self._build_provider(self._provider_name)
        return self._provider

    def _build_provider(self, name: str) -> ReconstructionProvider:
        if name == "trellis":
            return TrellisProvider()
        if name == "mock":
            if self.environment == "production":
                raise ProviderNotAllowed(
                    "RECONSTRUCTION_PROVIDER=mock is forbidden in production "
                    "because it does not run AI reconstruction")
            return MockProvider()
        raise ProviderNotAllowed(
            f"unknown RECONSTRUCTION_PROVIDER={name!r} "
            "(supported: trellis, mock)")

    def capabilities(self) -> dict:
        problem = None
        try:
            provider = self.provider()
        except ProviderNotAllowed as exc:
            return {
                "provider": self._provider_name,
                "configured": False,
                "simulated_available": self.environment != "production",
                "environment": self.environment,
                "problem": str(exc),
            }
        problem = provider.configuration_problem()
        return {
            "provider": self._provider_name,
            "configured": problem is None,
            "simulated_available": self.environment != "production",
            "environment": self.environment,
            "problem": problem,
        }

    # -- upload -> job ----------------------------------------------------
    def create_job(
        self,
        files: list[UploadedFile],
        *,
        vessel_length_m: float | None = None,
        vessel_beam_m: float | None = None,
        reference_note: str | None = None,
    ) -> tuple[dict, int]:
        """Validate + store uploads and create a queued job.

        Returns (job_dict, http_status). 422 with problems when input is bad;
        otherwise 201. Provider availability is NOT checked at submission
        time so queued jobs survive brief provider restarts; the worker
        reports the honest failure if the provider cannot run.
        """
        if not files:
            return {"detail": "at least one photograph is required"}, 422
        if len(files) > self.max_images:
            return {
                "detail": f"at most {self.max_images} photographs per job"
            }, 413

        problems: list[str] = []
        validated = []
        for upload in files:
            try:
                fmt, w, h = validate_image(upload, max_bytes=self.max_image_bytes)
            except ReconstructionError as exc:
                problems.extend(getattr(exc, "problems",
                                        [str(exc)]))
                continue
            validated.append((upload, fmt, w, h))
        if problems:
            return {"detail": "image validation failed", "problems": problems}, 422
        if not validated:
            return {"detail": "no valid photographs provided"}, 422

        metadata = JobMetadata(
            vessel_length_m=vessel_length_m,
            vessel_beam_m=vessel_beam_m,
            reference_note=reference_note or None,
        )
        job = self.jobs.create(metadata=metadata)
        images_dir = self.jobs.images_dir(job.id)
        stored = []
        for idx, (upload, fmt, w, h) in enumerate(validated):
            # Extension matches the sniffed format (validated earlier).
            ext = {  # noqa: E231
                "JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp",
            }[fmt]
            target = images_dir / f"{idx:02d}_{Path(upload.filename).stem}{ext}"
            target.write_bytes(upload.content)
            stored.append({
                "filename": upload.filename,
                "path": target,
                "format": fmt,
                "width": w,
                "height": h,
                "bytes": len(upload.content),
            })
        from .contract import ImageSubmission  # noqa: PLC0415
        self.jobs.set_images(job.id, [ImageSubmission(**s) for s in stored])
        return self.jobs.get(job.id).to_dict(), 201

    def start(self, job_id: str) -> None:
        """Launch the worker thread for a queued job (idempotent)."""
        with self.jobs._lock:  # noqa: SLF001
            job = self.jobs.get(job_id)
            if job.status is not JobStatus.QUEUED:
                return
            self.jobs.transition(job_id, JobStatus.PROCESSING)
            thread = threading.Thread(
                target=self._run_job, args=(job_id,), daemon=True)
            self._threads[job_id] = thread
            thread.start()

    def _run_job(self, job_id: str) -> None:
        # start() already transitioned QUEUED -> PROCESSING and guarantees a
        # single thread per job; cancellation is honoured mid-flight below.
        job = self.jobs.get(job_id)
        work_dir = self.jobs.job_dir(job_id)
        image_paths = [p for p in sorted(
            (work_dir / "images").glob("*"))
            if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
        try:
            provider = self.provider()
            problem = provider.configuration_problem()
            if problem:
                self.jobs.transition(
                    job_id, JobStatus.FAILED,
                    error=f"provider unavailable: {problem}")
                return
            self.jobs.transition(
                job_id, JobStatus.PROCESSING,
                provider=provider.name,
                provider_model=getattr(provider, "model", ""))
            result = provider.reconstruct(
                image_paths, work_dir,
                timeout_seconds=self.timeout_seconds,
                metadata=job.metadata)
            if self.jobs.get(job_id).status is JobStatus.CANCELED:
                return  # operator canceled mid-flight: keep canceled
            inspection = inspect_mesh(result)
            glb, obj = export_download_formats(result, work_dir)
            self.jobs.transition(
                job_id, JobStatus.SUCCEEDED,
                result_model=result.name,
                exported_glb=glb.name,
                exported_obj=obj.name,
                output_bytes=result.stat().st_size,
                vertex_count=inspection.vertex_count,
                triangle_count=inspection.triangle_count,
                simulated=provider.name == "mock",
                warnings=["SIMULATED — NOT AI RECONSTRUCTION (dev mock)"
                          ] if provider.name == "mock" else [],
            )
        except ProviderTimeout as exc:
            if self.jobs.get(job_id).status is JobStatus.CANCELED:
                return
            self.jobs.transition(job_id, JobStatus.FAILED, error=str(exc))
        except ReconstructionError as exc:
            if self.jobs.get(job_id).status is JobStatus.CANCELED:
                return
            self.jobs.transition(job_id, JobStatus.FAILED, error=str(exc))
        except Exception as exc:  # noqa: BLE001 - never let the thread die silently
            if self.jobs.get(job_id).status is JobStatus.CANCELED:
                return
            self.jobs.transition(
                job_id, JobStatus.FAILED,
                error=f"internal error: {exc.__class__.__name__}: {exc}")

    def cancel(self, job_id: str) -> tuple[dict, int]:
        job = self.jobs.get(job_id)
        if job.status in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELED):
            return {"detail": f"job already {job.status.value}"}, 409
        updated = self.jobs.transition(job_id, JobStatus.CANCELED,
                                       error="canceled by operator")
        return updated.to_dict(), 200
