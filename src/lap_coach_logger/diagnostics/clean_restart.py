"""Clean-restart preparation (T236).

Helper that renames an existing config file aside so the next
launch falls through to the "no config → write defaults" path
in ``ConfigManager.load()``. Pure, side-effect-only-on-disk;
tests can pin behavior on a tmp_path.

The actual restart mechanism (spawn child process + exit
current) crosses the Qt boundary and is the QML shell's
responsibility.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

_log = logging.getLogger(__name__)


def _timestamp_suffix() -> str:
    """Filesystem-safe ``YYYY-MM-DDTHHMMSS`` (no colons, which
    NTFS forbids in filenames)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")


def prepare_clean_restart(config_path: Path) -> Path | None:
    """Rename ``config_path`` to a timestamped backup so the
    next launch sees no config.

    Returns the backup path on success, or ``None`` when there
    was no config to move (first-run state — already clean).

    If the candidate backup name collides (rapid successive
    invocations on the same second), appends a numeric counter
    so the older backup isn't clobbered.
    """
    if not config_path.exists():
        _log.info(
            "Clean restart: no config at %s, nothing to do", config_path
        )
        return None

    base = config_path.with_name(
        f"{config_path.name}.before-restart.{_timestamp_suffix()}.bak"
    )
    backup = base
    counter = 0
    while backup.exists():
        counter += 1
        backup = base.with_name(f"{base.name}.{counter}")

    config_path.rename(backup)
    _log.info(
        "Clean restart: moved %s aside to %s", config_path, backup
    )
    return backup


__all__ = ["prepare_clean_restart"]
