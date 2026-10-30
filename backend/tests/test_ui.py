import json
from pathlib import Path
from fastapi.testclient import TestClient

UI_DIR = Path(__file__).resolve().parents[1] / "app" / "ui"


def _client(monkeypatch=None, **env):
    from app.mvp import create_app
    if monkeypatch is not None:
        for k, v in env.items():
            monkeypatch.setenv(k, v)
    return TestClient(create_app())


def test_page_loads_with_all_controls():
    with _client() as client:
        response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    html = response.text
    for element in ["project-name", "loa", "lwl", "beam", "draft", "depth",
                    "hull-family", "station-count", "btn-rhino", "btn-validate",
                    "btn-stations", "btn-hull", "btn-view", "btn-open",
                    "rhino-pill", "out-validation", "out-hull", "dims-body",
                    "out-warnings", "out-errors", "out-reference", "viewer"]:
        assert f'id="{element}"' in html, element
    assert "/ui/app.js" in html


def test_static_assets_are_served():
    with _client() as client:
        for path, needle in [("/ui/app.js", "/api/vessel/hull"),
                             ("/ui/app.js", "/api/rhino/status"),
                             ("/ui/app.js", "/api/vessel/validate"),
                             ("/ui/styles.css", ".pill")]:
            response = client.get(path)
            assert response.status_code == 200, path
            assert needle in response.text, path
        vendor = client.get("/ui/vendor/three.module.js")
        assert vendor.status_code == 200
        assert "THREE" in vendor.text[:200000] or len(vendor.text) > 1000


def test_ui_is_absent_from_openapi_surface():
    with _client() as client:
        paths = set(client.get("/openapi.json").json()["paths"])
    assert "/" not in paths and "/ui/app.js" not in paths
    assert "/reconstruct" not in paths  # Module 10 UI page is also UI, not API
    assert paths == {"/health", "/api/rhino/status", "/api/rhino/box",
        "/api/vessel/hull/3dm/{name}",
                     "/api/rhino/capabilities", "/api/vessel/validate",
                     "/api/vessel/stations", "/api/vessel/hull",
                     "/api/reconstruct/capabilities", "/api/reconstruct/jobs",
                     "/api/reconstruct/jobs/{job_id}",
                     "/api/reconstruct/jobs/{job_id}/cancel",
                     "/api/reconstruct/jobs/{job_id}/model",
                     "/api/reconstruct/jobs/{job_id}/export",
                     "/api/reconstruct/jobs/{job_id}/images/{idx}"}


def test_no_secrets_reach_the_browser(monkeypatch):
    with _client(monkeypatch, RHINO_COMPUTE_URL="http://127.0.0.1:1",
                 RHINO_COMPUTE_API_KEY="SECRET_SENTINEL") as client:
        html = client.get("/").text
        js = client.get("/ui/app.js").text
        status = client.get("/api/rhino/status")
    for payload in (html, js, status.text):
        assert "SECRET_SENTINEL" not in payload
    assert "Authorization" not in js  # the browser never sends the API key


def test_ui_wires_expected_endpoints():
    js = (UI_DIR / "app.js").read_text()
    for endpoint in ["/api/rhino/status", "/api/vessel/validate",
                     "/api/vessel/stations", "/api/vessel/hull"]:
        assert endpoint in js, endpoint
    assert "AbortController" in js        # API timeout handling
    assert "Rhino.Compute unavailable" in js  # clear offline message


def test_backend_validation_errors_shape():
    payload = {"project_id": "P", "units": "meters",
               "loa": {"value": 0, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
               "lwl": {"value": 1, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
               "beam": {"value": 1, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
               "draft": {"value": 1, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
               "depth": {"value": 2, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
               "hull_family": "MONOHULL"}
    with _client() as client:
        response = client.post("/api/vessel/validate", json=payload)
    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert details and all({"field", "code", "message"} <= set(d) for d in details)


def test_ui_reports_rhino_offline_via_status_endpoint(monkeypatch):
    with _client(monkeypatch, RHINO_COMPUTE_URL="http://127.0.0.1:1") as client:
        body = client.get("/api/rhino/status").json()
    assert body["reachable"] is False


def test_ui_declares_required_states():
    js = (UI_DIR / "app.js").read_text()
    html = (UI_DIR / "index.html").read_text()
    for state in ["NOT_STARTED", "VALIDATING", "VALID", "INVALID",
                  "GENERATING", "SUCCESS", "FAILED"]:
        assert state in js or state in html, state
    for rhino in ["CHECKING", "CONNECTED", "DISCONNECTED", "ERROR"]:
        assert rhino in js, rhino
    # guardrail: generation gated on validation
    assert 'state.validation === "VALID"' in js
    assert "disabled" in html  # generate buttons start disabled
