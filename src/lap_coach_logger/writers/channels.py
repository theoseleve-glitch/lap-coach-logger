"""Canonical channel definitions for telemetry columns.

Auto-derived from ``TelemetrySample`` fields so the channel manifest
stays in sync with the schema without manual maintenance.

Also provides a builder for iRacing raw channel definitions derived
from the actual raw sample column names.
"""

from __future__ import annotations

from typing import Any

from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.normalization.mapper import TELEMETRY_SCHEMA_VERSION, mapping_source_names
from lap_coach_logger.writers.bundle_schema import ChannelDef

# Per-field overrides: (dtype, units, missing_allowed, description)
_CHANNEL_META: dict[str, tuple[str, str | None, bool, str | None]] = {
    "timestamp_utc":        ("string",  None,   False, "ISO-8601 UTC wall-clock time"),
    "sim":                  ("string",  None,   False, "Simulator name"),
    "session_uid":          ("string",  None,   True,  "Unique session identifier"),
    "session_time_s":       ("float64", "s",    True,  "Session elapsed time"),
    "lap_number":           ("int32",   None,   True,  "Current lap number"),
    "lap_distance_m":       ("float64", "m",    True,  "Distance into current lap"),
    "lap_dist_pct":         ("float64", None,   True,  "Normalised track position 0-1"),
    "speed_kph":            ("float64", "km/h", True,  "Ground speed"),
    "throttle_pct":         ("float64", "%",    True,  "Throttle position 0-1"),
    "brake_pct":            ("float64", "%",    True,  "Brake position 0-1"),
    "clutch_pct":           ("float64", "%",    True,  "Clutch position 0-1"),
    "steering_deg":         ("float64", "deg",  True,  "Steering angle"),
    "gear":                 ("int32",   None,   True,  "Current gear (-1=R, 0=N)"),
    "rpm":                  ("float64", "rpm",  True,  "Engine RPM"),
    "abs_level":            ("float64", None,   True,  "ABS intervention/setting level"),
    "tc_level":             ("float64", None,   True,  "Traction control intervention/setting level"),
    "world_pos_x":          ("float64", "m",    True,  "World/reference position X"),
    "world_pos_y":          ("float64", "m",    True,  "World/reference position Y"),
    "world_pos_z":          ("float64", "m",    True,  "World/reference position Z"),
    "yaw_deg":              ("float64", "deg",  True,  "Yaw angle"),
    "pitch":                ("float64", "rad",  True,  "Pitch angle"),
    "roll":                 ("float64", "rad",  True,  "Roll angle"),
    "long_accel_g":         ("float64", "g",    True,  "Longitudinal acceleration"),
    "lat_accel_g":          ("float64", "g",    True,  "Lateral acceleration"),
    "tyre_temp_lf":         ("float64", "°C",   True,  "Tyre temp left-front"),
    "tyre_temp_rf":         ("float64", "°C",   True,  "Tyre temp right-front"),
    "tyre_temp_lr":         ("float64", "°C",   True,  "Tyre temp left-rear"),
    "tyre_temp_rr":         ("float64", "°C",   True,  "Tyre temp right-rear"),
    "fuel_level":           ("float64", "L",    True,  "Fuel remaining"),
    "fuel_capacity":        ("float64", "L",    True,  "Fuel tank capacity"),
    "water_temp":           ("float64", "°C",   True,  "Coolant temperature"),
    "oil_temp":             ("float64", "°C",   True,  "Oil temperature"),
    "track_temp_c":         ("float64", "°C",   True,  "Track surface temperature"),
    "air_temp_c":           ("float64", "°C",   True,  "Ambient air temperature"),
    "is_on_track":          ("bool",    None,   True,  "True when car is on track"),
    "is_in_pits":           ("bool",    None,   True,  "True when car is in pits"),
    "track_name":           ("string",  None,   True,  "Track / circuit name"),
    "car_name":             ("string",  None,   True,  "Car / vehicle name"),
    "session_type":         ("string",  None,   True,  "Session type (Practice / Race …)"),
    "raw_source_timestamp": ("float64", "s",    True,  "Sim-native timestamp"),
}


