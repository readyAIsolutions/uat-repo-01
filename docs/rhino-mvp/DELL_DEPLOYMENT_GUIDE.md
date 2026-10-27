# MARLIN Grasshopper Definitions — Dell Deployment & Testing Guide

**For**: Raj  
**Date**: 2026-10-25  
**Repo**: https://github.com/readyAIsolutions/uat-repo-01

---

## CRITICAL: How to Get Valid .gh Files

The `.gh` files in this repo were **removed** — they were hand-written XML that Grasshopper cannot read.

**The only way to get genuine `.gh` files is to run the generator script inside Rhino 8 on the Dell.**

---

## Step-by-Step on the Dell

### 1. Prerequisites
| Requirement | Version | Notes |
|-------------|---------|-------|
| Windows | 10/11 | |
| Rhino 8 | 8.x (licensed) | Must match Rhino.Compute license |
| Rhino.Compute | 8.x | Running on port 6500 |
| Grasshopper | Built-in | No separate install |
| .NET | 6.0+ | Included with Rhino 8 |

### 2. Generate the .gh Files (REQUIRED)

```powershell
# Option A: RunPythonScript (simpler)
# In Rhino 8 command line:
RunPythonScript "C:\path\to\repo\rhino\generate_gh_definitions.py"

# Option B: EditPythonScript (if you want to inspect first)
# In Rhino 8 command line:
EditPythonScript
# Browse to the file, press Run
```

**Result**: Three files created in `C:\MARLIN\definitions\`:
- `marlin_box.gh`
- `marlin_station_curves.gh`
- `marlin_hull.gh`

### 3. Verify the Generated Files

Open each in Rhino 8 Grasshopper to confirm they load without errors:

```powershell
# In Rhino 8:
# File > Grasshopper > File > Open > C:\MARLIN\definitions\marlin_box.gh
# File > Grasshopper > File > Open > C:\MARLIN\definitions\marlin_station_curves.gh
# File > Grasshopper > File > Open > C:\MARLIN\definitions\marlin_hull.gh
```

**Verify**:
- No red/orange components
- All components are native (no third-party plugins)
- C# Script components show no compile errors
- Input/Output parameter nicknames match the docs exactly

### 4. Quick Test with GrasshopperPlayer

```powershell
# In Rhino 8 command line:
GrasshopperPlayer "C:\MARLIN\definitions\marlin_box.gh"
# Prompts for width/length/height → creates box

GrasshopperPlayer "C:\MARLIN\definitions\marlin_station_curves.gh"
# Prompts for all params → creates station curves

GrasshopperPlayer "C:\MARLIN\definitions\marlin_hull.gh"
# Prompts for all params → creates hull surfaces
```

### 5. Ensure Rhino.Compute Is Running

```powershell
# Check
curl http://localhost:6500/healthcheck
# Should return "Healthy"

# If not running, start from Rhino.Compute install directory:
# "C:\Program Files\Rhino 8\System\compute.geometry.exe"
```

### 6. Configure MARLIN on Linux Dev Box

On the Linux machine running MARLIN backend:

```bash
cd /home/nova/uat-repo-01
cp .env.example .env
# Edit .env:
RHINO_COMPUTE_URL=http://<DELL_LAN_IP>:6500
RHINO_COMPUTE_API_KEY=  # if you set one on Compute
RHINO_STATION_DEFINITION=marlin_station_curves
RHINO_HULL_DEFINITION=marlin_hull
RHINO_BOX_DEFINITION=marlin_box
```

**Critical**: Use the Dell's **LAN IP** (e.g., `192.168.1.50`), NOT `localhost` or `127.0.0.1` from the Linux box.

---

## Testing Checklist (Linux → Dell)

### Level 1: Connectivity (Box Test)
```bash
cd /home/nova/uat-repo-01/backend
. .venv/bin/activate
export RHINO_COMPUTE_URL=http://<DELL_LAN_IP>:6500
python -c "
import httpx, asyncio
async def test():
    async with httpx.AsyncClient() as client:
        r = await client.post('http://localhost:8011/api/rhino/box', json={'width':5.5,'length':20,'height':2.4}, timeout=10)
        print(r.status_code, r.json())
asyncio.run(test())
"
```
**Expected**: 200 with geometry result from Rhino.Compute

### Level 2: Station Curves (Section 5)
```bash
python -m pytest tests/test_stations_api.py -v
```
Key test: `test_station_generation_real_rhino` (runs when `RHINO_COMPUTE_URL` is set)

### Level 3: Hull Loft (Section 6)
```bash
python -m pytest tests/test_hull_api.py -v
```
Key tests: `test_standard_hull_success`, `test_acceptance_20m_hull`

### Level 4: Full Integration Chain
```bash
python -m pytest tests/test_integration_rhino_mvp.py -v
```

---

## Verifying Real Geometry (Not Mock)

When testing against live Rhino, check these response fields:

```json
{
  "rhino_compute_used": true,
  "geometry_source": "rhino_compute_nurbs",
  "nurbs_ingested": true,
  "nurbs_ingested_count": 2
}
```

If `rhino_compute_used: false` or `geometry_source: "marlin_parameters"`, you're still hitting the stub.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `RHINO_NOT_CONFIGURED` | `RHINO_COMPUTE_URL` not set | Set in `.env` and restart MARLIN |
| `RHINO_UNAVAILABLE` (503) | Can't reach Dell:6500 | Check firewall, LAN IP, Compute running |
| `RHINO_REQUEST_FAILED` (502) | Definition not found / bad inputs | Verify `.gh` files generated, check Compute logs |
| `401/403` from Compute | API key mismatch | Set `RHINO_COMPUTE_API_KEY` on both sides |
| `malformed_response` | Output names don't match | Regenerate `.gh` files, check C# Script nicknames |
| C# Script errors in Grasshopper | .NET version / RhinoCommon | Ensure Rhino 8, .NET 6+, restart Rhino |

---

## File Structure on Dell After Generation

```
C:\MARLIN\
├── definitions\
│   ├── marlin_box.gh
│   ├── marlin_station_curves.gh
│   └── marlin_hull.gh
└── (optional) marlin_hull.py  # Hops alternative path
```

---

## Definition Pointer Mapping

| MARLIN Config Env Var | Default Value | Points To |
|----------------------|---------------|-----------|
| `RHINO_STATION_DEFINITION` | `marlin_station_curves` | `marlin_station_curves.gh` |
| `RHINO_HULL_DEFINITION` | `marlin_hull` | `marlin_hull.gh` |
| `RHINO_BOX_DEFINITION` | `marlin_box` | `marlin_box.gh` |

These are **server-side pointers** — Rhino.Compute resolves them to the `.gh` files on its filesystem.

---

## Support Contacts

- **Generator script**: `rhino/generate_gh_definitions.py`
- **Geometry/C# Script logic**: Same math as `rhino/marlin_hull.py` (Hops version)
- **MARLIN API / serialization**: `backend/app/services/rhino/compute_schema.py`
- **Test expectations**: `backend/tests/test_integration_rhino_mvp.py`

---

## Next Steps After Verification

Once all three definitions work live on the Dell:
1. Run full test suite with `RHINO_COMPUTE_URL` set → all 6 skipped tests should become `PASS_REAL`
2. Verify `.3dm` export downloads and opens in Rhino 8 on Dell
3. Proceed to Module 9 gate (one-click Windows launcher + live demo)

---

**Do not claim successful Rhino testing until the definitions have actually been executed in Rhino 8 on the Dell and the integration tests pass against the live node.**