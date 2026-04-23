"""Helpers for lap_pc live telemetry widgets.

This module stays free of Qt so the lap-by-lap corner heuristics can be
unit-tested independently from the desktop UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from lap_coach_logger.core.telemetry_utils import (
    to_float as _float,
    to_nonnegative_float as _nonnegative_float,
    to_percentage as _percentage,
    to_positive_int as _positive_int,
)


@dataclass(slots=True)
class LiveSamplePoint:
    lap_number: int
    lap_dist_pct: float
    session_time_s: float
    speed_kph: float | None = None
    lat_accel_g: float | None = None
    long_accel_g: float | None = None
    world_pos_x: float | None = None
    world_pos_z: float | None = None


@dataclass(slots=True)
class CornerDefinition:
    name: str
    start_pct: float
    end_pct: float


@dataclass(slots=True)
class CornerMetrics:
    name: str
    lap_time_s: float | None
    apex_speed_kph: float | None
    peak_lat_g: float | None


def build_live_sample_point(snapshot: Mapping[str, object]) -> LiveSamplePoint | None:
    lap_number = _positive_int(snapshot.get("lap_number"))
    lap_dist_pct = _percentage(snapshot.get("lap_dist_pct"))
    session_time_s = _nonnegative_float(snapshot.get("session_time_s"))
    if lap_number is None or lap_dist_pct is None or session_time_s is None:
        return None
    return LiveSamplePoint(
        lap_number=lap_number,
        lap_dist_pct=lap_dist_pct,
        session_time_s=session_time_s,
        speed_kph=_nonnegative_float(snapshot.get("speed_kph")),
        lat_accel_g=_float(snapshot.get("lat_accel_g")),
        long_accel_g=_float(snapshot.get("long_accel_g")),
        world_pos_x=_float(snapshot.get("world_pos_x")),
        world_pos_z=_float(snapshot.get("world_pos_z")),
    )


def detect_corners(
    samples: list[LiveSamplePoint],
    *,
    lat_threshold_g: float = 0.35,
    min_samples: int = 4,
    min_width_pct: float = 0.015,
    pad_pct: float = 0.004,
) -> list[CornerDefinition]:
    """Infer simple corner windows from sustained lateral load on lap one."""
    ordered = sorted(samples, key=lambda sample: sample.lap_dist_pct)
    groups: list[list[LiveSamplePoint]] = []
    current: list[LiveSamplePoint] = []
    inactive_streak = 0

    for sample in ordered:
        active = abs(sample.lat_accel_g or 0.0) >= lat_threshold_g
        if active:
            current.append(sample)
            inactive_streak = 0
            continue
        if current:
            inactive_streak += 1
            if inactive_streak <= 2:
                current.append(sample)
                continue
            active_only = [point for point in current if abs(point.lat_accel_g or 0.0) >= lat_threshold_g]
            if len(active_only) >= min_samples:
                groups.append(active_only)
            current = []
            inactive_streak = 0

    if current:
        active_only = [point for point in current if abs(point.lat_accel_g or 0.0) >= lat_threshold_g]
        if len(active_only) >= min_samples:
            groups.append(active_only)

    corners: list[CornerDefinition] = []
    for idx, group in enumerate(groups, start=1):
        start_pct = max(0.0, group[0].lap_dist_pct - pad_pct)
        end_pct = min(1.0, group[-1].lap_dist_pct + pad_pct)
        if end_pct - start_pct < min_width_pct:
            continue
        corners.append(CornerDefinition(name=f"T{idx:02d}", start_pct=start_pct, end_pct=end_pct))
    return corners


def compute_corner_metrics(
    samples: list[LiveSamplePoint],
    corners: list[CornerDefinition],
) -> list[CornerMetrics]:
    """Compute per-corner lap time, apex speed, and peak lateral G for one lap."""
    metrics: list[CornerMetrics] = []
    ordered = sorted(samples, key=lambda sample: sample.lap_dist_pct)
    for corner in corners:
        segment = [
            sample
            for sample in ordered
            if corner.start_pct <= sample.lap_dist_pct <= corner.end_pct
        ]
        if not segment:
            metrics.append(CornerMetrics(corner.name, None, None, None))
            continue
        lap_time_s = None
        if segment[-1].session_time_s >= segment[0].session_time_s:
            lap_time_s = round(segment[-1].session_time_s - segment[0].session_time_s, 3)
        valid_speeds = [sample.speed_kph for sample in segment if sample.speed_kph is not None]
        apex_speed = min(valid_speeds) if valid_speeds else None
        valid_lat = [abs(sample.lat_accel_g) for sample in segment if sample.lat_accel_g is not None]
        peak_lat = max(valid_lat) if valid_lat else None
        metrics.append(
            CornerMetrics(
                name=corner.name,
                lap_time_s=lap_time_s,
                apex_speed_kph=round(apex_speed, 1) if apex_speed is not None else None,
                peak_lat_g=round(peak_lat, 3) if peak_lat is not None else None,
            )
        )
    return metrics


class LiveCornerTracker:
    """Track live lap samples and build a simple corner table after lap one."""

    def __init__(self) -> None:
        self.reset()

    def reset(self, session_uid: str | None = None) -> None:
        self.session_uid = session_uid
        self._current_lap_number: int | None = None
        self._current_samples: list[LiveSamplePoint] = []
        self._corner_defs: list[CornerDefinition] = []
        self._last_metrics: list[CornerMetrics] = []
        self._best_times: dict[str, float] = {}

    def push_snapshot(self, snapshot: Mapping[str, object]) -> None:
        session_uid = str(snapshot.get("session_uid") or "") or None
        if session_uid != self.session_uid:
            self.reset(session_uid)

        point = build_live_sample_point(snapshot)
        if point is None:
            return

        if self._current_lap_number is None:
            self._current_lap_number = point.lap_number
        elif point.lap_number != self._current_lap_number:
            self._finalize_lap()
            self._current_samples = []
            self._current_lap_number = point.lap_number

        self._current_samples.append(point)

    def rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for metrics in self._last_metrics:
            rows.append(
                {
                    "corner": metrics.name,
                    "last_time_s": metrics.lap_time_s,
                    "best_time_s": self._best_times.get(metrics.name),
                    "apex_speed_kph": metrics.apex_speed_kph,
                    "peak_lat_g": metrics.peak_lat_g,
                }
            )
        return rows

    def _finalize_lap(self) -> None:
        if len(self._current_samples) < 12:
            return
        if not self._corner_defs:
            self._corner_defs = detect_corners(self._current_samples)
        if not self._corner_defs:
            return

        self._last_metrics = compute_corner_metrics(self._current_samples, self._corner_defs)
        for metrics in self._last_metrics:
            if metrics.lap_time_s is None:
                continue
            current_best = self._best_times.get(metrics.name)
            if current_best is None or metrics.lap_time_s < current_best:
                self._best_times[metrics.name] = metrics.lap_time_s


