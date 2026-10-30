# MODULE 10 — FULL-VESSEL AI IMAGE RECONSTRUCTION (image -> 3D mesh)

**Branch:** `feature/module-10-image-to-3d` (isolated; nothing merged to main)
**Baseline commit:** `362da968b208a42be353390e9b8034f777ea33e7` (main, untouched)
**Status:** IMPLEMENTED + MOCKED TESTS GREEN. Real-AI acceptance gate requires a GPU host — see "Dell / GPU gate".

---

## 1. What this module does

Accepts one or more photographs of a boat and produces a **polygonal 3D
reference model of the ENTIRE visible vessel** — hull, bow, stern/swim
platform, deck, cockpit, windshield, helm, cabin/superstructure, hardtop or
tower, visible seats and railings — as far as the reconstruction engine can
infer them from the photos.

The output is explicitly **NOT manufacturing-ready NURBS CAD**. It is a mesh
reference model for a later mesh-to-NURBS / Rhino conversion module.

## 2. Architecture

```
browser (/reconstruct UI)
   │  multipart: images[] + vessel_length_m + vessel_beam_m + reference_note
   ▼
POST /api/reconstruct/jobs ──► ReconstructionService.create_job()
   │                              • real image validation (magic bytes + Pillow)
   │                              • secure storage under <storage>/reconstruction/<job_id>/
   │                              • job persisted as meta.json (survives restarts)
   ▼ daemon worker thread
provider adapter (ReconstructionProvider ABC)
   │   trellis  = real engine (subprocess isolation, GPU host)
   │   mock     = labelled dev-only placeholder (REFUSED in production)
   ▼
mesh pipeline: inspect_mesh() → export.glb + export.obj (trimesh)
   │   provider original = model.glb (preserved untouched)
   ▼
GET /api/reconstruct/jobs/{id}/export?format=glb|obj   (downloads)
GET /api/reconstruct/jobs/{id}/model                  (original)
```

Key files (all NEW — no nine-module source file was modified except the
two additive wiring lines in `app/mvp.py`, listed in the commit diff):

