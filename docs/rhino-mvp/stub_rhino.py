"""Local Rhino.Compute-shaped stub for Section 7 browser verification.

NOT Rhino. Returns the same JSON shape MARLIN expects so the full UI workflow can
be exercised end-to-end without a licensed node. Clearly labelled as a stub.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8899


class Handler(BaseHTTPRequestHandler):
    server_version = "RhinoStub/1.0"

    def log_message(self, *args):
        pass

    def _send(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/rhino"):
            return self._send(200, {"stub": True})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        definition = body.get("definition")
        algo = body.get("algo") or {}
        if definition == "marlin_station_curves":
            stations = algo.get("stations", [])
            return self._send(200, {
                "curves": [{"id": f"curve-{s['index']}"} for s in stations],
                "reference_curves": {"baseline": {"id": "ref-baseline"},
                                     "centerline": {"id": "ref-centerline"},
                                     "design_waterline": {"id": "ref-dwl"}},
                "stub": True,
            })
        if definition == "marlin_hull_loft":
            loa = float(algo.get("loa", 20.0))
            beam = float(algo.get("beam", 5.5))
            draft = float(algo.get("draft", 1.2))
            depth = float(algo.get("depth", 2.4))
            return self._send(200, {
                "surfaces": [{"id": "port-1", "side": "port", "valid": True, "naked_edges": 2},
                             {"id": "stbd-1", "side": "starboard", "valid": True, "naked_edges": 2}],
                "sheer_line": {"id": "sheer"}, "bow_termination": {"id": "bow"},
                "stern_termination": {"id": "stern"},
                "measurements": {
                    "loa": round(loa * 0.998, 3), "beam": round(beam * 0.997, 3),
                    "draft": round(draft * 0.99, 3),
                    "bounding_box": {"min": [0.0, round(-beam / 2, 3), round(-draft, 3)],
                                     "max": [round(loa * 0.998, 3), round(beam / 2, 3),
                                             round(depth - draft, 3)]},
                    "surface_count": 2, "naked_edges": 4, "invalid_trims": 0,
                    "self_intersections": 0, "normals_consistent": True},
                "file_reference": "rhino://stub/hull.3dm", "stub": True,
            })
        return self._send(404, {"error": "unknown definition"})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
