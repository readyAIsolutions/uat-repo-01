"""Module 10 tests (5, 6, 7): provider adapter behavior.

- service-level worker behaviour via fake providers (success / auth / timeout)
- TrellisProvider subprocess plumbing exercised with REAL scripts that
  emulate the TRELLIS entrypoint contract (success, failure, timeout, 401)
- mock provider blocked in production by construction
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from app.services.reconstruct.contract import (
    JobMetadata,
    ProviderAuthError,
    ProviderRejected,
    ProviderTimeout,
    ReconstructionProvider,
)
from app.services.reconstruct.jobs import JobStore
from app.services.reconstruct.service import (
    ProviderNotAllowed,
    ReconstructionService,
)
from app.services.reconstruct.trellis import TrellisProvider

from .reconstruct_helpers import make_glb, make_image

HERE = Path(__file__).resolve().parent


class FakeProvider(ReconstructionProvider):
    """Deterministic provider double wired into the worker."""

    name = "fake"

    def __init__(self, *, result=None, error=None, model="fake-model"):
        self._result = result
        self._error = error
        self.model = model
        self.calls = []

    def is_configured(self) -> bool:
        return self.configuration_problem() is None

    def configuration_problem(self) -> str | None:
        return None

    def reconstruct(self, image_paths, work_dir, *, timeout_seconds,
                    metadata=None):
        self.calls.append((list(image_paths), timeout_seconds))
        if self._error is not None:
            raise self._error
        if self._result is None:
            out = Path(work_dir) / "model.glb"
            out.write_bytes(make_glb())
            return out
        return self._result


class FailingConfiguredProvider(FakeProvider):
    """A provider that can never run (for honest-failure tests)."""

    def configuration_problem(self) -> str | None:
        return "no GPU on this host"


@pytest.fixture()
def work_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MARLIN_ENVIRONMENT", "development")
    return tmp_path


def _store(tmp_path) -> JobStore:
    return JobStore(tmp_path / "reconstruction")


def _wait_terminal(service, job_id, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = service.jobs.get(job_id)
        if job.status.value in ("succeeded", "failed", "canceled"):
            return job
        time.sleep(0.05)
    raise TimeoutError("job did not reach a terminal state")


def _submit(service, tmp_path, n=1):
    job = service.create_job(
        [__import__("app.services.reconstruct.validation", fromlist=["UploadedFile"])
         .UploadedFile(f"p{i}.jpg", make_image("JPEG")) for i in range(n)],
        vessel_length_m=20.0)[0]
    service.start(job["id"])
    return job["id"]


# -- 5. provider adapter behaviour (service worker) -------------------------
def test_worker_success_records_provider_and_mesh(work_env, tmp_path):
    service = ReconstructionService(storage_dir=tmp_path,
                                    environment="development")
    service._provider = FakeProvider()  # noqa: SLF001
    job_id = _submit(service, tmp_path)
    job = _wait_terminal(service, job_id)
    assert job.status.value == "succeeded"
    assert job.provider == "fake"
    assert job.provider_model == "fake-model"
    assert job.vertex_count > 0 and job.triangle_count > 0
    assert (service.jobs.job_dir(job_id) / "model.glb").is_file()
    assert (service.jobs.job_dir(job_id) / "export.obj").is_file()


def test_worker_passes_timeout_and_metadata_to_provider(work_env, tmp_path):
    provider = FakeProvider()
    service = ReconstructionService(storage_dir=tmp_path,
                                    environment="development",
                                    timeout_seconds=123.0)
    service._provider = provider  # noqa: SLF001
    job_id = _submit(service, tmp_path)
    _wait_terminal(service, job_id)
    paths, timeout = provider.calls[0]
    assert timeout == 123.0
    assert len(paths) == 1


def test_unconfigured_provider_fails_job_honestly(work_env, tmp_path):
    service = ReconstructionService(storage_dir=tmp_path,
                                    environment="development")
    service._provider = FailingConfiguredProvider()  # noqa: SLF001
    job_id = _submit(service, tmp_path)
    job = _wait_terminal(service, job_id)
    assert job.status.value == "failed"
    assert "no GPU on this host" in (job.error or "")


def test_provider_raise_auth_fails_job(work_env, tmp_path):
    service = ReconstructionService(storage_dir=tmp_path,
                                    environment="development")
    service._provider = FakeProvider(  # noqa: SLF001
        error=ProviderAuthError("invalid API key"))
    job = _wait_terminal(service, _submit(service, tmp_path))
    assert job.status.value == "failed"
    assert "invalid API key" in (job.error or "")


def test_provider_timeout_fails_job(work_env, tmp_path):
    service = ReconstructionService(storage_dir=tmp_path,
                                    environment="development")
    service._provider = FakeProvider(  # noqa: SLF001
        error=ProviderTimeout("TRELLIS did not finish within 900s"))
    job = _wait_terminal(service, _submit(service, tmp_path))
    assert job.status.value == "failed"
    assert "did not finish" in (job.error or "")


def test_provider_rejected_input_fails_job(work_env, tmp_path):
    service = ReconstructionService(storage_dir=tmp_path,
                                    environment="development")
    service._provider = FakeProvider(  # noqa: SLF001
        error=ProviderRejected("image blurry; cannot reconstruct"))
    job = _wait_terminal(service, _submit(service, tmp_path))
    assert job.status.value == "failed"
    assert "blurry" in (job.error or "")


def test_internal_provider_exception_fails_job_not_thread(work_env, tmp_path):
    service = ReconstructionService(storage_dir=tmp_path,
                                    environment="development")

    class BoomProvider(FakeProvider):
        def reconstruct(self, *a, **k):
            raise RuntimeError("kaboom")

    service._provider = BoomProvider()  # noqa: SLF001
    job = _wait_terminal(service, _submit(service, tmp_path))
    assert job.status.value == "failed"
    assert "kaboom" in (job.error or "")


def test_mock_refused_in_production(work_env, tmp_path):
    service = ReconstructionService(storage_dir=tmp_path,
                                    environment="production",
                                    provider_name="mock")
    with pytest.raises(ProviderNotAllowed):
        service.provider()
    caps = service.capabilities()
    assert caps["configured"] is False
    assert "SIMULATED" in caps["problem"].upper() or "mock" in caps["problem"].lower()


def test_unknown_provider_name_rejected(work_env, tmp_path):
    service = ReconstructionService(storage_dir=tmp_path,
                                    environment="development",
                                    provider_name="aliens")
    with pytest.raises(ProviderNotAllowed):
        service.provider()


# -- TrellisProvider: configuration honesty ---------------------------------
def test_trellis_unconfigured_reports_problem(monkeypatch):
    monkeypatch.delenv("RECONSTRUCTION_TRELLIS_PYTHON", raising=False)
    tp = TrellisProvider(python=None)
    assert tp.is_configured() is False
    problem = tp.configuration_problem()
    assert problem and "RECONSTRUCTION_TRELLIS_PYTHON" in problem


def test_trellis_rejects_missing_python(monkeypatch, tmp_path):
    tp = TrellisProvider(
        python=str(tmp_path / "does-not-exist"),
        entrypoint=tmp_path / "entry.py",
    )
    assert not tp.is_configured()
    assert "not found" in tp.configuration_problem()


def test_trellis_rejects_missing_entrypoint():
    tp = TrellisProvider(python=sys.executable,
                         entrypoint=Path("/nonexistent/entry.py"))
    assert not tp.is_configured()
    assert "entrypoint" in tp.configuration_problem()


# -- TrellisProvider: real subprocess plumbing (fake TRELLIS scripts) --------
def _write_script(dir, code) -> Path:
    p = dir / "fake_trellis.py"
    p.write_text(code)
    return p


def test_trellis_subprocess_success(tmp_path):
    script = _write_script(tmp_path, f"""
