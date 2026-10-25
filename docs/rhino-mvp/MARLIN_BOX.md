# marlin_box.gh — Primitive Box Generator

**Purpose**: Simple connectivity/smoke test definition — generates a primitive box to verify Rhino.Compute is reachable and executing Grasshopper definitions correctly.

**Rhino/Grasshopper Version**: Rhino 8 / Grasshopper (native components only)

**Definition Pointer**: `marlin_box` (server-side path on Rhino.Compute node)

---

## Inputs (DataTree format)

| Parameter Name | NickName | Type | Required | Default | Units | Description |
|----------------|----------|------|----------|---------|-------|-------------|
| Width | width | System.Double | Yes | 5.5 | m | Box width (Y dimension) |
| Length | length | System.Double | Yes | 20.0 | m | Box length (X dimension) |
| Height | height | System.Double | Yes | 2.4 | m | Box height (Z dimension) |

---

## Outputs (DataTree format)

| Parameter Name | NickName | Type | Access | Description |
|----------------|----------|------|--------|-------------|
| Geometry | geometry | Rhino.Geometry.GeometryBase | Item | Closed box Brep |

---

## Internal Logic (Native Components)

1. **Box** component — constructs box from WorldXY plane + X/Y/Z dimensions
2. **Deconstruct Box** — breaks box into 6 faces
3. **Brep Join** — joins faces into a single closed Brep
4. **Geometry Output** — emits the joined Brep

---

## Deployment on Rhino.Compute (Dell)

1. Copy `marlin_box.gh` to the Rhino.Compute node
2. In Rhino 8: **File > Grasshopper > File > Open** → select the `.gh`
3. Set `RHINO_BOX_DEFINITION=marlin_box` in MARLIN `.env`

---

## Testing

```bash
cd /home/nova/uat-repo-01/backend
. .venv/bin/activate
export RHINO_COMPUTE_URL=http://<DELL_LAN_IP>:6500
python -m pytest tests/test_rhino_client.py::test_box_primitive -v
```

The test calls `/api/rhino/box` which executes this definition.

---

## I/O Example

**Request**:
```json
{
  "pointer": "marlin_box",
  "values": [
    {"ParamName": "length", "InnerTree": {"{0}": [{"type": "System.Double", "data": 20.0}]}},
    {"ParamName": "width", "InnerTree": {"{0}": [{"type": "System.Double", "data": 5.5}]}},
    {"ParamName": "height", "InnerTree": {"{0}": [{"type": "System.Double", "data": 2.4}]}}
  ]
}
```

**Response**:
```json
{
  "values": [
    {"ParamName": "geometry", "InnerTree": {"{0}": [{"type": "Rhino.Geometry.Brep", "data": "brep-guid"}]}}
  ],
  "warnings": [],
  "errors": []
}
```