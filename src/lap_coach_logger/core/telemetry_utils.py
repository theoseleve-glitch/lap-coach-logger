"""Shared telemetry value coercion helpers.

These pure functions safely convert raw telemetry values from adapters
(which may be None, wrong-typed, or out of range) into validated floats
or ints for downstream processing.
"""

from __future__ import annotations


def to_float(value: object) -> float | None:
    """Return *value* as a float, or None if it's not numeric."""
    if not isinstance(value, (int, float)):
        return None
    return float(value)


def to_nonnegative_float(value: object) -> float | None:
    """Return *value* as a non-negative float, or None."""
    if not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number < 0:
        return None
    return number


def to_positive_float(value: object) -> float | None:
    """Return *value* as a strictly positive float, or None."""
    number = to_nonnegative_float(value)
    if number is None or number <= 0:
        return None
    return number


def to_percentage(value: object) -> float | None:
    """Return *value* as a float in [0.0, 1.0], or None."""
    number = to_nonnegative_float(value)
    if number is None or number > 1.0:
        return None
    return number


def to_clamp_unit(value: object) -> float | None:
    """Return *value* clamped to [0.0, 1.0], or None if not numeric."""
    number = to_nonnegative_float(value)
    if number is None:
        return None
    return min(1.0, number)


def to_positive_int(value: object) -> int | None:
    """Return *value* as a positive int, or None."""
    if not isinstance(value, int):
        return None
    return value if value > 0 else None
