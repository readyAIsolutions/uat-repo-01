import copy
import pytest
from fastapi.testclient import TestClient

VALID = {
    "project_id": "MARLIN-001",
    "units": "meters",
    "loa": {"value": 20, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "lwl": {"value": 18.5, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "beam": {"value": 5.5, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "draft": {"value": 1.2, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "depth": {"value": 2.4, "unit": "m", "source": "USER_SPECIFIED", "locked": True},
    "hull_family": "MONOHULL",
}


def _client():
    from app.mvp import create_app
    return TestClient(create_app())


def _post(payload):
    with _client() as client:
        response = client.post("/api/vessel/validate", json=payload)
    return response


def _codes(response):
    return {d["field"]: d["code"] for d in response.json()["error"]["details"]}


def test_valid_vessel_returns_normalized_data():
    response = _post(VALID)
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["project_id"] == "MARLIN-001"
    assert body["units"] == "m"
    assert body["hull_family"] == "MONOHULL"
    assert body["parameters"]["loa"] == {
        "value": 20.0, "unit": "m", "source": "USER_SPECIFIED", "locked": True}
    assert body["base_meters"]["loa"] == 20.0
    assert body["base_meters"]["lwl"] == 18.5


def test_missing_loa():
    payload = copy.deepcopy(VALID); del payload["loa"]
    response = _post(payload)
    assert response.status_code == 422
    assert _codes(response)["loa"] == "MISSING"
    assert response.json()["error"]["code"] == "VESSEL_VALIDATION_FAILED"


def test_negative_beam():
    payload = copy.deepcopy(VALID); payload["beam"]["value"] = -1
    assert _codes(_post(payload))["beam"] == "OUT_OF_RANGE"


def test_zero_draft():
    payload = copy.deepcopy(VALID); payload["draft"]["value"] = 0
    assert _codes(_post(payload))["draft"] == "OUT_OF_RANGE"


def test_lwl_greater_than_loa():
    payload = copy.deepcopy(VALID); payload["lwl"]["value"] = 25
    assert _codes(_post(payload))["lwl"] == "INVALID_RELATIONSHIP"


def test_depth_less_than_draft():
    payload = copy.deepcopy(VALID); payload["depth"]["value"] = 1.0
    assert _codes(_post(payload))["depth"] == "INVALID_RELATIONSHIP"


def test_unsupported_units():
    payload = copy.deepcopy(VALID); payload["units"] = "furlongs"
    assert _codes(_post(payload))["units"] == "UNSUPPORTED_UNIT"


def test_unsupported_measurement_unit():
    payload = copy.deepcopy(VALID); payload["loa"]["unit"] = "cubits"
    assert _codes(_post(payload))["loa.unit"] == "UNSUPPORTED_UNIT"


def test_malformed_numeric_input():
    payload = copy.deepcopy(VALID); payload["loa"]["value"] = "twenty"
    assert _codes(_post(payload))["loa.value"] == "NOT_A_NUMBER"


def test_missing_source():
    payload = copy.deepcopy(VALID); del payload["loa"]["source"]
    assert _codes(_post(payload))["loa.source"] == "MISSING"


def test_invalid_hull_family():
    payload = copy.deepcopy(VALID); payload["hull_family"] = "SUBMARINE"
    assert _codes(_post(payload))["hull_family"] == "INVALID_VALUE"


def test_errors_are_correlated_and_do_not_echo_values():
    payload = copy.deepcopy(VALID); payload["beam"]["value"] = -1234.5
    response = _post(payload)
    assert response.status_code == 422
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert "-1234.5" not in response.text


def test_validate_does_not_call_rhino(monkeypatch):
    from tests.stubs.rhino_stub import rhino_stub
    with rhino_stub() as (server, base):
        monkeypatch.setenv("RHINO_COMPUTE_URL", base)
        response = _post(VALID)
    assert response.status_code == 200
    assert server.records == []
