"""Module 10 — photograph upload validation.

Real validation: magic bytes + Pillow decode. A file is accepted only if its
declared extension AND magic signature AND a full Pillow open/load agree.
Nothing here touches the Rhino modules.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from .contract import ReconstructionError

ALLOWED_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}

# magic-byte signatures (start of file)
_MAGIC = {
    b"\xff\xd8\xff": "JPEG",
    b"\x89PNG\r\n\x1a\n": "PNG",
    b"RIFF": "WEBP",  # WEBP is RIFF....WEBP; verified below
}


@dataclass
class UploadedFile:
    filename: str
    content: bytes


class UploadValidationError(ReconstructionError):
    """One or more uploaded files are not acceptable boat photographs."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


def sniff_format(data: bytes) -> str | None:
    """Identify format from magic bytes only (no PIL required)."""
    if data[:3] == b"\xff\xd8\xff":
        return "JPEG"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP"
    return None


def _extension_ok(filename: str, fmt: str) -> bool:
    return Path(filename).suffix.lower() == ALLOWED_FORMATS[fmt]


def validate_image(
    uploaded: UploadedFile,
    *,
    max_bytes: int,
) -> tuple[str, int, int]:
    """Validate one file; returns (format, width, height) or raises."""
    problems: list[str] = []
    name = uploaded.filename or "unnamed"
    data = uploaded.content

    if len(data) == 0:
        raise UploadValidationError([f"{name}: file is empty"])
    if len(data) > max_bytes:
        raise UploadValidationError(
            [f"{name}: {len(data)} bytes exceeds limit of {max_bytes}"])

    fmt = sniff_format(data)
    if fmt is None:
        raise UploadValidationError(
            [f"{name}: not a JPEG/PNG/WebP image (magic bytes unrecognised)"])
    if not _extension_ok(name, fmt):
        raise UploadValidationError(
            [f"{name}: extension does not match detected {fmt} format"])

    # Full decode (catches truncated / polyglot / corrupt files).
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            width, height = img.size
            if width < 8 or height < 8:
                raise UploadValidationError(
                    [f"{name}: image too small ({width}x{height})"])
            if img.format is None or img.format.upper() not in ALLOWED_FORMATS:
                raise UploadValidationError(
                    [f"{name}: Pillow could not confirm an allowed format"])
    except UploadValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 - any decode failure = reject
        raise UploadValidationError(
            [f"{name}: image decode failed ({exc.__class__.__name__})"]) from None
    return fmt, width, height
