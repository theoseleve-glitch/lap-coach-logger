"""Tests for snapshot validator."""
from __future__ import annotations

from lap_coach_logger.core.metric_state import MetricState
from lap_coach_logger.utils.snapshot_validator import (
    ValidatedSnapshot,
    missing_keys,
    safe_get,
    validate_live,
    validate_snapshot,
)


class TestValidateSnapshot:

    def test_returns_none_for_non_dict(self):
        assert validate_snapshot(None) is None
        assert validate_snapshot("string") is None
        assert validate_snapshot(42) is None
        assert validate_snapshot([1, 2, 3]) is None

    def test_empty_dict_is_valid(self):
        result = validate_snapshot({})
        assert result is not None
        assert isinstance(result, ValidatedSnapshot)

    def test_all_fields_unavailable_in_empty_payload(self):
        result = validate_snapshot({})
        assert result.state_of("raw_state") == MetricState.UNAVAILABLE
        assert result.state_of("live") == MetricState.UNAVAILABLE

    def test_present_fields_available(self):
        result = validate_snapshot({"raw_state": "recording", "live": {}})
        assert result.state_of("raw_state") == MetricState.AVAILABLE
        assert result.state_of("live") == MetricState.AVAILABLE

    def test_get_returns_raw_value(self):
        result = validate_snapshot({"raw_state": "recording"})
        assert result.get("raw_state") == "recording"
        assert result.get("nonexistent") is None
        assert result.get("nonexistent", "fallback") == "fallback"

    def test_is_available(self):
        result = validate_snapshot({"raw_state": "recording", "live": None})
        assert result.is_available("raw_state") is True
        assert result.is_available("live") is False
        assert result.is_available("nonexistent") is False


class TestValidateLive:

    def test_returns_none_for_non_dict(self):
        assert validate_live(None) is None
        assert validate_live("x") is None

    def test_empty_live_all_unavailable(self):
        result = validate_live({})
        assert result.state_of("lap_number") == MetricState.UNAVAILABLE
        assert result.state_of("speed_kph") == MetricState.UNAVAILABLE

    def test_populated_live_has_available_fields(self):
        live = {"lap_number": 5, "speed_kph": 200.0, "fuel_level": 50.0}
        result = validate_live(live)
        assert result.state_of("lap_number") == MetricState.AVAILABLE
        assert result.state_of("speed_kph") == MetricState.AVAILABLE
        assert result.state_of("fuel_level") == MetricState.AVAILABLE
        assert result.state_of("brake_temp_lf") == MetricState.UNAVAILABLE

    def test_null_value_is_unavailable(self):
        live = {"lap_number": None}
        result = validate_live(live)
        assert result.state_of("lap_number") == MetricState.UNAVAILABLE


class TestSafeGet:

    def test_none_returns_default(self):
        assert safe_get(None, "x") is None
        assert safe_get(None, "x", default=42) == 42

    def test_dict_access(self):
        assert safe_get({"a": 1}, "a") == 1
        assert safe_get({"a": 1}, "missing") is None
        assert safe_get({"a": 1}, "missing", default=99) == 99

    def test_validated_snapshot_access(self):
        vs = validate_snapshot({"raw_state": "idle"})
        assert safe_get(vs, "raw_state") == "idle"
        assert safe_get(vs, "missing", default="x") == "x"

    def test_non_mapping_returns_default(self):
        assert safe_get(42, "x", default="fallback") == "fallback"
        assert safe_get("string", "x", default="fallback") == "fallback"


class TestMissingKeys:

    def test_all_missing_when_empty(self):
        missing = missing_keys({}, {"a", "b", "c"})
        assert missing == ["a", "b", "c"]

    def test_returns_only_missing(self):
        missing = missing_keys({"a": 1, "b": 2}, {"a", "b", "c"})
        assert missing == ["c"]

    def test_none_values_counted_as_missing(self):
        missing = missing_keys({"a": None, "b": 2}, {"a", "b"})
        assert missing == ["a"]

    def test_non_dict_returns_all_required(self):
        missing = missing_keys(None, {"a", "b"})
        assert missing == ["a", "b"]

    def test_validated_snapshot_input(self):
        vs = validate_live({"lap_number": 5})
        missing = missing_keys(vs, {"lap_number", "speed_kph"})
        assert missing == ["speed_kph"]
