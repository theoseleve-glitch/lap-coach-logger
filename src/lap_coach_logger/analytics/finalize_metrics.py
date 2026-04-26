"""Session-finalization success-rate metric (T225).

A crashed save means the user just lost their lap data — so
"how often does session finalization succeed?" is a critical
health signal we want to chart over time.

Module-level counters (mirroring the pattern in
``analytics.__init__``):

  - :func:`record_success` / :func:`record_failure` — bump
    counters when ``SessionFinalizer.finalize()`` returns a
    Path / None respectively.
  - :func:`success_rate` — successes / (successes + failures),
    or ``None`` when nothing has been recorded yet (avoids the
    misleading 0/0 → 0% reading on idle launches).
  - :func:`snapshot` — dict for shipping to PostHog or logging
    on shutdown. Stable key set so dashboard schemas don't
    silently drift.
  - :func:`reset` — zero both counters (test isolation +
    "Reset stats" entry point in Settings).

The metric is process-local (in-memory). Persisting across
restarts is deliberate follow-up scope; for the v1 health
check, we ship a summary at shutdown via ``snapshot``.
"""
from __future__ import annotations

_success_count: int = 0
_failure_count: int = 0


def record_success() -> None:
    """Bump the success counter. Call after every
    ``SessionFinalizer.finalize()`` that returned a Path."""
    global _success_count
    _success_count += 1


def record_failure() -> None:
    """Bump the failure counter. Call after every
    ``SessionFinalizer.finalize()`` that returned None."""
    global _failure_count
    _failure_count += 1


def success_rate() -> float | None:
    """Fraction in [0, 1] or ``None`` when no observations.

    Returning None for the empty case avoids the 0/0 → 0%
    misread on dashboards. Call sites that just want a number
    can ``or 0.0``."""
    total = _success_count + _failure_count
    if total == 0:
        return None
    return _success_count / total


def snapshot() -> dict:
    """Canonical PostHog payload + summary for shutdown logs.
    Keys are pinned by tests — renaming a key breaks
    dashboards."""
    return {
        "success_count": _success_count,
        "failure_count": _failure_count,
        "total": _success_count + _failure_count,
        "success_rate": success_rate(),
    }


def reset() -> None:
    """Zero both counters."""
    global _success_count, _failure_count
    _success_count = 0
    _failure_count = 0


__all__ = [
    "record_success",
    "record_failure",
    "success_rate",
    "snapshot",
    "reset",
]
