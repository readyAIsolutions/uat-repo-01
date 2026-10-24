import pytest


@pytest.mark.parametrize("method,args", [("health_check", ()), ("create_box", (1, 2, 3)),
    ("create_geometry", ({"kind": "box"},)), ("execute_grasshopper", ("unused", {}))])
async def test_unconfigured_adapter_fails_every_operation(method, args):
    from app.services.rhino.contract import RhinoService, RhinoNotConfiguredError
    from app.services.rhino.unconfigured import UnconfiguredRhinoAdapter
    service = UnconfiguredRhinoAdapter()
    assert isinstance(service, RhinoService)
    with pytest.raises(RhinoNotConfiguredError) as caught:
        await getattr(service, method)(*args)
    assert caught.value.code == "RHINO_NOT_CONFIGURED"
