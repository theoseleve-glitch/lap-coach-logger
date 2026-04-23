"""Tests for null-safe schema handling."""

from lap_coach_logger.core.schema import TelemetrySample


def test_default_sample_has_none_channels() -> None:
    sample = TelemetrySample()
    d = sample.to_dict()
    # All dynamic channels should be None
    for key in ["speed_kph", "throttle_pct", "brake_pct", "steering_deg", "clutch_pct",
                 "gear", "rpm", "abs_level", "tc_level",
                 "world_pos_x", "world_pos_y", "world_pos_z", "yaw_deg", "pitch", "roll",
                 "long_accel_g", "lat_accel_g", "lap_number", "lap_distance_m",
                 "lap_dist_pct",
                 "tyre_temp_lf", "tyre_temp_rf", "tyre_temp_lr", "tyre_temp_rr",
                 "fuel_level", "fuel_capacity",
                 "water_temp", "oil_temp", "track_temp_c", "air_temp_c",
                 "is_on_track", "is_in_pits",
                 "track_name", "car_name", "session_type", "raw_source_timestamp"]:
        assert d[key] is None, f"{key} should be None by default"


def test_partial_construction() -> None:
    """Only some fields provided — rest stays None."""
    sample = TelemetrySample(sim="iRacing", speed_kph=142.5, gear=4)
    assert sample.sim == "iRacing"
    assert sample.speed_kph == 142.5
    assert sample.gear == 4
    assert sample.brake_pct is None
    assert sample.world_pos_x is None


def test_to_dict_roundtrip() -> None:
    sample = TelemetrySample(sim="ACC", throttle_pct=0.85)
    d = sample.to_dict()
    assert isinstance(d, dict)
    assert d["sim"] == "ACC"
    assert d["throttle_pct"] == 0.85
    assert d["brake_pct"] is None


def test_field_names_complete() -> None:
    names = TelemetrySample.field_names()
    assert "timestamp_utc" in names
    assert "speed_kph" in names
    assert "raw_source_timestamp" in names
    assert len(names) == 47
