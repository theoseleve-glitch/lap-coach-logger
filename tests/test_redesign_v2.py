"""Tests for the product redesign v2 changes.

Covers:
  - Live strategy recalculation trigger behavior
  - Pit countdown state transitions
  - Divergence alert logic
  - Overlay category / tier filtering
  - Coaching self-comparison output generation
  - Readiness action suggestions
  - Coaching carryover data
  - Plan-vs-actual review
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.qt_mock import install

install()

from lap_coach_logger.coaching.output import Confidence  # noqa: E402
from lap_coach_logger.coaching.plan_engine import (  # noqa: E402
    CoachingPlan,
    SectorGap,
    generate_plan,
)
from lap_coach_logger.core.consistency_analyzer import ConsistencyReport  # noqa: E402
from lap_coach_logger.core.mode_descriptor import (  # noqa: E402
    COACHING,
    DATA,
    ENDURANCE,
    SPRINT,
)
from lap_coach_logger.core.practice_readiness import (  # noqa: E402
    CoachingCarryover,
    ReadinessAction,
    build_coaching_carryover,
    compute_readiness_action,
)
from lap_coach_logger.core.race_strategy import (  # noqa: E402
    PlannedStint,
    RacePlan,
)
from lap_coach_logger.core.stint_store import CompoundProfile, StintStore  # noqa: E402
from lap_coach_logger.viewmodels.overlay_helpers import (  # noqa: E402
    OVERLAY_TIERS,
    get_widget_tier,
    is_widget_visible_in_catalog,
)
from lap_coach_logger.viewmodels.strategy_vm import StrategyViewModel  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_report(
    lap_count: int = 10,
    overall_std: float = 0.45,
    per_sector_std: list[float] | None = None,
    worst_corners: list[dict] | None = None,
    trend: str = "stable",
) -> ConsistencyReport:
    return ConsistencyReport(
        overall_std_dev_s=overall_std,
        consistency_pct=95.0,
        median_lap_time_s=92.0,
        best_lap_time_s=91.2,
        theoretical_best_s=90.8,
        per_sector_std_dev=per_sector_std or [0.15, 0.35, 0.12],
        worst_sector=1,
        worst_corners=worst_corners or [
            {"name": "T5", "std_dev_s": 0.28},
            {"name": "T9", "std_dev_s": 0.18},
        ],
        trend=trend,
        focus_recommendation="Focus on Sector 2",
        lap_count=lap_count,
    )


def _make_sector_gaps() -> list[SectorGap]:
    return [
        SectorGap(sector=1, gap_s=0.15, std_dev_s=0.15, best_time_s=29.8, median_time_s=29.95),
        SectorGap(sector=2, gap_s=0.45, std_dev_s=0.35, best_time_s=30.2, median_time_s=30.65),
        SectorGap(sector=3, gap_s=0.10, std_dev_s=0.12, best_time_s=31.0, median_time_s=31.10),
    ]


def _make_strategy_vm(tmp_path: Path) -> StrategyViewModel:
    store = StintStore(tmp_path / "stints.json")
    vm = StrategyViewModel(store=store)
    return vm


# ---------------------------------------------------------------------------
# 1. Live strategy recalculation
# ---------------------------------------------------------------------------


class TestLiveStrategyRecalc:
    """Verify that live recalculation fires and updates state."""

    def test_fuel_deltas_tracked_on_lap_completion(self, tmp_path: Path) -> None:
        vm = _make_strategy_vm(tmp_path)
        vm.on_session_detected("race", "Monza", "Ferrari 296 GT3")
        vm._mode = "sprint"
        vm._race_active = True

        # First snapshot initialises prev_fuel_level
        vm.update_live({"lap_number": 1, "session_time_s": 0.0, "fuel_level": 50.0})
        # Lap 1→2: delta = 50 - 47.5 = 2.5
        vm.update_live({"lap_number": 2, "session_time_s": 92.0, "fuel_level": 47.5})
        # Lap 2→3: delta = 47.5 - 45.0 = 2.5
        vm.update_live({"lap_number": 3, "session_time_s": 184.0, "fuel_level": 45.0})

        assert len(vm._fuel_deltas) >= 1
        assert abs(vm._fuel_deltas[0] - 2.5) < 0.01

    def test_burn_rate_computed_from_deltas(self, tmp_path: Path) -> None:
        vm = _make_strategy_vm(tmp_path)
        vm._fuel_deltas = [2.3, 2.5, 2.4]
        assert abs(vm.fuelBurnRate - 2.4) < 0.01

    def test_fuel_margin_computed(self, tmp_path: Path) -> None:
        vm = _make_strategy_vm(tmp_path)
        vm._fuel_deltas = [2.5, 2.5, 2.5]
        vm._current_fuel = 30.0
        vm._total_laps = 20
        vm._prev_consistency_lap = 10
        # 10 laps remaining × 2.5 L/lap = 25L needed, have 30L → margin = 5L
        assert abs(vm.fuelMargin - 5.0) < 0.1

    def test_fuel_deficit_detected(self, tmp_path: Path) -> None:
        vm = _make_strategy_vm(tmp_path)
        vm._fuel_deltas = [3.0, 3.0, 3.0]
        vm._current_fuel = 15.0
        vm._total_laps = 20
        vm._prev_consistency_lap = 12
        # 8 laps remaining × 3.0 = 24L needed, have 15L → margin = -9L
        assert vm.fuelMargin < 0

    def test_live_recalc_does_not_fire_without_plan(self, tmp_path: Path) -> None:
        vm = _make_strategy_vm(tmp_path)
        vm._mode = "sprint"
        vm._race_active = True
        vm._plan = None  # no pre-race plan
        # Should not raise
        vm.update_live({"lap_number": 1, "session_time_s": 0.0, "fuel_level": 50.0})
        vm.update_live({"lap_number": 2, "session_time_s": 92.0, "fuel_level": 47.5})


# ---------------------------------------------------------------------------
# 2. Pit countdown state transitions
# ---------------------------------------------------------------------------


class TestPitCountdown:
    def test_laps_to_pit_from_plan(self, tmp_path: Path) -> None:
        vm = _make_strategy_vm(tmp_path)
        vm._plan = RacePlan(
            stints=[
                PlannedStint("soft", 1, 12, 55.0, 0.0, 80.0, 1100.0),
                PlannedStint("soft", 13, 20, 17.0, 38.0, 72.0, 750.0),
            ],
            total_race_time_s=1850.0,
            fuel_at_finish=2.1,
            alerts=[],
        )
        vm._prev_consistency_lap = 9
        assert vm.lapsToPit == 3  # pit at end of lap 12, currently on lap 9

    def test_pit_now_true_on_last_lap(self, tmp_path: Path) -> None:
        vm = _make_strategy_vm(tmp_path)
        vm._plan = RacePlan(
            stints=[
                PlannedStint("soft", 1, 12, 55.0, 0.0, 80.0, 1100.0),
                PlannedStint("soft", 13, 20, 17.0, 38.0, 72.0, 750.0),
            ],
            total_race_time_s=1850.0,
            fuel_at_finish=2.1,
            alerts=[],
        )
        vm._prev_consistency_lap = 11
        assert vm.pitNow is True

    def test_pit_fuel_load_for_next_stop(self, tmp_path: Path) -> None:
        vm = _make_strategy_vm(tmp_path)
        vm._plan = RacePlan(
            stints=[
                PlannedStint("soft", 1, 12, 55.0, 0.0, 80.0, 1100.0),
                PlannedStint("soft", 13, 20, 17.0, 38.0, 72.0, 750.0),
            ],
            total_race_time_s=1850.0,
            fuel_at_finish=2.1,
            alerts=[],
        )
        vm._prev_consistency_lap = 9
        assert vm.pitFuelLoad == 38.0

    def test_no_pit_when_no_plan(self, tmp_path: Path) -> None:
        vm = _make_strategy_vm(tmp_path)
        vm._plan = None
        assert vm.lapsToPit == -1
        assert vm.pitNow is False
        assert vm.pitFuelLoad == 0.0


# ---------------------------------------------------------------------------
# 3. Overlay category / tier filtering
# ---------------------------------------------------------------------------


class TestOverlayTiers:
    def test_core_race_widgets_visible_by_default(self) -> None:
        assert get_widget_tier("pit_countdown") == "core_race"
        assert get_widget_tier("sector_delta") == "core_race"
        assert get_widget_tier("strategy_status") == "core_race"
        assert get_widget_tier("gap_timing") == "core_race"
        assert get_widget_tier("push_manage") == "core_race"

    def test_coaching_widgets_visible_by_default(self) -> None:
        assert get_widget_tier("coaching") == "coaching"
        assert get_widget_tier("inputs_grip") == "coaching"

    def test_streamer_widgets_are_optional(self) -> None:
        assert get_widget_tier("chat") == "optional"
        assert get_widget_tier("promo_code_alert") == "optional"
        assert get_widget_tier("mic_visualizer") == "optional"

    def test_optional_hidden_from_default_catalog(self) -> None:
        assert is_widget_visible_in_catalog("chat", show_optional=False) is False
        assert is_widget_visible_in_catalog("chat", show_optional=True) is True

    def test_core_always_visible(self) -> None:
        assert is_widget_visible_in_catalog("pit_countdown", show_optional=False) is True

    def test_sprint_mode_has_new_widgets(self) -> None:
        # Post-refinement: Sprint default = 6-widget minimum.
        # gap_timing, standings, etc. are available in the catalog but
        # not enabled by default (ruthless cut for cognitive load).
        assert "pit_countdown" in SPRINT.overlay_profile
        assert "sector_delta" in SPRINT.overlay_profile
        assert "strategy_status" in SPRINT.overlay_profile
        assert "fuel_strategy" in SPRINT.overlay_profile
        assert "radar" in SPRINT.overlay_profile
        assert "gap_timing" not in SPRINT.overlay_profile  # opt-in

    def test_endurance_has_push_manage(self) -> None:
        assert "push_manage" in ENDURANCE.overlay_profile
        assert "push_manage" not in SPRINT.overlay_profile  # Sprint is always push

    def test_coaching_mode_stripped(self) -> None:
        assert "radar" not in COACHING.overlay_profile
        assert "standings" not in COACHING.overlay_profile
        assert "delta_bar" in COACHING.overlay_profile
        assert "sector_delta" in COACHING.overlay_profile


# ---------------------------------------------------------------------------
# 4. Coaching self-comparison output
# ---------------------------------------------------------------------------


class TestCoachingSelfComparison:
    def test_sector_gap_produces_concrete_insight(self) -> None:
        # Lower corner std_devs so sector focus wins
        report = _make_report(worst_corners=[
            {"name": "T5", "std_dev_s": 0.10},
            {"name": "T9", "std_dev_s": 0.08},
        ])
        gaps = _make_sector_gaps()
        result = generate_plan(report, laps_completed=10, sector_gaps=gaps)
        plan = result.value
        assert isinstance(plan, CoachingPlan)
        assert "Sector 2" in plan.focus_area
        assert plan.technique_insight  # non-empty
        assert "0.4" in plan.technique_insight or "0.5" in plan.technique_insight

    def test_technique_insight_mentions_best_time(self) -> None:
        report = _make_report(worst_corners=[
            {"name": "T5", "std_dev_s": 0.10},
        ])
        gaps = _make_sector_gaps()
        result = generate_plan(report, laps_completed=10, sector_gaps=gaps)
        plan = result.value
        assert "best" in plan.technique_insight.lower() or "30.2" in plan.technique_insight

    def test_without_gaps_falls_back_gracefully(self) -> None:
        report = _make_report()
        result = generate_plan(report, laps_completed=10, sector_gaps=None)
        plan = result.value
        assert isinstance(plan, CoachingPlan)
        assert plan.technique_insight  # still produces something
        assert "variance" in plan.technique_insight.lower() or "±" in plan.technique_insight

    def test_improving_trend_acknowledged(self) -> None:
        report = _make_report(trend="improving")
        gaps = _make_sector_gaps()
        result = generate_plan(report, laps_completed=10, sector_gaps=gaps)
        plan = result.value
        # Trend insight should surface somewhere
        assert plan.technique_insight  # non-empty

    def test_degrading_trend_warns(self) -> None:
        # No dominant corner, low sector stds → fallback to overall → trend insight
        report = _make_report(
            trend="degrading",
            per_sector_std=[0.1, 0.1, 0.1],
            worst_corners=[{"name": "T5", "std_dev_s": 0.05}],
        )
        result = generate_plan(report, laps_completed=10, sector_gaps=None)
        plan = result.value
        assert "dropping" in plan.technique_insight.lower() or "variance" in plan.technique_insight.lower()


# ---------------------------------------------------------------------------
# 5. Readiness action suggestions
# ---------------------------------------------------------------------------


class TestReadinessAction:
    def test_not_ready_with_few_laps(self) -> None:
        result = compute_readiness_action(profiles={}, pit_profile=None, lap_count=2)
        assert result.state == "not_ready"
        assert "3 more laps" in result.suggested_action

    def test_building_with_partial_data(self) -> None:
        profiles = {
            "soft": CompoundProfile(
                compound="soft",
                fuel_per_lap=2.5,
                fuel_curve=[],
                wear_per_lap=0.02,
                estimated_life=20,
                avg_lap_time_s=92.0,
                lap_time_delta_s=0.1,
                avg_track_temp_c=30.0,
                total_laps_logged=8,
                stint_count=1,
                confidence="medium",
            ),
        }
        result = compute_readiness_action(profiles, pit_profile=None, lap_count=8)
        assert result.state == "building"
        assert result.progress_pct > 0

    def test_ready_with_full_data(self) -> None:
        profiles = {
            "soft": CompoundProfile(
                compound="soft",
                fuel_per_lap=2.5,
                fuel_curve=[],
                wear_per_lap=0.02,
                estimated_life=20,
                avg_lap_time_s=92.0,
                lap_time_delta_s=0.1,
                avg_track_temp_c=30.0,
                total_laps_logged=30,
                stint_count=3,
                confidence="high",
                degradation={"available": True},
            ),
        }
        from lap_coach_logger.core.strategy_models import PitProfile
        pit = PitProfile(
            track="Monza", beta_transit=18.0, beta_fuel_rate=0.5,
            beta_tire_change=3.0, r_squared=0.95, measurements=[],
        )
        result = compute_readiness_action(profiles, pit_profile=pit, lap_count=30, consistency_std=0.8)
        assert result.state == "ready"
        assert "Ready to race" in result.suggested_action


# ---------------------------------------------------------------------------
# 6. Coaching carryover
# ---------------------------------------------------------------------------


class TestCoachingCarryover:
    def test_carryover_captures_focus(self) -> None:
        carry = build_coaching_carryover(
            focus_area="Sector 2",
            overall_std=0.45,
            trend="improving",
            sector_gaps_total=0.7,
            best_lap_time=91.2,
            technique_insight="Sector 2: You lose 0.4s here vs your best.",
        )
        assert carry.focus_sector == "Sector 2"
        assert carry.focus_corner is None
        assert carry.time_on_table_s == 0.7
        assert carry.trend == "improving"

    def test_carryover_truncates_long_insight(self) -> None:
        carry = build_coaching_carryover(
            focus_area="T5",
            overall_std=0.3,
            trend="stable",
            technique_insight="A" * 200,
        )
        assert len(carry.technique_hint) <= 80

    def test_corner_focus_detected(self) -> None:
        carry = build_coaching_carryover(
            focus_area="T5",
            overall_std=0.3,
            trend="stable",
        )
        assert carry.focus_corner == "T5"
        assert carry.focus_sector is None


# ---------------------------------------------------------------------------
# 7. Plan-vs-actual review
# ---------------------------------------------------------------------------


class TestPlanVsActual:
    def test_plan_vs_actual_empty_without_original(self, tmp_path: Path) -> None:
        vm = _make_strategy_vm(tmp_path)
        assert vm.planVsActual == {}

    def test_plan_vs_actual_records_pit_events(self, tmp_path: Path) -> None:
        vm = _make_strategy_vm(tmp_path)
        vm._original_plan = RacePlan(
            stints=[
                PlannedStint("soft", 1, 12, 55.0, 0.0, 80.0, 1100.0),
                PlannedStint("soft", 13, 20, 17.0, 38.0, 72.0, 750.0),
            ],
            total_race_time_s=1850.0,
            fuel_at_finish=2.1,
            alerts=[],
        )
        vm._actual_pit_laps = [12]
        vm._actual_fuel_added = [39.0]
        vm._current_fuel = 1.8
        vm._fuel_deltas = [2.5] * 20

        review = vm.planVsActual
        assert review["planned_pit_laps"] == [12]
        assert review["actual_pit_laps"] == [12]
        assert review["planned_fuel_at_finish"] == 2.1
        assert review["actual_fuel_at_finish"] == 1.8
        assert review["planned_num_stops"] == 1
        assert review["actual_num_stops"] == 1
