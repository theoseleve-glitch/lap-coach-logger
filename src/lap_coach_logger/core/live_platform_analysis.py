"""Live ride-height, balance, and aero-platform analysis for lap_pc."""

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
class PlatformPoint:
    session_time_s: float
    speed_kph: float | None = None
    throttle_pct: float | None = None
    brake_pct: float | None = None
    steering_deg: float | None = None
    lat_accel_g: float | None = None
    long_accel_g: float | None = None
    pitch: float | None = None
    roll: float | None = None
    ride_height_front: float | None = None
    ride_height_rear: float | None = None
    suspension_travel_lf: float | None = None
    suspension_travel_rf: float | None = None
    suspension_travel_lr: float | None = None
    suspension_travel_rr: float | None = None


class LivePlatformAnalysisTracker:
    """Track platform behavior, axle limitation, and aero-balance suspicion."""

    def __init__(self) -> None:
        self.reset()

    def reset(self, session_uid: str | None = None) -> None:
        self.session_uid = session_uid
        self._points: list[PlatformPoint] = []

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
        if len(self._points) > 700:
            self._points = self._points[-700:]

    def snapshot(self) -> dict[str, Any]:
        recent = _recent_points(self._points, window_s=12.0)
        rake = _evaluate_rake_trend(recent)
        compression = _evaluate_ride_height_compression(recent)
        balance = _evaluate_chassis_balance(recent)
        axle_limit = _evaluate_axle_limitation(recent)
        asymmetry = _evaluate_roll_asymmetry(recent)
        aero = _evaluate_aero_balance(recent, rake, compression)
        rows = {
            "rake_trend": rake,
            "ride_height_compression": compression,
            "chassis_balance": balance,
            "front_rear_limitation": axle_limit,
            "roll_asymmetry": asymmetry,
            "aero_balance": aero,
        }
        return {
            "rows": rows,
            "flags": _build_flags(rows),
        }


def _build_point(sample: TelemetrySample, merged: dict[str, Any]) -> PlatformPoint | None:
    session_time_s = _nonnegative_float(sample.session_time_s)
    if session_time_s is None:
        return None
    return PlatformPoint(
        session_time_s=session_time_s,
        speed_kph=_nonnegative_float(sample.speed_kph),
        throttle_pct=_clamp_unit(sample.throttle_pct),
        brake_pct=_clamp_unit(sample.brake_pct),
        steering_deg=_float(sample.steering_deg),
        lat_accel_g=_float(sample.lat_accel_g),
        long_accel_g=_float(sample.long_accel_g),
        pitch=_float(sample.pitch),
        roll=_float(sample.roll),
        ride_height_front=_nonnegative_float(merged.get("ride_height_front")),
        ride_height_rear=_nonnegative_float(merged.get("ride_height_rear")),
        suspension_travel_lf=_nonnegative_float(merged.get("suspension_travel_lf")),
        suspension_travel_rf=_nonnegative_float(merged.get("suspension_travel_rf")),
        suspension_travel_lr=_nonnegative_float(merged.get("suspension_travel_lr")),
        suspension_travel_rr=_nonnegative_float(merged.get("suspension_travel_rr")),
    )


def _evaluate_rake_trend(points: list[PlatformPoint]) -> dict[str, Any]:
    ride_points = [point for point in points if point.ride_height_front is not None and point.ride_height_rear is not None]
    if len(ride_points) >= 6:
        rakes = [_height_mm(point.ride_height_rear) - _height_mm(point.ride_height_front) for point in ride_points]
        avg_rake = _mean(rakes)
        latest_rake = rakes[-1]
        trend_mm = latest_rake - avg_rake
        if trend_mm <= -4.0:
            label = "Flattening"
        elif trend_mm >= 4.0:
            label = "Building Rake"
        elif avg_rake >= 15.0:
            label = "Rear-High"
        elif avg_rake <= -5.0:
            label = "Nose-High"
        else:
            label = "Stable"
        detail = f"Average rake {avg_rake:.0f} mm; latest {latest_rake:.0f} mm."
        return _metric(label, detail, value_mm=round(latest_rake, 1))

    pitch_values = [abs(point.pitch or 0.0) for point in points if point.pitch is not None]
    if len(pitch_values) >= 6:
        return _metric(
            "Inferred Only",
            f"No direct ride-height channel; pitch variation is {max(pitch_values) - min(pitch_values):.1f}°.",
        )
    return _metric("Collecting", "Need more loaded samples to estimate rake trend.")


