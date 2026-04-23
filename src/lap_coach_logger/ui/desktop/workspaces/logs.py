"""Immersive logs workspace."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
)

from lap_coach_logger.ui.desktop.panels import LogsPanel as _LegacyLogsPanel
from lap_coach_logger.ui.desktop.workspaces.common import (
    WorkspacePanel,
    WorkspaceShellCallbacks,
    WorkspaceTopStrip,
    wire_shell_callbacks,
    workspace_page_styles,
)
from lap_coach_logger.ui.desktop.workspaces.design_system import WorkspaceDesignTokens, default_workspace_tokens


class LogsWorkspace(_LegacyLogsPanel):
    """Table-first immersive diagnostics console."""

    _COL_TIME = 0
    _COL_LEVEL = 1
    _COL_SUBSYSTEM = 2
    _COL_SIM = 3
    _COL_ADAPTER = 4
    _COL_MODULE = 5
    _COL_MESSAGE = 6

    def __init__(
        self,
        *,
        tokens: WorkspaceDesignTokens | None = None,
        shell_callbacks: WorkspaceShellCallbacks | None = None,
        parent: QWidget | None = None,
    ) -> None:
        self._tokens = tokens or default_workspace_tokens()
        self._shell_callbacks = shell_callbacks or WorkspaceShellCallbacks()
        self._top_strip: WorkspaceTopStrip | None = None
        self._detail_summary: QLabel | None = None
        self._detail_message: QTextEdit | None = None
        super().__init__(parent)

    def _build(self) -> None:
        self.setObjectName("LogsWorkspacePage")

        root = QVBoxLayout(self)
        root.setContentsMargins(self._tokens.layout.shell_margin_px, self._tokens.layout.shell_margin_px, self._tokens.layout.shell_margin_px, self._tokens.layout.shell_margin_px)
        root.setSpacing(self._tokens.spacing.md)

        self._top_strip = WorkspaceTopStrip(active_page="logs", tokens=self._tokens)
        wire_shell_callbacks(self._top_strip, self._shell_callbacks)
        root.addWidget(self._top_strip)

        filters_card = WorkspacePanel("Filters", heading="Diagnostics Console", variant="dock", tokens=self._tokens)
        root.addWidget(filters_card)
        filters_layout = filters_card.content_layout

        filters = QHBoxLayout()
        filters.setContentsMargins(0, 0, 0, 0)
        filters.setSpacing(self._tokens.spacing.xs)
        filters_layout.addLayout(filters)

        self.filter_severity = self._combo(["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.filter_subsystem = self._combo(["ALL", "system", "adapter", "session", "storage", "ui"])
        self.filter_simulator = self._combo(["ALL", "iRacing", "Assetto Corsa", "ACC", "Le Mans Ultimate", "-"])
        self.filter_adapter = self._combo(["ALL", "IRacingAdapter", "AssettoCorsaAdapter", "ACCAdapter", "LMUAdapter", "LMURecordingImport", "-"])
        self.filter_scope = self._combo(["ALL LOGS", "CURRENT SESSION ONLY"])
        self.search = self._line_edit("Search logs...")
        filters.addWidget(self.filter_severity)
        filters.addWidget(self.filter_subsystem)
        filters.addWidget(self.filter_simulator)
        filters.addWidget(self.filter_adapter)
        filters.addWidget(self.filter_scope)
        filters.addWidget(self.search, 1)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(self._tokens.layout.shell_gap_px)
        root.addLayout(body, 1)

        table_card = WorkspacePanel("Event Stream", heading="Application Logs", variant="hero", tokens=self._tokens)
        body.addWidget(table_card, 3)
        table_layout = table_card.content_layout

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(["TIME", "LEVEL", "SUBSYSTEM", "SIM", "ADAPTER", "MODULE", "MESSAGE"])
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(self._COL_TIME, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(self._COL_LEVEL, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(self._COL_SUBSYSTEM, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(self._COL_SIM, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(self._COL_ADAPTER, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(self._COL_MODULE, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(self._COL_MESSAGE, QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self._table.setWordWrap(False)
        self._table.setMinimumHeight(420)
        self._table.itemSelectionChanged.connect(self._sync_detail_panel)
        table_layout.addWidget(self._table, 1)

        inspect = WorkspacePanel("Inspector", heading="Selected Entry", variant="inspect", tokens=self._tokens)
        body.addWidget(inspect, 1)
        inspect_layout = inspect.content_layout

        self._detail_summary = QLabel("Select a log row to inspect the full entry.")
        self._detail_summary.setWordWrap(True)
        inspect_layout.addWidget(self._detail_summary)

        self._detail_message = QTextEdit()
        self._detail_message.setReadOnly(True)
        self._detail_message.setMinimumHeight(280)
        inspect_layout.addWidget(self._detail_message, 1)

        dock = WorkspacePanel("Actions", heading="Console Controls", variant="dock", tokens=self._tokens)
        root.addWidget(dock)
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(self._tokens.spacing.xs)
        dock.content_layout.addLayout(actions)

        self._btn_clear = self._button("CLEAR", object_name="DangerButton")
        self._btn_scroll = self._button("AUTO-SCROLL: ON")
        self._btn_copy_selected = self._button("COPY SELECTED")
        self._btn_copy_visible = self._button("COPY VISIBLE")
        self._btn_export_bundle = self._button("EXPORT SUPPORT BUNDLE", object_name="PrimaryButton")
        actions.addWidget(self._btn_clear)
        actions.addWidget(self._btn_scroll)
        actions.addWidget(self._btn_copy_selected)
        actions.addWidget(self._btn_copy_visible)
        actions.addStretch(1)
        actions.addWidget(self._btn_export_bundle)

        self._btn_clear.clicked.connect(self._clear)
        self._btn_scroll.clicked.connect(self._toggle_scroll)
        self._btn_copy_selected.clicked.connect(self._copy_selected)
        self._btn_copy_visible.clicked.connect(self._copy_visible)
        self._btn_export_bundle.clicked.connect(self._export_bundle)
        self.filter_severity.currentTextChanged.connect(self._refresh_view)
        self.filter_subsystem.currentTextChanged.connect(self._refresh_view)
        self.filter_simulator.currentTextChanged.connect(self._refresh_view)
        self.filter_adapter.currentTextChanged.connect(self._refresh_view)
        self.filter_scope.currentTextChanged.connect(self._refresh_view)
        self.search.textChanged.connect(self._refresh_view)

        self.setStyleSheet(workspace_page_styles("LogsWorkspacePage", tokens=self._tokens))

    def _combo(self, items: list[str]):
        from PySide6.QtWidgets import QComboBox

        combo = QComboBox()
        combo.addItems(items)
        return combo

    def _line_edit(self, placeholder: str):
        from PySide6.QtWidgets import QLineEdit

        line = QLineEdit()
        line.setPlaceholderText(placeholder)
        return line

    def _button(self, label: str, *, object_name: str | None = None):
        from PySide6.QtWidgets import QPushButton

        button = QPushButton(label)
        if object_name:
            button.setObjectName(object_name)
        return button

    def _toggle_scroll(self) -> None:
        current = self._btn_scroll.text()
        if "ON" in current:
            self._btn_scroll.setText("AUTO-SCROLL: OFF")
        else:
            self._btn_scroll.setText("AUTO-SCROLL: ON")

    def _copy_selected(self) -> None:
        pass

    def _copy_visible(self) -> None:
        pass

    def _export_bundle(self) -> None:
        pass

    def _refresh_view(self) -> None:
        self._sync_detail_panel()

    def _clear(self) -> None:
        self._table.setRowCount(0)
        self._sync_detail_panel()

    def _sync_detail_panel(self) -> None:
        if self._detail_summary is None or self._detail_message is None:
            return
        rows = sorted({idx.row() for idx in self._table.selectedIndexes()})
        if not rows:
            self._detail_summary.setText("Select a log row to inspect the full entry.")
            self._detail_message.setPlainText("")
            return
        row = rows[-1]
        parts = []
        for col in range(self._table.columnCount()):
            item = self._table.item(row, col)
            parts.append(item.text() if item else "")
        self._detail_summary.setText(" | ".join(parts[:4]))
        self._detail_message.setPlainText(self._row_to_text(row))

    def _row_to_text(self, row: int) -> str:
        parts = []
        for col in range(self._table.columnCount()):
            item = self._table.item(row, col)
            parts.append(item.text() if item else "")
        return "\n".join(parts)

    def set_shell_status(self, *, status: str, detail: str, monitoring_active: bool) -> None:
        if self._top_strip is not None:
            self._top_strip.set_status(status=status, detail=detail, monitoring_active=monitoring_active)
