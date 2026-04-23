"""Backend page-state models and service for the overlay browser/controls experience."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from lap_coach_logger.overlays.entitlements import (
    OverlayEntitlementContext,
    OverlayEntitlementResolver,
    StaticOverlayEntitlementResolver,
)
from lap_coach_logger.overlays.layouts import OverlayLayoutPresetService
from lap_coach_logger.overlays.models import (
    OverlayCatalogFilter,
    OverlayDefinition,
    OverlayInstance,
)
from lap_coach_logger.overlays.registry import OverlayRegistry
from lap_coach_logger.overlays.settings_models import (
    OverlaySettingsField,
    OverlaySettingsSection,
    OverlaySettingsValidationIssue,
)
from lap_coach_logger.overlays.settings_service import OverlaySettingsSchemaService


@dataclass(slots=True, frozen=True)
class OverlayBrowserFilterState:
    query: str = ""
    tags: tuple[str, ...] = ()
    simulators: tuple[str, ...] = ()
    availability_statuses: tuple[str, ...] = ()
    status_filters: tuple[str, ...] = ()
    entitlement_filter: str = "all"
    favorites_only: bool = False
    include_hidden: bool = False


@dataclass(slots=True, frozen=True)
class OverlayBrowserSelectionState:
    selected_category: str = ""
    selected_overlay_id: str = ""
    selected_layout_id: str = ""


@dataclass(slots=True, frozen=True)
class OverlayBrowserCategoryItem:
    category: str
    label: str
    count: int
    selected: bool = False


@dataclass(slots=True, frozen=True)
class OverlayBrowserOverlayItem:
    overlay_id: str
    display_name: str
    category: str
    tags: tuple[str, ...]
    favorite: bool
    selected: bool
    installed: bool
    active: bool
    locked: bool
    entitled: bool
    access_state: str
    access_badge: str
    premium_tier: str
    availability_status: str
    preview_asset: str
    supported_simulators: tuple[str, ...]
    status: str


@dataclass(slots=True, frozen=True)
class OverlayBrowserLayoutItem:
    layout_id: str
    display_name: str
    description: str
    favorite: bool
    selected: bool
    active: bool
    tags: tuple[str, ...]
    simulator_filter: tuple[str, ...]
    car_filter: tuple[str, ...]
    session_type_filter: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class OverlayBrowserAction:
    action_id: str
    label: str
    enabled: bool
    visible: bool = True
    reason: str = ""
    tone: str = "neutral"


@dataclass(slots=True, frozen=True)
class OverlayBrowserSettingOption:
    value: str
    label: str
    description: str = ""
    premium_only: bool = False


@dataclass(slots=True, frozen=True)
class OverlayBrowserSettingFieldView:
    field_key: str
    label: str
    description: str
    kind: str
    section_key: str
    current_value: object
    default_value: object
    source: str
    editable: bool
    premium_only: bool = False
    advanced: bool = False
    min_value: int | float | None = None
    max_value: int | float | None = None
    step: int | float | None = None
    unit: str = ""
    options: tuple[OverlayBrowserSettingOption, ...] = ()
    issues: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class OverlayBrowserSettingsSectionView:
    section_key: str
    label: str
    description: str
    fields: tuple[OverlayBrowserSettingFieldView, ...]


@dataclass(slots=True, frozen=True)
class OverlayBrowserPreviewState:
    session_id: str
    overlay_id: str
    mode: str
    title: str
    message: str = ""
    preview_asset: str = ""
    instance_id: str = ""
    layout_id: str = ""
    active: bool = False


@dataclass(slots=True, frozen=True)
class OverlayBrowserEntitlementState:
    premium_active: bool
    locked_overlays_visible: bool
    feature_flags: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class OverlayBrowserOverlayDetail:
    overlay_id: str
    display_name: str
    short_description: str
    category: str
    tags: tuple[str, ...]
    supported_simulators: tuple[str, ...]
    premium_tier: str
    availability_status: str
    favorite: bool
    entitled: bool
    locked: bool
    access_state: str
    access_badge: str
    lock_reason: str
    installed: bool
    active: bool
    installed_instance_ids: tuple[str, ...]
    selected_layout_id: str
    preview: OverlayBrowserPreviewState
    actions: tuple[OverlayBrowserAction, ...]
    settings_sections: tuple[OverlayBrowserSettingsSectionView, ...]


@dataclass(slots=True, frozen=True)
class OverlayBrowserPageState:
    filters: OverlayBrowserFilterState
    selection: OverlayBrowserSelectionState
    entitlement: OverlayBrowserEntitlementState
    categories: tuple[OverlayBrowserCategoryItem, ...]
    overlays: tuple[OverlayBrowserOverlayItem, ...]
    layouts: tuple[OverlayBrowserLayoutItem, ...]
    selected_overlay: OverlayBrowserOverlayDetail | None


class OverlayBrowserPageService:
    """Backend state and actions for the overlay browser and controls page."""

    def __init__(
        self,
        *,
        registry: OverlayRegistry,
        layout_service: OverlayLayoutPresetService,
        settings_service: OverlaySettingsSchemaService | None = None,
        entitlement_resolver: OverlayEntitlementResolver | None = None,
    ) -> None:
        self._registry = registry
        self._layouts = layout_service
        self._settings_service = settings_service
        self._entitlements = entitlement_resolver or StaticOverlayEntitlementResolver()
        preferences = self._layouts.browser_preferences()
        document = self._layouts.document()
        self._filters = OverlayBrowserFilterState(
            query=preferences.search_query,
            tags=preferences.tag_filters,
            simulators=preferences.simulator_filters,
            availability_statuses=preferences.availability_filters,
            status_filters=preferences.status_filters,
            entitlement_filter=preferences.entitlement_filter,
            favorites_only=preferences.favorites_only,
            include_hidden=preferences.include_hidden,
        )
        self._selection = OverlayBrowserSelectionState(
            selected_category=preferences.selected_category,
            selected_overlay_id=preferences.selected_overlay_id,
            selected_layout_id=preferences.selected_layout_id or document.active_preset_id,
        )
        self._entitlement_context = OverlayEntitlementContext()
        self._preview_overlay_id = ""
        self._preview_session_id = ""

    def set_entitlement_context(self, context: OverlayEntitlementContext) -> None:
        self._entitlement_context = context
        self._layouts.set_entitlement_context(context)

    def selection_state(self) -> OverlayBrowserSelectionState:
        return self._selection

    def filter_state(self) -> OverlayBrowserFilterState:
        return self._filters

    def set_selected_category(self, category: str) -> OverlayBrowserSelectionState:
        self._selection = OverlayBrowserSelectionState(
            selected_category=category.strip(),
            selected_overlay_id="",
            selected_layout_id=self._resolved_layout_id(),
        )
        self._sync_preferences()
        return self._selection

    def set_selected_overlay(self, overlay_id: str) -> OverlayBrowserSelectionState:
        self._selection = OverlayBrowserSelectionState(
            selected_category=self._selection.selected_category,
            selected_overlay_id=overlay_id.strip(),
            selected_layout_id=self._resolved_layout_id(),
        )
        self._sync_preferences()
        return self._selection

    def set_selected_layout(self, layout_id: str) -> OverlayBrowserSelectionState:
        resolved_layout_id = layout_id.strip() or self._layouts.document().active_preset_id
        self._selection = OverlayBrowserSelectionState(
            selected_category=self._selection.selected_category,
            selected_overlay_id=self._selection.selected_overlay_id,
            selected_layout_id=resolved_layout_id,
        )
        self._sync_preferences()
        return self._selection

    def set_search_query(self, query: str) -> OverlayBrowserFilterState:
        self._filters = OverlayBrowserFilterState(
            query=query,
            tags=self._filters.tags,
            simulators=self._filters.simulators,
            availability_statuses=self._filters.availability_statuses,
            status_filters=self._filters.status_filters,
            entitlement_filter=self._filters.entitlement_filter,
            favorites_only=self._filters.favorites_only,
            include_hidden=self._filters.include_hidden,
        )
        self._sync_preferences()
        return self._filters

    def update_filters(
        self,
        *,
        tags: tuple[str, ...] | list[str] | None = None,
        simulators: tuple[str, ...] | list[str] | None = None,
        availability_statuses: tuple[str, ...] | list[str] | None = None,
        status_filters: tuple[str, ...] | list[str] | None = None,
        entitlement_filter: str | None = None,
        favorites_only: bool | None = None,
        include_hidden: bool | None = None,
    ) -> OverlayBrowserFilterState:
        self._filters = OverlayBrowserFilterState(
            query=self._filters.query,
            tags=tuple(tags) if tags is not None else self._filters.tags,
            simulators=tuple(simulators) if simulators is not None else self._filters.simulators,
            availability_statuses=tuple(availability_statuses) if availability_statuses is not None else self._filters.availability_statuses,
            status_filters=tuple(status_filters) if status_filters is not None else self._filters.status_filters,
            entitlement_filter=entitlement_filter or self._filters.entitlement_filter,
            favorites_only=self._filters.favorites_only if favorites_only is None else bool(favorites_only),
            include_hidden=self._filters.include_hidden if include_hidden is None else bool(include_hidden),
        )
        self._sync_preferences()
        return self._filters

    def query_overlays(self) -> tuple[OverlayBrowserOverlayItem, ...]:
        layout_id = self._resolved_layout_id()
        catalog = self._registry.catalog_entries(
            filter_spec=OverlayCatalogFilter(
                query=self._filters.query,
                categories=(self._selection.selected_category,) if self._selection.selected_category else (),
                tags=self._filters.tags,
                premium_tiers=("free",) if self._filters.entitlement_filter == "free" else ("premium",) if self._filters.entitlement_filter == "premium" else (),
                availability_statuses=self._filters.availability_statuses,
                simulators=self._filters.simulators,
                favorites_only=self._filters.favorites_only,
                entitled_only=self._filters.entitlement_filter == "entitled_only",
                include_locked=True,
                include_hidden=self._filters.include_hidden,
            ),
            favorites=set(self._layouts.favorite_overlay_ids()),
            entitlement_resolver=self._entitlements,
            entitlement_context=self._entitlement_context,
        )
        items: list[OverlayBrowserOverlayItem] = []
        for entry in catalog:
            instances = self._layouts.overlay_instances_for_overlay(layout_id, entry.overlay_id) if layout_id else ()
            installed = bool(instances)
            active = any(instance.enabled for instance in instances)
            locked = entry.access_state in {"preview_only", "locked"}
            status = "active" if active else "installed" if installed else "locked" if locked else "available"
            if self._filters.status_filters and status not in set(self._filters.status_filters):
                continue
            items.append(
                OverlayBrowserOverlayItem(
                    overlay_id=entry.overlay_id,
                    display_name=entry.display_name,
                    category=entry.category,
                    tags=entry.tags,
                    favorite=entry.favorite,
                    selected=entry.overlay_id == self._selection.selected_overlay_id,
                    installed=installed,
                    active=active,
                    locked=locked,
                    entitled=entry.can_activate,
                    access_state=entry.access_state,
                    access_badge=entry.access_badge,
                    premium_tier=entry.premium_tier,
                    availability_status=entry.availability_status,
                    preview_asset=entry.preview_asset,
                    supported_simulators=entry.supported_simulators,
                    status=status,
                )
            )
        return tuple(items)

    def start_preview(self, overlay_id: str | None = None) -> OverlayBrowserPreviewState:
        target_overlay_id = str(overlay_id or self._selection.selected_overlay_id or "")
        if not target_overlay_id:
            raise KeyError("No overlay selected for preview")
        definition = self._registry.get(target_overlay_id)
        entitlement = self._entitlements.evaluate(definition, context=self._entitlement_context)
        if not entitlement.can_preview:
            raise PermissionError(entitlement.reason or "Preview is not available for this overlay")
        self._preview_overlay_id = target_overlay_id
        self._preview_session_id = f"preview-{uuid.uuid4().hex[:10]}"
        return self._preview_state(definition, (), entitlement)

    def stop_preview(self) -> None:
        self._preview_overlay_id = ""
        self._preview_session_id = ""

    def toggle_favorite(self, overlay_id: str | None = None) -> bool:
        target_overlay_id = str(overlay_id or self._selection.selected_overlay_id or "")
        if not target_overlay_id:
            raise KeyError("No overlay selected")
        return self._layouts.toggle_overlay_favorite(target_overlay_id)

    def install_overlay(
        self,
        overlay_id: str | None = None,
        *,
        settings: dict[str, object] | None = None,
    ) -> OverlayInstance:
        target_overlay_id = str(overlay_id or self._selection.selected_overlay_id or "")
        layout_id = self._resolved_layout_id()
        if not target_overlay_id or not layout_id:
            raise KeyError("Overlay and layout selection are required")
        instance = self._layouts.install_overlay(layout_id, target_overlay_id, settings=settings)
        self._selection = OverlayBrowserSelectionState(
            selected_category=self._selection.selected_category,
            selected_overlay_id=target_overlay_id,
            selected_layout_id=layout_id,
        )
        self._sync_preferences()
        return instance

    def uninstall_overlay(self, overlay_id: str | None = None) -> int:
        target_overlay_id = str(overlay_id or self._selection.selected_overlay_id or "")
        layout_id = self._resolved_layout_id()
        if not target_overlay_id or not layout_id:
            raise KeyError("Overlay and layout selection are required")
        return self._layouts.uninstall_overlay(layout_id=layout_id, overlay_id=target_overlay_id)

    def activate_layout(self, layout_id: str | None = None) -> None:
        target_layout_id = str(layout_id or self._resolved_layout_id() or "")
        if not target_layout_id:
            raise KeyError("No layout selected")
        self._layouts.activate_layout(target_layout_id)
        self._selection = OverlayBrowserSelectionState(
            selected_category=self._selection.selected_category,
            selected_overlay_id=self._selection.selected_overlay_id,
            selected_layout_id=target_layout_id,
        )
        self._sync_preferences()

    def deactivate_layout(self, layout_id: str | None = None) -> None:
        target_layout_id = str(layout_id or self._resolved_layout_id() or "")
        if not target_layout_id:
            raise KeyError("No layout selected")
        self._layouts.deactivate_layout(target_layout_id)
        self._selection = OverlayBrowserSelectionState(
            selected_category=self._selection.selected_category,
            selected_overlay_id=self._selection.selected_overlay_id,
            selected_layout_id=self._resolved_layout_id(),
        )
        self._sync_preferences()

    def activate_overlay(self, overlay_id: str | None = None) -> tuple[OverlayInstance, ...]:
        target_overlay_id = str(overlay_id or self._selection.selected_overlay_id or "")
        layout_id = self._resolved_layout_id()
        instances = self._layouts.overlay_instances_for_overlay(layout_id, target_overlay_id)
        if not instances:
            raise KeyError(f"Overlay '{target_overlay_id}' is not installed in layout '{layout_id}'")
        return tuple(self._layouts.set_overlay_instance_enabled(instance.instance_id, True) for instance in instances)

    def deactivate_overlay(self, overlay_id: str | None = None) -> tuple[OverlayInstance, ...]:
        target_overlay_id = str(overlay_id or self._selection.selected_overlay_id or "")
        layout_id = self._resolved_layout_id()
        instances = self._layouts.overlay_instances_for_overlay(layout_id, target_overlay_id)
        if not instances:
            raise KeyError(f"Overlay '{target_overlay_id}' is not installed in layout '{layout_id}'")
        return tuple(self._layouts.set_overlay_instance_enabled(instance.instance_id, False) for instance in instances)

    def update_overlay_settings(
        self,
        changes: dict[str, object],
        *,
        overlay_id: str | None = None,
    ) -> tuple[OverlayInstance, list[str]]:
        target_overlay_id = str(overlay_id or self._selection.selected_overlay_id or "")
        instance = self._selected_or_first_instance(target_overlay_id)
        if instance is None:
            raise KeyError(f"Overlay '{target_overlay_id}' is not installed in selected layout")
        return self._layouts.update_overlay_instance_settings(instance.instance_id, changes)

    def page_state(self) -> OverlayBrowserPageState:
        overlays = self.query_overlays()
        layouts = self._layout_items()
        categories = self._category_items(overlays)
        selected_overlay_id = self._selection.selected_overlay_id
        if selected_overlay_id not in {item.overlay_id for item in overlays} and overlays:
            selected_overlay_id = overlays[0].overlay_id
        selection = OverlayBrowserSelectionState(
            selected_category=self._selection.selected_category,
            selected_overlay_id=selected_overlay_id,
            selected_layout_id=self._resolved_layout_id(),
        )
        self._selection = selection
        self._sync_preferences()
        selected_overlay = self._selected_overlay_detail(selection.selected_overlay_id)
        return OverlayBrowserPageState(
            filters=self._filters,
            selection=selection,
            entitlement=OverlayBrowserEntitlementState(
                premium_active=self._entitlement_context.premium_active,
                locked_overlays_visible=True,
                feature_flags=tuple(sorted(self._entitlement_context.feature_flags)),
            ),
            categories=categories,
            overlays=tuple(
                OverlayBrowserOverlayItem(
                    overlay_id=item.overlay_id,
                    display_name=item.display_name,
                    category=item.category,
                    tags=item.tags,
                    favorite=item.favorite,
                    selected=item.overlay_id == selection.selected_overlay_id,
                    installed=item.installed,
                    active=item.active,
                    locked=item.locked,
                    entitled=item.entitled,
                    access_state=item.access_state,
                    access_badge=item.access_badge,
                    premium_tier=item.premium_tier,
                    availability_status=item.availability_status,
                    preview_asset=item.preview_asset,
                    supported_simulators=item.supported_simulators,
                    status=item.status,
                )
                for item in overlays
            ),
            layouts=layouts,
            selected_overlay=selected_overlay,
        )

    def _category_items(self, overlays: tuple[OverlayBrowserOverlayItem, ...]) -> tuple[OverlayBrowserCategoryItem, ...]:
        counts: dict[str, int] = {}
        for item in overlays:
            counts[item.category] = counts.get(item.category, 0) + 1
        return tuple(
            OverlayBrowserCategoryItem(
                category=category,
                label=category.title(),
                count=counts[category],
                selected=category == self._selection.selected_category,
            )
            for category in sorted(counts)
        )

    def _layout_items(self) -> tuple[OverlayBrowserLayoutItem, ...]:
        selected_layout_id = self._resolved_layout_id()
        return tuple(
            OverlayBrowserLayoutItem(
                layout_id=layout.layout_id,
                display_name=layout.display_name,
                description=layout.description,
                favorite=layout.favorite,
                selected=layout.layout_id == selected_layout_id,
                active=layout.active,
                tags=layout.tags,
                simulator_filter=layout.simulator_filter,
                car_filter=layout.car_filter,
                session_type_filter=layout.session_type_filter,
            )
            for layout in self._layouts.layouts()
        )

    def _selected_overlay_detail(self, overlay_id: str) -> OverlayBrowserOverlayDetail | None:
        if not overlay_id:
            return None
        definition = self._registry.get(overlay_id)
        entitlement = self._entitlements.evaluate(definition, context=self._entitlement_context)
        layout_id = self._resolved_layout_id()
        instances = self._layouts.overlay_instances_for_overlay(layout_id, overlay_id) if layout_id else ()
        active = any(instance.enabled for instance in instances)
        preview = self._preview_state(definition, instances, entitlement)
        settings_sections = self._settings_sections(definition, instances[0] if instances else None, entitlement.can_view_settings, entitlement.can_activate)
        actions = self._actions_for_overlay(definition, instances, entitlement, layout_id, active)
        return OverlayBrowserOverlayDetail(
            overlay_id=definition.overlay_id,
            display_name=definition.display_name,
            short_description=definition.short_description,
            category=definition.category,
            tags=definition.tags,
            supported_simulators=definition.supported_simulators,
            premium_tier=definition.premium_tier,
            availability_status=definition.availability_status,
            favorite=definition.overlay_id in set(self._layouts.favorite_overlay_ids()),
            entitled=entitlement.can_activate,
            locked=entitlement.locked,
            access_state=entitlement.access_state,
            access_badge=entitlement.access_badge,
            lock_reason=entitlement.reason,
            installed=bool(instances),
            active=active,
            installed_instance_ids=tuple(instance.instance_id for instance in instances),
            selected_layout_id=layout_id,
            preview=preview,
            actions=actions,
            settings_sections=settings_sections,
        )

    def _preview_state(
        self,
        definition: OverlayDefinition,
        instances: tuple[OverlayInstance, ...],
        entitlement,
    ) -> OverlayBrowserPreviewState:
        active_instance = next((instance for instance in instances if instance.enabled), None)
        if self._preview_overlay_id == definition.overlay_id:
            return OverlayBrowserPreviewState(
                session_id=self._preview_session_id,
                overlay_id=definition.overlay_id,
                mode="preview",
                title="Preview Running",
                message="Interactive preview session is active in the browser.",
                preview_asset=definition.preview_asset_ref,
                instance_id=active_instance.instance_id if active_instance else "",
                layout_id=self._resolved_layout_id(),
                active=True,
            )
        if active_instance is not None:
            return OverlayBrowserPreviewState(
                session_id="",
                overlay_id=definition.overlay_id,
                mode="live_instance",
                title="Active Overlay",
                message="The selected overlay is active in the current layout.",
                preview_asset=definition.preview_asset_ref,
                instance_id=active_instance.instance_id,
                layout_id=self._resolved_layout_id(),
                active=True,
            )
        if entitlement.preview_only:
            return OverlayBrowserPreviewState(
                session_id="",
                overlay_id=definition.overlay_id,
                mode="preview_only",
                title="Premium Preview",
                message=entitlement.upsell_message or entitlement.reason,
                preview_asset=definition.preview_asset_ref,
                layout_id=self._resolved_layout_id(),
                active=False,
            )
        if entitlement.locked:
            return OverlayBrowserPreviewState(
                session_id="",
                overlay_id=definition.overlay_id,
                mode="locked_placeholder",
                title="Locked Preview",
                message=entitlement.reason,
                preview_asset=definition.preview_asset_ref,
                layout_id=self._resolved_layout_id(),
                active=False,
            )
        if entitlement.can_preview and definition.preview_asset_ref:
            return OverlayBrowserPreviewState(
                session_id="",
                overlay_id=definition.overlay_id,
                mode="asset_placeholder",
                title="Preview Placeholder",
                message="This overlay is not active in the selected layout.",
                preview_asset=definition.preview_asset_ref,
                layout_id=self._resolved_layout_id(),
                active=False,
            )
        return OverlayBrowserPreviewState(
            session_id="",
            overlay_id=definition.overlay_id,
            mode="unavailable",
            title="Preview Unavailable",
            message="No preview asset is available for this overlay.",
            layout_id=self._resolved_layout_id(),
            active=False,
        )

    def _actions_for_overlay(
        self,
        definition: OverlayDefinition,
        instances: tuple[OverlayInstance, ...],
        entitlement,
        layout_id: str,
        active: bool,
    ) -> tuple[OverlayBrowserAction, ...]:
        installed = bool(instances)
        can_preview = entitlement.can_preview and bool(definition.preview_asset_ref or definition.capabilities.preview_supported)
        favorite = definition.overlay_id in set(self._layouts.favorite_overlay_ids())
        actions = [
            OverlayBrowserAction(
                action_id="install",
                label="Install to Layout",
                enabled=not installed and entitlement.can_activate and bool(layout_id),
                visible=not installed,
                reason="" if entitlement.can_activate else entitlement.reason,
                tone="primary",
            ),
            OverlayBrowserAction(
                action_id="activate",
                label="Activate Overlay",
                enabled=installed and not active,
                visible=installed and not active,
                tone="primary",
            ),
            OverlayBrowserAction(
                action_id="deactivate",
                label="Deactivate Overlay",
                enabled=installed and active,
                visible=installed and active,
            ),
            OverlayBrowserAction(
                action_id="uninstall",
                label="Remove from Layout",
                enabled=installed,
                visible=installed,
                tone="danger",
            ),
            OverlayBrowserAction(
                action_id="toggle_favorite",
                label="Unfavorite" if favorite else "Favorite",
                enabled=True,
                tone="secondary",
            ),
            OverlayBrowserAction(
                action_id="start_preview",
                label="Start Preview",
                enabled=can_preview and self._preview_overlay_id != definition.overlay_id,
                visible=can_preview and self._preview_overlay_id != definition.overlay_id,
            ),
            OverlayBrowserAction(
                action_id="stop_preview",
                label="Stop Preview",
                enabled=self._preview_overlay_id == definition.overlay_id,
                visible=self._preview_overlay_id == definition.overlay_id,
            ),
            OverlayBrowserAction(
                action_id="edit_settings",
                label="Edit Settings",
                enabled=entitlement.can_activate and installed,
                visible=entitlement.can_view_settings,
                reason="" if entitlement.can_activate else entitlement.reason,
            ),
        ]
        return tuple(action for action in actions if action.visible)

    def _settings_sections(
        self,
        definition: OverlayDefinition,
        instance: OverlayInstance | None,
        settings_visible: bool,
        editable: bool,
    ) -> tuple[OverlayBrowserSettingsSectionView, ...]:
        effective_instance = instance
        if effective_instance is None:
            last_used = self._layouts.last_used_settings_for(definition.overlay_id)
            if last_used is not None:
                effective_instance = OverlayInstance(
                    instance_id=f"last-used:{definition.overlay_id}",
                    overlay_id=definition.overlay_id,
                    preset_id="",
                    name=definition.display_name,
                    enabled=False,
                    settings=dict(last_used.values),
                )
        if not settings_visible:
            return ()
        if self._settings_service is not None and definition.settings_schema_ref:
            try:
                schema = self._settings_service.schema(definition.settings_schema_ref)
            except KeyError:
                schema = None
            if schema is not None:
                return self._settings_sections_from_schema(schema.sections, schema.fields, definition.settings_schema_ref, effective_instance, editable)
        return self._settings_sections_from_inline_definition(definition, effective_instance, editable)

    def _settings_sections_from_schema(
        self,
        sections: tuple[OverlaySettingsSection, ...],
        fields: tuple[OverlaySettingsField, ...],
        schema_id: str,
        instance: OverlayInstance | None,
        entitled: bool,
    ) -> tuple[OverlayBrowserSettingsSectionView, ...]:
        resolution = self._settings_service.merge_overrides(schema_id, instance.settings if instance else {})
        visible = set(resolution.visible_field_keys)
        issues_by_field = _issues_by_field(resolution.issues)
        section_views: list[OverlayBrowserSettingsSectionView] = []
        defaults = self._settings_service.default_values(schema_id)
        for section in sorted(sections, key=lambda item: item.sort_order):
            section_fields: list[OverlayBrowserSettingFieldView] = []
            for field in fields:
                if field.section != section.key or field.field_key not in visible:
                    continue
                source = "instance_override" if instance and field.field_key in instance.settings else "default"
                section_fields.append(
                    OverlayBrowserSettingFieldView(
                        field_key=field.field_key,
                        label=field.label,
                        description=field.description,
                        kind=field.kind,
                        section_key=section.key,
                        current_value=resolution.values.get(field.field_key),
                        default_value=defaults.get(field.field_key),
                        source=source,
                        editable=entitled and not field.premium_only,
                        premium_only=field.premium_only,
                        advanced=field.advanced,
                        min_value=field.min_value,
                        max_value=field.max_value,
                        step=field.step,
                        unit=field.unit,
                        options=tuple(
                            OverlayBrowserSettingOption(
                                value=option.value,
                                label=option.label,
                                description=option.description,
                                premium_only=option.premium_only,
                            )
                            for option in field.options
                        ),
                        issues=tuple(issue.message for issue in issues_by_field.get(field.field_key, ())),
                    )
                )
            if section_fields:
                section_views.append(
                    OverlayBrowserSettingsSectionView(
                        section_key=section.key,
                        label=section.label,
                        description=section.description,
                        fields=tuple(section_fields),
                    )
                )
        return tuple(section_views)

    def _settings_sections_from_inline_definition(
        self,
        definition: OverlayDefinition,
        instance: OverlayInstance | None,
        entitled: bool,
    ) -> tuple[OverlayBrowserSettingsSectionView, ...]:
        values, issues = self._registry.validate_settings(definition.overlay_id, instance.settings if instance else {}, include_defaults=True)
        issues_by_field = _legacy_issues_by_field(issues)
        sections: dict[str, list[OverlayBrowserSettingFieldView]] = {}
        defaults = definition.default_settings()
        for field in definition.settings_schema:
            source = "instance_override" if instance and field.key in instance.settings else "default"
            sections.setdefault(field.section, []).append(
                OverlayBrowserSettingFieldView(
                    field_key=field.key,
                    label=field.label,
                    description=field.description,
                    kind=field.kind,
                    section_key=field.section,
                    current_value=values.get(field.key),
                    default_value=defaults.get(field.key),
                    source=source,
                    editable=entitled and not field.premium,
                    premium_only=field.premium,
                    advanced=False,
                    min_value=field.min_value,
                    max_value=field.max_value,
                    step=field.step,
                    unit=field.unit,
                    options=tuple(
                        OverlayBrowserSettingOption(
                            value=option.value,
                            label=option.label,
                            description=option.description,
                        )
                        for option in field.options
                    ),
                    issues=tuple(issues_by_field.get(field.key, ())),
                )
            )
        return tuple(
            OverlayBrowserSettingsSectionView(
                section_key=section_key,
                label=section_key.replace("_", " ").title(),
                description="",
                fields=tuple(fields),
            )
            for section_key, fields in sections.items()
        )

    def _selected_or_first_instance(self, overlay_id: str) -> OverlayInstance | None:
        layout_id = self._resolved_layout_id()
        instances = self._layouts.overlay_instances_for_overlay(layout_id, overlay_id) if layout_id else ()
        return instances[0] if instances else None

    def _resolved_layout_id(self) -> str:
        selected = self._selection.selected_layout_id
        if selected:
            return selected
        document = self._layouts.document()
        if document.active_preset_id:
            return document.active_preset_id
        layouts = self._layouts.layouts()
        return layouts[0].layout_id if layouts else ""

    def _sync_preferences(self) -> None:
        self._layouts.update_browser_preferences(
            selected_category=self._selection.selected_category,
            selected_overlay_id=self._selection.selected_overlay_id,
            selected_layout_id=self._selection.selected_layout_id,
            search_query=self._filters.query,
            tag_filters=self._filters.tags,
            simulator_filters=self._filters.simulators,
            availability_filters=self._filters.availability_statuses,
            status_filters=self._filters.status_filters,
            entitlement_filter=self._filters.entitlement_filter,
            favorites_only=self._filters.favorites_only,
            include_hidden=self._filters.include_hidden,
        )


def _issues_by_field(
    issues: tuple[OverlaySettingsValidationIssue, ...],
) -> dict[str, list[OverlaySettingsValidationIssue]]:
    grouped: dict[str, list[OverlaySettingsValidationIssue]] = {}
    for issue in issues:
        grouped.setdefault(issue.field_key, []).append(issue)
    return grouped


def _legacy_issues_by_field(issues: list[str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for issue in issues:
        prefix, separator, remainder = issue.partition(":")
        key = prefix if separator else ""
        grouped.setdefault(key, []).append(remainder.strip() if separator else issue)
    return grouped
