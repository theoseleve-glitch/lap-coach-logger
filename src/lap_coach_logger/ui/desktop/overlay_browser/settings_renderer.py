"""Schema-driven settings form renderer for the immersive overlay workspace."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from lap_coach_logger.overlays import (
    OverlayBrowserSettingFieldView,
    OverlayBrowserSettingsSectionView,
)
from lap_coach_logger.ui.desktop.overlay_browser.design_system import (
    OverlayBrowserDesignTokens,
    default_overlay_browser_tokens,
    rgba,
)


@dataclass(slots=True)
class _FieldBinding:
    field: OverlayBrowserSettingFieldView
    widget: QWidget
    baseline_value: object


class AccordionSection(QFrame):
    """Thin collapsible inspector section."""

    toggled = Signal(bool)

    def __init__(
        self,
        title: str,
        *,
        description: str = "",
        expanded: bool = True,
        tokens: OverlayBrowserDesignTokens | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tokens = tokens or default_overlay_browser_tokens()
        self._expanded = bool(expanded)
        self._title = title
        self.setObjectName("OverlayAccordionSection")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._toggle = QPushButton("")
        self._toggle.setCheckable(True)
        self._toggle.setChecked(self._expanded)
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.setObjectName("OverlayAccordionToggle")
        self._toggle.clicked.connect(self._set_expanded)
        root.addWidget(self._toggle)

        self._description = QLabel(description)
        self._description.setWordWrap(True)
        self._description.setObjectName("OverlayAccordionDescription")
        self._description.setVisible(bool(description))
        root.addWidget(self._description)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, self._tokens.spacing.xs, 0, self._tokens.spacing.md)
        self._content_layout.setSpacing(self._tokens.spacing.xs)
        self._content.setVisible(self._expanded)
        root.addWidget(self._content)

        self._update_toggle_text()
        self._apply_style()

    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    def _set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        self._content.setVisible(self._expanded)
        self._toggle.setChecked(self._expanded)
        self._update_toggle_text()
        self.toggled.emit(self._expanded)

    def _update_toggle_text(self) -> None:
        marker = "-" if self._expanded else "+"
        self._toggle.setText(f"{self._title}   {marker}")

    def _apply_style(self) -> None:
        t = self._tokens
        self.setStyleSheet(
            f"""
            QFrame#OverlayAccordionSection {{
                background: transparent;
                border: none;
                border-top: 1px solid {rgba(t.colors.chalk, 0.07)};
            }}
            QPushButton#OverlayAccordionToggle {{
                text-align: left;
                background: transparent;
                border: none;
                padding: {t.spacing.sm}px 0 {t.spacing.xs}px 0;
                color: {rgba(t.colors.chalk, 0.84)};
                font-family: '{t.typography.body_family}', 'Segoe UI', sans-serif;
                font-size: {t.typography.caption_px}px;
                font-weight: 600;
            }}
            QPushButton#OverlayAccordionToggle:hover {{
                color: {t.colors.chalk};
            }}
            QLabel#OverlayAccordionDescription {{
                padding: 0 0 {t.spacing.xs}px 0;
                color: {rgba(t.colors.steel, 0.70)};
                font-family: '{t.typography.body_family}', 'Segoe UI', sans-serif;
                font-size: {t.typography.micro_px}px;
            }}
            """
        )


class OverlaySettingsFormRenderer(QScrollArea):
    """Renders backend settings DTOs into the workspace control style."""

    values_changed = Signal(dict)
    dirty_changed = Signal(bool)

    def __init__(
        self,
        *,
        tokens: OverlayBrowserDesignTokens | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tokens = tokens or default_overlay_browser_tokens()
        self._sections: tuple[OverlayBrowserSettingsSectionView, ...] = ()
        self._bindings: dict[str, _FieldBinding] = {}
        self._search_query = ""

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setObjectName("OverlaySettingsFormRenderer")
        self.setStyleSheet("QScrollArea#OverlaySettingsFormRenderer { background: transparent; border: none; }")

        holder = QWidget()
        self._layout = QVBoxLayout(holder)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addStretch(1)
        self.setWidget(holder)

    def set_sections(self, sections: tuple[OverlayBrowserSettingsSectionView, ...]) -> None:
        self._sections = sections
        self._rebuild()

    def set_search_query(self, query: str) -> None:
        self._search_query = str(query or "").strip().lower()
        self._rebuild()

    def collect_changes(self) -> dict[str, object]:
        changes: dict[str, object] = {}
        for field_key, binding in self._bindings.items():
            value = self._read_value(binding)
            if value != binding.baseline_value:
                changes[field_key] = value
        return changes

    def reset_to_baseline(self) -> None:
        for binding in self._bindings.values():
            self._write_value(binding, binding.baseline_value)
        self.values_changed.emit({})
        self.dirty_changed.emit(False)

    def _rebuild(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._bindings.clear()

        matched_sections = 0
        for section in self._sections:
            visible_fields = tuple(field for field in section.fields if self._field_matches_query(field))
            if not visible_fields:
                continue
            matched_sections += 1
            accordion = AccordionSection(
                section.label,
                description=section.description,
                expanded=True,
                tokens=self._tokens,
            )
            for field in visible_fields:
                accordion.content_layout().addWidget(self._build_field_row(field))
            self._layout.addWidget(accordion)

        if matched_sections == 0:
            empty = QLabel("No settings match this filter.")
            empty.setObjectName("OverlaySettingsEmptyState")
            empty.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self._layout.addWidget(empty)

        self._layout.addStretch(1)
        self.values_changed.emit(self.collect_changes())
        self.dirty_changed.emit(bool(self.collect_changes()))

    def _build_field_row(self, field: OverlayBrowserSettingFieldView) -> QWidget:
        row = QFrame()
        row.setObjectName("OverlaySettingRow")
        outer = QVBoxLayout(row)
        outer.setContentsMargins(0, self._tokens.spacing.xs, 0, self._tokens.spacing.xs)
        outer.setSpacing(self._tokens.spacing.xxs)

        main = QHBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(self._tokens.spacing.sm)
        outer.addLayout(main)

        label_wrap = QWidget()
        label_wrap.setFixedWidth(self._tokens.layout.overlay_inspector_label_width_px)
        label_layout = QVBoxLayout(label_wrap)
        label_layout.setContentsMargins(0, 0, 0, 0)
        label_layout.setSpacing(self._tokens.spacing.xxs)
        main.addWidget(label_wrap, 0)

        label = QLabel(field.label)
        label.setObjectName("OverlaySettingLabel")
        label_layout.addWidget(label)

        if field.unit:
            unit = QLabel(field.unit)
            unit.setObjectName("OverlaySettingUnit")
            label_layout.addWidget(unit)

        editor_wrap = QWidget()
        editor_layout = QVBoxLayout(editor_wrap)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(self._tokens.spacing.xxs)
        main.addWidget(editor_wrap, 1)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(self._tokens.spacing.xs)
        editor_layout.addLayout(head)

        editor = self._create_editor(field)
        editor.setEnabled(field.editable)
        head.addWidget(editor, 1)

        if field.premium_only:
            badge = QLabel("Pro")
            badge.setObjectName("OverlaySettingPremiumBadge")
            head.addWidget(badge)
        if field.advanced:
            badge = QLabel("Adv")
            badge.setObjectName("OverlaySettingAdvancedBadge")
            head.addWidget(badge)

        if field.description:
            description = QLabel(field.description)
            description.setWordWrap(True)
            description.setObjectName("OverlaySettingDescription")
            editor_layout.addWidget(description)

        if field.issues:
            issue = QLabel("; ".join(field.issues))
            issue.setWordWrap(True)
            issue.setObjectName("OverlaySettingIssue")
            editor_layout.addWidget(issue)

        self._bindings[field.field_key] = _FieldBinding(
            field=field,
            widget=editor,
            baseline_value=field.current_value,
        )
        row.setStyleSheet(self._row_stylesheet())
        return row

    def _create_editor(self, field: OverlayBrowserSettingFieldView) -> QWidget:
        kind = field.kind
        control_height = self._tokens.layout.overlay_control_height_px
        if kind == "boolean":
            widget = QCheckBox("Enabled")
            widget.setChecked(bool(field.current_value))
            widget.toggled.connect(lambda _checked: self._emit_change_state())
            return widget
        if kind == "integer":
            widget = QSpinBox()
            widget.setRange(int(field.min_value or -99999), int(field.max_value or 99999))
            widget.setSingleStep(int(field.step or 1))
            widget.setValue(int(field.current_value or 0))
            if field.unit:
                widget.setSuffix(f" {field.unit}")
            widget.setMinimumHeight(control_height)
            widget.valueChanged.connect(lambda _value: self._emit_change_state())
            return widget
        if kind in {"float", "range"}:
            widget = QDoubleSpinBox()
            widget.setDecimals(2)
            widget.setRange(float(field.min_value or -99999.0), float(field.max_value or 99999.0))
            widget.setSingleStep(float(field.step or 0.1))
            widget.setValue(float(field.current_value or 0.0))
            if field.unit:
                widget.setSuffix(f" {field.unit}")
            widget.setMinimumHeight(control_height)
            widget.valueChanged.connect(lambda _value: self._emit_change_state())
            return widget

        widget = QComboBox()
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        widget.setMinimumHeight(control_height)
        if field.options:
            for option in field.options:
                widget.addItem(option.label, option.value)
            index = widget.findData(field.current_value)
            widget.setCurrentIndex(index if index >= 0 else 0)
        else:
            widget.addItem(str(field.current_value or ""), field.current_value)
        widget.currentIndexChanged.connect(lambda _index: self._emit_change_state())
        return widget

    def _read_value(self, binding: _FieldBinding) -> object:
        widget = binding.widget
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QSpinBox):
            return int(widget.value())
        if isinstance(widget, QDoubleSpinBox):
            return float(widget.value())
        if isinstance(widget, QComboBox):
            return widget.currentData()
        return None

    def _write_value(self, binding: _FieldBinding, value: object) -> None:
        widget = binding.widget
        if isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(value or 0))
        elif isinstance(widget, QDoubleSpinBox):
            widget.setValue(float(value or 0.0))
        elif isinstance(widget, QComboBox):
            index = widget.findData(value)
            widget.setCurrentIndex(index if index >= 0 else 0)

    def _field_matches_query(self, field: OverlayBrowserSettingFieldView) -> bool:
        if not self._search_query:
            return True
        haystack = " ".join((field.label, field.description, field.section_key)).lower()
        return self._search_query in haystack

    def _emit_change_state(self) -> None:
        changes = self.collect_changes()
        self.values_changed.emit(changes)
        self.dirty_changed.emit(bool(changes))

    def _row_stylesheet(self) -> str:
        t = self._tokens
        return f"""
        QFrame#OverlaySettingRow {{
            background: transparent;
            border: none;
            border-bottom: 1px solid {rgba(t.colors.chalk, 0.06)};
        }}
        QLabel#OverlaySettingLabel {{
            color: {rgba(t.colors.chalk, 0.94)};
            font-family: '{t.typography.body_family}', 'Segoe UI', sans-serif;
            font-size: {t.typography.caption_px}px;
            font-weight: 600;
        }}
        QLabel#OverlaySettingUnit {{
            color: {rgba(t.colors.steel, 0.60)};
            font-family: '{t.typography.mono_family}', 'Consolas', monospace;
            font-size: {t.typography.micro_px}px;
        }}
        QLabel#OverlaySettingDescription {{
            color: {rgba(t.colors.steel, 0.72)};
            font-family: '{t.typography.body_family}', 'Segoe UI', sans-serif;
            font-size: {t.typography.micro_px}px;
        }}
        QLabel#OverlaySettingIssue {{
            color: {t.colors.safety_red};
            font-family: '{t.typography.body_family}', 'Segoe UI', sans-serif;
            font-size: {t.typography.micro_px}px;
        }}
        QLabel#OverlaySettingPremiumBadge, QLabel#OverlaySettingAdvancedBadge {{
            padding: 1px 6px;
            border-radius: {t.radii.xs}px;
            font-family: '{t.typography.mono_family}', 'Consolas', monospace;
            font-size: {t.typography.micro_px}px;
            font-weight: 700;
        }}
        QLabel#OverlaySettingPremiumBadge {{
            color: #1A1304;
            background: {t.colors.pit_orange};
        }}
        QLabel#OverlaySettingAdvancedBadge {{
            color: {rgba(t.colors.chalk, 0.78)};
            background: {rgba(t.colors.chalk, 0.035)};
            border: 1px solid {rgba(t.colors.chalk, 0.06)};
        }}
        QLabel#OverlaySettingsEmptyState {{
            color: {rgba(t.colors.steel, 0.66)};
            padding: {t.spacing.md}px 0;
            font-family: '{t.typography.body_family}', 'Segoe UI', sans-serif;
            font-size: {t.typography.caption_px}px;
        }}
        QCheckBox {{
            color: {t.colors.chalk};
            spacing: {t.spacing.sm}px;
            font-family: '{t.typography.body_family}', 'Segoe UI', sans-serif;
            font-size: {t.typography.caption_px}px;
            min-height: {t.layout.overlay_control_height_px}px;
        }}
        QCheckBox::indicator {{
            width: 14px;
            height: 14px;
            border-radius: 3px;
            border: 1px solid {rgba(t.colors.chalk, 0.16)};
            background: {rgba(t.colors.chalk, 0.03)};
        }}
        QCheckBox::indicator:checked {{
            background: {t.colors.acid_green};
            border-color: {t.colors.acid_green};
        }}
        QSpinBox, QDoubleSpinBox, QComboBox {{
            min-height: {t.layout.overlay_control_height_px}px;
            background: {rgba("#04070B", 0.90)};
            border: 1px solid {rgba(t.colors.chalk, 0.08)};
            border-radius: {t.radii.sm}px;
            color: {t.colors.chalk};
            padding: 2px 8px;
            font-family: '{t.typography.body_family}', 'Segoe UI', sans-serif;
            font-size: {t.typography.caption_px}px;
        }}
        QComboBox::drop-down {{
            border: none;
            width: 18px;
        }}
        QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled, QCheckBox:disabled {{
            color: {rgba(t.colors.steel, 0.46)};
        }}
        """
