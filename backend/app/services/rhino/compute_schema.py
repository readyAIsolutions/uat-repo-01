"""Grasshopper request/response schema helpers for Rhino.Compute.

Official request body (src/compute.geometry/IO/Schema.cs): ``values`` is a list of
DataTrees, one per input parameter, each ``{ParamName, InnerTree: {"{0}": [leaf]}}``
where a leaf is ``{type, data}`` (a .NET type name + value). The response mirrors
this with the definition's outputs plus ``warnings``/``errors``.
"""
from __future__ import annotations


def _leaf(value) -> dict:
    if isinstance(value, bool):
        return {"type": "System.Boolean", "data": value}
    if isinstance(value, int):
        return {"type": "System.Int32", "data": value}
    if isinstance(value, float):
        return {"type": "System.Double", "data": value}
    return {"type": "System.String", "data": str(value)}


def build_values(inputs: dict) -> list:
    """Build the ``values`` list (one DataTree per input) from a simple dict."""
    values = []
    for name, value in inputs.items():
        items = value if isinstance(value, (list, tuple)) else [value]
        values.append({"ParamName": name, "InnerTree": {"{0}": [_leaf(v) for v in items]}})
    return values


def normalize_values(response: dict) -> dict:
    """Flatten a compute response into ``{output_name: [data, ...]}``."""
    out: dict = {}
    for tree in (response or {}).get("values", []) or []:
        if not isinstance(tree, dict):
            continue
        name = tree.get("ParamName") or tree.get("paramName") or "?"
        items = []
        for branch in (tree.get("InnerTree") or {}).values():
            for leaf in branch or []:
                if isinstance(leaf, dict) and "data" in leaf:
                    items.append(leaf["data"])
        out[name] = items
    return out
