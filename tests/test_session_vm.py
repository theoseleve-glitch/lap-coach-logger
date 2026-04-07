"""Tests for SessionViewModel -- live telemetry state for QML."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# PySide6 may not be installed in the test environment.  We mock the Qt
# modules so the ViewModel source can be imported without a real Qt runtime.
# ---------------------------------------------------------------------------

_qt_core_mock = MagicMock()


class _FakeSignalInstance:
    """Per-object signal instance that records emit() calls."""

    def __init__(self) -> None:
        self._mock = MagicMock()

    def emit(self, *args: object) -> None:
        self._mock(*args)

    def connect(self, slot: object) -> None:  # noqa: ARG002
        pass

    @property
    def call_count(self) -> int:
        return self._mock.call_count

    @property
    def call_args(self):  # noqa: ANN204
        return self._mock.call_args

    @property
    def call_args_list(self):  # noqa: ANN204
        return self._mock.call_args_list


class _FakeSignal:
    """Descriptor that yields a fresh _FakeSignalInstance per owner object."""

    def __init__(self, *_args: object) -> None:
        self._name: str | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def __get__(self, obj: object, objtype: type | None = None) -> _FakeSignal | _FakeSignalInstance:
        if obj is None:
            return self
        attr = f"_sig_{self._name}"
        inst = obj.__dict__.get(attr)
        if inst is None:
            inst = _FakeSignalInstance()
            obj.__dict__[attr] = inst
        return inst


class _FakeQObject:
    def __init__(self, *_a: object, **_kw: object) -> None:
        pass


_qt_core_mock.QObject = _FakeQObject
_qt_core_mock.Signal = _FakeSignal
_qt_core_mock.Slot = lambda *a, **kw: (lambda fn: fn)  # noqa: ARG005
_qt_core_mock.Property = lambda *a, **kw: property(kw.get("fget", lambda s: None))  # noqa: ARG005

sys.modules.setdefault("PySide6", MagicMock())
sys.modules.setdefault("PySide6.QtCore", _qt_core_mock)

from lap_coach_logger.viewmodels.session_vm import (  # noqa: E402
    SessionViewModel,
    _format_delta,
    _format_time,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_snapshot(**overrides: object) -> dict:
    """Build a realistic snapshot dict with sensible defaults."""
    base: dict[str, object] = {
        "sim": None,
        "track": None,
        "car": None,
        "current_lap": 0,
        "sample_rate_hz_est": 0.0,
        "live": {},
        "lap_times": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# _format_time
# ---------------------------------------------------------------------------

class TestFormatTime:
    """Module-level helper: seconds -> 'M:SS.mmm'."""

    def test_zero_returns_dash(self) -> None:
        assert _format_time(0) == "\u2014"

    def test_negative_returns_dash(self) -> None:
        assert _format_time(-1.0) == "\u2014"

    def test_sub_minute(self) -> None:
        # 90.5s -> 1:30.500
        assert _format_time(90.5) == "1:30.500"

    def test_over_two_minutes(self) -> None:
        # 137.834s -> 2:17.834
        assert _format_time(137.834) == "2:17.834"

    def test_exact_minute(self) -> None:
        # 60.0s -> 1:00.000
        assert _format_time(60.0) == "1:00.000"

    def test_small_value(self) -> None:
        # 23.456s -> 0:23.456
        assert _format_time(23.456) == "0:23.456"


# ---------------------------------------------------------------------------
# _format_delta
# ---------------------------------------------------------------------------

class TestFormatDelta:
    """Module-level helper: delta seconds -> '+X.XXX' / '-X.XXX' / 'BEST'."""

    def test_zero_returns_best(self) -> None:
        assert _format_delta(0.0) == "BEST"

    def test_positive_delta(self) -> None:
        assert _format_delta(1.234) == "+1.234"

    def test_negative_delta(self) -> None:
        assert _format_delta(-0.567) == "-0.567"

    def test_large_positive(self) -> None:
        assert _format_delta(12.1) == "+12.100"

    def test_small_negative(self) -> None:
        assert _format_delta(-0.001) == "-0.001"


# ---------------------------------------------------------------------------
# Default property values
# ---------------------------------------------------------------------------

class TestDefaultProperties:
    """Before any snapshot arrives, properties should have safe defaults."""

    def test_track_default(self) -> None:
        vm = SessionViewModel()
        assert vm.track == ""

    def test_car_default(self) -> None:
        vm = SessionViewModel()
        assert vm.car == ""

    def test_sim_default(self) -> None:
        vm = SessionViewModel()
        assert vm.sim == ""

    def test_current_lap_default(self) -> None:
        vm = SessionViewModel()
        assert vm.currentLap == 0

    def test_last_lap_time_default(self) -> None:
        vm = SessionViewModel()
        assert vm.lastLapTime == "\u2014"

    def test_best_lap_time_default(self) -> None:
        vm = SessionViewModel()
        assert vm.bestLapTime == "\u2014"

    def test_best_lap_number_default(self) -> None:
        vm = SessionViewModel()
        assert vm.bestLapNumber == 0

    def test_last_lap_delta_default(self) -> None:
        vm = SessionViewModel()
        assert vm.lastLapDelta == ""

    def test_consistency_pct_default(self) -> None:
        vm = SessionViewModel()
        assert vm.consistencyPct == 100.0

    def test_consistency_sigma_default(self) -> None:
        vm = SessionViewModel()
        assert vm.consistencySigma == ""

    def test_speed_kph_default(self) -> None:
        vm = SessionViewModel()
        assert vm.speedKph == 0.0

    def test_throttle_pct_default(self) -> None:
        vm = SessionViewModel()
        assert vm.throttlePct == 0.0

    def test_brake_pct_default(self) -> None:
        vm = SessionViewModel()
        assert vm.brakePct == 0.0

    def test_laps_default(self) -> None:
        vm = SessionViewModel()
        assert vm.laps == []

    def test_speed_history_default(self) -> None:
        vm = SessionViewModel()
        assert list(vm.speedHistory) == []


# ---------------------------------------------------------------------------
# update_from_snapshot — track/car/sim
# ---------------------------------------------------------------------------

class TestUpdateTrackCarSim:
    """Snapshot keys for track, car, sim should populate the properties."""

    def test_track_populated(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(track="Spa"))
        assert vm.track == "Spa"

    def test_car_populated(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(car="BMW M4 GT3"))
        assert vm.car == "BMW M4 GT3"

    def test_sim_populated(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(sim="iRacing"))
        assert vm.sim == "iRacing"

    def test_none_values_become_empty_strings(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(track=None, car=None, sim=None))
        assert vm.track == ""
        assert vm.car == ""
        assert vm.sim == ""

    def test_track_signal_fires_on_change(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(track="Monza", car="Ferrari", sim="ACC"))
        assert vm.trackChanged.call_count == 1

    def test_track_signal_skipped_when_same(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot())  # all empty
        assert vm.trackChanged.call_count == 0


# ---------------------------------------------------------------------------
# update_from_snapshot — current lap
# ---------------------------------------------------------------------------

class TestUpdateCurrentLap:
    def test_current_lap_populated(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(current_lap=7))
        assert vm.currentLap == 7

    def test_lap_signal_fires_on_change(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(current_lap=3))
        assert vm.lapChanged.call_count == 1

    def test_lap_signal_skipped_when_same(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(current_lap=0))
        assert vm.lapChanged.call_count == 0


# ---------------------------------------------------------------------------
# update_from_snapshot — live telemetry
# ---------------------------------------------------------------------------

class TestUpdateLiveTelemetry:
    def test_speed_populated(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(live={"speed_kph": 245.3}))
        assert vm.speedKph == pytest.approx(245.3)

    def test_throttle_populated(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(live={"throttle_pct": 0.85}))
        assert vm.throttlePct == pytest.approx(0.85)

    def test_brake_populated(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(live={"brake_pct": 0.45}))
        assert vm.brakePct == pytest.approx(0.45)

    def test_telemetry_signal_fires(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(live={"speed_kph": 100.0}))
        assert vm.telemetryChanged.call_count == 1

    def test_speed_history_accumulates(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(live={"speed_kph": 100.0}))
        vm.update_from_snapshot(_make_snapshot(live={"speed_kph": 120.0}))
        assert list(vm.speedHistory) == [100.0, 120.0]

    def test_speed_history_capped_at_180(self) -> None:
        vm = SessionViewModel()
        for i in range(200):
            vm.update_from_snapshot(_make_snapshot(live={"speed_kph": float(i)}))
        assert len(vm.speedHistory) == 180
        # Most recent values kept
        assert vm.speedHistory[-1] == 199.0
        assert vm.speedHistory[0] == 20.0


# ---------------------------------------------------------------------------
# update_from_snapshot — lap times / best lap detection
# ---------------------------------------------------------------------------

class TestUpdateLapTimes:
    """Lap times should be processed into formatted laps list."""

    def _three_lap_snapshot(self) -> dict:
        return _make_snapshot(lap_times=[
            {"lap": 1, "time_s": 137.834, "sectors": [], "status": "valid"},
            {"lap": 2, "time_s": 135.200, "sectors": [], "status": "valid"},
            {"lap": 3, "time_s": 136.500, "sectors": [], "status": "valid"},
        ])

    def test_laps_populated(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(self._three_lap_snapshot())
        assert len(vm.laps) == 3

    def test_lap_has_required_keys(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(self._three_lap_snapshot())
        lap = vm.laps[0]
        for key in ("lap", "time", "time_s", "delta", "status", "is_best"):
            assert key in lap, f"Missing key: {key}"

    def test_best_lap_detected(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(self._three_lap_snapshot())
        # Lap 2 has lowest time_s (135.200)
        assert vm.bestLapNumber == 2
        assert vm.bestLapTime == _format_time(135.200)

    def test_best_lap_marked_in_list(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(self._three_lap_snapshot())
        best_flags = [lap["is_best"] for lap in vm.laps]
        assert best_flags == [False, True, False]

    def test_delta_relative_to_best(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(self._three_lap_snapshot())
        # Lap 2 is best -> delta "BEST"
        assert vm.laps[1]["delta"] == "BEST"
        # Lap 1: 137.834 - 135.200 = +2.634
        assert vm.laps[0]["delta"] == "+2.634"

    def test_last_lap_time_is_most_recent(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(self._three_lap_snapshot())
        assert vm.lastLapTime == _format_time(136.500)

    def test_last_lap_delta(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(self._three_lap_snapshot())
        # Last lap (3): 136.500 - 135.200 = +1.300
        assert vm.lastLapDelta == "+1.300"

    def test_invalid_laps_excluded_from_best(self) -> None:
        vm = SessionViewModel()
        snap = _make_snapshot(lap_times=[
            {"lap": 1, "time_s": 100.0, "sectors": [], "status": "invalid"},
            {"lap": 2, "time_s": 140.0, "sectors": [], "status": "valid"},
            {"lap": 3, "time_s": 138.0, "sectors": [], "status": "valid"},
        ])
        vm.update_from_snapshot(snap)
        # Invalid lap 1 should be excluded from best calculation
        assert vm.bestLapNumber == 3
        assert vm.bestLapTime == _format_time(138.0)

    def test_laps_changed_signal_fires(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(self._three_lap_snapshot())
        assert vm.lapsChanged.call_count == 1

    def test_times_changed_signal_fires(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(self._three_lap_snapshot())
        assert vm.timesChanged.call_count == 1


# ---------------------------------------------------------------------------
# Consistency calculation
# ---------------------------------------------------------------------------

class TestConsistency:
    """Consistency: (1 - stdev/mean) * 100 for 2+ valid laps."""

    def test_single_lap_returns_100(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(lap_times=[
            {"lap": 1, "time_s": 90.0, "sectors": [], "status": "valid"},
        ]))
        assert vm.consistencyPct == 100.0

    def test_no_laps_returns_100(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(lap_times=[]))
        assert vm.consistencyPct == 100.0

    def test_identical_laps_returns_100(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(lap_times=[
            {"lap": 1, "time_s": 90.0, "sectors": [], "status": "valid"},
            {"lap": 2, "time_s": 90.0, "sectors": [], "status": "valid"},
        ]))
        assert vm.consistencyPct == 100.0
        assert vm.consistencySigma == "\u03c3 0.00s"

    def test_varied_laps(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(lap_times=[
            {"lap": 1, "time_s": 90.0, "sectors": [], "status": "valid"},
            {"lap": 2, "time_s": 92.0, "sectors": [], "status": "valid"},
            {"lap": 3, "time_s": 91.0, "sectors": [], "status": "valid"},
        ]))
        # mean = 91.0, stdev ~ 0.8165
        # consistency ~ (1 - 0.8165/91.0)*100 ~ 99.1%
        assert 98.0 < vm.consistencyPct < 100.0
        assert vm.consistencySigma.startswith("\u03c3 ")
        assert vm.consistencySigma.endswith("s")

    def test_invalid_laps_excluded_from_consistency(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(lap_times=[
            {"lap": 1, "time_s": 90.0, "sectors": [], "status": "valid"},
            {"lap": 2, "time_s": 500.0, "sectors": [], "status": "invalid"},
        ]))
        # Only one valid lap -> 100%
        assert vm.consistencyPct == 100.0


# ---------------------------------------------------------------------------
# clear()
# ---------------------------------------------------------------------------

class TestClear:
    """clear() should reset all state to defaults."""

    def test_clear_resets_track(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(track="Spa", sim="iRacing", car="BMW"))
        vm.clear()
        assert vm.track == ""
        assert vm.car == ""
        assert vm.sim == ""

    def test_clear_resets_lap(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(current_lap=5))
        vm.clear()
        assert vm.currentLap == 0

    def test_clear_resets_times(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(lap_times=[
            {"lap": 1, "time_s": 90.0, "sectors": [], "status": "valid"},
        ]))
        vm.clear()
        assert vm.lastLapTime == "\u2014"
        assert vm.bestLapTime == "\u2014"
        assert vm.bestLapNumber == 0
        assert vm.lastLapDelta == ""
        assert vm.consistencyPct == 100.0
        assert vm.consistencySigma == ""

    def test_clear_resets_telemetry(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(live={"speed_kph": 200.0}))
        vm.clear()
        assert vm.speedKph == 0.0
        assert vm.throttlePct == 0.0
        assert vm.brakePct == 0.0
        assert list(vm.speedHistory) == []

    def test_clear_resets_laps_list(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(lap_times=[
            {"lap": 1, "time_s": 90.0, "sectors": [], "status": "valid"},
        ]))
        vm.clear()
        assert vm.laps == []

    def test_clear_emits_all_signals(self) -> None:
        vm = SessionViewModel()
        vm.update_from_snapshot(_make_snapshot(
            track="Spa", sim="iRacing", car="BMW",
            current_lap=3,
            live={"speed_kph": 100.0},
            lap_times=[{"lap": 1, "time_s": 90.0, "sectors": [], "status": "valid"}],
        ))
        # Reset counters by accessing signals (creating fresh instances won't
        # work because they're cached).  Instead, note counts before clear.
        pre_track = vm.trackChanged.call_count
        pre_lap = vm.lapChanged.call_count
        pre_times = vm.timesChanged.call_count
        pre_telemetry = vm.telemetryChanged.call_count
        pre_laps = vm.lapsChanged.call_count

        vm.clear()

        assert vm.trackChanged.call_count > pre_track
        assert vm.lapChanged.call_count > pre_lap
        assert vm.timesChanged.call_count > pre_times
        assert vm.telemetryChanged.call_count > pre_telemetry
        assert vm.lapsChanged.call_count > pre_laps
