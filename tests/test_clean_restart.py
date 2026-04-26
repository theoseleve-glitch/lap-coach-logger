"""T236: Ctrl+Shift+R — restart with clean config for testing.

Splits the feature into a pure helper + a drift-prevention
test on AppShell.qml:

  - ``prepare_clean_restart(config_path)`` renames the existing
    config file aside (with a timestamped suffix so multiple
    invocations don't collide) and returns the backup path.
    No-op when the config doesn't exist.
  - AppShell.qml declares a ``Shortcut { sequence: "Ctrl+Shift+R" }``
    so the keystroke fires the helper.

The actual restart mechanism (spawn child process, exit current)
crosses the Qt boundary and is deliberate follow-up — T236
guarantees the testable preparation step is correct and the
keybinding is wired.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from lap_coach_logger.diagnostics import clean_restart as cr


_REPO_ROOT = Path(__file__).resolve().parents[1]
_APPSHELL = _REPO_ROOT / "src" / "lap_coach_logger" / "qml" / "AppShell.qml"


# ---------------------------------------------------------------------------
# prepare_clean_restart: rename config aside
# ---------------------------------------------------------------------------


def test_prepare_clean_restart_renames_existing_config(tmp_path: Path) -> None:
    """The existing config.json must move out of the way so
    the next launch falls through to the "no config → write
    defaults" path in ConfigManager.load()."""
    cfg = tmp_path / "config.json"
    cfg.write_text('{"output_dir": "/tmp/x"}', encoding="utf-8")

    backup = cr.prepare_clean_restart(cfg)

    assert backup is not None
    assert not cfg.exists(), "original config.json should be moved out of the way"
    assert backup.exists(), "backup file should exist"


def test_prepare_clean_restart_backup_contents_match_original(tmp_path: Path) -> None:
    """Byte-for-byte preserved — ``--clean`` is a *testing*
    aid; users may want to restore their settings if the
    fresh-start launch reveals something was working before."""
    cfg = tmp_path / "config.json"
    payload = '{"output_dir": "/tmp/x", "driver_name": "Theo"}'
    cfg.write_text(payload, encoding="utf-8")

    backup = cr.prepare_clean_restart(cfg)

    assert backup is not None
    assert backup.read_text(encoding="utf-8") == payload


def test_prepare_clean_restart_filename_includes_timestamp(tmp_path: Path) -> None:
    """The backup filename must include a timestamp so
    repeated restarts don't collide — ``config.json.before-
    restart.bak`` would clobber the first backup with the
    second."""
    cfg = tmp_path / "config.json"
    cfg.write_text("{}", encoding="utf-8")

    backup = cr.prepare_clean_restart(cfg)

    assert backup is not None
    # Match a YYYY-MM-DDTHHMMSS pattern in the filename.
    assert re.search(r"\d{4}-\d{2}-\d{2}T\d{6}", backup.name), (
        f"backup filename {backup.name!r} lacks a timestamp"
    )


def test_prepare_clean_restart_returns_none_when_config_missing(tmp_path: Path) -> None:
    """First-run state: no config.json exists yet.
    ``prepare_clean_restart`` must NOT raise — there's
    nothing to clean. Returning None signals the no-op."""
    cfg = tmp_path / "config.json"
    assert not cfg.exists()

    result = cr.prepare_clean_restart(cfg)

    assert result is None


def test_prepare_clean_restart_does_not_overwrite_prior_backup(
    tmp_path: Path,
) -> None:
    """Two clean-restarts in quick succession (or on the
    same second) must not lose the older backup. The
    timestamp-suffix scheme is the primary defense; if a
    collision still happens, append a counter."""
    cfg = tmp_path / "config.json"

    cfg.write_text("first", encoding="utf-8")
    backup1 = cr.prepare_clean_restart(cfg)
    assert backup1 is not None
    assert backup1.read_text(encoding="utf-8") == "first"

    cfg.write_text("second", encoding="utf-8")
    backup2 = cr.prepare_clean_restart(cfg)
    assert backup2 is not None
    assert backup2.read_text(encoding="utf-8") == "second"

    # Both backups must still exist with their respective contents.
    assert backup1.exists()
    assert backup1.read_text(encoding="utf-8") == "first"
    assert backup1 != backup2


# ---------------------------------------------------------------------------
# AppShell.qml drift: Ctrl+Shift+R is wired
# ---------------------------------------------------------------------------


def test_appshell_declares_ctrl_shift_r_shortcut() -> None:
    """The keybinding must exist in AppShell.qml — without it
    the helper can't be invoked from a running app."""
    src = _APPSHELL.read_text(encoding="utf-8")
    pattern = r'sequence:\s*"Ctrl\+Shift\+R"'
    assert re.search(pattern, src), (
        "AppShell.qml is missing the Ctrl+Shift+R shortcut "
        "(restart-with-clean-config)"
    )
