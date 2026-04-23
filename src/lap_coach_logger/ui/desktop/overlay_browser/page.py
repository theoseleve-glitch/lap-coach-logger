"""Immersive overlay workspace page assembly for the LAP COACH desktop shell."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import QFileDialog, QFrame, QInputDialog, QLabel, QSplitter, QVBoxLayout, QWidget

from lap_coach_logger.ui.desktop.overlay_browser.controller import OverlayBrowserPageController
from lap_coach_logger.ui.desktop.overlay_browser.design_system import (
    OverlayBrowserDesignTokens,
    default_overlay_browser_tokens,
    rgba,
)
from lap_coach_logger.ui.desktop.overlay_browser.widgets import (
    BottomActionBar,
    OverlaySettingsPanel,
    OverlaySidebar,
    OverlayWorkspaceTopStrip,
    PreviewCanvas,
)


@dataclass(slots=True)
class OverlayWorkspaceShellCallbacks:
    switch_page: Callable[[str], None] | None = None
    step_page: Callable[[int], None] | None = None
    open_settings: Callable[[], None] | None = None
    open_about: Callable[[], None] | None = None
    open_output: Callable[[], None] | None = None
    open_logs: Callable[[], None] | None = None
    open_config: Callable[[], None] | None = None
    resume_monitoring: Callable[[], None] | None = None
    pause_monitoring: Callable[[], None] | None = None


class OverlayBrowserPage(QWidget):
    """Dedicated full-window overlay workspace."""

    def __init__(
        self,
        *,
        controller: OverlayBrowserPageController,
        tokens: OverlayBrowserDesignTokens | None = None,
        shell_callbacks: OverlayWorkspaceShellCallbacks | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._tokens = tokens or default_overlay_browser_tokens()
        self._shell_callbacks = shell_callbacks or OverlayWorkspaceShellCallbacks()

        self.setObjectName("OverlayWorkspacePage")

        root = QVBoxLayout(self)
        root.setContentsMargins(
            self._tokens.layout.overlay_shell_margin_px,
            self._tokens.layout.overlay_shell_margin_px,
            self._tokens.layout.overlay_shell_margin_px,
            self._tokens.layout.overlay_shell_margin_px,
        )
        root.setSpacing(self._tokens.layout.overlay_pane_gap_px)

        self._top_strip = OverlayWorkspaceTopStrip(tokens=self._tokens)
        root.addWidget(self._top_strip)

        self._splitter = QSplitter()
        self._splitter.setObjectName("OverlayWorkspaceSplitter")
        self._splitter.setChildrenCollapsible(False)
        root.addWidget(self._splitter, 1)

        self._sidebar = OverlaySidebar(tokens=self._tokens)
        self._preview = PreviewCanvas(tokens=self._tokens)
        self._settings = OverlaySettingsPanel(tokens=self._tokens)

        self._splitter.addWidget(self._sidebar)
        self._splitter.addWidget(self._preview)
        self._splitter.addWidget(self._settings)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 0)
        self._splitter.setSizes(
            [
                self._tokens.layout.overlay_sidebar_width_px,
                900,
                self._tokens.layout.overlay_settings_width_px,
            ]
        )

        status_row = QFrame()
        status_row.setObjectName("OverlayWorkspaceStatusRow")
        status_layout = QVBoxLayout(status_row)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(0)
        self._message = QLabel("")
        self._message.setObjectName("OverlayWorkspaceMessage")
        self._message.setVisible(False)
        status_layout.addWidget(self._message)
        root.addWidget(status_row)

        self._bottom = BottomActionBar(tokens=self._tokens)
        root.addWidget(self._bottom)

        self._wire()
        self._apply_style()
        self._controller.refresh()

    def set_shell_status(self, *, status: str, detail: str, monitoring_active: bool) -> None:
        self._top_strip.set_status(status=status, detail=detail, monitoring_active=monitoring_active)

    def _wire(self) -> None:
        self._top_strip.page_requested.connect(self._handle_page_request)
        self._top_strip.page_step_requested.connect(self._handle_page_step)
        self._top_strip.open_settings_requested.connect(self._invoke_callback("open_settings"))
        self._top_strip.open_about_requested.connect(self._invoke_callback("open_about"))
        self._top_strip.open_output_requested.connect(self._invoke_callback("open_output"))
        self._top_strip.open_logs_requested.connect(self._invoke_callback("open_logs"))
        self._top_strip.open_config_requested.connect(self._invoke_callback("open_config"))
        self._top_strip.resume_requested.connect(self._invoke_callback("resume_monitoring"))
        self._top_strip.pause_requested.connect(self._invoke_callback("pause_monitoring"))

        self._sidebar.search_changed.connect(self._controller.set_search_query)
        self._sidebar.entitlement_changed.connect(self._controller.set_entitlement_filter)
        self._sidebar.favorites_only_changed.connect(self._controller.set_favorites_only)
        self._sidebar.include_hidden_changed.connect(self._controller.set_include_hidden)
        self._sidebar.category_selected.connect(self._controller.select_category)
        self._sidebar.overlay_selected.connect(self._controller.select_overlay)
        self._sidebar.favorite_toggled.connect(self._controller.toggle_favorite)

        self._preview.overlay_action_requested.connect(self._controller.run_overlay_action)
        self._settings.overlay_action_requested.connect(self._controller.run_overlay_action)
        self._settings.apply_requested.connect(self._controller.apply_setting_changes)

        self._bottom.layout_selected.connect(self._controller.select_layout)
        self._bottom.action_requested.connect(self._handle_layout_action)

        self._controller.state_changed.connect(self._apply_state)
        self._controller.preview_changed.connect(self._preview.apply_model)
        self._controller.message_emitted.connect(self._show_message)
        self._controller.error_emitted.connect(self._show_error)

    def _invoke_callback(self, attr_name: str):
        def _callback(*_args) -> None:
            callback = getattr(self._shell_callbacks, attr_name, None)
            if callable(callback):
                callback()

        return _callback

    def _handle_page_request(self, page_id: str) -> None:
        callback = self._shell_callbacks.switch_page
        if callable(callback):
            callback(page_id)

    def _handle_page_step(self, delta: int) -> None:
        callback = self._shell_callbacks.step_page
        if callable(callback):
            callback(int(delta))

    def _apply_state(self, state) -> None:  # noqa: ANN001
        self._sidebar.apply_filters(
            query=state.filters.query,
            entitlement_filter=state.filters.entitlement_filter,
            favorites_only=state.filters.favorites_only,
            include_hidden=state.filters.include_hidden,
        )
        self._sidebar.apply_state(state.categories, state.overlays)
        self._preview.apply_detail(state.selected_overlay)
        self._settings.apply_detail(state.selected_overlay)
        self._bottom.apply_layouts(state.layouts)

    def _handle_layout_action(self, action_id: str) -> None:
        if action_id == "create_layout":
            name, accepted = QInputDialog.getText(self, "Create Layout", "Layout name:", text="New Layout")
            if accepted:
                self._controller.create_layout(name or "New Layout")
            return
        if action_id == "clone_layout":
            self._controller.clone_selected_layout()
            return
        if action_id == "rename_layout":
            state = self._controller.page_state
            current = ""
            if state is not None:
                selected = next((layout for layout in state.layouts if layout.selected), None)
                current = selected.display_name if selected is not None else ""
            name, accepted = QInputDialog.getText(self, "Rename Layout", "Layout name:", text=current)
            if accepted and name.strip():
                self._controller.rename_selected_layout(name)
            return
        if action_id == "import_layout":
            path, _filter = QFileDialog.getOpenFileName(
                self,
                "Import Layout",
                "",
                "Overlay Layout (*.json);;JSON (*.json);;All Files (*)",
            )
            if path:
                self._controller.import_layout(path)
            return
        if action_id == "export_layout":
            path, _filter = QFileDialog.getSaveFileName(
                self,
                "Export Layout",
                "overlay-layout.json",
                "Overlay Layout (*.json);;JSON (*.json)",
            )
            if path:
                self._controller.export_selected_layout(Path(path))
            return
        if action_id == "activate_layout":
            self._controller.activate_selected_layout()
            return
        self._show_error(f"Unknown layout action '{action_id}'.")

    def _show_error(self, message: str) -> None:
        self._message.setText(message)
        self._message.setProperty("error", True)
        self._message.setVisible(bool(message))
        self.style().unpolish(self._message)
        self.style().polish(self._message)

    def _show_message(self, message: str) -> None:
        self._message.setText(message)
        self._message.setProperty("error", False)
        self._message.setVisible(bool(message))
        self.style().unpolish(self._message)
        self.style().polish(self._message)

    def _apply_style(self) -> None:
        t = self._tokens
        self.setStyleSheet(
            f"""
            QWidget#OverlayWorkspacePage {{
                background:
                    qlineargradient(
                        x1:0, y1:0, x2:1, y2:1,
                        stop:0 {t.colors.page_bg_alt},
                        stop:0.48 {t.colors.page_bg},
                        stop:1 #030405
                    );
            }}
            QSplitter#OverlayWorkspaceSplitter::handle {{
                background: transparent;
                width: {t.layout.overlay_pane_gap_px}px;
            }}
            QLabel#OverlayWorkspaceMessage {{
                padding: 0 4px;
                color: {rgba(t.colors.steel, 0.78)};
                font-size: {t.typography.micro_px}px;
                font-weight: 600;
            }}
            QLabel#OverlayWorkspaceMessage[error="true"] {{
                color: {t.colors.safety_red};
            }}
            """
        )
