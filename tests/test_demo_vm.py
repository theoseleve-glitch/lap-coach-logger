"""Tests for DemoViewModel."""
from __future__ import annotations

from tests.qt_mock import install
install()

from lap_coach_logger.demo.runner import DemoRunner  # noqa: E402
from lap_coach_logger.viewmodels.demo_vm import DemoViewModel  # noqa: E402


class _SnapSink:
    def __init__(self):
        self.snaps = []

    def __call__(self, snap):
        self.snaps.append(snap)


def test_vm_initially_inactive():
    sink = _SnapSink()
    runner = DemoRunner(snapshot_sink=sink)
    vm = DemoViewModel(runner=runner)
    assert vm.isActive is False
    assert vm.isPlaying is False


def test_vm_start_activates_runner():
    sink = _SnapSink()
    runner = DemoRunner(snapshot_sink=sink)
    vm = DemoViewModel(runner=runner)
    vm.start()
    assert vm.isActive is True
    assert vm.totalLaps == 10


def test_vm_step_advances_lap():
    sink = _SnapSink()
    runner = DemoRunner(snapshot_sink=sink)
    vm = DemoViewModel(runner=runner)
    vm.start()
    vm.stepLap()
    assert vm.currentLap == 1
    assert len(sink.snaps) > 0


def test_vm_reset_returns_to_zero():
    sink = _SnapSink()
    runner = DemoRunner(snapshot_sink=sink)
    vm = DemoViewModel(runner=runner)
    vm.start()
    vm.stepLap()
    vm.stepLap()
    vm.reset()
    assert vm.currentLap == 0
    assert vm.isActive is True


def test_vm_stop_deactivates():
    sink = _SnapSink()
    runner = DemoRunner(snapshot_sink=sink)
    vm = DemoViewModel(runner=runner)
    vm.start()
    vm.stop()
    assert vm.isActive is False


def test_vm_jump_to_phase_advances_laps():
    sink = _SnapSink()
    runner = DemoRunner(snapshot_sink=sink)
    vm = DemoViewModel(runner=runner)
    vm.start()
    vm.jumpToPhase("endurance")
    assert vm.currentLap >= 8


def test_vm_mode_switch_fires_on_phase_change():
    class FakeModeVM:
        def __init__(self):
            self.last_mode = ""

        def setMode(self, mode):
            self.last_mode = mode

    sink = _SnapSink()
    runner = DemoRunner(snapshot_sink=sink)
    vm = DemoViewModel(runner=runner)
    mode_vm = FakeModeVM()
    vm.set_mode_vm(mode_vm)

    vm.start()
    # Step enough laps to cross into SPRINT phase (lap 6)
    for _ in range(6):
        vm.stepLap()
    assert mode_vm.last_mode == "sprint"


def test_vm_moment_title_populated_after_scripted_lap():
    sink = _SnapSink()
    runner = DemoRunner(snapshot_sink=sink)
    vm = DemoViewModel(runner=runner)
    vm.start()
    for _ in range(5):
        vm.stepLap()
    # After lap 5, plan_generated moment should have fired
    assert vm.lastMomentTitle != ""


def test_vm_invalid_phase_jump_is_noop():
    sink = _SnapSink()
    runner = DemoRunner(snapshot_sink=sink)
    vm = DemoViewModel(runner=runner)
    vm.start()
    vm.jumpToPhase("nonexistent")  # should not crash
    assert vm.currentLap == 0
