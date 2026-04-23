"""Strategy Runtime Consolidation — integration + invariant tests.

Locks in the invariants after the strategy runtime got consolidated
onto one deterministic path:

- StrategyConfig drives the pit window and fuel-deficit threshold
  (single source of truth — no duplicate magic numbers).
- PitCallState is the sole progression engine the overlay VM uses;
  pit_countdown and strategy_status severity both derive from it.
- Widget severities can never contradict each other.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.qt_mock import install

install()

from lap_coach_logger.core.pit_call_state import (  # noqa: E402
    PitCallState,
    STATE_BOX_THIS_LAP,
    STATE_IN_PIT_SEQUENCE,
    STATE_ON_PLAN,
    STATE_PIT_IN_1,
    STATE_PIT_IN_2,
    STATE_PIT_IN_3,
    STATE_PIT_IN_5,
    STATE_STOP_COMPLETED,
)
from lap_coach_logger.core.strategy_config import DEFAULT_STRATEGY  # noqa: E402
from lap_coach_logger.core.stint_store import StintStore  # noqa: E402
from lap_coach_logger.viewmodels.overlay_derived import (  # noqa: E402
    FUEL_SAVE_MARGIN_L,
    PitCountdownDisplay,
    build_pit_countdown_display,
    build_pit_countdown_from_state,
    build_strategy_status_from_state,
)
from lap_coach_logger.viewmodels.overlay_vm import OverlayViewModel  # noqa: E402
from lap_coach_logger.viewmodels.strategy_vm import StrategyViewModel  # noqa: E402


# ---------------------------------------------------------------------------
# PART 1 — StrategyConfig drives live thresholds
# ---------------------------------------------------------------------------

class TestStrategyConfigIsSourceOfTruth:
    def test_fuel_save_margin_comes_from_strategy_config(self):
        """Legacy FUEL_SAVE_MARGIN_L now sources from StrategyConfig."""
        assert FUEL_SAVE_MARGIN_L == DEFAULT_STRATEGY.fuel_deficit_margin_l

    def test_pit_window_default_comes_from_strategy_config(self):
        """build_pit_countdown_display honors DEFAULT_STRATEGY.pit_window_laps
        when called without an explicit window_laps."""
        # Just outside the default window → hidden
        far = build_pit_countdown_display(
            laps_to_pit=DEFAULT_STRATEGY.pit_window_laps + 1,
            pit_fuel_load=0.0,
            fuel_state="SAFE",
        )
        assert far.visible is False

        # At the boundary → visible
        at_edge = build_pit_countdown_display(
            laps_to_pit=DEFAULT_STRATEGY.pit_window_laps,
            pit_fuel_load=0.0,
            fuel_state="SAFE",
        )
        assert at_edge.visible is True


# ---------------------------------------------------------------------------
# PART 2 — PitCallState-driven countdown display
# ---------------------------------------------------------------------------

class TestPitCountdownFromState:
    def test_on_plan_hides_widget(self):
        display = build_pit_countdown_from_state(
            state=PitCallState(state=STATE_ON_PLAN),
            pit_fuel_load=0.0, fuel_state="SAFE",
        )
        assert display.visible is False

    def test_pit_in_2_renders_advisory_countdown(self):
        display = build_pit_countdown_from_state(
            state=PitCallState(state=STATE_PIT_IN_2),
            pit_fuel_load=40.0, fuel_state="SAFE",
        )
        assert display.visible is True
        assert display.headline == "PIT IN 2"
        assert display.severity == "advisory"

    def test_pit_in_1_renders_critical_next_lap(self):
        display = build_pit_countdown_from_state(
            state=PitCallState(state=STATE_PIT_IN_1),
            pit_fuel_load=40.0, fuel_state="SAFE",
        )
        assert display.headline == "PIT NEXT LAP"
        assert display.severity == "critical"

    def test_box_this_lap_renders_critical_box(self):
        display = build_pit_countdown_from_state(
            state=PitCallState(state=STATE_BOX_THIS_LAP),
            pit_fuel_load=40.0, fuel_state="SAFE",
        )
        assert display.headline == "BOX BOX BOX"
        assert display.severity == "critical"

    def test_deficit_fuel_escalates_advisory_to_critical(self):
        display = build_pit_countdown_from_state(
            state=PitCallState(state=STATE_PIT_IN_3),
            pit_fuel_load=0.0, fuel_state="DEFICIT",
        )
        assert display.severity == "critical"

    def test_in_pit_sequence_and_stop_completed_render_labels(self):
        in_pits = build_pit_countdown_from_state(
            state=PitCallState(state=STATE_IN_PIT_SEQUENCE),
            pit_fuel_load=0.0, fuel_state="SAFE",
        )
        assert in_pits.visible is True
        done = build_pit_countdown_from_state(
            state=PitCallState(state=STATE_STOP_COMPLETED),
            pit_fuel_load=0.0, fuel_state="SAFE",
        )
        assert done.visible is True


# ---------------------------------------------------------------------------
# PART 3 — Strategy-status severity derived from the same state
# ---------------------------------------------------------------------------

class TestStrategyStatusFromState:
    def test_on_plan_is_ok_severity(self):
        status = build_strategy_status_from_state(
            position=3, current_lap=5, total_laps=20,
            fuel_state="SAFE",
            pit_state=PitCallState(state=STATE_ON_PLAN),
        )
        assert status.severity == "ok"

    def test_pit_in_3_is_advisory(self):
        status = build_strategy_status_from_state(
            position=3, current_lap=17, total_laps=20,
            fuel_state="SAFE",
            pit_state=PitCallState(state=STATE_PIT_IN_3),
        )
        assert status.severity == "advisory"

    def test_pit_in_1_is_critical(self):
        status = build_strategy_status_from_state(
            position=3, current_lap=19, total_laps=20,
            fuel_state="SAFE",
            pit_state=PitCallState(state=STATE_PIT_IN_1),
        )
        assert status.severity == "critical"

    def test_fuel_deficit_wins_over_on_plan(self):
        status = build_strategy_status_from_state(
            position=3, current_lap=15, total_laps=20,
            fuel_state="DEFICIT",
            pit_state=PitCallState(state=STATE_ON_PLAN),
        )
        assert status.severity == "critical"

    def test_pit_in_5_is_ok_severity_preserves_legacy(self):
        """Old behaviour: pit_in_5/4 were severity=ok. Preserve it."""
        status_5 = build_strategy_status_from_state(
            position=3, current_lap=15, total_laps=20,
            fuel_state="SAFE",
            pit_state=PitCallState(state=STATE_PIT_IN_5),
        )
        assert status_5.severity == "ok"


# ---------------------------------------------------------------------------
# VM integration — state machine + widgets can't disagree
# ---------------------------------------------------------------------------

class _FakeStrategyVM:
    """Minimal stub so OverlayViewModel.lapsToPit can be driven from tests."""
    def __init__(self):
        self.lapsToPit = -1
        self.pitNow = False
        self.pitFuelLoad = 0.0
        self.fuelMargin = 5.0
        self.currentStintLap = 0
        self.currentStintTotalLaps = 0
        self.carClass = ""
        self.cornerFocus = ""
        self.techniqueInsight = ""
        self.techniqueAction = ""
        self.techniqueConfidence = "low"
        self.cornerInsights = []
        self.coachingMessage = {"is_empty": True, "supporting": {}}
        self.totalLaps = 20
        self.racePlan = []
        self.planFuelAtFinish = 0.0
        self.alerts = []
        self.currentMode = "sprint"

    def build_coaching_message(self, config=None):
        from lap_coach_logger.coaching.presentation import CoachingMessage
        return CoachingMessage()

    class _Sig:
        def connect(self, *a, **kw): pass
        def emit(self, *a, **kw): pass
    planChanged = _Sig()
    alertsChanged = _Sig()
    profilesChanged = _Sig()


class TestOverlayVMPitStateIntegration:
    def test_initial_state_is_on_plan(self):
        ovm = OverlayViewModel()
        assert ovm.pitCallState == STATE_ON_PLAN
        assert ovm.pitCountdownVisible is False

    def test_advance_through_full_pit_sequence(self):
        ovm = OverlayViewModel()
        stub = _FakeStrategyVM()
        ovm.set_strategy_vm(stub)

        snap = {
            "live": {"is_in_pits": False, "current_lap": 15, "session_time_s": 100.0},
            "sim": "iRacing",
            "status": "Recording",
            "total_laps": 20,
        }

        # Lap N-3: advisory
        stub.lapsToPit = 3
        ovm.update_from_snapshot(snap)
        assert ovm.pitCallState == STATE_PIT_IN_3
        assert ovm.pitCountdownHeadline == "PIT IN 3"
        assert ovm.pitCountdownSeverity == "advisory"

        # Lap N-1: critical (pit next lap)
        stub.lapsToPit = 1
        snap["live"]["session_time_s"] = 200.0
        ovm.update_from_snapshot(snap)
        assert ovm.pitCallState == STATE_PIT_IN_1
        assert ovm.pitCountdownSeverity == "critical"

        # BOX THIS LAP
        stub.lapsToPit = 0
        snap["live"]["session_time_s"] = 300.0
        ovm.update_from_snapshot(snap)
        assert ovm.pitCallState == STATE_BOX_THIS_LAP
        assert ovm.pitCountdownHeadline == "BOX BOX BOX"

        # In pits
        stub.lapsToPit = -1
        snap["live"]["is_in_pits"] = True
        snap["live"]["session_time_s"] = 400.0
        ovm.update_from_snapshot(snap)
        assert ovm.pitCallState == STATE_IN_PIT_SEQUENCE

        # Stop completed (one-tick latch)
        snap["live"]["is_in_pits"] = False
        snap["live"]["session_time_s"] = 500.0
        ovm.update_from_snapshot(snap)
        assert ovm.pitCallState == STATE_STOP_COMPLETED

    def test_anti_bounce_via_vm_path(self):
        """A spurious lapsToPit flip (3 → 2 → 3) in the VM must not
        make the pit state bounce backward."""
        ovm = OverlayViewModel()
        stub = _FakeStrategyVM()
        ovm.set_strategy_vm(stub)
        snap = {
            "live": {"is_in_pits": False, "session_time_s": 100.0},
            "sim": "iRacing",
            "status": "Recording",
        }

        stub.lapsToPit = 3
        ovm.update_from_snapshot(snap)
        stub.lapsToPit = 2
        snap["live"]["session_time_s"] = 200.0
        ovm.update_from_snapshot(snap)
        assert ovm.pitCallState == STATE_PIT_IN_2

        # VM recomputes 3 (burn-rate wobble) — state must stay at 2.
        stub.lapsToPit = 3
        snap["live"]["session_time_s"] = 300.0
        ovm.update_from_snapshot(snap)
        assert ovm.pitCallState == STATE_PIT_IN_2

    def test_widget_severities_never_contradict(self):
        """Pit countdown + strategy status both read from the same
        PitCallState, so their severities are guaranteed consistent."""
        ovm = OverlayViewModel()
        stub = _FakeStrategyVM()
        ovm.set_strategy_vm(stub)
        snap = {
            "live": {"is_in_pits": False, "session_time_s": 100.0},
            "sim": "iRacing",
            "status": "Recording",
        }

        stub.lapsToPit = 1
        ovm.update_from_snapshot(snap)
        # Countdown says critical
        assert ovm.pitCountdownSeverity == "critical"
        # Strategy status must agree
        assert ovm.strategyStatusSeverity == "critical"

    def test_unknown_laps_to_pit_keeps_widget_hidden(self):
        ovm = OverlayViewModel()
        stub = _FakeStrategyVM()
        ovm.set_strategy_vm(stub)
        snap = {
            "live": {"is_in_pits": False, "session_time_s": 0.0},
            "sim": "iRacing",
            "status": "Recording",
        }
        stub.lapsToPit = -1
        ovm.update_from_snapshot(snap)
        assert ovm.pitCountdownVisible is False
        assert ovm.pitCallState == STATE_ON_PLAN

    def test_set_strategy_vm_clears_stale_pit_state(self):
        """Session A leaves the VM with was_in_pits=True and an
        in-pit-sequence state; re-wiring set_strategy_vm for Session B
        must reset everything so the first tick of the new session
        doesn't fire a spurious STOP_COMPLETED latch."""
        ovm = OverlayViewModel()
        # Simulate end-of-session-A leakage
        ovm._was_in_pits_prev = True
        ovm._pit_call_state = PitCallState(state=STATE_IN_PIT_SEQUENCE, stint_high_water=11)

        stub = _FakeStrategyVM()
        ovm.set_strategy_vm(stub)
        assert ovm._was_in_pits_prev is False
        assert ovm.pitCallState == STATE_ON_PLAN

        # First snapshot of Session B with is_in_pits=False must NOT
        # latch STOP_COMPLETED (was_in_pits_prev was just cleared).
        snap = {
            "live": {"is_in_pits": False, "session_time_s": 0.0},
            "sim": "iRacing",
            "status": "Recording",
        }
        stub.lapsToPit = -1
        ovm.update_from_snapshot(snap)
        assert ovm.pitCallState == STATE_ON_PLAN

    def test_clear_smoke_scenario_resets_pit_state(self):
        ovm = OverlayViewModel()
        ovm._pit_call_state = PitCallState(state=STATE_PIT_IN_2, stint_high_water=8)
        ovm._was_in_pits_prev = True

        ovm.injectSmokeState("clear")
        assert ovm.pitCallState == STATE_ON_PLAN
        assert ovm._was_in_pits_prev is False

    def test_reset_pit_state_is_idempotent(self):
        """Calling reset on an already-on_plan VM should not emit or error."""
        ovm = OverlayViewModel()
        # Fresh VM is already at on_plan — reset should be a no-op
        ovm.reset_pit_state()
        assert ovm.pitCallState == STATE_ON_PLAN


# ---------------------------------------------------------------------------
# PART 4 — StrategyReview is the canonical verdict path
# ---------------------------------------------------------------------------

class TestStrategyReviewCanonical:
    def test_strategy_review_property_exists_on_strategy_vm(self, tmp_path: Path):
        store = StintStore(tmp_path / "stints.json")
        svm = StrategyViewModel(store=store)
        review = svm.strategyReview
        # Degraded when no plan, but the @Property exists and returns a dict
        assert isinstance(review, dict)
        assert "verdict" in review
        assert review["verdict"] == "no_plan"
        assert review["degraded"] is True

    def test_plan_vs_actual_docstring_points_at_strategy_review(self):
        """Regression: planVsActual must document that user-facing
        verdict text lives on strategyReview (no drift to old formatter).

        Read the module source directly — qt_mock's Property descriptor
        doesn't expose ``fget``.
        """
        import inspect
        from lap_coach_logger.viewmodels import strategy_vm
        src = inspect.getsource(strategy_vm)
        # The docstring must reference strategyReview near planVsActual
        idx = src.find("def planVsActual")
        assert idx >= 0
        window = src[idx:idx + 500]
        assert "strategyReview" in window
