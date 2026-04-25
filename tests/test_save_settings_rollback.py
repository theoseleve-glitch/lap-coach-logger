"""T174: Settings persistence — rollback if save fails.

The :meth:`DesktopService.save_settings` mutates ``self._config``
across ~30 fields *before* attempting the disk write. If the
write fails (permission denied, disk full, atomic rename
collision), the user sees an error toast via ``settings_failed``
but ``self._config`` is left holding the new values that never
reached disk — UI state and persisted state diverge until the
next successful save.

T174 fixes this by snapshotting ``self._config`` (deepcopy)
before mutation and restoring it inside the exception handler.
After rollback the in-memory state matches what's actually on
disk, so the next ``settings_snapshot()`` and any signal-driven
VM reload show the user's last-saved values.

Source-content pin (consistent with T156-T173 file-content
QML pins). DesktopService heavyweight enough that an
end-to-end fixture isn't worth the cost — the rollback pattern
is what matters and the pin enforces it.
"""
from __future__ import annotations

import re
from pathlib import Path

_SERVICE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "ui" / "desktop" / "service.py"
)


def _service_text() -> str:
    return _SERVICE_PATH.read_text(encoding="utf-8")


def _save_settings_body() -> str:
    """Slice the source from the ``def save_settings`` signature
    to the next top-level ``def`` so the regex tests don't drift
    onto unrelated methods."""
    text = _service_text()
    start = text.find("def save_settings(self")
    assert start >= 0, "DesktopService must define save_settings"
    # Find the next def at the same indentation (4-space class body)
    next_def = re.search(r'\n    def\s+\w+', text[start + 1 :])
    assert next_def is not None, "expected another method after save_settings"
    return text[start : start + 1 + next_def.start()]


def test_save_settings_imports_copy() -> None:
    """The rollback uses ``copy.deepcopy`` to snapshot config —
    so the module must import ``copy``."""
    text = _service_text()
    assert re.search(
        r'^\s*import\s+copy\b|^\s*from\s+copy\s+import\s+deepcopy\b',
        text,
        re.MULTILINE,
    ), (
        "service.py must import `copy` (deepcopy) for "
        "save_settings rollback snapshot"
    )


def test_save_settings_snapshots_config_before_mutation() -> None:
    """``save_settings`` calls ``copy.deepcopy(self._config)``
    (or ``deepcopy(self._config)``) at the top of the function,
    *before* any mutation. The snapshot is the rollback target
    when the disk write fails."""
    body = _save_settings_body()
    # Snapshot must appear before the first mutation (the line
    # `self._config.output_dir = ...`).
    snap_match = re.search(
        r'(copy\.deepcopy|deepcopy)\s*\(\s*self\._config\s*\)',
        body,
    )
    assert snap_match is not None, (
        "save_settings must take a deepcopy of self._config so "
        "rollback has a snapshot to restore"
    )
    mut_match = re.search(
        r'self\._config\.\w+\s*=', body,
    )
    assert mut_match is not None, "save_settings must mutate self._config"
    assert snap_match.start() < mut_match.start(), (
        "deepcopy snapshot must happen before any "
        "self._config mutation, otherwise the snapshot "
        "captures already-mutated state"
    )


def test_save_settings_restores_snapshot_in_except_block() -> None:
    """The ``except`` block must restore ``self._config`` from
    the snapshot before emitting ``settings_failed`` — so
    callers reading ``self._config`` after the failure see the
    last-saved state."""
    body = _save_settings_body()
    # Find the except block
    except_match = re.search(
        r'except\s+Exception\s+as\s+\w+:\s*\n([\s\S]+?)$',
        body,
    )
    assert except_match is not None, (
        "save_settings must have an `except Exception` block"
    )
    except_body = except_match.group(1)
    # Pin a restoration assignment back to self._config
    assert re.search(
        r'self\._config\s*=', except_body,
    ), (
        "except block must restore self._config from the "
        "deepcopy snapshot (e.g. `self._config = snapshot`)"
    )
    # And settings_failed.emit must still fire so the user sees the error
    assert re.search(
        r'settings_failed\.emit', except_body,
    ), (
        "except block must still call `settings_failed.emit` "
        "so the user sees the error"
    )
