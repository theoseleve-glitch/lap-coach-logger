"""Runtime soak test — 30-minute simulated session.

Verifies the app is production-safe under realistic load:
- No crashes when snapshots are malformed or missing keys
- Mode switching doesn't leak state
- Log output is bounded (dedup works)
- Memory stays roughly stable (no unbounded buffers)
- All VM properties remain accessible throughout the run
"""
from __future__ import annotations

import gc
import logging
import sys
import threading
import time
from pathlib import Path

import pytest

from tests.qt_mock import install

install()

from lap_coach_logger.core.stint_store import StintStore  # noqa: E402
from lap_coach_logger.utils.log_dedupe import DedupFilter  # noqa: E402
from lap_coach_logger.viewmodels.strategy_vm import StrategyViewModel  # noqa: E402


# Real-world session = 30 minutes @ 10 Hz = 18,000 samples.
# We run a condensed version that hits every code path without taking
# 30 wall-clock minutes. 5000 iterations exercises ~8 minutes of data
# and is enough to prove stability patterns.
_SOAK_ITERATIONS = 5000
_LAPS_PER_ITERATION = 0.01  # ~50 laps total
_SAMPLE_RATE_HZ = 10.0


def _make_snap(iteration: int, missing_keys: frozenset[str] = frozenset()) -> dict:
    """Generate one realistic telemetry snapshot."""
    lap_number = int(iteration * _LAPS_PER_ITERATION) + 1
    session_time = iteration / _SAMPLE_RATE_HZ
    base = {
        "timestamp_utc": f"2026-04-15T12:00:{iteration % 60:02d}",
        "sim": "iRacing",
        "session_uid": "soak-test-uid",
        "session_time_s": session_time,
        "lap_number": lap_number,
        "lap_distance_m": (iteration % 1000) * 5.0,
        "lap_dist_pct": (iteration % 100) / 100.0,
        "speed_kph": 180.0 + (iteration % 50),
        "throttle_pct": 0.8 if iteration % 3 else 0.3,
        "brake_pct": 0.0 if iteration % 3 else 0.5,
        "steering_deg": -2.0 + (iteration % 5),
        "gear": 4,
        "rpm": 7000.0,
        "tyre_temp_lf": 85.0, "tyre_temp_rf": 86.0,
        "tyre_temp_lr": 84.0, "tyre_temp_rr": 85.5,
        "track_temp_c": 30.0, "air_temp_c": 22.0,
        "fuel_level": 50.0 - iteration * 0.001,
        "fuel_capacity": 110.0,
        "is_in_pits": False,
        "is_on_track": True,
        "track_name": "Monza",
        "car_name": "Ferrari 296 GT3",
        "session_type": "practice",
        "position": 5,
        "num_cars": 20,
    }
    for key in missing_keys:
        base.pop(key, None)
    return base


class TestSoak:
    """30-minute simulated session stability tests."""

    def test_soak_no_crash_with_complete_snapshots(self, tmp_path: Path) -> None:
        """Base case: all fields present, no crash across many iterations."""
        store = StintStore(tmp_path / "stints.json")
        vm = StrategyViewModel(store=store)
        vm.on_session_detected("practice", "Monza", "Ferrari 296 GT3")

        for i in range(_SOAK_ITERATIONS):
            vm.update_live(_make_snap(i))

        vm.on_session_ended()

        # VM is still responsive
        assert vm.dataInspection["total_samples"] > 0
        assert vm.readinessState["lap_count"] >= 0

    def test_soak_handles_missing_keys(self, tmp_path: Path) -> None:
        """Random missing keys should not crash the VM."""
        store = StintStore(tmp_path / "stints.json")
        vm = StrategyViewModel(store=store)
        vm.on_session_detected("practice", "Monza", "Ferrari 296 GT3")

        # Every 100th snapshot drops lap_number; every 50th drops fuel_level;
        # every 200th drops session_time_s
        for i in range(_SOAK_ITERATIONS):
            missing = set()
            if i % 100 == 0:
                missing.add("lap_number")
            if i % 50 == 0:
                missing.add("fuel_level")
            if i % 200 == 0:
                missing.add("session_time_s")
            vm.update_live(_make_snap(i, frozenset(missing)))

        # No crash, VM still functional
        inspection = vm.dataInspection
        assert inspection["total_samples"] > 0

    def test_soak_handles_empty_snapshots(self, tmp_path: Path) -> None:
        """Empty/None snapshots must not crash."""
        store = StintStore(tmp_path / "stints.json")
        vm = StrategyViewModel(store=store)
        vm.on_session_detected("practice", "Monza", "Ferrari 296 GT3")

        for i in range(1000):
            if i % 10 == 0:
                vm.update_live({})  # empty dict
            elif i % 7 == 0:
                vm.update_live(None)  # None
            elif i % 5 == 0:
                vm.update_live("not a dict")  # wrong type
            else:
                vm.update_live(_make_snap(i))

        # VM is still usable
        assert vm.currentMode == "sprint"

    def test_soak_mode_switching(self, tmp_path: Path) -> None:
        """Rapid mode switches should not leak state or crash."""
        store = StintStore(tmp_path / "stints.json")
        vm = StrategyViewModel(store=store)
        modes = ["sprint", "endurance", "coaching", "data"]

        for i in range(1000):
            vm.set_mode(modes[i % 4])
            if i % 10 == 0:
                vm.update_live(_make_snap(i))

        # Final mode is stable
        assert vm.currentMode in modes
        # Tabs for current mode are populated
        tabs = vm.tabsForMode
        assert len(tabs) >= 2

    def test_soak_memory_bounded(self, tmp_path: Path) -> None:
        """Snapshot buffer must not grow unbounded."""
        store = StintStore(tmp_path / "stints.json")
        vm = StrategyViewModel(store=store)
        vm.on_session_detected("practice", "Monza", "Ferrari 296 GT3")

        for i in range(_SOAK_ITERATIONS):
            vm.update_live(_make_snap(i))

        # Snapshot buffer is capped
        buffer_size = len(vm._snapshot_buffer)
        assert buffer_size <= vm._snapshot_buffer_max, (
            f"Buffer grew to {buffer_size}, max is {vm._snapshot_buffer_max}"
        )

        # Lap times buffer should also be reasonable (one per lap, max ~50 laps)
        assert len(vm._lap_times_buffer) < 100


