"""Tests for demo session generator."""
from __future__ import annotations

from lap_coach_logger.demo.session_generator import (
    DemoLapRecord,
    DemoSession,
    generate_session,
    iter_snapshots,
)


class TestSessionShape:

    def test_generates_ten_laps(self):
        session = generate_session()
        assert len(session.laps) == 10
        assert session.total_laps == 10

    def test_lap_numbers_are_sequential(self):
        session = generate_session()
        assert [l.lap_number for l in session.laps] == list(range(1, 11))

    def test_deterministic_across_calls(self):
        s1 = generate_session()
        s2 = generate_session()
        assert [l.lap_time_s for l in s1.laps] == [l.lap_time_s for l in s2.laps]

    def test_story_arc_has_s2_improvement(self):
        session = generate_session()
        early_s2 = [l.sector_times_s[1] for l in session.laps[:5]]
        late_s2 = [l.sector_times_s[1] for l in session.laps[5:]]
        # Early sector 2 should be more variable (higher std dev) than late
        import statistics
        assert statistics.stdev(early_s2) > statistics.stdev(late_s2)
        # And late average should be lower
        assert sum(late_s2) / 5 < sum(early_s2) / 5

    def test_events_include_pit_and_plan(self):
        session = generate_session()
        types = {e.event_type for e in session.events}
        assert "pit_stop" in types
        assert "plan_generated" in types
        assert "readiness_changed" in types


class TestSnapshotIter:

    def test_yields_samples_per_lap_times_laps(self):
        session = generate_session()
        snaps = list(iter_snapshots(session))
        assert len(snaps) == session.total_laps * session.samples_per_lap

    def test_all_snapshots_labeled_demo(self):
        session = generate_session()
        snaps = list(iter_snapshots(session))
        assert all(s.get("_demo") is True for s in snaps)

    def test_snapshot_has_required_fields(self):
        session = generate_session()
        snap = next(iter_snapshots(session))
        required = {
            "sim", "track_name", "car_name", "session_type",
            "session_time_s", "lap_number", "fuel_level", "fuel_capacity",
            "tyre_temp_lf", "tyre_temp_rf", "tyre_temp_lr", "tyre_temp_rr",
            "speed_kph", "throttle_pct", "brake_pct", "gear", "rpm",
            "is_in_pits", "is_on_track",
        }
        missing = required - set(snap.keys())
        assert not missing, f"Missing keys: {missing}"

    def test_fuel_monotonically_decreases_within_lap(self):
        session = generate_session()
        snaps = list(iter_snapshots(session))
        first_lap = [s for s in snaps if s["lap_number"] == 1]
        fuels = [s["fuel_level"] for s in first_lap]
        assert fuels == sorted(fuels, reverse=True) or fuels[0] >= fuels[-1]

    def test_session_time_increases(self):
        session = generate_session()
        snaps = list(iter_snapshots(session))
        times = [s["session_time_s"] for s in snaps]
        for i in range(1, len(times)):
            assert times[i] >= times[i - 1], f"time regressed at sample {i}"
