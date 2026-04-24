"""Tests for sim-specific raw telemetry normalization into canonical schema."""

from __future__ import annotations

from lap_coach_logger.normalization.mapper import TELEMETRY_SCHEMA_VERSION, mapping_source_names, normalise_sample


def test_iracing_normalizes_into_canonical_fields() -> None:
    sample = normalise_sample(
        {
            "SessionTime": 12.5,
            "Lap": 3,
            "LapDist": 1534.2,
            "Speed": 40.0,
            "Throttle": 0.8,
            "Brake": 0.1,
            "Clutch": 0.0,
            "SteeringWheelAngle": 0.174532925,
            "Gear": 4,
            "RPM": 6500,
            "Lat": 100.0,
            "Alt": 5.0,
            "Lon": 250.0,
            "Yaw": 1.570796326,
            "LatAccel": 1.1,
            "LongAccel": 0.4,
            "TrackTempCrew": 31.5,
            "AirTemp": 22.0,
            "IsOnTrack": 1,
            "OnPitRoad": 0,
        },
        sim="iRacing",
        passthrough={"track_name": "Spa", "car_name": "GT3", "session_type": "race"},
    )

    assert sample.speed_kph == 144.0
    assert round(sample.steering_deg or 0.0, 3) == 10.0
    assert round(sample.yaw_deg or 0.0, 3) == 90.0
    assert sample.throttle_pct == 0.8
    assert sample.brake_pct == 0.1
    assert sample.world_pos_x == 100.0
    assert sample.track_temp_c == 31.5


def test_acc_normalizes_into_same_canonical_fields() -> None:
    sample = normalise_sample(
        {
            "iCurrentTime": 12500,
            "completedLaps": 3,
            "normalizedCarPosition": 0.5,
            "trackSPlineLength": 3068.4,
            "speedKmh": 144.0,
            "gas": 0.8,
            "brake": 0.1,
            "clutch": 0.0,
            "steerAngle": 0.174532925,
            "gear": 5,
            "rpms": 6500,
            "heading": 1.570796326,
            "accG_x": 1.1,
            "accG_z": 0.4,
            "roadTemp": 31.5,
            "airTemp": 22.0,
            "ABS": 4,
            "TC": 3,
            "status": 2,
            "isInPit": 0,
            "session": 2,
            "packetId": 91,
        },
        sim="ACC",
        passthrough={"track_name": "Spa", "car_name": "GT3"},
    )

    assert sample.session_time_s == 12.5
    assert sample.lap_distance_m == 1534.2
    assert sample.speed_kph == 144.0
    assert round(sample.steering_deg or 0.0, 3) == 10.0
    assert round(sample.yaw_deg or 0.0, 3) == 90.0
    assert sample.throttle_pct == 0.8
    assert sample.brake_pct == 0.1
    assert sample.abs_level == 4.0
    assert sample.tc_level == 3.0
    assert sample.track_temp_c == 31.5


def test_assetto_corsa_normalizes_into_same_canonical_fields() -> None:
    sample = normalise_sample(
        {
            "iCurrentTime": 12500,
            "completedLaps": 3,
            "normalizedCarPosition": 0.5,
            "trackSPlineLength": 3068.4,
            "speedKmh": 144.0,
            "gas": 0.8,
            "brake": 0.1,
            "clutch": 0.0,
            "steerAngle": 0.174532925,
            "gear": 5,
            "rpms": 6500,
            "heading": 1.570796326,
            "accG_x": 1.1,
            "accG_z": 0.4,
            "roadTemp": 31.5,
            "airTemp": 22.0,
            "abs": 2.0,
            "tc": 1.0,
            "status": 2,
            "isInPit": 0,
            "session": 2,
            "packetId": 91,
        },
        sim="Assetto Corsa",
        passthrough={"track_name": "Spa", "car_name": "GT3"},
    )

    assert sample.session_time_s == 12.5
    assert sample.lap_distance_m == 1534.2
    assert sample.speed_kph == 144.0
    assert round(sample.steering_deg or 0.0, 3) == 10.0
    assert round(sample.yaw_deg or 0.0, 3) == 90.0
    assert sample.throttle_pct == 0.8
    assert sample.brake_pct == 0.1
    assert sample.abs_level == 2.0
    assert sample.tc_level == 1.0
    assert sample.track_temp_c == 31.5


def test_unavailable_channels_are_null_not_missing() -> None:
    sample = normalise_sample({"speedKmh": 100.0}, sim="ACC")
    row = sample.to_dict()
    assert "world_pos_x" in row
    assert "abs_level" in row
    assert row["world_pos_x"] is None
    assert row["abs_level"] is None


def test_lmu_live_fields_normalize_into_same_canonical_fields() -> None:
    sample = normalise_sample(
        {
            "Session Time": 123.4,
            "Lap": 5,
            "Lap Dist": 6813.0,
            "Lap Dist Pct": 0.5,
            "Ground Speed": 69.0,
            "Throttle Pos": 0.82,
            "Brake Pos": 0.08,
            "Clutch Pos": 0.02,
            "Steered Angle": 45.0,
            "Gear": 4,
            "Engine RPM": 7200.0,
            "World Pos X": 100.0,
            "World Pos Y": 2.5,
            "World Pos Z": 250.0,
            "Lateral Acceleration": 0.31,
            "Longitudinal Acceleration": 0.46,
            "Track Temperature": 29.0,
            "Ambient Temperature": 21.5,
            "Fuel Level": 41.5,
            "Engine Water Temp": 91.0,
            "Engine Oil Temp": 102.0,
            "Tyre Temp LF": 83.0,
            "Tyre Temp RF": 84.0,
            "Tyre Temp LR": 81.0,
            "Tyre Temp RR": 82.0,
            "In Pits": 0,
        },
        sim="Le Mans Ultimate",
        passthrough={"track_name": "Circuit de la Sarthe", "car_name": "Toyota GR010"},
    )

    assert sample.session_time_s == 123.4
    assert sample.lap_dist_pct == 0.5
    assert round(sample.speed_kph or 0.0, 1) == 248.4
    assert sample.clutch_pct == 0.02
    assert sample.world_pos_x == 100.0
    assert round(sample.tyre_temp_lf or 0.0, 2) == 83.0


def test_source_traceability_in_mapping_registry() -> None:
    source_names = mapping_source_names("speed_kph")
    assert source_names["iRacing"] == "Speed"
    assert source_names["Assetto Corsa"] == "speedKmh"
    assert source_names["ACC"] == "speedKmh"
    assert source_names["Le Mans Ultimate"] == "Ground Speed, GPS Speed"
    assert TELEMETRY_SCHEMA_VERSION == "2.0.0"
