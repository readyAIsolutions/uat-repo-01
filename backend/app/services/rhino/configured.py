"""Configured Rhino adapter — REAL Rhino.Compute contract.

health_check() probes GET /healthcheck. execute_grasshopper() solves a definition
via POST /grasshopper (official Schema) and returns normalized outputs. Each call
is a SELF-CONTAINED solve (no cross-request geometry IDs).
"""
from __future__ import annotations

from .client import RhinoComputeClient
from .compute_schema import build_values, normalize_values
from .errors import RhinoCapabilityUnavailableError, RhinoRequestError, RhinoUnavailableError

DEFAULT_STATION_DEFINITION = "marlin_station_curves"
DEFAULT_HULL_DEFINITION = "marlin_hull"
DEFAULT_BOX_DEFINITION = "marlin_box"


class ConfiguredRhinoAdapter:
    def __init__(self, client: RhinoComputeClient,
                 station_definition: str = DEFAULT_STATION_DEFINITION,
                 hull_definition: str = DEFAULT_HULL_DEFINITION,
                 box_definition: str = DEFAULT_BOX_DEFINITION) -> None:
        self._client = client
        self.station_definition = station_definition
        self.hull_definition = hull_definition
        self.box_definition = box_definition

    async def health_check(self) -> dict:
        try:
            await self._client.health()
        except RhinoUnavailableError:
            return {"configured": True, "reachable": False, "status": "unreachable"}
        except RhinoRequestError as exc:
            return {"configured": True, "reachable": True, "status": "error",
                    "status_code": exc.status_code}
        return {"configured": True, "reachable": True, "status": "ok"}

    async def execute_grasshopper(self, definition: str, inputs: dict) -> dict:
        """Solve ``definition`` (server-side pointer) with ``inputs``; return outputs."""
        response = await self._client.solve_definition(pointer=definition, values=build_values(inputs))
        return normalize_values(response)

    async def create_box(self, width: float, length: float, height: float) -> dict:
        inputs = {"width": width, "length": length, "height": height}
        outputs = await self.execute_grasshopper(self.box_definition, inputs)
        return {"source": "rhino-compute", "definition": self.box_definition,
                "inputs": inputs, "result": outputs}

    async def create_geometry(self, specification: dict) -> dict:
        raise RhinoCapabilityUnavailableError("create_geometry")
