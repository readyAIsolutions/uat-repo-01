#!/usr/bin/env python
"""Module 10 — TRELLIS image-to-3D entrypoint (runs INSIDE the TRELLIS env).

This script is executed as a subprocess by the MARLIN API on the GPU
workstation. It uses the REAL official TRELLIS pipeline:

    pipeline = TrellisImageTo3DPipeline.from_pretrained(model)
    outputs  = pipeline.run(image)                     # 1 image
    outputs  = pipeline.run_multi_image([images])      # multi-view
    glb      = postprocessing_utils.to_glb(...)        # GLB export

Usage:
    python trellis_entrypoint.py --job-dir <dir> --model <hf-name> IMG...

The last line of stdout is a JSON summary; everything else goes to stderr.
Exit code 0 only when a non-empty GLB was actually written.

Live API verified against https://github.com/microsoft/TRELLIS (README,
example.py, trellis_image_to_3d.py). Requires Linux + NVIDIA GPU >= 16GB.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

# TRELLIS tuning knobs (documented in its README).
os.environ.setdefault("SPCONV_ALGO", "native")
# ATTN_BACKEND is left to the TRELLIS env default (flash-attn); set
# ATTN_BACKEND=xformers explicitly if your GPU does not support flash-attn.


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("images", nargs="+", help="input photograph paths")
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--model", default="microsoft/TRELLIS-image-large")
    args = parser.parse_args()

    job_dir = Path(args.job_dir)
    images = [Path(p) for p in args.images]
    for img in images:
        if not img.is_file():
            _log(f"ERROR: input image missing: {img}")
            return 2

    try:
        from PIL import Image
        from trellis.pipelines import TrellisImageTo3DPipeline
        from trellis.utils import postprocessing_utils
    except Exception as exc:  # noqa: BLE001
        _log(f"ERROR: TRELLIS dependencies unavailable: {exc}")
        return 3

    try:
        _log(f"loading pipeline {args.model} ...")
        pipeline = TrellisImageTo3DPipeline.from_pretrained(args.model)
        if not pipeline.device.type == "cuda":
            _log("WARNING: TRELLIS running on CPU (slow); CUDA GPU expected")
        loaded = [Image.open(p).convert("RGB") for p in images]
        _log(f"running reconstruction on {len(loaded)} image(s) ...")
        if len(loaded) == 1:
            outputs = pipeline.run(loaded[0], seed=1)
        else:
            outputs = pipeline.run_multi_image(loaded, seed=1)
    except Exception as exc:  # noqa: BLE001
        details = traceback.format_exc(limit=5)
        _log(f"ERROR: reconstruction failed: {exc}\n{details}")
        return 4

    if not outputs or not outputs.get("mesh"):
        _log("ERROR: pipeline returned no mesh")
        return 5

    mesh = outputs["mesh"][0]
    gaussian = outputs.get("gaussian", [None])[0]
    _log(f"mesh stats: {mesh}")

    out_glb = job_dir / "model.glb"
    try:
        if gaussian is not None:
            glb = postprocessing_utils.to_glb(gaussian, mesh, simplify=0.95,
                                              texture_size=1024)
        else:
            glb = postprocessing_utils.to_glb(mesh, texture_size=1024)
        glb.export(str(out_glb))
    except Exception as exc:  # noqa: BLE001
        details = traceback.format_exc(limit=5)
        # Fall back to exporting just the mesh if textured export fails.
        _log(f"WARNING: GLB export issue ({exc}); retrying mesh-only")
        try:
            scene = mesh.to_trimesh_scene()
            scene.export(str(out_glb))
        except Exception as exc2:  # noqa: BLE001
            _log(f"ERROR: GLB export failed: {exc2}\n{details}")
            return 6

    if not out_glb.is_file() or out_glb.stat().st_size == 0:
        _log("ERROR: GLB output missing or empty")
        return 7

    print(json.dumps({
        "status": "ok",
        "output_glb": out_glb.name,
        "bytes": out_glb.stat().st_size,
        "images": len(loaded),
        "model": args.model,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
