"""Live lap comparison helpers for the desktop dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lap_coach_logger.core.live_dashboard import CornerDefinition, LiveSamplePoint, detect_corners
from lap_coach_logger.core.schema import TelemetrySample


@dataclass(slots=True)
class ComparePoint:
    lap_number: int
    lap_dist_pct: float
    session_time_s: float
    speed_kph: float | None = None
    lat_accel_g: float | None = None


@dataclass(slots=True)
class SegmentMetrics:
    name: str
    start_pct: float
    end_pct: float
    lap_time_s: float | None = None
    entry_speed_kph: float | None = None
    apex_speed_kph: float | None = None
    exit_speed_kph: float | None = None
    complete: bool = False


@dataclass(slots=True)
class LapProfile:
    source_id: str
    label: str
    lap_number: int | None
    lap_time_s: float
    points: list[ComparePoint]
    segments: list[CornerDefinition] = field(default_factory=list)
    segment_metrics: list[SegmentMetrics] = field(default_factory=list)
    sector_splits: dict[int, float] = field(default_factory=dict)

    def metric_map(self) -> dict[str, SegmentMetrics]:
        return {metric.name: metric for metric in self.segment_metrics}


def build_point_from_sample(sample: TelemetrySample) -> ComparePoint | None:
    lap_number = sample.lap_number
    lap_dist_pct = _percentage(sample.lap_dist_pct)
    session_time_s = _nonnegative_float(sample.session_time_s)
    if lap_number is None or lap_number <= 0 or lap_dist_pct is None or session_time_s is None:
        return None
    return ComparePoint(
        lap_number=lap_number,
        lap_dist_pct=lap_dist_pct,
        session_time_s=session_time_s,
        speed_kph=_nonnegative_float(sample.speed_kph),
        lat_accel_g=_float(sample.lat_accel_g),
    )


def build_lap_profile(
    points: list[ComparePoint],
    *,
    source_id: str,
    label: str,
    lap_number: int | None = None,
    segments: list[CornerDefinition] | None = None,
    sector_splits: dict[int, float] | None = None,
) -> LapProfile | None:
    ordered = _dedupe_points(points)
    if len(ordered) < 8:
        return None

    lap_time_s = ordered[-1].session_time_s - ordered[0].session_time_s
    if lap_time_s <= 0:
        return None

    active_segments = list(segments or _detect_segments_from_points(ordered))
    metrics = _compute_segment_metrics(
        ordered,
        active_segments,
        current_pct=ordered[-1].lap_dist_pct,
    )
    return LapProfile(
        source_id=source_id,
        label=label,
        lap_number=lap_number,
        lap_time_s=round(lap_time_s, 3),
        points=ordered,
        segments=active_segments,
        segment_metrics=metrics,
        sector_splits=_normalize_sector_splits(sector_splits),
    )


def extract_best_lap_profile(
    samples: list[TelemetrySample],
    *,
    source_id: str,
    label: str,
    preferred_lap_number: int | None = None,
    segments: list[CornerDefinition] | None = None,
    sector_splits: dict[int, float] | None = None,
) -> LapProfile | None:
    laps = _group_points_by_lap(samples)
    if preferred_lap_number is not None and preferred_lap_number in laps:
        return build_lap_profile(
            laps[preferred_lap_number],
            source_id=source_id,
            label=label,
            lap_number=preferred_lap_number,
            segments=segments,
            sector_splits=sector_splits,
        )

    best_profile: LapProfile | None = None
    for lap_number, points in sorted(laps.items()):
        profile = build_lap_profile(
            points,
            source_id=source_id,
            label=label,
            lap_number=lap_number,
            segments=segments,
            sector_splits=sector_splits,
        )
        if profile is None:
            continue
        if best_profile is None or profile.lap_time_s < best_profile.lap_time_s:
            best_profile = profile
    return best_profile


class LiveLapComparisonTracker:
    """Track current lap progress against best and reference laps."""

    def __init__(self) -> None:
        self.reset()

    def reset(self, session_uid: str | None = None) -> None:
        self.session_uid = session_uid
        self.reference_id = "session_best"
        self.reference_label = "Session Best"
        self._current_lap_number: int | None = None
        self._current_points: list[ComparePoint] = []
        self._current_sector_splits: dict[int, float] = {}
        self._current_segment_entry_elapsed: dict[str, float] = {}
        self._segments: list[CornerDefinition] = []
        self._last_profile: LapProfile | None = None
        self._best_profile: LapProfile | None = None
        self._reference_profile: LapProfile | None = None
        self._best_sector_splits: dict[int, float] = {}
        self._best_segment_times: dict[str, float] = {}

    def set_reference_profile(
        self,
        profile: LapProfile | None,
        *,
        reference_id: str,
        reference_label: str,
    ) -> None:
        self.reference_id = reference_id
        self.reference_label = reference_label
        if profile is None:
            self._reference_profile = None
            return
        if self._segments:
            profile = build_lap_profile(
                profile.points,
                source_id=profile.source_id,
                label=profile.label,
                lap_number=profile.lap_number,
                segments=self._segments,
                sector_splits=profile.sector_splits,
            ) or profile
        elif profile.segments:
            self._segments = list(profile.segments)
        self._reference_profile = profile

    def push_sample(
        self,
        sample: TelemetrySample,
        *,
        dashboard_state: dict[str, Any] | None = None,
        derived_state: dict[str, Any] | None = None,
    ) -> None:
        if sample.session_uid != self.session_uid:
            self.reset(sample.session_uid)

        point = build_point_from_sample(sample)
        if point is None:
            return

        if self._current_lap_number is None:
            self._current_lap_number = point.lap_number
        elif point.lap_number != self._current_lap_number:
            self._finalize_current_lap()
            self._current_points = []
            self._current_sector_splits = {}
            self._current_segment_entry_elapsed = {}
            self._current_lap_number = point.lap_number

        if self._current_points:
            previous = self._current_points[-1]
            if (
                abs(previous.lap_dist_pct - point.lap_dist_pct) < 0.0005
                and abs(previous.session_time_s - point.session_time_s) < 0.02
            ):
                return

        self._current_points.append(point)
        self._update_current_sector_splits(dashboard_state, derived_state)
        self._track_segment_entry(point)

    def snapshot(self) -> dict[str, Any]:
        current_profile = build_lap_profile(
            list(self._current_points),
            source_id="current",
            label=f"Lap {self._current_lap_number or '-'}",
            lap_number=self._current_lap_number,
            segments=self._segments or None,
            sector_splits=self._current_sector_splits,
        )
        best_profile = self._best_profile
        reference_profile = self._reference_profile or best_profile
        current_pct = current_profile.points[-1].lap_dist_pct if current_profile else None
        current_elapsed = current_profile.lap_time_s if current_profile else None

        active_segment = None
        if current_pct is not None:
            active_segment = _segment_for_pct(self._segments, current_pct)

        current_vs_best_delta_s = (
            _delta_against_profile(current_profile, best_profile, current_pct)
            if current_profile and best_profile and current_pct is not None
            else None
        )
        current_vs_reference_delta_s = (
            _delta_against_profile(current_profile, reference_profile, current_pct)
            if current_profile and reference_profile and current_pct is not None
            else None
        )

        sector_rows = self._build_sector_rows()
        corner_rows, speed_compare = self._build_corner_rows(
            current_profile=current_profile,
            best_profile=best_profile,
            reference_profile=reference_profile,
            current_pct=current_pct,
            current_elapsed=current_elapsed,
            active_segment=active_segment,
        )

        live_marker = _build_live_marker(
            active_segment=active_segment,
            current_profile=current_profile,
            reference_profile=reference_profile,
            current_pct=current_pct,
            current_elapsed=current_elapsed,
            segment_entry_elapsed=self._current_segment_entry_elapsed,
            reference_label=self.reference_label if reference_profile else "Session Best",
        )

        return {
            "current_lap_number": self._current_lap_number,
            "current_lap_time_s": round(current_elapsed, 3) if current_elapsed is not None else None,
            "best_lap_time_s": best_profile.lap_time_s if best_profile else None,
            "reference_label": self.reference_label if reference_profile else "Session Best",
            "reference_lap_time_s": reference_profile.lap_time_s if reference_profile else None,
            "current_vs_best_delta_s": round(current_vs_best_delta_s, 3) if current_vs_best_delta_s is not None else None,
            "current_vs_reference_delta_s": round(current_vs_reference_delta_s, 3) if current_vs_reference_delta_s is not None else None,
            "theoretical_best_sector_s": _sum_best_times(self._best_sector_splits, range(1, 4)),
            "theoretical_best_corner_s": _sum_best_segment_times(self._segments, self._best_segment_times),
            "active_segment": active_segment.name if active_segment else None,
            "live_marker": live_marker,
            "speed_compare": speed_compare,
            "sector_rows": sector_rows,
            "corner_rows": corner_rows,
        }

    def _update_current_sector_splits(
        self,
        dashboard_state: dict[str, Any] | None,
        derived_state: dict[str, Any] | None,
    ) -> None:
        merged: dict[str, Any] = {}
        if dashboard_state:
            merged.update(dashboard_state)
        if derived_state:
            merged.update(derived_state)
        for index in range(1, 4):
            split = _positive_float(merged.get(f"sector_{index}_time_s"))
            if split is not None:
                self._current_sector_splits[index] = split

    def _track_segment_entry(self, point: ComparePoint) -> None:
        if not self._segments or not self._current_points:
            return
        active_segment = _segment_for_pct(self._segments, point.lap_dist_pct)
        if active_segment is None or active_segment.name in self._current_segment_entry_elapsed:
            return
        entry_elapsed = point.session_time_s - self._current_points[0].session_time_s
        self._current_segment_entry_elapsed[active_segment.name] = max(0.0, entry_elapsed)

    def _finalize_current_lap(self) -> None:
        profile = build_lap_profile(
            list(self._current_points),
            source_id=f"session:{self._current_lap_number}",
            label=f"Lap {self._current_lap_number}",
            lap_number=self._current_lap_number,
            segments=self._segments or None,
            sector_splits=self._current_sector_splits,
        )
        if profile is None:
            return

        if not self._segments and profile.segments:
            self._segments = list(profile.segments)
            profile = build_lap_profile(
                profile.points,
                source_id=profile.source_id,
                label=profile.label,
                lap_number=profile.lap_number,
                segments=self._segments,
                sector_splits=profile.sector_splits,
            ) or profile
            if self._reference_profile is not None:
                self._reference_profile = build_lap_profile(
                    self._reference_profile.points,
                    source_id=self._reference_profile.source_id,
                    label=self._reference_profile.label,
                    lap_number=self._reference_profile.lap_number,
                    segments=self._segments,
                    sector_splits=self._reference_profile.sector_splits,
                ) or self._reference_profile

        self._last_profile = profile
        if self._best_profile is None or profile.lap_time_s < self._best_profile.lap_time_s:
            self._best_profile = profile

        for index, split in profile.sector_splits.items():
            current_best = self._best_sector_splits.get(index)
            if current_best is None or split < current_best:
                self._best_sector_splits[index] = split

        for metric in profile.segment_metrics:
            if metric.lap_time_s is None:
                continue
            current_best = self._best_segment_times.get(metric.name)
            if current_best is None or metric.lap_time_s < current_best:
                self._best_segment_times[metric.name] = metric.lap_time_s

    def _build_sector_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index in range(1, 4):
            current = self._current_sector_splits.get(index)
            best = self._best_sector_splits.get(index)
            delta = None
            if current is not None and best is not None:
                delta = current - best
            rows.append(
                {
                    "segment": f"S{index}",
                    "current_time_s": round(current, 3) if current is not None else None,
                    "best_time_s": round(best, 3) if best is not None else None,
                    "delta_s": round(delta, 3) if delta is not None else None,
                    "marker": _delta_marker(delta),
                }
            )
        return rows

    def _build_corner_rows(
        self,
        *,
        current_profile: LapProfile | None,
        best_profile: LapProfile | None,
        reference_profile: LapProfile | None,
        current_pct: float | None,
        current_elapsed: float | None,
        active_segment: CornerDefinition | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        current_metric_map = current_profile.metric_map() if current_profile else {}
        best_metric_map = best_profile.metric_map() if best_profile else {}
        reference_metric_map = reference_profile.metric_map() if reference_profile else {}
        rows: list[dict[str, Any]] = []
        speed_compare: dict[str, Any] = {}

        for segment in self._segments:
            current_metric = current_metric_map.get(segment.name)
            best_metric = best_metric_map.get(segment.name)
            reference_metric = reference_metric_map.get(segment.name)

            delta_vs_reference = None
            marker = None
            if (
                current_metric is not None
                and current_metric.complete
                and current_metric.lap_time_s is not None
                and reference_metric is not None
                and reference_metric.lap_time_s is not None
            ):
                delta_vs_reference = current_metric.lap_time_s - reference_metric.lap_time_s
                marker = _delta_marker(delta_vs_reference)
            elif (
                active_segment is not None
                and active_segment.name == segment.name
                and current_profile is not None
                and reference_profile is not None
                and current_pct is not None
                and current_elapsed is not None
            ):
                delta_vs_reference = _active_segment_delta(
                    segment=segment,
                    current_profile=current_profile,
                    reference_profile=reference_profile,
                    current_pct=current_pct,
                    current_elapsed=current_elapsed,
                    segment_entry_elapsed=self._current_segment_entry_elapsed.get(segment.name),
                )
                marker = _delta_marker(delta_vs_reference)

            if active_segment is not None and active_segment.name == segment.name:
                speed_compare = {
                    "entry_current_kph": current_metric.entry_speed_kph if current_metric else None,
                    "entry_reference_kph": reference_metric.entry_speed_kph if reference_metric else None,
                    "apex_current_kph": current_metric.apex_speed_kph if current_metric else None,
                    "apex_reference_kph": reference_metric.apex_speed_kph if reference_metric else None,
                    "exit_current_kph": current_metric.exit_speed_kph if current_metric else None,
                    "exit_reference_kph": reference_metric.exit_speed_kph if reference_metric else None,
                }

            rows.append(
                {
                    "segment": segment.name,
                    "current_time_s": current_metric.lap_time_s if current_metric else None,
                    "best_time_s": best_metric.lap_time_s if best_metric else None,
                    "reference_time_s": reference_metric.lap_time_s if reference_metric else None,
                    "delta_vs_reference_s": round(delta_vs_reference, 3) if delta_vs_reference is not None else None,
                    "marker": marker,
                    "entry_compare": _speed_compare_text(
                        current_metric.entry_speed_kph if current_metric else None,
                        reference_metric.entry_speed_kph if reference_metric else None,
                    ),
                    "apex_compare": _speed_compare_text(
                        current_metric.apex_speed_kph if current_metric else None,
                        reference_metric.apex_speed_kph if reference_metric else None,
                    ),
                    "exit_compare": _speed_compare_text(
                        current_metric.exit_speed_kph if current_metric else None,
                        reference_metric.exit_speed_kph if reference_metric else None,
                    ),
                }
            )
        return rows, speed_compare


def _group_points_by_lap(samples: list[TelemetrySample]) -> dict[int, list[ComparePoint]]:
    grouped: dict[int, list[ComparePoint]] = {}
    for sample in samples:
        point = build_point_from_sample(sample)
        if point is None:
            continue
        grouped.setdefault(point.lap_number, []).append(point)
    return grouped


def _detect_segments_from_points(points: list[ComparePoint]) -> list[CornerDefinition]:
    samples = [
        LiveSamplePoint(
            lap_number=point.lap_number,
            lap_dist_pct=point.lap_dist_pct,
            session_time_s=point.session_time_s,
            speed_kph=point.speed_kph,
            lat_accel_g=point.lat_accel_g,
        )
        for point in points
    ]
    return detect_corners(samples)


def _compute_segment_metrics(
    points: list[ComparePoint],
    segments: list[CornerDefinition],
    *,
    current_pct: float,
) -> list[SegmentMetrics]:
    lap_start = points[0].session_time_s
    metrics: list[SegmentMetrics] = []
    for segment in segments:
        partial_end_pct = min(segment.end_pct, current_pct)
        if partial_end_pct < segment.start_pct:
            continue
        segment_points = [
            point
            for point in points
            if segment.start_pct <= point.lap_dist_pct <= partial_end_pct
        ]
        if not segment_points:
            continue
        elapsed = segment_points[-1].session_time_s - segment_points[0].session_time_s
        speeds = [point.speed_kph for point in segment_points if point.speed_kph is not None]
        metrics.append(
            SegmentMetrics(
                name=segment.name,
                start_pct=segment.start_pct,
                end_pct=segment.end_pct,
                lap_time_s=round(elapsed, 3) if elapsed >= 0 else None,
                entry_speed_kph=round(speeds[0], 1) if speeds else None,
                apex_speed_kph=round(min(speeds), 1) if speeds else None,
                exit_speed_kph=round(speeds[-1], 1) if speeds else None,
                complete=current_pct >= segment.end_pct,
            )
        )
    return metrics


def _dedupe_points(points: list[ComparePoint]) -> list[ComparePoint]:
    ordered = sorted(points, key=lambda point: (point.session_time_s, point.lap_dist_pct))
    deduped: list[ComparePoint] = []
    for point in ordered:
        if deduped:
            previous = deduped[-1]
            if (
                abs(previous.session_time_s - point.session_time_s) < 0.001
                and abs(previous.lap_dist_pct - point.lap_dist_pct) < 0.0001
            ):
                continue
        deduped.append(point)
    return deduped


def _normalize_sector_splits(value: dict[int, float] | None) -> dict[int, float]:
    normalized: dict[int, float] = {}
    for index in range(1, 4):
        if value is None:
            continue
        split = _positive_float(value.get(index))
        if split is not None:
            normalized[index] = round(split, 3)
    return normalized


def _segment_for_pct(segments: list[CornerDefinition], pct: float) -> CornerDefinition | None:
    for segment in segments:
        if segment.start_pct <= pct <= segment.end_pct:
            return segment
    return None


def _delta_against_profile(
    current_profile: LapProfile,
    baseline_profile: LapProfile | None,
    current_pct: float,
) -> float | None:
    if baseline_profile is None:
        return None
    baseline_elapsed = _interpolate_elapsed(baseline_profile, current_pct)
    if baseline_elapsed is None:
        return None
    return current_profile.lap_time_s - baseline_elapsed


def _active_segment_delta(
    *,
    segment: CornerDefinition,
    current_profile: LapProfile,
    reference_profile: LapProfile,
    current_pct: float,
    current_elapsed: float,
    segment_entry_elapsed: float | None,
) -> float | None:
    if segment_entry_elapsed is None:
        return None
    reference_at_start = _interpolate_elapsed(reference_profile, segment.start_pct)
    reference_at_current = _interpolate_elapsed(reference_profile, current_pct)
    if reference_at_start is None or reference_at_current is None:
        return None
    current_segment_elapsed = current_elapsed - segment_entry_elapsed
    reference_segment_elapsed = reference_at_current - reference_at_start
    return current_segment_elapsed - reference_segment_elapsed


def _interpolate_elapsed(profile: LapProfile, pct: float) -> float | None:
    if not profile.points:
        return None
    lap_start = profile.points[0].session_time_s
    if pct <= profile.points[0].lap_dist_pct:
        return 0.0
    for previous, current in zip(profile.points, profile.points[1:]):
        if pct > current.lap_dist_pct:
            continue
        span = current.lap_dist_pct - previous.lap_dist_pct
        prev_elapsed = previous.session_time_s - lap_start
        cur_elapsed = current.session_time_s - lap_start
        if span <= 0.00001:
            return round(cur_elapsed, 3)
        ratio = (pct - previous.lap_dist_pct) / span
        interpolated = prev_elapsed + ratio * (cur_elapsed - prev_elapsed)
        return round(interpolated, 3)
    return round(profile.lap_time_s, 3)


def _build_live_marker(
    *,
    active_segment: CornerDefinition | None,
    current_profile: LapProfile | None,
    reference_profile: LapProfile | None,
    current_pct: float | None,
    segment_entry_elapsed: dict[str, float],
    current_elapsed: float | None,
    reference_label: str,
) -> str | None:
    if (
        active_segment is None
        or current_profile is None
        or reference_profile is None
        or current_pct is None
        or current_elapsed is None
    ):
        return None
    delta = _active_segment_delta(
        segment=active_segment,
        current_profile=current_profile,
        reference_profile=reference_profile,
        current_pct=current_pct,
        current_elapsed=current_elapsed,
        segment_entry_elapsed=segment_entry_elapsed.get(active_segment.name),
    )
    if delta is None or abs(delta) < 0.04:
        return None
    if delta > 0:
        return f"Losing time in {active_segment.name}: +{delta:.3f}s vs {reference_label}"
    return f"Gaining time in {active_segment.name}: {delta:.3f}s vs {reference_label}"


def _sum_best_times(source: dict[int, float], indices) -> float | None:  # noqa: ANN001
    values = [source.get(index) for index in indices]
    if any(value is None for value in values):
        return None
    return round(sum(value for value in values if value is not None), 3)


def _sum_best_segment_times(
    segments: list[CornerDefinition],
    best_segment_times: dict[str, float],
) -> float | None:
    if not segments:
        return None
    values = [best_segment_times.get(segment.name) for segment in segments]
    if any(value is None for value in values):
        return None
    return round(sum(value for value in values if value is not None), 3)


def _delta_marker(value: float | None) -> str | None:
    if value is None:
        return None
    if value <= -0.04:
        return "GAIN"
    if value >= 0.04:
        return "LOSS"
    return "HOLD"


def _speed_compare_text(current: float | None, reference: float | None) -> str:
    if current is None and reference is None:
        return "-"
    if current is None:
        return f"- / {reference:.0f}"
    if reference is None:
        return f"{current:.0f} / -"
    return f"{current:.0f} / {reference:.0f}"


def _float(value: object) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    return float(value)


def _nonnegative_float(value: object) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number < 0:
        return None
    return number


def _positive_float(value: object) -> float | None:
    number = _nonnegative_float(value)
    if number is None or number <= 0:
        return None
    return number


def _percentage(value: object) -> float | None:
    number = _nonnegative_float(value)
    if number is None or number > 1.0:
        return None
    return number
