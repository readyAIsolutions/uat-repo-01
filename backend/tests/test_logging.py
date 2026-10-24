import json
import logging
from fastapi.testclient import TestClient


def test_safe_structured_request_log(caplog):
    from app.mvp import create_app
    original_handlers = list(logging.getLogger().handlers)
    app = create_app()

    @app.get("/item/{value}")
    def item(value: str):
        raise RuntimeError(value)

    with caplog.at_level(logging.INFO, logger="marlin.mvp"):
        with TestClient(app) as client:
            response = client.get("/item/SECRET_SENTINEL?token=SECRET_SENTINEL",
                headers={"Authorization": "SECRET_SENTINEL", "X-Request-ID": "SECRET_SENTINEL"})
            client.get("/SECRET_SENTINEL")
    records = [r for r in caplog.records if r.name == "marlin.mvp"]
    assert len(records) == 2
    data = json.loads(records[0].getMessage())
    assert data == {"event": "request", "method": "GET", "route": "/item/{value}",
                    "status": 500, "request_id": response.headers["x-request-id"]}
    assert json.loads(records[1].getMessage())["route"] == "<unmatched>"
    assert "SECRET_SENTINEL" not in str([(r.msg, r.args, r.exc_info) for r in records])
    assert list(logging.getLogger().handlers) == original_handlers
