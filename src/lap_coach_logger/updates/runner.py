"""T187: bootstrap-side helper for spawning the update-check
thread, with the opt-out branch encapsulated so it's
unit-testable without standing up the whole app.

Two responsibilities:

1. **Opt-out gate.** ``start_update_check_thread(...,
   enabled=False)`` returns ``None`` and logs that the check
   is suppressed — no thread is spawned.

2. **Thread spawn.** When enabled, spawns a daemon thread
   that runs ``check_for_updates`` and logs the result.

Returning the ``Thread | None`` lets tests (and shutdown code,
if it ever needs to) inspect the lifecycle without
monkey-patching ``threading``.
"""
from __future__ import annotations

import logging
import threading
from typing import Callable

from lap_coach_logger.updates.checker import (
    UpdateCheckResult,
    check_for_updates,
)

_default_log = logging.getLogger(__name__)


CheckFn = Callable[[str], UpdateCheckResult]


def start_update_check_thread(
    current_version: str,
    *,
    enabled: bool,
    check_fn: CheckFn | None = None,
    log: logging.Logger | None = None,
) -> threading.Thread | None:
    """Run a best-effort update check in a daemon thread.

    Args:
        current_version: The running app's ``__version__``.
        enabled: ``False`` to honor the user's opt-out — no
            thread is spawned, an INFO log records the suppression.
        check_fn: Injectable update-check function (defaults to
            :func:`lap_coach_logger.updates.checker.check_for_updates`).
            Tests pass a fake to avoid real network calls.
        log: Optional logger override; defaults to this
            module's logger.

    Returns:
        The started ``Thread`` when ``enabled=True``; ``None``
        when the user has opted out.
    """
    logger = log if log is not None else _default_log

    if not enabled:
        logger.info(
            "Auto-update check disabled by user setting; skipping",
        )
        return None

    fn: CheckFn = check_fn if check_fn is not None else check_for_updates

    def _run() -> None:
        result = fn(current_version)
        if result.error:
            logger.info("Update check skipped: %s", result.error)
        elif result.has_update:
            logger.info(
                "Update available: v%s (currently v%s)",
                result.latest_version, result.current_version,
            )
        else:
            logger.info(
                "Update check: app is current (v%s)",
                result.current_version,
            )

    thread = threading.Thread(
        target=_run,
        daemon=True,
        name="update-check",
    )
    thread.start()
    return thread
