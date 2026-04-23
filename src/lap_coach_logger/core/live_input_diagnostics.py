"""Live hardware, pedal, steering, and FFB diagnostics for lap_pc."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.core.telemetry_utils import (
    to_clamp_unit as _clamp_unit,
    to_float as _float,
    to_nonnegative_float as _nonnegative_float,
)


@dataclass(slots=True)
class InputPoint:
    session_time_s: float
    speed_kph: float | None = None
    throttle_pct: float | None = None
    brake_pct: float | None = None
    clutch_pct: float | None = None
    steering_deg: float | None = None
    lat_accel_g: float | None = None
    long_accel_g: float | None = None
    ffb_clip_pct: float | None = None


class LiveInputDiagnosticsTracker:
    """Track live input quality and inferred hardware issues."""

    def __init__(self) -> None:
        self.reset()

    def reset(self, session_uid: str | None = None) -> None:
        self.session_uid = session_uid
        self._points: list[InputPoint] = []
        self._min_active_throttle: float | None = None
        self._min_active_brake: float | None = None
        self._min_active_steering: float | None = None
        self._ffb_direct_seen = False

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

        point = _build_point(sample, merged)
        if point is None:
            return

        if self._points:
            previous = self._points[-1]
            if abs(previous.session_time_s - point.session_time_s) < 0.02:
                return

        self._points.append(point)
        if len(self._points) > 600:
            self._points = self._points[-600:]

        if point.throttle_pct is not None and point.throttle_pct >= 0.04:
            self._min_active_throttle = _min_value(self._min_active_throttle, point.throttle_pct)
        if point.brake_pct is not None and point.brake_pct >= 0.04:
            self._min_active_brake = _min_value(self._min_active_brake, point.brake_pct)
        if point.steering_deg is not None and abs(point.steering_deg) >= 2.0:
            self._min_active_steering = _min_value(self._min_active_steering, abs(point.steering_deg))
        if point.ffb_clip_pct is not None:
            self._ffb_direct_seen = True

    def snapshot(self) -> dict[str, Any]:
        recent = _recent_points(self._points, window_s=10.0)
        steering_linearity, saturation = _evaluate_steering(recent)
        rows = {
            "brake_trace": _evaluate_brake_trace(recent),
            "throttle_modulation": _evaluate_throttle_modulation(recent),
            "pedal_overlap": _evaluate_pedal_overlap(recent),
            "deadzone": _evaluate_deadzone(
                recent,
                min_active_throttle=self._min_active_throttle,
                min_active_brake=self._min_active_brake,
                min_active_steering=self._min_active_steering,
            ),
            "steering_linearity": steering_linearity,
            "steering_saturation": saturation,
            "ffb_clipping": _evaluate_ffb_clipping(recent, saturation, direct_seen=self._ffb_direct_seen),
            "wheel_oscillation": _evaluate_wheel_oscillation(recent),
        }
        return {
            "rows": rows,
            "flags": _build_flags(rows),
        }


def _build_point(sample: TelemetrySample, merged: dict[str, Any]) -> InputPoint | None:
    session_time_s = _nonnegative_float(sample.session_time_s)
    if session_time_s is None:
        return None
    ffb_clip_pct = _first_float(
        merged.get("ffb_clip_pct"),
        merged.get("ffb_clipping"),
        merged.get("ffb_output_pct"),
        merged.get("steering_torque_pct"),
        merged.get("force_feedback_clip_pct"),
    )
    if ffb_clip_pct is not None and ffb_clip_pct > 1.0:
        ffb_clip_pct = None

    return InputPoint(
        session_time_s=session_time_s,
        speed_kph=_nonnegative_float(sample.speed_kph),
        throttle_pct=_clamp_unit(sample.throttle_pct),
        brake_pct=_clamp_unit(sample.brake_pct),
        clutch_pct=_clamp_unit(sample.clutch_pct),
        steering_deg=_float(sample.steering_deg),
        lat_accel_g=_float(sample.lat_accel_g),
        long_accel_g=_float(sample.long_accel_g),
        ffb_clip_pct=ffb_clip_pct,
    )


def _evaluate_brake_trace(points: list[InputPoint]) -> dict[str, Any]:
    active = [point for point in points if (point.brake_pct or 0.0) >= 0.05]
    if len(active) < 6:
        return _metric("Collecting", "Build a few brake events to grade trace quality.")

    deltas = _input_deltas(active, "brake_pct")
    jump_ratio = _ratio(delta >= 0.22 for delta in deltas)
    work_ratio = _ratio(0.15 <= (point.brake_pct or 0.0) <= 0.85 for point in active)
    score = _clamp_score(100.0 - jump_ratio * 75.0 - max(0.0, 0.35 - work_ratio) * 70.0)
    if score >= 78.0:
        label = "Smooth"
    elif score >= 56.0:
        label = "Usable"
    else:
        label = "Abrupt"
    detail = f"Step changes {jump_ratio:.0%}; working range {work_ratio:.0%}."
    return _metric(label, detail, score=score)


def _evaluate_throttle_modulation(points: list[InputPoint]) -> dict[str, Any]:
    active = [point for point in points if (point.throttle_pct or 0.0) >= 0.08]
    if len(active) < 6:
        return _metric("Collecting", "Build a few throttle applications to grade modulation.")

    deltas = _input_deltas(active, "throttle_pct")
    spike_ratio = _ratio(delta >= 0.20 for delta in deltas)
    traction_ratio = _ratio(_is_traction_loss(point) for point in active)
    work_ratio = _ratio(0.20 <= (point.throttle_pct or 0.0) <= 0.85 for point in active)
    score = _clamp_score(100.0 - spike_ratio * 70.0 - traction_ratio * 85.0 - max(0.0, 0.25 - work_ratio) * 40.0)
    if score >= 78.0:
        label = "Progressive"
    elif score >= 58.0:
        label = "Busy"
    else:
        label = "Aggressive"
    detail = f"Large throttle steps {spike_ratio:.0%}; traction-risk samples {traction_ratio:.0%}."
    return _metric(label, detail, score=score)


def _evaluate_pedal_overlap(points: list[InputPoint]) -> dict[str, Any]:
    relevant = [point for point in points if (point.speed_kph or 0.0) >= 20.0]
    if len(relevant) < 8:
        return _metric("Collecting", "Need more pedal data to estimate overlap.")

    overlap_ratio = _ratio(
        (point.throttle_pct or 0.0) >= 0.12 and (point.brake_pct or 0.0) >= 0.08
        for point in relevant
    )
    if overlap_ratio >= 0.12:
        label = "High"
    elif overlap_ratio >= 0.05:
        label = "Watch"
    else:
        label = "Clean"
    detail = f"Throttle and brake overlap on {overlap_ratio:.0%} of moving samples."
    return _metric(label, detail, value_pct=overlap_ratio)


def _evaluate_deadzone(
    points: list[InputPoint],
    *,
    min_active_throttle: float | None,
    min_active_brake: float | None,
    min_active_steering: float | None,
) -> dict[str, Any]:
    if len(points) < 12:
        return _metric("Collecting", "Need more gentle inputs to estimate deadzones.")

    issues: list[str] = []
    details: list[str] = []
    if min_active_throttle is not None:
        details.append(f"Throttle starts at {min_active_throttle:.0%}")
        if min_active_throttle >= 0.09:
            issues.append("throttle")
    if min_active_brake is not None:
        details.append(f"Brake starts at {min_active_brake:.0%}")
        if min_active_brake >= 0.12:
            issues.append("brake")
    if min_active_steering is not None:
        details.append(f"Steering starts at {min_active_steering:.1f}°")
        if min_active_steering >= 10.0:
            issues.append("steering")

    if not details:
        return _metric("Collecting", "No light inputs observed yet.")
    if issues:
        return _metric("Possible Deadzone", f"{', '.join(details)}.")
    return _metric("Clean", f"{', '.join(details)}.")


def _evaluate_steering(points: list[InputPoint]) -> tuple[dict[str, Any], dict[str, Any]]:
    corner_points = [
        point
        for point in points
        if abs(point.steering_deg or 0.0) >= 6.0
        and abs(point.lat_accel_g or 0.0) >= 0.15
        and (point.speed_kph or 0.0) >= 60.0
    ]
    if len(corner_points) < 8:
        collecting = _metric("Collecting", "Need more cornering load to grade steering behavior.")
        return collecting, collecting

    ordered = sorted(corner_points, key=lambda point: abs(point.steering_deg or 0.0))
    split = max(1, len(ordered) // 2)
    low = ordered[:split]
    high = ordered[split:]
    low_lat = _mean(abs(point.lat_accel_g or 0.0) for point in low)
    high_lat = _mean(abs(point.lat_accel_g or 0.0) for point in high)
    lat_gain = high_lat - low_lat
    if lat_gain >= 0.18:
        linearity_label = "Consistent"
    elif lat_gain >= 0.08:
        linearity_label = "Compressed"
    else:
        linearity_label = "Nonlinear"
    linearity_score = _clamp_score(50.0 + lat_gain * 190.0)
    linearity = _metric(
        linearity_label,
        f"Lateral response rises {lat_gain:.2f} g from low to high steering demand.",
        score=linearity_score,
    )

    max_abs_steer = max(abs(point.steering_deg or 0.0) for point in corner_points)
    sat_points = [
        point
        for point in corner_points
        if abs(point.steering_deg or 0.0) >= 0.82 * max_abs_steer
    ]
    sat_ratio = len(sat_points) / len(corner_points) if corner_points else 0.0
    if sat_ratio >= 0.24 and lat_gain < 0.10:
        sat_label = "High"
    elif sat_ratio >= 0.12:
        sat_label = "Watch"
    else:
        sat_label = "Low"
    saturation = _metric(
        sat_label,
        f"Near-peak steering on {sat_ratio:.0%} of loaded corner samples.",
        value_pct=sat_ratio,
    )
    return linearity, saturation


def _evaluate_ffb_clipping(
    points: list[InputPoint],
    saturation_metric: dict[str, Any],
    *,
    direct_seen: bool,
) -> dict[str, Any]:
    direct_values = [point.ffb_clip_pct for point in points if point.ffb_clip_pct is not None]
    if direct_values:
        peak = max(direct_values)
        hot_ratio = _ratio(value >= 0.95 for value in direct_values)
        if peak >= 0.99 or hot_ratio >= 0.10:
            label = "Detected"
        elif peak >= 0.92 or hot_ratio >= 0.04:
            label = "Near Clip"
        else:
            label = "Headroom OK"
        detail = f"Direct FFB signal peaks at {peak:.0%}; near-limit samples {hot_ratio:.0%}."
        return _metric(label, detail, value_pct=peak, direct=True)

    saturation_label = str(saturation_metric.get("label") or "")
    if saturation_label == "High":
        return _metric(
            "Inferred Risk",
            "Direct FFB telemetry is unavailable; steering saturation suggests possible clipping in heavy load.",
            direct=False,
        )
    if direct_seen:
        return _metric("Unavailable", "FFB channel was present but no valid clip values were readable.", direct=False)
    return _metric("Unavailable", "No direct FFB clip telemetry is exposed by the current sim adapter.", direct=False)


def _evaluate_wheel_oscillation(points: list[InputPoint]) -> dict[str, Any]:
    straight_points = [
        point
        for point in points
        if (point.speed_kph or 0.0) >= 120.0
        and abs(point.lat_accel_g or 0.0) <= 0.18
        and (point.brake_pct or 0.0) <= 0.05
    ]
    if len(straight_points) < 8:
        return _metric("Collecting", "Need more straight-line running to grade oscillation.")

    usable = [point for point in straight_points if abs(point.steering_deg or 0.0) >= 3.0]
    if len(usable) < 4:
        return _metric("Stable", "Straight-line steering stays calm in the sampled window.")

    sign_changes = 0
    previous_sign = None
    for point in usable:
        sign = 1 if (point.steering_deg or 0.0) > 0 else -1
        if previous_sign is not None and sign != previous_sign:
            sign_changes += 1
        previous_sign = sign

    change_ratio = sign_changes / max(1, len(usable) - 1)
    mean_abs = _mean(abs(point.steering_deg or 0.0) for point in usable)
    if change_ratio >= 0.30 and mean_abs >= 6.0:
        label = "Oscillation"
    elif change_ratio >= 0.18 and mean_abs >= 4.0:
        label = "Watch"
    else:
        label = "Stable"
    detail = f"Straight-line steering averages {mean_abs:.1f}° with {change_ratio:.0%} sign changes."
    return _metric(label, detail)


def _build_flags(rows: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    if str(rows["pedal_overlap"].get("label")) == "High":
        flags.append({
            "severity": "warning",
            "title": "Pedal overlap",
            "detail": str(rows["pedal_overlap"].get("detail") or ""),
        })
    if str(rows["deadzone"].get("label")) == "Possible Deadzone":
        flags.append({
            "severity": "warning",
            "title": "Deadzone suspected",
            "detail": str(rows["deadzone"].get("detail") or ""),
        })
    if str(rows["wheel_oscillation"].get("label")) in {"Oscillation", "Watch"}:
        flags.append({
            "severity": "warning",
            "title": "Wheel instability",
            "detail": str(rows["wheel_oscillation"].get("detail") or ""),
        })
    if str(rows["ffb_clipping"].get("label")) in {"Detected", "Near Clip", "Inferred Risk"}:
        flags.append({
            "severity": "warning",
            "title": "FFB clipping",
            "detail": str(rows["ffb_clipping"].get("detail") or ""),
        })
    if str(rows["brake_trace"].get("label")) == "Abrupt":
        flags.append({
            "severity": "warning",
            "title": "Brake trace quality",
            "detail": str(rows["brake_trace"].get("detail") or ""),
        })
    if str(rows["throttle_modulation"].get("label")) == "Aggressive":
        flags.append({
            "severity": "warning",
            "title": "Throttle modulation",
            "detail": str(rows["throttle_modulation"].get("detail") or ""),
        })
    return flags[:5]


def _metric(label: str, detail: str, **extra: object) -> dict[str, Any]:
    payload: dict[str, Any] = {"label": label, "detail": detail}
    payload.update(extra)
    return payload


def _recent_points(points: list[InputPoint], *, window_s: float) -> list[InputPoint]:
    if not points:
        return []
    latest_time = points[-1].session_time_s
    return [point for point in points if latest_time - point.session_time_s <= window_s]


def _input_deltas(points: list[InputPoint], attr: str) -> list[float]:
    deltas: list[float] = []
    for previous, current in zip(points, points[1:]):
        prev_value = getattr(previous, attr) or 0.0
        curr_value = getattr(current, attr) or 0.0
        deltas.append(abs(curr_value - prev_value))
    return deltas


def _is_traction_loss(point: InputPoint) -> bool:
    return (
        (point.throttle_pct or 0.0) >= 0.78
        and abs(point.steering_deg or 0.0) >= 15.0
        and 45.0 <= (point.speed_kph or 0.0) <= 170.0
        and (point.long_accel_g or 0.0) >= 0.28
    )


def _ratio(values: Any) -> float:
    items = list(values)
    if not items:
        return 0.0
    return sum(1 for item in items if item) / len(items)


def _mean(values: Any) -> float:
    numbers = [float(value) for value in values]
    if not numbers:
        return 0.0
    return sum(numbers) / len(numbers)


def _clamp_score(value: float) -> int:
    return int(max(0.0, min(100.0, round(value))))




def _min_value(current: float | None, candidate: float) -> float:
    if current is None:
        return candidate
    return min(current, candidate)


def _first_float(*values: object) -> float | None:
    for value in values:
        number = _float(value)
        if number is not None:
            return number
    return None