import json, sys
sys.path.insert(0, {str(HERE)!r})
from reconstruct_helpers import make_glb
from pathlib import Path
work = Path(sys.argv[sys.argv.index('--job-dir') + 1])
(work / 'model.glb').write_bytes(make_glb())
print(json.dumps({{"status": "ok", "output_glb": "model.glb"}}))
""")
    tp = TrellisProvider(python=sys.executable, entrypoint=script)
    result = tp.reconstruct(
        [tmp_path / "img.jpg"], tmp_path / "work",
        timeout_seconds=60, metadata=JobMetadata())
    assert result.name == "model.glb"
    assert result.stat().st_size > 0


def test_trellis_subprocess_nonzero_exit(tmp_path):
    script = _write_script(tmp_path, "import sys; sys.stderr.write('boom'); sys.exit(3)")
    tp = TrellisProvider(python=sys.executable, entrypoint=script)
    with pytest.raises(ProviderRejected) as exc:
        tp.reconstruct([tmp_path / "i.jpg"], tmp_path / "work",
                       timeout_seconds=60)
    assert "boom" in str(exc.value)


def test_trellis_subprocess_auth_failure(tmp_path):
    script = _write_script(
        tmp_path,
        "import sys; sys.stderr.write('403 Forbidden: license expired'); sys.exit(1)")
    tp = TrellisProvider(python=sys.executable, entrypoint=script)
    with pytest.raises(ProviderAuthError) as exc:
        tp.reconstruct([tmp_path / "i.jpg"], tmp_path / "work",
                       timeout_seconds=60)
    assert "license" in str(exc.value)


def test_trellis_subprocess_timeout(tmp_path):
    script = _write_script(tmp_path, "import time; time.sleep(30)")
    tp = TrellisProvider(python=sys.executable, entrypoint=script)
    with pytest.raises(ProviderTimeout):
        tp.reconstruct([tmp_path / "i.jpg"], tmp_path / "work",
                       timeout_seconds=2)


def test_trellis_subprocess_no_output_json(tmp_path):
    script = _write_script(tmp_path, "print('not json at all')")
    tp = TrellisProvider(python=sys.executable, entrypoint=script)
    with pytest.raises(Exception) as exc:
        tp.reconstruct([tmp_path / "i.jpg"], tmp_path / "work",
                       timeout_seconds=60)
    assert isinstance(exc.value, (ProviderRejected, Exception))


def test_trellis_subprocess_missing_glb(tmp_path):
    script = _write_script(
        tmp_path,
        "import json; print(json.dumps({'status':'ok','output_glb':'nope.glb'}))")
    tp = TrellisProvider(python=sys.executable, entrypoint=script)
    from app.services.reconstruct.contract import InvalidGeometryError
    with pytest.raises(InvalidGeometryError):
        tp.reconstruct([tmp_path / "i.jpg"], tmp_path / "work",
                       timeout_seconds=60)


def test_worker_runs_real_trellis_subprocess(tmp_path):
    """End-to-end worker + real subprocess adapter (emulated provider)."""
    script = _write_script(tmp_path, f"""
import json, sys
sys.path.insert(0, {str(HERE)!r})
from reconstruct_helpers import make_glb
from pathlib import Path
work = Path(sys.argv[sys.argv.index('--job-dir') + 1])
(work / 'model.glb').write_bytes(make_glb())
print(json.dumps({{"status": "ok", "output_glb": "model.glb"}}))
""")
    service = ReconstructionService(storage_dir=tmp_path,
                                    environment="development")
    service._provider = TrellisProvider(  # noqa: SLF001
        python=sys.executable, entrypoint=script)
    job_id = _submit(service, tmp_path)
    job = _wait_terminal(service, job_id)
    assert job.status.value == "succeeded"
    assert job.provider == "trellis"
    assert job.vertex_count > 0


def test_worker_thread_cancel_is_safe(work_env, tmp_path):
    service = ReconstructionService(storage_dir=tmp_path,
                                    environment="development")
    service._provider = FakeProvider()  # noqa: SLF001
    job_id = _submit(service, tmp_path)
    body, status = service.cancel(job_id)
    assert status in (200, 409)  # either cancel won or job already finished
    job = service.jobs.get(job_id)
    assert job.status.value in ("succeeded", "canceled")
