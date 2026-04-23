"""Tests for tire_model module — focused on bugs #3 and #4."""

from lap_coach_logger.core.tire_model import TireDegradationTracker, TireState


def _normal_temps() -> tuple[float, float, float, float]:
    """Temps within optimal range (75-100C)."""
    return (85.0, 87.0, 83.0, 86.0)


def _hot_temps() -> tuple[float, float, float, float]:
    """Temps above optimal range -> higher wear."""
    return (115.0, 118.0, 112.0, 116.0)


def _push_full_lap(tracker: TireDegradationTracker, lap: int,
                   temps: tuple[float, float, float, float], samples: int = 10) -> None:
    """Push `samples` identical temp readings for a lap, then trigger finalization."""
    for _ in range(samples):
        tracker.push_sample(temps, lap)
    # Finalize by starting next lap
    tracker.push_sample(temps, lap + 1)


class TestCurrentTempsInitialization:
    """Bug #3: _current_temps was conditionally created via hasattr."""

    def test_current_temps_exists_at_init(self):
        tracker = TireDegradationTracker()
        assert hasattr(tracker, "_current_temps")
        assert tracker._current_temps == []

    def test_current_temps_exists_after_reset(self):
        tracker = TireDegradationTracker()
        tracker.push_sample(_normal_temps(), 1)
        tracker.reset()
        assert hasattr(tracker, "_current_temps")
        assert tracker._current_temps == []

    def test_push_sample_on_lap_zero_no_crash(self):
        tracker = TireDegradationTracker()
        # Lap 0 was problematic because _current_temps was only created
        # when lap_number > 0 and different from _last_lap
        tracker.push_sample(_normal_temps(), 0)
        tracker.push_sample(_normal_temps(), 0)
        assert tracker.state.lap_count == 0  # lap 0 doesn't finalize


class TestAccumulatedWear:
    """Bug #4: grip was retroactively recalculated using only current wear rate."""

    def test_normal_laps_accumulate_linearly(self):
        tracker = TireDegradationTracker()
        # 5 laps of normal temps -> each lap adds ~2% base wear
        for lap in range(1, 6):
            _push_full_lap(tracker, lap, _normal_temps())

        state = tracker.state
        assert state.lap_count == 5
        # 5 laps * ~2% = ~10% wear -> grip ~90%
        assert 88.0 <= state.grip_pct <= 92.0

    def test_hot_lap_does_not_retroactively_increase_prior_wear(self):
        tracker = TireDegradationTracker()

        # 5 normal-temp laps
        for lap in range(1, 6):
            _push_full_lap(tracker, lap, _normal_temps())
        grip_after_5_normal = tracker.state.grip_pct

        # 1 overheated lap
        _push_full_lap(tracker, 6, _hot_temps())
        grip_after_hot = tracker.state.grip_pct

        # The hot lap should add MORE wear than a normal lap
        hot_lap_wear = grip_after_5_normal - grip_after_hot
        assert hot_lap_wear > 2.0  # significantly more than the ~2% base

        # But total grip should NOT be recalculated as if ALL 6 laps were hot
        # (Old bug: grip = 100 - 6 * hot_wear, which would be much lower)
        # With accumulation: grip = 100 - (5 * ~2) - (1 * hot_wear)
        assert grip_after_hot > 70.0  # should still be "good" condition

    def test_grip_never_negative(self):
        tracker = TireDegradationTracker()
        # Many hot laps to drive grip to zero
        for lap in range(1, 60):
            _push_full_lap(tracker, lap, _hot_temps())
        assert tracker.state.grip_pct == 0.0

    def test_condition_transitions(self):
        tracker = TireDegradationTracker()

        # After a few laps, should be "good"
        for lap in range(1, 6):
            _push_full_lap(tracker, lap, _normal_temps())
        assert tracker.state.condition == "good"

        # After many laps, should transition to "worn"
        for lap in range(6, 18):
            _push_full_lap(tracker, lap, _normal_temps())
        assert tracker.state.condition in ("good", "worn")

        # After very many laps, should become "critical"
        for lap in range(18, 35):
            _push_full_lap(tracker, lap, _normal_temps())
        assert tracker.state.condition in ("worn", "critical")

    def test_wear_rate_reflects_current_lap_only(self):
        tracker = TireDegradationTracker()

        _push_full_lap(tracker, 1, _normal_temps())
        normal_wear_rate = tracker.state.wear_rate

        _push_full_lap(tracker, 2, _hot_temps())
        hot_wear_rate = tracker.state.wear_rate

        assert hot_wear_rate > normal_wear_rate

    def test_laps_remaining_based_on_accumulated_grip(self):
        tracker = TireDegradationTracker()
        _push_full_lap(tracker, 1, _normal_temps())

        state = tracker.state
        # With ~98% grip, ~2% wear rate, threshold at 40%:
        # remaining = (98 - 40) / 2 = ~29 laps
        assert state.laps_remaining > 20

    def test_reset_clears_accumulated_wear(self):
        tracker = TireDegradationTracker()
        for lap in range(1, 10):
            _push_full_lap(tracker, lap, _normal_temps())
        assert tracker.state.grip_pct < 100.0

        tracker.reset()
        assert tracker.state.grip_pct == 100.0
        assert tracker.state.lap_count == 0
        assert tracker.state.wear_rate == 0.0

    def test_to_dict_snapshot(self):
        tracker = TireDegradationTracker()
        _push_full_lap(tracker, 1, _normal_temps())
        d = tracker.state.to_dict()
        assert "grip_pct" in d
        assert "wear_rate" in d
        assert "laps_remaining" in d
        assert d["lap_count"] == 1
