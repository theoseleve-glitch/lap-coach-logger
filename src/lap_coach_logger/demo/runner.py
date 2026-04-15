"""Demo playback runner - deterministic state machine."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from lap_coach_logger.demo.coaching_scenario import ScriptedMoment, moment_for_lap
from lap_coach_logger.demo.session_generator import (
    DemoSession,
    generate_session,
    iter_snapshots,
)


class DemoPhase(Enum):
    INTRO = "intro"
    COACHING = "coaching"     # laps 1-5 narrative
    SPRINT = "sprint"         # switch mode, show fuel + pit
    ENDURANCE = "endurance"   # show strategy + timeline
    DATA = "data"             # show channel inventory + export
    DONE = "done"


# Phase boundaries (by lap number). After the lap completes, advance phase.
_PHASE_BY_LAP: dict[int, DemoPhase] = {
    0: DemoPhase.INTRO,
    1: DemoPhase.COACHING,
    6: DemoPhase.SPRINT,
    8: DemoPhase.ENDURANCE,
    10: DemoPhase.DATA,
}


@dataclass
class DemoState:
    """Current state of the demo playback."""
    active: bool = False
    paused: bool = False
    current_lap: int = 0
    current_sample_in_lap: int = 0
    phase: DemoPhase = DemoPhase.INTRO
    last_moment: ScriptedMoment | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "paused": self.paused,
            "current_lap": self.current_lap,
            "current_sample_in_lap": self.current_sample_in_lap,
            "phase": self.phase.value,
            "last_moment_title": self.last_moment.title if self.last_moment else "",
            "last_moment_description": self.last_moment.description if self.last_moment else "",
        }


class DemoRunner:
    """Deterministic demo playback controller.

    Pulls snapshots from the synthetic session generator and feeds them
    into caller-provided sinks (e.g. strategy_vm.update_live). The runner
    controls pacing (lap-by-lap stepping, play/pause, reset).
    """

    def __init__(
        self,
        snapshot_sink: Callable[[dict[str, Any]], None],
        phase_sink: Callable[[DemoPhase], None] | None = None,
        moment_sink: Callable[[ScriptedMoment], None] | None = None,
    ) -> None:
        self._snapshot_sink = snapshot_sink
        self._phase_sink = phase_sink
        self._moment_sink = moment_sink
        self._session: DemoSession | None = None
        self._snapshots: list[dict[str, Any]] = []
        self._state = DemoState()

    # -- public API ---------------------------------------------------

    @property
    def state(self) -> DemoState:
        return self._state

    @property
    def session(self) -> DemoSession | None:
        return self._session

    def start(self) -> None:
        """Begin the demo. Builds the session and resets to lap 0."""
        self._session = generate_session()
        self._snapshots = list(iter_snapshots(self._session))
        self._state = DemoState(active=True, paused=False, current_lap=0)
        self._emit_phase(DemoPhase.INTRO)

    def pause(self) -> None:
        if self._state.active:
            self._state.paused = True

    def resume(self) -> None:
        if self._state.active:
            self._state.paused = False

    def stop(self) -> None:
        self._state = DemoState()
        self._session = None
        self._snapshots = []

    def reset(self) -> None:
        """Restart from lap 0. Preserves `active` flag."""
        was_active = self._state.active
        self.stop()
        if was_active:
            self.start()

    def step_lap(self) -> bool:
        """Advance one complete lap. Returns False if demo is finished."""
        if self._session is None or not self._state.active:
            return False
        if self._state.current_lap >= self._session.total_laps:
            self._state.phase = DemoPhase.DONE
            return False

        next_lap = self._state.current_lap + 1
        # Emit all snapshots for this lap
        samples_per_lap = self._session.samples_per_lap
        start_idx = self._state.current_lap * samples_per_lap
        end_idx = start_idx + samples_per_lap
        for snap in self._snapshots[start_idx:end_idx]:
            self._snapshot_sink(snap)

        self._state.current_lap = next_lap
        self._state.current_sample_in_lap = 0

        # Fire scripted moment if any
        moment = moment_for_lap(next_lap)
        if moment is not None:
            self._state.last_moment = moment
            if self._moment_sink:
                self._moment_sink(moment)

        # Advance phase if we crossed a boundary
        phase = _PHASE_BY_LAP.get(next_lap)
        if phase is not None and phase != self._state.phase:
            self._state.phase = phase
            self._emit_phase(phase)

        return True

    def step_sample(self) -> bool:
        """Advance one sample (sub-lap). Returns False if lap just completed."""
        if self._session is None or not self._state.active:
            return False
        if self._state.current_lap >= self._session.total_laps:
            return False

        samples_per_lap = self._session.samples_per_lap
        idx = self._state.current_lap * samples_per_lap + self._state.current_sample_in_lap
        if idx >= len(self._snapshots):
            return False

        self._snapshot_sink(self._snapshots[idx])
        self._state.current_sample_in_lap += 1
        if self._state.current_sample_in_lap >= samples_per_lap:
            # Lap completed - bump lap counter and fire scripted moment
            self._state.current_lap += 1
            self._state.current_sample_in_lap = 0
            moment = moment_for_lap(self._state.current_lap)
            if moment is not None:
                self._state.last_moment = moment
                if self._moment_sink:
                    self._moment_sink(moment)
            phase = _PHASE_BY_LAP.get(self._state.current_lap)
            if phase is not None and phase != self._state.phase:
                self._state.phase = phase
                self._emit_phase(phase)
            return False  # lap just closed
        return True

    def play_to_completion(self) -> None:
        """Run all laps sequentially. Used when play mode drives from a timer."""
        while self.step_lap():
            pass

    def jump_to_phase(self, phase: DemoPhase) -> None:
        """Skip directly to a phase - advance laps until we're there."""
        # Find the lap at which this phase begins
        target_lap = next(
            (lap for lap, p in sorted(_PHASE_BY_LAP.items()) if p == phase),
            None,
        )
        if target_lap is None:
            return
        while self._state.current_lap < target_lap:
            if not self.step_lap():
                break

    def _emit_phase(self, phase: DemoPhase) -> None:
        if self._phase_sink:
            self._phase_sink(phase)
