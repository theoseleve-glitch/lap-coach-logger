"""Shared test utility functions for the LapCoachLogger test suite.

These are plain functions (not pytest fixtures) that can be imported into
any test module.  Pytest fixtures that wrap these functions live in conftest.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.writers.finalizer import SessionFinalizer


def make_quality_samples(
    count: int = 200,
    *,
    sim: str = "iRacing",
    track: str = "Spa",
    car: str = "GT3",
    session_type: str = "Race",
    laps: int = 3,
    base_speed: float = 130.0,
    session_uid: str = "test-uid",
) -> list[TelemetrySample]:
    """Return *count* synthetic TelemetrySample objects that pass all quality gates.

    Samples span *laps* laps at 1 sample/second with realistic variation in
    speed, throttle, brake, steering, gear, and rpm.  All critical channels
    (speed, throttle, brake, gear, lap_number) are populated.
    """
    samples: list[TelemetrySample] = []
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    per_lap = max(1, count // laps)
    for i in range(count):
        lap_num = min(laps, 1 + (i // per_lap))
        lap_idx = i % per_lap
        samples.append(
            TelemetrySample(
                timestamp_utc=(start + timedelta(seconds=i)).isoformat(),
                sim=sim,
                session_uid=session_uid,
                session_time_s=float(i),
                lap_number=lap_num,
                lap_distance_m=float(lap_idx * 200),
                lap_dist_pct=float(lap_idx / max(1, per_lap - 1)),
                speed_kph=base_speed + float(i % 10),
                throttle_pct=0.6 + float(i % 5) * 0.04,
                brake_pct=0.01 if i % 8 == 0 else 0.0,
                steering_deg=float((-4 + (i % 9)) * 1.5),
                gear=3 + (i % 3),
                rpm=5200.0 + float(i % 300),
                world_pos_x=float(i),
                world_pos_y=0.0,
                world_pos_z=float(lap_idx),
                yaw_deg=float(i % 360),
                long_accel_g=0.1,
                lat_accel_g=0.12,
                is_on_track=True,
                is_in_pits=False,
                track_name=track,
                car_name=car,
                session_type=session_type,
            )
        )
    return samples


def finalize_session(
    output_root: Path,
    *,
    sim: str = "iRacing",
    track: str = "Spa",
    car: str = "GT3",
    session_type: str = "Race",
    session_uid: str = "gate-session",
    sample_count: int = 200,
    started_at: datetime | None = None,
    duration_s: float = 200.0,
    laps: int = 3,
) -> Path:
    """Finalize a well-formed session bundle and assert success.

    Returns the path to the finalized bundle directory.
    Raises AssertionError if finalize() returns None (i.e., fails).
    """
    fin = SessionFinalizer(output_root)
    now = started_at or datetime(2026, 1, 1, tzinfo=timezone.utc)
    samples = make_quality_samples(
        sample_count,
        sim=sim,
        track=track,
        car=car,
        session_type=session_type,
        session_uid=session_uid,
        laps=laps,
    )
    result = fin.finalize(
        samples,
        started_at=now,
        ended_at=now + timedelta(seconds=duration_s),
        sim=sim,
        track=track,
        session_type=session_type,
        session_uid=session_uid,
        extra_metadata={"car": car, "sample_rate_hz": 1.0},
    )
    assert result is not None, "finalize_session: finalize() must not return None"
    return result
