"""Interface only. No Rhino client or geometry implementation in Section 1."""
from typing import Any, Protocol, runtime_checkable


class RhinoNotConfiguredError(RuntimeError):
    code = "RHINO_NOT_CONFIGURED"

    def __init__(self):
        super().__init__("Rhino adapter unavailable in Section 1")


@runtime_checkable
class RhinoService(Protocol):
    async def health_check(self) -> dict[str, Any]: ...
    async def create_box(self, width: float, length: float, height: float) -> dict[str, Any]: ...
    async def create_geometry(self, specification: dict[str, Any]) -> dict[str, Any]: ...
    async def execute_grasshopper(self, definition: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]: ...