def _evaluate_ride_height_compression(points: list[PlatformPoint]) -> dict[str, Any]:
    ride_points = [point for point in points if point.ride_height_front is not None and point.ride_height_rear is not None]
    if len(ride_points) >= 6:
        fronts = [_height_mm(point.ride_height_front) for point in ride_points]
        rears = [_height_mm(point.ride_height_rear) for point in ride_points]
        baseline_front = _high_mean(fronts)
        baseline_rear = _high_mean(rears)
        front_drop = max(0.0, baseline_front - min(fronts))
        rear_drop = max(0.0, baseline_rear - min(rears))
        compression_ratio = _ratio(_is_heavily_compressed(point, baseline_front, baseline_rear) for point in ride_points)
        bottoming_risk = compression_ratio >= 0.16 or max(front_drop, rear_drop) >= 14.0
        if bottoming_risk:
            label = "Bottoming Risk"
        elif max(front_drop, rear_drop) >= 7.0:
            label = "Compressed"
        else:
            label = "Controlled"
        detail = (
            f"Peak drop front {front_drop:.0f} mm, rear {rear_drop:.0f} mm; "
            f"heavy compression on {compression_ratio:.0%} of loaded samples."
        )
        return _metric(label, detail, value_pct=compression_ratio)

    if _ratio(_is_bottoming_proxy(point) for point in points) >= 0.14:
        return _metric(
            "Bottoming Risk",
            "No direct ride-height channel; pitch and roll spikes at high speed suggest floor contact risk.",
        )
    if points:
        return _metric(
            "Inferred Only",
            "No direct ride-height channel; using pitch and roll as a bottoming proxy.",
        )
    return _metric("Collecting", "Need more loaded samples to estimate platform compression.")


def _evaluate_chassis_balance(points: list[PlatformPoint]) -> dict[str, Any]:
    corner_points = [point for point in points if _is_cornering(point)]
    if len(corner_points) < 8:
        return _metric("Collecting", "Need more cornering load to estimate balance trend.")

    front_push = _ratio(_is_understeer(point) for point in corner_points)
    rear_instability = _ratio(_is_oversteer(point) or _is_traction_loss(point) for point in corner_points)
    net = front_push - rear_instability
    if net >= 0.12:
        label = "Understeer Trend"
    elif net <= -0.08:
        label = "Oversteer Trend"
    else:
        label = "Neutral"
    score = _clamp_score(100.0 - abs(net) * 280.0)
    detail = f"Front-push markers {front_push:.0%}; rear-instability markers {rear_instability:.0%}."
    return _metric(label, detail, score=score)


def _evaluate_axle_limitation(points: list[PlatformPoint]) -> dict[str, Any]:
    corner_points = [point for point in points if _is_cornering(point)]
    if len(corner_points) < 8:
        return _metric("Collecting", "Need more cornering load to judge axle limitation.")

    front_limit = _ratio(_is_understeer(point) or _is_front_brake_limited(point) for point in corner_points)
    rear_limit = _ratio(_is_oversteer(point) or _is_traction_loss(point) for point in corner_points)
    if front_limit >= rear_limit + 0.08:
        label = "Front Limited"
    elif rear_limit >= front_limit + 0.08:
        label = "Rear Limited"
    else:
        label = "Balanced"
    detail = f"Front-limit markers {front_limit:.0%}; rear-limit markers {rear_limit:.0%}."
    return _metric(label, detail)


def _evaluate_roll_asymmetry(points: list[PlatformPoint]) -> dict[str, Any]:
    loaded = [
        point
        for point in points
        if point.roll is not None
        and point.lat_accel_g is not None
        and abs(point.lat_accel_g) >= 0.45
        and (point.speed_kph or 0.0) >= 85.0
    ]
    if len(loaded) < 8:
        return _metric("Collecting", "Need left and right loaded corners to estimate roll asymmetry.")

    positive = [abs(point.roll or 0.0) / max(0.45, abs(point.lat_accel_g or 0.0)) for point in loaded if (point.lat_accel_g or 0.0) > 0.0]
    negative = [abs(point.roll or 0.0) / max(0.45, abs(point.lat_accel_g or 0.0)) for point in loaded if (point.lat_accel_g or 0.0) < 0.0]
    if len(positive) < 3 or len(negative) < 3:
        return _metric("Collecting", "Need sustained load in both turn directions.")

    pos_mean = _mean(positive)
    neg_mean = _mean(negative)
    delta_ratio = abs(pos_mean - neg_mean) / max(0.001, max(pos_mean, neg_mean))
    if delta_ratio >= 0.22:
        label = "Asymmetric"
    elif delta_ratio >= 0.12:
        label = "Watch"
    else:
        label = "Even"
    detail = f"Roll-per-g differs by {delta_ratio:.0%} between turn directions."
    return _metric(label, detail, value_pct=delta_ratio)


def _evaluate_aero_balance(
    points: list[PlatformPoint],
    rake_metric: dict[str, Any],
    compression_metric: dict[str, Any],
) -> dict[str, Any]:
    high_speed = [
        point
        for point in points
        if (point.speed_kph or 0.0) >= 160.0 and abs(point.lat_accel_g or 0.0) >= 0.35
    ]
    if len(high_speed) < 6:
        if str(compression_metric.get("label") or "") == "Bottoming Risk":
            return _metric("Platform Sensitive", "Compression spikes suggest aero load is running into the floor.")
        return _metric("Collecting", "Need more high-speed cornering load to infer aero balance.")

    front_aero_risk = _ratio(_is_understeer(point) for point in high_speed)
    rear_aero_risk = _ratio(_is_oversteer(point) for point in high_speed)
    compression_label = str(compression_metric.get("label") or "")
    rake_label = str(rake_metric.get("label") or "")
    if front_aero_risk >= rear_aero_risk + 0.10:
        label = "Front Aero Weak"
        detail = "High-speed push suggests the front platform is not holding enough support."
        if compression_label == "Bottoming Risk" or rake_label == "Flattening":
            detail = "High-speed push plus platform flattening suggests front floor or splitter support is weak."
        return _metric(label, detail, value_pct=front_aero_risk)
    if rear_aero_risk >= front_aero_risk + 0.08:
        return _metric(
            "Rear Aero Weak",
            "High-speed rear movement suggests the rear platform is losing support.",
            value_pct=rear_aero_risk,
        )
    if compression_label == "Bottoming Risk":
        return _metric("Platform Sensitive", "Aero platform looks load-sensitive even without a clear axle bias.")
    return _metric("No Strong Flag", "High-speed balance is not pointing to one clear aero limitation.")


