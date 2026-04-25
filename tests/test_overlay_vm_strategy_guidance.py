"""T148: ``OverlayViewModel.strategyGuidance`` — Qt-bindable
projection of :meth:`RaceStrategyService.compute_guidance`.

Same wiring shape as T141's ``pitArmed``: VM owns the QML
state, service owns the logic. The VM refreshes the guidance
string after each per-lap recalc and emits
``strategyGuidanceChanged`` only on transitions so QML
doesn't rebind unnecessarily.
"""
from __future__ import annotations

from tests.qt_mock import install
install()

from lap_coach_logger.viewmodels.overlay_vm import OverlayViewModel  # noqa: E402


def test_strategy_guidance_defaults_to_empty() -> None:
    """No baseline plan yet → no guidance. The widget renders
    nothing rather than a stale or default 'PUSH'."""
    vm = OverlayViewModel()

    assert vm.strategyGuidance == ""


def test_recalc_sets_guidance_to_push_when_fuel_and_tires_healthy() -> None:
    """Same scenario as the service-level test but routed
    through the VM's recalc path — proves the wiring lands."""
    vm = OverlayViewModel()
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)

    vm._lap_number = 20
    vm._fuel_level = 50.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()

    assert vm.strategyGuidance == "PUSH"


def test_recalc_sets_guidance_to_manage_when_fuel_is_tight() -> None:
    """Tight fuel → MANAGE. End-to-end exercise of the service
    decision rule via the VM."""
    vm = OverlayViewModel()
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)

    vm._lap_number = 20
    vm._fuel_level = 91.0  # ~0.3 lap of buffer
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()

    assert vm.strategyGuidance == "MANAGE"


def test_strategy_guidance_changed_fires_on_transition() -> None:
    """QML rebinds on the change signal. Pin that the signal
    fires when the value flips so the overlay updates without
    polling."""
    vm = OverlayViewModel()
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)
    # Establish PUSH
    vm._lap_number = 20
    vm._fuel_level = 50.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()
    baseline = vm.strategyGuidanceChanged.call_count

    # Transition to MANAGE
    vm._lap_number = 21
    vm._fuel_level = 6.0  # critical
    vm.recalculateLiveStrategy()

    assert vm.strategyGuidance == "MANAGE"
    assert vm.strategyGuidanceChanged.call_count > baseline


def test_strategy_guidance_changed_does_not_fire_on_no_op_recalc() -> None:
    """Idempotency: same inputs → same guidance → no signal.
    Avoids QML rebinds on every per-lap recalc when nothing
    actually changes."""
    vm = OverlayViewModel()
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)
    vm._lap_number = 20
    vm._fuel_level = 50.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()
    baseline = vm.strategyGuidanceChanged.call_count

    # Identical recalc — guidance doesn't change
    vm._lap_number = 21
    vm._fuel_level = 47.0  # still healthy
    vm.recalculateLiveStrategy()

    assert vm.strategyGuidance == "PUSH"
    assert vm.strategyGuidanceChanged.call_count == baseline
