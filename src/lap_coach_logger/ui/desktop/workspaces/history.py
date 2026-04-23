"""Immersive session archive workspace."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QVBoxLayout,
)

from lap_coach_logger.ui.desktop.panels import HistoryPanel as _LegacyHistoryPanel
from lap_coach_logger.ui.desktop.workspaces.common import (
    WorkspacePanel,
    WorkspaceShellCallbacks,
    WorkspaceTopStrip,
    wire_shell_callbacks,
    workspace_page_styles,
)
from lap_coach_logger.ui.desktop.workspaces.design_system import WorkspaceDesignTokens, default_workspace_tokens


class HistoryWorkspace(_LegacyHistoryPanel):
    """Archive browser with a dominant table and selected-session inspector."""

    _COLUMNS = ("DATE", "SIM", "TRACK", "CAR", "TYPE", "LAPS", "BEST", "QUALITY", "STATUS")

    refresh_requested = Signal()
    review_requested = Signal()
    open_requested = Signal()
    reprocess_requested = Signal()
    toggle_ignored_requested = Signal()
    queue_sync_requested = Signal()
    export_requested = Signal()
    copy_id_requested = Signal()
    delete_requested = Signal()

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
        self._summary_total: QLabel | None = None
        self._summary_visible: QLabel | None = None
        self._summary_quality: QLabel | None = None
        self._selection_title: QLabel | None = None
        self._selection_meta: QLabel | None = None
        self._selection_status: QLabel | None = None
        self._sessions: list[dict] = []
        self._filtered_sessions: list[dict] = []
        super().__init__(parent)

    def _build(self) -> None:
        self.setObjectName("HistoryWorkspacePage")

        root = QVBoxLayout(self)
        root.setContentsMargins(self._tokens.layout.shell_margin_px, self._tokens.layout.shell_margin_px, self._tokens.layout.shell_margin_px, self._tokens.layout.shell_margin_px)
        root.setSpacing(self._tokens.spacing.md)

        self._top_strip = WorkspaceTopStrip(active_page="history", tokens=self._tokens)
        wire_shell_callbacks(self._top_strip, self._shell_callbacks)
        root.addWidget(self._top_strip)

        summary = WorkspacePanel("Archive", heading="Recorded Sessions", variant="dock", tokens=self._tokens)
        root.addWidget(summary)
        summary_row = QHBoxLayout()
        summary_row.setContentsMargins(0, 0, 0, 0)
        summary_row.setSpacing(self._tokens.spacing.lg)
        summary.content_layout.addLayout(summary_row)

        self._summary_total = QLabel("0 sessions")
        self._summary_visible = QLabel("0 visible")
        self._summary_quality = QLabel("Awaiting data")
        for label in (self._summary_total, self._summary_visible, self._summary_quality):
            summary_row.addWidget(label)
        summary_row.addStretch(1)

        filters_card = WorkspacePanel("Filters", heading="Archive Query", variant="rail", tokens=self._tokens)
        root.addWidget(filters_card)
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(self._tokens.spacing.xs)
        filters_card.content_layout.addLayout(filter_layout)

        self.filter_sim = QComboBox()
        self.filter_sim.addItem("All Simulators")
        self.filter_sim.currentTextChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.filter_sim)

        self.filter_track = QComboBox()
        self.filter_track.addItem("All Tracks")
        self.filter_track.currentTextChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.filter_track)

        self.filter_car = QComboBox()
        self.filter_car.addItem("All Cars")
        self.filter_car.currentTextChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.filter_car)

        self.filter_quality = QComboBox()
        self.filter_quality.addItems(["All Quality", "Accepted", "Warnings", "Rejected", "Unknown"])
        self.filter_quality.currentTextChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.filter_quality)

        filter_layout.addStretch(1)
        self.btn_clear_filters = self._button("CLEAR FILTERS")
        self.btn_clear_filters.clicked.connect(self._clear_filters)
        filter_layout.addWidget(self.btn_clear_filters)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(self._tokens.layout.shell_gap_px)
        root.addLayout(body, 1)

        table_card = WorkspacePanel("Archive", heading="Session Table", variant="hero", tokens=self._tokens)
        body.addWidget(table_card, 3)
        table_layout = table_card.content_layout

        self._table = QTableWidget(0, len(self._COLUMNS))
        self._table.setHorizontalHeaderLabels(list(self._COLUMNS))
        hdr = self._table.horizontalHeader()
        hdr.setStretchLastSection(False)
        col_widths = {
            0: 135,
            1: 120,
            2: 120,
            3: 100,
            4: 80,
            5: 80,
            6: 60,
            7: 60,
            8: 80,
            9: 110,
            10: 90,
            11: 110,
            12: 0,
        }
        for col, width in col_widths.items():
            if width > 0:
                hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
                self._table.setColumnWidth(col, width)
            else:
                self._table.setColumnHidden(col, True)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        self._table.setWordWrap(False)
        self._table.verticalHeader().setDefaultSectionSize(24)
        self._table.itemSelectionChanged.connect(self._sync_selection_summary)
        table_layout.addWidget(self._table, 1)

        self._empty = QLabel("No sessions recorded yet")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet("padding: 40px;")
        table_layout.addWidget(self._empty)

        inspect = WorkspacePanel("Selected Session", heading="Inspector", variant="inspect", tokens=self._tokens)
        body.addWidget(inspect, 1)
        inspect_layout = inspect.content_layout

        self._selection_title = QLabel("No session selected")
        self._selection_title.setWordWrap(True)
        inspect_layout.addWidget(self._selection_title)

        self._selection_meta = QLabel("Choose a row in the archive table to inspect it.")
        self._selection_meta.setWordWrap(True)
        inspect_layout.addWidget(self._selection_meta)

        self._selection_status = QLabel("")
        self._selection_status.setWordWrap(True)
        inspect_layout.addWidget(self._selection_status)
        inspect_layout.addStretch(1)

        action_card = WorkspacePanel("Actions", heading="Archive Workflow", variant="dock", tokens=self._tokens)
        root.addWidget(action_card)
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(self._tokens.spacing.xs)
        action_card.content_layout.addLayout(actions)

        self.btn_refresh = self._button("REFRESH", object_name="PrimaryButton")
        self.btn_review = self._button("VIEW REVIEW")
        self.btn_open = self._button("OPEN FOLDER")
        self.btn_reprocess = self._button("REPROCESS")
        self.btn_marked = self._button("MARK IGNORED")
        self.btn_queue_sync = self._button("QUEUE SYNC")
        self.btn_export = self._button("EXPORT CSV")
        self.btn_copy_id = self._button("COPY ID")
        self.btn_delete = self._button("DELETE", object_name="DangerButton")
        for button in (
            self.btn_refresh,
            self.btn_review,
            self.btn_open,
            self.btn_reprocess,
            self.btn_marked,
            self.btn_queue_sync,
            self.btn_export,
            self.btn_copy_id,
            self.btn_delete,
        ):
            actions.addWidget(button)
        actions.addStretch(1)

        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        self.btn_review.clicked.connect(self.review_requested.emit)
        self.btn_open.clicked.connect(self.open_requested.emit)
        self.btn_reprocess.clicked.connect(self.reprocess_requested.emit)
        self.btn_marked.clicked.connect(self.toggle_ignored_requested.emit)
        self.btn_queue_sync.clicked.connect(self.queue_sync_requested.emit)
        self.btn_export.clicked.connect(self.export_requested.emit)
        self.btn_copy_id.clicked.connect(self.copy_id_requested.emit)
        self.btn_delete.clicked.connect(self.delete_requested.emit)

        self.setStyleSheet(workspace_page_styles("HistoryWorkspacePage", tokens=self._tokens))

    def _button(self, label: str, *, object_name: str | None = None):
        from PySide6.QtWidgets import QPushButton

        button = QPushButton(label)
        if object_name:
            button.setObjectName(object_name)
        return button

    def update_sessions(self, sessions: list[dict]) -> None:
        self._sessions = list(sessions)
        self._apply_filters()

    def _apply_filters(self) -> None:
        self._filtered_sessions = list(self._sessions)
        self._populate_table()

    def _clear_filters(self) -> None:
        for combo in (self.filter_sim, self.filter_track, self.filter_car, self.filter_quality):
            combo.setCurrentIndex(0)
        self._apply_filters()

    def _populate_table(self) -> None:
        self._sync_selection_summary()

    def _sync_selection_summary(self) -> None:
        if self._summary_total is not None:
            self._summary_total.setText(f"{len(self._sessions)} sessions")
        if self._summary_visible is not None:
            self._summary_visible.setText(f"{len(self._filtered_sessions)} visible")
        if self._summary_quality is not None:
            qualities = sorted({str(session.get('quality') or 'unknown').replace('_', ' ').upper() for session in self._filtered_sessions[:5]})
            self._summary_quality.setText(", ".join(qualities) if qualities else "Awaiting data")
        if self._selection_title is None or self._selection_meta is None or self._selection_status is None:
            return
        row = self._table.currentRow()
        if not (0 <= row < len(self._filtered_sessions)):
            self._selection_title.setText("No session selected")
            self._selection_meta.setText("Choose a row in the archive table to inspect it.")
            self._selection_status.setText("")
            return
        session = self._filtered_sessions[row]
        self._selection_title.setText(str(session.get("name") or session.get("track") or "Session"))
        self._selection_meta.setText(
            " / ".join(
                str(value)
                for value in (
                    session.get("sim") or "—",
                    session.get("car") or "—",
                    session.get("session_type") or "—",
                    session.get("duration_display") or "—",
                )
            )
        )
        self._selection_status.setText(
            " • ".join(
                str(value)
                for value in (
                    session.get("quality") or "unknown",
                    session.get("review_status") or "ready",
                    session.get("sync_status") or "not_queued",
                )
            ).upper()
        )

    def set_shell_status(self, *, status: str, detail: str, monitoring_active: bool) -> None:
        if self._top_strip is not None:
            self._top_strip.set_status(status=status, detail=detail, monitoring_active=monitoring_active)
