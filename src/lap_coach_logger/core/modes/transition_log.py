"""T119: Build a SessionEvent describing a mid-recording mode change.

Per T119 ("Mode switch during recording: allowed but logged,
mid-session tag split ⇒ handled"), the recording layer can't
just silently honour a mode switch — it has to drop a
``mode_changed`` lifecycle event into the bundle's events
stream so server-side cohort analysis can split pre- and
post-switch laps into the correct buckets.

This helper is a pure event builder: takes (from_mode,
to_mode) plus an injectable clock, returns a
:class:`~lap_coach_logger.writers.bundle_schema.SessionEvent`.
Wiring (subscribing to ``ModeEngine.on_mode_changed`` during
recording and pushing the event into the live events buffer)
lands at T120 — same shape as the T112-T114 binding adapters.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from lap_coach_logger.writers.bundle_schema import SessionEvent

log = logging.getLogger(__name__)


def build_mode_transition_event(
    from_mode: str,
    to_mode: str,
    *,
    now: datetime | None = None,
) -> SessionEvent:
    """Return a ``mode_changed`` :class:`SessionEvent` and log
    the transition at INFO level.

    :param now: Injectable clock. Defaults to
        ``datetime.now(timezone.utc)`` — production callers
        omit it; tests pin a deterministic value.
    """
    timestamp = (now or datetime.now(timezone.utc)).isoformat()
    log.info("mode transition: %s → %s", from_mode, to_mode)
    return SessionEvent(
        event="mode_changed",
        timestamp_utc=timestamp,
        detail={"from": from_mode, "to": to_mode},
    )


__all__ = ["build_mode_transition_event"]
