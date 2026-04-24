"""Formal session lifecycle state machine (sprint T017).

Backed by the ``transitions`` library so the allowed-state graph is
declarative and hooks are standardised. Public API preserved so every
caller (session_coordinator, tests) sees the same behaviour:

* ``state`` — current ``SessionState`` enum.
* ``entered_at`` — UTC datetime of the last state entry.
* ``transition_history`` — ordered list of ``TransitionEntry`` audit rows.
* ``on_enter(state, cb)`` — register callback ``cb(prev, new)`` for a state.
* ``transition(target, *, reason, event)`` — attempt a move; returns
  ``True`` on success, ``False`` on invalid (logs a warning, retains state).
* ``reset()`` — force back to ``IDLE`` and clear history.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from transitions import Machine

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


# Allowed (from → set-of-to) transitions.
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


def _trigger_name(target: SessionState) -> str:
    return f"go_to_{target.value}"


def _build_transitions_table() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for src, dsts in _TRANSITIONS.items():
        for dst in dsts:
            rows.append({
                "trigger": _trigger_name(dst),
                "source": src.value,
                "dest": dst.value,
            })
    return rows


class SessionStateMachine:
    """Session lifecycle FSM backed by ``transitions.Machine``."""

    def __init__(self) -> None:
        self._entered_at: datetime = datetime.now(timezone.utc)
        self._on_enter_cbs: dict[SessionState, list[Callable]] = {
            s: [] for s in SessionState
        }
        self._history: list[TransitionEntry] = []

        # Machine stores the string state on ``self._state_str`` so that
        # our public ``state`` property can return the ``SessionState``
        # enum without clashing with Machine's ``state`` attribute.
        self._machine = Machine(
            model=self,
            model_attribute="_state_str",
            states=[s.value for s in SessionState],
            transitions=_build_transitions_table(),
            initial=SessionState.IDLE.value,
            ignore_invalid_triggers=True,
            auto_transitions=False,
            send_event=False,
        )

    # -- properties --------------------------------------------------------

    @property
    def state(self) -> SessionState:
        return SessionState(self._state_str)

    @property
    def entered_at(self) -> datetime:
        return self._entered_at

    @property
    def transition_history(self) -> list[TransitionEntry]:
        return list(self._history)

    # -- registration ------------------------------------------------------

    def on_enter(self, state: SessionState, callback: Callable) -> None:
        """Register a callback to fire when *state* is entered."""
        self._on_enter_cbs[state].append(callback)

    # -- transitions -------------------------------------------------------

    def transition(
        self,
        target: SessionState,
        *,
        reason: str = "unspecified",
        event: str | None = None,
    ) -> bool:
        """Attempt to move to *target*. Returns True on success."""
        prev_state = self.state
        trigger = getattr(self, _trigger_name(target), None)
        if trigger is None:
            log.warning(
                "Unknown transition target %s (reason=%s, event=%s)",
                target.value,
                reason,
                event,
            )
            return False

        trigger()  # ignore_invalid_triggers=True → silent no-op on illegal
        if self.state is prev_state:
            log.warning(
                "Invalid transition %s → %s (reason=%s, event=%s)",
                prev_state.value,
                target.value,
                reason,
                event,
            )
            return False

        self._entered_at = datetime.now(timezone.utc)
        entry = TransitionEntry(
            timestamp_utc=self._entered_at.isoformat(),
            previous_state=prev_state.value,
            new_state=target.value,
            reason=reason,
            event=event,
        )
        self._history.append(entry)
        log.info(
            "Session state: %s → %s at %s (reason=%s, event=%s)",
            prev_state.value,
            target.value,
            entry.timestamp_utc,
            reason,
            event,
        )

        for cb in self._on_enter_cbs[target]:
            try:
                cb(prev_state, target)
            except Exception:
                log.exception("on_enter callback failed for %s", target.value)
        return True

    def reset(self) -> None:
        """Force back to IDLE (used after full cleanup)."""
        self._state_str = SessionState.IDLE.value
        self._entered_at = datetime.now(timezone.utc)
        self._history.clear()
