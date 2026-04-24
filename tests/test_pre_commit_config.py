"""Regression test: .pre-commit-config.yaml declares ruff + mypy + pytest (T014).

Acceptance: ``pre-commit install`` wires the hooks. This verifies the
configuration file exists, parses as valid YAML, and declares each of
the three hook families (ruff, mypy, pytest) so that the install step
actually registers something useful on any contributor's machine.
"""
from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / ".pre-commit-config.yaml"


def _load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _all_hook_ids(config: dict) -> set[str]:
    ids: set[str] = set()
    for repo in config.get("repos", []) or []:
        for hook in repo.get("hooks", []) or []:
            hid = hook.get("id")
            if hid:
                ids.add(hid)
    return ids


def test_config_file_exists() -> None:
    assert CONFIG_PATH.exists(), (
        ".pre-commit-config.yaml missing — T014 requires one at repo root"
    )


def test_config_is_valid_yaml_with_repos_list() -> None:
    data = _load_config()
    assert isinstance(data, dict)
    assert isinstance(data.get("repos"), list)
    assert data["repos"], "repos list is empty"


def test_config_declares_ruff_hook() -> None:
    assert "ruff" in _all_hook_ids(_load_config())


def test_config_declares_mypy_hook() -> None:
    assert "mypy" in _all_hook_ids(_load_config())


def test_config_declares_pytest_hook() -> None:
    ids = _all_hook_ids(_load_config())
    # Accept the conventional "pytest" id or a local "pytest-staged" variant.
    assert "pytest" in ids or "pytest-staged" in ids, (
        "no pytest hook declared in .pre-commit-config.yaml"
    )
