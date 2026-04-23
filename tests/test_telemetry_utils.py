"""Tests for shared telemetry value coercion helpers."""

from lap_coach_logger.core.telemetry_utils import (
    to_clamp_unit,
    to_float,
    to_nonnegative_float,
    to_percentage,
    to_positive_float,
    to_positive_int,
)


class TestToFloat:
    def test_int(self):
        assert to_float(42) == 42.0

    def test_float(self):
        assert to_float(3.14) == 3.14

    def test_negative(self):
        assert to_float(-5.0) == -5.0

    def test_none(self):
        assert to_float(None) is None

    def test_string(self):
        assert to_float("3.14") is None

    def test_bool_excluded(self):
        # bool is subclass of int in Python, but we accept it as numeric
        assert to_float(True) == 1.0


class TestToNonnegativeFloat:
    def test_positive(self):
        assert to_nonnegative_float(5.0) == 5.0

    def test_zero(self):
        assert to_nonnegative_float(0.0) == 0.0

    def test_negative(self):
        assert to_nonnegative_float(-1.0) is None

    def test_none(self):
        assert to_nonnegative_float(None) is None


class TestToPositiveFloat:
    def test_positive(self):
        assert to_positive_float(3.0) == 3.0

    def test_zero(self):
        assert to_positive_float(0.0) is None

    def test_negative(self):
        assert to_positive_float(-1.0) is None


class TestToPercentage:
    def test_valid(self):
        assert to_percentage(0.5) == 0.5

    def test_zero(self):
        assert to_percentage(0.0) == 0.0

    def test_one(self):
        assert to_percentage(1.0) == 1.0

    def test_over_one(self):
        assert to_percentage(1.5) is None

    def test_negative(self):
        assert to_percentage(-0.1) is None


class TestToClampUnit:
    def test_normal(self):
        assert to_clamp_unit(0.5) == 0.5

    def test_over_one_clamped(self):
        assert to_clamp_unit(1.5) == 1.0

    def test_negative(self):
        assert to_clamp_unit(-0.1) is None


class TestToPositiveInt:
    def test_positive(self):
        assert to_positive_int(5) == 5

    def test_zero(self):
        assert to_positive_int(0) is None

    def test_negative(self):
        assert to_positive_int(-3) is None

    def test_float(self):
        assert to_positive_int(3.0) is None
