"""Routes depend on the contract, not an adapter implementation."""
from fastapi import Request
from .contract import RhinoService


def get_rhino_service(request: Request) -> RhinoService:
    return request.app.state.rhino_service
