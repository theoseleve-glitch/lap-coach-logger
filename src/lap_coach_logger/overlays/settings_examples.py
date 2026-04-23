"""Example overlay settings schemas for LAP COACH."""

from __future__ import annotations

from lap_coach_logger.overlays.settings_models import (
    OverlaySettingsField,
    OverlaySettingsOption,
    OverlaySettingsSchema,
    OverlaySettingsValidationRule,
    OverlaySettingsVisibilityCondition,
)
from lap_coach_logger.overlays.settings_service import (
    OverlaySettingsSchemaMigrator,
    OverlaySettingsSchemaRegistry,
    OverlaySettingsSchemaService,
)

_PIN_MODE_OPTIONS = (
    OverlaySettingsOption("normal", "Normal"),
    OverlaySettingsOption("always_on_top", "Always On Top"),
    OverlaySettingsOption("layout_managed", "Layout Managed"),
)

_SHOW_HIDE_OPTIONS = (
    OverlaySettingsOption("always", "Always"),
    OverlaySettingsOption("live_only", "Live Session Only"),
    OverlaySettingsOption("session_only", "Session Only"),
    OverlaySettingsOption("telemetry_present", "When Telemetry Present"),
)

_METADATA_VISIBILITY_OPTIONS = (
    OverlaySettingsOption("full", "Full"),
    OverlaySettingsOption("compact", "Compact"),
    OverlaySettingsOption("hidden", "Hidden"),
)

_ACCENT_COLOR_OPTIONS = (
    OverlaySettingsOption("pit_orange", "Pit Orange"),
    OverlaySettingsOption("acid_green", "Acid Green"),
    OverlaySettingsOption("marshal_yellow", "Marshal Yellow"),
    OverlaySettingsOption("chalk", "Chalk"),
)


