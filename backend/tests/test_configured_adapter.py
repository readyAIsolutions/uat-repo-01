import json
import pytest
from tests.stubs.rhino_stub import rhino_stub, outputs


def _adapter(base, key=None, **kw):
    from app.services.rhino.client import RhinoComputeClient
    from app.services.rhino.configured import ConfiguredRhinoAdapter
    client = RhinoComputeClient(base, api_key=key, **kw)
    return ConfiguredRhinoAdapter(client, station_definition="marlin_station_curves",
                                  hull_definition="marlin_hull", box_definition="marlin_box")


async def test_health_check_ok():
    with rhino_stub() as (server, base):
        assert await _adapter(base).health_check() == {"configured": True, "reachable": True, "status": "ok"}


async def test_health_check_unreachable_does_not_raise():
    assert await _adapter("http://127.0.0.1:1").health_check() == {
        "configured": True, "reachable": False, "status": "unreachable"}


async def test_health_check_node_error_status():
    with rhino_stub(lambda r: (500, {"error": "down"}, 0)) as (server, base):
        result = await _adapter(base).health_check()
    assert result == {"configured": True, "reachable": True, "status": "error", "status_code": 500}


async def test_execute_grasshopper_returns_normalized_outputs():
    with rhino_stub() as (server, base):
        result = await _adapter(base).execute_grasshopper("marlin_hull", {"loa": 12.0})
    body = json.loads(server.records[0]["body"])
    assert server.records[0]["path"] == "/grasshopper"
    assert body["pointer"] == "marlin_hull"
    assert {v["ParamName"] for v in body["values"]} == {"loa"}
    assert isinstance(result.get("stations"), list)  # normalized outputs


async def test_create_box_transport_round_trip():
    with rhino_stub() as (server, base):
        result = await _adapter(base, key="SECRET_SENTINEL").create_box(1.0, 2.0, 3.0)
    body = json.loads(server.records[0]["body"])
    assert result["source"] == "rhino-compute"
    assert result["definition"] == "marlin_box"
    assert result["inputs"] == {"width": 1.0, "length": 2.0, "height": 3.0}
    assert body["pointer"] == "marlin_box"
    assert server.records[0]["headers"]["rhinocomputekey"] == "SECRET_SENTINEL"


async def test_create_geometry_reserved():
    from app.services.rhino.errors import RhinoCapabilityUnavailableError
    with rhino_stub() as (server, base):
        with pytest.raises(RhinoCapabilityUnavailableError) as caught:
            await _adapter(base).create_geometry({"kind": "hull"})
    assert caught.value.code == "RHINO_CAPABILITY_UNAVAILABLE"
    assert server.records == []


async def test_adapter_satisfies_contract():
    from app.services.rhino.contract import RhinoService
    with rhino_stub() as (server, base):
        assert isinstance(_adapter(base), RhinoService)
