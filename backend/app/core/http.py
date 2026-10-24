"""ASGI safety boundary. Never serialize exception text or request data."""
import json
import logging
from uuid import uuid4

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from ..services.rhino.contract import RhinoNotConfiguredError
from ..services.vessel.validation import VesselValidationError
from ..services.rhino.errors import (
    RhinoCapabilityUnavailableError,
    RhinoRequestError,
    RhinoUnavailableError,
)

logger = logging.getLogger("marlin.mvp")


def error_response(code, message, status, request_id):
    return JSONResponse({"error": {"code": code, "message": message},
                         "request_id": request_id}, status_code=status)


def install_error_handlers(app):
    @app.exception_handler(RhinoNotConfiguredError)
    async def rhino_unavailable(request, exc):
        return error_response("RHINO_NOT_CONFIGURED", "Rhino unavailable in Section 1", 503,
                              request.state.request_id)

    @app.exception_handler(RhinoUnavailableError)
    async def rhino_node_unavailable(request, exc):
        return error_response("RHINO_UNAVAILABLE", "Rhino node unavailable", 503,
                              request.state.request_id)

    @app.exception_handler(RhinoRequestError)
    async def rhino_request_failed(request, exc):
        return error_response("RHINO_REQUEST_FAILED", "Rhino request failed", 502,
                              request.state.request_id)

    @app.exception_handler(RhinoCapabilityUnavailableError)
    async def rhino_capability_unavailable(request, exc):
        return error_response("RHINO_CAPABILITY_UNAVAILABLE", "Rhino capability unavailable", 501,
                              request.state.request_id)

    @app.exception_handler(VesselValidationError)
    async def vessel_validation_failed(request, exc):
        return JSONResponse({"error": {"code": "VESSEL_VALIDATION_FAILED",
                                       "message": "Vessel geometry validation failed",
                                       "details": exc.issues},
                             "request_id": request.state.request_id}, status_code=422)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error_response("HTTP_ERROR", "Request failed", exc.status_code,
                              request.state.request_id)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error_response("VALIDATION_ERROR", "Invalid request", 422,
                              request.state.request_id)


class SafeRequestMiddleware:
    def __init__(self, app, log_level="INFO"):
        self.app = app
        self.log_level = logging.getLevelName(log_level)
        logger.setLevel(logging.DEBUG)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        # Server-owned ID: never trust or echo arbitrary client-supplied IDs.
        request_id = uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        started = False
        status = 500

        async def safe_send(message):
            nonlocal started, status
            if message["type"] == "http.response.start":
                started = True
                status = message["status"]
                message = dict(message)
                headers = [(k, v) for k, v in message.get("headers", [])
                           if k.lower() != b"x-request-id"]
                message["headers"] = headers + [(b"x-request-id", request_id.encode())]
            await send(message)

        try:
            await self.app(scope, receive, safe_send)
        except Exception:
            # Do not let the server log exception tracebacks containing secrets.
            # A response already started cannot be replaced (streaming not in MVP).
            if not started:
                response = error_response("INTERNAL_ERROR", "Internal server error", 500, request_id)
                await response(scope, receive, safe_send)
        finally:
            level = logging.ERROR if status >= 500 else logging.INFO
            if level >= self.log_level:
                route = getattr(scope.get("route"), "path", "<unmatched>")
                method = scope.get("method", "")
                if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE", "CONNECT"}:
                    method = "OTHER"
                logger.log(level, json.dumps({"event": "request", "method": method,
                    "route": route, "status": status, "request_id": request_id}))
