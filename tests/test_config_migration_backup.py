"""T223: Config backup on schema migration.

When ConfigManager.load() detects an older schema (T222 v1→v2),
the original config.json must be backed up to disk BEFORE the
migrated form is written back. If migration ever has a bug, the
user's original settings are preserved and recoverable.

Contract:

  - On v1→v2 migration: write ``<name>.v1.bak`` next to the
    config file containing the EXACT original bytes
  - The backup is created BEFORE the new (migrated) file is
    written, so a crash mid-save can never lose data
  - If the backup target already exists (user already migrated
    once), don't overwrite it — leave the oldest backup in place
    so the original-original is preserved
  - No backup is created when the config is already current
    (v2) — would just be noise on every launch
  - No backup is created on first-run (no source file existed)
"""
from __future__ import annotations

import json
from pathlib import Path

from lap_coach_logger.config.manager import ConfigManager


def _write_v1(path: Path, payload: dict) -> bytes:
    """Write a v1-style config file (no schema_version) and
    return the exact bytes for later byte-for-byte comparison."""
    raw = json.dumps(payload).encode("utf-8")
    path.write_bytes(raw)
    return raw


# ---------------------------------------------------------------------------
# v1→v2 migration creates a backup
# ---------------------------------------------------------------------------


def test_v1_to_v2_migration_creates_backup_file(tmp_path: Path) -> None:
    """The backup must exist after load() returns. Naming
    convention: original ``<stem>.json`` -> backup
    ``<stem>.json.v1.bak`` (suffix-style so file managers keep
    them grouped)."""
    cfg_path = tmp_path / "config.json"
    _write_v1(cfg_path, {"output_dir": str(tmp_path / "sessions"), "debug": False})

    ConfigManager(path=cfg_path).load()

    backup = cfg_path.with_suffix(cfg_path.suffix + ".v1.bak")
    assert backup.exists(), (
        f"Expected backup at {backup} but it doesn't exist — "
        f"v1 user data is unrecoverable if migration introduced a bug"
    )


def test_backup_contains_exact_original_bytes(tmp_path: Path) -> None:
    """The backup must be byte-for-byte identical to the user's
    original file — not the parsed/re-emitted form. JSON round-
    trip would lose comment hints, formatting, key order, etc."""
    cfg_path = tmp_path / "config.json"
    original = _write_v1(
        cfg_path,
        {"output_dir": str(tmp_path / "x"), "driver_name": "Theo"},
    )

    ConfigManager(path=cfg_path).load()

    backup = cfg_path.with_suffix(cfg_path.suffix + ".v1.bak")
    assert backup.read_bytes() == original


def test_backup_written_before_new_file(tmp_path: Path) -> None:
    """If backup is written AFTER the new file, a crash between
    the two writes loses the original. Pin the order: backup
    mtime must be <= new file mtime.

    Note: filesystem timestamp granularity on Windows can be
    coarse (~100 ns NTFS, ~1 sec FAT), so the test allows
    equality (== considered valid for "before-or-same-instant").
    """
    cfg_path = tmp_path / "config.json"
    _write_v1(cfg_path, {"output_dir": str(tmp_path / "x")})

    ConfigManager(path=cfg_path).load()

    backup = cfg_path.with_suffix(cfg_path.suffix + ".v1.bak")
    backup_mtime = backup.stat().st_mtime_ns
    new_mtime = cfg_path.stat().st_mtime_ns
    assert backup_mtime <= new_mtime, (
        f"Backup mtime ({backup_mtime}) is after new file mtime "
        f"({new_mtime}) — backup must be written first"
    )


# ---------------------------------------------------------------------------
# Idempotence / safety
# ---------------------------------------------------------------------------


def test_existing_backup_is_not_overwritten(tmp_path: Path) -> None:
    """If a backup already exists (user previously migrated once
    on a prior install, then somehow got handed a v1 file again),
    don't overwrite it — the *first* backup is the most-original
    state and is the most valuable one to preserve."""
    cfg_path = tmp_path / "config.json"
    backup_path = cfg_path.with_suffix(cfg_path.suffix + ".v1.bak")

    # Simulate a pre-existing backup from an earlier migration.
    original_backup = b'{"output_dir": "/old/backup/from/last/time"}'
    backup_path.write_bytes(original_backup)

    # Now write a fresh v1 config and migrate.
    _write_v1(cfg_path, {"output_dir": str(tmp_path / "current")})
    ConfigManager(path=cfg_path).load()

    # The pre-existing backup must be untouched.
    assert backup_path.read_bytes() == original_backup, (
        "Migration overwrote a pre-existing backup — the "
        "oldest backup is the most-original state and should "
        "win the keep-conflict"
    )


def test_v2_config_load_creates_no_backup(tmp_path: Path) -> None:
    """A current-schema config doesn't migrate, so a backup is
    just noise. No backup file should appear."""
    cfg_path = tmp_path / "config.json"
    # Write a v2 config (using ConfigManager.save so it has the
    # current schema_version stamp).
    mgr = ConfigManager(path=cfg_path)
    from lap_coach_logger.config.models import AppConfig
    mgr.save(AppConfig())

    # Re-load (should be a no-op migration).
    mgr.load()

    backup = cfg_path.with_suffix(cfg_path.suffix + ".v1.bak")
    assert not backup.exists(), (
        f"Backup file {backup} appeared on a v2-config load — "
        f"only migrations should produce backups"
    )


def test_first_run_creates_no_backup(tmp_path: Path) -> None:
    """First launch (no config.json on disk) writes defaults but
    has nothing to back up. No backup file should appear."""
    cfg_path = tmp_path / "config.json"
    assert not cfg_path.exists()

    ConfigManager(path=cfg_path).load()

    backup = cfg_path.with_suffix(cfg_path.suffix + ".v1.bak")
    assert not backup.exists()
