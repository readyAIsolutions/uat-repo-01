from tests.stubs.rhino_stub import rhino_stub


def _adapter(base):
    from app.services.rhino.client import RhinoComputeClient
    from app.services.rhino.configured import ConfiguredRhinoAdapter
    return ConfiguredRhinoAdapter(RhinoComputeClient(base))


async def test_execute_grasshopper_with_empty_inputs():
    import json
    with rhino_stub() as (server, base):
        await _adapter(base).execute_grasshopper("marlin_hull", {})
    body = json.loads(server.records[0]["body"])
    assert body["pointer"] == "marlin_hull"
    assert body["values"] == []
