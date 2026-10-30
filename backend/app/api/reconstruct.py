"""Module 10 API routes — /api/reconstruct.

Endpoints:
  GET  /capabilities                 provider/config status (honest)
  POST /jobs                         multipart upload -> job (201)
  GET  /jobs                         recent jobs
  GET  /jobs/{id}                    status + metrics
  POST /jobs/{id}/cancel             cancel a queued/processing job
  GET  /jobs/{id}/model?format=glb   original provider mesh (preserved)
  GET  /jobs/{id}/export?format=glb|obj   validated export
  GET  /jobs/{id}/images/{idx}       stored input preview
"""
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile

from ..services.reconstruct.contract import JobNotFound
from ..services.reconstruct.service import ReconstructionService
from ..services.reconstruct.validation import UploadedFile

router = APIRouter(prefix="/api/reconstruct", tags=["reconstruct"])

# Constructor args mirror the service defaults; the app factory overrides
# them from config/env via `build_reconstruction_service`.
MAX_IMAGES = 10
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def build_reconstruction_service(
    *,
    storage_dir: str,
    environment: str,
    max_images: int = MAX_IMAGES,
    max_image_bytes: int = MAX_IMAGE_BYTES,
) -> ReconstructionService:
    return ReconstructionService(
        storage_dir=storage_dir,
        environment=environment,
        max_images=max_images,
        max_image_bytes=max_image_bytes,
    )


def _service(request: Request) -> ReconstructionService:
    service = getattr(request.app.state, "reconstruction_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="Module 10 reconstruction service is not available")
    return service


def _reject(status: int, code: str, message: str,
            details: list[str] | None = None):
    """422s use the repo's native error shape (problems survive as details)."""
    from fastapi.responses import JSONResponse
    body: dict = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(body, status_code=status)


async def _read_upload(upload: UploadFile, max_bytes: int) -> UploadedFile:
    data = await upload.read()
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=422,
            detail=f"{upload.filename}: exceeds {max_bytes} byte limit")
    return UploadedFile(filename=upload.filename or "upload", content=data)


@router.get("/capabilities")
async def capabilities(request: Request) -> dict:
    return _service(request).capabilities()


@router.post("/jobs", status_code=201)
async def create_job(request: Request,
                     images: list[UploadFile] | None = Form(None),
                     vessel_length_m: float | None = Form(None),
                     vessel_beam_m: float | None = Form(None),
                     reference_note: str | None = Form(None)):
    service = _service(request)
    files = []
    for upload in images or []:
        try:
            files.append(await _read_upload(upload, service.max_image_bytes))
        except HTTPException:
            raise
    if not files:
        return _reject(422, "IMAGES_REQUIRED",
                       "at least one photograph is required")
    body, status = service.create_job(
        files,
        vessel_length_m=vessel_length_m,
        vessel_beam_m=vessel_beam_m,
        reference_note=reference_note)
    if status != 201:
        code = "PROVIDER_UNAVAILABLE" if status == 503 else \
            ("IMAGE_VALIDATION_FAILED" if status == 422 else
             "IMAGE_LIMIT_EXCEEDED")
        return _reject(status, code,
                       body.get("detail", "invalid submission"),
                       body.get("problems"))
    service.start(body["id"])
    return body


@router.get("/jobs")
async def list_jobs(request: Request, limit: int = 20) -> dict:
    jobs = _service(request).jobs.list(limit=max(1, min(limit, 100)))
    return {"jobs": [j.to_dict() for j in jobs], "count": len(jobs)}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request) -> dict:
    try:
        return _service(request).jobs.get(job_id).to_dict()
    except JobNotFound:
        raise HTTPException(status_code=404, detail="job not found") from None


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, request: Request) -> dict:
    service = _service(request)
    try:
        body, status = service.cancel(job_id)
    except JobNotFound:
        raise HTTPException(status_code=404, detail="job not found") from None
    if status != 200:
        raise HTTPException(status_code=status, detail=body.get("detail"))
    return body


@router.get("/jobs/{job_id}/model")
async def get_model(job_id: str, request: Request,
                    format: str = "glb") -> dict:
    """Download the PRESERVED original provider mesh (GLB only)."""
    service = _service(request)
    try:
        path = service.jobs.result_path(job_id)
    except JobNotFound:
        raise HTTPException(status_code=404, detail="job not found") from None
    return _download(service, job_id, path, format, original=True)


@router.get("/jobs/{job_id}/export")
async def get_export(job_id: str, request: Request,
                     format: str = "glb") -> dict:
    """Download a validated derived export (glb or obj)."""
    service = _service(request)
    try:
        path = service.jobs.export_path(job_id, format)
    except JobNotFound:
        raise HTTPException(status_code=404, detail="job not found") from None
    return _download(service, job_id, path, format, original=False)


def _download(service: ReconstructionService, job_id: str,
              path: Path | None, format: str, *, original: bool) -> Any:
    if format not in ("glb", "obj"):
        raise HTTPException(status_code=422,
                            detail="format must be 'glb' or 'obj'")
    job = service.jobs.get(job_id)
    if job.status.value != "succeeded":
        raise HTTPException(status_code=409,
                            detail=f"model not ready (job {job.status.value})")
    if path is None or not path.is_file():
        raise HTTPException(status_code=404,
                            detail="model file not found on disk")
    media = {"glb": "model/gltf-binary", "obj": "text/plain"}[format]
    from fastapi.responses import FileResponse
    return FileResponse(path, media_type=media,
                        filename=f"vesyntra-{job_id[:8]}.{format}")


@router.get("/jobs/{job_id}/images/{idx}")
async def get_image(job_id: str, idx: int, request: Request):
    service = _service(request)
    try:
        job = service.jobs.get(job_id)
    except JobNotFound:
        raise HTTPException(status_code=404, detail="job not found") from None
    if idx < 0 or idx >= len(job.images):
        raise HTTPException(status_code=404, detail="image index out of range")
    candidates = list(service.jobs.images_dir(job_id).glob(f"{idx:02d}_*"))
    if not candidates:
        raise HTTPException(status_code=404, detail="image file missing")
    from fastapi.responses import FileResponse
    return FileResponse(candidates[0],
                        media_type=mimetypes.guess_type(candidates[0].name)[0]
                        or "application/octet-stream")
