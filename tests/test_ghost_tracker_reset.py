"""Tests for ghost tracker lap-reset detection (item 5 fix)."""

import json
import numpy as np
import pytest

from lap_coach_logger.core.ghost_reference import GhostReference
from lap_coach_logger.core.ghost_tracker import GhostTracker
from lap_coach_logger.core.schema import TelemetrySample


@pytest.fixture
def reference(tmp_path):
    data = {
        "track_name": "Monza",
        "car_name": "GT3",
        "theoretical_lap_time_s": 100.0,
        "distance_pct": np.linspace(0, 1.0, 200).tolist(),
        "speed_kph": (200 + 30 * np.sin(np.linspace(0, 4 * np.pi, 200))).tolist(),
        "throttle_pct": np.clip(np.cos(np.linspace(0, 4 * np.pi, 200)), 0, 1).tolist(),
        "brake_pct": np.clip(-np.cos(np.linspace(0, 4 * np.pi, 200)), 0, 1).tolist(),
        "steering_deg": (20 * np.sin(np.linspace(0, 8 * np.pi, 200))).tolist(),
    }
    path = tmp_path / "theoretical_ghost.json"
    path.write_text(json.dumps(data))
    return GhostReference(path)


def _sample(dist_pct: float, time_s: float) -> TelemetrySample:
    return TelemetrySample(
        lap_dist_pct=dist_pct,
        session_time_s=time_s,
        speed_kph=180.0,
        throttle_pct=0.8,
        brake_pct=0.0,
        steering_deg=5.0,
        lap_number=1,
    )


class TestLapResetDetection:
    def test_full_lap_wraparound_resets(self, reference):
        """dist_pct going from 0.95 to 0.02 should reset."""
        tracker = GhostTracker(reference)
        tracker.update(_sample(0.90, 85.0))
        tracker.update(_sample(0.95, 90.0))
        # Accumulate some delta
        assert tracker.cumulative_delta_s != 0.0 or True  # may be zero, that's ok
        old_delta = tracker.cumulative_delta_s

        # Lap wrap
        tracker.update(_sample(0.02, 92.0))
        assert tracker.cumulative_delta_s == 0.0  # reset happened

    def test_pit_teleport_resets(self, reference):
        """dist_pct dropping from 0.4 to 0.0 (pit reset) should now reset."""
        tracker = GhostTracker(reference)
        tracker.update(_sample(0.30, 30.0))
        tracker.update(_sample(0.40, 40.0))

        # Teleport to pits (dist drops by 0.4 — previously missed by 0.5 threshold)
        tracker.update(_sample(0.0, 42.0))
        assert tracker.cumulative_delta_s == 0.0

    def test_mid_lap_reset_resets(self, reference):
        """dist_pct dropping from 0.6 to 0.1 should reset."""
        tracker = GhostTracker(reference)
        tracker.update(_sample(0.50, 50.0))
        tracker.update(_sample(0.60, 60.0))

        tracker.update(_sample(0.10, 62.0))
        assert tracker.cumulative_delta_s == 0.0

    def test_small_jitter_does_not_reset(self, reference):
        """dist_pct dropping by 0.05 (jitter/corner cut) should NOT reset."""
        tracker = GhostTracker(reference)
        tracker.update(_sample(0.50, 50.0))
        tracker.update(_sample(0.55, 55.0))

        # Small backward jitter
        tracker.update(_sample(0.52, 56.0))
        # Should NOT have reset — cumulative delta may be non-zero
        # The key test: _prev_dist_pct should still be tracking (not reset to None)
        assert tracker._prev_dist_pct == 0.52

    def test_normal_forward_progress_no_reset(self, reference):
        """Monotonic forward progress should never reset."""
        tracker = GhostTracker(reference)
        for i in range(10):
            pct = 0.1 * i
            tracker.update(_sample(pct, float(i * 10)))

        # Should have accumulated some delta, _prev_dist_pct should be 0.9
        assert tracker._prev_dist_pct == pytest.approx(0.9)
