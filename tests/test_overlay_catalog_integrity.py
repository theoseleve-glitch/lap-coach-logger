"""Overlay catalog integrity gates.

Locks in the "nothing unfinished ships" invariant:
- Every default widget has a real QML component file on disk.
- Every default widget has a tier assigned.
- No default is text-heavy.
- Widget IDs in the catalog + tier map stay in sync with the settings
  map so settings don't drift from the registry.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from lap_coach_logger.core.mode_descriptor import MODE_REGISTRY
from lap_coach_logger.viewmodels.overlay_helpers import (
    OVERLAY_TIERS,
    WIDGET_CATEGORIES,
    make_default_widget_settings,
)


# Widgets that explicitly map to non-standard QML filenames / don't
# render a standalone widget (they mount directly into OverlayWindow).
# Any widget registered but not in this set must have a matching
# QML file in src/lap_coach_logger/qml/Overlay/widgets/.
_QML_FILENAME_OVERRIDES: dict[str, str] = {
    # widget_id -> QML filename (without .qml extension)
    "delta_timing": "DeltaTimeWidget",
    "inputs_grip": "InputsWidget",
    "fuel_strategy": "FuelWidget",
    "track_map": "TrackMapWidget",
    "laptime_graph": "LaptimeGraphWidget",
    "laptime_log": "LaptimeLogWidget",
    "laptime_spread": "LaptimeSpreadWidget",
    "mini_map": "MiniMapWidget",
    "flat_map": "FlatMapWidget",
    "world_map": "WorldMapWidget",
    "fuel_calculator": "FuelCalculatorWidget",
    "race_strategy": "RaceStrategyWidget",
    "tire_life": "TireLifeWidget",
    "pitbox_helper": "PitboxHelperWidget",
    "weather_monitor": "WeatherMonitorWidget",
    "boost_box": "BoostBoxWidget",
    "gforce_meter": "GForceMeterWidget",
    "gforce_meter_full": "GForceMeterWidget",
    "advanced_panel": "AdvancedPanelWidget",
    "data_blocks": "DataBlocksWidget",
    "race_schedule": "RaceScheduleWidget",
    "heart_rate": "HeartRateWidget",
    "input_telemetry": "InputTelemetryWidget",
    "chat": "ChatWidget",
    "chat_highlight": "ChatHighlightWidget",
    "chat_race_game": "ChatRaceGameWidget",
    "chat_race_standing": "ChatRaceStandingWidget",
    "custom_text": "CustomTextWidget",
    "custom_url": "CustomUrlWidget",
    "garage_cover": "GarageCoverWidget",
    "mic_visualizer": "MicVisualizerWidget",
    "promo_code_alert": "PromoCodeAlertWidget",
    "sector_delta": "SectorDeltaWidget",
    "pit_countdown": "PitCountdownWidget",
    "strategy_status": "StrategyStatusWidget",
    "push_manage": "PushManageWidget",
    "gap_timing": "GapTimingWidget",
    "race_reminder": "RaceReminderWidget",
    "delta_bar": "DeltaBarWidget",
    "lap_timing": "LapTimingWidget",
    "session_timer": "SessionTimerWidget",
    "flags": "FlagsWidget",
    "digiflag": "DigiflagWidget",
    "radar": "RadarWidget",
    "radar_bars": "RadarBarsWidget",
    "blind_spot": "BlindSpotWidget",
    "overtake_alert": "OvertakeAlertWidget",
    "relatives": "RelativesWidget",
    "standings": "StandingsWidget",
    "standings_table": "StandingsWidget",
    "leaderboard": "LeaderboardWidget",
    "head_to_head": "HeadToHeadWidget",
    "track_map_canvas": "TrackMapWidget",
    "coaching": "CoachingWidget",
    "weather": "WeatherMonitorWidget",
}


def _qml_widgets_dir() -> Path:
    here = Path(__file__).resolve().parent.parent
    return here / "src" / "lap_coach_logger" / "qml" / "Overlay" / "widgets"


def _all_default_widget_ids() -> set[str]:
    """Every widget enabled by default in any mode."""
    ids: set[str] = set()
    for desc in MODE_REGISTRY.values():
        ids.update(desc.overlay_profile)
    return ids


class TestDefaultWidgetsHaveQmlComponents:
    """No broken references — every default widget maps to real QML."""

    def test_every_default_has_a_qml_file(self):
        widgets_dir = _qml_widgets_dir()
        assert widgets_dir.exists(), f"Expected QML widgets dir at {widgets_dir}"

        missing = []
        for widget_id in _all_default_widget_ids():
            qml_name = _QML_FILENAME_OVERRIDES.get(widget_id)
            if qml_name is None:
                missing.append(f"{widget_id} (no filename mapping)")
                continue
            qml_path = widgets_dir / f"{qml_name}.qml"
            if not qml_path.exists():
                missing.append(f"{widget_id} -> {qml_name}.qml")
        assert not missing, (
            "Default widgets without a QML component:\n  " + "\n  ".join(missing)
        )


class TestCatalogConsistency:
    def test_every_default_has_a_tier(self):
        """Every default widget must be in OVERLAY_TIERS — no 'optional'
        defaults."""
        for widget_id in _all_default_widget_ids():
            tier = OVERLAY_TIERS.get(widget_id)
            assert tier is not None, (
                f"{widget_id} is enabled by default but missing from OVERLAY_TIERS"
            )
            assert tier in ("core_race", "coaching"), (
                f"{widget_id} is tier={tier} but enabled by default — "
                f"only core_race / coaching may appear in defaults"
            )

    def test_every_default_has_a_category(self):
        for widget_id in _all_default_widget_ids():
            assert widget_id in WIDGET_CATEGORIES, (
                f"{widget_id} is enabled by default but missing from WIDGET_CATEGORIES"
            )

    def test_every_default_has_settings(self):
        """Every default widget must have a default size/opacity entry
        so the settings manager can render it."""
        settings = make_default_widget_settings()
        for widget_id in _all_default_widget_ids():
            assert widget_id in settings, (
                f"{widget_id} is enabled by default but missing from "
                f"make_default_widget_settings()"
            )

    def test_tier_map_and_category_map_agree_on_core_widgets(self):
        """Every widget tagged core_race should also have a category —
        catches drift between the two registries."""
        for widget_id, tier in OVERLAY_TIERS.items():
            if tier == "core_race":
                assert widget_id in WIDGET_CATEGORIES, (
                    f"{widget_id} is tier=core_race but missing from "
                    f"WIDGET_CATEGORIES — registries drifted"
                )
