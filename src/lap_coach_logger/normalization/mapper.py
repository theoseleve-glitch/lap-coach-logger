"""Simulator-specific raw-to-canonical telemetry mapping utilities."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Callable

from lap_coach_logger.adapters.acc_shm_structs import SESSION_TYPE_MAP
from lap_coach_logger.core.schema import TELEMETRY_SCHEMA_VERSION, TelemetrySample

log = logging.getLogger(__name__)


Extractor = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class MappingRule:
    source_names: tuple[str, ...]
    extractor: Extractor


def clamp(value: float | None, lo: float, hi: float) -> float | None:
    """Clamp *value* to [lo, hi], returning None if input is None."""
    if value is None:
        return None
    return max(lo, min(hi, value))


def mps_to_kph(mps: float | None) -> float | None:
    """Convert metres-per-second to km/h."""
    return mps * 3.6 if mps is not None else None


def rad_to_deg(value: float | None) -> float | None:
    if value is None:
        return None
    return math.degrees(value)


def clean_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        parsed = float(value)
        if math.isnan(parsed) or math.isinf(parsed):
            return None
        return parsed
    except Exception:
        return None


def clean_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def clean_bool(value: Any) -> bool | None:
    return None if value is None else bool(value)


def first_float(raw: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in raw:
            value = clean_float(raw.get(key))
            if value is not None:
                return value
    return None


def first_int(raw: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        if key in raw:
            value = clean_int(raw.get(key))
            if value is not None:
                return value
    return None


def first_bool(raw: dict[str, Any], *keys: str) -> bool | None:
    for key in keys:
        if key in raw:
            value = clean_bool(raw.get(key))
            if value is not None:
                return value
    return None


def _iracing_gear(raw: dict[str, Any]) -> int | None:
    return first_int(raw, "Gear")


def _acc_gear(raw: dict[str, Any]) -> int | None:
    gear = first_int(raw, "gear")
    if gear is None:
        return None
    return gear - 1 if gear >= 2 else (0 if gear == 1 else -1)


def _acc_session_time_s(raw: dict[str, Any]) -> float | None:
    current_ms = first_float(raw, "iCurrentTime")
    return (current_ms / 1000.0) if current_ms and current_ms > 0 else None


def _acc_session_type(raw: dict[str, Any]) -> str | None:
    session_code = first_int(raw, "session")
    return SESSION_TYPE_MAP.get(session_code, "unknown") if session_code is not None else None


def _acc_lap_number(raw: dict[str, Any]) -> int | None:
    return first_int(raw, "completedLaps")


def _acc_lap_distance(raw: dict[str, Any]) -> float | None:
    norm_pos = first_float(raw, "normalizedCarPosition")
    length = first_float(raw, "trackSPlineLength")
    if norm_pos is None or length is None or length <= 0:
        return None
    return norm_pos * length


def _session_type_passthrough(raw: dict[str, Any]) -> str | None:
    value = raw.get("session_type")
    return str(value) if value is not None else None


def _lmu_gear(raw: dict[str, Any]) -> int | None:
    return first_int(raw, "Gear")


SIM_FIELD_MAPPINGS: dict[str, dict[str, MappingRule]] = {
    "Le Mans Ultimate": {
        "session_time_s": MappingRule(("Session Time",), lambda raw: first_float(raw, "Session Time")),
        "lap_number": MappingRule(("Lap",), lambda raw: first_int(raw, "Lap")),
        "lap_distance_m": MappingRule(("Lap Dist",), lambda raw: first_float(raw, "Lap Dist")),
        "lap_dist_pct": MappingRule(("Lap Dist Pct",), lambda raw: first_float(raw, "Lap Dist Pct")),
        "speed_kph": MappingRule(("Ground Speed",), lambda raw: mps_to_kph(first_float(raw, "Ground Speed"))),
        "throttle_pct": MappingRule(("Throttle Pos",), lambda raw: first_float(raw, "Throttle Pos")),
        "brake_pct": MappingRule(("Brake Pos",), lambda raw: first_float(raw, "Brake Pos")),
        "clutch_pct": MappingRule(("Clutch Pos",), lambda raw: first_float(raw, "Clutch Pos")),
        "steering_deg": MappingRule(("Steered Angle",), lambda raw: first_float(raw, "Steered Angle")),
        "gear": MappingRule(("Gear",), _lmu_gear),
        "rpm": MappingRule(("Engine RPM",), lambda raw: first_float(raw, "Engine RPM")),
        "world_pos_x": MappingRule(("World Pos X",), lambda raw: first_float(raw, "World Pos X")),
        "world_pos_y": MappingRule(("World Pos Y",), lambda raw: first_float(raw, "World Pos Y")),
        "world_pos_z": MappingRule(("World Pos Z",), lambda raw: first_float(raw, "World Pos Z")),
        "lat_accel_g": MappingRule(("Lateral Acceleration",), lambda raw: first_float(raw, "Lateral Acceleration")),
        "long_accel_g": MappingRule(("Longitudinal Acceleration",), lambda raw: first_float(raw, "Longitudinal Acceleration")),
        "track_temp_c": MappingRule(("Track Temperature",), lambda raw: first_float(raw, "Track Temperature")),
        "air_temp_c": MappingRule(("Ambient Temperature",), lambda raw: first_float(raw, "Ambient Temperature")),
        "tyre_temp_lf": MappingRule(("Tyre Temp LF",), lambda raw: first_float(raw, "Tyre Temp LF")),
        "tyre_temp_rf": MappingRule(("Tyre Temp RF",), lambda raw: first_float(raw, "Tyre Temp RF")),
        "tyre_temp_lr": MappingRule(("Tyre Temp LR",), lambda raw: first_float(raw, "Tyre Temp LR")),
        "tyre_temp_rr": MappingRule(("Tyre Temp RR",), lambda raw: first_float(raw, "Tyre Temp RR")),
        "fuel_level": MappingRule(("Fuel Level",), lambda raw: first_float(raw, "Fuel Level")),
        "water_temp": MappingRule(("Engine Water Temp",), lambda raw: first_float(raw, "Engine Water Temp")),
        "oil_temp": MappingRule(("Engine Oil Temp",), lambda raw: first_float(raw, "Engine Oil Temp")),
        "is_in_pits": MappingRule(("In Pits",), lambda raw: first_bool(raw, "In Pits")),
        "raw_source_timestamp": MappingRule(("Session Time",), lambda raw: first_float(raw, "Session Time")),
    },
    "iRacing": {
        "session_time_s": MappingRule(("SessionTime",), lambda raw: first_float(raw, "SessionTime")),
        "lap_number": MappingRule(("Lap",), lambda raw: first_int(raw, "Lap")),
        "lap_distance_m": MappingRule(("LapDist",), lambda raw: first_float(raw, "LapDist")),
        "lap_dist_pct": MappingRule(("LapDistPct",), lambda raw: first_float(raw, "LapDistPct")),
        "speed_kph": MappingRule(("Speed",), lambda raw: mps_to_kph(first_float(raw, "Speed"))),
        "throttle_pct": MappingRule(("Throttle",), lambda raw: first_float(raw, "Throttle")),
        "brake_pct": MappingRule(("Brake",), lambda raw: first_float(raw, "Brake")),
        "clutch_pct": MappingRule(("Clutch",), lambda raw: first_float(raw, "Clutch")),
        "steering_deg": MappingRule(("SteeringWheelAngle",), lambda raw: rad_to_deg(first_float(raw, "SteeringWheelAngle"))),
        "gear": MappingRule(("Gear",), _iracing_gear),
        "rpm": MappingRule(("RPM",), lambda raw: first_float(raw, "RPM")),
        "world_pos_x": MappingRule(("Lat",), lambda raw: first_float(raw, "Lat")),
        "world_pos_y": MappingRule(("Alt",), lambda raw: first_float(raw, "Alt")),
        "world_pos_z": MappingRule(("Lon",), lambda raw: first_float(raw, "Lon")),
        "yaw_deg": MappingRule(("Yaw",), lambda raw: rad_to_deg(first_float(raw, "Yaw"))),
        "lat_accel_g": MappingRule(("LatAccel",), lambda raw: first_float(raw, "LatAccel")),
        "long_accel_g": MappingRule(("LongAccel",), lambda raw: first_float(raw, "LongAccel")),
        "track_temp_c": MappingRule(("TrackTempCrew",), lambda raw: first_float(raw, "TrackTempCrew")),
        "air_temp_c": MappingRule(("AirTemp",), lambda raw: first_float(raw, "AirTemp")),
        "abs_level": MappingRule(("dcABS",), lambda raw: first_float(raw, "dcABS")),
        "tc_level": MappingRule(("dcTractionControl",), lambda raw: first_float(raw, "dcTractionControl")),
        "pitch": MappingRule(("Pitch",), lambda raw: first_float(raw, "Pitch")),
        "roll": MappingRule(("Roll",), lambda raw: first_float(raw, "Roll")),
        "tyre_temp_lf": MappingRule(("LFtempCL",), lambda raw: first_float(raw, "LFtempCL")),
        "tyre_temp_rf": MappingRule(("RFtempCL",), lambda raw: first_float(raw, "RFtempCL")),
        "tyre_temp_lr": MappingRule(("LRtempCL",), lambda raw: first_float(raw, "LRtempCL")),
        "tyre_temp_rr": MappingRule(("RRtempCL",), lambda raw: first_float(raw, "RRtempCL")),
        "fuel_level": MappingRule(("FuelLevel",), lambda raw: first_float(raw, "FuelLevel")),
        "water_temp": MappingRule(("WaterTemp",), lambda raw: first_float(raw, "WaterTemp")),
        "oil_temp": MappingRule(("OilTemp",), lambda raw: first_float(raw, "OilTemp")),
        "is_on_track": MappingRule(("IsOnTrack",), lambda raw: first_bool(raw, "IsOnTrack")),
        "is_in_pits": MappingRule(("OnPitRoad",), lambda raw: first_bool(raw, "OnPitRoad")),
        "raw_source_timestamp": MappingRule(("SessionTime",), lambda raw: first_float(raw, "SessionTime")),
    },
    "ACC": {
        "session_time_s": MappingRule(("iCurrentTime",), _acc_session_time_s),
        "lap_number": MappingRule(("completedLaps",), _acc_lap_number),
        "lap_distance_m": MappingRule(("normalizedCarPosition", "trackSPlineLength"), _acc_lap_distance),
        "lap_dist_pct": MappingRule(("normalizedCarPosition",), lambda raw: first_float(raw, "normalizedCarPosition")),
        "speed_kph": MappingRule(("speedKmh",), lambda raw: first_float(raw, "speedKmh")),
        "throttle_pct": MappingRule(("gas",), lambda raw: first_float(raw, "gas")),
        "brake_pct": MappingRule(("brake",), lambda raw: first_float(raw, "brake")),
        "clutch_pct": MappingRule(("clutch",), lambda raw: first_float(raw, "clutch")),
        "steering_deg": MappingRule(("steerAngle",), lambda raw: rad_to_deg(first_float(raw, "steerAngle"))),
        "gear": MappingRule(("gear",), _acc_gear),
        "rpm": MappingRule(("rpms",), lambda raw: first_float(raw, "rpms")),
        "world_pos_x": MappingRule((), lambda raw: None),
        "world_pos_y": MappingRule((), lambda raw: None),
        "world_pos_z": MappingRule((), lambda raw: None),
        "yaw_deg": MappingRule(("heading",), lambda raw: rad_to_deg(first_float(raw, "heading"))),
        "lat_accel_g": MappingRule(("accG[0]", "accG_x"), lambda raw: first_float(raw, "accG_x")),
        "long_accel_g": MappingRule(("accG[2]", "accG_z"), lambda raw: first_float(raw, "accG_z")),
        "track_temp_c": MappingRule(("roadTemp",), lambda raw: first_float(raw, "roadTemp")),
        "air_temp_c": MappingRule(("airTemp",), lambda raw: first_float(raw, "airTemp")),
        "abs_level": MappingRule(("ABS", "abs"), lambda raw: first_float(raw, "ABS", "abs")),
        "tc_level": MappingRule(("TC", "tc"), lambda raw: first_float(raw, "TC", "tc")),
        "pitch": MappingRule(("pitch",), lambda raw: first_float(raw, "pitch")),
        "roll": MappingRule(("roll",), lambda raw: first_float(raw, "roll")),
        "tyre_temp_lf": MappingRule(("tyreCoreTemperature_0",), lambda raw: first_float(raw, "tyreCoreTemperature_0")),
        "tyre_temp_rf": MappingRule(("tyreCoreTemperature_1",), lambda raw: first_float(raw, "tyreCoreTemperature_1")),
        "tyre_temp_lr": MappingRule(("tyreCoreTemperature_2",), lambda raw: first_float(raw, "tyreCoreTemperature_2")),
        "tyre_temp_rr": MappingRule(("tyreCoreTemperature_3",), lambda raw: first_float(raw, "tyreCoreTemperature_3")),
        "fuel_level": MappingRule(("fuel",), lambda raw: first_float(raw, "fuel")),
        "water_temp": MappingRule(("waterTemp",), lambda raw: first_float(raw, "waterTemp")),
        "oil_temp": MappingRule((), lambda raw: None),
        "is_on_track": MappingRule(("status",), lambda raw: first_int(raw, "status") == 2 if first_int(raw, "status") is not None else None),
        "is_in_pits": MappingRule(("isInPit",), lambda raw: first_bool(raw, "isInPit")),
        "session_type": MappingRule(("session",), _acc_session_type),
        "raw_source_timestamp": MappingRule(("packetId",), lambda raw: first_float(raw, "packetId")),
    },
}


def mapping_source_names(canonical_name: str) -> dict[str, str | None]:
    """Return raw source-name traceability for one canonical field."""
    result: dict[str, str | None] = {}
    for sim, mapping in SIM_FIELD_MAPPINGS.items():
        rule = mapping.get(canonical_name)
        result[sim] = ", ".join(rule.source_names) if rule and rule.source_names else None
    return result


def normalise_sample(
    raw: dict[str, Any],
    *,
    sim: str,
    passthrough: dict[str, Any] | None = None,
) -> TelemetrySample:
    """Build a canonical ``TelemetrySample`` from sim-native raw fields."""
    data = {field: None for field in TelemetrySample.field_names()}
    data["sim"] = sim

    mapping = SIM_FIELD_MAPPINGS.get(sim, {})
    for canonical_name, rule in mapping.items():
        try:
            data[canonical_name] = rule.extractor(raw)
        except Exception:
            log.debug("Failed to normalise field %s for %s", canonical_name, sim, exc_info=True)
            data[canonical_name] = None

    if passthrough:
        for key, value in passthrough.items():
            if key in data:
                data[key] = value

    try:
        return TelemetrySample(**data)
    except TypeError:
        log.warning("Unexpected fields while normalising sample for %s", sim)
        return TelemetrySample(sim=sim)


__all__ = [
    "MappingRule",
    "SIM_FIELD_MAPPINGS",
    "TELEMETRY_SCHEMA_VERSION",
    "mapping_source_names",
    "normalise_sample",
]