def build_channel_defs() -> list[ChannelDef]:
    """Return a ``ChannelDef`` for every field in ``TelemetrySample``."""
    defs: list[ChannelDef] = []
    for name in TelemetrySample.field_names():
        if name in _CHANNEL_META:
            dtype, units, missing, desc = _CHANNEL_META[name]
        else:
            # Fallback for any new field not yet catalogued
            dtype, units, missing, desc = ("string", None, True, None)
        defs.append(ChannelDef(
            canonical_name=name,
            dtype=dtype,
            units=units,
            missing_allowed=missing,
            description=desc,
            source_names=mapping_source_names(name),
        ))
    return defs


def build_channels_payload() -> dict[str, object]:
    """Return versioned channels.json payload."""
    return {
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "channels": [d.to_dict() for d in build_channel_defs()],
    }


def _infer_raw_dtype(value: Any) -> str:
    """Infer a conservative manifest dtype from a sample raw value."""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int64"
    if isinstance(value, float):
        return "float64"
    if isinstance(value, str):
        return "string"
    return "float64"


def build_raw_channels_payload(
    column_names: list[str],
    *,
    preview_row: dict[str, Any] | None = None,
) -> dict[str, object]:
    """Build a generic raw-channel manifest from flattened column names."""
    channels: list[dict[str, Any]] = []
    for col in column_names:
        _, sep, remainder = col.partition("__")
        raw_field_name = remainder if sep else col
        parts = raw_field_name.rsplit("__", 1)
        is_array = len(parts) == 2 and parts[1].isdigit()
        preview_value = preview_row.get(col) if preview_row else None
        channels.append({
            "column_name": col,
            "raw_field_name": raw_field_name,
            "is_array_element": is_array,
            "dtype": _infer_raw_dtype(preview_value),
            "units": None,
            "description": None,
            "missing_allowed": True,
        })

    return {
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "channel_count": len(channels),
        "channels": channels,
    }


def build_raw_iracing_channels_payload(
    column_names: list[str],
    var_schema: list[dict[str, Any]] | None = None,
) -> dict[str, object]:
    """Build a channels_iracing_raw.json payload from actual column names.

    If *var_schema* (the 332-var inventory) is provided, it is used to
    attach unit and description metadata to matching columns.
    """
    # Build a lookup from var name to schema entry
    schema_lookup: dict[str, dict[str, Any]] = {}
    if var_schema:
        for entry in var_schema:
            schema_lookup[entry.get("name", "")] = entry

    channels: list[dict[str, Any]] = []
    for col in column_names:
        # Strip the irsdk__ prefix and any array suffix to find the base var
        base = col
        if base.startswith("irsdk__"):
            base = base[7:]  # len("irsdk__")
        # Strip array suffix (e.g. __0, __42)
        parts = base.rsplit("__", 1)
        var_name = parts[0] if len(parts) == 2 and parts[1].isdigit() else base

        schema_entry = schema_lookup.get(var_name, {})
        unit = schema_entry.get("unit") or None
        desc = schema_entry.get("desc") or None
        count = schema_entry.get("count", 1)
        is_array = count > 1

        channels.append({
            "column_name": col,
            "irsdk_var_name": var_name,
            "is_array_element": is_array,
            "dtype": "float64",  # conservative default; actual types vary
            "units": unit,
            "description": desc,
            "missing_allowed": True,
        })

    return {
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "channel_count": len(channels),
        "channels": channels,
    }


def _detect_column_prefix(column_names: list[str]) -> str | None:
    """Detect common ``<sim>__`` prefix from column names.

    For example, columns like ``["ac__physics__gas", "ac__graphics__status"]``
    share the prefix ``"ac__"``.
    """
    if not column_names:
        return None
    # Take the first column, find the first "__" — that's the sim tag boundary
    first = column_names[0]
    sep_idx = first.find("__")
    if sep_idx < 1:
        return None
    candidate = first[: sep_idx + 2]  # e.g. "ac__"
    # Verify at least half the columns share this prefix
    matching = sum(1 for col in column_names if col.startswith(candidate))
    if matching >= len(column_names) // 2:
        return candidate
    return None


