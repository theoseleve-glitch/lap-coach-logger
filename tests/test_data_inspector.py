"""Tests for data mode channel inspector."""
from __future__ import annotations

from lap_coach_logger.data_mode.inspector import (
    ChannelStatus,
    InspectionReport,
    inspect_channels,
    inspect_live_metric,
)
from lap_coach_logger.core.metric_state import MetricState


def _make_snapshots(n: int, missing_channels: set[str] | None = None) -> list[dict]:
    """Generate n fake telemetry snapshots."""
    missing = missing_channels or set()
    snapshots = []
    for i in range(n):
        snap = {
            "speed_kph": 200.0 + i,
            "throttle_pct": 0.8,
            "brake_pct": 0.0,
            "steering_deg": 2.0,
            "gear": 4,
            "rpm": 7000.0,
            "fuel_level": 50.0 - i * 0.1,
            "fuel_capacity": 120.0,
            "lap_number": 1,
            "lap_distance_m": 100.0 * i,
            "lap_dist_pct": i / max(n, 1),
            "tyre_temp_lf": 85.0,
            "tyre_temp_rf": 86.0,
            "tyre_temp_lr": 84.0,
            "tyre_temp_rr": 85.5,
            "brake_temp_lf": 400.0,
            "brake_temp_rf": 410.0,
            "brake_temp_lr": 390.0,
            "brake_temp_rr": 395.0,
            "track_temp_c": 30.0,
            "air_temp_c": 25.0,
            "position": 1,
            "num_cars": 20,
            "world_pos_x": float(i),
            "world_pos_y": 0.0,
            "world_pos_z": float(i * 2),
            "lat_accel_g": 0.5,
            "long_accel_g": 0.3,
            "is_in_pits": False,
            "is_on_track": True,
            "session_time_s": float(i),
            "track_name": "Monza",
            "car_name": "GT3",
            "session_type": "practice",
        }
        for ch in missing:
            snap[ch] = None
        snapshots.append(snap)
    return snapshots


class TestInspectChannels:

    def test_all_present_channels_are_available(self):
        report = inspect_channels(_make_snapshots(50), sample_rate_hz=10.0)
        speed = next(c for c in report.channels if c.name == "speed_kph")
        assert speed.state == MetricState.AVAILABLE
        assert speed.null_ratio == 0.0
        assert speed.warning is None

    def test_missing_channels_are_unavailable(self):
        # Generate snapshots where brake_temp_lf is explicitly absent
        report = inspect_channels(
            _make_snapshots(50, missing_channels={"brake_temp_lf"}),
            sample_rate_hz=10.0,
        )
        brake = next(c for c in report.channels if c.name == "brake_temp_lf")
        assert brake.state == MetricState.UNAVAILABLE

    def test_intermittent_channels_are_estimated(self):
        snaps = _make_snapshots(100)
        # Make fuel_level None for 30% of snapshots
        for i in range(30):
            snaps[i]["fuel_level"] = None
        report = inspect_channels(snaps, sample_rate_hz=10.0)
        fuel = next(c for c in report.channels if c.name == "fuel_level")
        assert fuel.state == MetricState.ESTIMATED

    def test_overall_quality_good(self):
        report = inspect_channels(_make_snapshots(50), sample_rate_hz=10.0)
        assert report.overall_quality in ("good", "degraded")

    def test_low_sample_rate_warning(self):
        report = inspect_channels(_make_snapshots(50), sample_rate_hz=2.0)
        assert any("sample rate" in w.lower() for w in report.warnings)

    def test_limited_data_warning(self):
        report = inspect_channels(_make_snapshots(10), sample_rate_hz=10.0)
        assert any("limited data" in w.lower() for w in report.warnings)

    def test_report_to_dict(self):
        report = inspect_channels(_make_snapshots(20), sample_rate_hz=10.0)
        d = report.to_dict()
        assert "channels" in d
        assert "overall_quality" in d
        assert isinstance(d["channels"], list)


class TestInspectLiveMetric:

    def test_available_metric(self):
        status = inspect_live_metric("speed_kph", 200.0)
        assert status.state == MetricState.AVAILABLE

    def test_unavailable_metric(self):
        status = inspect_live_metric("brake_temp_lf", None)
        assert status.state == MetricState.UNAVAILABLE

    def test_with_history(self):
        history = [200.0, None, 201.0, None, 202.0]  # 40% null
        status = inspect_live_metric("speed_kph", 203.0, history=history)
        assert status.null_ratio > 0.3
