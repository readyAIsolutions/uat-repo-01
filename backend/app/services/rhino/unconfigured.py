"""Fail closed even if a future Rhino URL/key is supplied."""
from .contract import RhinoNotConfiguredError


class UnconfiguredRhinoAdapter:
    async def health_check(self):
        raise RhinoNotConfiguredError()

    async def create_box(self, width: float, length: float, height: float):
        raise RhinoNotConfiguredError()

    async def create_geometry(self, specification: dict):
        raise RhinoNotConfiguredError()

    async def execute_grasshopper(self, definition: str, inputs: dict):
        raise RhinoNotConfiguredError()
