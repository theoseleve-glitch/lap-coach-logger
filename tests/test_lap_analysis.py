"""Tests for conservative lap classification heuristics."""

from __future__ import annotations

from lap_coach_logger.core.lap_analysis import LapAnalysisConfig, classify_laps
from lap_coach_logger.core.schema import TelemetrySample


def _sample(
    *,
    lap_number: int,
    session_time_s: float,
    speed_kph: float,
    throttle_pct: float,
    brake_pct: float = 0.0,
    gear: int = 4,
    lap_distance_m: float | None = None,
    is_on_track: bool | None = True,
    is_in_pits: bool | None = False,
    yaw_deg: float | None = 5.0,
) -> TelemetrySample:
    return TelemetrySample(
        sim="iRacing",
        session_uid="u1",
        session_time_s=session_time_s,
        lap_number=lap_number,
        lap_distance_m=lap_distance_m,
        speed_kph=speed_kph,
        throttle_pct=throttle_pct,
        brake_pct=brake_pct,
        gear=gear,
        is_on_track=is_on_track,
        is_in_pits=is_in_pits,
        yaw_deg=yaw_deg,
        track_name="Spa",
        car_name="GT3",
        session_type="race",
    )


def _lap(
    lap_number: int,
    *,
    start_time: float,
    lap_time_s: float,
    sample_count: int = 40,
    speed_kph: float = 150.0,
    throttle_pct: float = 0.75,
    brake_pct: float = 0.08,
    pit: bool = False,
    offtrack: bool = False,
    spin: bool = False,
    flying_start: bool = True,
    flying_end: bool = True,
) -> list[TelemetrySample]:
    samples: list[TelemetrySample] = []
    dt = lap_time_s / max(1, sample_count - 1)
    for idx in range(sample_count):
        t = start_time + (idx * dt)
        distance = (idx / max(1, sample_count - 1)) * 5000.0
        yaw = 5.0
        current_speed = speed_kph
        current_pit = pit
        current_on_track = not offtrack
        if idx == 0 and not flying_start:
            current_speed = 45.0
        if idx == sample_count - 1 and not flying_end:
            current_speed = 55.0
        if pit and idx > sample_count // 2:
            current_pit = True
            current_speed = min(current_speed, 50.0)
        if offtrack and idx in (10, 11, 12):
            current_on_track = False
        if spin and idx == sample_count // 2:
            yaw = 200.0
        samples.append(_sample(
            lap_number=lap_number,
            session_time_s=t,
            speed_kph=current_speed,
            throttle_pct=throttle_pct,
            brake_pct=brake_pct,
            lap_distance_m=distance,
            is_on_track=current_on_track,
            is_in_pits=current_pit,
            yaw_deg=yaw,
        ))
    return samples


def test_push_lap_classified_clean_and_valid() -> None:
    samples = _lap(1, start_time=0.0, lap_time_s=90.0)
    laps, summary = classify_laps(samples, config=LapAnalysisConfig())

    assert len(laps) == 1
    lap = laps[0]
    assert lap.classification == "push_lap"
    assert lap.valid_for_analysis is True
    assert lap.clean_lap is True
    assert summary.clean_laps == 1
    assert summary.best_clean_lap_time_s == lap.lap_time_s


def test_first_non_flying_lap_is_out_lap() -> None:
    samples = _lap(1, start_time=0.0, lap_time_s=110.0, flying_start=False)
    laps, summary = classify_laps(samples, config=LapAnalysisConfig())

    assert laps[0].classification == "out_lap"
    assert laps[0].likely_flying_lap is False
    assert summary.clean_laps == 0


def test_pit_transition_marks_in_or_pit_lap() -> None:
    samples = _lap(1, start_time=0.0, lap_time_s=95.0)
    samples.extend(_lap(2, start_time=95.0, lap_time_s=105.0, pit=True, flying_end=False))
    laps, _summary = classify_laps(samples, config=LapAnalysisConfig())

    assert len(laps) == 2
    assert laps[1].pit_entry_or_exit_detected is True
    assert laps[1].classification in {"pit_lap", "in_lap"}
    assert laps[1].valid_for_analysis is False


def test_offtrack_or_spin_invalidates_lap() -> None:
    samples = _lap(1, start_time=0.0, lap_time_s=88.0, offtrack=True)
    samples.extend(_lap(2, start_time=88.0, lap_time_s=89.0, spin=True))
    laps, summary = classify_laps(samples, config=LapAnalysisConfig())

    assert laps[0].suspected_offtrack is True
    assert laps[0].classification == "invalid_lap"
    assert laps[1].suspected_spin_or_reset is True
    assert laps[1].classification == "invalid_lap"
    assert summary.valid_laps == 0


def test_representative_lap_prefers_median_clean_lap() -> None:
    samples: list[TelemetrySample] = []
    samples.extend(_lap(1, start_time=0.0, lap_time_s=88.0))
    samples.extend(_lap(2, start_time=88.0, lap_time_s=91.0))
    samples.extend(_lap(3, start_time=179.0, lap_time_s=95.0))
    laps, summary = classify_laps(samples, config=LapAnalysisConfig())

    assert [lap.classification for lap in laps] == ["push_lap", "push_lap", "push_lap"]
    assert summary.clean_laps == 3
    assert summary.representative_lap_number == 2
    assert summary.representative_lap_time_s == 91.0
