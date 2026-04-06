"""Tests for the session state machine."""

from lap_coach_logger.core.session_state import SessionState, SessionStateMachine


def test_initial_state_is_idle() -> None:
    fsm = SessionStateMachine()
    assert fsm.state is SessionState.IDLE


def test_valid_transitions() -> None:
    fsm = SessionStateMachine()
    assert fsm.transition(SessionState.SIMULATOR_DETECTED, reason="sim detected") is True
    assert fsm.state is SessionState.SIMULATOR_DETECTED

    assert fsm.transition(SessionState.WAITING_FOR_VALID_SESSION, reason="adapter connected") is True
    assert fsm.state is SessionState.WAITING_FOR_VALID_SESSION

    assert fsm.transition(SessionState.ARMING, reason="valid session found") is True
    assert fsm.state is SessionState.ARMING

    assert fsm.transition(SessionState.RECORDING, reason="first valid sample") is True
    assert fsm.state is SessionState.RECORDING

    assert fsm.transition(SessionState.FINALIZING, reason="recording stopped") is True
    assert fsm.state is SessionState.FINALIZING

    assert fsm.transition(SessionState.READY_FOR_REVIEW, reason="finalize succeeded") is True
    assert fsm.state is SessionState.READY_FOR_REVIEW

    assert fsm.transition(SessionState.IDLE, reason="review complete") is True
    assert fsm.state is SessionState.IDLE


def test_invalid_transition_rejected() -> None:
    fsm = SessionStateMachine()
    # IDLE → RECORDING is not allowed.
    assert fsm.transition(SessionState.RECORDING, reason="invalid") is False
    assert fsm.state is SessionState.IDLE


def test_failed_transitions() -> None:
    fsm = SessionStateMachine()
    fsm.transition(SessionState.SIMULATOR_DETECTED, reason="sim")
    fsm.transition(SessionState.WAITING_FOR_VALID_SESSION, reason="connected")
    fsm.transition(SessionState.ARMING, reason="session found")
    assert fsm.transition(SessionState.FAILED, reason="no telemetry") is True
    assert fsm.state is SessionState.FAILED
    assert fsm.transition(SessionState.FINALIZING, reason="best effort finalize") is True


def test_reset_returns_to_idle() -> None:
    fsm = SessionStateMachine()
    fsm.transition(SessionState.SIMULATOR_DETECTED, reason="sim")
    fsm.transition(SessionState.WAITING_FOR_VALID_SESSION, reason="connected")
    fsm.transition(SessionState.ARMING, reason="session found")
    fsm.transition(SessionState.RECORDING, reason="sample")
    fsm.reset()
    assert fsm.state is SessionState.IDLE
    assert fsm.transition_history == []


def test_on_enter_callback() -> None:
    fsm = SessionStateMachine()
    calls: list[tuple] = []
    fsm.on_enter(SessionState.SIMULATOR_DETECTED, lambda prev, cur: calls.append((prev, cur)))
    fsm.transition(SessionState.SIMULATOR_DETECTED, reason="sim detected")
    assert len(calls) == 1
    assert calls[0] == (SessionState.IDLE, SessionState.SIMULATOR_DETECTED)


def test_transition_history_records_reason_and_event() -> None:
    fsm = SessionStateMachine()
    assert fsm.transition(SessionState.SIMULATOR_DETECTED, reason="sim detected", event="sim_detected")
    hist = fsm.transition_history
    assert len(hist) == 1
    assert hist[0].previous_state == "idle"
    assert hist[0].new_state == "simulator_detected"
    assert hist[0].reason == "sim detected"
    assert hist[0].event == "sim_detected"
