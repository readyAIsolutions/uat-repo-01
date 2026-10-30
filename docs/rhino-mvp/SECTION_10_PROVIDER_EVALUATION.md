# Module 10 — image-to-3D provider evaluation (verification notes)

All facts below were checked against primary sources on 2026-10-30
(provider repos/docs), not assumed.

## TRELLIS — SELECTED (microsoft/TRELLIS)

| Question | Verified answer |
|---|---|
| Image input? | Yes — `TrellisImageTo3DPipeline.from_pretrained("microsoft/TRELLIS-image-large")`; `pipeline.run(image)` for 1 image. |
| Multi-view? | Yes — `pipeline.run_multi_image([images])`, tuning-free conditioning (README 12/18/2024 update). |
| Mesh output? | Yes — `outputs['mesh']`; GLB via `postprocessing_utils.to_glb(...)`; PLY gaussians too. |
| Local or cloud? | Local/self-hosted (weights on Hugging Face). No API key, no per-image fee. |
| Licensing | Open code + open weights (MIT-style repo; verify the exact license file at deploy time). |
| Hardware | **Linux + NVIDIA GPU ≥ 16 GB VRAM** (README: verified A100/A6000; conda + CUDA toolkit + flash-attn). |
| Cost | GPU electricity only. |
| Integration difficulty | Moderate: heavy conda env, but our subprocess adapter keeps it off the API process. |

## TripoSR (Stability AI + Tripo) — evaluated, not selected

- MIT-licensed open model incl. weights; fast (<0.5 s on A100), single-image
  only (no genuine multi-view), lower detail than TRELLIS, same GPU
  requirement (CUDA). Good fallback if GPU is small.

## Tripo3D cloud API — evaluated, not selected

- REST API with account/credits (paid, per-task); convenient but adds a
  cloud dependency + cost + data egress for vessel photos. Revisit if
  on-prem GPU is unavailable. (Live page is JS-rendered; docs verified
  indirectly via tripo3d.ai research pages, NOT by calling the API.)

## Photogrammetry (COLMAP/OpenMVG + MVS) — evaluated, not selected

- Genuine multi-view reconstruction but needs many overlapping angles with
  stable lighting (hard for boats on water), heavy CPU/GPU tuning, no
  single-image support, and no AI completion of unseen surfaces.

## Decision

TRELLIS is the initial provider: real single-/multi-image input, mesh +
GLB output, self-hosted (no keys/costs, fits VESYNTRA's on-prem philosophy),
runnable on a workstation-class GPU (the Dell or a rented g5 instance).
Provider adapter interface (`ReconstructionProvider` ABC) means Tripo3D or
any later engine slots in by implementing 3 methods and setting
`RECONSTRUCTION_PROVIDER=<name>`.
