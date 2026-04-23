import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pytest
from lap_coach_logger.core.ghost_reference import GhostReference, GhostPoint
from lap_coach_logger.core.ghost_tracker import GhostTracker, GhostDelta
from lap_coach_logger.core.schema import TelemetrySample


@pytest.fixture
def ghost_json(tmp_path):
    data = {
        "version": 1,
        "track_name": "Test Track",
        "car_name": "Test Car",
        "theoretical_lap_time_s": 60.0,
        "n_points": 100,
        "distance_pct": np.linspace(0, 1.0, 100).tolist(),
        "speed_kph": (100 + 50 * np.sin(np.linspace(0, 2 * np.pi, 100))).tolist(),
        "throttle_pct": np.clip(
            np.cos(np.linspace(0, 2 * np.pi, 100)), 0, 1
        ).tolist(),
        "brake_pct": np.clip(
            -np.cos(np.linspace(0, 2 * np.pi, 100)), 0, 1
        ).tolist(),
        "steering_deg": (30 * np.sin(np.linspace(0, 4 * np.pi, 100))).tolist(),
    }
    path = tmp_path / "theoretical_ghost.json"
    path.write_text(json.dumps(data))
    return path


def test_load_ghost(ghost_json):
    ref = GhostReference(ghost_json)
    assert ref.loaded is True
    assert ref.track_name == "Test Track"
    assert ref.car_name == "Test Car"
    assert ref.theoretical_lap_time_s == 60.0


def test_lookup_interpolates(ghost_json):
    ref = GhostReference(ghost_json)
    pt = ref.lookup(0.5)
    assert pt is not None
    assert isinstance(pt, GhostPoint)
    # At dist 0.5, sin(pi) ~ 0, so speed ~ 100
    assert abs(pt.speed_kph - 100.0) < 5.0
    assert 0.0 <= pt.cumulative_time_s <= 60.0


def test_lookup_at_boundaries(ghost_json):
    ref = GhostReference(ghost_json)
    pt0 = ref.lookup(0.0)
    assert pt0 is not None
    pt1 = ref.lookup(1.0)
    assert pt1 is not None
    # Out of range returns None
    assert ref.lookup(-0.1) is None


def test_tracker_computes_delta(ghost_json):
    ref = GhostReference(ghost_json)
    tracker = GhostTracker(ref)
    # Ghost speed at dist 0.1: 100 + 50*sin(0.2*pi) ~ 129.4
    # We drive at 100 kph -> delta should be positive (we're slow)
    for i, d in enumerate([0.1, 0.2, 0.3]):
        sample = TelemetrySample(
            speed_kph=100.0,
            throttle_pct=0.8,
            brake_pct=0.0,
            steering_deg=0.0,
            lap_dist_pct=d,
            session_time_s=float(i) * 2.0,
        )
        delta = tracker.update(sample)
    assert delta is not None
    assert isinstance(delta, GhostDelta)
    # Ghost speed at 0.3 > 100, so speed_delta should be positive
    assert delta.speed_delta_kph > 0


def test_tracker_accumulates_time(ghost_json):
    ref = GhostReference(ghost_json)
    tracker = GhostTracker(ref)
    # Feed 10 samples with actual time slower than ghost
    for i in range(10):
        d = 0.05 + i * 0.05  # 0.05 to 0.50
        # Use a larger session_time to simulate being slower
        sample = TelemetrySample(
            speed_kph=80.0,
            throttle_pct=0.5,
            brake_pct=0.0,
            steering_deg=0.0,
            lap_dist_pct=d,
            session_time_s=float(i) * 4.0,  # generous time steps
        )
        tracker.update(sample)
    # If actual is slower, cumulative_delta should be positive
    assert tracker.cumulative_delta_s > 0


def test_tracker_resets_on_new_lap(ghost_json):
    ref = GhostReference(ghost_json)
    tracker = GhostTracker(ref)
    # Build up some delta
    for i, d in enumerate([0.7, 0.8, 0.9]):
        sample = TelemetrySample(
            speed_kph=80.0,
            lap_dist_pct=d,
            session_time_s=float(i) * 3.0,
        )
        tracker.update(sample)
    old_delta = tracker.cumulative_delta_s
    # Simulate lap boundary: dist drops from 0.9 to 0.05
    sample = TelemetrySample(
        speed_kph=80.0,
        lap_dist_pct=0.05,
        session_time_s=10.0,
    )
    tracker.update(sample)
    # After reset, cumulative_delta should be 0
    assert tracker.cumulative_delta_s == 0.0


def test_unloaded_returns_none():
    ref = GhostReference()
    assert ref.loaded is False
    assert ref.lookup(0.5) is None
    tracker = GhostTracker(ref)
    sample = TelemetrySample(speed_kph=100.0, lap_dist_pct=0.5, session_time_s=1.0)
    assert tracker.update(sample) is None


def test_tracker_with_none_fields(ghost_json):
    ref = GhostReference(ghost_json)
    tracker = GhostTracker(ref)
    # TelemetrySample with None speed/throttle/brake/steering
    sample = TelemetrySample(
        speed_kph=None,
        throttle_pct=None,
        brake_pct=None,
        steering_deg=None,
        lap_dist_pct=0.5,
        session_time_s=1.0,
    )
    delta = tracker.update(sample)
    assert delta is not None
    # With None fields treated as 0, deltas should equal theoretical values
    assert delta.speed_delta_kph == delta.theoretical_speed_kph
    assert delta.throttle_delta_pct == delta.theoretical_throttle_pct
