"""Regression test: pyproject pinned to Python 3.12 + deps locked (T013).

Acceptance: ``uv sync`` clean. This asserts the static contract
behind that:

1. ``pyproject.toml`` parses as valid TOML.
2. ``requires-python`` is pinned to the 3.12 line (``>=3.12,<3.13``).
3. Core runtime deps (PySide6, pyarrow, psutil) are declared.
4. ``uv.lock`` exists and targets Python 3.12.
5. Pytest config lives in pyproject so the tree has one config source
   (preventing the T004-style merge-conflict blocker).
"""
from __future__ import annotations

import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_pyproject() -> dict:
    return tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_pyproject_is_valid_toml() -> None:
    data = _load_pyproject()
    assert "project" in data


def test_requires_python_pinned_to_312_line() -> None:
    data = _load_pyproject()
    assert data["project"]["requires-python"] == ">=3.12,<3.13"


def test_core_dependencies_declared() -> None:
    data = _load_pyproject()
    deps = data["project"]["dependencies"]
    names = {d.split(">=")[0].split("==")[0].strip().lower() for d in deps}
    for required in {"pyside6", "pyarrow", "psutil"}:
        assert required in names, f"missing core dep: {required}"


def test_uv_lockfile_exists_and_targets_py312() -> None:
    lock = REPO_ROOT / "uv.lock"
    assert lock.exists(), "uv.lock missing — run `uv sync`"
    header = lock.read_text(encoding="utf-8")[:200]
    assert "3.12" in header, "uv.lock does not target Python 3.12"


def test_pytest_config_is_in_pyproject() -> None:
    data = _load_pyproject()
    pytest_cfg = data["tool"]["pytest"]["ini_options"]
    assert pytest_cfg["testpaths"] == ["tests"]
    assert pytest_cfg["pythonpath"] == ["src"]
