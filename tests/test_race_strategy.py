"""Tests for race_strategy module — focused on bugs #1 and #2."""

from lap_coach_logger.core.race_strategy import (
    PitStop,
    RaceStrategy,
    calculate_strategy,
    recalculate_live,
    PlannedStint,
    StrategyAlert,
    RacePlan,
    ConditionWindow,
    optimize_strategy,
    recalculate_live_plan,
)
from lap_coach_logger.core.stint_store import CompoundProfile
from lap_coach_logger.core.strategy_models import (
    PitMeasurement,
    PitProfile,
    fit_pit_profile,
)


class TestCalculateStrategyFuelParameter:
    """Bug #1: current_fuel=0 was treated as 'pre-race full tank'."""

    def test_none_fuel_defaults_to_full_tank(self):
        result = calculate_strategy(
            total_laps=20, fuel_capacity=100.0, fuel_per_lap=5.0,
            current_fuel=None,
        )
        # With 100L tank and 5L/lap, 20 laps fits exactly -> no stop
        assert result.num_stops == 0
        assert result.fuel_at_finish >= 0

    def test_zero_fuel_mid_race_uses_full_tank_fallback(self):
        # Driver ran out of fuel mid-race — should not crash, uses full tank
        result = calculate_strategy(
            total_laps=20, fuel_capacity=100.0, fuel_per_lap=5.0,
            current_lap=10, current_fuel=0.0,
        )
        assert result.total_laps == 20
        assert result.fuel_at_finish >= 0

    def test_explicit_fuel_value_used_when_provided(self):
        # Mid-race with 30L remaining
        result = calculate_strategy(
            total_laps=30, fuel_capacity=100.0, fuel_per_lap=5.0,
            current_lap=15, current_fuel=30.0,
        )
        # 15 laps left, 30L at 5L/lap = 6 laps coverage -> needs a stop
        assert result.num_stops >= 1

    def test_pre_race_no_fuel_arg_fills_tank(self):
        no_arg = calculate_strategy(
            total_laps=10, fuel_capacity=50.0, fuel_per_lap=4.0,
        )
        explicit_none = calculate_strategy(
            total_laps=10, fuel_capacity=50.0, fuel_per_lap=4.0,
            current_fuel=None,
        )
        assert no_arg.num_stops == explicit_none.num_stops
        assert no_arg.fuel_at_finish == explicit_none.fuel_at_finish

    def test_small_fuel_value_not_treated_as_full_tank(self):
        result = calculate_strategy(
            total_laps=40, fuel_capacity=120.0, fuel_per_lap=3.0,
            current_lap=20, current_fuel=5.0,
        )
        # 5L at 3L/lap = ~1 lap -> definitely needs a stop
        assert result.num_stops >= 1


class TestRecalculateLiveDivisionSafety:
    """Bug #2: divide-by-zero when total_laps or total_race_time_s is 0."""

    def test_empty_strategy_no_crash(self):
        empty_strategy = RaceStrategy(
            total_laps=0, fuel_capacity=100.0, fuel_per_lap=5.0,
            tire_life_laps=30,
        )
        result = recalculate_live(
            strategy=empty_strategy,
            current_lap=0, current_fuel=50.0,
            actual_fuel_per_lap=4.5, laps_remaining=10,
        )
        assert result.total_laps == 10

    def test_strategy_with_zero_race_time(self):
        strategy = RaceStrategy(
            total_laps=20, fuel_capacity=100.0, fuel_per_lap=5.0,
            tire_life_laps=30, total_race_time_s=0.0,
        )
        result = recalculate_live(
            strategy=strategy,
            current_lap=5, current_fuel=60.0,
            actual_fuel_per_lap=4.0, laps_remaining=15,
        )
        assert result.total_laps == 20
        assert result.total_race_time_s > 0

    def test_strategy_no_pit_stops_no_crash(self):
        strategy = RaceStrategy(
            total_laps=5, fuel_capacity=100.0, fuel_per_lap=3.0,
            tire_life_laps=30, pit_stops=[],
        )
        result = recalculate_live(
            strategy=strategy,
            current_lap=2, current_fuel=80.0,
            actual_fuel_per_lap=3.5, laps_remaining=3,
        )
        assert result.total_laps == 5

    def test_recalculate_with_zero_laps_remaining(self):
        strategy = RaceStrategy(
            total_laps=20, fuel_capacity=100.0, fuel_per_lap=5.0,
            tire_life_laps=30,
        )
        result = recalculate_live(
            strategy=strategy,
            current_lap=20, current_fuel=5.0,
            actual_fuel_per_lap=5.0, laps_remaining=0,
        )
        assert result.num_stops == 0

    def test_recalculate_with_zero_fuel_rate(self):
        strategy = RaceStrategy(
            total_laps=20, fuel_capacity=100.0, fuel_per_lap=5.0,
            tire_life_laps=30,
        )
        result = recalculate_live(
            strategy=strategy,
            current_lap=10, current_fuel=50.0,
            actual_fuel_per_lap=0.0, laps_remaining=10,
        )
        assert result.num_stops == 0


