"""DemoViewModel -- wires DemoRunner to QML with timer-driven playback."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from lap_coach_logger.demo.coaching_scenario import ScriptedMoment
from lap_coach_logger.demo.runner import DemoPhase, DemoRunner
from lap_coach_logger.utils.qt_safe_slot import safe_slot


# Phase -> mode mapping. When the demo advances to a phase, the VM tells
# the ModeViewModel to switch modes for the matching walkthrough.
_PHASE_TO_MODE: dict[str, str] = {
    "intro": "coaching",
    "coaching": "coaching",
    "sprint": "sprint",
    "endurance": "endurance",
    "data": "data",
    "done": "coaching",
}


class DemoViewModel(QObject):
    """QML-facing wrapper around DemoRunner with timer-driven playback."""

    stateChanged = Signal()
    momentFired = Signal(str, str)   # title, description

    def __init__(
        self,
        runner: DemoRunner,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._runner = runner
        self._playing = False
        self._mode_vm: object | None = None  # set via set_mode_vm

        # Timer drives lap stepping during play mode
        self._timer = QTimer(self)
        try:
            self._timer.setInterval(2000)   # 2s per lap -- full demo ~20s
            self._timer.timeout.connect(self._tick)
        except Exception:
            # Under the test mock, QTimer is a MagicMock and setInterval/connect
            # are no-ops that tolerate anything. Guard against rare edge cases.
            pass

        # Wire runner's phase_sink / moment_sink to our handlers so the VM
        # reacts to phase changes and scripted coaching moments.
        runner._phase_sink = self._on_phase_changed  # type: ignore[attr-defined]
        runner._moment_sink = self._on_moment_fired  # type: ignore[attr-defined]

    # -- public wiring API -------------------------------------------------

    def set_mode_vm(self, mode_vm: object) -> None:
        """Attach a ModeViewModel so the demo can switch app modes."""
        self._mode_vm = mode_vm

    # -- QML properties ----------------------------------------------------

    @Property(bool, notify=stateChanged)
    def isActive(self) -> bool:  # noqa: N802
        return self._runner.state.active

    @Property(bool, notify=stateChanged)
    def isPlaying(self) -> bool:  # noqa: N802
        return self._playing

    @Property(bool, notify=stateChanged)
    def isPaused(self) -> bool:  # noqa: N802
        return self._runner.state.paused

    @Property(int, notify=stateChanged)
    def currentLap(self) -> int:  # noqa: N802
        return self._runner.state.current_lap

    @Property(int, notify=stateChanged)
    def totalLaps(self) -> int:  # noqa: N802
        return self._runner.session.total_laps if self._runner.session else 0

    @Property(str, notify=stateChanged)
    def phase(self) -> str:
        return self._runner.state.phase.value

    @Property(str, notify=stateChanged)
    def lastMomentTitle(self) -> str:  # noqa: N802
        m = self._runner.state.last_moment
        return m.title if m else ""

    @Property(str, notify=stateChanged)
    def lastMomentDescription(self) -> str:  # noqa: N802
        m = self._runner.state.last_moment
        return m.description if m else ""

    # -- QML slots ---------------------------------------------------------

    @safe_slot()
    @Slot()
    def start(self) -> None:
        """Begin the demo from lap 0."""
        self._runner.start()
        self._playing = False
        self.stateChanged.emit()

    @safe_slot()
    @Slot()
    def stop(self) -> None:
        """Stop the demo and clear state."""
        try:
            self._timer.stop()
        except Exception:
            pass
        self._playing = False
        self._runner.stop()
        self.stateChanged.emit()

    @safe_slot()
    @Slot()
    def play(self) -> None:
        """Resume timer-driven playback."""
        if not self._runner.state.active:
            self._runner.start()
        self._playing = True
        self._runner.resume()
        try:
            self._timer.start()
        except Exception:
            pass
        self.stateChanged.emit()

    @safe_slot()
    @Slot()
    def pause(self) -> None:
        try:
            self._timer.stop()
        except Exception:
            pass
        self._playing = False
        self._runner.pause()
        self.stateChanged.emit()

    @safe_slot()
    @Slot()
    def stepLap(self) -> None:  # noqa: N802
        if not self._runner.state.active:
            self._runner.start()
        self._runner.step_lap()
        self.stateChanged.emit()

    @safe_slot()
    @Slot()
    def reset(self) -> None:
        try:
            self._timer.stop()
        except Exception:
            pass
        self._playing = False
        self._runner.reset()
        self.stateChanged.emit()

    @safe_slot()
    @Slot(str)
    def jumpToPhase(self, phase_str: str) -> None:  # noqa: N802
        try:
            phase = DemoPhase(phase_str)
        except ValueError:
            return
        if not self._runner.state.active:
            self._runner.start()
        self._runner.jump_to_phase(phase)
        self.stateChanged.emit()

    # -- internals ---------------------------------------------------------

    def _tick(self) -> None:
        advanced = self._runner.step_lap()
        if not advanced:
            try:
                self._timer.stop()
            except Exception:
                pass
            self._playing = False
        self.stateChanged.emit()

    def _on_phase_changed(self, phase: DemoPhase) -> None:
        """Switch ModeViewModel when phase changes."""
        if self._mode_vm is None:
            return
        target_mode = _PHASE_TO_MODE.get(phase.value, "coaching")
        if hasattr(self._mode_vm, "setMode"):
            self._mode_vm.setMode(target_mode)

    def _on_moment_fired(self, moment: ScriptedMoment) -> None:
        self.momentFired.emit(moment.title, moment.description)
        self.stateChanged.emit()
