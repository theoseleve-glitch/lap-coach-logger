"""Qt-friendly controller for the overlay browser workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from lap_coach_logger.overlays import (
    OverlayBrowserOverlayDetail,
    OverlayBrowserPageService,
    OverlayBrowserPageState,
    OverlayLayoutExportBundle,
    OverlayLayoutPresetService,
    OverlayRegistry,
    OverlayTelemetryBindingResult,
    OverlayTelemetryBindingService,
)


@dataclass(frozen=True, slots=True)
class OverlayBrowserPreviewStat:
    label: str
    value: str
    tone: str = "muted"


@dataclass(frozen=True, slots=True)
class OverlayBrowserPreviewCardModel:
    overlay_id: str
    title: str
    subtitle: str
    badge: str
    message: str
    asset_ref: str
    locked: bool
    active: bool
    health_status: str = ""
    stats: tuple[OverlayBrowserPreviewStat, ...] = ()


class OverlayBrowserPageController(QObject):
    """Thin Qt adapter around the overlay browser and layout backend services."""

    state_changed = Signal(object)
    preview_changed = Signal(object)
    message_emitted = Signal(str)
    error_emitted = Signal(str)

    def __init__(
        self,
        *,
        registry: OverlayRegistry,
        browser_service: OverlayBrowserPageService,
        layout_service: OverlayLayoutPresetService,
        telemetry_bindings: OverlayTelemetryBindingService | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._registry = registry
        self._browser = browser_service
        self._layouts = layout_service
        self._telemetry = telemetry_bindings
        self._page_state: OverlayBrowserPageState | None = None
        self._live_snapshot: dict[str, object] | None = None

    @property
    def page_state(self) -> OverlayBrowserPageState | None:
        return self._page_state

    def refresh(self) -> OverlayBrowserPageState:
        state = self._browser.page_state()
        self._page_state = state
        self.state_changed.emit(state)
        self.preview_changed.emit(self.preview_model())
        return state

    def set_live_snapshot(self, snapshot: dict[str, object] | None) -> None:
        self._live_snapshot = dict(snapshot or {}) if snapshot else None
        self.preview_changed.emit(self.preview_model())

    def select_category(self, category: str) -> OverlayBrowserPageState:
        self._browser.set_selected_category(category)
        return self.refresh()

    def select_overlay(self, overlay_id: str) -> OverlayBrowserPageState:
        self._browser.set_selected_overlay(overlay_id)
        return self.refresh()

    def select_layout(self, layout_id: str) -> OverlayBrowserPageState:
        self._browser.set_selected_layout(layout_id)
        return self.refresh()

    def set_search_query(self, query: str) -> OverlayBrowserPageState:
        self._browser.set_search_query(query)
        return self.refresh()

    def set_favorites_only(self, enabled: bool) -> OverlayBrowserPageState:
        self._browser.update_filters(favorites_only=enabled)
        return self.refresh()

    def set_include_hidden(self, enabled: bool) -> OverlayBrowserPageState:
        self._browser.update_filters(include_hidden=enabled)
        return self.refresh()

    def set_entitlement_filter(self, value: str) -> OverlayBrowserPageState:
        self._browser.update_filters(entitlement_filter=value)
        return self.refresh()

    def toggle_favorite(self, overlay_id: str | None = None) -> OverlayBrowserPageState:
        try:
            is_favorite = self._browser.toggle_favorite(overlay_id)
        except Exception as exc:
            self.error_emitted.emit(str(exc))
            return self.refresh()
        self.message_emitted.emit("Overlay favorited." if is_favorite else "Overlay removed from favorites.")
        return self.refresh()

    def run_overlay_action(self, action_id: str, *, overlay_id: str | None = None) -> OverlayBrowserPageState:
        try:
            if action_id == "install":
                self._browser.install_overlay(overlay_id)
                self.message_emitted.emit("Overlay installed into the selected layout.")
            elif action_id == "activate":
                self._browser.activate_overlay(overlay_id)
                self.message_emitted.emit("Overlay activated.")
            elif action_id == "deactivate":
                self._browser.deactivate_overlay(overlay_id)
                self.message_emitted.emit("Overlay deactivated.")
            elif action_id == "uninstall":
                self._browser.uninstall_overlay(overlay_id)
                self.message_emitted.emit("Overlay removed from the selected layout.")
            elif action_id == "toggle_favorite":
                return self.toggle_favorite(overlay_id)
            elif action_id == "start_preview":
                self._browser.start_preview(overlay_id)
                self.message_emitted.emit("Preview mode started.")
            elif action_id == "stop_preview":
                self._browser.stop_preview()
                self.message_emitted.emit("Preview mode stopped.")
            elif action_id == "edit_settings":
                self.message_emitted.emit("Edit settings in the right-hand panel.")
            else:
                self.error_emitted.emit(f"Unknown overlay action '{action_id}'.")
        except Exception as exc:
            self.error_emitted.emit(str(exc))
        return self.refresh()

    def apply_setting_changes(self, changes: dict[str, object]) -> OverlayBrowserPageState:
        if not changes:
            self.message_emitted.emit("No setting changes to apply.")
            return self.refresh()
        try:
            _instance, issues = self._browser.update_overlay_settings(changes)
        except Exception as exc:
            self.error_emitted.emit(str(exc))
            return self.refresh()
        if issues:
            self.message_emitted.emit("; ".join(issues))
        else:
            self.message_emitted.emit("Overlay settings updated.")
        return self.refresh()

    def activate_selected_layout(self) -> OverlayBrowserPageState:
        try:
            self._browser.activate_layout()
        except Exception as exc:
            self.error_emitted.emit(str(exc))
            return self.refresh()
        self.message_emitted.emit("Layout activated.")
        return self.refresh()

    def deactivate_selected_layout(self) -> OverlayBrowserPageState:
        try:
            self._browser.deactivate_layout()
        except Exception as exc:
            self.error_emitted.emit(str(exc))
            return self.refresh()
        self.message_emitted.emit("Layout deactivated.")
        return self.refresh()

    def create_layout(self, display_name: str = "New Layout") -> OverlayBrowserPageState:
        try:
            layout = self._layouts.create_layout(display_name=display_name, activate=False)
            self._browser.set_selected_layout(layout.layout_id)
        except Exception as exc:
            self.error_emitted.emit(str(exc))
            return self.refresh()
        self.message_emitted.emit(f"Layout '{layout.display_name}' created.")
        return self.refresh()

    def clone_selected_layout(self, display_name: str | None = None) -> OverlayBrowserPageState:
        selected_layout = self._selected_layout_id()
        if not selected_layout:
            self.error_emitted.emit("No layout selected.")
            return self.refresh()
        try:
            layout = self._layouts.clone_layout(selected_layout, display_name=display_name)
            self._browser.set_selected_layout(layout.layout_id)
        except Exception as exc:
            self.error_emitted.emit(str(exc))
            return self.refresh()
        self.message_emitted.emit(f"Layout cloned as '{layout.display_name}'.")
        return self.refresh()

    def rename_selected_layout(self, display_name: str) -> OverlayBrowserPageState:
        selected_layout = self._selected_layout_id()
        if not selected_layout:
            self.error_emitted.emit("No layout selected.")
            return self.refresh()
        try:
            layout = self._layouts.rename_layout(selected_layout, display_name)
        except Exception as exc:
            self.error_emitted.emit(str(exc))
            return self.refresh()
        self.message_emitted.emit(f"Layout renamed to '{layout.display_name}'.")
        return self.refresh()

    def delete_selected_layout(self) -> OverlayBrowserPageState:
        selected_layout = self._selected_layout_id()
        if not selected_layout:
            self.error_emitted.emit("No layout selected.")
            return self.refresh()
        try:
            self._layouts.delete_layout(selected_layout)
        except Exception as exc:
            self.error_emitted.emit(str(exc))
            return self.refresh()
        self.message_emitted.emit("Layout deleted.")
        return self.refresh()

    def export_selected_layout(self, path: str | Path | None = None) -> OverlayLayoutExportBundle | None:
        selected_layout = self._selected_layout_id()
        if not selected_layout:
            self.error_emitted.emit("No layout selected.")
            return None
        try:
            bundle = self._layouts.export_layout(selected_layout, path=path)
        except Exception as exc:
            self.error_emitted.emit(str(exc))
            return None
        self.message_emitted.emit("Layout exported.")
        return bundle

    def import_layout(self, source: str | Path | dict[str, object]) -> OverlayBrowserPageState:
        try:
            imported = self._layouts.import_layout(source)
            if imported:
                self._browser.set_selected_layout(imported[0].layout_id)
        except Exception as exc:
            self.error_emitted.emit(str(exc))
            return self.refresh()
        self.message_emitted.emit(f"Imported {len(imported)} layout(s).")
        return self.refresh()

    def preview_model(self) -> OverlayBrowserPreviewCardModel:
        detail = self._selected_overlay_detail()
        if detail is None:
            return OverlayBrowserPreviewCardModel(
                overlay_id="",
                title="No Overlay Selected",
                subtitle="Select an overlay from the catalog",
                badge="Idle",
                message="The center stage will show the selected overlay preview and its telemetry health.",
                asset_ref="",
                locked=False,
                active=False,
            )

        badge = detail.access_badge or ("Active" if detail.active else "Available")
        stats = self._stats_for_detail(detail)
        health_status = ""
        if self._telemetry is not None:
            try:
                definition = self._registry.get(detail.overlay_id)
                if self._live_snapshot:
                    binding = self._telemetry.bind_for_definition(definition, self._live_snapshot)
                else:
                    binding = self._telemetry.preview_binding_for_definition(definition)
            except Exception:
                binding = None
            if binding is not None:
                health_status = binding.health.status
                stats = _stats_from_binding(binding)

        return OverlayBrowserPreviewCardModel(
            overlay_id=detail.overlay_id,
            title=detail.display_name,
            subtitle=detail.category.replace("-", " ").title(),
            badge=badge,
            message=detail.preview.message or detail.short_description,
            asset_ref=detail.preview.preview_asset,
            locked=detail.locked,
            active=detail.active,
            health_status=health_status,
            stats=stats,
        )

    def _stats_for_detail(
        self,
        detail: OverlayBrowserOverlayDetail,
    ) -> tuple[OverlayBrowserPreviewStat, ...]:
        stats: list[OverlayBrowserPreviewStat] = [
            OverlayBrowserPreviewStat("Tier", detail.premium_tier.title(), "brand" if detail.premium_tier != "free" else "muted"),
            OverlayBrowserPreviewStat("Access", detail.access_badge, "danger" if detail.locked else "positive"),
            OverlayBrowserPreviewStat("Layout", detail.selected_layout_id or "-", "muted"),
        ]
        if detail.installed_instance_ids:
            stats.append(OverlayBrowserPreviewStat("Instances", str(len(detail.installed_instance_ids)), "muted"))
        return tuple(stats)

    def _selected_overlay_detail(self) -> OverlayBrowserOverlayDetail | None:
        state = self._page_state or self._browser.page_state()
        return state.selected_overlay

    def _selected_layout_id(self) -> str:
        state = self._page_state or self._browser.page_state()
        return state.selection.selected_layout_id


def _stats_from_binding(binding: OverlayTelemetryBindingResult) -> tuple[OverlayBrowserPreviewStat, ...]:
    tone = {
        "healthy": "positive",
        "preview": "brand",
        "degraded": "warning",
        "stale": "warning",
        "invalid": "danger",
        "missing": "danger",
    }.get(binding.health.status, "muted")
    stats: list[OverlayBrowserPreviewStat] = [
        OverlayBrowserPreviewStat("Health", binding.health.status.upper(), tone),
        OverlayBrowserPreviewStat("Fields", f"{binding.health.resolved_field_count}/{binding.health.total_field_count}", "muted"),
    ]
    scalar_count = 0
    for key, value in binding.values.items():
        if scalar_count >= 4:
            break
        if isinstance(value, bool):
            rendered = "ON" if value else "OFF"
        elif isinstance(value, int):
            rendered = str(value)
        elif isinstance(value, float):
            rendered = f"{value:.2f}"
        elif isinstance(value, str):
            rendered = value
        else:
            continue
        stats.append(OverlayBrowserPreviewStat(_humanize_key(key), rendered, "muted"))
        scalar_count += 1
    return tuple(stats)


def _humanize_key(value: str) -> str:
    return str(value).replace("_", " ").strip().title()
