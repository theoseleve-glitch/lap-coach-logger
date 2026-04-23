from __future__ import annotations

from pathlib import Path

from lap_coach_logger.overlays import (
    OverlayBrowserPageService,
    OverlayCatalogFilter,
    OverlayEntitlementContext,
    OverlayInstanceLifecycleService,
    OverlayLayoutPresetService,
    OverlayRegistry,
    OverlayStateStore,
    StaticOverlayEntitlementResolver,
    builtin_overlay_definitions,
    example_overlay_layout_templates,
)


def test_entitlement_service_distinguishes_accessible_preview_only_and_hidden() -> None:
    registry = OverlayRegistry(builtin_overlay_definitions())
    resolver = StaticOverlayEntitlementResolver()

    free_access = resolver.evaluate(registry.get("track_map"))
    assert free_access.access_state == "accessible"
    assert free_access.can_activate is True
    assert free_access.can_preview is True
    assert free_access.can_view_settings is True

    premium_locked = resolver.evaluate(registry.get("live_coach"))
    assert premium_locked.access_state == "preview_only"
    assert premium_locked.can_activate is False
    assert premium_locked.can_preview is True
    assert premium_locked.can_view_settings is True
    assert premium_locked.upsell_message

    internal_hidden = resolver.evaluate(registry.get("engineer_debug_panel"))
    assert internal_hidden.access_state == "hidden"
    assert internal_hidden.visible_in_catalog is False
    assert internal_hidden.can_activate is False
    assert internal_hidden.can_preview is False


def test_entitlement_service_unlocks_premium_and_internal_when_context_allows() -> None:
    registry = OverlayRegistry(builtin_overlay_definitions())
    resolver = StaticOverlayEntitlementResolver()

    premium_access = resolver.evaluate(
        registry.get("fuel_strategy"),
        context=OverlayEntitlementContext(premium_active=True),
    )
    assert premium_access.access_state == "accessible"
    assert premium_access.can_activate is True

    internal_access = resolver.evaluate(
        registry.get("engineer_debug_panel"),
        context=OverlayEntitlementContext(dev_mode=True),
    )
    assert internal_access.access_state == "accessible"
    assert internal_access.can_activate is True
    assert internal_access.access_badge == "DEV"


def test_registry_catalog_entries_expose_rich_access_state(tmp_path: Path) -> None:
    registry = OverlayRegistry(builtin_overlay_definitions())

    entries = registry.catalog_entries(
        filter_spec=OverlayCatalogFilter(query="coach", include_locked=True),
        entitlement_resolver=StaticOverlayEntitlementResolver(),
    )
    assert len(entries) == 2
    entry_ids = {e.overlay_id for e in entries}
    assert "live_coach" in entry_ids
    assert "theoretical_ghost" in entry_ids
    for entry in entries:
        assert entry.access_state == "preview_only"
        assert entry.can_activate is False
        assert entry.can_preview is True
        assert entry.can_view_settings is True

    hidden_entries = registry.catalog_entries(
        filter_spec=OverlayCatalogFilter(query="engineer", include_hidden=True, include_locked=True),
        entitlement_resolver=StaticOverlayEntitlementResolver(),
    )
    assert hidden_entries == ()

    dev_entries = registry.catalog_entries(
        filter_spec=OverlayCatalogFilter(query="engineer", include_hidden=True, include_locked=True),
        entitlement_resolver=StaticOverlayEntitlementResolver(),
        entitlement_context=OverlayEntitlementContext(dev_mode=True),
    )
    assert len(dev_entries) == 1
    assert dev_entries[0].access_state == "accessible"


def test_browser_uses_preview_only_access_for_premium_overlay(tmp_path: Path) -> None:
    registry = OverlayRegistry(builtin_overlay_definitions())
    runtime = OverlayInstanceLifecycleService(registry=registry)
    layout_service = OverlayLayoutPresetService(
        registry=registry,
        store=OverlayStateStore(path=tmp_path / "overlay_state.json"),
        runtime=runtime,
        default_layouts=example_overlay_layout_templates(),
    )
    browser = OverlayBrowserPageService(registry=registry, layout_service=layout_service)
    browser.set_selected_overlay("live_coach")

    state = browser.page_state()

    assert state.selected_overlay is not None
    assert state.selected_overlay.locked is True
    assert state.selected_overlay.preview.mode == "preview_only"
    assert any(action.action_id == "start_preview" and action.enabled for action in state.selected_overlay.actions)
