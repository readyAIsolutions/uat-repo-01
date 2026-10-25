# marlin_station_curves.gh — Station Curve Generator

**Purpose**: Generates parametric hull station cross-section curves from vessel principal dimensions.

**Rhino/Grasshopper Version**: Rhino 8 / Grasshopper (native components only — no plugins required)

**Definition Pointer**: `marlin_station_curves` (server-side path on Rhino.Compute node)

---

## Inputs (DataTree format — one entry per parameter)

| Parameter Name | NickName | Type | Required | Default | Units | Description |
|----------------|----------|------|----------|---------|-------|-------------|
| LOA | loa | System.Double | Yes | 20.0 | m | Length overall |
| LWL | lwl | System.Double | Yes | 18.5 | m | Waterline length |
| Beam | beam | System.Double | Yes | 5.5 | m | Maximum beam |
| Draft | draft | System.Double | Yes | 1.2 | m | Draft |
| Depth | depth | System.Double | Yes | 2.4 | m | Depth at sheer |
| Station Count | station_count | System.Int32 | Yes | 15 | — | Number of stations (clamped 10–20) |
| Deadrise | deadrise | System.Double | No | 18.0 | deg | Deadrise angle (affects section shape) |
| Transom Width | transom_width | System.Double | No | -1.0 | m | Transom width (-1 = auto) |
| Chine Height | chine_height | System.Double | No | -1.0 | m | Chine height above keel (-1 = auto) |
| Bow Height | bow_height | System.Double | No | 0.0 | m | Bow height above sheer |

---

## Outputs (DataTree format — one entry per parameter)

| Parameter Name | NickName | Type | Access | Description |
|----------------|----------|------|--------|-------------|
| Stations | stations | Rhino.Geometry.Curve | List | Station curves ordered stern → bow |
| Baseline | baseline | Rhino.Geometry.Curve | Item | Baseline reference curve (keel line) |
| Centerline | centerline | Rhino.Geometry.Curve | Item | Centerline reference curve |
| Design Waterline | design_waterline | Rhino.Geometry.Curve | Item | Design waterline reference curve |

---

## Internal Logic (C# Script Component)

The definition uses a single C# Script component implementing the MARLIN station math:

1. **Shape Factor** — smooth beam distribution: 0.62 at stern → 1.0 at midship → 0.10 at bow
2. **Section Points** — 11-point symmetric section profile (port sheer → keel → starboard sheer)
3. **Station Curves** — NURBS curves (degree 3) through section points at each station
4. **Reference Curves** — baseline, centerline, design waterline as LineCurves

---

## Deployment on Rhino.Compute (Dell)

1. Copy `marlin_station_curves.gh` to the Rhino.Compute node (e.g., `C:\MARLIN\definitions\`)
2. In Rhino 8 on the Dell: **File > Grasshopper > File > Open** → select the `.gh`
3. Verify no missing components (all native)
4. Option A — GrasshopperPlayer: `GrasshopperPlayer marlin_station_curves.gh`
5. Option B — Rhino.Compute geometry endpoint: the definition is available at its server-side path
6. Set `RHINO_STATION_DEFINITION=marlin_station_curves` in MARLIN `.env`

---

## Testing

Run MARLIN's integration test against the live node:

```bash
cd /home/nova/uat-repo-01/backend
. .venv/bin/activate
export RHINO_COMPUTE_URL=http://<DELL_LAN_IP>:6500
python -m pytest tests/test_stations_api.py -v
```

The test `test_station_generation_real_rhino` (skipped by default) will execute against real Rhino.Compute.

---

## I/O Example (Compute JSON)

**Request** (`POST /grasshopper`):
```json
{
  "pointer": "marlin_station_curves",
  "values": [
    {"ParamName": "loa", "InnerTree": {"{0}": [{"type": "System.Double", "data": 20.0}]}},
    {"ParamName": "beam", "InnerTree": {"{0}": [{"type": "System.Double", "data": 5.5}]}},
    ...
  ]
}
```

**Response**:
```json
{
  "values": [
    {"ParamName": "stations", "InnerTree": {"{0}": [{"type": "Rhino.Geometry.Curve", "data": "curve-guid-1"}, ...]}},
    {"ParamName": "baseline", "InnerTree": {"{0}": [{"type": "Rhino.Geometry.Curve", "data": "curve-guid-baseline"}]}},
    ...
  ],
  "warnings": [],
  "errors": []
}
```

MARLIN's `normalize_values()` flattens this to `{"stations": [guid, ...], "baseline": [guid], ...}`.

---

## Version / Geometry Version

- Definition version: 1
- MARLIN `GEOMETRY_VERSION`: 1 (see `stations.py`)