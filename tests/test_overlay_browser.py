from __future__ import annotations

from pathlib import Path

from lap_coach_logger.overlays import (
    OverlayBrowserPageService,
    OverlayEntitlementContext,
    OverlayInstanceLifecycleService,
    OverlayLayoutPresetService,
    OverlayRegistry,
    OverlayStateStore,
    builtin_overlay_definitions,
    example_overlay_layout_templates,
)


def _build_browser_service(tmp_path: Path) -> OverlayBrowserPageService:
    registry = OverlayRegistry(builtin_overlay_definitions())
    runtime = OverlayInstanceLifecycleService(registry=registry)
    layout_service = OverlayLayoutPresetService(
        registry=registry,
        store=OverlayStateStore(path=tmp_path / "overlay_state.json"),
        runtime=runtime,
        default_layouts=example_overlay_layout_templates(),
    )
    return OverlayBrowserPageService(
        registry=registry,
        layout_service=layout_service,
    )


def test_browser_page_state_exposes_categories_layouts_and_locked_premium_overlays(tmp_path: Path) -> None:
    service = _build_browser_service(tmp_path)
    service.set_selected_overlay("live_coach")

    state = service.page_state()

    assert state.selection.selected_layout_id == "layout-race-focus"
    assert any(item.category == "coaching" for item in state.categories)
    assert any(layout.layout_id == "layout-race-focus" and layout.active for layout in state.layouts)
    assert state.selected_overlay is not None
    assert state.selected_overlay.overlay_id == "live_coach"
    assert state.selected_overlay.locked is True
    assert state.selected_overlay.preview.mode == "preview_only"
    assert any(action.action_id == "install" and action.enabled is False for action in state.selected_overlay.actions)


def test_browser_flow_registry_to_selected_overlay_to_settings_and_activation(tmp_path: Path) -> None:
    service = _build_browser_service(tmp_path)
    service.set_selected_overlay("track_map")

    initial = service.page_state()
    assert initial.selected_overlay is not None
    assert initial.selected_overlay.installed is False
    assert initial.selected_overlay.preview.mode == "asset_placeholder"
    assert any(section.section_key == "appearance" for section in initial.selected_overlay.settings_sections)

    instance = service.install_overlay()
    assert instance.overlay_id == "track_map"

    after_install = service.page_state()
    assert after_install.selected_overlay is not None
    assert after_install.selected_overlay.installed is True
    assert after_install.selected_overlay.active is False
    assert any(action.action_id == "activate" for action in after_install.selected_overlay.actions)

    service.activate_overlay()
    service.update_overlay_settings({"show_corner_labels": True, "line_thickness": 2.0})

    active_state = service.page_state()
    assert active_state.selected_overlay is not None
    assert active_state.selected_overlay.active is True
    assert active_state.selected_overlay.preview.mode == "live_instance"
    appearance_section = next(section for section in active_state.selected_overlay.settings_sections if section.section_key == "appearance")
    line_thickness = next(field for field in appearance_section.fields if field.field_key == "line_thickness")
    assert line_thickness.current_value == 2.0
    behavior_section = next(section for section in active_state.selected_overlay.settings_sections if section.section_key == "behavior")
    show_corner_labels = next(field for field in behavior_section.fields if field.field_key == "show_corner_labels")
    assert show_corner_labels.current_value is True

    service.deactivate_overlay()
    inactive_state = service.page_state()
    assert inactive_state.selected_overlay is not None
    assert inactive_state.selected_overlay.active is False
    assert inactive_state.selected_overlay.preview.mode == "asset_placeholder"


def test_browser_search_filter_preview_and_favorites_state(tmp_path: Path) -> None:
    service = _build_browser_service(tmp_path)
    service.set_search_query("fuel")
    service.update_filters(status_filters=("active",))

    filtered = service.page_state()
    assert [item.overlay_id for item in filtered.overlays] == ["fuel_strategy"]

    service.update_filters(status_filters=(), favorites_only=True)
    service.toggle_favorite("track_map")
    service.set_search_query("track")
    favorited = service.page_state()
    assert [item.overlay_id for item in favorited.overlays] == ["track_map"]

    service.set_selected_overlay("track_map")
    preview = service.start_preview()
    assert preview.mode == "preview"
    preview_state = service.page_state()
    assert preview_state.selected_overlay is not None
    assert preview_state.selected_overlay.preview.mode == "preview"
    service.stop_preview()
    stopped = service.page_state()
    assert stopped.selected_overlay is not None
    assert stopped.selected_overlay.preview.mode == "asset_placeholder"


def test_browser_entitlement_unlocks_premium_overlay_actions(tmp_path: Path) -> None:
    service = _build_browser_service(tmp_path)
    service.set_entitlement_context(OverlayEntitlementContext(feature_flags=frozenset({"overlay.live_coach"})))
    service.set_selected_overlay("live_coach")

    state = service.page_state()

    assert state.selected_overlay is not None
    assert state.selected_overlay.locked is False
    install_action = next(action for action in state.selected_overlay.actions if action.action_id == "install")
    assert install_action.enabled is True
