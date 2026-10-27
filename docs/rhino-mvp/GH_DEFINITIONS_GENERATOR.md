# MARLIN Grasshopper Definitions — Genuine .gh Generator

**Critical**: The `.gh` files are **not** hand-editable XML. They are Grasshopper's proprietary binary serialization (GH_IO). The only way to produce valid files is to have Grasshopper serialize them.

**This repository now contains a generator script** that Raj runs **inside Rhino 8 on the Dell** to create the three genuine `.gh` files.

---

## Generator Script

**File**: `rhino/generate_gh_definitions.py`

**Run on the Dell (Rhino 8):**
1. Open Rhino 8
2. Type `EditPythonScript` (or `RunPythonScript`)
3. Browse to this file: `C:\path\to\repo\rhino\generate_gh_definitions.py`
4. Run it
5. It creates three files in `C:\MARLIN\definitions\`:
   - `marlin_box.gh`
   - `marlin_station_curves.gh`
   - `marlin_hull.gh`

**No manual Grasshopper wiring needed** — the script programmatically builds the exact definitions using Grasshopper's SDK.

---

## What Each Definition Does

### `marlin_box.gh` — Connectivity Test
- **Inputs**: `width`, `length`, `height` (Numbers)
- **Logic**: Box → Deconstruct Box → Brep Join → Geometry output
- **Output**: `geometry` (GeometryBase) — closed box Brep
- **Use**: `POST /api/rhino/box` smoke test

### `marlin_station_curves.gh` — Section 5 Station Curves
- **Inputs** (matching `stations.py` `vessel_inputs()`):
  - `loa`, `lwl`, `beam`, `draft`, `depth` (Numbers)
  - `station_count` (Integer, 10–20)
  - `deadrise`, `transom_width`, `chine_height`, `bow_height` (optional Numbers)
- **Logic**: Single C# Script component implementing MARLIN station math (ShapeFactor, SectionPoints, NURBS curves)
- **Outputs** (matching `normalize_values()` expectation):
  - `stations` (Curve list) — stern → bow
  - `baseline`, `centerline`, `design_waterline` (Curve items)

### `marlin_hull.gh` — Section 6 NURBS Hull Loft
- **Inputs** (matching `hull.py` `vessel_inputs()` + `mirror`, `join`):
  - Same as station curves + `mirror` (Boolean), `join` (Boolean)
- **Logic**: C# Script — builds station curves → Loft port surface → Mirror to starboard → Extract surfaces → Measurements JSON
- **Outputs** (matching `inspect_hull()` expectation):
  - `surfaces` (Surface list) — port, starboard
  - `sheer`, `bow`, `stern` (Curve items)
  - `measurements` (String) — JSON with loa, beam, draft, bounding_box, surface_count, valid_surfaces, symmetry, sides, naked_edges, invalid_trims, self_intersections, normals_consistent

---

## Verification Steps (Raj on Dell)

After running the generator:

```powershell
# 1. Open each in Grasshopper to verify
# Rhino 8 > File > Grasshopper > File > Open > C:\MARLIN\definitions\marlin_box.gh
# ... same for station_curves and hull

# 2. Test with GrasshopperPlayer (quick)
GrasshopperPlayer "C:\MARLIN\definitions\marlin_box.gh"
# Prompts for width/length/height, creates box

# 3. Test via Rhino.Compute
# Ensure Compute running on port 6500
curl http://localhost:6500/healthcheck

# 4. From Linux dev box (with RHINO_COMPUTE_URL set)
cd /home/nova/uat-repo-01/backend
. .venv/bin/activate
export RHINO_COMPUTE_URL=http://<DELL_LAN_IP>:6500
python -m pytest tests/test_integration_rhino_mvp.py -v
```

**Only after the live integration tests pass are the definitions "verified real."**

---

## Dependencies

- **Rhino 8** (licensed)
- **Grasshopper** (built into Rhino 8)
- **No third-party plugins** — only native components:
  - `GH_Number`, `GH_Integer`, `GH_Boolean`, `GH_String`
  - `GH_Box`, `GH_DeconstructBox`, `GH_BrepJoin`
  - `GH_Curve`, `GH_Surface`, `GH_GeometryBase`
  - `GH_CScript` (C# Script component)
- **.NET 6+** (included with Rhino 8)

---

## Why Not Commit .gh Files Directly?

Because Grasshopper's `.gh` format is:
1. **Binary serialization** of .NET object graph (GH_IO)
2. **Version-sensitive** — Rhino 8 writes Rhino 8 format
3. **Impossible to hand-author** — any text edit corrupts it
4. **Must be created by Grasshopper** → hence the generator script

The generator script **is** the source of truth. The `.gh` files it produces are the build artifacts.

---

## Commit Status

- ❌ `rhino/marlin_box.gh` — removed (was invalid hand-written XML)
- ❌ `rhino/marlin_station_curves.gh` — removed (was invalid)
- ❌ `rhino/marlin_hull.gh` — removed (was invalid)
- ✅ `rhino/generate_gh_definitions.py` — **NEW** generator script (committed)
- ✅ `docs/rhino-mvp/MARLIN_BOX.md` — I/O contract docs
- ✅ `docs/rhino-mvp/MARLIN_STATION_CURVES.md` — I/O contract docs
- ✅ `docs/rhino-mvp/MARLIN_HULL_DEFINITION.md` — I/O contract docs
- ✅ `docs/rhino-mvp/DELL_DEPLOYMENT_GUIDE.md` — deployment guide