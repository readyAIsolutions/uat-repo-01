import pytest
from tests.stubs.rhino_stub import rhino_stub
from app.services.rhino.client import API_KEY_HEADER


async def test_health_uses_healthcheck_and_sends_rhinocomputekey():
    with rhino_stub() as (server, base):
        from app.services.rhino.client import RhinoComputeClient
        client = RhinoComputeClient(base, api_key="SECRET_SENTINEL")
        result = await client.health()
    assert result == {"reachable": True, "status_code": 200, "healthy": True}
    assert server.records[0]["method"] == "GET"
    assert server.records[0]["path"] == "/healthcheck"
    assert server.records[0]["headers"][API_KEY_HEADER.lower()] == "SECRET_SENTINEL"
    assert "Authorization" not in server.records[0]["headers"]
    assert "SECRET_SENTINEL" not in repr(result) + repr(client)


async def test_version_endpoint():
    with rhino_stub() as (server, base):
        from app.services.rhino.client import RhinoComputeClient
        result = await RhinoComputeClient(base).version()
    assert "version" in result
    assert server.records[0]["path"] == "/version"


async def test_unreachable_raises_typed_error_without_leaking():
    from app.services.rhino.client import RhinoComputeClient
    from app.services.rhino.errors import RhinoUnavailableError
    client = RhinoComputeClient("http://127.0.0.1:1", api_key="SECRET_SENTINEL")
    with pytest.raises(RhinoUnavailableError) as caught:
        await client.health()
    assert caught.value.code == "RHINO_UNAVAILABLE"
    assert "SECRET_SENTINEL" not in str(caught.value)


async def test_timeout_raises_unavailable():
    with rhino_stub(lambda r: (200, b"Healthy", 2.0)) as (server, base):
        from app.services.rhino.client import RhinoComputeClient
        from app.services.rhino.errors import RhinoUnavailableError
        with pytest.raises(RhinoUnavailableError):
            await RhinoComputeClient(base, timeout=0.3).health()


async def test_http_5xx_raises_request_error():
    from app.services.rhino.client import RhinoComputeClient
    from app.services.rhino.errors import RhinoRequestError
    with rhino_stub(lambda r: (500, {"error": "SECRET_SENTINEL"}, 0)) as (server, base):
        with pytest.raises(RhinoRequestError) as caught:
            await RhinoComputeClient(base).version()
    assert caught.value.status_code == 500
    assert "SECRET_SENTINEL" not in str(caught.value)


async def test_401_is_authentication_error_without_echo():
    from app.services.rhino.client import RhinoComputeClient
    from app.services.rhino.errors import RhinoRequestError
    with rhino_stub(lambda r: (401, "Api Key was not provided.", 0)) as (server, base):
        with pytest.raises(RhinoRequestError) as caught:
            await RhinoComputeClient(base).health()
    assert caught.value.reason == "authentication_failed"


async def test_no_api_key_means_no_key_header():
    with rhino_stub() as (server, base):
        from app.services.rhino.client import RhinoComputeClient
        await RhinoComputeClient(base).health()
    assert API_KEY_HEADER.lower() not in server.records[0]["headers"]


async def test_solve_definition_sends_official_schema():
    with rhino_stub() as (server, base):
        from app.services.rhino.client import RhinoComputeClient
        result = await RhinoComputeClient(base).solve_definition(
            pointer="marlin_hull", values=[])
    body = __import__("json").loads(server.records[0]["body"])
    assert server.records[0]["path"] == "/grasshopper"
    assert body["pointer"] == "marlin_hull"
    assert body["modelunits"] == "Meters"
    assert body["cachesolve"] is False
    assert "values" in body
    assert "values" in result and "warnings" in result


async def test_solve_definition_requires_pointer_or_algo():
    from app.services.rhino.client import RhinoComputeClient
    with rhino_stub() as (server, base):
        with pytest.raises(ValueError):
            await RhinoComputeClient(base).solve_definition(values=[])
