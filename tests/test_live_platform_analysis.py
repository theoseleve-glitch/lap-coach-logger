from __future__ import annotations

from lap_coach_logger.core.live_platform_analysis import LivePlatformAnalysisTracker
from lap_coach_logger.core.schema import TelemetrySample


def _sample(
    *,
    session_time_s: float,
    speed_kph: float = 160.0,
    throttle_pct: float = 0.0,
    brake_pct: float = 0.0,
    steering_deg: float = 0.0,
    lat_accel_g: float = 0.0,
    long_accel_g: float = 0.0,
    pitch: float = 0.0,
    roll: float = 0.0,
) -> TelemetrySample:
    return TelemetrySample(
        sim="test_sim",
        session_uid="session-1",
        session_time_s=session_time_s,
        speed_kph=speed_kph,
        throttle_pct=throttle_pct,
        brake_pct=brake_pct,
        steering_deg=steering_deg,
        lat_accel_g=lat_accel_g,
        long_accel_g=long_accel_g,
        pitch=pitch,
        roll=roll,
    )


def test_platform_analysis_detects_front_platform_risk() -> None:
    tracker = LivePlatformAnalysisTracker()

    for index in range(16):
        tracker.push_sample(
            _sample(
                session_time_s=index * 0.5,
                speed_kph=192.0,
                throttle_pct=0.42,
                brake_pct=0.10,
                steering_deg=30.0,
                lat_accel_g=0.40,
                long_accel_g=0.12,
                pitch=8.4,
                roll=5.2,
            ),
            dashboard_state={
                "ride_height_front": 62.0 if index < 6 else 48.0,
                "ride_height_rear": 92.0 if index < 6 else 66.0,
                "suspension_travel_lf": 8.0 if index < 6 else 15.0,
                "suspension_travel_rf": 8.5 if index < 6 else 15.2,
                "suspension_travel_lr": 6.0 if index < 6 else 10.0,
                "suspension_travel_rr": 6.2 if index < 6 else 10.1,
            },
        )

    snap = tracker.snapshot()
    rows = snap["rows"]
    titles = {item["title"] for item in snap["flags"]}

    assert rows["rake_trend"]["label"] == "Flattening"
    assert rows["ride_height_compression"]["label"] == "Bottoming Risk"
    assert rows["chassis_balance"]["label"] == "Understeer Trend"
    assert rows["front_rear_limitation"]["label"] == "Front Limited"
    assert rows["aero_balance"]["label"] == "Front Aero Weak"
    assert "Bottoming risk" in titles
    assert "Aero balance suspicion" in titles


def test_platform_analysis_detects_roll_asymmetry_and_rear_limit() -> None:
    tracker = LivePlatformAnalysisTracker()

    for index in range(8):
        tracker.push_sample(
            _sample(
                session_time_s=index * 0.4,
                speed_kph=118.0,
                throttle_pct=0.84,
                brake_pct=0.02,
                steering_deg=8.0,
                lat_accel_g=1.02,
                long_accel_g=0.40,
                pitch=1.2,
                roll=4.2,
            ),
        )
    for index in range(8):
        tracker.push_sample(
            _sample(
                session_time_s=3.2 + index * 0.4,
                speed_kph=116.0,
                throttle_pct=0.86,
                brake_pct=0.02,
                steering_deg=-8.0,
                lat_accel_g=-1.00,
                long_accel_g=0.42,
                pitch=1.1,
                roll=7.4,
            ),
        )

    snap = tracker.snapshot()
    rows = snap["rows"]
    titles = {item["title"] for item in snap["flags"]}

    assert rows["chassis_balance"]["label"] == "Oversteer Trend"
    assert rows["front_rear_limitation"]["label"] == "Rear Limited"
    assert rows["roll_asymmetry"]["label"] == "Asymmetric"
    assert "Roll asymmetry" in titles
    assert "Axle limitation" in titles
