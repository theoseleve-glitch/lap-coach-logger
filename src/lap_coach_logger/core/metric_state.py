"""Metric confidence states for live telemetry values.

Every displayed metric is either directly measured from telemetry
(available), derived/computed from other values (estimated), or
missing entirely (unavailable). UI and sync consumers use this
to decide how to present or trust each value.
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class MetricState(Enum):
    AVAILABLE = "available"      # directly from telemetry
    ESTIMATED = "estimated"      # computed/derived from other data
    UNAVAILABLE = "unavailable"  # no data source


def classify_metric(value: Any, is_derived: bool = False) -> MetricState:
    """Classify a metric value's confidence state."""
    if value is None:
        return MetricState.UNAVAILABLE
    if is_derived:
        return MetricState.ESTIMATED
    return MetricState.AVAILABLE


def metric_dict(value: Any, state: MetricState) -> dict[str, Any]:
    """Bundle a value with its confidence state for QML/sync consumers."""
    return {"value": value, "state": state.value}
