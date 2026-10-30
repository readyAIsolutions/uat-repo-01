"""Module 10 — image-to-3D reconstruction domain contract.

Defines the provider-agnostic interface every reconstruction engine adapter
must implement, plus the shared domain models and typed errors. Raj's Rhino
modules are NOT imported anywhere in this package.

Providers plug in behind :class:`ReconstructionProvider`. The application code
never talks to a concrete provider directly — it talks to this contract — so
TRELLIS, Tripo3D, or any future engine can be swapped in with a single config
change.
"""
from __future__ import annotations

import abc
import enum
import time
from dataclasses import dataclass, field
from pathlib import Path


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


TERMINAL_STATUSES = {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELED}


class ReconstructionError(RuntimeError):
    """Base class for all Module 10 errors."""


class ProviderUnavailable(ReconstructionError):
    """Provider is not configured or cannot be reached (honest 503)."""


class ProviderAuthError(ReconstructionError):
    """Provider rejected credentials / license."""


class ProviderTimeout(ReconstructionError):
    """Provider exceeded the processing deadline."""


class ProviderRejected(ReconstructionError):
    """Provider refused the submission (bad image, content policy, ...)."""


class InvalidGeometryError(ReconstructionError):
    """Provider returned no mesh, an empty mesh, or an unreadable file."""


class JobNotFound(ReconstructionError):
    """Unknown reconstruction job id."""


class JobNotCancelable(ReconstructionError):
    """Job already reached a terminal state."""


@dataclass
class ImageSubmission:
    """A validated, stored input photograph."""

    filename: str
    path: Path
    format: str          # JPEG | PNG | WEBP (normalised, uppercase)
    width: int
    height: int
    bytes: int


@dataclass
class JobMetadata:
    """User-provided reference dimensions (optional, never invented)."""

    vessel_length_m: float | None = None
    vessel_beam_m: float | None = None
    reference_note: str | None = None


@dataclass
class ReconstructionJob:
    """A reconstruction job as seen by the API layer."""

    id: str
    status: JobStatus
    images: list[ImageSubmission] = field(default_factory=list)
    metadata: JobMetadata = field(default_factory=JobMetadata)
    provider: str = ""
    provider_model: str = ""
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    result_model: str | None = None    # file name under job dir (original)
    exported_glb: str | None = None   # file name under job dir
    exported_obj: str | None = None    # file name under job dir
    output_bytes: int | None = None
    vertex_count: int | None = None
    triangle_count: int | None = None
    simulated: bool = False            # True ONLY for the labelled dev mock

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "status": self.status.value,
            "images": [
                {
                    "filename": i.filename,
                    "path": str(i.path),
                    "format": i.format,
                    "width": i.width,
                    "height": i.height,
                    "bytes": i.bytes,
                }
                for i in self.images
            ],
            "metadata": {
                "vessel_length_m": self.metadata.vessel_length_m,
                "vessel_beam_m": self.metadata.vessel_beam_m,
                "reference_note": self.metadata.reference_note,
            },
            "provider": self.provider,
            "provider_model": self.provider_model,
            "warnings": self.warnings,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result_model": self.result_model,
            "exported_glb": self.exported_glb,
            "exported_obj": self.exported_obj,
            "output_bytes": self.output_bytes,
            "vertex_count": self.vertex_count,
            "triangle_count": self.triangle_count,
            "simulated": self.simulated,
        }
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "ReconstructionJob":
        job = cls(id=data["id"], status=JobStatus(data["status"]))
        job.metadata = JobMetadata(**data.get("metadata", {}))
        job.images = [
            ImageSubmission(
                filename=i.get("filename", "upload"),
                path=Path(i["path"]),
                format=i.get("format", "JPEG"),
                width=i.get("width", 0),
                height=i.get("height", 0),
                bytes=i.get("bytes", 0),
            )
            for i in data.get("images", [])
        ]
        job.provider = data.get("provider", "")
        job.provider_model = data.get("provider_model", "")
        job.warnings = list(data.get("warnings", []))
        job.error = data.get("error")
        job.created_at = data.get("created_at", 0.0)
        job.updated_at = data.get("updated_at", 0.0)
        job.started_at = data.get("started_at")
        job.finished_at = data.get("finished_at")
        job.result_model = data.get("result_model")
        job.exported_glb = data.get("exported_glb")
        job.exported_obj = data.get("exported_obj")
        job.output_bytes = data.get("output_bytes")
        job.vertex_count = data.get("vertex_count")
        job.triangle_count = data.get("triangle_count")
        job.simulated = bool(data.get("simulated", False))
        return job


class ReconstructionProvider(abc.ABC):
    """Adapter interface. Implementations MUST NOT fake results.

    ``reconstruct`` runs the provider synchronously and returns the path of
    the produced mesh file (GLB preferred). Orchestration (status tracking,
    timeouts, retries) lives in the service, not in the adapter.
    """

    name: str = "abstract"

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """True when this provider can actually run on this machine."""

    @abc.abstractmethod
    def configuration_problem(self) -> str | None:
        """Human-readable reason why the provider cannot run (None if ok)."""

    @abc.abstractmethod
    def reconstruct(
        self,
        image_paths: list[Path],
        work_dir: Path,
        *,
        timeout_seconds: float,
        metadata: JobMetadata | None = None,
    ) -> Path:
        """Run reconstruction. Returns absolute path to the output GLB.

        Raises ProviderAuthError / ProviderTimeout / ProviderRejected /
        InvalidGeometryError on failure. Must NOT raise on success.
        """
