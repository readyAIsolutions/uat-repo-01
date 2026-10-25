# MARLIN Grasshopper Definitions — Dell Deployment & Testing Guide

**For**: Raj  
**Date**: 2026-10-25  
**Repo**: https://github.com/readyAIsolutions/uat-repo-01

---

## Files to Deploy

Copy these three files from the repo's `rhino/` folder to the Dell:

| File | Purpose | Definition Pointer |
|------|---------|-------------------|
| `marlin_box.gh` | Connectivity/smoke test — primitive box | `marlin_box` |
| `marlin_station_curves.gh` | Section 5 — parametric station cross-sections | `marlin_station_curves` |
| `marlin_hull.gh` | Section 6 — NURBS hull loft + measurements | `marlin_hull` |

**Destination on Dell** (suggested): `C:\MARLIN\definitions\`

---

## Prerequisites on the Dell

| Requirement | Version | Notes |
|-------------|---------|-------|
| Windows | 10/11 | |
| Rhino 8 | 8.x (licensed) | Must be the same license used for Rhino.Compute |
| Rhino.Compute | 8.x | Installed and running as a service or console app |
| Grasshopper | Built into Rhino 8 | No separate install needed |
| .NET | 6.0+ | Required by Rhino.Compute |
| Hops (optional) | ghhops_server | Only if using `rhino/marlin_hull.py` Hops path |

---

## Step-by-Step Deployment

### 1. Copy the `.gh` Files

```powershell
# On the Dell (PowerShell)
mkdir C:\MARLIN\definitions -Force
# Copy the three .gh files from your transfer method (USB, network share, git clone, etc.)
# to C:\MARLIN\definitions\
```

### 2. Verify the Definitions Open Cleanly

For each file, open in Rhino 8 → Grasshopper:

```powershell
# In Rhino 8 on the Dell:
# File > Grasshopper > File > Open > C:\MARLIN\definitions\marlin_box.gh
# File > Grasshopper > File > Open > C:\MARLIN\definitions\marlin_station_curves.gh
# File > Grasshopper > File > Open > C:\MARLIN\definitions\marlin_hull.gh
```

**Verify**:
- No red/orange components (missing plugins)
- All components are native Grasshopper (no third-party)
- C# Script components show no compile errors (hover over them)
- Input/Output parameter names match the docs exactly

### 3. Configure Rhino.Compute

Ensure Rhino.Compute is running and accessible. Default port is **6500**.

```powershell
# Check if Compute is running
curl http://localhost:6500/healthcheck
# Should return "Healthy"
```

If not running, start it:
```powershell
# From Rhino.Compute install directory (typically):
# C:\Program Files\Rhino 8\System\compute.geometry.exe
# Or if installed via NuGet / custom location, run the executable
```

### 4. Register Definitions with Rhino.Compute

**Option A: GrasshopperPlayer (quick test)**
```powershell
# In Rhino 8 command line:
GrasshopperPlayer "C:\MARLIN\definitions\marlin_box.gh"
# Should prompt for width/length/height and create a box
```

**Option B: Rhino.Compute Geometry Endpoint (production)**
The definitions are automatically discoverable by Rhino.Compute when placed in the definitions folder, OR you can reference them by path in the MARLIN config.

### 5. Configure MARLIN `.env` on Linux Dev Box

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

## Testing Checklist

### Level 1: Connectivity (Box Test)
```bash
# On Linux dev box
cd /home/nova/uat-repo-01/backend
. .venv/bin/activate
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
Key test: `test_station_generation_real_rhino` (currently skipped — will run when `RHINO_COMPUTE_URL` is set)

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

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `RHINO_NOT_CONFIGURED` | `RHINO_COMPUTE_URL` not set | Set in `.env` and restart MARLIN |
| `RHINO_UNAVAILABLE` (503) | Can't reach Dell:6500 | Check firewall, LAN IP, Compute running |
| `RHINO_REQUEST_FAILED` (502) | Definition not found / bad inputs | Verify `.gh` files deployed, check Compute logs |
| `401/403` from Compute | API key mismatch | Set `RHINO_COMPUTE_API_KEY` on both sides |
| `malformed_response` | Output names don't match | Check `.gh` output param nicknames match docs |
| C# Script errors in Grasshopper | .NET version / RhinoCommon | Ensure Rhino 8, .NET 6+, restart Rhino |

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

## File Structure on Dell After Deployment

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

- **Geometry/C# Script issues**: Check `docs/rhino-mvp/MARLIN_STATION_CURVES.md` and `MARLIN_HULL_DEFINITION.md`
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