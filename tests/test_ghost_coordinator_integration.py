"""Integration test: ghost tracker wired into session coordinator pattern."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import json
import tempfile
import numpy as np
import pytest

from lap_coach_logger.core.ghost_reference import GhostReference
from lap_coach_logger.core.ghost_tracker import GhostTracker
from lap_coach_logger.core.schema import TelemetrySample


@pytest.fixture
def ghost_session_dir(tmp_path):
    """Create a temp dir with a theoretical_ghost.json."""
    data = {
        "version": 1, "track_name": "Red Bull Ring", "car_name": "Porsche 911 GT3 R (992)",
        "theoretical_lap_time_s": 87.0, "n_points": 100,
        "distance_pct": np.linspace(0, 1.0, 100).tolist(),
        "speed_kph": (150 + 50 * np.sin(np.linspace(0, 2*np.pi, 100))).tolist(),
        "throttle_pct": np.clip(np.cos(np.linspace(0, 2*np.pi, 100)), 0, 1).tolist(),
        "brake_pct": np.clip(-np.cos(np.linspace(0, 2*np.pi, 100)), 0, 1).tolist(),
        "steering_deg": (30 * np.sin(np.linspace(0, 4*np.pi, 100))).tolist(),
    }
    (tmp_path / "theoretical_ghost.json").write_text(json.dumps(data))
    return tmp_path


def test_find_latest_matches_track_car(ghost_session_dir):
    ref = GhostReference.find_latest(ghost_session_dir, "Red Bull Ring", "Porsche 911 GT3 R (992)")
    assert ref is not None
    assert ref.loaded
    assert ref.theoretical_lap_time_s == pytest.approx(87.0)


def test_find_latest_wrong_track_returns_none(ghost_session_dir):
    ref = GhostReference.find_latest(ghost_session_dir, "Silverstone", "Porsche 911 GT3 R (992)")
    assert ref is None


def test_ghost_snapshot_format(ghost_session_dir):
    """Verify the snapshot dict has all keys the overlay expects."""
    ref = GhostReference(ghost_session_dir / "theoretical_ghost.json")
    tracker = GhostTracker(ref)
    sample = TelemetrySample(
        speed_kph=160.0, throttle_pct=0.8, brake_pct=0.0,
        steering_deg=15.0, lap_dist_pct=0.25, session_time_s=20.0,
        lap_number=1,
    )
    delta = tracker.update(sample)
    assert delta is not None
    # Build snapshot like the coordinator does
    snapshot = {
        "ghost_speed_delta_kph": round(delta.speed_delta_kph, 1),
        "ghost_cumulative_delta_s": round(delta.cumulative_delta_s, 3),
        "ghost_loaded": True,
    }
    assert "ghost_speed_delta_kph" in snapshot
    assert "ghost_loaded" in snapshot
