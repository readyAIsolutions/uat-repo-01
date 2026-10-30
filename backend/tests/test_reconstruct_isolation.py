"""Module 10 tests (11): independence from Raj's existing Rhino modules.

Three guarantees:
1. No Module 10 source file imports app.services.rhino / rhino3dm.
2. The branch's diff never touches the nine Rhino modules' files.
3. The full existing suite (nine modules) still passes (run separately as
   the regression gate; here we assert the file-level boundary).

NOTE: mvp.py gains purely additive wiring (a new router include + one state
field). That is the documented, minimal integration point.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MOD10_PATHS = [
    REPO / "backend/app/services/reconstruct",
    REPO / "backend/app/api/reconstruct.py",
    REPO / "backend/app/core/env.py",
    REPO / "reconstruction/trellis_entrypoint.py",
]


def _mod10_sources():
    files = []
    for root in MOD10_PATHS:
        if root.is_dir():
            files.extend(root.rglob("*.py"))
        elif root.is_file():
            files.append(root)
    return [f for f in files if "__pycache__" not in str(f)]


def _imported_modules(source: str) -> list[str]:
    """Names actually imported (AST-based; docstrings can't false-positive)."""
    import ast
    tree = ast.parse(source)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.append(node.module or "")
    return found


def test_module10_never_imports_rhino_services():
    hits = []
    for path in _mod10_sources():
        for module in _imported_modules(path.read_text()):
            if "rhino" in module.lower() or module.lower() == "rhino3dm":
                hits.append(f"{path.name}: imports '{module}'")
    assert not hits, "Module 10 leaked Rhino imports:\n" + "\n".join(hits)


def test_module10_imports_cleanly_without_rhino3dm():
    """The reconstruct package must import even if rhino3dm were absent."""
    import subprocess as sp
    code = (
        "import sys\n"
        "sys.path.insert(0, 'backend')\n"
        "class _Block:\n"
        "    def find_spec(self, fullname, path=None, target=None):\n"
        "        if fullname == 'rhino3dm' or fullname.startswith('rhino3dm.'):\n"
        "            raise ImportError('rhino3dm blocked by module-10 import test')\n"
        "        return None\n"
        "sys.meta_path.insert(0, _Block())\n"
        "import app.services.reconstruct.contract\n"
        "import app.services.reconstruct.jobs\n"
        "import app.services.reconstruct.validation\n"
        "import app.services.reconstruct.service\n"
        "import app.services.reconstruct.trellis\n"
        "import app.services.reconstruct.meshes\n"
        "import app.api.reconstruct\n"
        "print('MOD10 IMPORT OK')"
    )
    result = sp.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=REPO)
    assert result.returncode == 0, result.stderr
    assert "MOD10 IMPORT OK" in result.stdout


def test_rhino_module_files_untouched_by_branch():
    """Git diff (main..HEAD) must not alter the nine modules' source files."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "main...HEAD"],
        capture_output=True, text=True, cwd=REPO)
    assert result.returncode == 0, result.stderr
    changed = result.stdout.splitlines()
    forbidden_prefixes = (
        "backend/app/services/rhino/",
        "backend/app/services/vessel/",
        "backend/app/api/rhino.py",
        "backend/app/api/vessel.py",
        "backend/app/services/rhino.py",
    )
    violations = [
        f for f in changed if f.startswith(forbidden_prefixes)
    ]
    # mvp.py wiring is the one allowed additive integration point.
    violations = [f for f in violations if f != "backend/app/mvp.py"]
    assert not violations, "Branch modifies Raj's Rhino module files:\n" \
        + "\n".join(violations)


def test_reconstruct_sources_do_not_import_rhino_router():
    import ast
    for path in _mod10_sources():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if "rhino" in mod:
                    raise AssertionError(
                        f"{path.name} imports Rhino module '{mod}'")
