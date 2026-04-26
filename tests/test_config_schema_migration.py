"""T222: Settings schema migration v1 → v2.

Pins the contract for explicit config schema versioning so future
breaking schema changes have a place to land:

  - Fresh ``AppConfig`` round-trips with ``schema_version: 2``
  - Loading a config that lacks ``schema_version`` (= v1) returns
    a working AppConfig and gets re-saved as v2 silently
  - Loading a config that already has ``schema_version: 2`` does
    NOT trigger a re-save (no churn)
  - The migration step is pure and idempotent — calling it on v2
    data returns identical data
  - Future schema_version values (3, 4...) don't crash; we
    interpret them as best-effort with a warning so an older
    binary launched on a newer config doesn't lose user state

The actual migration on the 1→2 boundary is a no-op apart from
stamping the version (the existing schema absorbed several
silent-upgrade fields via ``from_dict`` defaults). The point of
T222 is to put the framework in place so 2→3 has an explicit
home for breaking changes.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lap_coach_logger.config.manager import ConfigManager
from lap_coach_logger.config.migrations import (
    CURRENT_SCHEMA_VERSION,
    migrate_to_current,
)
from lap_coach_logger.config.models import AppConfig


# ---------------------------------------------------------------------------
# Schema version contract
# ---------------------------------------------------------------------------


def test_current_schema_version_is_two() -> None:
    """v2 is what this codebase ships. If we bump to v3 in the
    future, this test gets updated alongside the bump (and we
    add a v2→v3 step in migrations.py)."""
    assert CURRENT_SCHEMA_VERSION == 2


def test_app_config_to_dict_includes_schema_version() -> None:
    """A freshly-saved config must carry the version stamp so
    ConfigManager can detect the format on next load."""
    config = AppConfig()
    payload = config.to_dict()
    assert payload.get("schema_version") == CURRENT_SCHEMA_VERSION, (
        f"to_dict() omitted schema_version: {payload!r}"
    )


# ---------------------------------------------------------------------------
# migrate_to_current — pure function on dicts
# ---------------------------------------------------------------------------


def test_migrate_v1_dict_returns_v2_with_did_migrate_true() -> None:
    """A v1 config dict (no schema_version) must come out
    stamped v2 with the did_migrate flag set so callers know
    to write it back to disk."""
    v1 = {"output_dir": "/tmp/test", "debug": False}  # no schema_version
    migrated, did_migrate = migrate_to_current(v1)
    assert did_migrate is True
    assert migrated["schema_version"] == 2


def test_migrate_v1_dict_preserves_user_fields() -> None:
    """Migration must not drop user-set fields — stamping the
    version is additive, not destructive."""
    v1 = {
        "output_dir": "/data/sessions",
        "debug": True,
        "driver_name": "Theo",
    }
    migrated, _ = migrate_to_current(v1)
    assert migrated["output_dir"] == "/data/sessions"
    assert migrated["debug"] is True
    assert migrated["driver_name"] == "Theo"


def test_migrate_v2_dict_is_no_op() -> None:
    """If the config is already current, did_migrate=False and
    the data is unchanged. Caller skips the re-save."""
    v2 = {
        "schema_version": 2,
        "output_dir": "/tmp/test",
        "debug": False,
    }
    migrated, did_migrate = migrate_to_current(v2)
    assert did_migrate is False
    assert migrated == v2


def test_migrate_is_idempotent() -> None:
    """Calling migrate twice on the same data must give the
    same result the second time as the first — and the second
    call must NOT report did_migrate=True."""
    v1 = {"output_dir": "/tmp/x"}
    once, _ = migrate_to_current(v1)
    twice, did_migrate_again = migrate_to_current(once)
    assert twice == once
    assert did_migrate_again is False


def test_migrate_future_schema_does_not_crash() -> None:
    """An older binary launched on a newer config (schema 3+)
    must NOT crash — we interpret it best-effort. did_migrate
    is False (we can't actually upgrade newer→older); the
    data passes through unchanged."""
    future = {"schema_version": 99, "output_dir": "/tmp/future"}
    migrated, did_migrate = migrate_to_current(future)
    assert migrated == future  # passthrough
    assert did_migrate is False


# ---------------------------------------------------------------------------
# ConfigManager integration: load auto-migrates v1 files
# ---------------------------------------------------------------------------


def test_loading_v1_file_returns_working_app_config(tmp_path: Path) -> None:
    """A config.json from before T222 (no schema_version) must
    load without error and produce a usable AppConfig — silent
    upgrade on first launch after the migration ships."""
    cfg_path = tmp_path / "config.json"
    v1_payload = {
        "output_dir": str(tmp_path / "sessions"),
        "debug": False,
        "driver_name": "PreT222Driver",
    }
    cfg_path.write_text(json.dumps(v1_payload), encoding="utf-8")

    mgr = ConfigManager(path=cfg_path)
    cfg = mgr.load()

    assert isinstance(cfg, AppConfig)
    assert cfg.driver_name == "PreT222Driver"


def test_loading_v1_file_re_saves_as_v2(tmp_path: Path) -> None:
    """After loading a v1 config, the file on disk must be
    stamped v2 — otherwise users hit migration on every launch."""
    cfg_path = tmp_path / "config.json"
    v1_payload = {"output_dir": str(tmp_path / "sessions"), "debug": False}
    cfg_path.write_text(json.dumps(v1_payload), encoding="utf-8")

    mgr = ConfigManager(path=cfg_path)
    mgr.load()

    on_disk = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert on_disk.get("schema_version") == CURRENT_SCHEMA_VERSION


def test_loading_v2_file_does_not_rewrite(tmp_path: Path) -> None:
    """If the config is already current, ConfigManager.load()
    must NOT rewrite the file. Otherwise every launch bumps the
    file mtime and triggers any file-watcher integrations."""
    cfg_path = tmp_path / "config.json"
    payload = AppConfig().to_dict()
    cfg_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    original_mtime = cfg_path.stat().st_mtime_ns

    mgr = ConfigManager(path=cfg_path)
    mgr.load()

    new_mtime = cfg_path.stat().st_mtime_ns
    assert new_mtime == original_mtime, (
        "ConfigManager rewrote a v2 file unnecessarily — "
        "this churns mtime on every launch"
    )


def test_loading_missing_file_creates_v2_default(tmp_path: Path) -> None:
    """First-run path: no config.json → defaults written WITH
    schema_version stamp."""
    cfg_path = tmp_path / "config.json"
    assert not cfg_path.exists()

    mgr = ConfigManager(path=cfg_path)
    mgr.load()

    on_disk = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert on_disk.get("schema_version") == CURRENT_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# AppConfig.from_dict drops schema_version (it lives in the dict layer)
# ---------------------------------------------------------------------------


def test_from_dict_accepts_dict_with_schema_version() -> None:
    """AppConfig.from_dict must tolerate ``schema_version`` in the
    payload — it's a dict-level field, not an AppConfig dataclass
    field, so from_dict must strip it (already happens via the
    "filter unknown keys" pass) without raising."""
    payload = {
        "schema_version": 2,
        "output_dir": "/tmp/test",
        "debug": True,
    }
    config = AppConfig.from_dict(payload)
    assert isinstance(config, AppConfig)
    assert config.debug is True
