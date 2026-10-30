import subprocess
import sys
from pathlib import Path
from fastapi.testclient import TestClient


def test_clean_process_has_no_legacy_imports_or_network():
    script = """
import sys, socket, builtins
from fastapi.testclient import TestClient
original_import = builtins.__import__
forbidden = ('sqlalchemy', 'psycopg', 'psycopg2', 'sqlite3', 'openai', 'anthropic', 'rhino3dm')
class BlockImports:
    def find_spec(self, fullname, *args):
        if fullname.startswith(forbidden) or fullname in ('app.main', 'app.database', 'app.models', 'app.rhino_engine'):
            raise AssertionError('Forbidden import: ' + fullname)
sys.meta_path.insert(0, BlockImports())
def denied(*args, **kwargs):
    raise AssertionError('Outbound connection attempted')
socket.socket.connect = denied
socket.socket.connect_ex = denied
socket.create_connection = denied
socket.getaddrinfo = denied
from app.mvp import create_app
with TestClient(create_app()) as client:
    assert client.get('/health').status_code == 200
assert 'app.main' not in sys.modules
print('ISOLATION_OK')
"""
    result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).parents[1],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert "ISOLATION_OK" in result.stdout


def test_public_routes_are_the_documented_surface():
    # Section 3 adds the /api/rhino/* surface (Section 1 deferred it).
    # Module 10 adds the /api/reconstruct/* surface. This asserts the exact
    # intended public surface so new routes cannot slip in.
    from app.mvp import create_app
    with TestClient(create_app()) as client:
        assert client.get("/docs").status_code == 200
        schema = client.get("/openapi.json").json()
        assert set(schema["paths"]) == {
            "/health",
            "/api/rhino/status",
            "/api/rhino/box",
            "/api/rhino/capabilities",
            "/api/vessel/validate",
            "/api/vessel/stations",
            "/api/vessel/hull",
            "/api/vessel/hull/3dm/{name}",
            "/api/reconstruct/capabilities",
            "/api/reconstruct/jobs",
            "/api/reconstruct/jobs/{job_id}",
            "/api/reconstruct/jobs/{job_id}/cancel",
            "/api/reconstruct/jobs/{job_id}/model",
            "/api/reconstruct/jobs/{job_id}/export",
            "/api/reconstruct/jobs/{job_id}/images/{idx}",
        }
        assert client.get("/api/rhino/nope").status_code == 404