| File | Purpose |
|---|---|
| `backend/app/services/reconstruct/contract.py` | provider ABC, domain models, typed errors |
| `backend/app/services/reconstruct/validation.py` | upload validation (magic bytes + Pillow decode) |
| `backend/app/services/reconstruct/jobs.py` | JSON-persisted job store + lifecycle |
| `backend/app/services/reconstruct/trellis.py` | TRELLIS adapter (subprocess) |
| `backend/app/services/reconstruct/mock_provider.py` | labelled dev mock (blocked in prod) |
| `backend/app/services/reconstruct/meshes.py` | mesh validation + GLB/OBJ export |
| `backend/app/services/reconstruct/service.py` | orchestrator + worker thread |
| `backend/app/api/reconstruct.py` | /api/reconstruct/* routes |
| `backend/app/core/env.py` | env helpers (additive) |
| `reconstruction/trellis_entrypoint.py` | runs INSIDE the TRELLIS conda env (GPU box) |
| `backend/app/ui/reconstruct.html` + `reconstruct.js` | Module 10 UI page at `/reconstruct` |
| `backend/app/ui/vendor/GLTFLoader.js` | vendored Three.js r169 loader (new file) |
| `backend/requirements-module10.txt` | additive deps: trimesh, pillow, python-multipart |

## 3. Provider selection — TRELLIS (Microsoft)

Verified against the official repository (microsoft/TRELLIS) before wiring:

| Criterion | Finding |
|---|---|
| Inputs | 1 image (`pipeline.run`) or multi-view (`pipeline.run_multi_image`) — real |
| Outputs | mesh + GLB via `postprocessing_utils.to_glb(...)` — real, documented |
| Models | `microsoft/TRELLIS-image-large` (1.2B) on Hugging Face |
| Hardware | Linux + NVIDIA GPU ≥ 16 GB VRAM (verified A100/A6000) — NOT runnable here |
| Licensing | open code + open weights (no per-image fee, self-hosted) |
| Integration | subprocess adapter → heavy CUDA stack stays OFF the API process |

Alternatives evaluated (rejected for this iteration): TripoSR (MIT, same GPU
requirement, lower detail), Tripo3D cloud API (account + credits, less
control), photogrammetry tools (need many angles + heavy processing).

**Why subprocess:** the API process never imports torch/TRELLIS; the GPU box
only needs the `reconstruction/trellis_entrypoint.py` script + its conda env.

## 4. Working features

- Upload of JPEG/PNG/WebP, 1–10 images, 10 MB each, previews, drag & drop.
- Real validation: magic bytes + extension match + full Pillow decode.
- Optional vessel length/beam/reference note carried as job metadata.
- Job lifecycle: queued → processing → succeeded | failed | canceled,
  persisted as JSON, survives API restarts, cancel is race-safe.
- Honest failures: provider auth, timeouts, provider rejection, invalid or
  empty geometry all produce `failed` jobs with readable errors. No fake
  geometry is ever reported as AI output.
- Viewer at `/reconstruct`: rotate / zoom / pan / reset, warnings banner,
  GLB + OBJ + original downloads.
- `simulated=true` + visible banner on every mock-provider job (the mock is
  hard-blocked when `MARLIN_ENVIRONMENT=production`).
- Export integrity: every successful job's mesh passes `inspect_mesh()`
  (non-empty, has bounds) and derived exports are re-opened by trimesh.

## 5. Test results (mocked — repeatable, no GPU needed)

`pytest -c backend/pytest.ini backend/tests` →
**253 passed, 7 skipped, 0 failed** (42s)

- 6 skipped = the pre-existing live-Rhino tests (unchanged, need the Dell/Compute node).
- 1 skipped = `test_reconstruct_live.py` (REAL TRELLIS gate; opt-in).
- 66 Module-10 tests cover: upload validation, invalid-file rejection,
  multi-image handling, job creation, provider adapter behaviour, provider
  auth failures, processing timeouts, model retrieval, invalid-geometry
  rejection, exported-model integrity, and Rhino-module independence
  (AST-level check that Module 10 never imports the Rhino services, plus a
  git-diff check that Raj's module files are untouched).

## 6. Live reconstruction evidence — NOT VERIFIED ON THIS MACHINE

**Honest status:** the real AI engine (TRELLIS) has NOT processed an image
on this Linux box — there is no NVIDIA GPU here (no nvidia-smi; 15 GB RAM;
4.4 GB free disk). The acceptance condition "a real reconstruction engine
successfully processes at least one image submission" is therefore
**NOT satisfied yet** and cannot be satisfied in this environment.

What WAS verified live in this environment:
- A real public-domain boat photograph (CC0, Papa-Golfe motor yacht) was
  uploaded through the real API, validated, stored, processed by the
  workflow with the **labelled mock** provider, produced `export.glb` +
  `export.obj`, both re-opened successfully by trimesh. That run is
  explicitly SIMULATED — it proves the pipeline, not AI quality.
- See `docs/rhino-mvp/SECTION_10_DEMO.md` for the evidence and artifacts.

## 7. Dell / GPU gate (the one real-AI step)

On any machine with an NVIDIA GPU ≥ 16 GB (the Dell workstation if it has
one, or an AWS g5 instance):

```bash
# 1. TRELLIS env (per its README): conda, CUDA, then
git clone --recurse-submodules https://github.com/microsoft/TRELLIS.git
cd TRELLIS && . ./setup.sh --new-env --basic --xformers --flash-attn

# 2. Copy the entrypoint + model into the env:
cp <repo>/reconstruction/trellis_entrypoint.py ~/TRELLIS/

# 3. Run VESYNTRA with the real engine (env identifiers keep the legacy MARLIN_ prefix for compatibility):
RECONSTRUCTION_PROVIDER=trellis \
RECONSTRUCTION_TRELLIS_PYTHON=~/miniconda3/envs/trellis/bin/python \
MARLIN_ENVIRONMENT=production \
MARLIN_STORAGE_DIR=/data/storage \
.venv-m10/bin/python -m uvicorn app.mvp:create_app --factory --port 8011

# 4. Prove it end-to-end (the real acceptance gate):
RECONSTRUCTION_RUN_LIVE=1 RECONSTRUCTION_SAMPLE_IMAGE=<boat photo> \
  .venv-m10/bin/python -m pytest -c backend/pytest.ini \
    backend/tests/test_reconstruct_live.py -v
```

The live test asserts: non-empty GLB with `glTF` magic, vertex/face counts,
and re-openable exports. Supporting files land in the job dir
(`provider.log` shows the full TRELLIS run).

## 8. Known limitations (honest)

1. Real AI reconstruction is unverified until the GPU gate above runs.
2. 4.4 GB free disk on this box — the TRELLIS install (~several GB) cannot
   fit here; it belongs on the GPU host.
3. The mock's placeholder mesh is a box pair, NOT a boat — used only to
   prove the workflow; every such job is flagged SIMULATED.
4. TRELLIS inference on a boat may take minutes per image and can produce
   imperfect geometry (blurred, merged, or missing small components). The
   pipeline reports warnings; the report must not overstate quality.
5. No scale/units in the mesh: `vessel_length_m`/`vessel_beam_m` are stored
   as metadata for the NEXT module to apply as calibration, not applied here.
6. Multi-image conditioning is tuning-free in TRELLIS; quality depends on
   consistent angles (roughly same lighting, no water reflections).

## 9. Missing requirements / credentials

- **GPU host with TRELLIS env** — required for the real engine (no API key
  needed; self-hosted).
- Nothing else. No paid API, no cloud keys. The dev mock needs nothing.

## 10. Interface for the next CAD conversion module

The next module (mesh cleanup → component ID → parametric surface fitting →
editable Rhino) should consume:

- `GET /api/reconstruct/jobs/{id}` → `${...}.exported_glb` + `metadata`
  (vessel_length_m / beam), or the file paths under
  `<MARLIN_STORAGE_DIR>/reconstruction/<job_id>/export.glb`.
- Every export is already validated: non-empty, bounds known, format GLB
  (or OBJ). Metadata JSON (`meta.json`) carries provider, model, timings,
  `simulated` flag, vertex/triangle counts, and the reference dimensions.

Suggested contract for the next module (to be confirmed with Raj):
`POST /api/cad/convert {job_id, target: "rhino"}` → mesh-to-NURBS job,
producing a .3dm; the reconstructed `.glb` stays the input of record.
