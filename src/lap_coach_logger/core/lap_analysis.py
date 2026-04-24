"""Post-recording lap classification and summary generation."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from statistics import median
from typing import Any

from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.writers.bundle_schema import (
    LegacyLapRecord as LapRecord,
)


@dataclass
class LapAnalysisConfig:
    """Thresholds for conservative lap classification."""
    min_samples_per_lap: int = 20
    min_complete_ratio: float = 0.85
    min_lap_time_s: float = 20.0
    max_lap_time_s: float = 600.0
    offtrack_ratio_warn: float = 0.05
    spin_yaw_delta_deg: float = 110.0
    spin_min_speed_kph: float = 40.0
    reset_distance_drop_m: float = 250.0
    reset_world_jump_m: float = 150.0
    pit_speed_kph: float = 80.0
    flying_speed_threshold_kph: float = 100.0
    push_mean_throttle_pct: float = 0.55
    cooldown_mean_throttle_pct: float = 0.35
    cooldown_mean_brake_pct: float = 0.10


@dataclass
class LapSummary:
    total_laps: int = 0
    valid_laps: int = 0
    clean_laps: int = 0
    best_lap_time_s: float | None = None
    best_clean_lap_time_s: float | None = None
    representative_lap_number: int | None = None
    representative_lap_time_s: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class _LapSegment:
    lap_number: int
    samples: list[TelemetrySample] = field(default_factory=list)


def classify_laps(
    samples: list[TelemetrySample],
    *,
    config: LapAnalysisConfig,
) -> tuple[list[LapRecord], LapSummary]:
    """Classify completed laps using only currently available telemetry."""
    segments = _segment_laps(samples)
    if not segments:
        return [], LapSummary()

    session_max_speed = max((s.speed_kph or 0.0) for s in samples)
    lap_records: list[LapRecord] = []

    for index, segment in enumerate(segments):
        lap_records.append(
            _classify_segment(
                segment,
                index=index,
                total_segments=len(segments),
                config=config,
                session_max_speed=session_max_speed,
            )
        )

    lap_times = [lap.lap_time_s for lap in lap_records if lap.lap_time_valid and lap.lap_time_s is not None]
    clean_laps = [lap for lap in lap_records if lap.clean_lap and lap.lap_time_s is not None]
    clean_times = [lap.lap_time_s for lap in clean_laps if lap.lap_time_s is not None]

    summary = LapSummary(
        total_laps=len(lap_records),
        valid_laps=sum(1 for lap in lap_records if lap.valid_for_analysis),
        clean_laps=sum(1 for lap in lap_records if lap.clean_lap),
        best_lap_time_s=min(lap_times) if lap_times else None,
        best_clean_lap_time_s=min(clean_times) if clean_times else None,
    )

    if clean_laps:
        target_time = median(clean_times)
        representative = min(
            clean_laps,
            key=lambda lap: abs((lap.lap_time_s or target_time) - target_time),
        )
        summary.representative_lap_number = representative.lap_number
        summary.representative_lap_time_s = representative.lap_time_s
    elif lap_records:
        candidate = next(
            (lap for lap in lap_records if lap.valid_for_analysis and lap.lap_time_s is not None),
            None,
        )
        if candidate is not None:
            summary.representative_lap_number = candidate.lap_number
            summary.representative_lap_time_s = candidate.lap_time_s

    return lap_records, summary


def _segment_laps(samples: list[TelemetrySample]) -> list[_LapSegment]:
    segments: list[_LapSegment] = []
    current: _LapSegment | None = None
    current_lap: int | None = None

    for sample in samples:
        if sample.lap_number is None:
            continue
        if current_lap != sample.lap_number:
            current_lap = sample.lap_number
            current = _LapSegment(lap_number=current_lap)
            segments.append(current)
        assert current is not None
        current.samples.append(sample)

    return [segment for segment in segments if segment.samples]


def _classify_segment(
    segment: _LapSegment,
    *,
    index: int,
    total_segments: int,
    config: LapAnalysisConfig,
    session_max_speed: float,
) -> LapRecord:
    samples = segment.samples
    start_time = _first_non_none(samples, "session_time_s") or 0.0
    end_time = _last_non_none(samples, "session_time_s")
    lap_time = None
    if end_time is not None and end_time >= start_time:
        lap_time = round(end_time - start_time, 3)

    speeds = [s.speed_kph for s in samples if s.speed_kph is not None]
    throttles = [s.throttle_pct for s in samples if s.throttle_pct is not None]
    brakes = [s.brake_pct for s in samples if s.brake_pct is not None]
    pit_states = [bool(s.is_in_pits) for s in samples if s.is_in_pits is not None]
    on_track_states = [bool(s.is_on_track) for s in samples if s.is_on_track is not None]
    max_speed = max(speeds) if speeds else None
    first_speed = speeds[0] if speeds else None
    last_speed = speeds[-1] if speeds else None
    mean_throttle = sum(throttles) / len(throttles) if throttles else 0.0
    mean_brake = sum(brakes) / len(brakes) if brakes else 0.0

    essential_present = sum(
        1
        for s in samples
        if s.session_time_s is not None and s.speed_kph is not None and s.gear is not None
    )
    complete_ratio = essential_present / len(samples) if samples else 0.0
    has_complete_telemetry = len(samples) >= config.min_samples_per_lap and complete_ratio >= config.min_complete_ratio

    lap_time_valid = lap_time is not None and config.min_lap_time_s <= lap_time <= config.max_lap_time_s

    suspected_offtrack = False
    if on_track_states:
        offtrack_ratio = 1.0 - (sum(1 for value in on_track_states if value) / len(on_track_states))
        suspected_offtrack = offtrack_ratio >= config.offtrack_ratio_warn and not any(pit_states)

    pit_entry_or_exit_detected = False
    if pit_states:
        pit_entry_or_exit_detected = any(
            pit_states[i] != pit_states[i - 1] for i in range(1, len(pit_states))
        ) or any(pit_states)

    suspected_spin_or_reset = _detect_spin_or_reset(samples, config)

    likely_flying_lap = bool(
        lap_time_valid
        and not pit_entry_or_exit_detected
        and not suspected_offtrack
        and (first_speed or 0.0) >= config.flying_speed_threshold_kph
        and (last_speed or 0.0) >= config.flying_speed_threshold_kph
    )

    classification = "unknown"
    if not lap_time_valid:
        classification = "unknown"
    elif suspected_spin_or_reset or suspected_offtrack:
        classification = "invalid_lap"
    elif pit_entry_or_exit_detected:
        if index == 0:
            classification = "out_lap"
        elif index == total_segments - 1:
            classification = "in_lap"
        else:
            classification = "pit_lap"
    elif index == 0 and not likely_flying_lap:
        classification = "out_lap"
    elif index == total_segments - 1 and (last_speed or 0.0) < config.flying_speed_threshold_kph:
        classification = "cooldown_lap"
    elif likely_flying_lap and mean_throttle >= config.push_mean_throttle_pct:
        classification = "push_lap"
    elif mean_throttle <= config.cooldown_mean_throttle_pct and mean_brake <= config.cooldown_mean_brake_pct:
        classification = "cooldown_lap"
    else:
        classification = "unknown"

    valid_for_analysis = bool(
        has_complete_telemetry
        and lap_time_valid
        and not suspected_offtrack
        and not suspected_spin_or_reset
        and classification in {"push_lap", "unknown"}
        and likely_flying_lap
    )
    clean_lap = bool(valid_for_analysis and classification == "push_lap")

    return LapRecord(
        lap_number=segment.lap_number,
        start_session_time_s=start_time,
        end_session_time_s=end_time,
        lap_time_s=lap_time,
        out_lap=(classification == "out_lap"),
        in_lap=(classification == "in_lap"),
        invalid=(classification == "invalid_lap"),
        classification=classification,
        has_complete_telemetry=has_complete_telemetry,
        valid_for_analysis=valid_for_analysis,
        suspected_offtrack=suspected_offtrack,
        suspected_spin_or_reset=suspected_spin_or_reset,
        pit_entry_or_exit_detected=pit_entry_or_exit_detected,
        lap_time_valid=lap_time_valid,
        likely_flying_lap=likely_flying_lap,
        clean_lap=clean_lap,
        sample_count=len(samples),
        max_speed_kph=max_speed,
    )


def _first_non_none(samples: list[TelemetrySample], attr: str) -> Any:
    for sample in samples:
        value = getattr(sample, attr, None)
        if value is not None:
            return value
    return None


def _last_non_none(samples: list[TelemetrySample], attr: str) -> Any:
    for sample in reversed(samples):
        value = getattr(sample, attr, None)
        if value is not None:
            return value
    return None


def _detect_spin_or_reset(samples: list[TelemetrySample], config: LapAnalysisConfig) -> bool:
    previous: TelemetrySample | None = None
    for sample in samples:
        if previous is not None:
            prev_dist = previous.lap_distance_m
            cur_dist = sample.lap_distance_m
            if prev_dist is not None and cur_dist is not None:
                if (prev_dist - cur_dist) >= config.reset_distance_drop_m:
                    return True

            prev_yaw = previous.yaw_deg
            cur_yaw = sample.yaw_deg
            prev_speed = previous.speed_kph or 0.0
            cur_speed = sample.speed_kph or 0.0
            if prev_yaw is not None and cur_yaw is not None:
                delta = abs(cur_yaw - prev_yaw)
                delta = min(delta, 360.0 - delta) if delta <= 360.0 else delta
                if delta >= config.spin_yaw_delta_deg and max(prev_speed, cur_speed) >= config.spin_min_speed_kph:
                    return True

            if _world_jump(previous, sample) >= config.reset_world_jump_m:
                return True
        previous = sample
    return False


def _world_jump(prev: TelemetrySample, cur: TelemetrySample) -> float:
    coords_prev = (prev.world_pos_x, prev.world_pos_y, prev.world_pos_z)
    coords_cur = (cur.world_pos_x, cur.world_pos_y, cur.world_pos_z)
    if any(value is None for value in coords_prev[:2]) or any(value is None for value in coords_cur[:2]):
        return 0.0
    dx = (cur.world_pos_x or 0.0) - (prev.world_pos_x or 0.0)
    dy = (cur.world_pos_y or 0.0) - (prev.world_pos_y or 0.0)
    dz = (cur.world_pos_z or 0.0) - (prev.world_pos_z or 0.0)
    return (dx * dx + dy * dy + dz * dz) ** 0.5
