"""T017 marker test: SessionStateMachine is backed by `transitions` lib.

The hand-rolled FSM is being migrated to the ``transitions`` Python
library so the allowed-graph is declarative and hooks are standardised.
This test locks that in: the machine instance must expose the
``transitions.Machine``-managed attribute the library installs.
"""
from __future__ import annotations

import pytest

from lap_coach_logger.core.session_state import SessionState, SessionStateMachine


def test_machine_uses_transitions_library_backend() -> None:
    fsm = SessionStateMachine()
    # transitions.Machine installs an attribute named ``machine`` on its
    # bound model by default. We expose it as ``_machine``; cover both
    # so later refactors can rename without breaking the test.
    machine = getattr(fsm, "_machine", None) or getattr(fsm, "machine", None)
    assert machine is not None, (
        "SessionStateMachine must wrap a transitions.Machine instance"
    )
    # Sanity: the Machine's state set covers every SessionState value.
    expected = {s.value for s in SessionState}
    actual = set(machine.states.keys())
    assert expected.issubset(actual), (
        f"transitions.Machine missing states: {expected - actual}"
    )


def test_machine_initial_is_idle() -> None:
    fsm = SessionStateMachine()
    # After migration, the library-backed FSM must still start at IDLE.
    assert fsm.state is SessionState.IDLE


@pytest.mark.parametrize(
    "start, target",
    [
        (SessionState.IDLE, SessionState.RECORDING),  # not allowed
        (SessionState.IDLE, SessionState.FINALIZING),  # not allowed
    ],
)
def test_invalid_transitions_return_false_without_raising(
    start: SessionState, target: SessionState
) -> None:
    fsm = SessionStateMachine()
    assert fsm.state is start
    # Library-backed FSM must preserve the hand-rolled contract:
    # invalid triggers return False rather than raising MachineError.
    assert fsm.transition(target, reason="invalid") is False
    assert fsm.state is start
