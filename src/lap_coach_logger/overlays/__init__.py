"""Reusable overlay platform backend for LAP COACH."""

from __future__ import annotations

from lap_coach_logger.overlays.builtins import builtin_overlay_definitions
from lap_coach_logger.overlays.browser import (
    OverlayBrowserAction,
    OverlayBrowserCategoryItem,
    OverlayBrowserEntitlementState,
    OverlayBrowserFilterState,
    OverlayBrowserLayoutItem,
    OverlayBrowserOverlayDetail,
    OverlayBrowserOverlayItem,
    OverlayBrowserPageService,
    OverlayBrowserPageState,
    OverlayBrowserPreviewState,
    OverlayBrowserSelectionState,
    OverlayBrowserSettingFieldView,
    OverlayBrowserSettingOption,
    OverlayBrowserSettingsSectionView,
)
from lap_coach_logger.overlays.entitlements import (
    OverlayEntitlementContext,
    OverlayEntitlementResult,
    OverlayEntitlementResolver,
    StaticOverlayEntitlementResolver,
)
from lap_coach_logger.overlays.layout_examples import example_overlay_layout_templates
from lap_coach_logger.overlays.layouts import (
    LAYOUT_EXPORT_SCHEMA_VERSION,
    OverlayLayoutExportBundle,
    OverlayLayoutMatch,
    OverlayLayoutPresetService,
    OverlayLayoutTemplate,
)
from lap_coach_logger.overlays.migrations import OVERLAY_STATE_SCHEMA_VERSION, OverlayStateMigrator
from lap_coach_logger.overlays.models import (
    OverlayAccessState,
    OverlayAutoApplyRule,
    OverlayAvailabilityStatus,
    OverlayBrowserPreferences,
    OverlayBrowserSnapshot,
    OverlayCapabilities,
    OverlayCatalogEntry,
    OverlayCatalogFilter,
    OverlayDefinition,
    OverlayEntitlement,
    OverlayEvent,
    OverlayInstance,
    OverlayLastUsedSettings,
    OverlayLayoutHints,
    OverlayLayoutContext,
    OverlayLayoutDiff,
    OverlayLayoutFieldChange,
    OverlayLayoutInstanceChange,
    OverlayLayoutSlot,
    OverlayPlacement,
    OverlayPreset,
    OverlayPresetScope,
    OverlayPreviewSession,
    OverlayRuntimeState,
    OverlaySettingField,
    OverlaySettingOption,
    OverlayStateDocument,
)
from lap_coach_logger.overlays.registry import OverlayRegistry
from lap_coach_logger.overlays.runtime import OverlayRuntimeController
from lap_coach_logger.overlays.runtime_instances import (
    OverlayInstanceEvent,
    OverlayInstanceEventBus,
    OverlayInstanceLifecycleService,
    OverlayInstanceState,
    OverlayRuntimeInstance,
    OverlayRuntimeMetrics,
)
from lap_coach_logger.overlays.settings_examples import (
    build_example_overlay_settings_service,
    example_overlay_settings_schemas,
)
from lap_coach_logger.overlays.telemetry_bindings import (
    OverlayTelemetryBindingResult,
    OverlayTelemetryBindingService,
    OverlayTelemetryContract,
    OverlayTelemetryContractRegistry,
    OverlayTelemetryFieldHealth,
    OverlayTelemetryHealth,
    OverlayTelemetryPreviewProvider,
    OverlayTelemetryRequirement,
    build_example_overlay_telemetry_binding_service,
    example_overlay_telemetry_contracts,
)
from lap_coach_logger.overlays.settings_models import (
    OverlaySettingsField,
    OverlaySettingsFieldKind,
    OverlaySettingsMigration,
    OverlaySettingsOption,
    OverlaySettingsResolution,
    OverlaySettingsSchema,
    OverlaySettingsSection,
    OverlaySettingsSectionKey,
    OverlaySettingsValidationIssue,
    OverlaySettingsValidationRule,
    OverlaySettingsVisibilityCondition,
    STANDARD_ANCHOR_PRESETS,
    STANDARD_SECTIONS,
    STANDARD_SPACING_TOKENS,
)
from lap_coach_logger.overlays.settings_service import (
    OverlaySettingsSchemaMigrator,
    OverlaySettingsSchemaRegistry,
    OverlaySettingsSchemaService,
)
from lap_coach_logger.overlays.service import OverlayEventBus, OverlayManagerService
from lap_coach_logger.overlays.store import OverlayStateStore
from lap_coach_logger.overlays.store import (
    JsonOverlayStateStoreBackend,
    OVERLAY_PERSISTENCE_SCHEMA_VERSION,
    OverlayPersistenceMigrationRunner,
    OverlayStoreLoadReport,
    OverlayStoreWarning,
    SQLiteOverlayStateStoreBackend,
)


def build_default_overlay_manager(
    *,
    entitlement_resolver: OverlayEntitlementResolver | None = None,
    store: OverlayStateStore | None = None,
) -> OverlayManagerService:
    registry = OverlayRegistry(builtin_overlay_definitions())
    return OverlayManagerService(
        registry=registry,
        store=store or OverlayStateStore(),
        entitlement_resolver=entitlement_resolver or StaticOverlayEntitlementResolver(),
    )


