from __future__ import annotations

import pytest

from lap_coach_logger.overlays import (
    OverlayDefinition,
    OverlayInstanceEvent,
    OverlayInstanceLifecycleService,
    OverlayLayoutHints,
    OverlayRegistry,
    OverlaySettingsSchemaService,
    build_example_overlay_settings_service,
)


def test_runtime_instance_creation_merges_defaults_layout_and_instance_overrides() -> None:
    service = _service()

    instance = service.create_instance(
        "delta_widget_overlay",
        layout_id="layout-a",
        screen_id="screen-main",
        visible=True,
        layout_overrides={"opacity": 0.8, "show_reference_chip": False},
        instance_overrides={"scale": "1.25", "inactive_opacity": 0.95},
    )

    assert instance.layout_id == "layout-a"
    assert instance.screen_id == "screen-main"
    assert instance.state.visible is True
    assert instance.state.active is True
    assert instance.state.lifecycle_status == "visible"
    assert instance.effective_settings["opacity"] == pytest.approx(0.8)
    assert instance.effective_settings["scale"] == pytest.approx(1.25)
    assert instance.effective_settings["show_reference_chip"] is False
    assert instance.effective_settings["inactive_opacity"] == pytest.approx(0.8)
    assert instance.placement.opacity == pytest.approx(0.8)
    assert instance.placement.scale == pytest.approx(1.25)


def test_show_hide_and_entitlement_block_state_transitions() -> None:
    service = _service()

    blocked = service.create_instance(
        "core_driving_hud_overlay",
        layout_id="layout-blocked",
        visible=True,
        entitlement_blocked=True,
    )
    assert blocked.state.lifecycle_status == "blocked"
    assert blocked.state.visible is False

    with pytest.raises(PermissionError):
        service.show(blocked.instance_id)

    instance = service.create_instance("core_driving_hud_overlay", layout_id="layout-main", visible=False)
    assert instance.state.lifecycle_status == "hidden"

    shown = service.show(instance.instance_id)
    assert shown.state.visible is True
    assert shown.state.active is True
    assert shown.metrics.show_count >= 1

    hidden = service.hide(instance.instance_id)
    assert hidden.state.visible is False
    assert hidden.state.active is False
    assert hidden.state.lifecycle_status == "hidden"


def test_lock_pin_move_resize_and_click_through() -> None:
    service = _service()
    instance = service.create_instance("relative_table_overlay", layout_id="layout-1", visible=True)

    service.lock(instance.instance_id)
    with pytest.raises(RuntimeError):
        service.move(instance.instance_id, x=100, y=120)
    with pytest.raises(RuntimeError):
        service.resize(instance.instance_id, width=500, height=280)

    service.unlock(instance.instance_id)
    moved = service.move(instance.instance_id, x=100, y=120, screen_id="screen-2")
    resized = service.resize(instance.instance_id, width=500, height=280)
    pinned = service.pin(instance.instance_id)
    assert pinned.state.pinned is True
    unpinned = service.unpin(instance.instance_id)
    clicked = service.set_click_through(instance.instance_id, True)

    assert moved.placement.x == 100
    assert moved.placement.y == 120
    assert moved.screen_id == "screen-2"
    assert resized.placement.width == 500
    assert resized.placement.height == 280
    assert unpinned.state.pinned is False
    assert clicked.state.click_through is True


def test_preview_destroy_and_destroyed_snapshot_access() -> None:
    service = _service()
    instance = service.create_instance("track_map_overlay", layout_id="layout-preview", visible=False)

    previewed = service.enter_preview_mode(instance.instance_id)
    assert previewed.state.preview_mode is True
    assert previewed.state.visible is True
    assert previewed.state.lifecycle_status == "preview"

    exited = service.exit_preview_mode(instance.instance_id)
    assert exited.state.preview_mode is False
    assert exited.state.lifecycle_status == "visible"

    service.hide(instance.instance_id)
    exited_hidden = service.exit_preview_mode(instance.instance_id)
    assert exited_hidden.state.lifecycle_status == "hidden"

    destroyed = service.destroy(instance.instance_id)
    assert destroyed.state.lifecycle_status == "destroyed"
    assert service.list_instances() == ()
    assert service.list_instances(include_destroyed=True)[0].instance_id == instance.instance_id
    assert service.instance(instance.instance_id).state.lifecycle_status == "destroyed"


def test_serialize_restore_and_persistence_hooks_round_trip() -> None:
    service = _service()
    instance = service.create_instance(
        "delta_widget_overlay",
        layout_id="layout-restore",
        visible=True,
        layout_overrides={"opacity": 0.7},
        instance_overrides={"scale": 1.1},
    )
    service.move(instance.instance_id, x=55, y=75)
    service.pin(instance.instance_id)
    service.set_click_through(instance.instance_id, True)

    snapshot = service.serialize_state(instance.instance_id)

    restored_service = _service()
    restored = restored_service.restore_state(snapshot)

    assert restored.instance_id == instance.instance_id
    assert restored.placement.x == 55
    assert restored.placement.y == 75
    assert restored.state.pinned is True
    assert restored.state.click_through is True
    assert restored.effective_settings["opacity"] == pytest.approx(0.7)
    assert restored.effective_settings["scale"] == pytest.approx(1.1)

    persisted = service.to_persisted_instance(instance.instance_id)
    assert persisted.preset_id == "layout-restore"
    assert persisted.placement.monitor_id == instance.screen_id
    assert persisted.settings == {"scale": 1.1}

    restored_from_persisted = _service().restore_from_persisted_instance(
        persisted,
        layout_overrides={"opacity": 0.75},
        click_through=True,
    )
    assert restored_from_persisted.effective_settings["opacity"] == pytest.approx(0.75)
    assert restored_from_persisted.state.click_through is True


def test_many_instances_and_event_bus_are_safe() -> None:
    events: list[OverlayInstanceEvent] = []
    service = _service(events.append)

    for index in range(40):
        service.create_instance(
            "core_driving_hud_overlay",
            layout_id=f"layout-{index % 3}",
            visible=bool(index % 2),
            x=index * 5,
            y=index * 3,
        )

    assert len(service.list_instances()) == 40
    assert len(service.instances_for_layout("layout-1")) >= 1
    created_events = [event for event in events if event.kind == "created"]
    assert len(created_events) == 40


def _service(listener=None) -> OverlayInstanceLifecycleService:
    registry = OverlayRegistry(
        (
            _definition("core_driving_hud_overlay", "core_driving_hud"),
            _definition("delta_widget_overlay", "delta_widget"),
            _definition("relative_table_overlay", "relative_table"),
            _definition("track_map_overlay", "track_map"),
        )
    )
    service = OverlayInstanceLifecycleService(
        registry=registry,
        settings_service=build_example_overlay_settings_service(),
    )
    if listener is not None:
        service.event_bus.subscribe(listener)
    return service


def _definition(overlay_id: str, schema_ref: str) -> OverlayDefinition:
    return OverlayDefinition(
        overlay_id=overlay_id,
        renderer_key=overlay_id,
        display_name=overlay_id.replace("_", " ").title(),
        short_description=f"Runtime test overlay for {schema_ref}.",
        category="timing",
        settings_schema_ref=schema_ref,
        preview_asset=f"assets/overlays/{overlay_id}.png",
        sort_order=10,
        layout=OverlayLayoutHints(default_width=320, default_height=180),
        default_enabled=False,
    )
