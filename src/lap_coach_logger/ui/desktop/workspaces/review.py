"""Immersive review workspace."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QTextEdit, QVBoxLayout

from lap_coach_logger.ui.desktop.panels import ReviewPanel as _LegacyReviewPanel
from lap_coach_logger.ui.desktop.panels import _metric_value, _add_metric_row
from lap_coach_logger.ui.desktop.workspaces.common import (
    ScenicArtworkWidget,
    WorkspacePanel,
    WorkspaceShellCallbacks,
    WorkspaceTopStrip,
    wire_shell_callbacks,
    workspace_page_styles,
)
from lap_coach_logger.ui.desktop.workspaces.design_system import WorkspaceDesignTokens, default_workspace_tokens


class ReviewWorkspace(_LegacyReviewPanel):
    """Immersive review route that stays visually tied to History."""

    open_folder_requested = Signal()
    queue_sync_requested = Signal()
    reprocess_requested = Signal()
    toggle_ignored_requested = Signal()
    delete_requested = Signal()
    return_requested = Signal()

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
        super().__init__(parent)

    def _build(self) -> None:
        self.setObjectName("ReviewWorkspacePage")

        root = QVBoxLayout(self)
        root.setContentsMargins(self._tokens.layout.shell_margin_px, self._tokens.layout.shell_margin_px, self._tokens.layout.shell_margin_px, self._tokens.layout.shell_margin_px)
        root.setSpacing(self._tokens.spacing.md)

        self._top_strip = WorkspaceTopStrip(active_page="history", context_label="Review", tokens=self._tokens)
        wire_shell_callbacks(self._top_strip, self._shell_callbacks)
        root.addWidget(self._top_strip)

        hero = WorkspacePanel("Recorded Session", heading="Review Summary", variant="hero", tokens=self._tokens)
        root.addWidget(hero)
        hero_row = QHBoxLayout()
        hero_row.setContentsMargins(0, 0, 0, 0)
        hero_row.setSpacing(self._tokens.layout.shell_gap_px)
        hero.content_layout.addLayout(hero_row)

        art = ScenicArtworkWidget(tokens=self._tokens, compact=False)
        art.setMinimumHeight(220)
        hero_row.addWidget(art, 2)

        status_col = QVBoxLayout()
        status_col.setContentsMargins(0, 0, 0, 0)
        status_col.setSpacing(self._tokens.spacing.sm)
        hero_row.addLayout(status_col, 1)

        self._status_value = _metric_value("READY", mono=False)
        self._quality_value = _metric_value("—", mono=False)
        self._quality_value.setWordWrap(True)
        status_col.addWidget(QLabel("SESSION STATUS"))
        status_col.addWidget(self._status_value)
        status_col.addWidget(QLabel("QUALITY CLASSIFICATION"))
        status_col.addWidget(self._quality_value)
        status_col.addStretch(1)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(self._tokens.layout.shell_gap_px)
        root.addLayout(body, 1)

        issues = WorkspacePanel("Warnings", heading="Review Attention", variant="inspect", tokens=self._tokens)
        body.addWidget(issues, 1)
        self._issues_summary = QLabel("No quality warnings or errors recorded")
        self._issues_summary.setWordWrap(True)
        self._issues_text = QTextEdit()
        self._issues_text.setReadOnly(True)
        self._issues_text.setMinimumHeight(180)
        issues.content_layout.addWidget(self._issues_summary)
        issues.content_layout.addWidget(self._issues_text, 1)

        details = WorkspacePanel("Bundle Summary", heading="Session Details", variant="inspect", tokens=self._tokens)
        body.addWidget(details, 1)
        self._detail_rows: dict[str, QLabel] = {}
        for key in (
            "Simulator",
            "Track",
            "Car",
            "Session Type",
            "Duration",
            "Sample Count",
            "Total Laps",
            "Valid Laps",
            "Clean Laps",
            "Best Lap",
            "Best Clean Lap",
            "Local Folder",
        ):
            value = _add_metric_row(details.content_layout, key)
            value.setWordWrap(True)
            self._detail_rows[key] = value

        actions = WorkspacePanel("Review Workflow", heading="Actions", variant="dock", tokens=self._tokens)
        root.addWidget(actions)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(self._tokens.spacing.xs)
        actions.content_layout.addLayout(row)

        self.btn_open_folder = self._button("OPEN FOLDER", object_name="PrimaryButton")
        self.btn_queue_sync = self._button("QUEUE SYNC")
        self.btn_reprocess = self._button("REPROCESS SESSION")
        self.btn_ignore = self._button("MARK IGNORED")
        self.btn_delete = self._button("DELETE LOCAL COPY", object_name="DangerButton")
        self.btn_return = self._button("RETURN TO HISTORY")
        for button in (
            self.btn_open_folder,
            self.btn_queue_sync,
            self.btn_reprocess,
            self.btn_ignore,
            self.btn_delete,
            self.btn_return,
        ):
            row.addWidget(button)
        row.addStretch(1)

        self.btn_open_folder.clicked.connect(self.open_folder_requested.emit)
        self.btn_queue_sync.clicked.connect(self.queue_sync_requested.emit)
        self.btn_reprocess.clicked.connect(self.reprocess_requested.emit)
        self.btn_ignore.clicked.connect(self.toggle_ignored_requested.emit)
        self.btn_delete.clicked.connect(self.delete_requested.emit)
        self.btn_return.clicked.connect(self.return_requested.emit)

        self.setStyleSheet(workspace_page_styles("ReviewWorkspacePage", tokens=self._tokens))

    def _button(self, label: str, *, object_name: str | None = None):
        from PySide6.QtWidgets import QPushButton

        button = QPushButton(label)
        if object_name:
            button.setObjectName(object_name)
        return button

    def set_shell_status(self, *, status: str, detail: str, monitoring_active: bool) -> None:
        if self._top_strip is not None:
            self._top_strip.set_status(status=status, detail=detail, monitoring_active=monitoring_active)
