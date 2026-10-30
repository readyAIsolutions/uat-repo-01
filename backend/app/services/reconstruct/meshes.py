"""Module 10 — mesh validation and export (trimesh).

The provider's original output is ALWAYS preserved untouched; exports are
derived copies. ``inspect_mesh`` is the gate that rejects empty/phantom
geometry so a 'successful' job can never carry a useless mesh.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .contract import InvalidGeometryError

# trimesh import is lazy: it is heavy and only needed for real mesh work.
_trimesh = None


def _tm():
    global _trimesh
    if _trimesh is None:
        import trimesh  # noqa: PLC0415
        _trimesh = trimesh
    return _trimesh


@dataclass
class MeshInspection:
    vertex_count: int
    triangle_count: int
    bounds: list[list[float]]  # [[minx,miny,minz],[maxx,maxy,maxz]]
    watertight: bool
    has_texture: bool
    size_m: float  # max bounding-box dimension


def inspect_mesh(path: Path) -> MeshInspection:
    """Open a GLB/OBJ and report real metrics. Raises if unusable."""
    tm = _tm()
    try:
        scene = tm.load(str(path), force=None)
    except Exception as exc:  # noqa: BLE001
        raise InvalidGeometryError(
            f"cannot read mesh file {path.name}: {exc.__class__.__name__}") from None

    meshes = [g for g in scene.geometry.values()] if hasattr(scene, "geometry") else []
    if not meshes:
        # A bare Trimesh object also has geometry only via scene; handle both.
        if isinstance(scene, tm.Trimesh):
            meshes = [scene]
    if not meshes:
        raise InvalidGeometryError(
            f"model {path.name} contains no mesh geometry")

    total_v = sum(len(m.vertices) for m in meshes)
    total_f = sum(len(m.faces) for m in meshes)
    if total_v == 0 or total_f == 0:
        raise InvalidGeometryError(
            f"model {path.name} has empty geometry "
            f"({total_v} verts / {total_f} faces)")

    # Combined bounds across all meshes.
    mins = [m.bounds[0] for m in meshes if m.bounds is not None]
    maxs = [m.bounds[1] for m in meshes if m.bounds is not None]
    if not mins or not maxs:
        raise InvalidGeometryError(
            f"model {path.name} has no valid bounds")
    lo = [min(v[i] for v in mins) for i in range(3)]
    hi = [max(v[i] for v in maxs) for i in range(3)]
    size = max(hi[i] - lo[i] for i in range(3))
    if size <= 0:
        raise InvalidGeometryError(
            f"model {path.name} has degenerate bounds {lo}..{hi}")

    watertight = all(
        getattr(m, "is_watertight", False) is True for m in meshes) \
        if len(meshes) == 1 else False
    has_texture = any(
        getattr(m, "visual", None) is not None
        and getattr(getattr(m, "visual", None), "kind", None) in ("texture",)
        for m in meshes)

    return MeshInspection(
        vertex_count=total_v,
        triangle_count=total_f,
        bounds=[lo, hi],
        watertight=watertight,
        has_texture=has_texture,
        size_m=size,
    )


def export_glb(src: Path, dst: Path) -> Path:
    """Load src (GLB/OBJ) and write a clean GLB. Raises InvalidGeometryError."""
    tm = _tm()
    try:
        scene = tm.load(str(src), force="scene")
    except Exception as exc:  # noqa: BLE001
        raise InvalidGeometryError(
            f"cannot read {src.name} for export: {exc.__class__.__name__}") from None
    try:
        exported = tm.exchange.gltf.export_glb(scene)
    except Exception as exc:  # noqa: BLE001
        raise InvalidGeometryError(
            f"GLB export failed: {exc.__class__.__name__}") from None
    dst.write_bytes(exported)
    return dst


def export_obj(src: Path, dst: Path) -> Path:
    """Load src (GLB/OBJ) and write OBJ (+ sidecar .mtl when textured)."""
    tm = _tm()
    try:
        scene = tm.load(str(src), force="scene")
        obj_bytes = tm.exchange.obj.export_obj(scene, include_texture=True)
    except Exception as exc:  # noqa: BLE001
        raise InvalidGeometryError(
            f"OBJ export failed: {exc.__class__.__name__}") from None
    dst.write_bytes(obj_bytes.encode("utf-8", errors="replace"))
    return dst


def export_download_formats(provider_glb: Path, job_dir: Path) -> tuple[Path, Path]:
    """Derive export.glb + export.obj from the preserved original."""
    glb = export_glb(provider_glb, job_dir / "export.glb")
    obj = export_obj(provider_glb, job_dir / "export.obj")
    return glb, obj
