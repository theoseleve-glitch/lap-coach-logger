"""Live alerts and coaching heuristics for the desktop dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lap_coach_logger.core.live_dashboard import CornerDefinition, LiveSamplePoint, detect_corners
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.core.telemetry_utils import (
    to_clamp_unit as _clamp_unit,
    to_float as _float,
    to_nonnegative_float as _nonnegative_float,
    to_percentage as _percentage,
)


@dataclass(slots=True)
class CoachPoint:
    lap_number: int
    lap_dist_pct: float
    session_time_s: float
    speed_kph: float | None = None
    throttle_pct: float | None = None
    brake_pct: float | None = None
    steering_deg: float | None = None
    lat_accel_g: float | None = None
    long_accel_g: float | None = None
    pitch: float | None = None
    roll: float | None = None


@dataclass(slots=True)
class CornerCoachMetrics:
    name: str
    lap_time_s: float | None = None
    entry_speed_kph: float | None = None
    apex_speed_kph: float | None = None
    exit_speed_kph: float | None = None
    coast_time_s: float | None = None
    brake_peak_pct: float | None = None
    lockup_events: int = 0
    traction_events: int = 0
    understeer_score: float = 0.0
    oversteer_score: float = 0.0


class LiveCoachTracker:
    """Track live alerts, coaching prompts, and lap-end summaries."""

    def __init__(self) -> None:
        self.reset()

    def reset(self, session_uid: str | None = None) -> None:
        self.session_uid = session_uid
        self._current_lap_number: int | None = None
        self._current_points: list[CoachPoint] = []
        self._latest_state: dict[str, Any] = {}
        self._corner_defs: list[CornerDefinition] = []
        self._best_lap_time_s: float | None = None
        self._best_corner_metrics: dict[str, CornerCoachMetrics] = {}
        self._last_summary: dict[str, Any] | None = None

    def push_sample(
        self,
        sample: TelemetrySample,
        *,
        dashboard_state: dict[str, Any] | None = None,
        derived_state: dict[str, Any] | None = None,
    ) -> None:
        if sample.session_uid != self.session_uid:
            self.reset(sample.session_uid)

        merged: dict[str, Any] = sample.to_dict()
        if dashboard_state:
            merged.update(dashboard_state)
        if derived_state:
            merged.update(derived_state)
        self._latest_state = merged

        point = _build_point(sample)
        if point is None:
            return

        if self._current_lap_number is None:
            self._current_lap_number = point.lap_number
        elif point.lap_number != self._current_lap_number:
            self._finalize_lap()
            self._current_points = []
            self._current_lap_number = point.lap_number

        if self._current_points:
            previous = self._current_points[-1]
            if (
                abs(previous.session_time_s - point.session_time_s) < 0.02
                and abs(previous.lap_dist_pct - point.lap_dist_pct) < 0.0005
            ):
                return
        self._current_points.append(point)

    def snapshot(self) -> dict[str, Any]:
        recent = _recent_points(self._current_points)
        alerts = _build_alerts(self._latest_state, recent, self._active_corner_name())
        coaching = self._build_coaching(recent)
        summary = dict(self._last_summary) if isinstance(self._last_summary, dict) else None
        return {
            "alerts": alerts,
            "coaching": coaching,
            "active_corner": self._active_corner_name(),
            "lap_end_summary": summary,
        }

    def _finalize_lap(self) -> None:
        if len(self._current_points) < 12:
            return

        if not self._corner_defs:
            self._corner_defs = _detect_corners(self._current_points)
        if not self._corner_defs:
            return

        metrics = _compute_corner_metrics(self._current_points, self._corner_defs)
        metric_map = {metric.name: metric for metric in metrics}
        lap_time_s = self._current_points[-1].session_time_s - self._current_points[0].session_time_s
        lap_time_s = round(lap_time_s, 3) if lap_time_s > 0 else None

        if self._best_corner_metrics and lap_time_s is not None:
            self._last_summary = _build_lap_end_summary(
                lap_number=self._current_lap_number,
                metrics=metric_map,
                best_metrics=self._best_corner_metrics,
            )
        elif lap_time_s is not None:
            self._last_summary = {
                "lap_number": self._current_lap_number,
                "biggest_time_loss_corner": "-",
                "biggest_technique_issue": "Collecting baseline lap",
                "recommended_focus": "Complete one clean push lap to establish a reference.",
            }

        if lap_time_s is not None and (self._best_lap_time_s is None or lap_time_s < self._best_lap_time_s):
            self._best_lap_time_s = lap_time_s
            self._best_corner_metrics = metric_map

    def _active_corner_name(self) -> str | None:
        if not self._corner_defs or not self._current_points:
            return None
        current_pct = self._current_points[-1].lap_dist_pct
        for corner in self._corner_defs:
            if corner.start_pct <= current_pct <= corner.end_pct:
                return corner.name
        return None

    def _build_coaching(self, recent: list[CoachPoint]) -> list[dict[str, str]]:
        if not self._corner_defs or not self._current_points:
            return []

        active_corner = self._active_corner_name()
        if active_corner is None:
            return []

        current_metrics = _compute_corner_metrics(self._current_points, self._corner_defs, current_pct=self._current_points[-1].lap_dist_pct)
        current_map = {metric.name: metric for metric in current_metrics}
        current = current_map.get(active_corner)
        baseline = self._best_corner_metrics.get(active_corner)
        if current is None or baseline is None:
            return []

        prompts: list[dict[str, str]] = []
        coast_delta = _delta(current.coast_time_s, baseline.coast_time_s)
        entry_delta = _delta(baseline.entry_speed_kph, current.entry_speed_kph)
        apex_delta = _delta(baseline.apex_speed_kph, current.apex_speed_kph)
        exit_delta = _delta(baseline.exit_speed_kph, current.exit_speed_kph)

        if entry_delta is not None and entry_delta >= 6.0:
            prompts.append({"title": "Brake later", "detail": f"Entry speed is down in {active_corner}."})
        if coast_delta is not None and coast_delta >= 0.18:
            prompts.append({"title": f"Too much coast in {active_corner}", "detail": "Roll the car less between brake release and throttle."})
        if (
            apex_delta is not None
            and apex_delta >= 4.0
            and current.brake_peak_pct is not None
            and current.brake_peak_pct >= 0.22
        ):
            prompts.append({"title": "Release earlier", "detail": f"Apex speed is low in {active_corner}."})
        if current.traction_events > baseline.traction_events:
            prompts.append({"title": "Throttle too aggressive on exit", "detail": f"Rear traction is limited in {active_corner}."})
        if current.understeer_score > baseline.understeer_score + 0.12:
            prompts.append({"title": "Front limited", "detail": f"The front axle is washing wide in {active_corner}."})
        if current.oversteer_score > baseline.oversteer_score + 0.12:
            prompts.append({"title": "Rear limited", "detail": f"The rear is moving around in {active_corner}."})
        if exit_delta is not None and exit_delta >= 5.0:
            prompts.append({"title": "Use more track on exit", "detail": f"Exit speed is behind the best lap in {active_corner}."})

        if not prompts:
            if _count_matching(recent, _is_understeer) >= 3:
                prompts.append({"title": "Front limited", "detail": f"Rotate the car earlier into {active_corner}."})
            elif _count_matching(recent, _is_oversteer) >= 2:
                prompts.append({"title": "Rear limited", "detail": f"Smooth the release and throttle in {active_corner}."})

        return prompts[:3]


def _build_point(sample: TelemetrySample) -> CoachPoint | None:
    lap_number = sample.lap_number
    lap_dist_pct = _percentage(sample.lap_dist_pct)
    session_time_s = _nonnegative_float(sample.session_time_s)
    if lap_number is None or lap_number <= 0 or lap_dist_pct is None or session_time_s is None:
        return None
    return CoachPoint(
        lap_number=lap_number,
        lap_dist_pct=lap_dist_pct,
        session_time_s=session_time_s,
        speed_kph=_nonnegative_float(sample.speed_kph),
        throttle_pct=_clamp_unit(sample.throttle_pct),
        brake_pct=_clamp_unit(sample.brake_pct),
        steering_deg=_float(sample.steering_deg),
        lat_accel_g=_float(sample.lat_accel_g),
        long_accel_g=_float(sample.long_accel_g),
        pitch=_float(sample.pitch),
        roll=_float(sample.roll),
    )


def _detect_corners(points: list[CoachPoint]) -> list[CornerDefinition]:
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


def _compute_corner_metrics(
    points: list[CoachPoint],
    corners: list[CornerDefinition],
    *,
    current_pct: float | None = None,
) -> list[CornerCoachMetrics]:
    metrics: list[CornerCoachMetrics] = []
    for corner in corners:
        end_pct = corner.end_pct if current_pct is None else min(corner.end_pct, current_pct)
        if end_pct < corner.start_pct:
            continue
        segment = [
            point
            for point in points
            if corner.start_pct <= point.lap_dist_pct <= end_pct
        ]
        if len(segment) < 2:
            continue
        segment_time = segment[-1].session_time_s - segment[0].session_time_s
        speeds = [point.speed_kph for point in segment if point.speed_kph is not None]
        metrics.append(
            CornerCoachMetrics(
                name=corner.name,
                lap_time_s=round(segment_time, 3) if segment_time >= 0 else None,
                entry_speed_kph=round(speeds[0], 1) if speeds else None,
                apex_speed_kph=round(min(speeds), 1) if speeds else None,
                exit_speed_kph=round(speeds[-1], 1) if speeds else None,
                coast_time_s=round(_coast_time(segment), 3),
                brake_peak_pct=max((point.brake_pct or 0.0) for point in segment),
                lockup_events=_count_matching(segment, _is_lockup),
                traction_events=_count_matching(segment, _is_traction_loss),
                understeer_score=_trend_score(segment, _is_understeer),
                oversteer_score=_trend_score(segment, _is_oversteer),
            )
        )
    return metrics


def _build_alerts(
    latest_state: dict[str, Any],
    recent: list[CoachPoint],
    active_corner: str | None,
) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []
    tyre_temps = [
        _nonnegative_float(latest_state.get(f"tyre_temp_{wheel}"))
        for wheel in ("lf", "rf", "lr", "rr")
    ]
    valid_tyres = [temp for temp in tyre_temps if temp is not None]
    if valid_tyres:
        avg_temp = sum(valid_tyres) / len(valid_tyres)
        if avg_temp < 68.0:
            alerts.append({"severity": "warning", "title": "Tyres cold", "detail": f"Average surface temp is {avg_temp:.0f}°C."})
        elif avg_temp > 104.0:
            alerts.append({"severity": "warning", "title": "Tyres overheated", "detail": f"Average surface temp is {avg_temp:.0f}°C."})

    max_brake_temp = max(
        (
            _nonnegative_float(latest_state.get(f"brake_temp_{wheel}")) or 0.0
            for wheel in ("lf", "rf", "lr", "rr")
        ),
        default=0.0,
    )
    if max_brake_temp >= 720.0:
        alerts.append({"severity": "warning", "title": "Excessive brake temp", "detail": f"Peak brake temp is {max_brake_temp:.0f}°C."})

    if _count_matching(recent, _is_lockup) >= 2:
        alerts.append({"severity": "error", "title": "Lockups detected", "detail": f"Front tyres are locking{_corner_suffix(active_corner)}."})
    if _count_matching(recent, _is_traction_loss) >= 2:
        alerts.append({"severity": "error", "title": "Wheelspin / traction loss", "detail": f"Rear traction is breaking away{_corner_suffix(active_corner)}."})
    understeer_score = _trend_score(recent, _is_understeer)
    oversteer_score = _trend_score(recent, _is_oversteer)
    if understeer_score >= 0.34:
        alerts.append({"severity": "warning", "title": "Understeer trend", "detail": f"The front axle is pushing wide{_corner_suffix(active_corner)}."})
    if oversteer_score >= 0.26:
        alerts.append({"severity": "warning", "title": "Oversteer trend", "detail": f"The rear axle is lively{_corner_suffix(active_corner)}."})
    if _count_matching(recent, _is_bottoming) >= 2:
        alerts.append({"severity": "warning", "title": "Bottoming suspected", "detail": "Ride control looks too aggressive over the surface."})

    if (
        active_corner is not None
        and (_count_matching(recent, _is_lockup) >= 1 or understeer_score >= 0.34 or _count_matching(recent, _is_traction_loss) >= 1)
    ):
        alerts.append({"severity": "warning", "title": "Clipping / overdriving", "detail": f"Inputs are too aggressive in {active_corner}."})
    return alerts[:5]


def _build_lap_end_summary(
    *,
    lap_number: int | None,
    metrics: dict[str, CornerCoachMetrics],
    best_metrics: dict[str, CornerCoachMetrics],
) -> dict[str, Any]:
    biggest_corner = "-"
    biggest_corner_delta = 0.0
    biggest_issue = "No clear issue"
    biggest_issue_severity = 0.0
    recommendation = "Stabilize the lap and keep building reference quality."

    for name, metric in metrics.items():
        baseline = best_metrics.get(name)
        if baseline is None:
            continue
        if metric.lap_time_s is not None and baseline.lap_time_s is not None:
            delta = metric.lap_time_s - baseline.lap_time_s
            if delta > biggest_corner_delta:
                biggest_corner_delta = delta
                biggest_corner = name
        issue, severity = _technique_issue(name, metric, baseline)
        if severity > biggest_issue_severity:
            biggest_issue = issue
            biggest_issue_severity = severity
            recommendation = _recommended_focus(name, issue)

    if biggest_corner == "-" and biggest_issue == "No clear issue":
        recommendation = "The lap was close to the benchmark. Chase consistency next lap."

    return {
        "lap_number": lap_number,
        "biggest_time_loss_corner": biggest_corner,
        "biggest_technique_issue": biggest_issue,
        "recommended_focus": recommendation,
    }


def _technique_issue(
    corner_name: str,
    metric: CornerCoachMetrics,
    baseline: CornerCoachMetrics,
) -> tuple[str, float]:
    coast_delta = _delta(metric.coast_time_s, baseline.coast_time_s) or 0.0
    entry_speed_gap = _delta(baseline.entry_speed_kph, metric.entry_speed_kph) or 0.0
    apex_speed_gap = _delta(baseline.apex_speed_kph, metric.apex_speed_kph) or 0.0
    exit_speed_gap = _delta(baseline.exit_speed_kph, metric.exit_speed_kph) or 0.0

    candidates = [
        (f"Too much coast in {corner_name}", coast_delta),
        (f"Brake later into {corner_name}", max(0.0, entry_speed_gap - 4.0)),
        (f"Release earlier in {corner_name}", max(0.0, apex_speed_gap - 3.0)),
        (f"Throttle too aggressive on exit of {corner_name}", max(0.0, metric.traction_events - baseline.traction_events)),
        (f"Front limited in {corner_name}", max(0.0, metric.understeer_score - baseline.understeer_score)),
        (f"Rear limited in {corner_name}", max(0.0, metric.oversteer_score - baseline.oversteer_score)),
        (f"Use more track on exit of {corner_name}", max(0.0, exit_speed_gap - 4.0)),
    ]
    issue, severity = max(candidates, key=lambda item: item[1], default=("No clear issue", 0.0))
    return issue, float(severity)


def _recommended_focus(corner_name: str, issue: str) -> str:
    if "coast" in issue.lower():
        return f"Focus on carrying brake pressure deeper into {corner_name} and getting back to throttle sooner."
    if "brake later" in issue.lower():
        return f"Move the braking point forward a car length for {corner_name}."
    if "release earlier" in issue.lower():
        return f"Come off the brake more progressively before the apex in {corner_name}."
    if "throttle too aggressive" in issue.lower():
        return f"Delay full throttle until the wheel is straighter on exit of {corner_name}."
    if "front limited" in issue.lower():
        return f"Prioritize rotation and a later apex in {corner_name}."
    if "rear limited" in issue.lower():
        return f"Smooth the release and throttle application in {corner_name}."
    if "use more track" in issue.lower():
        return f"Let the car breathe all the way to the exit curb in {corner_name}."
    return "Build one cleaner lap and protect the tyre window."


def _recent_points(points: list[CoachPoint], *, window_s: float = 2.0) -> list[CoachPoint]:
    if not points:
        return []
    latest = points[-1].session_time_s
    return [point for point in points if latest - point.session_time_s <= window_s]


def _coast_time(points: list[CoachPoint]) -> float:
    total = 0.0
    for previous, current in zip(points, points[1:]):
        if (
            (previous.brake_pct or 0.0) <= 0.08
            and (previous.throttle_pct or 0.0) <= 0.15
            and (current.brake_pct or 0.0) <= 0.08
            and (current.throttle_pct or 0.0) <= 0.15
            and (current.speed_kph or 0.0) >= 60.0
        ):
            total += max(0.0, current.session_time_s - previous.session_time_s)
    return total


def _count_matching(points: list[CoachPoint], predicate) -> int:  # noqa: ANN001
    return sum(1 for point in points if predicate(point))


def _trend_score(points: list[CoachPoint], predicate) -> float:  # noqa: ANN001
    if not points:
        return 0.0
    return round(_count_matching(points, predicate) / len(points), 3)


def _is_lockup(point: CoachPoint) -> bool:
    return (
        (point.brake_pct or 0.0) >= 0.88
        and (point.long_accel_g or 0.0) <= -1.15
        and (point.speed_kph or 0.0) >= 70.0
    )


def _is_traction_loss(point: CoachPoint) -> bool:
    return (
        (point.throttle_pct or 0.0) >= 0.78
        and abs(point.steering_deg or 0.0) >= 18.0
        and 45.0 <= (point.speed_kph or 0.0) <= 170.0
        and (point.long_accel_g or 0.0) >= 0.35
    )


def _is_understeer(point: CoachPoint) -> bool:
    return (
        abs(point.steering_deg or 0.0) >= 24.0
        and (point.speed_kph or 0.0) >= 80.0
        and abs(point.lat_accel_g or 0.0) <= 0.48
    )


def _is_oversteer(point: CoachPoint) -> bool:
    return (
        abs(point.steering_deg or 0.0) <= 12.0
        and (point.speed_kph or 0.0) >= 75.0
        and abs(point.lat_accel_g or 0.0) >= 0.9
    )


def _is_bottoming(point: CoachPoint) -> bool:
    return (
        (point.speed_kph or 0.0) >= 180.0
        and (abs(point.pitch or 0.0) >= 7.5 or abs(point.roll or 0.0) >= 8.5)
    )


def _corner_suffix(corner_name: str | None) -> str:
    return f" in {corner_name}" if corner_name else ""


def _delta(reference: float | None, current: float | None) -> float | None:
    if reference is None or current is None:
        return None
    return reference - current


