"""Tests for metric confidence states."""
from __future__ import annotations

from lap_coach_logger.core.metric_state import (
    MetricState,
    classify_metric,
    metric_dict,
)


def test_available_when_value_present():
    assert classify_metric(42.0) == MetricState.AVAILABLE


def test_unavailable_when_none():
    assert classify_metric(None) == MetricState.UNAVAILABLE


def test_estimated_when_derived():
    assert classify_metric(42.0, is_derived=True) == MetricState.ESTIMATED


def test_unavailable_overrides_derived():
    assert classify_metric(None, is_derived=True) == MetricState.UNAVAILABLE


def test_metric_dict_bundles_value_and_state():
    d = metric_dict(3.14, MetricState.AVAILABLE)
    assert d == {"value": 3.14, "state": "available"}


def test_metric_dict_with_none():
    d = metric_dict(None, MetricState.UNAVAILABLE)
    assert d == {"value": None, "state": "unavailable"}


def test_enum_values():
    assert MetricState.AVAILABLE.value == "available"
    assert MetricState.ESTIMATED.value == "estimated"
    assert MetricState.UNAVAILABLE.value == "unavailable"
