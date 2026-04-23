"""Tests for overlay_derived — widget state mapping, alert priority, degraded rendering.

These tests exercise the pure-function layer. The QML renders whatever
these return, so if these are right the widgets display correctly.
"""

from __future__ import annotations

from lap_coach_logger.viewmodels.overlay_derived import (
    FUEL_OK_MARGIN_L,
    FUEL_SAVE_MARGIN_L,
    FUEL_TIGHT_MARGIN_L,
    build_pit_countdown_display,
    build_strategy_status,
    compute_fuel_state,
    compute_push_manage,
    highest_severity,
)


# ---------------------------------------------------------------------------
# Fuel state mapping
# ---------------------------------------------------------------------------


class TestFuelState:
    def test_safe_when_margin_large(self) -> None:
        assert compute_fuel_state(5.0) == "SAFE"
        assert compute_fuel_state(FUEL_OK_MARGIN_L) == "SAFE"
        assert compute_fuel_state(FUEL_OK_MARGIN_L + 0.01) == "SAFE"

    def test_tight_between_ok_and_tight_thresholds(self) -> None:
        assert compute_fuel_state(FUEL_OK_MARGIN_L - 0.01) == "TIGHT"
        assert compute_fuel_state(FUEL_TIGHT_MARGIN_L + 0.01) == "TIGHT"

    def test_save_between_tight_and_zero(self) -> None:
        assert compute_fuel_state(FUEL_TIGHT_MARGIN_L - 0.01) == "SAVE"
        assert compute_fuel_state(FUEL_SAVE_MARGIN_L + 0.01) == "SAVE"
        assert compute_fuel_state(0.0) == "SAVE"

    def test_deficit_when_negative(self) -> None:
        assert compute_fuel_state(-0.01) == "DEFICIT"
        assert compute_fuel_state(-5.0) == "DEFICIT"


# ---------------------------------------------------------------------------
# Strategy status content rules
# ---------------------------------------------------------------------------


class TestStrategyStatus:
    def test_full_line_format(self) -> None:
        status = build_strategy_status(
            position=5, current_lap=9, total_laps=20,
            fuel_state="SAFE", grip_pct=82.0,
        )
        assert "P5" in status.line
        assert "L9/20" in status.line
        assert "Fuel SAFE" in status.line
        assert "Grip 82%" in status.line

    def test_no_position_when_unknown(self) -> None:
        status = build_strategy_status(
            position=None, current_lap=5, total_laps=15,
            fuel_state="SAFE",
        )
        assert "P" not in status.line
        assert "L5/15" in status.line

    def test_no_grip_when_unavailable(self) -> None:
        status = build_strategy_status(
            position=3, current_lap=1, total_laps=10,
            fuel_state="SAFE", grip_pct=None,
        )
        assert "Grip" not in status.line

    def test_severity_critical_on_pit_now(self) -> None:
        status = build_strategy_status(
            position=1, current_lap=12, total_laps=20,
            fuel_state="SAFE", pit_now=True,
        )
        assert status.severity == "critical"

    def test_severity_critical_on_fuel_deficit(self) -> None:
        status = build_strategy_status(
            position=1, current_lap=5, total_laps=20,
            fuel_state="DEFICIT",
        )
        assert status.severity == "critical"

    def test_severity_advisory_on_fuel_tight(self) -> None:
        status = build_strategy_status(
            position=1, current_lap=5, total_laps=20,
            fuel_state="TIGHT",
        )
        assert status.severity == "advisory"

    def test_severity_advisory_on_pit_soon(self) -> None:
        status = build_strategy_status(
            position=1, current_lap=9, total_laps=20,
            fuel_state="SAFE", laps_to_pit=2,
        )
        assert status.severity == "advisory"

    def test_severity_ok_when_all_normal(self) -> None:
        status = build_strategy_status(
            position=1, current_lap=5, total_laps=20,
            fuel_state="SAFE", laps_to_pit=10,
        )
        assert status.severity == "ok"


# ---------------------------------------------------------------------------
# Push / Manage / Save transitions
# ---------------------------------------------------------------------------