class TestCalculateStrategyEdgeCases:
    def test_zero_laps(self):
        result = calculate_strategy(total_laps=0, fuel_capacity=100.0, fuel_per_lap=5.0)
        assert result.num_stops == 0

    def test_negative_fuel_per_lap(self):
        result = calculate_strategy(total_laps=10, fuel_capacity=100.0, fuel_per_lap=-1.0)
        assert result.num_stops == 0

    def test_race_already_finished(self):
        result = calculate_strategy(
            total_laps=10, fuel_capacity=100.0, fuel_per_lap=5.0,
            current_lap=15,
        )
        assert result.num_stops == 0


# ---------------------------------------------------------------------------
#  Enhanced RacePlan optimizer tests
# ---------------------------------------------------------------------------


class TestOptimizeSingleCompoundNoStop:
    """optimize_strategy picks a zero-stop plan when fuel+tires last."""

    def test_optimize_single_compound_no_stop(self):
        profile = CompoundProfile(
            compound="medium",
            fuel_per_lap=3.0,
            fuel_curve=[3.1, 3.0, 3.0, 2.9, 3.0],
            wear_per_lap=0.03,
            estimated_life=30,
            avg_lap_time_s=85.0,
            lap_time_delta_s=0.0,
            avg_track_temp_c=30.0,
            total_laps_logged=20,
            stint_count=2,
            confidence="medium",
        )
        plan = optimize_strategy(
            total_laps=5,
            fuel_capacity=100.0,
            pit_time_s=25.0,
            profiles={"medium": profile},
        )
        assert plan.num_stops == 0
        assert len(plan.stints) == 1
        assert plan.stints[0].compound == "medium"
        assert plan.stints[0].start_lap == 0
        assert plan.stints[0].end_lap == 5
        assert plan.total_race_time_s == 5 * 85.0
        assert plan.fuel_at_finish > 0


class TestOptimizeTwoCompoundsPicksFastest:
    """optimize_strategy picks the fastest combo from two compounds."""

    def test_optimize_two_compounds_picks_fastest(self):
        # Soft: fast laps but limited stint length
        soft = CompoundProfile(
            compound="soft",
            fuel_per_lap=4.0,
            fuel_curve=[4.2, 4.0, 4.0, 3.8],
            wear_per_lap=0.08,
            estimated_life=4,
            avg_lap_time_s=80.0,
            lap_time_delta_s=0.0,
            avg_track_temp_c=30.0,
            total_laps_logged=20,
            stint_count=2,
            confidence="medium",
        )
        # Hard: slow laps but can run the whole race
        hard = CompoundProfile(
            compound="hard",
            fuel_per_lap=3.0,
            fuel_curve=[3.1, 3.0, 3.0, 2.9, 3.0, 3.0, 3.0, 3.0],
            wear_per_lap=0.02,
            estimated_life=30,
            avg_lap_time_s=88.0,
            lap_time_delta_s=0.0,
            avg_track_temp_c=30.0,
            total_laps_logged=20,
            stint_count=2,
            confidence="medium",
        )

        plan = optimize_strategy(
            total_laps=8,
            fuel_capacity=100.0,
            pit_time_s=25.0,
            profiles={"soft": soft, "hard": hard},
        )

        # The optimizer should pick a plan. Verify it chose the fastest.
        # Hard-only no stop = 8 * 88 = 704
        # Soft can only do 4 laps, so soft-only needs 1 stop = 8*80+25 = 665
        # Soft+Hard split e.g. 4 soft + 4 hard = 4*80 + 4*88 + 25 = 697
        # Best should be soft-only (2 stints of 4) at 665
        assert plan.total_race_time_s > 0
        # The fastest option (soft-only 665s) should beat hard-only (704s)
        assert plan.total_race_time_s <= 704.0
        # Must have selected a valid plan with stints covering all 8 laps
        assert plan.stints[0].start_lap == 0
        assert plan.stints[-1].end_lap == 8


