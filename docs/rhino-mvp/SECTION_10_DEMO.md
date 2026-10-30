# MODULE 10 DEMO — photograph → upload → job → mesh → viewer → download

Ran live on the Linux dev box, 2026-10-30, against the real API with the
**labelled development mock** provider (RECONSTRUCTION_PROVIDER=mock,
MARLIN_ENVIRONMENT=development).

> IMPORTANT: this demo proves the PIPELINE end-to-end. The mesh it produced
> is a SIMULATED placeholder (two boxes), visibly labelled as such in the UI,
> the API payloads (`simulated: true`), the warnings, and every download.
> Real AI reconstruction (TRELLIS) needs a GPU host — see SECTION_10 §7.

## Input

- Photograph: `demo/boat_photo.jpg` — "Papa-Golfe motor yacht" (RioStar
  Yachts), **CC0 public-domain dedication**, Wikimedia Commons, 1280×787 px,
  220,619 bytes, real JPEG (Exif present).
- Reference metadata: vessel_length_m=29.0, vessel_beam_m=6.5,
  note="CC0 demo photo, approximate dimensions".

## The journey (real HTTP, real storage, real job lifecycle)

```
POST /api/reconstruct/jobs          201  job 8644bee3-… (queued, 1 image validated)
GET  /api/reconstruct/jobs/{id}    succeeded
     provider=mock · simulated=true · vertex_count=16 · triangle_count=24
     result_model=model.glb · exported_glb=export.glb · exported_obj=export.obj
GET  /export?format=glb            200  marlin-demo.glb  (1,864 B, magic "glTF")
GET  /export?format=obj            200  marlin-demo.obj  (869 B, has faces)
GET  /model                        200  marlin-demo-original.glb (original, preserved)
GET  /reconstruct                  200  Module 10 UI page serves
```

## Evidence artifacts (committed under demo/)

| File | Meaning |
|---|---|
| `demo/boat_photo.jpg` | the CC0 demo photograph (input) |
| `demo/output/marlin-demo.glb` | validated GLB export (re-opened by trimesh: 16 verts) |
| `demo/output/marlin-demo.obj` | OBJ export (re-opened: 46 lines, faces present) |
| `demo/output/marlin-demo-original.glb` | provider original, byte-preserved |

Integrity proof run after download: both GLBs re-open in trimesh with real
geometry; OBJ contains vertices and faces. The UI renders at `/reconstruct`
with rotate/zoom/reset controls and the SIMULATED banner.

## How to reproduce

```bash
bash setup_module10_demo.sh   # starts the API with the mock provider
# open http://127.0.0.1:8123/reconstruct, drop demo/boat_photo.jpg, submit
```

or via curl:

```bash
curl -s -X POST http://127.0.0.1:8123/api/reconstruct/jobs \
  -F "images=@demo/boat_photo.jpg" -F "vessel_length_m=29.0" -F "vessel_beam_m=6.5"
```
