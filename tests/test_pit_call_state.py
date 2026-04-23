"""Tests for the pit-call state machine (strategy hardening sprint)."""
from __future__ import annotations

from lap_coach_logger.core.pit_call_state import (
    PitCallState,
    STATE_BOX_THIS_LAP,
    STATE_IN_PIT_SEQUENCE,
    STATE_ON_PLAN,
    STATE_PIT_IN_1,
    STATE_PIT_IN_2,
    STATE_PIT_IN_3,
    STATE_PIT_IN_4,
    STATE_PIT_IN_5,
    STATE_STOP_COMPLETED,
    advance_pit_call_state,
)
from lap_coach_logger.core.strategy_config import DEFAULT_STRATEGY, StrategyConfig


# ---------------------------------------------------------------------------
# StrategyConfig sanity
# ---------------------------------------------------------------------------

class TestStrategyConfig:
    def test_default_is_immutable(self):
        # dataclass(frozen=True) — any setattr must raise
        try:
            DEFAULT_STRATEGY.pit_window_laps = 99   # type: ignore[misc]
        except Exception:
            pass
        else:
            raise AssertionError("StrategyConfig should be frozen")

    def test_custom_config_preserves_defaults(self):
        custom = StrategyConfig(critical_alert_repeat_s=10.0)
        assert custom.critical_alert_repeat_s == 10.0
        assert custom.pit_window_laps == DEFAULT_STRATEGY.pit_window_laps


# ---------------------------------------------------------------------------
# Pit-call state machine
# ---------------------------------------------------------------------------

class TestPitCallStateMachine:
    def test_starts_on_plan(self):
        assert PitCallState().state == STATE_ON_PLAN

    def test_laps_to_pit_maps_to_correct_state(self):
        prev = PitCallState()
        for laps, expected in [(5, STATE_PIT_IN_5), (4, STATE_PIT_IN_4),
                                (3, STATE_PIT_IN_3), (2, STATE_PIT_IN_2),
                                (1, STATE_PIT_IN_1)]:
            state = advance_pit_call_state(
                prev, laps_to_pit=laps, is_in_pits=False, was_in_pits=False,
            )
            assert state.state == expected, f"{laps} laps → {expected}"
            prev = state  # advance chain

    def test_forward_progression_lap_by_lap(self):
        prev = PitCallState()
        for laps in (5, 4, 3, 2, 1, 0):
            prev = advance_pit_call_state(
                prev, laps_to_pit=laps, is_in_pits=False, was_in_pits=False,
            )
        assert prev.state == STATE_BOX_THIS_LAP

    def test_never_bounces_backward(self):
        """Once at pit_in_2, a spurious pit_in_3 reading must be ignored."""
        prev = PitCallState()
        prev = advance_pit_call_state(prev, laps_to_pit=3, is_in_pits=False, was_in_pits=False)
        prev = advance_pit_call_state(prev, laps_to_pit=2, is_in_pits=False, was_in_pits=False)
        assert prev.state == STATE_PIT_IN_2

        # VM recomputes and reports 3 again (burn-rate wobble) — ignore
        bounced = advance_pit_call_state(
            prev, laps_to_pit=3, is_in_pits=False, was_in_pits=False,
        )
        assert bounced.state == STATE_PIT_IN_2

    def test_box_this_lap_requires_prior_pit_in_1(self):
        """box_this_lap shouldn't fire straight from on_plan — but it
        should fire cleanly at cold-start when laps_to_pit == 0."""
        fresh = advance_pit_call_state(
            PitCallState(), laps_to_pit=0, is_in_pits=False, was_in_pits=False,
        )
        # Cold start jump is allowed — the car could have just crossed
        # the start/finish with no prior tick.
        assert fresh.state == STATE_BOX_THIS_LAP

    def test_in_pit_sequence_when_on_pit_road(self):
        prev = advance_pit_call_state(
            PitCallState(), laps_to_pit=1, is_in_pits=False, was_in_pits=False,
        )
        in_pits = advance_pit_call_state(
            prev, laps_to_pit=-1, is_in_pits=True, was_in_pits=False,
        )
        assert in_pits.state == STATE_IN_PIT_SEQUENCE

    def test_pit_exit_latches_stop_completed_briefly(self):
        in_pits = PitCallState(state=STATE_IN_PIT_SEQUENCE, stint_high_water=11)
        exit_state = advance_pit_call_state(
            in_pits, laps_to_pit=-1, is_in_pits=False, was_in_pits=True,
        )
        assert exit_state.state == STATE_STOP_COMPLETED

        # Next tick — back to on_plan with fresh stint state
        next_tick = advance_pit_call_state(
            exit_state, laps_to_pit=-1, is_in_pits=False, was_in_pits=False,
        )
        assert next_tick.state == STATE_ON_PLAN
        # High-water is reset for the new stint
        assert next_tick.stint_high_water == 0

    def test_unknown_laps_to_pit_stays_on_plan(self):
        state = advance_pit_call_state(
            PitCallState(), laps_to_pit=-1, is_in_pits=False, was_in_pits=False,
        )
        assert state.state == STATE_ON_PLAN

    def test_laps_beyond_window_stays_on_plan(self):
        state = advance_pit_call_state(
            PitCallState(), laps_to_pit=20, is_in_pits=False, was_in_pits=False,
        )
        assert state.state == STATE_ON_PLAN