def example_overlay_settings_schemas() -> tuple[OverlaySettingsSchema, ...]:
    return (
        OverlaySettingsSchema(
            schema_id="core_driving_hud",
            overlay_key="core_driving_hud",
            version=1,
            title="Core Driving HUD",
            description="Primary on-track HUD with glass styling, pinning, and visibility behavior.",
            fields=(
                OverlaySettingsField("width", "Width", "integer", "performance_and_size", 480, min_value=240, max_value=1600, step=10, unit="px"),
                OverlaySettingsField("height", "Height", "integer", "performance_and_size", 220, min_value=120, max_value=900, step=10, unit="px"),
                OverlaySettingsField("scale", "Scale", "range", "performance_and_size", 1.0, min_value=0.6, max_value=2.0, step=0.05, numeric_mode="float"),
                OverlaySettingsField("font_scale", "Font Scale", "range", "performance_and_size", 1.0, min_value=0.7, max_value=1.8, step=0.05, numeric_mode="float"),
                OverlaySettingsField("compactness", "Compactness", "spacing_token", "performance_and_size", "normal"),
                OverlaySettingsField("opacity", "Opacity", "range", "appearance", 0.94, min_value=0.3, max_value=1.0, step=0.05, numeric_mode="float"),
                OverlaySettingsField("use_glass_background", "Glass Background", "boolean", "appearance", True),
                OverlaySettingsField(
                    "blur_strength",
                    "Blur Strength",
                    "range",
                    "appearance",
                    0.45,
                    min_value=0.0,
                    max_value=1.0,
                    step=0.05,
                    numeric_mode="float",
                    visibility_conditions=(OverlaySettingsVisibilityCondition("use_glass_background", "truthy"),),
                ),
                OverlaySettingsField(
                    "glass_darkness",
                    "Glass Darkness",
                    "range",
                    "appearance",
                    0.4,
                    min_value=0.0,
                    max_value=1.0,
                    step=0.05,
                    numeric_mode="float",
                    visibility_conditions=(OverlaySettingsVisibilityCondition("use_glass_background", "truthy"),),
                ),
                OverlaySettingsField("border_thickness", "Border Thickness", "float", "appearance", 1.0, min_value=0.0, max_value=4.0, step=0.25, unit="px"),
                OverlaySettingsField("accent_intensity", "Accent Intensity", "range", "appearance", 0.7, min_value=0.0, max_value=1.0, step=0.05, numeric_mode="float"),
                OverlaySettingsField("metadata_visibility", "Metadata Visibility", "enum", "visibility", "full", options=_METADATA_VISIBILITY_OPTIONS),
                OverlaySettingsField(
                    "inactive_opacity",
                    "Inactive Opacity",
                    "range",
                    "visibility",
                    0.55,
                    min_value=0.1,
                    max_value=1.0,
                    step=0.05,
                    numeric_mode="float",
                    validation_rules=(
                        OverlaySettingsValidationRule(
                            "less_than_or_equal_field",
                            other_field_key="opacity",
                            message="Inactive opacity cannot exceed active opacity.",
                        ),
                    ),
                ),
                OverlaySettingsField("show_hide_condition", "Show/Hide Condition", "enum", "visibility", "live_only", options=_SHOW_HIDE_OPTIONS),
                OverlaySettingsField("pin_mode", "Pin Mode", "enum", "behavior", "always_on_top", options=_PIN_MODE_OPTIONS),
                OverlaySettingsField("click_through", "Click-Through", "boolean", "behavior", False),
                OverlaySettingsField("lock_position", "Lock Position", "boolean", "behavior", False),
                OverlaySettingsField("debug_overlay_id", "Debug Overlay Id", "enum", "advanced", "core", options=(OverlaySettingsOption("core", "Core"), OverlaySettingsOption("full", "Full")), advanced=True),
            ),
        ),
        OverlaySettingsSchema(
            schema_id="delta_widget",
            overlay_key="delta_widget",
            version=2,
            title="Delta Widget",
            description="Delta-focused lap comparison overlay with reference and chip controls.",
            fields=(
                OverlaySettingsField("width", "Width", "integer", "performance_and_size", 420, min_value=240, max_value=1000, step=10, unit="px"),
                OverlaySettingsField("height", "Height", "integer", "performance_and_size", 180, min_value=100, max_value=400, step=10, unit="px"),
                OverlaySettingsField("scale", "Scale", "range", "performance_and_size", 1.0, min_value=0.6, max_value=2.0, step=0.05, numeric_mode="float"),
                OverlaySettingsField("opacity", "Opacity", "range", "appearance", 0.95, min_value=0.3, max_value=1.0, step=0.05, numeric_mode="float"),
                OverlaySettingsField("accent_color_token", "Accent Color", "color_token", "appearance", "pit_orange", options=_ACCENT_COLOR_OPTIONS),
                OverlaySettingsField("show_reference_chip", "Reference Chip", "boolean", "visibility", True),
                OverlaySettingsField("show_gain_loss_markers", "Gain/Loss Markers", "boolean", "visibility", True),
                OverlaySettingsField("show_hide_condition", "Show/Hide Condition", "enum", "visibility", "live_only", options=_SHOW_HIDE_OPTIONS),
                OverlaySettingsField("pin_mode", "Pin Mode", "enum", "behavior", "always_on_top", options=_PIN_MODE_OPTIONS),
                OverlaySettingsField("click_through", "Click-Through", "boolean", "behavior", False),
                OverlaySettingsField("lock_position", "Lock Position", "boolean", "behavior", False),
                OverlaySettingsField(
                    "inactive_opacity",
                    "Inactive Opacity",
                    "range",
                    "advanced",
                    0.5,
                    min_value=0.1,
                    max_value=1.0,
                    step=0.05,
                    numeric_mode="float",
                    advanced=True,
                    validation_rules=(
                        OverlaySettingsValidationRule(
                            "less_than_or_equal_field",
                            other_field_key="opacity",
                            message="Inactive opacity cannot exceed active opacity.",
                        ),
                    ),
                ),
            ),
        ),
        OverlaySettingsSchema(
            schema_id="relative_table",
            overlay_key="relative_table",
            version=1,
            title="Relative Table",
            description="Nearby-car table with metadata density, anchor presets, and behavior toggles.",
            fields=(
                OverlaySettingsField("width", "Width", "integer", "performance_and_size", 360, min_value=260, max_value=960, step=10, unit="px"),
                OverlaySettingsField("height", "Height", "integer", "performance_and_size", 260, min_value=140, max_value=900, step=10, unit="px"),
                OverlaySettingsField("font_scale", "Font Scale", "range", "performance_and_size", 1.0, min_value=0.7, max_value=1.8, step=0.05, numeric_mode="float"),
                OverlaySettingsField("compactness", "Compactness", "spacing_token", "performance_and_size", "compact"),
                OverlaySettingsField("opacity", "Opacity", "range", "appearance", 0.92, min_value=0.3, max_value=1.0, step=0.05, numeric_mode="float"),
                OverlaySettingsField("accent_intensity", "Accent Intensity", "range", "appearance", 0.6, min_value=0.0, max_value=1.0, step=0.05, numeric_mode="float"),
                OverlaySettingsField("metadata_visibility", "Metadata Visibility", "enum", "visibility", "compact", options=_METADATA_VISIBILITY_OPTIONS),
                OverlaySettingsField("inactive_opacity", "Inactive Opacity", "range", "visibility", 0.45, min_value=0.1, max_value=1.0, step=0.05, numeric_mode="float"),
                OverlaySettingsField("anchor_preset", "Anchor Preset", "anchor_preset", "behavior", "top_right"),
                OverlaySettingsField("pin_mode", "Pin Mode", "enum", "behavior", "layout_managed", options=_PIN_MODE_OPTIONS),
                OverlaySettingsField("click_through", "Click-Through", "boolean", "behavior", False),
                OverlaySettingsField("lock_position", "Lock Position", "boolean", "behavior", True),
                OverlaySettingsField("show_hide_condition", "Show/Hide Condition", "enum", "behavior", "telemetry_present", options=_SHOW_HIDE_OPTIONS),
                OverlaySettingsField("show_class_rows_only", "Class Rows Only", "boolean", "advanced", False, premium_only=True, advanced=True),
            ),
        ),
        OverlaySettingsSchema(
            schema_id="track_map",
            overlay_key="track_map",
            version=1,
            title="Track Map",
            description="Track map styling, anchor presets, and metadata visibility configuration.",
            fields=(
                OverlaySettingsField("width", "Width", "integer", "performance_and_size", 300, min_value=180, max_value=900, step=10, unit="px"),
                OverlaySettingsField("height", "Height", "integer", "performance_and_size", 300, min_value=180, max_value=900, step=10, unit="px"),
                OverlaySettingsField("scale", "Scale", "range", "performance_and_size", 1.0, min_value=0.7, max_value=2.0, step=0.05, numeric_mode="float"),
                OverlaySettingsField("map_padding", "Map Padding", "spacing_token", "performance_and_size", "normal"),
                OverlaySettingsField("opacity", "Opacity", "range", "appearance", 0.93, min_value=0.3, max_value=1.0, step=0.05, numeric_mode="float"),
                OverlaySettingsField("border_thickness", "Border Thickness", "float", "appearance", 1.0, min_value=0.0, max_value=4.0, step=0.25, unit="px"),
                OverlaySettingsField("accent_color_token", "Accent Color", "color_token", "appearance", "acid_green", options=_ACCENT_COLOR_OPTIONS),
                OverlaySettingsField("accent_intensity", "Accent Intensity", "range", "appearance", 0.7, min_value=0.0, max_value=1.0, step=0.05, numeric_mode="float"),
                OverlaySettingsField("metadata_visibility", "Metadata Visibility", "enum", "visibility", "compact", options=_METADATA_VISIBILITY_OPTIONS),
                OverlaySettingsField("show_corner_labels", "Corner Labels", "boolean", "visibility", False),
                OverlaySettingsField("inactive_opacity", "Inactive Opacity", "range", "visibility", 0.5, min_value=0.1, max_value=1.0, step=0.05, numeric_mode="float"),
                OverlaySettingsField("anchor_preset", "Anchor Preset", "anchor_preset", "behavior", "top_right"),
                OverlaySettingsField("pin_mode", "Pin Mode", "enum", "behavior", "always_on_top", options=_PIN_MODE_OPTIONS),
                OverlaySettingsField("click_through", "Click-Through", "boolean", "behavior", False),
                OverlaySettingsField("lock_position", "Lock Position", "boolean", "behavior", False),
                OverlaySettingsField("show_hide_condition", "Show/Hide Condition", "enum", "behavior", "telemetry_present", options=_SHOW_HIDE_OPTIONS),
                OverlaySettingsField("show_sector_coloring", "Sector Coloring", "boolean", "advanced", True, advanced=True),
            ),
        ),
    )


def build_example_overlay_settings_service() -> OverlaySettingsSchemaService:
    registry = OverlaySettingsSchemaRegistry(example_overlay_settings_schemas())
    migrator = OverlaySettingsSchemaMigrator()
    migrator.register(
        "delta_widget",
        1,
        2,
        _migrate_delta_widget_v1_to_v2,
        description="Migrated Delta Widget settings from v1 to v2.",
    )
    return OverlaySettingsSchemaService(registry=registry, migrator=migrator)


def _migrate_delta_widget_v1_to_v2(values: dict[str, object]) -> dict[str, object]:
    migrated = dict(values)
    if "inactive_alpha" in migrated and "inactive_opacity" not in migrated:
        migrated["inactive_opacity"] = migrated.pop("inactive_alpha")
    if "show_reference_badge" in migrated and "show_reference_chip" not in migrated:
        migrated["show_reference_chip"] = migrated.pop("show_reference_badge")
    return migrated
