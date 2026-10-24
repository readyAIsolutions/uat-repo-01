import logging
import pytest
from fastapi import Depends, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from app.mvp import create_app
from app.services.rhino.dependencies import get_rhino_service


@pytest.mark.parametrize("kind,status", [("http", 401), ("validation", 422),
                                         ("rhino", 503), ("unexpected", 500)])
def test_all_error_logs_are_safe(kind, status, caplog):
    app = create_app()

    class Body(BaseModel):
        number: int

    @app.post("/validation")
    def validation(body: Body):
        return body

    @app.get("/http")
    def http():
        raise HTTPException(401, detail={"secret": "SECRET_SENTINEL"})

    @app.get("/unexpected")
    def unexpected():
        raise RuntimeError("SECRET_SENTINEL")

    @app.get("/rhino")
    async def rhino(service=Depends(get_rhino_service)):
        return await service.health_check()

    with caplog.at_level(logging.INFO, logger="marlin.mvp"):
        with TestClient(app) as client:
            response = (client.post("/validation", json={"number": "SECRET_SENTINEL"})
                        if kind == "validation" else client.get("/" + kind))
    assert response.status_code == status
    records = [r for r in caplog.records if r.name == "marlin.mvp"]
    assert len(records) == 1
    assert response.headers["x-request-id"] in records[0].getMessage()
    assert "SECRET_SENTINEL" not in repr(records[0].__dict__) + response.text
