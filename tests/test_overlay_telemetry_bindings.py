from __future__ import annotations

from dataclasses import dataclass

from lap_coach_logger.overlays import (
    OverlayDefinition,
    OverlayLayoutHints,
    build_example_overlay_telemetry_binding_service,
)


def test_core_driving_hud_binding_resolves_live_values_and_reports_healthy() -> None:
    service = build_example_overlay_telemetry_binding_service()

    result = service.bind(
        "core_driving_hud",
        {
            "status": "Recording",
            "sim": "ACC",
            "data_staleness_s": 0.15,
            "live": {
                "timestamp_utc": "2026-04-01T10:00:00+00:00",
                "speed_kph": 231.8,
                "gear": 6,
                "rpm": 7581.0,
                "lap_time_s": 81.442,
                "live_delta_s": -0.117,
                "sector_1_time_s": 25.8,
                "sector_2_time_s": 28.2,
                "sector_3_time_s": 27.4,
                "fuel_level": 44.2,
                "flag_state": "Green",
                "tyre_temp_fl": 79.0,
                "brake_temp_fl": 521.0,
            },
        },
    )

    assert result.health.status == "healthy"
    assert result.values["speed_kph"] == 231.8
    assert result.values["gear"] == 6
    assert result.values["rpm"] == 7581.0
    assert result.values["live_delta_s"] == -0.117
    assert result.values["flag_state"] == "Green"
    assert result.field_health_map()["speed_kph"].status == "ok"


def test_binding_health_reports_invalid_and_stale_fields_explicitly() -> None:
    service = build_example_overlay_telemetry_binding_service()

    result = service.bind(
        "track_map",
        {
            "data_staleness_s": 4.1,
            "live": {
                "timestamp_utc": "2026-04-01T10:00:00+00:00",
                "world_pos_x": "far",
                "world_pos_z": -18.6,
            },
        },
    )

    assert result.health.status == "invalid"
    assert "world_pos_x" in result.health.invalid_field_keys
    assert result.values["world_pos_x"] is None
    assert result.field_health_map()["world_pos_y"].status == "stale"


def test_relative_table_missing_rows_reports_missing_required_health() -> None:
    service = build_example_overlay_telemetry_binding_service()

    result = service.bind_for_overlay_key(
        "standings",
        {
            "data_staleness_s": 0.2,
            "live": {
                "timestamp_utc": "2026-04-01T10:00:00+00:00",
                "player_position": 5,
            },
        },
    )

    assert result.contract_id == "relative_table"
    assert result.health.status == "missing"
    assert result.health.missing_field_keys == ("relative_rows",)
    assert result.field_health_map()["relative_rows"].status == "missing"


def test_preview_provider_generates_preview_binding_for_track_map_alias() -> None:
    service = build_example_overlay_telemetry_binding_service()

    result = service.preview_binding_for_overlay_key("track_map_overlay")

    assert result.preview_mode is True
    assert result.contract_id == "track_map"
    assert result.health.status == "preview"
    assert isinstance(result.values["world_pos_x"], float)
    assert isinstance(result.values["world_pos_y"], float)
    assert result.values["track_name"] == "Preview Raceway"


def test_bind_for_definition_and_instance_resolves_contract_from_schema_ref_and_overlay_suffix() -> None:
    service = build_example_overlay_telemetry_binding_service()
    definition = OverlayDefinition(
        overlay_id="track_map_overlay",
        renderer_key="track_map_renderer",
        display_name="Track Map",
        short_description="Track map overlay.",
        category="telemetry",
        settings_schema_ref="track_map.v1",
        layout=OverlayLayoutHints(default_width=300, default_height=300),
    )

    by_definition = service.bind_for_definition(
        definition,
        {
            "data_staleness_s": 0.0,
            "live": {
                "timestamp_utc": "2026-04-01T10:00:00+00:00",
                "world_pos_x": 91.5,
                "world_pos_z": -12.4,
            },
        },
    )

    @dataclass(slots=True)
    class _Instance:
        overlay_id: str
        definition: OverlayDefinition

    by_instance = service.preview_binding_for_instance(
        _Instance(overlay_id="track_map_overlay", definition=definition)
    )

    assert by_definition.contract_id == "track_map"
    assert by_definition.values["world_pos_x"] == 91.5
    assert by_definition.values["world_pos_y"] == -12.4
    assert by_instance.health.status == "preview"
