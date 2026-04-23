from __future__ import annotations

from lap_coach_logger.core.live_coach import LiveCoachTracker
from lap_coach_logger.core.schema import TelemetrySample


def test_live_coach_raises_temperature_brake_and_lockup_alerts() -> None:
    tracker = LiveCoachTracker()

    for index, session_time_s in enumerate((10.0, 10.4, 10.8)):
        tracker.push_sample(
            TelemetrySample(
                session_uid="session-alerts",
                lap_number=1,
                lap_dist_pct=0.10 + index * 0.01,
                session_time_s=session_time_s,
                speed_kph=128.0,
                brake_pct=0.96,
                throttle_pct=0.0,
                steering_deg=7.0,
                long_accel_g=-1.32,
                lat_accel_g=0.12,
                tyre_temp_lf=60.0,
                tyre_temp_rf=61.0,
                tyre_temp_lr=62.0,
                tyre_temp_rr=60.0,
            ),
            dashboard_state={
                "brake_temp_lf": 760.0,
                "brake_temp_rf": 745.0,
                "brake_temp_lr": 701.0,
                "brake_temp_rr": 710.0,
            },
        )

    titles = {item["title"] for item in tracker.snapshot()["alerts"]}

    assert "Tyres cold" in titles
    assert "Excessive brake temp" in titles
    assert "Lockups detected" in titles


def test_live_coach_generates_corner_prompts_and_lap_end_summary() -> None:
    tracker = LiveCoachTracker()
    lap_one = _build_lap(session_uid="session-compare", lap_number=1, start_time_s=0.0, poor_t1=False)
    lap_two = _build_lap(session_uid="session-compare", lap_number=2, start_time_s=lap_one[-1].session_time_s + 2.0, poor_t1=True)
    lap_three_start = TelemetrySample(
        session_uid="session-compare",
        lap_number=3,
        lap_dist_pct=0.0,
        session_time_s=lap_two[-1].session_time_s + 2.0,
        speed_kph=240.0,
        throttle_pct=1.0,
        brake_pct=0.0,
        steering_deg=0.0,
        long_accel_g=0.18,
        lat_accel_g=0.02,
    )

    for sample in lap_one:
        tracker.push_sample(sample)

    for sample in lap_two[:16]:
        tracker.push_sample(sample)

    coaching_titles = [item["title"] for item in tracker.snapshot()["coaching"]]

    assert "Brake later" in coaching_titles
    assert any(title.startswith("Too much coast in T01") for title in coaching_titles)
    assert "Release earlier" in coaching_titles

    for sample in lap_two[16:]:
        tracker.push_sample(sample)
    tracker.push_sample(lap_three_start)

    summary = tracker.snapshot()["lap_end_summary"]

    assert isinstance(summary, dict)
    assert summary["biggest_time_loss_corner"] == "T01"
    assert "T01" in summary["biggest_technique_issue"]
    assert summary["recommended_focus"]


def _build_lap(
    *,
    session_uid: str,
    lap_number: int,
    start_time_s: float,
    poor_t1: bool,
) -> list[TelemetrySample]:
    samples: list[TelemetrySample] = []
    session_time_s = start_time_s
    segment_dt_s = 1.8

    for index in range(51):
        lap_dist_pct = index / 50.0
        if index > 0:
            prev_lap_dist_pct = (index - 1) / 50.0
            midpoint = (prev_lap_dist_pct + lap_dist_pct) / 2.0
            time_weight = 1.0
            if poor_t1 and 0.18 <= midpoint <= 0.32:
                time_weight = 1.7
            session_time_s += segment_dt_s * time_weight

        sample = TelemetrySample(
            session_uid=session_uid,
            lap_number=lap_number,
            lap_dist_pct=lap_dist_pct,
            session_time_s=round(session_time_s, 3),
            speed_kph=245.0,
            throttle_pct=1.0,
            brake_pct=0.0,
            steering_deg=0.0,
            long_accel_g=0.18,
            lat_accel_g=0.03,
            pitch=1.0,
            roll=1.5,
        )

        if 0.18 <= lap_dist_pct <= 0.32:
            _apply_turn_one_profile(sample, lap_dist_pct=lap_dist_pct, poor=poor_t1)
        elif 0.58 <= lap_dist_pct <= 0.74:
            _apply_turn_two_profile(sample, lap_dist_pct=lap_dist_pct)

        samples.append(sample)

    return samples


def _apply_turn_one_profile(sample: TelemetrySample, *, lap_dist_pct: float, poor: bool) -> None:
    phase = (lap_dist_pct - 0.18) / 0.14
    if poor:
        if phase < 0.25:
            sample.speed_kph = 155.0
            sample.brake_pct = 0.64
            sample.throttle_pct = 0.0
            sample.steering_deg = 28.0
            sample.long_accel_g = -0.92
            sample.lat_accel_g = 0.44
        elif phase < 0.70:
            sample.speed_kph = 103.0
            sample.brake_pct = 0.03
            sample.throttle_pct = 0.04
            sample.steering_deg = 31.0
            sample.long_accel_g = 0.0
            sample.lat_accel_g = 0.39
        else:
            sample.speed_kph = 150.0
            sample.brake_pct = 0.0
            sample.throttle_pct = 0.92
            sample.steering_deg = 21.0
            sample.long_accel_g = 0.46
            sample.lat_accel_g = 0.43
    else:
        if phase < 0.25:
            sample.speed_kph = 175.0
            sample.brake_pct = 0.72
            sample.throttle_pct = 0.0
            sample.steering_deg = 22.0
            sample.long_accel_g = -1.02
            sample.lat_accel_g = 0.78
        elif phase < 0.70:
            sample.speed_kph = 121.0
            sample.brake_pct = 0.18
            sample.throttle_pct = 0.05
            sample.steering_deg = 24.0
            sample.long_accel_g = -0.24
            sample.lat_accel_g = 0.88
        else:
            sample.speed_kph = 185.0
            sample.brake_pct = 0.0
            sample.throttle_pct = 0.62
            sample.steering_deg = 15.0
            sample.long_accel_g = 0.28
            sample.lat_accel_g = 0.76


def _apply_turn_two_profile(sample: TelemetrySample, *, lap_dist_pct: float) -> None:
    phase = (lap_dist_pct - 0.58) / 0.16
    if phase < 0.25:
        sample.speed_kph = 168.0
        sample.brake_pct = 0.58
        sample.throttle_pct = 0.0
        sample.steering_deg = -19.0
        sample.long_accel_g = -0.82
        sample.lat_accel_g = -0.62
    elif phase < 0.70:
        sample.speed_kph = 126.0
        sample.brake_pct = 0.08
        sample.throttle_pct = 0.12
        sample.steering_deg = -23.0
        sample.long_accel_g = -0.08
        sample.lat_accel_g = -0.91
    else:
        sample.speed_kph = 174.0
        sample.brake_pct = 0.0
        sample.throttle_pct = 0.74
        sample.steering_deg = -14.0
        sample.long_accel_g = 0.32
        sample.lat_accel_g = -0.74
