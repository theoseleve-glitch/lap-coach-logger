from __future__ import annotations

from lap_coach_logger.core.live_input_diagnostics import LiveInputDiagnosticsTracker
from lap_coach_logger.core.schema import TelemetrySample


def _sample(
    *,
    session_time_s: float,
    speed_kph: float = 120.0,
    throttle_pct: float = 0.0,
    brake_pct: float = 0.0,
    steering_deg: float = 0.0,
    lat_accel_g: float = 0.0,
    long_accel_g: float = 0.0,
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
    )


def test_input_diagnostics_flags_overlap_deadzone_and_ffb_clip() -> None:
    tracker = LiveInputDiagnosticsTracker()

    for index in range(14):
        tracker.push_sample(
            _sample(
                session_time_s=index * 0.5,
                speed_kph=135.0,
                throttle_pct=0.16,
                brake_pct=0.20,
                steering_deg=14.0,
                lat_accel_g=0.45,
                long_accel_g=-0.20,
            ),
            dashboard_state={"ffb_clip_pct": 0.99},
        )

    snap = tracker.snapshot()
    rows = snap["rows"]
    titles = {item["title"] for item in snap["flags"]}

    assert rows["pedal_overlap"]["label"] == "High"
    assert rows["deadzone"]["label"] == "Possible Deadzone"
    assert rows["ffb_clipping"]["label"] == "Detected"
    assert "Pedal overlap" in titles
    assert "Deadzone suspected" in titles
    assert "FFB clipping" in titles


def test_input_diagnostics_detects_oscillation_and_poor_inputs() -> None:
    tracker = LiveInputDiagnosticsTracker()

    for index in range(12):
        tracker.push_sample(
            _sample(
                session_time_s=index * 0.4,
                speed_kph=145.0,
                throttle_pct=1.0 if index % 2 else 0.10,
                brake_pct=0.0,
                steering_deg=8.0 if index % 2 else -8.0,
                lat_accel_g=0.05,
                long_accel_g=0.30,
            ),
        )

    for index in range(8):
        tracker.push_sample(
            _sample(
                session_time_s=5.0 + index * 0.4,
                speed_kph=105.0,
                throttle_pct=1.0 if index % 2 else 0.10,
                brake_pct=0.95 if index % 2 else 0.05,
                steering_deg=20.0 if index % 2 else -20.0,
                lat_accel_g=0.06,
                long_accel_g=0.42,
            ),
        )

    snap = tracker.snapshot()
    rows = snap["rows"]
    titles = {item["title"] for item in snap["flags"]}

    assert rows["brake_trace"]["label"] == "Abrupt"
    assert rows["throttle_modulation"]["label"] == "Aggressive"
    assert rows["wheel_oscillation"]["label"] == "Oscillation"
    assert "Brake trace quality" in titles
    assert "Throttle modulation" in titles
    assert "Wheel instability" in titles
