"""Integration helpers for the overlay browser Qt frontend."""

from __future__ import annotations

from dataclasses import dataclass

from lap_coach_logger.overlays import (
    OverlayBrowserPageService,
    OverlayInstanceLifecycleService,
    OverlayLayoutPresetService,
    OverlayRegistry,
    OverlayStateStore,
    OverlayTelemetryBindingService,
    StaticOverlayEntitlementResolver,
    build_example_overlay_settings_service,
    build_example_overlay_telemetry_binding_service,
    builtin_overlay_definitions,
    example_overlay_layout_templates,
)
from lap_coach_logger.ui.desktop.overlay_browser.controller import OverlayBrowserPageController
from lap_coach_logger.ui.desktop.overlay_browser.page import OverlayBrowserPage, OverlayWorkspaceShellCallbacks


@dataclass(slots=True)
class OverlayBrowserFrontend:
    registry: OverlayRegistry
    store: OverlayStateStore
    runtime: OverlayInstanceLifecycleService
    layout_service: OverlayLayoutPresetService
    browser_service: OverlayBrowserPageService
    telemetry_bindings: OverlayTelemetryBindingService
    controller: OverlayBrowserPageController
    page: OverlayBrowserPage


def build_overlay_browser_frontend(
    *,
    parent=None,  # noqa: ANN001
    store: OverlayStateStore | None = None,
    shell_callbacks: OverlayWorkspaceShellCallbacks | None = None,
) -> OverlayBrowserFrontend:
    """Build a coherent frontend/backend overlay browser stack for the desktop shell."""
    registry = OverlayRegistry(builtin_overlay_definitions())
    store = store or OverlayStateStore()
    settings_service = build_example_overlay_settings_service()
    telemetry_bindings = build_example_overlay_telemetry_binding_service()
    entitlement_resolver = StaticOverlayEntitlementResolver()
    runtime = OverlayInstanceLifecycleService(
        registry=registry,
        settings_service=settings_service,
    )
    layout_service = OverlayLayoutPresetService(
        registry=registry,
        store=store,
        runtime=runtime,
        entitlement_resolver=entitlement_resolver,
        default_layouts=example_overlay_layout_templates(),
    )
    browser_service = OverlayBrowserPageService(
        registry=registry,
        layout_service=layout_service,
        settings_service=settings_service,
        entitlement_resolver=entitlement_resolver,
    )
    controller = OverlayBrowserPageController(
        registry=registry,
        browser_service=browser_service,
        layout_service=layout_service,
        telemetry_bindings=telemetry_bindings,
    )
    page = OverlayBrowserPage(
        controller=controller,
        shell_callbacks=shell_callbacks,
        parent=parent,
    )
    return OverlayBrowserFrontend(
        registry=registry,
        store=store,
        runtime=runtime,
        layout_service=layout_service,
        browser_service=browser_service,
        telemetry_bindings=telemetry_bindings,
        controller=controller,
        page=page,
    )
