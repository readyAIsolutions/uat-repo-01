"""Shared helpers for Module 10 tests (unit-level; no app import)."""
from __future__ import annotations

import io

from PIL import Image


def make_image(fmt: str = "JPEG", size: tuple[int, int] = (320, 240),
               color: int | tuple[int, ...] = (40, 90, 160)) -> bytes:
    """Build a tiny but real image of the requested format."""
    buf = io.BytesIO()
    img = Image.new("RGB", size, color)
    img.save(buf, format=fmt)
    return buf.getvalue()


def make_glb() -> bytes:
    """A tiny REAL GLB (one triangle) as exported by trimesh."""
    import trimesh
    mesh = trimesh.creation.box(extents=(1, 1, 1))
    return trimesh.exchange.gltf.export_glb(mesh)
