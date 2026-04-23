from __future__ import annotations

import json
from pathlib import Path

import pytest

from lap_coach_logger.overlays import (
    OverlayCatalogFilter,
    OverlayEntitlementContext,
    OverlayLayoutSlot,
    OverlayManagerService,
    OverlayPresetScope,
    OverlayRegistry,
    OVERLAY_STATE_SCHEMA_VERSION,
    OverlayStateStore,
    build_default_overlay_manager,
    builtin_overlay_definitions,
)


def test_overlay_registry_catalog_search_filter_and_definition_shape(tmp_path: Path) -> None:
    registry = OverlayRegistry(builtin_overlay_definitions())
    fuel_definition = registry.get("fuel_strategy")

    assert len(registry.list_definitions()) >= 10
    assert {
        "awareness",
        "timing",
        "telemetry",
        "strategy",
        "race context",
        "diagnostics",
        "coaching",
    }.issubset(set(registry.categories()))
    assert fuel_definition.settings_schema_ref == "fuel_strategy.v1"
    assert fuel_definition.default_size == (360, 200)
    assert fuel_definition.default_anchor == "top_right"
    assert fuel_definition.premium_tier == "premium"
    assert fuel_definition.preview_asset_ref.endswith("fuel_strategy.png")
    assert "ACC" in fuel_definition.supported_simulators

    defaults = registry.default_settings("fuel_strategy")
    assert defaults["safety_margin_l"] == 1.5

    values, issues = registry.validate_settings(
        "fuel_strategy",
        {
            "safety_margin_l": "12.5",
            "compact_mode": "yes",
            "unknown_field": 123,
        },
    )

    assert values["safety_margin_l"] == pytest.approx(10.0)
    assert values["compact_mode"] is True
    assert any("Unknown setting key ignored: unknown_field" in issue for issue in issues)

    entries = registry.catalog_entries(
        filter_spec=OverlayCatalogFilter(
            query="fuel_strategy",
            premium_tiers=("premium",),
            categories=("strategy",),
            availability_statuses=("available",),
            simulators=("ACC",),
            include_locked=True,
        ),
        favorites={"fuel_strategy"},
    )

    assert len(entries) == 1
    assert entries[0].overlay_id == fuel_definition.overlay_id
    assert entries[0].favorite is True
    assert entries[0].premium_tier == "premium"
    assert entries[0].availability_status == "available"
    assert entries[0].short_description == fuel_definition.short_description
    assert entries[0].settings_schema_ref == "fuel_strategy.v1"

    hidden_entries = registry.catalog_entries(
        filter_spec=OverlayCatalogFilter(query="engineer", include_hidden=False, include_locked=True),
    )
    assert hidden_entries == ()

    declarative_path = tmp_path / "overlays.json"
    declarative_path.write_text(
        json.dumps(
            {
                "overlays": [
                    {
                        "overlay_id": "garage_awareness",
                        "renderer_key": "garage_awareness",
                        "display_name": "Garage Awareness",
                        "short_description": "Simple sample loaded from JSON.",
                        "category": "awareness",
                        "tags": ["sample", "awareness"],
                        "settings_schema_ref": "garage_awareness.v1",
                        "supported_simulators": ["ACC", "Assetto Corsa"],
                        "default_enabled": False,
                        "availability_status": "beta",
                        "preview_asset": "assets/overlays/garage_awareness.png",
                        "default_size": [300, 120],
                        "default_anchor": "bottom_left",
                        "settings_schema": [
                            {
                                "key": "show_title",
                                "label": "Show Title",
                                "kind": "bool",
                                "section": "visibility",
                                "default": True,
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    loaded = registry.register_from_file(declarative_path)
    assert loaded[0].overlay_id == "garage_awareness"
    assert registry.get("garage_awareness").default_size == (300, 120)
    assert registry.get("garage_awareness").availability_status == "beta"


def test_overlay_state_store_migrates_legacy_document(tmp_path: Path) -> None:
    path = tmp_path / "overlay_state.json"
    path.write_text(
        json.dumps(
            {
                "active_layout_id": "legacy-layout",
                "favorites": ["track_map"],
                "layouts": [
                    {
                        "preset_id": "legacy-layout",
                        "name": "Legacy Layout",
                    }
                ],
                "instances": [
                    {
                        "instance_id": "legacy-instance",
                        "overlay_id": "track_map",
                        "preset_id": "legacy-layout",
                        "name": "Track Map",
                        "placement": {
                            "x": 10,
                            "y": 20,
                            "width": 280,
                            "height": 280,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    document, report = OverlayStateStore(path=path).load_with_report()

    assert report.backend == "json"
    assert report.migrated is True
    assert document.schema_version == OVERLAY_STATE_SCHEMA_VERSION
    assert document.active_preset_id == "legacy-layout"
    assert document.favorite_overlay_ids == ["track_map"]
    assert document.layout_shortcuts == {"A": "", "B": "", "C": ""}
    assert document.browser_preferences.selected_layout_id == "legacy-layout"
    assert document.last_used_settings == []
    assert document.presets[0].scope.sim == ""
    assert document.presets[0].simulator_filter == ()
    assert document.instances[0].placement.monitor_id == "primary"
    assert path.with_suffix(".json.bak").exists()


def test_overlay_manager_creates_instances_slots_and_runtime_state(tmp_path: Path) -> None:
    service = build_default_overlay_manager(store=OverlayStateStore(path=tmp_path / "overlay_state.json"))

    preset = service.create_preset(
        name="Race Day",
        scope=OverlayPresetScope(sim="ACC", car="Ferrari 296 GT3"),
        slots=[
            OverlayLayoutSlot(slot_id="top_left", name="Top Left", allowed_categories=("timing",)),
            OverlayLayoutSlot(slot_id="top_right", name="Top Right"),
        ],
    )
    service.activate_preset(preset.preset_id)

    instance = service.add_overlay_instance("session_delta", preset_id=preset.preset_id, slot_id="top_left")
    runtime = service.runtime_states()

    assert instance.slot_id == "top_left"
    assert preset.instance_ids == [instance.instance_id]
    assert any(state.instance_id == instance.instance_id and state.status == "mounted" for state in runtime)

    updated, issues = service.update_instance_settings(instance.instance_id, {"scale": 1.4})
    assert not issues
    assert updated.settings["scale"] == pytest.approx(1.4)
    assert updated.placement.scale == pytest.approx(1.4)


def test_overlay_manager_blocks_premium_overlay_without_entitlement(tmp_path: Path) -> None:
    service = build_default_overlay_manager(store=OverlayStateStore(path=tmp_path / "overlay_state.json"))

    with pytest.raises(PermissionError):
        service.add_overlay_instance("fuel_strategy")

    service.set_entitlement_context(OverlayEntitlementContext(feature_flags=frozenset({"overlay.fuel_strategy"})))
    premium_instance = service.add_overlay_instance("fuel_strategy")
    assert premium_instance.overlay_id == "fuel_strategy"


def test_overlay_preview_sessions_are_ephemeral_and_search_filters_work(tmp_path: Path) -> None:
    service = build_default_overlay_manager(store=OverlayStateStore(path=tmp_path / "overlay_state.json"))
    preview = service.start_preview("track_map")

    assert preview.overlay_id == "track_map"
    assert service.preview_sessions()[0].preview_id == preview.preview_id

    filtered = service.catalog(
        filter_spec=OverlayCatalogFilter(categories=("telemetry",), include_locked=False)
    )
    assert [entry.overlay_id for entry in filtered.entries] == ["track_map"]

    service.stop_preview(preview.preview_id)
    assert service.preview_sessions() == ()

    reloaded = OverlayManagerService(
        registry=OverlayRegistry(builtin_overlay_definitions()),
        store=OverlayStateStore(path=tmp_path / "overlay_state.json"),
    )
    assert reloaded.preview_sessions() == ()
