"""Graceful shutdown coordination.

Provides a process-wide ``threading.Event`` plus helpers for signal
registration and ``atexit`` hooks.  Every long-running loop in the app
should check ``shutdown_requested()`` to exit cleanly.
"""

from __future__ import annotations

import atexit
import logging
import signal
import threading
from typing import Callable

log = logging.getLogger(__name__)

_shutdown_event = threading.Event()
_cleanup_callbacks: list[Callable[[], None]] = []


def shutdown_requested() -> bool:
    """Return True once a shutdown has been signalled."""
    return _shutdown_event.is_set()


def request_shutdown() -> None:
    """Signal all threads to stop."""
    _shutdown_event.set()


def wait_for_shutdown(timeout: float | None = None) -> bool:
    """Block until shutdown is requested.  Returns True if the event fired."""
    return _shutdown_event.wait(timeout=timeout)


def register_cleanup(fn: Callable[[], None]) -> None:
    """Register a callable to run during orderly shutdown."""
    _cleanup_callbacks.append(fn)


def run_cleanup() -> None:
    """Execute registered cleanup callbacks (best-effort, log errors)."""
    for fn in reversed(_cleanup_callbacks):
        try:
            fn()
        except Exception:
            log.exception("Cleanup callback %s failed", fn)


def install_signal_handlers() -> None:
    """Install SIGINT / SIGTERM (+ SIGBREAK on Windows) handlers.

    Signal handlers only set the event — no I/O, no locks.
    """
    def _handler(signum: int, _frame: object) -> None:  # noqa: ANN001
        _shutdown_event.set()

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)
    # Windows-specific: Ctrl+Break / service stop
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _handler)  # type: ignore[attr-defined]


def install_atexit() -> None:
    """Register ``run_cleanup`` with ``atexit`` as a last-resort hook."""
    atexit.register(run_cleanup)