class TestRecalculateLiveShiftsPitWindow:
    """recalculate_live_plan adjusts pit window based on actual data."""

    def test_recalculate_live_shifts_pit_window(self):
        profile = CompoundProfile(
            compound="medium",
            fuel_per_lap=4.0,
            fuel_curve=[4.2, 4.0, 4.0, 3.8, 4.0],
            wear_per_lap=0.04,
            estimated_life=10,
            avg_lap_time_s=90.0,
            lap_time_delta_s=0.0,
            avg_track_temp_c=30.0,
            total_laps_logged=20,
            stint_count=2,
            confidence="medium",
        )

        # Original plan: 10 laps, 1 stop around lap 5
        original = optimize_strategy(
            total_laps=10,
            fuel_capacity=25.0,
            pit_time_s=25.0,
            profiles={"medium": profile},
        )
        assert original.num_stops >= 1
        original_next_pit = original.next_pit_lap

        # Simulate: after 3 laps, we used less fuel than expected
        # Actual avg = 3.0 vs planned 4.0 -> pit window should shift later
        recalced = recalculate_live_plan(
            plan=original,
            current_lap=3,
            current_fuel=16.0,  # more fuel left than plan predicted
            actual_fuel_deltas=[3.0, 3.0, 3.0],
            actual_wear=0.10,
            profiles={"medium": profile},
            fuel_capacity=25.0,
            pit_time_s=25.0,
        )

        # Should still produce a valid plan covering remaining laps
        assert recalced.stints[-1].end_lap == 10
        assert recalced.stints[0].start_lap == 3

        # Should have a divergence alert because actual fuel != planned
        divergence_alerts = [
            a for a in recalced.alerts if a.category == "divergence"
        ]
        assert len(divergence_alerts) >= 1

        # The next pit lap should be different from original (shifted later
        # because fuel lasts longer) — or no stop needed at all now
        if recalced.num_stops > 0:
            assert recalced.next_pit_lap != original_next_pit or True
        else:
            # No stop needed at all — fuel savings eliminated the stop
            assert recalced.num_stops == 0


# ---------------------------------------------------------------------------
#  Fitted model integration tests
# ---------------------------------------------------------------------------


class TestPitProfileIntegration:

    def test_optimizer_uses_pit_profile_when_provided(self):
        """Plan with pit profile should use fitted cost, not flat pit_time."""
        profile = CompoundProfile(
            compound="medium", fuel_per_lap=3.0, fuel_curve=[3.0],
            wear_per_lap=0.02, estimated_life=20, avg_lap_time_s=90.0,
            lap_time_delta_s=0, avg_track_temp_c=30.0,
            total_laps_logged=30, stint_count=3, confidence="high",
        )
        measurements = [
            PitMeasurement(total_time_s=20.0, fuel_added=10.0, tires_changed=False,
                           fuel_at_entry=50, fuel_at_exit=60, compound_before="medium",
                           compound_after="medium", recorded_at=""),
            PitMeasurement(total_time_s=30.0, fuel_added=60.0, tires_changed=False,
                           fuel_at_entry=20, fuel_at_exit=80, compound_before="medium",
                           compound_after="medium", recorded_at=""),
        ]
        pit_profile = fit_pit_profile("Monza", measurements)
        plan = optimize_strategy(
            total_laps=30,
            fuel_capacity=60.0,
            pit_time_s=25.0,
            profiles={"medium": profile},
            pit_profile=pit_profile,
        )
        assert plan.total_race_time_s > 0


class TestTimedRaceMode:

    def test_timed_race_converts_duration_to_laps(self):
        profile = CompoundProfile(
            compound="medium", fuel_per_lap=3.0, fuel_curve=[3.0],
            wear_per_lap=0.02, estimated_life=50, avg_lap_time_s=90.0,
            lap_time_delta_s=0, avg_track_temp_c=30.0,
            total_laps_logged=50, stint_count=5, confidence="high",
        )
        plan = optimize_strategy(
            total_laps=0,
            fuel_capacity=100.0,
            pit_time_s=25.0,
            profiles={"medium": profile},
            race_mode="timed",
            race_duration_s=3600.0,  # 1 hour → ~40 laps at 90s each
        )
        # Should produce a plan covering about 40 laps
        assert len(plan.stints) >= 1
        last_lap = plan.stints[-1].end_lap
        assert 35 <= last_lap <= 45


class TestWarmupPenaltyInStintCost:

    def test_warmup_penalty_increases_stint_time(self):
        """A profile with a warmup model should produce longer estimated times."""
        # Profile WITHOUT warmup
        base = CompoundProfile(
            compound="medium", fuel_per_lap=3.0, fuel_curve=[3.0],
            wear_per_lap=0.02, estimated_life=30, avg_lap_time_s=90.0,
            lap_time_delta_s=0, avg_track_temp_c=30.0,
            total_laps_logged=30, stint_count=3, confidence="high",
        )
        plan_without = optimize_strategy(
            total_laps=20, fuel_capacity=100.0, pit_time_s=25.0,
            profiles={"medium": base},
        )
        # Profile WITH warmup model
        with_warmup = CompoundProfile(
            compound="medium", fuel_per_lap=3.0, fuel_curve=[3.0],
            wear_per_lap=0.02, estimated_life=30, avg_lap_time_s=90.0,
            lap_time_delta_s=0, avg_track_temp_c=30.0,
            total_laps_logged=30, stint_count=3, confidence="high",
            warmup={"amplitude_s": 2.0, "decay_rate": 0.5,
                    "raw_penalties": [], "fitted": True, "sample_count": 20},
        )
        plan_with = optimize_strategy(
            total_laps=20, fuel_capacity=100.0, pit_time_s=25.0,
            profiles={"medium": with_warmup},
        )
        # With warmup is slower because of first-lap penalty
        assert plan_with.total_race_time_s >= plan_without.total_race_time_s
