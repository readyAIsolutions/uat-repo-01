"""TEST ONLY: mock metadata, never real geometry or CAD files."""
class MockRhinoAdapter:
    async def health_check(self):
        return {"mock": True, "connected": False}

    async def create_box(self, width, length, height):
        return {"mock": True, "geometry": None, "cad_files": []}

    async def create_geometry(self, specification):
        return {"mock": True, "geometry": None, "cad_files": []}

    async def execute_grasshopper(self, definition, inputs):
        return {"mock": True, "geometry": None, "cad_files": []}
