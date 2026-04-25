"""T175: Repeated saves don't corrupt config.json.

The :meth:`ConfigManager.save` uses an atomic write pattern —
write to a temp file in the same directory, then ``Path.replace()``
to swap into place. ``replace()`` is atomic on POSIX and on
Windows (NTFS) for files on the same volume, so a crash mid-write
leaves *either* the old file *or* the new file on disk — never a
partial / corrupt one.

T175 verifies that property holds across 100 rapid saves with
mutating values: each save must round-trip cleanly through load,
and the on-disk file must always be valid JSON whose top-level
shape matches AppConfig.

Touches real disk via ``tmp_path`` — no mocks. The atomic
behaviour is filesystem-level so mocking it would prove nothing.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lap_coach_logger.config.manager import ConfigManager
from lap_coach_logger.config.models import AppConfig


_REPEATED_SAVES = 100


@pytest.fixture
def cfg_manager(tmp_path: Path) -> ConfigManager:
    """ConfigManager pointing at a clean tmp config file."""
    return ConfigManager(path=tmp_path / "config.json")


def test_repeated_saves_do_not_corrupt_config_json(
    cfg_manager: ConfigManager,
) -> None:
    """100 saves with mutating driver_name should each round-trip
    cleanly through load. If atomic-rename ever regresses we'd
    expect the read-back to either fail JSON parse or return a
    stale value mid-burst."""
    cfg = AppConfig()

    for i in range(_REPEATED_SAVES):
        cfg.driver_name = f"driver_{i}"
        cfg_manager.save(cfg)

        # Re-read straight from disk — bypassing the manager's
        # `from_dict` fallback to defaults so a parse failure
        # surfaces as a json.JSONDecodeError, not a silent reset.
        raw = cfg_manager.path.read_text(encoding="utf-8")
        data = json.loads(raw)
        assert data["driver_name"] == f"driver_{i}", (
            f"iteration {i}: read-back driver_name "
            f"{data['driver_name']!r} != expected driver_{i!r}"
        )


def test_final_config_round_trips_after_repeated_saves(
    cfg_manager: ConfigManager,
) -> None:
    """After the burst the final state reads back via the
    manager's own load() path (which exercises from_dict's
    nested-dataclass reconstruction)."""
    cfg = AppConfig()
    for i in range(_REPEATED_SAVES):
        cfg.driver_name = f"driver_{i}"
        cfg_manager.save(cfg)

    loaded = cfg_manager.load()
    assert loaded.driver_name == f"driver_{_REPEATED_SAVES - 1}"


def test_no_temp_files_left_behind_after_repeated_saves(
    cfg_manager: ConfigManager,
) -> None:
    """Atomic-rename means each tempfile gets renamed into
    config.json. After 100 saves we expect exactly one file in
    the directory: config.json. Lingering ``cfg_*.tmp`` files
    would indicate the rename was failing silently."""
    cfg = AppConfig()
    for i in range(_REPEATED_SAVES):
        cfg.driver_name = f"driver_{i}"
        cfg_manager.save(cfg)

    files_in_dir = list(cfg_manager.path.parent.iterdir())
    tmp_files = [f for f in files_in_dir if f.suffix == ".tmp"]
    assert tmp_files == [], (
        f"Atomic-rename leaked {len(tmp_files)} tmp file(s): "
        f"{[f.name for f in tmp_files]}"
    )
    assert cfg_manager.path.exists(), "config.json must exist after saves"
