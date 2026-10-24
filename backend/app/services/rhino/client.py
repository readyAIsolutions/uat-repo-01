"""Rhino.Compute REST client — OFFICIAL contract (McNeel Compute 8.x).

Verified against developer.rhino3d.com and the compute.rhino3d source:
  GET  /healthcheck   liveness (API key validated by middleware when configured)
  GET  /version       server + Rhino version
  GET  /validate      liveness + API-key check
  GET  /io            introspect a Grasshopper definition's inputs/outputs
  POST /grasshopper   solve a Grasshopper definition (Schema body)

API key: header ``RhinoComputeKey`` (src/rhino.compute/ApiKeyMiddleware.cs).
NOT ``Authorization: Bearer``.

Grasshopper Schema body (src/compute.geometry/IO/Schema.cs):
  {"pointer"|"algo": ..., "values": [ <DataTree per input param> ], ...}
The response carries ``values`` (outputs), ``warnings`` and ``errors``.

The api_key is held privately and never appears in repr() or error text.
"""
from __future__ import annotations

import asyncio

import httpx

from .errors import RhinoRequestError, RhinoUnavailableError

DEFAULT_TIMEOUT = 10.0
HEALTHCHECK_PATH = "/healthcheck"
VERSION_PATH = "/version"
VALIDATE_PATH = "/validate"
IO_PATH = "/io"
GRASSHOPPER_PATH = "/grasshopper"
API_KEY_HEADER = "RhinoComputeKey"


class RhinoComputeClient:
    def __init__(self, base_url: str, api_key: str | None = None,
                 timeout: float = DEFAULT_TIMEOUT, max_attempts: int = 1,
                 backoff: float = 0.0, model_units: str = "Meters") -> None:
        self._base_url = str(base_url).rstrip("/")
        self._api_key = api_key
        self._timeout = float(timeout)
        self._max_attempts = max(1, int(max_attempts))
        self._backoff = max(0.0, float(backoff))
        self._model_units = model_units

    @staticmethod
    def _retryable_status(status_code: int) -> bool:
        return status_code >= 500 or status_code == 429

    async def _sleep_before_retry(self, attempt: int) -> None:
        if self._backoff > 0:
            await asyncio.sleep(self._backoff * (2 ** (attempt - 1)))

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            # Official McNeel Compute API-key header (not Authorization: Bearer).
            headers[API_KEY_HEADER] = self._api_key
        return headers

    async def _exchange(self, method: str, path: str, payload: dict | None = None):
        """Single HTTP exchange with bounded retries on transient failures."""
        url = self._base_url + path
        attempt = 0
        while True:
            attempt += 1
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.request(method, url, json=payload, headers=self._headers())
            except httpx.TimeoutException:
                error = RhinoUnavailableError("rhino-compute timeout")
            except httpx.HTTPError:
                error = RhinoUnavailableError("rhino-compute unreachable")
            else:
                if response.status_code in (401, 403):
                    # Bad/missing RhinoComputeKey. Never echo the key or body.
                    raise RhinoRequestError(response.status_code, reason="authentication_failed")
                if response.status_code >= 400:
                    if (self._retryable_status(response.status_code)
                            and attempt < self._max_attempts):
                        await self._sleep_before_retry(attempt)
                        continue
                    raise RhinoRequestError(response.status_code)
                return response
            if attempt < self._max_attempts:
                await self._sleep_before_retry(attempt)
                continue
            raise error

    async def _request_json(self, method: str, path: str, payload: dict | None = None) -> dict:
        response = await self._exchange(method, path, payload)
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            raise RhinoRequestError(response.status_code, reason="invalid_json") from None

    async def _request_text(self, method: str, path: str) -> str:
        response = await self._exchange(method, path)
        return response.text

    async def health(self) -> dict:
        """GET /healthcheck — liveness (and API-key validation when configured)."""
        text = await self._request_text("GET", HEALTHCHECK_PATH)
        return {"reachable": True, "status_code": 200, "healthy": "unhealthy" not in text.lower()}

    async def version(self) -> dict:
        """GET /version — server + Rhino version information."""
        return await self._request_json("GET", VERSION_PATH)

    async def validate(self) -> dict:
        return await self._request_json("GET", VALIDATE_PATH)

    async def io(self, requested_file: str) -> dict:
        """GET /io?requestedFile=... — a definition's inputs/outputs schema."""
        return await self._request_json("GET", f"{IO_PATH}?requestedFile={requested_file}")

    async def solve_definition(self, *, pointer: str | None = None, algo: str | None = None,
                               values: list | None = None, cache_solve: bool = False) -> dict:
        """POST /grasshopper — solve a Grasshopper definition (official Schema)."""
        if not pointer and not algo:
            raise ValueError("solve_definition requires either 'pointer' or 'algo'")
        payload: dict = {"values": values or [], "cachesolve": cache_solve,
                         "modelunits": self._model_units}
        if pointer:
            payload["pointer"] = pointer
        if algo:
            payload["algo"] = algo
        return await self._request_json("POST", GRASSHOPPER_PATH, payload)
