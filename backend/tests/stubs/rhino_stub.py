"""TEST ONLY: a loopback stub standing in for Rhino.Compute.

Emulates the OFFICIAL Compute contract (see app/services/rhino/client.py):
  GET  /healthcheck  -> 200 text
  GET  /version      -> 200 json
  POST /grasshopper  -> 200 {"values":[...], "warnings":[], "errors":[]}
Records every request and answers with a canned response chosen by the test.
No real Rhino, no geometry, no license.
"""
import json
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def outputs(**named) -> dict:
    """Build a Compute-style response body with named outputs."""
    values = []
    for name, items in named.items():
        if not isinstance(items, (list, tuple)):
            items = [items]
        leaves = []
        for v in items:
            if isinstance(v, (dict, list)):
                leaves.append({"type": "Rhino.Geometry.GeometryBase", "data": v})
            else:
                leaves.append({"type": "System.String", "data": str(v)})
        values.append({"ParamName": name, "InnerTree": {"{0}": leaves}})
    return {"values": values, "warnings": [], "errors": []}


def _input_values(record) -> dict:
    body = json.loads(record["body"]) if record.get("body") else {}
    out = {}
    for tree in body.get("values", []) or []:
        name = tree.get("ParamName")
        data = []
        for branch in (tree.get("InnerTree") or {}).values():
            for leaf in branch or []:
                if isinstance(leaf, dict) and "data" in leaf:
                    data.append(leaf["data"])
        if name is not None and data:
            out[name] = data[0]
    return out


def compute_responder(record):
    """Default responder emulating a healthy Rhino.Compute node."""
    path = record["path"]
    if path.startswith("/healthcheck"):
        return 200, b"Healthy", 0
    if path.startswith("/version"):
        return 200, {"version": "8.0.0-stub", "rhino": "8.0.0-stub"}, 0
    if path.startswith("/io"):
        return 200, {"FileName": "marlin_hull.gh", "InputNames": ["loa"],
                     "OutputNames": ["stations"]}, 0
    if path.startswith("/grasshopper"):
        v = _input_values(record)
        loa = float(v.get("loa", 20.0)); beam = float(v.get("beam", 5.5))
        draft = float(v.get("draft", 1.2)); depth = float(v.get("depth", 2.4))
        count = int(v.get("station_count", 15))
        measurements = {"loa": loa * 0.998, "beam": beam * 0.997, "draft": draft * 0.99,
                        "bounding_box": {"min": [0.0, -beam / 2, -draft],
                                         "max": [loa, beam / 2, depth - draft]},
                        "surface_count": 2, "naked_edges": 4, "invalid_trims": 0,
                        "self_intersections": 0, "normals_consistent": True,
                        "valid_surfaces": True, "symmetry": True,
                        "sides": ["port", "starboard"]}
        return 200, outputs(stations=[f"curve-{i}" for i in range(count)],
                            baseline="ref-baseline", centerline="ref-centerline",
                            design_waterline="ref-dwl", surfaces=["port-1", "stbd-1"],
                            sheer="sheer", bow="bow", stern="stern",
                            measurements=json.dumps(measurements)), 0
    return 404, {"error": "not found"}, 0


class _Handler(BaseHTTPRequestHandler):
    server_version = "RhinoStub/1.0"

    def log_message(self, *args):
        pass

    def _handle(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        record = {"method": self.command, "path": self.path,
                  "headers": {k.lower(): v for k, v in self.headers.items()},
                  "body": body.decode("utf-8", "replace")}
        self.server.records.append(record)
        status, payload, delay = self.server.responder(record)
        if delay:
            time.sleep(delay)
        if payload is None:
            data = b""
        elif isinstance(payload, (bytes, bytearray)):
            data = bytes(payload)
        else:
            data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if data:
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

    do_GET = do_POST = do_PUT = do_DELETE = _handle


@contextmanager
def rhino_stub(responder=compute_responder):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.records = []
    server.responder = responder
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