def _build_flags(rows: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    if str(rows["ride_height_compression"].get("label")) == "Bottoming Risk":
        flags.append({
            "severity": "warning",
            "title": "Bottoming risk",
            "detail": str(rows["ride_height_compression"].get("detail") or ""),
        })
    if str(rows["chassis_balance"].get("label")) in {"Understeer Trend", "Oversteer Trend"}:
        flags.append({
            "severity": "warning",
            "title": "Chassis balance trend",
            "detail": str(rows["chassis_balance"].get("detail") or ""),
        })
    if str(rows["front_rear_limitation"].get("label")) in {"Front Limited", "Rear Limited"}:
        flags.append({
            "severity": "warning",
            "title": "Axle limitation",
            "detail": str(rows["front_rear_limitation"].get("detail") or ""),
        })
    if str(rows["roll_asymmetry"].get("label")) == "Asymmetric":
        flags.append({
            "severity": "warning",
            "title": "Roll asymmetry",
            "detail": str(rows["roll_asymmetry"].get("detail") or ""),
        })
    if str(rows["aero_balance"].get("label")) in {"Front Aero Weak", "Rear Aero Weak", "Platform Sensitive"}:
        flags.append({
            "severity": "warning",
            "title": "Aero balance suspicion",
            "detail": str(rows["aero_balance"].get("detail") or ""),
        })
    return flags[:5]


def _metric(label: str, detail: str, **extra: object) -> dict[str, Any]:
    payload: dict[str, Any] = {"label": label, "detail": detail}
    payload.update(extra)
    return payload


def _recent_points(points: list[PlatformPoint], *, window_s: float) -> list[PlatformPoint]:
    if not points:
        return []
    latest = points[-1].session_time_s
    return [point for point in points if latest - point.session_time_s <= window_s]


def _is_cornering(point: PlatformPoint) -> bool:
    return (point.speed_kph or 0.0) >= 80.0 and abs(point.lat_accel_g or 0.0) >= 0.35


def _is_understeer(point: PlatformPoint) -> bool:
    return (
        abs(point.steering_deg or 0.0) >= 24.0
        and (point.speed_kph or 0.0) >= 85.0
        and abs(point.lat_accel_g or 0.0) <= 0.52
    )


def _is_oversteer(point: PlatformPoint) -> bool:
    return (
        abs(point.steering_deg or 0.0) <= 14.0
        and (point.speed_kph or 0.0) >= 80.0
        and abs(point.lat_accel_g or 0.0) >= 0.92
    )


def _is_traction_loss(point: PlatformPoint) -> bool:
    return (
        (point.throttle_pct or 0.0) >= 0.78
        and abs(point.steering_deg or 0.0) >= 15.0
        and 45.0 <= (point.speed_kph or 0.0) <= 170.0
        and (point.long_accel_g or 0.0) >= 0.32
    )


def _is_front_brake_limited(point: PlatformPoint) -> bool:
    return (
        (point.brake_pct or 0.0) >= 0.60
        and (point.speed_kph or 0.0) >= 75.0
        and abs(point.steering_deg or 0.0) >= 18.0
        and abs(point.lat_accel_g or 0.0) <= 0.55
    )


def _is_bottoming_proxy(point: PlatformPoint) -> bool:
    return (
        (point.speed_kph or 0.0) >= 180.0
        and (abs(point.pitch or 0.0) >= 7.5 or abs(point.roll or 0.0) >= 8.5)
    )


def _is_heavily_compressed(point: PlatformPoint, baseline_front_mm: float, baseline_rear_mm: float) -> bool:
    front_mm = _height_mm(point.ride_height_front)
    rear_mm = _height_mm(point.ride_height_rear)
    front_drop = baseline_front_mm - front_mm
    rear_drop = baseline_rear_mm - rear_mm
    return (
        (point.speed_kph or 0.0) >= 120.0
        and (abs(point.lat_accel_g or 0.0) >= 0.45 or abs(point.long_accel_g or 0.0) >= 0.40)
        and (front_drop >= 8.0 or rear_drop >= 8.0)
    )


def _height_mm(value: float | None) -> float:
    if value is None:
        return 0.0
    return value * 1000.0 if abs(value) < 2.0 else value


def _high_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    keep = max(2, len(values) // 3)
    return _mean(sorted(values, reverse=True)[:keep])


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


