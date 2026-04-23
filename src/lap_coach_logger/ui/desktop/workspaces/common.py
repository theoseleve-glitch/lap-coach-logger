"""Shared shell primitives for immersive desktop workspaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from lap_coach_logger.assets import monogram_path, overlay_workspace_hero_path, overlay_workspace_icon_path
from lap_coach_logger.ui.desktop.workspaces.design_system import WorkspaceDesignTokens, default_workspace_tokens, rgba


@dataclass(slots=True)
class WorkspaceShellCallbacks:
    switch_page: Callable[[str], None] | None = None
    step_page: Callable[[int], None] | None = None
    open_settings: Callable[[], None] | None = None
    open_about: Callable[[], None] | None = None
    open_output: Callable[[], None] | None = None
    open_logs: Callable[[], None] | None = None
    open_config: Callable[[], None] | None = None
    resume_monitoring: Callable[[], None] | None = None
    pause_monitoring: Callable[[], None] | None = None


def _icon(name: str) -> QIcon:
    path = overlay_workspace_icon_path(name)
    if path is not None and path.exists():
        return QIcon(str(path))
    return QIcon()


def _apply_icon(button: QToolButton | QPushButton, name: str, px: int) -> None:
    icon = _icon(name)
    if not icon.isNull():
        button.setIcon(icon)
        button.setIconSize(QSize(px, px))


class WorkspaceSurface(QFrame):
    """Flat premium surface used across immersive desktop workspaces."""

    def __init__(
        self,
        *,
        tokens: WorkspaceDesignTokens | None = None,
        variant: str = "panel",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tokens = tokens or default_workspace_tokens()
        self._variant = variant
        self.setObjectName(f"WorkspaceSurface_{variant}")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._apply_style()

    def _apply_style(self) -> None:
        t = self._tokens
        bg = t.colors.controls_bg
        radius = t.radii.lg
        border_alpha = t.surface.border_soft_alpha
        if self._variant == "hero":
            bg = t.colors.hero_bg
            radius = t.radii.xl
            border_alpha = t.surface.border_mid_alpha
        elif self._variant == "dock":
            bg = t.colors.dock_bg
            radius = t.radii.xl
            border_alpha = t.surface.border_mid_alpha
        elif self._variant == "rail":
            bg = t.colors.rail_bg
            radius = t.radii.xl
            border_alpha = t.surface.border_mid_alpha
        elif self._variant == "inspect":
            bg = t.colors.page_bg_alt
            radius = t.radii.lg
            border_alpha = t.surface.border_mid_alpha
        self.setStyleSheet(
            f"""
            QFrame#{self.objectName()} {{
                background: {rgba(bg, t.surface.fill_mid_alpha)};
                border: 1px solid {rgba(t.colors.chalk, border_alpha)};
                border-radius: {radius}px;
            }}
            """
        )


class WorkspacePanel(WorkspaceSurface):
    """Standard section panel with editorial heading stack."""

    def __init__(
        self,
        section: str,
        *,
        heading: str | None = None,
        variant: str = "panel",
        tokens: WorkspaceDesignTokens | None = None,
        parent: QWidget | None = None,
    ) -> None:
        self._tokens = tokens or default_workspace_tokens()
        super().__init__(tokens=self._tokens, variant=variant, parent=parent)
        self.setObjectName(f"WorkspacePanel_{variant}_{section.lower().replace(' ', '_')}")
        self._apply_style()
        root = QVBoxLayout(self)
        root.setContentsMargins(self._tokens.spacing.lg, self._tokens.spacing.lg, self._tokens.spacing.lg, self._tokens.spacing.lg)
        root.setSpacing(self._tokens.spacing.sm)
        self._root = root

        section_label = QLabel(section.upper())
        section_label.setObjectName("WorkspacePanelSection")
        root.addWidget(section_label)

        if heading:
            title = QLabel(heading)
            title.setObjectName("WorkspacePanelHeading")
            root.addWidget(title)

        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(self._tokens.spacing.sm)
        root.addLayout(self.content_layout, 1)
        self._apply_panel_style()

    def _apply_panel_style(self) -> None:
        t = self._tokens
        self.setStyleSheet(
            self.styleSheet()
            + f"""
            QLabel#WorkspacePanelSection {{
                color: {rgba(t.colors.steel, 0.78)};
                font-family: '{t.typography.mono_family}', 'Consolas', monospace;
                font-size: {t.typography.micro_px}px;
                font-weight: 700;
                letter-spacing: 1px;
            }}
            QLabel#WorkspacePanelHeading {{
                color: {t.colors.chalk};
                font-family: '{t.typography.display_family}', 'Segoe UI', sans-serif;
                font-size: {t.typography.section_px}px;
                font-weight: 700;
            }}
            """
        )


class WorkspaceSectionTabs(QFrame):
    """Compact chip tabs used by section-heavy workspaces."""

    section_requested = Signal(str)

    def __init__(
        self,
        sections: tuple[tuple[str, str], ...],
        *,
        current: str,
        tokens: WorkspaceDesignTokens | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tokens = tokens or default_workspace_tokens()
        self.setObjectName("WorkspaceSectionTabs")
        self._buttons: dict[str, QToolButton] = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(self._tokens.spacing.xs)
        for section_id, label in sections:
            button = QToolButton()
            button.setObjectName(f"WorkspaceSectionTab_{section_id}")
            button.setCheckable(True)
            button.setText(label.upper())
            button.clicked.connect(lambda _checked=False, section=section_id: self.section_requested.emit(section))
            self._buttons[section_id] = button
            root.addWidget(button)
        root.addStretch(1)
        self.set_current(current)
        self._apply_style()

    def set_current(self, section_id: str) -> None:
        for key, button in self._buttons.items():
            checked = key == section_id
            button.setChecked(checked)
            button.setEnabled(not checked)

    def _apply_style(self) -> None:
        t = self._tokens
        self.setStyleSheet(
            f"""
            QFrame#WorkspaceSectionTabs {{
                background: transparent;
                border: none;
            }}
            QToolButton {{
                min-height: 36px;
                padding: 0 14px;
                border-radius: {t.radii.md}px;
                background: {rgba(t.colors.chalk, 0.03)};
                border: 1px solid {rgba(t.colors.chalk, 0.07)};
                color: {rgba(t.colors.steel, 0.84)};
                font-family: '{t.typography.mono_family}', 'Consolas', monospace;
                font-size: {t.typography.micro_px}px;
                font-weight: 700;
                letter-spacing: 0.8px;
            }}
            QToolButton:hover {{
                background: {rgba(t.colors.chalk, 0.05)};
            }}
            QToolButton:checked {{
                background: {rgba(t.colors.safety_red, 0.15)};
                border-color: {rgba(t.colors.safety_red, 0.26)};
                color: {t.colors.chalk};
            }}
            """
        )


class WorkspaceTopStrip(QWidget):
    """Shared top strip for immersive desktop pages."""

    page_requested = Signal(str)
    page_step_requested = Signal(int)
    resume_requested = Signal()
    pause_requested = Signal()
    open_settings_requested = Signal()
    open_about_requested = Signal()
    open_output_requested = Signal()
    open_logs_requested = Signal()
    open_config_requested = Signal()

    def __init__(
        self,
        *,
        active_page: str,
        context_label: str | None = None,
        tokens: WorkspaceDesignTokens | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tokens = tokens or default_workspace_tokens()
        self._active_page = str(active_page or "dashboard").lower()
        self._monitoring_active = False
        self.setObjectName("WorkspaceTopStrip")
        self.setFixedHeight(self._tokens.layout.top_strip_height_px)

        root = QHBoxLayout(self)
        root.setContentsMargins(self._tokens.spacing.md, 0, self._tokens.spacing.md, 0)
        root.setSpacing(self._tokens.spacing.lg)

        brand = QFrame()
        brand.setObjectName("WorkspaceTopBrand")
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(self._tokens.spacing.sm)
        root.addWidget(brand)

        mono = monogram_path()
        if mono is not None and mono.exists():
            mark = QSvgWidget(str(mono))
            mark.setFixedSize(30, 30)
            mark.setStyleSheet("background: transparent;")
            brand_layout.addWidget(mark)

        brand_copy = QVBoxLayout()
        brand_copy.setContentsMargins(0, 0, 0, 0)
        brand_copy.setSpacing(0)
        brand_layout.addLayout(brand_copy)

        title = QLabel("LAP COACH")
        title.setObjectName("WorkspaceTopBrandTitle")
        brand_copy.addWidget(title)

        subtitle = QLabel("Motorsport Intelligence")
        subtitle.setObjectName("WorkspaceTopBrandSubtitle")
        brand_copy.addWidget(subtitle)

        nav_cluster = QFrame()
        nav_cluster.setObjectName("WorkspaceTopNavCluster")
        nav_layout = QHBoxLayout(nav_cluster)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(self._tokens.spacing.xs)
        root.addWidget(nav_cluster, 1, Qt.AlignmentFlag.AlignCenter)

        self._prev = QToolButton()
        self._prev.setObjectName("WorkspaceTopArrow")
        _apply_icon(self._prev, "arrow-left", 16)
        self._prev.clicked.connect(lambda: self.page_step_requested.emit(-1))
        nav_layout.addWidget(self._prev)

        self._next = QToolButton()
        self._next.setObjectName("WorkspaceTopArrow")
        _apply_icon(self._next, "arrow-right", 16)
        self._next.clicked.connect(lambda: self.page_step_requested.emit(1))
        nav_layout.addWidget(self._next)

        self._nav_buttons: dict[str, QToolButton] = {}
        for page_id, icon_name, tooltip in (
            ("dashboard", "dashboard", "Dashboard"),
            ("live", "live", "Live"),
            ("logs", "logs", "Logs"),
            ("history", "history", "History"),
            ("overlay", "overlay", "Overlay"),
        ):
            button = QToolButton()
            button.setObjectName(f"WorkspaceTopNavButton_{page_id}")
            button.setCheckable(True)
            button.setToolTip(tooltip)
            _apply_icon(button, icon_name, 18)
            button.clicked.connect(lambda _checked=False, page=page_id: self.page_requested.emit(page))
            self._nav_buttons[page_id] = button
            nav_layout.addWidget(button)

        self._context = QLabel(str(context_label or "").upper())
        self._context.setObjectName("WorkspaceTopContext")
        self._context.setVisible(bool(context_label))
        nav_layout.addWidget(self._context)
        nav_layout.addStretch(1)

        util_cluster = QFrame()
        util_cluster.setObjectName("WorkspaceTopUtilityCluster")
        util_layout = QHBoxLayout(util_cluster)
        util_layout.setContentsMargins(0, 0, 0, 0)
        util_layout.setSpacing(self._tokens.spacing.xs)
        root.addWidget(util_cluster, 0, Qt.AlignmentFlag.AlignRight)

        status_box = QFrame()
        status_box.setObjectName("WorkspaceTopStatus")
        status_layout = QVBoxLayout(status_box)
        status_layout.setContentsMargins(10, 6, 10, 6)
        status_layout.setSpacing(0)
        self._status = QLabel("IDLE")
        self._status.setObjectName("WorkspaceTopStatusTitle")
        self._detail = QLabel("Waiting for simulator")
        self._detail.setObjectName("WorkspaceTopStatusDetail")
        status_layout.addWidget(self._status)
        status_layout.addWidget(self._detail)
        util_layout.addWidget(status_box)

        self._monitor = QPushButton("RESUME")
        self._monitor.setObjectName("WorkspaceTopMonitorAction")
        _apply_icon(self._monitor, "play", 14)
        self._monitor.clicked.connect(self._handle_monitor)
        util_layout.addWidget(self._monitor)

        self._output = QPushButton("OUT")
        self._output.setObjectName("WorkspaceTopTextAction")
        self._output.clicked.connect(self.open_output_requested.emit)
        util_layout.addWidget(self._output)

        self._logs = QPushButton("LOGS")
        self._logs.setObjectName("WorkspaceTopTextAction")
        self._logs.clicked.connect(self.open_logs_requested.emit)
        util_layout.addWidget(self._logs)

        self._config = QPushButton("CFG")
        self._config.setObjectName("WorkspaceTopTextAction")
        self._config.clicked.connect(self.open_config_requested.emit)
        util_layout.addWidget(self._config)

        self._settings = QToolButton()
        self._settings.setObjectName("WorkspaceTopIconAction_settings")
        self._settings.setToolTip("Settings")
        _apply_icon(self._settings, "settings", 16)
        self._settings.clicked.connect(self.open_settings_requested.emit)
        util_layout.addWidget(self._settings)

        self._about = QToolButton()
        self._about.setObjectName("WorkspaceTopIconAction_about")
        self._about.setToolTip("About")
        _apply_icon(self._about, "help", 16)
        self._about.clicked.connect(self.open_about_requested.emit)
        util_layout.addWidget(self._about)

        self.set_active_page(self._active_page)
        self._apply_style()

    def set_active_page(self, page_id: str) -> None:
        self._active_page = str(page_id or "").lower()
        for key, button in self._nav_buttons.items():
            checked = key == self._active_page
            button.setChecked(checked)
            button.setEnabled(not checked)

    def set_context_label(self, label: str | None) -> None:
        text = str(label or "").strip().upper()
        self._context.setText(text)
        self._context.setVisible(bool(text))

    def set_status(self, *, status: str, detail: str, monitoring_active: bool) -> None:
        self._status.setText(str(status or "IDLE").upper())
        self._detail.setText(str(detail or "Ready"))
        self._monitoring_active = bool(monitoring_active)
        self._monitor.setText("PAUSE" if self._monitoring_active else "RESUME")
        _apply_icon(self._monitor, "pause" if self._monitoring_active else "play", 14)
        self._apply_style()

    def _handle_monitor(self) -> None:
        if self._monitoring_active:
            self.pause_requested.emit()
            return
        self.resume_requested.emit()

    def _apply_style(self) -> None:
        t = self._tokens
        monitor_color = t.colors.safety_red if self._monitoring_active else t.colors.acid_green
        self.setStyleSheet(
            f"""
            QWidget#WorkspaceTopStrip {{
                background: {rgba(t.colors.page_bg_alt, 0.92)};
                border: 1px solid {rgba(t.colors.chalk, 0.07)};
                border-radius: {t.radii.xl}px;
            }}
            QFrame#WorkspaceTopBrand, QFrame#WorkspaceTopNavCluster, QFrame#WorkspaceTopUtilityCluster {{
                background: transparent;
                border: none;
            }}
            QLabel#WorkspaceTopBrandTitle {{
                color: {t.colors.chalk};
                font-family: '{t.typography.display_family}', 'Segoe UI', sans-serif;
                font-size: {t.typography.title_px}px;
                font-weight: 700;
            }}
            QLabel#WorkspaceTopBrandSubtitle {{
                color: {rgba(t.colors.steel, 0.72)};
                font-family: '{t.typography.mono_family}', 'Consolas', monospace;
                font-size: {t.typography.micro_px}px;
                font-weight: 700;
                letter-spacing: 0.8px;
            }}
            QLabel#WorkspaceTopContext {{
                padding: 4px 8px;
                border-radius: {t.radii.sm}px;
                background: {rgba(t.colors.chalk, 0.05)};
                border: 1px solid {rgba(t.colors.chalk, 0.08)};
                color: {rgba(t.colors.chalk, 0.82)};
                font-family: '{t.typography.mono_family}', 'Consolas', monospace;
                font-size: {t.typography.micro_px}px;
                font-weight: 700;
                letter-spacing: 0.8px;
            }}
            QFrame#WorkspaceTopStatus {{
                background: {rgba(t.colors.chalk, 0.035)};
                border: 1px solid {rgba(t.colors.chalk, 0.07)};
                border-radius: {t.radii.md}px;
            }}
            QLabel#WorkspaceTopStatusTitle {{
                color: {t.colors.chalk};
                font-family: '{t.typography.mono_family}', 'Consolas', monospace;
                font-size: {t.typography.micro_px}px;
                font-weight: 700;
                letter-spacing: 1px;
            }}
            QLabel#WorkspaceTopStatusDetail {{
                color: {rgba(t.colors.steel, 0.74)};
                font-family: '{t.typography.body_family}', 'Segoe UI', sans-serif;
                font-size: {t.typography.micro_px}px;
            }}
            QToolButton#WorkspaceTopArrow,
            QToolButton#WorkspaceTopNavButton_dashboard,
            QToolButton#WorkspaceTopNavButton_live,
            QToolButton#WorkspaceTopNavButton_logs,
            QToolButton#WorkspaceTopNavButton_history,
            QToolButton#WorkspaceTopNavButton_overlay,
            QToolButton#WorkspaceTopIconAction_settings,
            QToolButton#WorkspaceTopIconAction_about {{
                min-width: 36px;
                min-height: 36px;
                border-radius: 12px;
                background: transparent;
                border: 1px solid transparent;
            }}
            QToolButton#WorkspaceTopArrow:hover,
            QToolButton#WorkspaceTopNavButton_dashboard:hover,
            QToolButton#WorkspaceTopNavButton_live:hover,
            QToolButton#WorkspaceTopNavButton_logs:hover,
            QToolButton#WorkspaceTopNavButton_history:hover,
            QToolButton#WorkspaceTopNavButton_overlay:hover,
            QToolButton#WorkspaceTopIconAction_settings:hover,
            QToolButton#WorkspaceTopIconAction_about:hover {{
                background: {rgba(t.colors.chalk, 0.045)};
                border-color: {rgba(t.colors.chalk, 0.08)};
            }}
            QToolButton#WorkspaceTopNavButton_dashboard:checked,
            QToolButton#WorkspaceTopNavButton_live:checked,
            QToolButton#WorkspaceTopNavButton_logs:checked,
            QToolButton#WorkspaceTopNavButton_history:checked,
            QToolButton#WorkspaceTopNavButton_overlay:checked {{
                background: {rgba(t.colors.safety_red, 0.18)};
                border-color: {rgba(t.colors.safety_red, 0.36)};
            }}
            QPushButton#WorkspaceTopMonitorAction, QPushButton#WorkspaceTopTextAction {{
                min-height: 36px;
                border-radius: {t.radii.md}px;
                padding: 0 12px;
                font-family: '{t.typography.mono_family}', 'Consolas', monospace;
                font-size: {t.typography.micro_px}px;
                font-weight: 700;
                letter-spacing: 0.8px;
            }}
            QPushButton#WorkspaceTopTextAction {{
                background: transparent;
                border: 1px solid {rgba(t.colors.chalk, 0.07)};
                color: {rgba(t.colors.chalk, 0.82)};
            }}
            QPushButton#WorkspaceTopTextAction:hover {{
                background: {rgba(t.colors.chalk, 0.045)};
            }}
            QPushButton#WorkspaceTopMonitorAction {{
                background: {rgba(monitor_color, 0.16)};
                border: 1px solid {rgba(monitor_color, 0.28)};
                color: {t.colors.chalk};
            }}
            """
        )


class ScenicArtworkWidget(QWidget):
    """Shared scenic renderer for dashboard and review hero surfaces."""

    def __init__(
        self,
        *,
        tokens: WorkspaceDesignTokens | None = None,
        compact: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tokens = tokens or default_workspace_tokens()
        self._compact = compact
        self._renderer: QSvgRenderer | None = None
        path = overlay_workspace_hero_path()
        if path is not None and path.exists():
            self._renderer = QSvgRenderer(str(path))
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def paintEvent(self, event) -> None:  # noqa: ANN001
        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        radius = float(self._tokens.radii.lg if self._compact else self._tokens.radii.xl)
        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        painter.setClipPath(clip)

        base = QLinearGradient(rect.topLeft(), rect.bottomRight())
        base.setColorAt(0.0, QColor("#182435"))
        base.setColorAt(0.35, QColor("#A06D66"))
        base.setColorAt(0.68, QColor("#E8BF7E"))
        base.setColorAt(1.0, QColor("#08121C"))
        painter.fillPath(clip, base)

        if self._renderer is not None and self._renderer.isValid():
            self._renderer.render(painter, rect)

        overlay = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        overlay.setColorAt(0.0, QColor(4, 6, 9, 52))
        overlay.setColorAt(0.55, QColor(8, 10, 14, 34))
        overlay.setColorAt(1.0, QColor(3, 5, 8, 112))
        painter.fillRect(rect, overlay)

        vignette = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * 0.68)
        vignette.setColorAt(0.55, QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 110 if self._compact else 150))
        painter.fillRect(rect, vignette)

        dot_pen = QPen(QColor(255, 255, 255, 10 if self._compact else 14))
        dot_pen.setWidth(1)
        painter.setPen(dot_pen)
        step = 10 if self._compact else 8
        y = int(rect.top()) + step
        while y < int(rect.bottom()) - step:
            x = int(rect.left()) + step
            while x < int(rect.right()) - step:
                painter.drawPoint(x, y)
                x += step
            y += step

        painter.setClipping(False)
        border_pen = QPen(QColor(255, 255, 255, 28))
        border_pen.setWidth(1)
        painter.setPen(border_pen)
        painter.drawRoundedRect(rect, radius, radius)


def workspace_page_styles(page_object_name: str, *, tokens: WorkspaceDesignTokens | None = None) -> str:
    """Return shared page-level styling for immersive workspaces."""

    t = tokens or default_workspace_tokens()
    return f"""
    QWidget#{page_object_name} {{
        background:
            qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 {t.colors.page_bg_alt},
                stop:0.52 {t.colors.page_bg},
                stop:1 #030405
            );
        color: {t.colors.chalk};
    }}
    QLabel {{
        color: {t.colors.chalk};
        font-family: '{t.typography.body_family}', 'Segoe UI', sans-serif;
        font-size: {t.typography.body_px}px;
    }}
    QPushButton {{
        min-height: 38px;
        padding: 0 14px;
        border-radius: {t.radii.md}px;
        background: {rgba(t.colors.chalk, 0.05)};
        border: 1px solid {rgba(t.colors.chalk, 0.08)};
        color: {t.colors.chalk};
        font-family: '{t.typography.mono_family}', 'Consolas', monospace;
        font-size: {t.typography.micro_px}px;
        font-weight: 700;
        letter-spacing: 0.8px;
    }}
    QPushButton:hover {{
        background: {rgba(t.colors.chalk, 0.08)};
    }}
    QPushButton#PrimaryButton, QPushButton#WorkspacePrimaryAction {{
        background: {rgba(t.colors.pit_orange, 0.18)};
        border: 1px solid {rgba(t.colors.pit_orange, 0.32)};
        color: {t.colors.chalk};
    }}
    QPushButton#DangerButton {{
        background: {rgba(t.colors.safety_red, 0.12)};
        border: 1px solid {rgba(t.colors.safety_red, 0.24)};
        color: {t.colors.chalk};
    }}
    QLineEdit, QTextEdit, QComboBox {{
        min-height: 38px;
        background: {rgba("#010203", 0.52)};
        border: 1px solid {rgba(t.colors.chalk, 0.08)};
        border-radius: {t.radii.md}px;
        color: {t.colors.chalk};
        padding: 5px 12px;
        font-family: '{t.typography.body_family}', 'Segoe UI', sans-serif;
        font-size: {t.typography.caption_px}px;
    }}
    QTextEdit {{
        padding: 10px 12px;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 18px;
    }}
    QTableWidget {{
        background: transparent;
        border: 1px solid {rgba(t.colors.chalk, 0.08)};
        border-radius: {t.radii.md}px;
        gridline-color: {rgba(t.colors.chalk, 0.06)};
        selection-background-color: {rgba(t.colors.safety_red, 0.14)};
        selection-color: {t.colors.chalk};
    }}
    QHeaderView::section {{
        background: {rgba(t.colors.chalk, 0.04)};
        color: {rgba(t.colors.steel, 0.86)};
        border: none;
        border-bottom: 1px solid {rgba(t.colors.chalk, 0.08)};
        padding: 8px;
        font-family: '{t.typography.mono_family}', 'Consolas', monospace;
        font-size: {t.typography.micro_px}px;
        font-weight: 700;
    }}
    QToolButton {{
        min-height: 34px;
        padding: 0 12px;
        border-radius: {t.radii.md}px;
        background: {rgba(t.colors.chalk, 0.03)};
        border: 1px solid {rgba(t.colors.chalk, 0.08)};
        color: {t.colors.chalk};
        font-family: '{t.typography.mono_family}', 'Consolas', monospace;
        font-size: {t.typography.micro_px}px;
        font-weight: 700;
        letter-spacing: 0.8px;
    }}
    QToolButton:checked {{
        background: {rgba(t.colors.safety_red, 0.15)};
        border-color: {rgba(t.colors.safety_red, 0.28)};
    }}
    """


def wire_shell_callbacks(top_strip: WorkspaceTopStrip, callbacks: WorkspaceShellCallbacks) -> None:
    """Connect a workspace top strip to shell-level callbacks."""

    def _invoke(name: str):
        def _handler(*args) -> None:  # noqa: ANN002
            callback = getattr(callbacks, name, None)
            if callable(callback):
                callback(*args)

        return _handler

    top_strip.page_requested.connect(_invoke("switch_page"))
    top_strip.page_step_requested.connect(_invoke("step_page"))
    top_strip.open_settings_requested.connect(_invoke("open_settings"))
    top_strip.open_about_requested.connect(_invoke("open_about"))
    top_strip.open_output_requested.connect(_invoke("open_output"))
    top_strip.open_logs_requested.connect(_invoke("open_logs"))
    top_strip.open_config_requested.connect(_invoke("open_config"))
    top_strip.resume_requested.connect(_invoke("resume_monitoring"))
    top_strip.pause_requested.connect(_invoke("pause_monitoring"))


__all__ = [
    "ScenicArtworkWidget",
    "WorkspacePanel",
    "WorkspaceShellCallbacks",
    "WorkspaceSectionTabs",
    "WorkspaceSurface",
    "WorkspaceTopStrip",
    "wire_shell_callbacks",
    "workspace_page_styles",
]
