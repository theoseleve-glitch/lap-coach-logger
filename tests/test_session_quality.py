"""Unit tests for session data-quality validation."""

from __future__ import annotations

from lap_coach_logger.config.models import QualityConfig
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.core.session_quality import validate_session_quality
from lap_coach_logger.writers.bundle_schema import LapRecord


def _sample(i: int) -> TelemetrySample:
    return TelemetrySample(
        timestamp_utc=f"2026-03-23T00:00:{i:02d}+00:00",
        sim="iRacing",
        session_uid="u1",
        session_time_s=float(i) * 0.1,
        lap_number=1 + (i // 100),
        speed_kph=80.0 + (i % 15),
        throttle_pct=0.2 + ((i % 7) * 0.1),
        brake_pct=0.05 if i % 20 else 0.5,
        gear=3 + (i % 3),
        track_name="Spa",
        car_name="GT3",
        session_type="Race",
        raw_source_timestamp=float(i) * 0.1,
    )


def test_quality_valid_session_accepted_or_warning() -> None:
    samples = [_sample(i) for i in range(300)]
    laps = [
        LapRecord(lap_number=1, start_session_time_s=0.0, end_session_time_s=10.0, lap_time_s=10.0),
        LapRecord(lap_number=2, start_session_time_s=10.0, end_session_time_s=20.0, lap_time_s=10.0),
    ]
    report = validate_session_quality(
        samples=samples,
        laps=laps,
        track_name="Spa",
        car_name="GT3",
        session_type="Race",
        sample_rate_hz=10.0,
        config=QualityConfig(),
    )

    assert report.recommended_classification in {"accepted", "accepted_with_warnings"}
    assert report.overall_quality_score > 0.5
    assert any(c.name == "timestamps_monotonic" and c.status == "pass" for c in report.individual_checks)


def test_quality_rejects_impossible_values() -> None:
    samples = [_sample(i) for i in range(150)]
    samples[20].speed_kph = -10.0
    samples[30].gear = 99

    report = validate_session_quality(
        samples=samples,
        laps=[],
        track_name="Monza",
        car_name="GT3",
        session_type="Race",
        sample_rate_hz=10.0,
        config=QualityConfig(),
    )

    assert report.recommended_classification == "rejected"
    assert any("Impossible telemetry values" in r for r in report.rejection_reasons)


def test_quality_rejects_missing_track_or_car() -> None:
    samples = [_sample(i) for i in range(120)]
    report = validate_session_quality(
        samples=samples,
        laps=[],
        track_name=None,
        car_name="",
        session_type="Race",
        sample_rate_hz=10.0,
        config=QualityConfig(),
    )

    assert report.recommended_classification == "rejected"
    assert any("Track or car metadata missing" in r for r in report.rejection_reasons)


def test_quality_flags_non_monotonic_timestamps() -> None:
    samples = [_sample(i) for i in range(140)]
    samples[80].session_time_s = samples[79].session_time_s - 0.5

    report = validate_session_quality(
        samples=samples,
        laps=[],
        track_name="Spa",
        car_name="GT3",
        session_type="Race",
        sample_rate_hz=10.0,
        config=QualityConfig(),
    )

    assert report.recommended_classification == "rejected"
    assert any(c.name == "timestamps_monotonic" and c.status == "fail" for c in report.individual_checks)


def test_quality_needs_review_with_many_warnings() -> None:
    cfg = QualityConfig(min_meaningful_speed_kph=5.0)
    samples = [_sample(i) for i in range(150)]
    # induce warnings without hard fails: large time gaps + flatline controls + interval jitter
    t = 0.0
    for i, s in enumerate(samples):
        s.speed_kph = 40.0
        s.throttle_pct = 0.3
        s.brake_pct = 0.1
        t += 0.2
        if i % 5 == 0:
            t += 0.7
        s.session_time_s = t

    report = validate_session_quality(
        samples=samples,
        laps=[],
        track_name="Spa",
        car_name="GT3",
        session_type="Race",
        sample_rate_hz=5.0,
        config=cfg,
    )

    assert report.recommended_classification in {"needs_review", "accepted_with_warnings"}
    assert len(report.warnings) >= 1
