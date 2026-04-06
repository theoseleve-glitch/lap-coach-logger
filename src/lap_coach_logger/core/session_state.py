"""Formal session lifecycle state machine.

This FSM centralizes all allowed state transitions so the coordinator,
UI and tests all share one authoritative lifecycle model.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

log = logging.getLogger(__name__)


class SessionState(enum.Enum):
    IDLE = "idle"
    SIMULATOR_DETECTED = "simulator_detected"
    WAITING_FOR_VALID_SESSION = "waiting_for_valid_session"
    ARMING = "arming"
    RECORDING = "recording"
    FINALIZING = "finalizing"
    READY_FOR_REVIEW = "ready_for_review"
    FAILED = "failed"


@dataclass(frozen=True)
class TransitionEntry:
    """One state transition audit record."""
    timestamp_utc: str
    previous_state: str
    new_state: str
    reason: str
    event: str | None = None


# Allowed (from → set-of-to) transitions
_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.IDLE: {SessionState.SIMULATOR_DETECTED},
    SessionState.SIMULATOR_DETECTED: {
        SessionState.WAITING_FOR_VALID_SESSION,
        SessionState.IDLE,
        SessionState.FAILED,
    },
    SessionState.WAITING_FOR_VALID_SESSION: {
        SessionState.ARMING,
        SessionState.IDLE,
        SessionState.FAILED,
    },
    SessionState.ARMING: {
        SessionState.RECORDING,
        SessionState.FINALIZING,
        SessionState.IDLE,
        SessionState.FAILED,
    },
    SessionState.RECORDING: {SessionState.FINALIZING, SessionState.FAILED},
    SessionState.FINALIZING: {SessionState.READY_FOR_REVIEW, SessionState.FAILED},
    SessionState.READY_FOR_REVIEW: {
        SessionState.WAITING_FOR_VALID_SESSION,
        SessionState.IDLE,
    },
    SessionState.FAILED: {
        SessionState.FINALIZING,
        SessionState.READY_FOR_REVIEW,
        SessionState.IDLE,
    },
}


class SessionStateMachine:
    """Tiny FSM with timestamp tracking and callback hooks."""

    def __init__(self) -> None:
        self._state = SessionState.IDLE
        self._entered_at: datetime = datetime.now(timezone.utc)
        self._on_enter: dict[SessionState, list] = {s: [] for s in SessionState}
        self._history: list[TransitionEntry] = []

    # -- properties --------------------------------------------------------

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def entered_at(self) -> datetime:
        return self._entered_at

    @property
    def transition_history(self) -> list[TransitionEntry]:
        return list(self._history)

    # -- registration ------------------------------------------------------

    def on_enter(self, state: SessionState, callback: object) -> None:
        """Register a callback to fire when *state* is entered."""
        self._on_enter[state].append(callback)

    # -- transitions -------------------------------------------------------

    def transition(
        self,
        target: SessionState,
        *,
        reason: str = "unspecified",
        event: str | None = None,
    ) -> bool:
        """Attempt to move to *target*. Returns True on success."""
        if target not in _TRANSITIONS.get(self._state, set()):
            log.warning(
                "Invalid transition %s → %s (reason=%s, event=%s)",
                self._state.value,
                target.value,
                reason,
                event,
            )
            return False

        prev = self._state
        self._state = target
        self._entered_at = datetime.now(timezone.utc)
        entry = TransitionEntry(
            timestamp_utc=self._entered_at.isoformat(),
            previous_state=prev.value,
            new_state=target.value,
            reason=reason,
            event=event,
        )
        self._history.append(entry)
        log.info(
            "Session state: %s → %s at %s (reason=%s, event=%s)",
            prev.value,
            target.value,
            entry.timestamp_utc,
            reason,
            event,
        )

        for cb in self._on_enter[target]:
            try:
                cb(prev, target)
            except Exception:
                log.exception("on_enter callback failed for %s", target.value)
        return True

    def reset(self) -> None:
        """Force back to IDLE (used after full cleanup)."""
        self._state = SessionState.IDLE
        self._entered_at = datetime.now(timezone.utc)
        self._history.clear()
