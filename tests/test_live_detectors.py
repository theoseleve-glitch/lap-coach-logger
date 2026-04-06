"""Tests for live coaching detectors."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.core.detector_models import CoachingNote, DetectorConfig, DetectorType
from lap_coach_logger.core.live_detectors import (
    DetectorManager,
    OversteerDetector,
    UndersteerDetector,
    BrakePointDetector,
    ApexSpeedDetector,
)


def _sample(**kw) -> TelemetrySample:
    """Helper to build a TelemetrySample with only the fields we care about."""
    return TelemetrySample(**kw)


# ── Oversteer ──────────────────────────────────────────────────────


def test_oversteer_fires_on_yaw_deviation():
    """Large yaw change at high speed triggers oversteer note."""
    cfg = DetectorConfig(oversteer_yaw_rate_threshold_dps=15.0, oversteer_min_speed_kph=40.0)
    det = OversteerDetector(cfg)

    # First sample seeds the previous state
    det.check(_sample(yaw_deg=0.0, session_time_s=0.0, speed_kph=80.0, lat_accel_g=0.5, lap_dist_pct=0.10))

    # Second sample: huge yaw change in short time -> high yaw rate
    # dt=0.016s (~60Hz), dyaw=10 deg -> yaw_rate = 625 deg/s, well above expected
    note = det.check(_sample(yaw_deg=10.0, session_time_s=0.016, speed_kph=80.0, lat_accel_g=0.5, lap_dist_pct=0.11))

    assert note is not None
    assert note.detector == DetectorType.OVERSTEER
    assert "Oversteer" in note.message
    assert note.severity == "warning"


def test_oversteer_no_fire_at_low_speed():
    """Same yaw deviation at low speed should NOT fire."""
    cfg = DetectorConfig(oversteer_yaw_rate_threshold_dps=15.0, oversteer_min_speed_kph=40.0)
    det = OversteerDetector(cfg)

    det.check(_sample(yaw_deg=0.0, session_time_s=0.0, speed_kph=20.0, lat_accel_g=0.5, lap_dist_pct=0.10))
    note = det.check(_sample(yaw_deg=10.0, session_time_s=0.016, speed_kph=20.0, lat_accel_g=0.5, lap_dist_pct=0.11))

    assert note is None


# ── Understeer ─────────────────────────────────────────────────────


def test_understeer_fires_on_steering_increase_lat_g_drop():
    """Steering increases but lat_g drops -> understeer detected."""
    cfg = DetectorConfig(
        understeer_steering_increase_deg=5.0,
        understeer_lat_g_drop_threshold=0.15,
        understeer_min_speed_kph=30.0,
        cooldown_dist_pct=0.01,
    )
    det = UndersteerDetector(cfg)

    # Feed 5 samples: steering 10->22 deg, lat_g 0.9->0.7 (drop of 0.2 > 0.15)
    samples = [
        (0.20, 10.0, 0.90),
        (0.21, 13.0, 0.88),
        (0.22, 16.0, 0.85),
        (0.23, 19.0, 0.78),
        (0.24, 22.0, 0.70),
    ]
    note = None
    for dist, steer, lat in samples:
        note = det.check(_sample(steering_deg=steer, lat_accel_g=lat, speed_kph=80.0, lap_dist_pct=dist))

    assert note is not None
    assert note.detector == DetectorType.UNDERSTEER
    assert "Understeer" in note.message


# ── Brake point ────────────────────────────────────────────────────


def test_brake_point_late_detection():
    """Braking 15m past reference triggers LATE_BRAKE."""
    cfg = DetectorConfig(brake_point_margin_m=10.0, brake_threshold_pct=0.1)
    det = BrakePointDetector(cfg)
    det.set_reference({1: 100.0})  # corner 1 brake at 100m

    # Not braking yet
    det.check(_sample(brake_pct=0.0, lap_distance_m=90.0, lap_dist_pct=0.30))
    # Start braking at 115m (15m late)
    note = det.check(_sample(brake_pct=0.8, lap_distance_m=115.0, lap_dist_pct=0.35))

    assert note is not None
    assert note.detector == DetectorType.LATE_BRAKE
    assert note.value == 15.0
    assert "late" in note.message.lower()


def test_brake_point_early_detection():
    """Braking 15m before reference triggers EARLY_BRAKE."""
    cfg = DetectorConfig(brake_point_margin_m=10.0, brake_threshold_pct=0.1)
    det = BrakePointDetector(cfg)
    det.set_reference({1: 100.0})

    det.check(_sample(brake_pct=0.0, lap_distance_m=80.0, lap_dist_pct=0.25))
    note = det.check(_sample(brake_pct=0.8, lap_distance_m=85.0, lap_dist_pct=0.28))

    assert note is not None
    assert note.detector == DetectorType.EARLY_BRAKE
    assert note.value == -15.0
    assert "early" in note.message.lower()


# ── Apex speed ─────────────────────────────────────────────────────


def test_apex_speed_low_detection():
    """Speed below reference apex triggers LOW_APEX_SPEED."""
    cfg = DetectorConfig(apex_speed_margin_kph=3.0)
    det = ApexSpeedDetector(cfg)
    det.set_reference({0.30: 90.0})  # apex at 30%, best speed 90 kph

    note = det.check(_sample(speed_kph=84.0, lap_dist_pct=0.30))

    assert note is not None
    assert note.detector == DetectorType.LOW_APEX_SPEED
    assert note.value == 6.0
    assert "Apex" in note.message


# ── DetectorManager ────────────────────────────────────────────────


def test_detector_manager_collects_notes():
    """DetectorManager returns notes from multiple detectors in one check."""
    cfg = DetectorConfig(
        apex_speed_margin_kph=3.0,
        brake_point_margin_m=10.0,
        brake_threshold_pct=0.1,
    )
    mgr = DetectorManager(cfg)
    mgr.set_best_lap_reference(
        brake_points={1: 100.0},
        apex_speeds={0.50: 95.0},
    )

    # Feed a sample that triggers apex speed (at apex dist_pct, slow)
    notes = mgr.check(_sample(
        speed_kph=85.0,
        lap_dist_pct=0.50,
        lap_distance_m=200.0,
        brake_pct=0.0,
        steering_deg=0.0,
        lat_accel_g=0.0,
        yaw_deg=0.0,
        session_time_s=1.0,
    ))

    types = {n.detector for n in notes}
    assert DetectorType.LOW_APEX_SPEED in types


# ── Cooldown ───────────────────────────────────────────────────────


def test_cooldown_prevents_rapid_fire():
    """Same condition within cooldown_dist_pct fires only once."""
    cfg = DetectorConfig(apex_speed_margin_kph=3.0, cooldown_dist_pct=0.05)
    det = ApexSpeedDetector(cfg)
    det.set_reference({0.30: 90.0})

    # First check fires
    note1 = det.check(_sample(speed_kph=84.0, lap_dist_pct=0.300))
    assert note1 is not None

    # Second check at dist 0.305 (within 0.05 cooldown) should not fire
    note2 = det.check(_sample(speed_kph=84.0, lap_dist_pct=0.305))
    assert note2 is None
