"""T141: ``OverlayViewModel.pitArmed`` — Qt-bindable projection of
the strategy service's ``armed`` state.

T139 / T140 shipped the service-level computation. T141 surfaces
that to QML as a property the strategy widget can react to with
a colour change + indicator. The VM is the single owner of QML
state, so ``pitArmed`` lives on the VM rather than QML reaching
through to the service directly.

Wired in :meth:`OverlayViewModel.recalculateLiveStrategy` (which
already runs once per lap completion via the auto-recalc hook):
after the recalc returns, the VM calls
``service.update_armed_state(...)`` and mirrors the result onto
``_pit_armed``. ``pitArmedChanged`` fires on state transitions
so QML rebinds without polling.
"""
from __future__ import annotations

from tests.qt_mock import install
install()

from lap_coach_logger.viewmodels.overlay_vm import OverlayViewModel  # noqa: E402


# ---------------------------------------------------------------------------
# Default state + property exposure
# ---------------------------------------------------------------------------


def test_pit_armed_defaults_to_false() -> None:
    """A fresh VM has not been told to arm — caller must opt in
    via the recalc cycle (or T143's manual override). Mirrors
    the service-level default from T139."""
    vm = OverlayViewModel()

    assert vm.pitArmed is False


# ---------------------------------------------------------------------------
# Recalc updates pit_armed from the service's threshold logic
# ---------------------------------------------------------------------------


def test_recalculate_arms_when_fuel_window_critical() -> None:
    """The natural integration point: per-lap recalc runs the
    strategy update *and* the auto-arm computation. Pinning low-
    fuel telemetry should flip ``pitArmed`` without any extra
    method call from the caller."""
    vm = OverlayViewModel()
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)

    # Simulate telemetry: lap 15, near-empty tank
    vm._lap_number = 15
    vm._fuel_level = 2.0  # 2 L / 3 L/lap = 0.67 laps → arm
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()

    assert vm.pitArmed is True


def test_recalculate_disarms_when_state_returns_healthy() -> None:
    """The service-level disarm path (T140) reaches the VM too
    — a previously-armed state must be cleared once telemetry
    returns to a safe window. Covers the symmetry around the
    arm transition."""
    vm = OverlayViewModel()
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)

    vm._lap_number = 15
    vm._fuel_level = 2.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()
    assert vm.pitArmed is True  # established the armed state

    # Now telemetry shows we just refuelled — auto-disarm
    vm._lap_number = 16
    vm._fuel_level = 60.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()

    assert vm.pitArmed is False


# ---------------------------------------------------------------------------
# Signal emission on transitions
# ---------------------------------------------------------------------------


def test_pit_armed_changed_fires_on_transition_to_armed() -> None:
    """QML rebinds on the ``pitArmedChanged`` signal. A
    transition from disarmed → armed must emit it once so the
    overlay's pit indicator lights up reactively."""
    vm = OverlayViewModel()
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)
    before = vm.pitArmedChanged.call_count

    vm._lap_number = 15
    vm._fuel_level = 2.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()

    assert vm.pitArmed is True
    assert vm.pitArmedChanged.call_count > before


def test_pit_armed_changed_fires_on_transition_to_disarmed() -> None:
    """Symmetric path: armed → disarmed transition must also
    emit so the pit indicator clears reactively."""
    vm = OverlayViewModel()
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)
    # Establish armed
    vm._lap_number = 15
    vm._fuel_level = 2.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()
    assert vm.pitArmed is True
    armed_count = vm.pitArmedChanged.call_count

    # Healthy snapshot → disarm
    vm._lap_number = 16
    vm._fuel_level = 60.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()

    assert vm.pitArmed is False
    assert vm.pitArmedChanged.call_count > armed_count


def test_pit_armed_changed_does_not_fire_on_no_op_recalc() -> None:
    """Idempotency: if the recalc leaves the armed state
    unchanged, the signal must not fire — QML rebinds are
    expensive and a no-op shouldn't trigger them."""
    vm = OverlayViewModel()
    vm.calculatePreRaceStrategy(50, 65.0, 25.0, 30)
    # Establish a stable disarmed state with healthy telemetry
    vm._lap_number = 5
    vm._fuel_level = 50.0
    vm._fuel_per_lap = 3.0
    vm.recalculateLiveStrategy()
    baseline = vm.pitArmedChanged.call_count

    # Same telemetry → no transition
    vm._lap_number = 6
    vm._fuel_level = 47.0
    vm.recalculateLiveStrategy()

    assert vm.pitArmedChanged.call_count == baseline