def build_default_overlay_layout_service(
    *,
    entitlement_resolver: OverlayEntitlementResolver | None = None,
    store: OverlayStateStore | None = None,
    runtime: OverlayInstanceLifecycleService | None = None,
) -> OverlayLayoutPresetService:
    registry = OverlayRegistry(builtin_overlay_definitions())
    return OverlayLayoutPresetService(
        registry=registry,
        store=store or OverlayStateStore(),
        runtime=runtime,
        entitlement_resolver=entitlement_resolver or StaticOverlayEntitlementResolver(),
        default_layouts=example_overlay_layout_templates(),
    )


def build_default_overlay_browser_service(
    *,
    entitlement_resolver: OverlayEntitlementResolver | None = None,
    store: OverlayStateStore | None = None,
    runtime: OverlayInstanceLifecycleService | None = None,
    settings_service: OverlaySettingsSchemaService | None = None,
) -> OverlayBrowserPageService:
    registry = OverlayRegistry(builtin_overlay_definitions())
    layout_service = OverlayLayoutPresetService(
        registry=registry,
        store=store or OverlayStateStore(),
        runtime=runtime,
        entitlement_resolver=entitlement_resolver or StaticOverlayEntitlementResolver(),
        default_layouts=example_overlay_layout_templates(),
    )
    return OverlayBrowserPageService(
        registry=registry,
        layout_service=layout_service,
        settings_service=settings_service,
        entitlement_resolver=entitlement_resolver or StaticOverlayEntitlementResolver(),
    )


__all__ = [
    "OVERLAY_STATE_SCHEMA_VERSION",
    "LAYOUT_EXPORT_SCHEMA_VERSION",
    "OverlayBrowserAction",
    "OverlayBrowserCategoryItem",
    "OverlayBrowserEntitlementState",
    "OverlayBrowserFilterState",
    "OverlayBrowserLayoutItem",
    "OverlayBrowserOverlayDetail",
    "OverlayBrowserOverlayItem",
    "OverlayBrowserPageService",
    "OverlayBrowserPageState",
    "OverlayBrowserPreviewState",
    "OverlayBrowserSelectionState",
    "OverlayBrowserSettingFieldView",
    "OverlayBrowserSettingOption",
    "OverlayBrowserSettingsSectionView",
    "OverlayAutoApplyRule",
    "OverlayAccessState",
    "OverlayAvailabilityStatus",
    "OverlayBrowserPreferences",
    "OverlayBrowserSnapshot",
    "OverlayCapabilities",
    "OverlayCatalogEntry",
    "OverlayCatalogFilter",
    "OverlayDefinition",
    "OverlayEntitlement",
    "OverlayEntitlementContext",
    "OverlayEntitlementResolver",
    "OverlayEntitlementResult",
    "OverlayEvent",
    "OverlayEventBus",
    "OverlayInstance",
    "OverlayInstanceEvent",
    "OverlayInstanceEventBus",
    "OverlayInstanceLifecycleService",
    "OverlayInstanceState",
    "OverlayLayoutContext",
    "OverlayLayoutDiff",
    "OverlayLayoutExportBundle",
    "OverlayLayoutFieldChange",
    "OverlayLayoutHints",
    "OverlayLayoutInstanceChange",
    "OverlayLayoutMatch",
    "OverlayLayoutPresetService",
    "OverlayLayoutSlot",
    "OverlayLayoutTemplate",
    "OverlayLastUsedSettings",
    "OverlayManagerService",
    "OverlayPlacement",
    "OverlayPersistenceMigrationRunner",
    "OverlayPreset",
    "OverlayPresetScope",
    "OverlayPreviewSession",
    "OverlayRegistry",
    "OverlayRuntimeController",
    "OverlayRuntimeInstance",
    "OverlayRuntimeMetrics",
    "OverlayRuntimeState",
    "OverlaySettingField",
    "OverlaySettingOption",
    "OverlaySettingsField",
    "OverlaySettingsFieldKind",
    "OverlaySettingsMigration",
    "OverlaySettingsOption",
    "OverlaySettingsResolution",
    "OverlaySettingsSchema",
    "OverlaySettingsSchemaMigrator",
    "OverlaySettingsSchemaRegistry",
    "OverlaySettingsSchemaService",
    "OverlaySettingsSection",
    "OverlaySettingsSectionKey",
    "OverlaySettingsValidationIssue",
    "OverlaySettingsValidationRule",
    "OverlaySettingsVisibilityCondition",
    "OverlayStateDocument",
    "OverlayStateMigrator",
    "OverlayStateStore",
    "OverlayStoreLoadReport",
    "OverlayStoreWarning",
    "OverlayTelemetryBindingResult",
    "OverlayTelemetryBindingService",
    "OverlayTelemetryContract",
    "OverlayTelemetryContractRegistry",
    "OverlayTelemetryFieldHealth",
    "OverlayTelemetryHealth",
    "OverlayTelemetryPreviewProvider",
    "OverlayTelemetryRequirement",
    "JsonOverlayStateStoreBackend",
    "SQLiteOverlayStateStoreBackend",
    "OVERLAY_PERSISTENCE_SCHEMA_VERSION",
    "STANDARD_ANCHOR_PRESETS",
    "STANDARD_SECTIONS",
    "STANDARD_SPACING_TOKENS",
    "StaticOverlayEntitlementResolver",
    "build_default_overlay_manager",
    "build_default_overlay_layout_service",
    "build_example_overlay_settings_service",
    "build_default_overlay_browser_service",
    "build_example_overlay_telemetry_binding_service",
    "builtin_overlay_definitions",
    "example_overlay_layout_templates",
    "example_overlay_settings_schemas",
    "example_overlay_telemetry_contracts",
]
