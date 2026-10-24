import logging
import json
import pytest
from tests.stubs.rhino_stub import rhino_stub


def _client(base, **kw):
    from app.services.rhino.client import RhinoComputeClient
    return RhinoComputeClient(base, **kw)


async def test_invalid_json_body_raises_request_error():
    from app.services.rhino.errors import RhinoRequestError
    with rhino_stub(lambda r: (200, b"<html>not json</html>", 0)) as (server, base):
        with pytest.raises(RhinoRequestError) as caught:
            await _client(base).version()
        assert caught.value.reason == "invalid_json"
        assert "not json" not in str(caught.value)


async def test_empty_200_body_is_empty_dict():
    with rhino_stub(lambda r: (200, None, 0)) as (server, base):
        assert await _client(base).solve_definition(pointer="x", values=[]) == {}


async def test_blank_api_key_sends_no_key_header():
    from app.services.rhino.client import API_KEY_HEADER
    with rhino_stub() as (server, base):
        await _client(base, api_key="").health()
        assert API_KEY_HEADER.lower() not in server.records[0]["headers"]


async def test_api_key_never_logged(caplog):
    with caplog.at_level(logging.DEBUG):
        with rhino_stub() as (server, base):
            await _client(base, api_key="SECRET_SENTINEL").solve_definition(pointer="d", values=[])
    assert "SECRET_SENTINEL" not in caplog.text


async def test_io_query_endpoint():
    with rhino_stub() as (server, base):
        await _client(base).io("marlin_hull.gh")
    assert server.records[0]["path"].startswith("/io?requestedFile=")


async def test_model_units_default_is_meters():
    with rhino_stub() as (server, base):
        await _client(base).solve_definition(pointer="d", values=[])
    assert json.loads(server.records[0]["body"])["modelunits"] == "Meters"