class TestPushManage:
    def test_save_on_fuel_deficit(self) -> None:
        state = compute_push_manage(
            fuel_margin_l=-1.0, fuel_state="DEFICIT",
            grip_pct=90.0,
        )
        assert state.state == "SAVE"
        assert "deficit" in state.reason.lower() or "fuel" in state.reason.lower()

    def test_save_on_fuel_save_state(self) -> None:
        state = compute_push_manage(
            fuel_margin_l=0.3, fuel_state="SAVE",
            grip_pct=90.0,
        )
        assert state.state == "SAVE"

    def test_save_on_fuel_tight(self) -> None:
        state = compute_push_manage(
            fuel_margin_l=1.0, fuel_state="TIGHT",
            grip_pct=90.0,
        )
        assert state.state == "SAVE"

    def test_manage_on_low_grip(self) -> None:
        state = compute_push_manage(
            fuel_margin_l=5.0, fuel_state="SAFE",
            grip_pct=50.0,   # below 55%
        )
        assert state.state == "MANAGE"

    def test_manage_on_late_stint_moderate_grip(self) -> None:
        state = compute_push_manage(
            fuel_margin_l=5.0, fuel_state="SAFE",
            grip_pct=65.0, stint_lap=15, stint_total_laps=18,
        )
        assert state.state == "MANAGE"

    def test_push_when_all_nominal(self) -> None:
        state = compute_push_manage(
            fuel_margin_l=5.0, fuel_state="SAFE",
            grip_pct=85.0, stint_lap=5, stint_total_laps=18,
        )
        assert state.state == "PUSH"

    def test_push_with_no_grip_data(self) -> None:
        """Missing grip data shouldn't force SAVE/MANAGE if fuel is fine."""
        state = compute_push_manage(
            fuel_margin_l=3.0, fuel_state="SAFE",
            grip_pct=None,
        )
        assert state.state == "PUSH"

    def test_fuel_overrides_grip(self) -> None:
        """Fuel DEFICIT overrides even good grip."""
        state = compute_push_manage(
            fuel_margin_l=-2.0, fuel_state="DEFICIT",
            grip_pct=95.0,
        )
        assert state.state == "SAVE"


# ---------------------------------------------------------------------------
# Pit countdown display rules
# ---------------------------------------------------------------------------


class TestPitCountdownDisplay:
    def test_hidden_when_no_plan(self) -> None:
        display = build_pit_countdown_display(
            laps_to_pit=-1, pit_fuel_load=0.0, fuel_state="SAFE",
        )
        assert display.visible is False

    def test_hidden_when_outside_window(self) -> None:
        display = build_pit_countdown_display(
            laps_to_pit=10, pit_fuel_load=40.0, fuel_state="SAFE",
        )
        assert display.visible is False

    def test_advisory_in_window(self) -> None:
        display = build_pit_countdown_display(
            laps_to_pit=3, pit_fuel_load=40.0, fuel_state="SAFE",
        )
        assert display.visible is True
        assert display.severity == "advisory"
        assert "PIT IN 3" in display.headline
        assert "40" in display.sub

    def test_critical_on_last_lap(self) -> None:
        display = build_pit_countdown_display(
            laps_to_pit=1, pit_fuel_load=40.0, fuel_state="SAFE",
        )
        assert display.visible is True
        assert display.severity == "critical"
        assert "PIT NEXT LAP" in display.headline or "NEXT LAP" in display.headline

    def test_box_box_box_on_zero_lap(self) -> None:
        display = build_pit_countdown_display(
            laps_to_pit=0, pit_fuel_load=40.0, fuel_state="SAFE",
        )
        assert display.visible is True
        assert display.severity == "critical"
        assert "BOX" in display.headline

    def test_fuel_deficit_escalates_to_critical(self) -> None:
        display = build_pit_countdown_display(
            laps_to_pit=4, pit_fuel_load=40.0, fuel_state="DEFICIT",
        )
        assert display.visible is True
        assert display.severity == "critical"


# ---------------------------------------------------------------------------
# Alert severity priority
# ---------------------------------------------------------------------------


class TestSeverityPriority:
    def test_critical_wins(self) -> None:
        assert highest_severity("advisory", "ok", "critical") == "critical"

    def test_advisory_beats_ok(self) -> None:
        assert highest_severity("ok", "advisory") == "advisory"

    def test_silent_lowest(self) -> None:
        assert highest_severity("silent", "ok") == "ok"

    def test_empty_defaults_to_ok(self) -> None:
        assert highest_severity() == "ok"

    def test_unknown_severity_treated_as_lowest(self) -> None:
        assert highest_severity("unknown", "ok") == "ok"
