# marlin_hull.gh — NURBS Hull Loft Generator

**Purpose**: Lofts station curves into NURBS hull surfaces, returns full geometry + measurements for MARLIN validation.

**Rhino/Grasshopper Version**: Rhino 8 / Grasshopper (native components only — no plugins required)

**Definition Pointer**: `marlin_hull` (server-side path on Rhino.Compute node)

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
| Mirror | mirror | System.Boolean | Yes | true | — | Mirror port side to starboard |
| Join | join | System.Boolean | Yes | true | — | Join surfaces into closed Brep |
| Deadrise | deadrise | System.Double | No | 18.0 | deg | Deadrise angle |
| Transom Width | transom_width | System.Double | No | -1.0 | m | Transom width (-1 = auto) |
| Chine Height | chine_height | System.Double | No | -1.0 | m | Chine height above keel (-1 = auto) |
| Bow Height | bow_height | System.Double | No | 0.0 | m | Bow height above sheer |

---

## Outputs (DataTree format — one entry per parameter)

| Parameter Name | NickName | Type | Access | Description |
|----------------|----------|------|--------|-------------|
| Surfaces | surfaces | Rhino.Geometry.Surface | List | NURBS hull surfaces (port, starboard) |
| Sheer | sheer | Rhino.Geometry.Curve | Item | Sheer line curve |
| Bow | bow | Rhino.Geometry.Curve | Item | Bow termination curve |
| Stern | stern | Rhino.Geometry.Curve | Item | Stern/transom termination curve |
| Measurements | measurements | System.String | Item | JSON string of measured geometry facts |

---

## Measurements JSON Structure

```json
{
  "loa": 20.0,
  "beam": 5.5,
  "draft": 1.2,
  "bounding_box": {
    "min": [0.0, -2.75, -1.2],
    "max": [20.0, 2.75, 1.2]
  },
  "surface_count": 2,
  "valid_surfaces": true,
  "symmetry": true,
  "sides": ["port", "starboard"],
  "naked_edges": 0,
  "invalid_trims": 0,
  "self_intersections": 0,
  "normals_consistent": true
}
```

---

## Internal Logic (C# Script Component)

1. **Reuse Station Math** — identical `ShapeFactor()` and `SectionPoints()` as station definition
2. **Build Station Curves** — same NURBS curves at each station
3. **Loft Port Surface** — `Brep.CreateFromLoft()` through all station curves
4. **Mirror to Starboard** — `Transform.Mirror(Plane.WorldXY)` if `mirror=true`
5. **Extract Surfaces** — `Brep.Faces[0].UnderlyingSurface()` for each side
6. **Termination Curves** — sheer (port sheer points), bow (last station), stern (first station)
7. **Measurements** — bounding box, surface count, validity, symmetry, naked edges

---

## Deployment on Rhino.Compute (Dell)

1. Copy `marlin_hull.gh` to the Rhino.Compute node (e.g., `C:\MARLIN\definitions\`)
2. In Rhino 8 on the Dell: **File > Grasshopper > File > Open** → select the `.gh`
3. Verify no missing components (all native)
4. Set `RHINO_HULL_DEFINITION=marlin_hull` in MARLIN `.env`

---

## Testing

```bash
cd /home/nova/uat-repo-01/backend
. .venv/bin/activate
export RHINO_COMPUTE_URL=http://<DELL_LAN_IP>:6500
python -m pytest tests/test_hull_api.py -v
```

Tests: `test_standard_hull_success`, `test_small_and_large_hulls`, `test_dimension_tolerance_failure_returns_failed_state`, `test_symmetry_failure_returns_failed_state`, `test_acceptance_20m_hull`.

---

## I/O Example (Compute JSON)

**Request** (`POST /grasshopper`):
```json
{
  "pointer": "marlin_hull",
  "values": [
    {"ParamName": "loa", "InnerTree": {"{0}": [{"type": "System.Double", "data": 20.0}]}},
    {"ParamName": "beam", "InnerTree": {"{0}": [{"type": "System.Double", "data": 5.5}]}},
    {"ParamName": "mirror", "InnerTree": {"{0}": [{"type": "System.Boolean", "data": true}]}},
    {"ParamName": "join", "InnerTree": {"{0}": [{"type": "System.Boolean", "data": true}]}},
    ...
  ]
}
```

**Response**:
```json
{
  "values": [
    {"ParamName": "surfaces", "InnerTree": {"{0}": [{"type": "Rhino.Geometry.Surface", "data": "surf-guid-port"}, {"type": "Rhino.Geometry.Surface", "data": "surf-guid-stbd"}]}},
    {"ParamName": "sheer", "InnerTree": {"{0}": [{"type": "Rhino.Geometry.Curve", "data": "curve-guid-sheer"}]}},
    {"ParamName": "bow", "InnerTree": {"{0}": [{"type": "Rhino.Geometry.Curve", "data": "curve-guid-bow"}]}},
    {"ParamName": "stern", "InnerTree": {"{0}": [{"type": "Rhino.Geometry.Curve", "data": "curve-guid-stern"}]}},
    {"ParamName": "measurements", "InnerTree": {"{0}": [{"type": "System.String", "data": "{\"loa\":20.0,...}"}]}},
  ],
  "warnings": [],
  "errors": []
}
```

MARLIN's `inspect_hull()` parses the measurements JSON and validates tolerances (1% LOA/beam, 2% draft).

---

## Version / Geometry Version

- Definition version: 1
- MARLIN `GEOMETRY_VERSION`: 1 (see `hull.py`)