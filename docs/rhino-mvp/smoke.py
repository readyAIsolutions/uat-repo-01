"""Run a real, local-only Uvicorn smoke test and verify safe request logs.

Two scenarios:
  1. unconfigured  (no RHINO_COMPUTE_URL) -> unconfigured adapter
  2. configured-unreachable (RHINO_COMPUTE_URL=http://127.0.0.1:1)
Both must serve the documented surface with NO startup network probe and
secret-free logs. No live Rhino is contacted.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
CLEAR = {"MARLIN_ENVIRONMENT", "MARLIN_LOG_LEVEL", "RHINO_COMPUTE_URL", "RHINO_COMPUTE_API_KEY"}
SENTINEL = "SECRET_SENTINEL"
VESSEL = {
    "project_id": "SMOKE-001", "units": "meters",
    "loa": {"value": 20, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "lwl": {"value": 18.5, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "beam": {"value": 5.5, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "draft": {"value": 1.2, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "depth": {"value": 2.4, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "hull_family": "MONOHULL",
}


def _run_scenario(extra_env: dict, expected_stations_code: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in CLEAR}
    env["MARLIN_ENVIRONMENT"] = "test"
    env.update(extra_env)
    with socket.socket() as listener, tempfile.TemporaryFile(mode="w+") as log:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        command = [sys.executable, "-m", "uvicorn", "app.mvp:create_app", "--factory",
                   "--app-dir", "backend", "--fd", str(listener.fileno()),
                   "--no-access-log", "--log-level", "warning"]
        process = subprocess.Popen(command, cwd=ROOT, env=env, pass_fds=(listener.fileno(),),
                                   stdout=log, stderr=subprocess.STDOUT)
        base = f"http://127.0.0.1:{port}"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        checks = []
        try:
            deadline = time.monotonic() + 15
            while True:
                if process.poll() is not None:
                    raise RuntimeError("Uvicorn exited before readiness")
                try:
                    with opener.open(base + "/health", timeout=1) as response:
                        assert json.load(response) == {"status": "ok", "service": "vesyntra-rhino-mvp"}
                    break
                except (urllib.error.URLError, TimeoutError):
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Uvicorn readiness timeout") from None
                    time.sleep(0.05)
            for path, expected in [("/health", 200), ("/docs", 200), ("/openapi.json", 200),
                                   ("/api/rhino/status", 200), ("/api/rhino/capabilities", 200),
                                   (f"/{SENTINEL}?token={SENTINEL}", 404)]:
                request = urllib.request.Request(base + path, headers={"X-Request-ID": SENTINEL})
                try:
                    response = opener.open(request, timeout=3)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    body = response.read().decode()
                    assert response.status == expected
                    cid = response.headers["x-request-id"]
                    assert len(cid) == 32 and cid != SENTINEL
                    if expected == 404:
                        assert json.loads(body)["request_id"] == cid
                        assert SENTINEL not in body
                    checks.append({"endpoint": path.split("?")[0].replace(SENTINEL, "<unknown>"),
                                   "status": response.status})
            post = urllib.request.Request(
                base + "/api/vessel/validate", data=json.dumps(VESSEL).encode(),
                headers={"Content-Type": "application/json", "X-Request-ID": SENTINEL})
            with opener.open(post, timeout=3) as response:
                body = response.read().decode()
                assert response.status == 200
                assert json.loads(body)["valid"] is True
                assert SENTINEL not in body
                checks.append({"endpoint": "/api/vessel/validate", "status": 200})
            stations = urllib.request.Request(
                base + "/api/vessel/stations", data=json.dumps(VESSEL).encode(),
                headers={"Content-Type": "application/json", "X-Request-ID": SENTINEL})
            try:
                with opener.open(stations, timeout=3) as response:
                    status, body = response.status, response.read().decode()
            except urllib.error.HTTPError as error:
                status, body = error.status, error.read().decode()
            assert status == 503, status
            assert json.loads(body)["error"]["code"] == expected_stations_code
            assert SENTINEL not in body
            checks.append({"endpoint": "/api/vessel/stations", "status": 503,
                           "code": expected_stations_code})
            hull_req = urllib.request.Request(
                base + "/api/vessel/hull", data=json.dumps(VESSEL).encode(),
                headers={"Content-Type": "application/json", "X-Request-ID": SENTINEL})
            try:
                with opener.open(hull_req, timeout=3) as response:
                    hstatus, hbody = response.status, response.read().decode()
            except urllib.error.HTTPError as error:
                hstatus, hbody = error.status, error.read().decode()
            assert hstatus == 503, hstatus
            assert json.loads(hbody)["error"]["code"] == expected_stations_code
            assert SENTINEL not in hbody
            checks.append({"endpoint": "/api/vessel/hull", "status": 503,
                           "code": expected_stations_code})
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        log.seek(0)
        output = log.read()
        assert SENTINEL not in output, "Sensitive input found in server logs"
        assert '"event": "request"' in output
        return {"checks": checks, "secret_free_logs": True,
                "server_stopped": process.poll() is not None}


if __name__ == "__main__":
    results = {
        "unconfigured": _run_scenario({}, "RHINO_NOT_CONFIGURED"),
        "configured_unreachable": _run_scenario(
            {"RHINO_COMPUTE_URL": "http://127.0.0.1:1"}, "RHINO_UNAVAILABLE"),
    }
    print(json.dumps(results, indent=2))
