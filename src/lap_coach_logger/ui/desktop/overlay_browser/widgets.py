"""Reusable Qt widgets for the immersive overlay workspace."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from lap_coach_logger.assets import monogram_path, overlay_workspace_hero_path, overlay_workspace_icon_path
from lap_coach_logger.overlays import (
    OverlayBrowserCategoryItem,
    OverlayBrowserLayoutItem,
    OverlayBrowserOverlayDetail,
    OverlayBrowserOverlayItem,
)
from lap_coach_logger.ui.desktop.overlay_browser.controller import OverlayBrowserPreviewCardModel
from lap_coach_logger.ui.desktop.overlay_browser.design_system import (
    OverlayBrowserDesignTokens,
    default_overlay_browser_tokens,
    rgba,
)
from lap_coach_logger.ui.desktop.overlay_browser.settings_renderer import OverlaySettingsFormRenderer


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


def _category_acronym(category: str) -> str:
    parts = [part for part in str(category or "").replace("-", " ").upper().split() if part]
    if not parts:
        return "OV"
    if len(parts) == 1:
        return parts[0][:2]
    return "".join(part[0] for part in parts[:2])


def _compatibility_text(simulators: tuple[str, ...]) -> str:
    if not simulators:
        return "Universal"
    if len(simulators) <= 3:
        return ", ".join(simulators)
    return ", ".join(simulators[:2]) + f" +{len(simulators) - 2}"


def _placement_hint(detail: OverlayBrowserOverlayDetail | None) -> tuple[str, str, str]:
    if detail is None:
        return ("Auto", "Adaptive", "Current layout")
    key = f"{detail.overlay_id} {detail.category}".lower()
    if "map" in key:
        return ("Bottom left", "Compact", "Navigation")
    if "delta" in key or "time" in key or "flag" in key:
        return ("Top center", "Wide", "Timing")
    if "spot" in key or "mirror" in key:
        return ("Side rail", "Medium", "Alert")
    if "fuel" in key or "heart" in key:
        return ("Bottom right", "Compact", "Telemetry")
    return ("Bottom right", "Adaptive", "Overlay")


class GlassPanel(QFrame):
    """Compact surface used across the overlay workspace."""

    def __init__(
        self,
        *,
        tokens: OverlayBrowserDesignTokens | None = None,
        variant: str = "surface",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tokens = tokens or default_overlay_browser_tokens()
        self._variant = variant
        self.setObjectName(f"OverlaySurface_{variant}")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._apply_style()

    def _apply_style(self) -> None:
        t = self._tokens
        bg = t.colors.controls_bg
        radius = t.radii.md
        border_alpha = t.surface.border_soft_alpha
        if self._variant == "sidebar":
            bg = t.colors.rail_bg
            border_alpha = t.surface.border_mid_alpha
        elif self._variant == "preview":
            bg = t.colors.hero_bg
            radius = t.radii.lg
            border_alpha = t.surface.border_mid_alpha
        elif self._variant == "dock":
            bg = t.colors.dock_bg
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


class SearchFilterBar(QWidget):
    """Compact library filters embedded in the left rail."""

    search_changed = Signal(str)
    entitlement_changed = Signal(str)
    favorites_only_changed = Signal(bool)
    include_hidden_changed = Signal(bool)

    def __init__(self, *, tokens: OverlayBrowserDesignTokens | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tokens = tokens or default_overlay_browser_tokens()
        self.setObjectName("OverlaySidebarFilters")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(self._tokens.spacing.xs)

        self.search = QLineEdit()
        self.search.setObjectName("OverlaySidebarSearch")
        self.search.setPlaceholderText("Search overlays")
        self.search.setMinimumHeight(self._tokens.layout.overlay_control_height_px + 2)
        self.search.textChanged.connect(self.search_changed.emit)
        root.addWidget(self.search)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(self._tokens.spacing.xs)
        root.addLayout(row)

        self.entitlement = QComboBox()
        self.entitlement.setObjectName("OverlaySidebarSelect")
        self.entitlement.addItem("All access", "all")
        self.entitlement.addItem("Free", "free")
        self.entitlement.addItem("Premium", "premium")
        self.entitlement.addItem("Entitled", "entitled_only")
        self.entitlement.setMinimumHeight(self._tokens.layout.overlay_control_height_px)
        self.entitlement.currentIndexChanged.connect(lambda _i: self.entitlement_changed.emit(str(self.entitlement.currentData())))
        row.addWidget(self.entitlement, 1)

        self.favorites = QToolButton()
        self.favorites.setObjectName("OverlaySidebarMiniToggle")
        self.favorites.setText("Fav")
        self.favorites.setCheckable(True)
        self.favorites.toggled.connect(self.favorites_only_changed.emit)
        row.addWidget(self.favorites)

        self.internal = QToolButton()
        self.internal.setObjectName("OverlaySidebarMiniToggle")
        self.internal.setText("Dev")
        self.internal.setCheckable(True)
        self.internal.toggled.connect(self.include_hidden_changed.emit)
        row.addWidget(self.internal)

        self.setStyleSheet(
            f"""
            QWidget#OverlaySidebarFilters {{ background: transparent; }}
            QLineEdit#OverlaySidebarSearch, QComboBox#OverlaySidebarSelect {{
                background: {rgba('#04070B', 0.88)};
                border: 1px solid {rgba(self._tokens.colors.chalk, 0.08)};
                border-radius: {self._tokens.radii.sm}px;
                color: {self._tokens.colors.chalk};
                padding: 0 8px;
                font-family: '{self._tokens.typography.body_family}', 'Segoe UI', sans-serif;
                font-size: {self._tokens.typography.caption_px}px;
            }}
            QComboBox#OverlaySidebarSelect::drop-down {{ border: none; width: 18px; }}
            QToolButton#OverlaySidebarMiniToggle {{
                min-width: 44px;
                min-height: {self._tokens.layout.overlay_control_height_px}px;
                background: {rgba(self._tokens.colors.chalk, 0.03)};
                border: 1px solid {rgba(self._tokens.colors.chalk, 0.08)};
                border-radius: {self._tokens.radii.sm}px;
                color: {rgba(self._tokens.colors.steel, 0.88)};
                font-family: '{self._tokens.typography.body_family}', 'Segoe UI', sans-serif;
                font-size: {self._tokens.typography.micro_px}px;
                font-weight: 600;
            }}
            QToolButton#OverlaySidebarMiniToggle:checked {{
                background: {rgba(self._tokens.colors.safety_red, 0.14)};
                border-color: {rgba(self._tokens.colors.safety_red, 0.24)};
                color: {self._tokens.colors.chalk};
            }}
            """
        )

    def apply_state(self, *, query: str, entitlement_filter: str, favorites_only: bool, include_hidden: bool) -> None:
        self.search.blockSignals(True)
        self.search.setText(query)
        self.search.blockSignals(False)
        self.entitlement.blockSignals(True)
        index = self.entitlement.findData(entitlement_filter)
        self.entitlement.setCurrentIndex(index if index >= 0 else 0)
        self.entitlement.blockSignals(False)
        self.favorites.blockSignals(True)
        self.favorites.setChecked(favorites_only)
        self.favorites.blockSignals(False)
        self.internal.blockSignals(True)
        self.internal.setChecked(include_hidden)
        self.internal.blockSignals(False)


class _OverlayCatalogItemWidget(QWidget):
    favorite_toggled = Signal(str)

    def __init__(self, item: OverlayBrowserOverlayItem, *, tokens: OverlayBrowserDesignTokens, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._item = item
        self._tokens = tokens
        self.setToolTip(f"{item.display_name}\n{item.category.replace('-', ' ').title()}")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        accent = QFrame()
        accent.setObjectName("OverlayCatalogAccent")
        accent.setFixedWidth(3)
        root.addWidget(accent)

        content = QFrame()
        content.setObjectName("OverlayCatalogContent")
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(tokens.spacing.sm, tokens.spacing.sm, tokens.spacing.sm, tokens.spacing.sm)
        content_layout.setSpacing(tokens.spacing.sm)
        root.addWidget(content, 1)

        thumb = QLabel(_category_acronym(item.category))
        thumb.setObjectName("OverlayCatalogThumb")
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setFixedSize(40, 40)
        content_layout.addWidget(thumb, 0, Qt.AlignmentFlag.AlignTop)

        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(tokens.spacing.xxs)
        content_layout.addLayout(copy, 1)

        title = QLabel(item.display_name)
        title.setObjectName("OverlayCatalogTitle")
        title.setWordWrap(True)
        title.setMinimumHeight(30)
        copy.addWidget(title)

        meta = QLabel(f"{item.category.replace('-', ' ').title()}  |  {_compatibility_text(item.supported_simulators)}")
        meta.setObjectName("OverlayCatalogMeta")
        meta.setToolTip(meta.text())
        copy.addWidget(meta)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(tokens.spacing.xs)
        content_layout.addLayout(right)

        status = QLabel(self._status_text(item))
        status.setObjectName("OverlayCatalogStatus")
        right.addWidget(status, 0, Qt.AlignmentFlag.AlignRight)

        favorite = QToolButton()
        favorite.setObjectName("OverlayCatalogFavorite")
        favorite.setText("Fav" if item.favorite else "+Fav")
        favorite.clicked.connect(lambda: self.favorite_toggled.emit(item.overlay_id))
        right.addWidget(favorite, 0, Qt.AlignmentFlag.AlignRight)
        right.addStretch(1)

        accent_fill = tokens.colors.safety_red if item.selected else "transparent"
        content_fill = rgba(tokens.colors.chalk, 0.05 if item.selected else 0.02)
        content_border = rgba(tokens.colors.safety_red, 0.24 if item.selected else 0.08)
        thumb_fill = rgba(tokens.colors.accent_blue, 0.18 if item.active else 0.08)
        thumb_border = rgba(tokens.colors.acid_green, 0.28 if item.active else 0.12)
        tone = tokens.colors.acid_green if item.active else tokens.colors.pit_orange if item.locked else tokens.colors.chalk
        self.setStyleSheet(
            f"""
            QFrame#OverlayCatalogAccent {{
                background: {accent_fill};
                border: none;
                border-top-left-radius: {tokens.radii.sm}px;
                border-bottom-left-radius: {tokens.radii.sm}px;
            }}
            QFrame#OverlayCatalogContent {{
                background: {content_fill};
                border: 1px solid {content_border};
                border-left: none;
                border-top-right-radius: {tokens.radii.sm}px;
                border-bottom-right-radius: {tokens.radii.sm}px;
            }}
            QFrame#OverlayCatalogContent:hover {{ background: {rgba(tokens.colors.chalk, 0.04)}; }}
            QLabel#OverlayCatalogThumb {{
                background: {thumb_fill};
                border: 1px solid {thumb_border};
                border-radius: {tokens.radii.sm}px;
                color: {tokens.colors.chalk};
                font-family: '{tokens.typography.mono_family}', 'Consolas', monospace;
                font-size: {tokens.typography.micro_px}px;
                font-weight: 700;
            }}
            QLabel#OverlayCatalogTitle {{
                color: {tokens.colors.chalk};
                font-family: '{tokens.typography.body_family}', 'Segoe UI', sans-serif;
                font-size: {tokens.typography.body_px}px;
                font-weight: 600;
            }}
            QLabel#OverlayCatalogMeta {{
                color: {rgba(tokens.colors.steel, 0.76)};
                font-family: '{tokens.typography.body_family}', 'Segoe UI', sans-serif;
                font-size: {tokens.typography.micro_px}px;
            }}
            QLabel#OverlayCatalogStatus {{
                padding: 2px 6px;
                border-radius: {tokens.radii.xs}px;
                background: {rgba(tone, 0.10)};
                border: 1px solid {rgba(tone, 0.18)};
                color: {tokens.colors.chalk};
                font-family: '{tokens.typography.body_family}', 'Segoe UI', sans-serif;
                font-size: {tokens.typography.micro_px}px;
                font-weight: 600;
            }}
            QToolButton#OverlayCatalogFavorite {{
                min-height: 20px;
                background: transparent;
                border: none;
                color: {tokens.colors.pit_orange if item.favorite else rgba(tokens.colors.steel, 0.78)};
                font-family: '{tokens.typography.body_family}', 'Segoe UI', sans-serif;
                font-size: {tokens.typography.micro_px}px;
                font-weight: 600;
                padding: 0;
            }}
            """
        )

    @staticmethod
    def _status_text(item: OverlayBrowserOverlayItem) -> str:
        if item.active:
            return "Active"
        if item.installed:
            return "Installed"
        if item.locked:
            return "Locked"
        return "Available"


class OverlaySidebar(GlassPanel):
    """Overlay-specific asset browser pane."""

    search_changed = Signal(str)
    entitlement_changed = Signal(str)
    favorites_only_changed = Signal(bool)
    include_hidden_changed = Signal(bool)
    category_selected = Signal(str)
    overlay_selected = Signal(str)
    favorite_toggled = Signal(str)

    def __init__(self, *, tokens: OverlayBrowserDesignTokens | None = None, parent: QWidget | None = None) -> None:
        self._tokens = tokens or default_overlay_browser_tokens()
        super().__init__(tokens=self._tokens, variant="sidebar", parent=parent)
        self.setObjectName("OverlayWorkspaceSidebar")
        self.setMinimumWidth(self._tokens.layout.overlay_sidebar_width_px)
        self.setMaximumWidth(self._tokens.layout.overlay_sidebar_width_px + 60)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        band = QFrame()
        band.setObjectName("OverlaySidebarBand")
        band_layout = QHBoxLayout(band)
        band_layout.setContentsMargins(self._tokens.spacing.md, self._tokens.spacing.sm, self._tokens.spacing.md, self._tokens.spacing.sm)
        band_layout.setSpacing(self._tokens.spacing.sm)
        root.addWidget(band)

        mono = monogram_path()
        if mono is not None and mono.exists():
            mark = QSvgWidget(str(mono))
            mark.setFixedSize(18, 18)
            mark.setStyleSheet("background: transparent;")
            band_layout.addWidget(mark, 0, Qt.AlignmentFlag.AlignVCenter)

        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(0)
        band_layout.addLayout(copy, 1)
        title = QLabel("Overlays")
        title.setObjectName("OverlaySidebarBandTitle")
        copy.addWidget(title)
        subtitle = QLabel("Library")
        subtitle.setObjectName("OverlaySidebarBandSubtitle")
        copy.addWidget(subtitle)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(self._tokens.spacing.md, self._tokens.spacing.md, self._tokens.spacing.md, self._tokens.spacing.md)
        content_layout.setSpacing(self._tokens.spacing.sm)
        root.addWidget(content, 1)

        self._filters = SearchFilterBar(tokens=self._tokens)
        self._filters.search_changed.connect(self.search_changed.emit)
        self._filters.entitlement_changed.connect(self.entitlement_changed.emit)
        self._filters.favorites_only_changed.connect(self.favorites_only_changed.emit)
        self._filters.include_hidden_changed.connect(self.include_hidden_changed.emit)
        content_layout.addWidget(self._filters)

        self._category_list = QListWidget()
        self._category_list.setObjectName("OverlaySidebarCategoryList")
        self._category_list.setFlow(QListView.Flow.LeftToRight)
        self._category_list.setWrapping(True)
        self._category_list.setResizeMode(QListView.ResizeMode.Adjust)
        self._category_list.setSpacing(self._tokens.spacing.xs)
        self._category_list.setFixedHeight(44)
        self._category_list.itemSelectionChanged.connect(self._emit_category_selected)
        content_layout.addWidget(self._category_list)

        self._overlay_list = QListWidget()
        self._overlay_list.setObjectName("OverlaySidebarOverlayList")
        self._overlay_list.setSpacing(self._tokens.spacing.xs)
        self._overlay_list.itemSelectionChanged.connect(self._emit_overlay_selected)
        content_layout.addWidget(self._overlay_list, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(self._tokens.spacing.sm)
        content_layout.addLayout(footer)
        self._footer_left = QLabel("0 active")
        self._footer_left.setObjectName("OverlaySidebarFooter")
        footer.addWidget(self._footer_left)
        footer.addStretch(1)
        self._footer_right = QLabel("0 premium")
        self._footer_right.setObjectName("OverlaySidebarFooter")
        footer.addWidget(self._footer_right)

        self._apply_style()

    def apply_filters(self, *, query: str, entitlement_filter: str, favorites_only: bool, include_hidden: bool) -> None:
        self._filters.apply_state(query=query, entitlement_filter=entitlement_filter, favorites_only=favorites_only, include_hidden=include_hidden)

    def apply_state(self, categories: tuple[OverlayBrowserCategoryItem, ...], overlays: tuple[OverlayBrowserOverlayItem, ...]) -> None:
        self._category_list.blockSignals(True)
        self._category_list.clear()
        for category in categories:
            item = QListWidgetItem(f"{category.label} ({category.count})")
            item.setData(Qt.ItemDataRole.UserRole, category.category)
            self._category_list.addItem(item)
            if category.selected:
                item.setSelected(True)
                self._category_list.setCurrentItem(item)
        self._category_list.blockSignals(False)

        self._overlay_list.blockSignals(True)
        self._overlay_list.clear()
        active_count = 0
        premium_count = 0
        for overlay in overlays:
            if overlay.active:
                active_count += 1
            if overlay.premium_tier != "free":
                premium_count += 1
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, overlay.overlay_id)
            widget = _OverlayCatalogItemWidget(overlay, tokens=self._tokens)
            widget.favorite_toggled.connect(self.favorite_toggled.emit)
            item.setSizeHint(QSize(0, self._tokens.layout.overlay_list_row_height_px))
            self._overlay_list.addItem(item)
            self._overlay_list.setItemWidget(item, widget)
            if overlay.selected:
                item.setSelected(True)
                self._overlay_list.setCurrentItem(item)
        self._overlay_list.blockSignals(False)
        self._footer_left.setText(f"{active_count} active")
        self._footer_right.setText(f"{premium_count} premium")

    def _emit_category_selected(self) -> None:
        current = self._category_list.currentItem()
        if current is not None:
            self.category_selected.emit(str(current.data(Qt.ItemDataRole.UserRole) or ""))

    def _emit_overlay_selected(self) -> None:
        current = self._overlay_list.currentItem()
        if current is not None:
            self.overlay_selected.emit(str(current.data(Qt.ItemDataRole.UserRole) or ""))

    def _apply_style(self) -> None:
        t = self._tokens
        self.setStyleSheet(
            self.styleSheet()
            + f"""
            QFrame#OverlaySidebarBand {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9E1C1C, stop:1 #521114);
                border: none;
                border-top-left-radius: {t.radii.md}px;
                border-top-right-radius: {t.radii.md}px;
                border-bottom: 1px solid {rgba(t.colors.chalk, 0.08)};
            }}
            QLabel#OverlaySidebarBandTitle {{ color: {t.colors.chalk}; font-size: {t.typography.title_px}px; font-weight: 700; }}
            QLabel#OverlaySidebarBandSubtitle, QLabel#OverlaySidebarFooter {{ color: {rgba(t.colors.steel, 0.76)}; font-size: {t.typography.micro_px}px; }}
            QListWidget#OverlaySidebarCategoryList, QListWidget#OverlaySidebarOverlayList {{ background: transparent; border: none; outline: none; }}
            QListWidget#OverlaySidebarCategoryList::item {{
                margin: 0 4px 0 0;
                padding: 5px 8px;
                border-radius: {t.radii.sm}px;
                background: {rgba(t.colors.chalk, 0.03)};
                color: {rgba(t.colors.steel, 0.84)};
                border: 1px solid {rgba(t.colors.chalk, 0.06)};
                font-size: {t.typography.micro_px}px;
                font-weight: 600;
            }}
            QListWidget#OverlaySidebarCategoryList::item:selected {{
                background: {rgba(t.colors.accent_blue, 0.14)};
                border-color: {rgba(t.colors.accent_blue, 0.22)};
                color: {t.colors.chalk};
            }}
            """
        )


class OverlayWorkspaceTopStrip(QWidget):
    """Compact application toolbar for the overlay workspace."""

    page_requested = Signal(str)
    page_step_requested = Signal(int)
    resume_requested = Signal()
    pause_requested = Signal()
    open_settings_requested = Signal()
    open_about_requested = Signal()
    open_output_requested = Signal()
    open_logs_requested = Signal()
    open_config_requested = Signal()

    def __init__(self, *, tokens: OverlayBrowserDesignTokens | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tokens = tokens or default_overlay_browser_tokens()
        self._monitoring_active = False
        self.setObjectName("OverlayWorkspaceTopStrip")
        self.setFixedHeight(self._tokens.layout.overlay_top_strip_height_px)

        root = QHBoxLayout(self)
        root.setContentsMargins(self._tokens.spacing.md, 0, self._tokens.spacing.md, 0)
        root.setSpacing(self._tokens.spacing.md)

        brand = QFrame()
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(self._tokens.spacing.sm)
        root.addWidget(brand)

        mono = monogram_path()
        if mono is not None and mono.exists():
            mark = QSvgWidget(str(mono))
            mark.setFixedSize(18, 18)
            mark.setStyleSheet("background: transparent;")
            brand_layout.addWidget(mark, 0, Qt.AlignmentFlag.AlignVCenter)
        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(0)
        brand_layout.addLayout(copy)
        title = QLabel("LAP COACH")
        title.setObjectName("OverlayTopBrandTitle")
        copy.addWidget(title)
        subtitle = QLabel("Overlays")
        subtitle.setObjectName("OverlayTopBrandSubtitle")
        copy.addWidget(subtitle)

        self._status_box = QFrame()
        self._status_box.setObjectName("OverlayTopStatus")
        status_layout = QHBoxLayout(self._status_box)
        status_layout.setContentsMargins(8, 0, 8, 0)
        status_layout.setSpacing(self._tokens.spacing.sm)
        root.addWidget(self._status_box)
        self._status = QLabel("Idle")
        self._status.setObjectName("OverlayTopStatusTitle")
        status_layout.addWidget(self._status)
        divider = QFrame()
        divider.setObjectName("OverlayTopStatusDivider")
        divider.setFixedWidth(1)
        status_layout.addWidget(divider)
        self._detail = QLabel("Waiting for simulator")
        self._detail.setObjectName("OverlayTopStatusDetail")
        status_layout.addWidget(self._detail)

        nav_cluster = QFrame()
        nav_layout = QHBoxLayout(nav_cluster)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(self._tokens.spacing.xs)
        root.addWidget(nav_cluster)
        self._prev = QToolButton()
        self._prev.setObjectName("OverlayTopArrow")
        _apply_icon(self._prev, "arrow-left", 14)
        self._prev.clicked.connect(lambda: self.page_step_requested.emit(-1))
        nav_layout.addWidget(self._prev)
        self._next = QToolButton()
        self._next.setObjectName("OverlayTopArrow")
        _apply_icon(self._next, "arrow-right", 14)
        self._next.clicked.connect(lambda: self.page_step_requested.emit(1))
        nav_layout.addWidget(self._next)

        self._nav_buttons: dict[str, QToolButton] = {}
        for page_id, icon_name in (("dashboard", "dashboard"), ("live", "live"), ("logs", "logs"), ("history", "history"), ("overlay", "overlay")):
            button = QToolButton()
            button.setObjectName(f"OverlayTopNavButton_{page_id}")
            button.setCheckable(True)
            _apply_icon(button, icon_name, 16)
            button.clicked.connect(lambda _checked=False, page=page_id: self.page_requested.emit(page))
            self._nav_buttons[page_id] = button
            nav_layout.addWidget(button)
        self._nav_buttons["overlay"].setChecked(True)
        self._nav_buttons["overlay"].setEnabled(False)

        root.addStretch(1)
        util = QFrame()
        util_layout = QHBoxLayout(util)
        util_layout.setContentsMargins(0, 0, 0, 0)
        util_layout.setSpacing(self._tokens.spacing.xs)
        root.addWidget(util)

        self._monitor = QPushButton("Resume")
        self._monitor.setObjectName("OverlayTopMonitorAction")
        _apply_icon(self._monitor, "play", 12)
        self._monitor.clicked.connect(self._handle_monitor)
        util_layout.addWidget(self._monitor)
        self._output = QPushButton("Output")
        self._output.setObjectName("OverlayTopTextAction")
        self._output.clicked.connect(self.open_output_requested.emit)
        util_layout.addWidget(self._output)
        self._logs = QPushButton("Logs")
        self._logs.setObjectName("OverlayTopTextAction")
        self._logs.clicked.connect(self.open_logs_requested.emit)
        util_layout.addWidget(self._logs)
        self._config = QPushButton("Config")
        self._config.setObjectName("OverlayTopTextAction")
        self._config.clicked.connect(self.open_config_requested.emit)
        util_layout.addWidget(self._config)
        self._settings = QToolButton()
        self._settings.setObjectName("OverlayTopIconAction_settings")
        _apply_icon(self._settings, "settings", 14)
        self._settings.clicked.connect(self.open_settings_requested.emit)
        util_layout.addWidget(self._settings)
        self._about = QToolButton()
        self._about.setObjectName("OverlayTopIconAction_about")
        _apply_icon(self._about, "help", 14)
        self._about.clicked.connect(self.open_about_requested.emit)
        util_layout.addWidget(self._about)
        self._apply_style()

    def set_status(self, *, status: str, detail: str, monitoring_active: bool) -> None:
        self._status.setText(str(status or "Idle"))
        self._detail.setText(str(detail or "Ready"))
        self._monitoring_active = bool(monitoring_active)
        self._monitor.setText("Pause" if self._monitoring_active else "Resume")
        _apply_icon(self._monitor, "pause" if self._monitoring_active else "play", 12)
        self._apply_style()

    def _handle_monitor(self) -> None:
        if self._monitoring_active:
            self.pause_requested.emit()
        else:
            self.resume_requested.emit()

    def _apply_style(self) -> None:
        t = self._tokens
        monitor_color = t.colors.safety_red if self._monitoring_active else t.colors.acid_green
        self.setStyleSheet(
            f"""
            QWidget#OverlayWorkspaceTopStrip {{ background: {rgba(t.colors.page_bg_alt, 0.96)}; border: 1px solid {rgba(t.colors.chalk, 0.06)}; border-radius: {t.radii.md}px; }}
            QLabel#OverlayTopBrandTitle {{ color: {t.colors.chalk}; font-size: {t.typography.title_px}px; font-weight: 700; }}
            QLabel#OverlayTopBrandSubtitle {{ color: {rgba(t.colors.steel, 0.74)}; font-size: {t.typography.micro_px}px; }}
            QFrame#OverlayTopStatus {{ background: {rgba(t.colors.chalk, 0.03)}; border: 1px solid {rgba(t.colors.chalk, 0.06)}; border-radius: {t.radii.sm}px; }}
            QFrame#OverlayTopStatusDivider {{ background: {rgba(t.colors.chalk, 0.10)}; border: none; }}
            QLabel#OverlayTopStatusTitle {{ color: {t.colors.chalk}; font-size: {t.typography.caption_px}px; font-weight: 600; }}
            QLabel#OverlayTopStatusDetail {{ color: {rgba(t.colors.steel, 0.78)}; font-size: {t.typography.micro_px}px; }}
            QToolButton#OverlayTopArrow, QToolButton#OverlayTopNavButton_dashboard, QToolButton#OverlayTopNavButton_live, QToolButton#OverlayTopNavButton_logs, QToolButton#OverlayTopNavButton_history, QToolButton#OverlayTopNavButton_overlay, QToolButton#OverlayTopIconAction_settings, QToolButton#OverlayTopIconAction_about {{ min-width: 28px; min-height: 28px; border-radius: {t.radii.sm}px; background: transparent; border: 1px solid transparent; }}
            QToolButton#OverlayTopArrow:hover, QToolButton#OverlayTopNavButton_dashboard:hover, QToolButton#OverlayTopNavButton_live:hover, QToolButton#OverlayTopNavButton_logs:hover, QToolButton#OverlayTopNavButton_history:hover, QToolButton#OverlayTopNavButton_overlay:hover, QToolButton#OverlayTopIconAction_settings:hover, QToolButton#OverlayTopIconAction_about:hover {{ background: {rgba(t.colors.chalk, 0.04)}; border-color: {rgba(t.colors.chalk, 0.08)}; }}
            QToolButton#OverlayTopNavButton_dashboard:checked, QToolButton#OverlayTopNavButton_live:checked, QToolButton#OverlayTopNavButton_logs:checked, QToolButton#OverlayTopNavButton_history:checked, QToolButton#OverlayTopNavButton_overlay:checked {{ background: {rgba(t.colors.safety_red, 0.18)}; border-color: {rgba(t.colors.safety_red, 0.28)}; }}
            QPushButton#OverlayTopMonitorAction, QPushButton#OverlayTopTextAction {{ min-height: 28px; border-radius: {t.radii.sm}px; padding: 0 10px; font-size: {t.typography.micro_px}px; font-weight: 600; }}
            QPushButton#OverlayTopTextAction {{ background: {rgba(t.colors.chalk, 0.03)}; border: 1px solid {rgba(t.colors.chalk, 0.06)}; color: {rgba(t.colors.chalk, 0.84)}; }}
            QPushButton#OverlayTopMonitorAction {{ background: {rgba(monitor_color, 0.16)}; border: 1px solid {rgba(monitor_color, 0.28)}; color: {t.colors.chalk}; }}
            """
        )


class _PlacementCanvasWidget(QWidget):
    """Canvas showing the selected overlay inside a layout context."""

    def __init__(self, *, tokens: OverlayBrowserDesignTokens | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tokens = tokens or default_overlay_browser_tokens()
        self._renderer: QSvgRenderer | None = None
        self._model = OverlayBrowserPreviewCardModel("", "No Overlay Selected", "", "Idle", "", "", False, False)
        self._detail: OverlayBrowserOverlayDetail | None = None
        path = overlay_workspace_hero_path()
        if path is not None and path.exists():
            self._renderer = QSvgRenderer(str(path))
        self.setObjectName("OverlayPlacementCanvas")
        self.setMinimumHeight(self._tokens.layout.overlay_canvas_min_height_px)

    def set_state(self, model: OverlayBrowserPreviewCardModel, detail: OverlayBrowserOverlayDetail | None) -> None:
        self._model = model
        self._detail = detail
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.fillRect(rect, QColor(self._tokens.colors.canvas_bg))
        output_rect = self._output_rect(rect)
        safe_rect = output_rect.adjusted(26.0, 22.0, -26.0, -22.0)

        painter.setPen(QPen(QColor(self._tokens.colors.line_strong), 1))
        painter.setBrush(QColor(self._tokens.colors.canvas_frame))
        painter.drawRoundedRect(output_rect, self._tokens.radii.md, self._tokens.radii.md)
        if self._renderer is not None and self._renderer.isValid():
            clip = QPainterPath()
            clip.addRoundedRect(output_rect.adjusted(1.0, 1.0, -1.0, -1.0), self._tokens.radii.sm, self._tokens.radii.sm)
            painter.save()
            painter.setClipPath(clip)
            self._renderer.render(painter, output_rect.adjusted(1.0, 1.0, -1.0, -1.0))
            painter.restore()
        overlay_fill = QLinearGradient(output_rect.topLeft(), output_rect.bottomLeft())
        overlay_fill.setColorAt(0.0, QColor(0, 0, 0, 36))
        overlay_fill.setColorAt(1.0, QColor(0, 0, 0, 120))
        painter.fillRect(output_rect, overlay_fill)

        grid_pen = QPen(QColor(255, 255, 255, 16))
        painter.setPen(grid_pen)
        step = 24
        x = int(output_rect.left()) + step
        while x < int(output_rect.right()):
            painter.drawLine(x, int(output_rect.top()), x, int(output_rect.bottom()))
            x += step
        y = int(output_rect.top()) + step
        while y < int(output_rect.bottom()):
            painter.drawLine(int(output_rect.left()), y, int(output_rect.right()), y)
            y += step

        safe_pen = QPen(QColor(255, 255, 255, 54), 1, Qt.PenStyle.DashLine)
        painter.setPen(safe_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(safe_rect, self._tokens.radii.sm, self._tokens.radii.sm)

        for ghost_rect in self._ghost_rects(output_rect):
            painter.setPen(QPen(QColor(255, 255, 255, 42), 1))
            painter.setBrush(QColor(7, 10, 14, 110))
            painter.drawRoundedRect(ghost_rect, self._tokens.radii.sm, self._tokens.radii.sm)

        selected_rect = self._selected_rect(output_rect)
        painter.setPen(QPen(QColor(self._tokens.colors.safety_red), 2))
        painter.setBrush(QColor(16, 18, 24, 84))
        painter.drawRoundedRect(selected_rect, self._tokens.radii.sm, self._tokens.radii.sm)
        if self._detail is not None and "preview" in self._detail.preview.mode:
            painter.setPen(QPen(QColor(self._tokens.colors.pit_orange), 1))
            painter.drawRoundedRect(selected_rect.adjusted(6.0, 6.0, -6.0, -6.0), self._tokens.radii.sm, self._tokens.radii.sm)
        handle_color = QColor(self._tokens.colors.acid_green if self._model.active else self._tokens.colors.pit_orange)
        painter.fillRect(QRectF(selected_rect.left() - 1.0, selected_rect.top() - 1.0, 10.0, 10.0), handle_color)

        painter.setPen(QColor(self._tokens.colors.chalk))
        painter.setBrush(QColor(8, 11, 16, 196))
        label_rect = QRectF(selected_rect.left(), selected_rect.top() - 26.0, max(130.0, selected_rect.width() * 0.4), 22.0)
        painter.drawRoundedRect(label_rect, self._tokens.radii.xs, self._tokens.radii.xs)
        painter.drawText(label_rect.adjusted(8.0, 0.0, -8.0, 0.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._model.title)
        painter.setPen(QPen(QColor(255, 255, 255, 28), 1))
        painter.drawRoundedRect(rect, self._tokens.radii.md, self._tokens.radii.md)

    def _output_rect(self, rect: QRectF) -> QRectF:
        inset = float(self._tokens.layout.overlay_canvas_frame_inset_px)
        available = rect.adjusted(inset, inset, -inset, -inset)
        aspect = 16.0 / 9.0
        width = available.width()
        height = width / aspect
        if height > available.height():
            height = available.height()
            width = height * aspect
        left = available.left() + (available.width() - width) / 2.0
        top = available.top() + (available.height() - height) / 2.0
        return QRectF(left, top, width, height)

    @staticmethod
    def _ghost_rects(output_rect: QRectF) -> list[QRectF]:
        return [
            QRectF(output_rect.left() + 18.0, output_rect.top() + 18.0, 132.0, 42.0),
            QRectF(output_rect.right() - 160.0, output_rect.bottom() - 82.0, 142.0, 46.0),
        ]

    def _selected_rect(self, output_rect: QRectF) -> QRectF:
        detail = self._detail
        key = f"{detail.overlay_id if detail else ''} {detail.category if detail else ''}".lower()
        if "map" in key:
            return QRectF(output_rect.left() + 22.0, output_rect.bottom() - 112.0, 196.0, 86.0)
        if "delta" in key or "time" in key or "flag" in key:
            return QRectF(output_rect.center().x() - 158.0, output_rect.top() + 24.0, 316.0, 54.0)
        if "spot" in key or "mirror" in key:
            return QRectF(output_rect.right() - 188.0, output_rect.center().y() - 66.0, 156.0, 118.0)
        if "fuel" in key or "heart" in key:
            return QRectF(output_rect.right() - 176.0, output_rect.bottom() - 96.0, 152.0, 62.0)
        return QRectF(output_rect.right() - 224.0, output_rect.bottom() - 122.0, 192.0, 88.0)


class PreviewCanvas(GlassPanel):
    """Center placement canvas and contextual workspace controls."""

    overlay_action_requested = Signal(str)

    def __init__(self, *, tokens: OverlayBrowserDesignTokens | None = None, parent: QWidget | None = None) -> None:
        self._tokens = tokens or default_overlay_browser_tokens()
        super().__init__(tokens=self._tokens, variant="preview", parent=parent)
        self.setObjectName("OverlayWorkspacePreview")
        self._current_detail: OverlayBrowserOverlayDetail | None = None
        self._primary_action_handler = None
        self._current_model = OverlayBrowserPreviewCardModel("", "No Overlay Selected", "Select an overlay from the library", "Idle", "", "", False, False)

        root = QVBoxLayout(self)
        root.setContentsMargins(self._tokens.spacing.md, self._tokens.spacing.md, self._tokens.spacing.md, self._tokens.spacing.md)
        root.setSpacing(self._tokens.spacing.sm)

        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(self._tokens.spacing.md)
        root.addWidget(header)

        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(self._tokens.spacing.xxs)
        header_layout.addLayout(copy, 1)
        self._eyebrow = QLabel("Selected overlay")
        self._eyebrow.setObjectName("OverlayPreviewEyebrow")
        copy.addWidget(self._eyebrow)
        self._title = QLabel("No Overlay Selected")
        self._title.setWordWrap(True)
        self._title.setObjectName("OverlayPreviewTitle")
        copy.addWidget(self._title)

        meta = QHBoxLayout()
        meta.setContentsMargins(0, 0, 0, 0)
        meta.setSpacing(self._tokens.spacing.xs)
        copy.addLayout(meta)
        self._subtitle = QLabel("")
        self._subtitle.setObjectName("OverlayPreviewSubtitle")
        meta.addWidget(self._subtitle)
        self._state = QLabel("Ready")
        self._state.setObjectName("OverlayPreviewState")
        meta.addWidget(self._state)
        meta.addStretch(1)
        self._message = QLabel("")
        self._message.setWordWrap(True)
        self._message.setObjectName("OverlayPreviewMessage")
        copy.addWidget(self._message)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(self._tokens.spacing.xs)
        header_layout.addLayout(actions)
        self._action_primary = QPushButton("")
        self._action_primary.setObjectName("OverlayPreviewPrimaryAction")
        self._action_primary.setVisible(False)
        actions.addWidget(self._action_primary)
        self._secondary_actions = QHBoxLayout()
        self._secondary_actions.setContentsMargins(0, 0, 0, 0)
        self._secondary_actions.setSpacing(self._tokens.spacing.xs)
        actions.addLayout(self._secondary_actions)

        self._canvas = _PlacementCanvasWidget(tokens=self._tokens)
        root.addWidget(self._canvas, 1)

        status_bar = QFrame()
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(self._tokens.spacing.sm, self._tokens.spacing.xs, self._tokens.spacing.sm, self._tokens.spacing.xs)
        status_layout.setSpacing(self._tokens.spacing.md)
        root.addWidget(status_bar)
        self._status_fields: dict[str, QLabel] = {}
        for key in ("Anchor", "Size", "Mode", "Layout", "Layer"):
            block = QVBoxLayout()
            block.setContentsMargins(0, 0, 0, 0)
            block.setSpacing(0)
            label = QLabel(key)
            label.setObjectName("OverlayCanvasStatusLabel")
            value = QLabel("-")
            value.setObjectName("OverlayCanvasStatusValue")
            block.addWidget(label)
            block.addWidget(value)
            status_layout.addLayout(block)
            self._status_fields[key] = value
        status_layout.addStretch(1)
        self._apply_style()
        self.apply_model(self._current_model)

    def apply_model(self, model: OverlayBrowserPreviewCardModel) -> None:
        self._current_model = model
        self._title.setText(model.title or "No Overlay Selected")
        subtitle = model.subtitle or ""
        if model.health_status:
            subtitle = f"{subtitle}  |  {model.health_status.title()}" if subtitle else model.health_status.title()
        self._subtitle.setText(subtitle)
        self._subtitle.setVisible(bool(subtitle))
        self._state.setText("Active" if model.active else model.badge or "Ready")
        self._message.setText(model.message or "")
        self._message.setVisible(bool(model.message))
        self._canvas.set_state(model, self._current_detail)
        self._sync_status_bar()

    def apply_detail(self, detail: OverlayBrowserOverlayDetail | None) -> None:
        self._current_detail = detail
        self._rebuild_actions()
        self._canvas.set_state(self._current_model, detail)
        self._sync_status_bar()

    def _sync_status_bar(self) -> None:
        anchor, size, layer = _placement_hint(self._current_detail)
        mode = self._current_detail.preview.mode.replace("_", " ").title() if self._current_detail else "Preview"
        layout_id = self._current_detail.selected_layout_id if self._current_detail else "-"
        for key, value in {"Anchor": anchor, "Size": size, "Mode": mode or "Preview", "Layout": layout_id or "-", "Layer": layer}.items():
            self._status_fields[key].setText(value)

    def _rebuild_actions(self) -> None:
        while self._secondary_actions.count():
            item = self._secondary_actions.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if self._primary_action_handler is not None:
            self._action_primary.clicked.disconnect(self._primary_action_handler)
            self._primary_action_handler = None
        if self._current_detail is None or not self._current_detail.actions:
            self._action_primary.setVisible(False)
            return
        actions = [action for action in self._current_detail.actions if action.visible]
        if not actions:
            self._action_primary.setVisible(False)
            return
        primary = next((action for action in actions if action.tone == "primary"), actions[0])
        self._action_primary.setText(primary.label)
        self._action_primary.setEnabled(primary.enabled)
        self._primary_action_handler = lambda _checked=False, action_id=primary.action_id: self.overlay_action_requested.emit(action_id)
        self._action_primary.clicked.connect(self._primary_action_handler)
        self._action_primary.setVisible(True)
        for action in actions:
            if action.action_id == primary.action_id:
                continue
            button = QPushButton(action.label)
            button.setObjectName("OverlayPreviewDangerAction" if action.tone == "danger" else "OverlayPreviewSecondaryAction")
            button.setEnabled(action.enabled)
            button.clicked.connect(lambda _checked=False, action_id=action.action_id: self.overlay_action_requested.emit(action_id))
            self._secondary_actions.addWidget(button)

    def _apply_style(self) -> None:
        t = self._tokens
        self.setStyleSheet(
            self.styleSheet()
            + f"""
            QLabel#OverlayPreviewEyebrow {{ color: {rgba(t.colors.steel, 0.68)}; font-size: {t.typography.micro_px}px; font-weight: 600; }}
            QLabel#OverlayPreviewTitle {{ color: {t.colors.chalk}; font-family: '{t.typography.display_family}', 'Segoe UI', sans-serif; font-size: {t.typography.hero_px}px; font-weight: 700; }}
            QLabel#OverlayPreviewSubtitle {{ color: {rgba(t.colors.steel, 0.80)}; font-size: {t.typography.caption_px}px; }}
            QLabel#OverlayPreviewState {{
                padding: 1px 6px;
                border-radius: {t.radii.xs}px;
                background: {rgba(t.colors.safety_red, 0.12)};
                border: 1px solid {rgba(t.colors.safety_red, 0.22)};
                color: {t.colors.chalk};
                font-size: {t.typography.micro_px}px;
                font-weight: 600;
            }}
            QLabel#OverlayPreviewMessage {{ color: {rgba(t.colors.chalk, 0.78)}; font-size: {t.typography.caption_px}px; }}
            QLabel#OverlayCanvasStatusLabel {{ color: {rgba(t.colors.steel, 0.66)}; font-size: {t.typography.micro_px}px; }}
            QLabel#OverlayCanvasStatusValue {{ color: {t.colors.chalk}; font-size: {t.typography.caption_px}px; font-weight: 600; }}
            QWidget#OverlayPlacementCanvas {{ background: {rgba(t.colors.canvas_bg, 0.96)}; border: 1px solid {rgba(t.colors.chalk, 0.06)}; border-radius: {t.radii.md}px; }}
            QPushButton#OverlayPreviewPrimaryAction, QPushButton#OverlayPreviewSecondaryAction, QPushButton#OverlayPreviewDangerAction {{
                min-height: {t.layout.overlay_control_height_px}px;
                border-radius: {t.radii.sm}px;
                padding: 0 10px;
                font-size: {t.typography.micro_px}px;
                font-weight: 600;
            }}
            QPushButton#OverlayPreviewPrimaryAction {{ background: {rgba(t.colors.safety_red, 0.18)}; border: 1px solid {rgba(t.colors.safety_red, 0.30)}; color: {t.colors.chalk}; }}
            QPushButton#OverlayPreviewSecondaryAction {{ background: {rgba(t.colors.chalk, 0.03)}; border: 1px solid {rgba(t.colors.chalk, 0.07)}; color: {t.colors.chalk}; }}
            QPushButton#OverlayPreviewDangerAction {{ background: {rgba(t.colors.safety_red, 0.06)}; border: 1px solid {rgba(t.colors.safety_red, 0.18)}; color: {t.colors.safety_red}; }}
            """
        )


class OverlaySettingsPanel(GlassPanel):
    """Right-hand inspector and settings rail."""

    overlay_action_requested = Signal(str)
    apply_requested = Signal(dict)

    def __init__(self, *, tokens: OverlayBrowserDesignTokens | None = None, parent: QWidget | None = None) -> None:
        self._tokens = tokens or default_overlay_browser_tokens()
        super().__init__(tokens=self._tokens, variant="surface", parent=parent)
        self.setObjectName("OverlayWorkspaceControls")
        self.setMinimumWidth(self._tokens.layout.overlay_settings_width_px)
        self._current_detail: OverlayBrowserOverlayDetail | None = None
        self._primary_action_handler = None

        root = QVBoxLayout(self)
        root.setContentsMargins(self._tokens.spacing.md, self._tokens.spacing.md, self._tokens.spacing.md, self._tokens.spacing.md)
        root.setSpacing(self._tokens.spacing.sm)
        heading = QLabel("Inspector")
        heading.setObjectName("OverlayControlsHeading")
        root.addWidget(heading)

        self._title = QLabel("No Overlay Selected")
        self._title.setObjectName("OverlayControlsTitle")
        root.addWidget(self._title)
        self._subtitle = QLabel("")
        self._subtitle.setWordWrap(True)
        self._subtitle.setObjectName("OverlayControlsSubtitle")
        root.addWidget(self._subtitle)

        self._search = QLineEdit()
        self._search.setObjectName("OverlayControlsSearch")
        self._search.setPlaceholderText("Filter settings")
        root.addWidget(self._search)
        self.form = OverlaySettingsFormRenderer(tokens=self._tokens)
        self._search.textChanged.connect(self.form.set_search_query)
        self.form.dirty_changed.connect(self._sync_dirty_state)
        root.addWidget(self.form, 1)

        self._primary_action = QPushButton("Select overlay")
        self._primary_action.setObjectName("OverlayControlsPrimaryAction")
        self._primary_action.setEnabled(False)
        root.addWidget(self._primary_action)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(self._tokens.spacing.xs)
        root.addLayout(footer)
        self._dirty_hint = QLabel("Settings linked")
        self._dirty_hint.setObjectName("OverlayControlsDirtyHint")
        footer.addWidget(self._dirty_hint)
        footer.addStretch(1)
        self._reset = QPushButton("Reset")
        self._reset.setObjectName("OverlayControlsSecondaryFooter")
        self._reset.clicked.connect(self.form.reset_to_baseline)
        footer.addWidget(self._reset)
        self._apply = QPushButton("Apply")
        self._apply.setObjectName("OverlayControlsPrimaryFooter")
        self._apply.clicked.connect(lambda: self.apply_requested.emit(self.form.collect_changes()))
        footer.addWidget(self._apply)
        self._apply_style()
        self.apply_detail(None)

    def apply_detail(self, detail: OverlayBrowserOverlayDetail | None) -> None:
        self._current_detail = detail
        if self._primary_action_handler is not None:
            self._primary_action.clicked.disconnect(self._primary_action_handler)
            self._primary_action_handler = None
        if detail is None:
            self._title.setText("No Overlay Selected")
            self._subtitle.setText("Choose an overlay from the library")
            self._primary_action.setText("Select overlay")
            self._primary_action.setEnabled(False)
            self.form.set_sections(())
            self._sync_dirty_state(False)
            return
        self._title.setText(detail.display_name)
        self._subtitle.setText(detail.short_description)
        self.form.set_sections(detail.settings_sections)
        actions = [action for action in detail.actions if action.visible]
        primary = next((action for action in actions if action.tone == "primary"), actions[0] if actions else None)
        if primary is None:
            self._primary_action.setText("No action")
            self._primary_action.setEnabled(False)
        else:
            self._primary_action.setText(primary.label)
            self._primary_action.setEnabled(primary.enabled)
            self._primary_action_handler = lambda _checked=False, action=primary.action_id: self.overlay_action_requested.emit(action)
            self._primary_action.clicked.connect(self._primary_action_handler)
        self._sync_dirty_state(False)

    def _sync_dirty_state(self, dirty: bool) -> None:
        self._dirty_hint.setText("Unsaved changes" if dirty else "Settings linked")
        self._apply.setEnabled(bool(dirty))

    def _apply_style(self) -> None:
        t = self._tokens
        self.setStyleSheet(
            self.styleSheet()
            + f"""
            QLabel#OverlayControlsHeading {{ color: {rgba(t.colors.chalk, 0.78)}; font-size: {t.typography.title_px}px; font-weight: 700; }}
            QLabel#OverlayControlsTitle {{ color: {t.colors.chalk}; font-size: {t.typography.title_px}px; font-weight: 700; }}
            QLabel#OverlayControlsSubtitle, QLabel#OverlayControlsDirtyHint {{ color: {rgba(t.colors.steel, 0.74)}; font-size: {t.typography.micro_px}px; }}
            QLineEdit#OverlayControlsSearch {{
                min-height: {t.layout.overlay_control_height_px}px;
                background: {rgba('#04070B', 0.88)};
                border: 1px solid {rgba(t.colors.chalk, 0.08)};
                border-radius: {t.radii.sm}px;
                color: {t.colors.chalk};
                padding: 0 8px;
                font-size: {t.typography.caption_px}px;
            }}
            QPushButton#OverlayControlsPrimaryAction, QPushButton#OverlayControlsSecondaryFooter, QPushButton#OverlayControlsPrimaryFooter {{
                min-height: {t.layout.overlay_control_height_px}px;
                border-radius: {t.radii.sm}px;
                padding: 0 10px;
                font-size: {t.typography.micro_px}px;
                font-weight: 600;
            }}
            QPushButton#OverlayControlsPrimaryAction {{ background: {rgba(t.colors.safety_red, 0.18)}; border: 1px solid {rgba(t.colors.safety_red, 0.30)}; color: {t.colors.chalk}; }}
            QPushButton#OverlayControlsSecondaryFooter {{ background: {rgba(t.colors.chalk, 0.03)}; border: 1px solid {rgba(t.colors.chalk, 0.07)}; color: {t.colors.chalk}; }}
            QPushButton#OverlayControlsPrimaryFooter {{ background: {rgba(t.colors.acid_green, 0.16)}; border: 1px solid {rgba(t.colors.acid_green, 0.26)}; color: #D8FFE7; }}
            """
        )


class BottomActionBar(GlassPanel):
    """Bottom layout manager strip."""

    layout_selected = Signal(str)
    action_requested = Signal(str)

    def __init__(self, *, tokens: OverlayBrowserDesignTokens | None = None, parent: QWidget | None = None) -> None:
        self._tokens = tokens or default_overlay_browser_tokens()
        super().__init__(tokens=self._tokens, variant="dock", parent=parent)
        self.setObjectName("OverlayWorkspaceDock")
        self.setFixedHeight(self._tokens.layout.overlay_bottom_dock_height_px)
        self._layout_ids: list[str] = []

        root = QHBoxLayout(self)
        root.setContentsMargins(self._tokens.spacing.md, self._tokens.spacing.xs, self._tokens.spacing.md, self._tokens.spacing.xs)
        root.setSpacing(self._tokens.spacing.sm)
        title = QLabel("Layout")
        title.setObjectName("OverlayDockTitle")
        root.addWidget(title)
        new_button = QPushButton("+ New")
        new_button.setObjectName("OverlayDockUtility")
        new_button.clicked.connect(lambda _checked=False: self.action_requested.emit("create_layout"))
        root.addWidget(new_button)
        self._tabs = QTabBar()
        self._tabs.setObjectName("OverlayDockTabs")
        self._tabs.setExpanding(False)
        self._tabs.setDrawBase(False)
        self._tabs.setUsesScrollButtons(True)
        self._tabs.currentChanged.connect(self._emit_layout_selected)
        root.addWidget(self._tabs, 1)
        self._live_label = QLabel("Live: none")
        self._live_label.setObjectName("OverlayDockLiveLabel")
        root.addWidget(self._live_label)
        for action_id, label in (("rename_layout", "Rename"), ("clone_layout", "Duplicate"), ("import_layout", "Import"), ("export_layout", "Export")):
            button = QPushButton(label)
            button.setObjectName("OverlayDockUtility")
            button.clicked.connect(lambda _checked=False, action=action_id: self.action_requested.emit(action))
            root.addWidget(button)
        self._activate = QPushButton("Activate")
        self._activate.setObjectName("OverlayDockPrimary")
        self._activate.clicked.connect(lambda _checked=False: self.action_requested.emit("activate_layout"))
        root.addWidget(self._activate)
        self._apply_style()

    def apply_layouts(self, layouts: tuple[OverlayBrowserLayoutItem, ...]) -> None:
        self._layout_ids = []
        self._tabs.blockSignals(True)
        while self._tabs.count():
            self._tabs.removeTab(0)
        selected_index = 0
        active_name = ""
        for index, layout in enumerate(layouts):
            label = layout.display_name + (" *" if layout.favorite else "")
            self._tabs.addTab(label)
            self._tabs.setTabToolTip(index, layout.description or layout.display_name)
            self._layout_ids.append(layout.layout_id)
            if layout.selected:
                selected_index = index
            if layout.active:
                active_name = layout.display_name
        if self._layout_ids:
            self._tabs.setCurrentIndex(selected_index)
        self._tabs.blockSignals(False)
        self._live_label.setText(f"Live: {active_name}" if active_name else "Live: none")
        is_active = bool(layouts and any(layout.active and layout.selected for layout in layouts))
        self._activate.setText("Live" if is_active else "Activate")
        self._activate.setEnabled(bool(layouts) and not is_active)

    def _emit_layout_selected(self, index: int) -> None:
        if 0 <= index < len(self._layout_ids):
            self.layout_selected.emit(self._layout_ids[index])

    def _apply_style(self) -> None:
        t = self._tokens
        self.setStyleSheet(
            self.styleSheet()
            + f"""
            QLabel#OverlayDockTitle, QLabel#OverlayDockLiveLabel {{ color: {rgba(t.colors.steel, 0.78)}; font-size: {t.typography.micro_px}px; }}
            QTabBar#OverlayDockTabs::tab {{
                min-width: {t.layout.overlay_tab_min_width_px}px;
                max-width: {t.layout.overlay_tab_max_width_px}px;
                min-height: {t.layout.overlay_control_height_px}px;
                margin-right: 4px;
                padding: 0 10px;
                border-radius: {t.radii.sm}px;
                background: {rgba(t.colors.chalk, 0.03)};
                border: 1px solid {rgba(t.colors.chalk, 0.07)};
                color: {rgba(t.colors.chalk, 0.82)};
                font-size: {t.typography.micro_px}px;
                font-weight: 600;
            }}
            QTabBar#OverlayDockTabs::tab:selected {{ background: {rgba(t.colors.accent_blue, 0.12)}; border-color: {rgba(t.colors.accent_blue, 0.24)}; color: {t.colors.chalk}; }}
            QPushButton#OverlayDockUtility, QPushButton#OverlayDockPrimary {{
                min-height: {t.layout.overlay_control_height_px}px;
                border-radius: {t.radii.sm}px;
                padding: 0 10px;
                font-size: {t.typography.micro_px}px;
                font-weight: 600;
            }}
            QPushButton#OverlayDockUtility {{ background: {rgba(t.colors.chalk, 0.03)}; border: 1px solid {rgba(t.colors.chalk, 0.07)}; color: {t.colors.chalk}; }}
            QPushButton#OverlayDockPrimary {{ background: {rgba(t.colors.safety_red, 0.18)}; border: 1px solid {rgba(t.colors.safety_red, 0.30)}; color: {t.colors.chalk}; }}
            """
        )
