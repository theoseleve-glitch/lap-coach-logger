from __future__ import annotations

import pytest

from lap_coach_logger.overlays import (
    OverlaySettingsSchemaRegistry,
    OverlaySettingsSchemaService,
    build_example_overlay_settings_service,
    example_overlay_settings_schemas,
)


def test_example_overlay_settings_registry_contains_expected_schemas() -> None:
    schemas = example_overlay_settings_schemas()
    registry = OverlaySettingsSchemaRegistry(schemas)

    assert {schema.schema_id for schema in registry.list_schemas()} == {
        "core_driving_hud",
        "delta_widget",
        "relative_table",
        "track_map",
    }
    assert registry.get("core_driving_hud").version == 1
    assert registry.get("delta_widget").version == 2


def test_default_value_resolver_exposes_schema_defaults() -> None:
    service = build_example_overlay_settings_service()

    defaults = service.default_values("core_driving_hud")

    assert defaults["width"] == 480
    assert defaults["height"] == 220
    assert defaults["scale"] == pytest.approx(1.0)
    assert defaults["use_glass_background"] is True
    assert defaults["pin_mode"] == "always_on_top"


def test_merge_overrides_coerces_values_and_applies_limits() -> None:
    service = build_example_overlay_settings_service()

    resolution = service.merge_overrides(
        "core_driving_hud",
        {
            "width": "900",
            "opacity": "0.55",
            "inactive_opacity": "0.95",
            "compactness": "spacious",
            "click_through": "yes",
            "show_hide_condition": "session_only",
            "unknown_value": 12,
        },
    )

    assert resolution.values["width"] == 900
    assert resolution.values["opacity"] == pytest.approx(0.55)
    assert resolution.values["inactive_opacity"] == pytest.approx(0.55)
    assert resolution.values["compactness"] == "spacious"
    assert resolution.values["click_through"] is True
    assert resolution.values["show_hide_condition"] == "session_only"
    assert any(issue.code == "unknown_field" for issue in resolution.issues)
    assert any(issue.code == "rule_less_than_or_equal_field" for issue in resolution.issues)


def test_visibility_conditions_hide_glass_controls_when_background_disabled() -> None:
    service = build_example_overlay_settings_service()

    resolution = service.merge_overrides(
        "core_driving_hud",
        {
            "use_glass_background": False,
        },
    )

    assert "blur_strength" not in resolution.visible_field_keys
    assert "glass_darkness" not in resolution.visible_field_keys
    assert "border_thickness" in resolution.visible_field_keys


def test_delta_widget_migration_renames_legacy_fields() -> None:
    service = build_example_overlay_settings_service()

    resolution = service.merge_overrides(
        "delta_widget",
        {
            "inactive_alpha": 0.42,
            "show_reference_badge": False,
        },
        source_version=1,
    )

    assert resolution.migrated_from_version == 1
    assert resolution.values["inactive_opacity"] == pytest.approx(0.4)
    assert resolution.values["show_reference_chip"] is False
    assert any(issue.code == "migration_applied" for issue in resolution.issues)


def test_track_map_schema_supports_auto_form_generation_metadata() -> None:
    service = build_example_overlay_settings_service()
    schema = service.schema("track_map")

    field = schema.field("anchor_preset")
    assert field is not None
    assert field.kind == "anchor_preset"
    assert field.section == "behavior"
    assert field.label == "Anchor Preset"

    accent = schema.field("accent_color_token")
    assert accent is not None
    assert accent.kind == "color_token"
    assert len(accent.options) >= 3