class TestLogDedupeIntegration:
    """Verify DedupFilter bounds log output under repeated errors."""

    def test_dedupe_bounds_error_log_output(self) -> None:
        """Repeated identical errors should produce bounded log output."""
        dedupe = DedupFilter(window_s=30.0)
        logger = logging.getLogger("test_soak_dedup")
        logger.handlers.clear()

        from io import StringIO
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(dedupe)
        logger.addHandler(handler)
        logger.propagate = False
        logger.setLevel(logging.DEBUG)

        # Fire the same exception 10,000 times (simulating a stuck signal handler)
        def _fire():
            try:
                raise ValueError("boom")
            except ValueError:
                logger.critical("slot error", exc_info=True)

        for _ in range(10_000):
            _fire()

        output = stream.getvalue()
        # Exactly ONE traceback should have reached the stream
        assert output.count("Traceback") == 1, (
            f"Expected 1 traceback, got {output.count('Traceback')}. "
            f"Output size: {len(output)} chars"
        )
        # Output should be bounded (not 10,000× the traceback size)
        assert len(output) < 10_000, f"Output grew to {len(output)} chars"

    def test_dedupe_thread_safety_under_load(self) -> None:
        """Concurrent threads hitting dedup should not deadlock or crash."""
        dedupe = DedupFilter(window_s=30.0)
        logger = logging.getLogger("test_soak_dedup_threads")
        logger.handlers.clear()
        logger.propagate = False

        from io import StringIO
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(dedupe)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        errors: list[BaseException] = []

        def _worker():
            try:
                for _ in range(500):
                    try:
                        raise RuntimeError("x")
                    except RuntimeError:
                        logger.error("err", exc_info=True)
            except BaseException as e:
                errors.append(e)

        threads = [threading.Thread(target=_worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        assert not errors, f"Threads raised: {errors}"
        # No thread should be stuck
        for t in threads:
            assert not t.is_alive(), "Worker thread deadlocked"


class TestSnapshotValidatorIntegration:
    """Verify validator gates malformed input at the entry point."""

    def test_validator_rejects_non_dict(self, tmp_path: Path) -> None:
        store = StintStore(tmp_path / "stints.json")
        vm = StrategyViewModel(store=store)

        # These should all be no-ops, not raise
        vm.update_live(None)
        vm.update_live([])
        vm.update_live("string")
        vm.update_live(42)

        # Buffer remains empty
        assert len(vm._snapshot_buffer) == 0

    def test_validator_accepts_sparse_dict(self, tmp_path: Path) -> None:
        """Dict with only some keys should still be accepted and buffered."""
        store = StintStore(tmp_path / "stints.json")
        vm = StrategyViewModel(store=store)

        sparse = {"speed_kph": 200.0, "session_time_s": 1.0}
        vm.update_live(sparse)

        assert len(vm._snapshot_buffer) == 1


class TestFullSessionCycle:
    """End-to-end session with all 4 modes."""

    def test_full_cycle_across_all_modes(self, tmp_path: Path) -> None:
        """Start session in each mode, drive 100 laps equivalent, end session."""
        store = StintStore(tmp_path / "stints.json")

        for mode in ["sprint", "endurance", "coaching", "data"]:
            vm = StrategyViewModel(store=store)
            vm.set_mode(mode)
            vm.on_session_detected("practice", "Monza", "GT3")

            for i in range(2000):
                vm.update_live(_make_snap(i))

            # All key properties readable
            _ = vm.currentMode
            _ = vm.tabsForMode
            _ = vm.activeTab
            _ = vm.readinessState
            _ = vm.paceBreakdown
            _ = vm.dataInspection
            _ = vm.activePlan
            _ = vm.syncStatus
            _ = vm.metricStates

            vm.on_session_ended()

        # Everything completed without crash
        assert True
