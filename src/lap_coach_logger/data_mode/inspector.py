"""Data mode channel inspector.

Provides a complete inventory of telemetry channels with their
confidence state, sampling quality, and actionable warnings.
Trust layer for advanced users and webapp sync validation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lap_coach_logger.core.metric_state import MetricState, classify_metric


_CANONICAL_CHANNELS = [
    "speed_kph", "throttle_pct", "brake_pct", "steering_deg", "gear", "rpm",
    "fuel_level", "fuel_capacity", "lap_number", "lap_distance_m", "lap_dist_pct",
    "tyre_temp_lf", "tyre_temp_rf", "tyre_temp_lr", "tyre_temp_rr",
    "brake_temp_lf", "brake_temp_rf", "brake_temp_lr", "brake_temp_rr",
    "track_temp_c", "air_temp_c", "position", "num_cars",
    "world_pos_x", "world_pos_y", "world_pos_z",
    "lat_accel_g", "long_accel_g", "is_in_pits", "is_on_track",
    "session_time_s", "track_name", "car_name", "session_type",
]


@dataclass
class ChannelStatus:
    """Status of one telemetry channel."""
    name: str
    state: MetricState
    last_value: Any = None
    sample_count: int = 0
    null_count: int = 0
    null_ratio: float = 0.0
    warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "last_value": self.last_value,
            "sample_count": self.sample_count,
            "null_count": self.null_count,
            "null_ratio": round(self.null_ratio, 3),
            "warning": self.warning,
        }


@dataclass
class InspectionReport:
    """Complete data quality report."""
    channels: list[ChannelStatus]
    total_samples: int
    sample_rate_hz: float
    available_count: int
    estimated_count: int
    unavailable_count: int
    warnings: list[str]
    overall_quality: str  # "good" / "degraded" / "poor"

    def to_dict(self) -> dict[str, Any]:
        return {
            "channels": [c.to_dict() for c in self.channels],
            "total_samples": self.total_samples,
            "sample_rate_hz": round(self.sample_rate_hz, 2),
            "available_count": self.available_count,
            "estimated_count": self.estimated_count,
            "unavailable_count": self.unavailable_count,
            "warnings": self.warnings,
            "overall_quality": self.overall_quality,
        }


def _build_channel_status(name: str, snapshots: list[dict]) -> ChannelStatus:
    """Analyse a single channel across all snapshots."""
    total = len(snapshots)
    if total == 0:
        return ChannelStatus(
            name=name,
            state=MetricState.UNAVAILABLE,
            warning=f"{name} not provided by this sim",
        )

    values = [s.get(name) for s in snapshots]
    null_count = sum(1 for v in values if v is None)
    sample_count = total - null_count
    null_ratio = null_count / total

    # Most recent non-None value
    last_value = None
    for v in reversed(values):
        if v is not None:
            last_value = v
            break

    # Classify state
    if null_ratio > 0.95:
        state = MetricState.UNAVAILABLE
    elif null_ratio > 0.20:
        state = MetricState.ESTIMATED
    else:
        state = MetricState.AVAILABLE

    # Generate warning
    warning: str | None = None
    if state == MetricState.UNAVAILABLE:
        warning = f"{name} not provided by this sim"
    elif state == MetricState.ESTIMATED and null_ratio > 0.5:
        warning = (
            f"{name} = ESTIMATED (LOW confidence) "
            f"— {null_ratio * 100:.0f}% missing"
        )
    elif state == MetricState.ESTIMATED:
        warning = f"{name} = ESTIMATED — intermittent data"

    return ChannelStatus(
        name=name,
        state=state,
        last_value=last_value,
        sample_count=sample_count,
        null_count=null_count,
        null_ratio=null_ratio,
        warning=warning,
    )


def inspect_channels(
    snapshots: list[dict],
    sample_rate_hz: float = 0.0,
) -> InspectionReport:
    """Inspect all canonical channels and produce a quality report.

    Parameters
    ----------
    snapshots:
        Buffer of recent telemetry snapshots (list of dicts).
    sample_rate_hz:
        Declared sample rate of the data source.

    Returns
    -------
    InspectionReport with per-channel status and overall quality.
    """
    total_samples = len(snapshots)
    channels = [_build_channel_status(ch, snapshots) for ch in _CANONICAL_CHANNELS]

    available_count = sum(1 for c in channels if c.state == MetricState.AVAILABLE)
    estimated_count = sum(1 for c in channels if c.state == MetricState.ESTIMATED)
    unavailable_count = sum(1 for c in channels if c.state == MetricState.UNAVAILABLE)

    # Collect warnings
    warnings: list[str] = [c.warning for c in channels if c.warning is not None]

    if sample_rate_hz < 5:
        warnings.append(
            f"Low sample rate ({sample_rate_hz} Hz) — data may be sparse"
        )
    if total_samples < 100:
        warnings.append(
            f"Limited data ({total_samples} samples) "
            f"— results may not be representative"
        )

    # Overall quality
    if unavailable_count <= 5 and estimated_count <= 3:
        overall_quality = "good"
    elif unavailable_count <= 10:
        overall_quality = "degraded"
    else:
        overall_quality = "poor"

    return InspectionReport(
        channels=channels,
        total_samples=total_samples,
        sample_rate_hz=sample_rate_hz,
        available_count=available_count,
        estimated_count=estimated_count,
        unavailable_count=unavailable_count,
        warnings=warnings,
        overall_quality=overall_quality,
    )


def inspect_live_metric(
    name: str,
    value: Any,
    history: list[Any] | None = None,
) -> ChannelStatus:
    """Quick single-channel inspection for live display.

    Parameters
    ----------
    name:
        Channel name.
    value:
        Current value of the metric.
    history:
        Optional list of recent values for null-ratio calculation.

    Returns
    -------
    ChannelStatus for the given metric.
    """
    state = classify_metric(value)

    null_count = 0
    sample_count = 0
    null_ratio = 0.0
    total = 0

    if history is not None:
        total = len(history)
        null_count = sum(1 for v in history if v is None)
        sample_count = total - null_count
        null_ratio = null_count / total if total > 0 else 0.0

    warning: str | None = None
    if state == MetricState.UNAVAILABLE:
        warning = f"{name} not provided by this sim"
    elif history is not None and null_ratio > 0.5:
        warning = (
            f"{name} = ESTIMATED (LOW confidence) "
            f"— {null_ratio * 100:.0f}% missing"
        )
    elif history is not None and null_ratio > 0.20:
        warning = f"{name} = ESTIMATED — intermittent data"

    return ChannelStatus(
        name=name,
        state=state,
        last_value=value,
        sample_count=sample_count,
        null_count=null_count,
        null_ratio=null_ratio,
        warning=warning,
    )
