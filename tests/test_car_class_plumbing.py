"""Tests for StrategyViewModel.carClass plumbing (Part 0)."""
from __future__ import annotations

from pathlib import Path

from tests.qt_mock import install

install()

from lap_coach_logger.core.stint_store import StintStore  # noqa: E402
from lap_coach_logger.viewmodels.strategy_vm import StrategyViewModel  # noqa: E402


def _build_vm(tmp_path: Path) -> StrategyViewModel:
    store = StintStore(tmp_path / "stints.json")
    return StrategyViewModel(store=store)


class TestCarClassProperty:
    def test_empty_when_no_resolution(self, tmp_path: Path):
        vm = _build_vm(tmp_path)
        assert vm.carClass == ""

    def test_resolves_from_live_snapshot(self, tmp_path: Path):
        # Ferrari 296 GT3 is in the bundled LUT with car_class "GT3".
        vm = _build_vm(tmp_path)
        vm.update_live({
            "sim": "iracing",
            "track_name": "Monza",
            "car_name": "Ferrari 296 GT3",
            "lap_number": 1,
            "session_time_s": 10.0,
        })
        assert vm.carClass == "GT3"

    def test_unknown_car_falls_back_to_empty(self, tmp_path: Path):
        vm = _build_vm(tmp_path)
        vm.update_live({
            "sim": "iracing",
            "track_name": "Mystery",
            "car_name": "Unknown Test Car 9000",
            "lap_number": 1,
            "session_time_s": 10.0,
        })
        assert vm.carClass == ""

    def test_re_resolves_when_car_changes(self, tmp_path: Path):
        vm = _build_vm(tmp_path)
        # First car resolved
        vm.update_live({
            "sim": "iracing",
            "track_name": "Monza",
            "car_name": "Ferrari 296 GT3",
            "lap_number": 1,
            "session_time_s": 10.0,
        })
        assert vm.carClass == "GT3"

        # Switch car mid-session — carClass should update on setTrackCar
        vm.setTrackCar("Monza", "Unknown Test Car 9000")
        assert vm.carClass == ""


class TestCarClassOverlayIntegration:
    def test_overlay_vm_reads_car_class_via_getattr(self, tmp_path: Path):
        """Overlay VM uses the same getattr path as before, so the new
        property surface must be accessible."""
        vm = _build_vm(tmp_path)
        vm.update_live({
            "sim": "iracing",
            "track_name": "Monza",
            "car_name": "Ferrari 296 GT3",
            "lap_number": 1,
            "session_time_s": 10.0,
        })
        # Overlay VM's getattr pattern:
        cls = getattr(vm, "carClass", "")
        assert cls == "GT3"


class TestCornerInsightHistoryCap:
    def test_history_is_capped_for_long_sessions(self, tmp_path: Path):
        """Endurance sessions can accumulate hundreds of laps; the
        rolling cap must prevent unbounded memory growth while still
        preserving the most recent insights for the summary."""
        from lap_coach_logger.coaching.corner_insights import CornerInsight

        vm = _build_vm(tmp_path)
        cap = vm._CORNER_INSIGHT_HISTORY_CAP
        # Push cap+50 laps worth of insights
        for lap in range(cap + 50):
            vm.push_corner_insights([
                CornerInsight(corner_name=f"T{lap % 5}", time_loss_s=0.2),
            ])
        assert len(vm._corner_insights_history) == cap
        # Latest lap's insight should still be accessible
        assert vm._corner_insights_latest[0].corner_name.startswith("T")
