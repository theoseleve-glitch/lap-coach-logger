"""T151: ``OverlayViewModel.decisionPrompt`` — Qt-bindable
projection of :meth:`RaceStrategyService.compute_decision_prompt`.

Same wiring shape as T148's ``strategyGuidance``: VM owns the
QML-facing string state, service owns the logic. The VM
refreshes the prompt after each per-lap recalc and emits
``decisionPromptChanged`` only on transitions, so QML
doesn't rebind unnecessarily.

Wiring order matters — :meth:`recalculateLiveStrategy` must
update ``pitArmed`` *before* refreshing the prompt, since the
prompt reads ``service.armed`` to decide between PIT and
the other directives. Same constraint as
:meth:`_refresh_strategy_guidance`.
"""
from __future__ import annotations

from tests.qt_mock import install
install()

from lap_coach_logger.viewmodels.overlay_vm import OverlayViewModel  # noqa: E402


def test_decision_prompt_defaults_to_empty() -> None:
    """No baseline plan yet ⇒ no prompt. Widget renders
    nothing rather than a stale 'PUSH' while standing still."""
    vm = OverlayViewModel()

    assert vm.decisionPrompt == ""


def test_recalc_sets_prompt_to_push_when_healthy() -> None:
    """End-to-end through the VM: pre-race plan + healthy
    telemetry ⇒ PUSH directive surfaces."""
    vm = OverlayViewModel()
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)

    vm._lap_number = 20
    vm._fuel_level = 50.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()

    assert vm.decisionPrompt == "PUSH"


def test_recalc_sets_prompt_to_pit_when_armed() -> None:
    """When the recalc cycle arms the service (T140 threshold),
    the prompt flips to PIT — same trigger that drives
    pitArmed should drive the directive too."""
    vm = OverlayViewModel()
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)

    # Critical fuel — auto-arm fires
    vm._lap_number = 15
    vm._fuel_level = 2.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()

    assert vm.pitArmed is True  # auto-arm sanity check
    assert vm.decisionPrompt == "PIT"


def test_decision_prompt_changed_fires_on_transition() -> None:
    """QML rebinds on the change signal. Pin that the signal
    fires when the prompt flips."""
    vm = OverlayViewModel()
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)
    # Establish PUSH
    vm._lap_number = 20
    vm._fuel_level = 50.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()
    baseline = vm.decisionPromptChanged.call_count

    # Auto-arm transition: critical fuel
    vm._lap_number = 21
    vm._fuel_level = 1.0
    vm.recalculateLiveStrategy()

    assert vm.decisionPrompt == "PIT"
    assert vm.decisionPromptChanged.call_count > baseline


def test_decision_prompt_changed_does_not_fire_on_no_op_recalc() -> None:
    """Idempotency: same prompt across consecutive recalcs ⇒
    no signal. Avoids QML rebinds on every per-lap recalc when
    the directive is stable."""
    vm = OverlayViewModel()
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)
    vm._lap_number = 20
    vm._fuel_level = 50.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()
    baseline = vm.decisionPromptChanged.call_count

    # Identical prompt
    vm._lap_number = 21
    vm._fuel_level = 47.0
    vm.recalculateLiveStrategy()

    assert vm.decisionPrompt == "PUSH"
    assert vm.decisionPromptChanged.call_count == baseline
