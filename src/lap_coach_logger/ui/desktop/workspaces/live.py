"""Immersive live diagnostics workspace."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from lap_coach_logger.ui.desktop.panels import LivePanel as _LegacyLivePanel
from lap_coach_logger.ui.desktop.panels import _ACID_GREEN, _MARSHAL_YELLOW, _SAFETY_RED, _STEEL, _add_metric_row, _metric_label
from lap_coach_logger.ui.desktop.workspaces.common import (
    WorkspacePanel,
    WorkspaceShellCallbacks,
    WorkspaceTopStrip,
    wire_shell_callbacks,
    workspace_page_styles,
)
from lap_coach_logger.ui.desktop.workspaces.design_system import WorkspaceDesignTokens, default_workspace_tokens
from lap_coach_logger.ui.desktop.workspaces.telemetry_widgets import TelemetrySparkline


class LiveWorkspace(_LegacyLivePanel):
    """Focused live operator console built on the legacy update contract."""

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
        self.setObjectName("LiveWorkspacePage")

        root = QVBoxLayout(self)
        root.setContentsMargins(self._tokens.layout.shell_margin_px, self._tokens.layout.shell_margin_px, self._tokens.layout.shell_margin_px, self._tokens.layout.shell_margin_px)
        root.setSpacing(self._tokens.spacing.md)

        self._top_strip = WorkspaceTopStrip(active_page="live", tokens=self._tokens)
        wire_shell_callbacks(self._top_strip, self._shell_callbacks)
        root.addWidget(self._top_strip)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(self._tokens.layout.shell_gap_px)
        root.addLayout(body, 1)

        left_col = QVBoxLayout()
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(self._tokens.spacing.md)
        body.addLayout(left_col, 2)

        runtime = WorkspacePanel("Runtime", heading="Live Diagnostics", variant="rail", tokens=self._tokens)
        left_col.addWidget(runtime)
        runtime_layout = runtime.content_layout
        self._feed_rows: dict[str, QLabel] = {}
        for key in ("Status", "State", "Adapter", "Detection", "Track", "Car", "Lap", "Samples", "Elapsed"):
            val = _add_metric_row(runtime_layout, key)
            self._feed_rows[key] = val

        self._stream_badge = QLabel("NO DATA")
        self._stream_badge.setStyleSheet(
            f"padding: 6px 12px; border-radius: {self._tokens.radii.md}px; font-weight:700;"
            f" background-color: rgba(250,204,21,0.15); color:{_MARSHAL_YELLOW}; letter-spacing:1px;"
        )
        runtime_layout.addWidget(self._stream_badge)

        traces = WorkspacePanel("Signals", heading="Real-Time Traces", variant="hero", tokens=self._tokens)
        left_col.addWidget(traces, 1)
        traces_layout = traces.content_layout
        self._plots: dict[str, TelemetrySparkline] = {
            "speed_kph": TelemetrySparkline(color=_ACID_GREEN, min_value=0.0, max_value=320.0),
            "throttle_pct": TelemetrySparkline(color="#C9A84C", min_value=0.0, max_value=1.0),
            "brake_pct": TelemetrySparkline(color=_SAFETY_RED, min_value=0.0, max_value=1.0),
            "steering_deg": TelemetrySparkline(color="#F5BE4B", min_value=-540.0, max_value=540.0),
            "rpm": TelemetrySparkline(color="#7AA3C8", min_value=0.0, max_value=11000.0),
        }

        plot_grid = QGridLayout()
        plot_grid.setHorizontalSpacing(12)
        plot_grid.setVerticalSpacing(10)
        for row, (label, key) in enumerate(
            (
                ("SPEED", "speed_kph"),
                ("THROTTLE", "throttle_pct"),
                ("BRAKE", "brake_pct"),
                ("STEERING", "steering_deg"),
                ("RPM", "rpm"),
            )
        ):
            lbl = _metric_label(label)
            lbl.setMinimumWidth(96)
            plot_grid.addWidget(lbl, row, 0)
            plot_grid.addWidget(self._plots[key], row, 1)
        traces_layout.addLayout(plot_grid)

        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(self._tokens.spacing.md)
        body.addLayout(right_col, 1)

        diag = WorkspacePanel("Health", heading="Capture Quality", variant="inspect", tokens=self._tokens)
        right_col.addWidget(diag)
        diag_layout = diag.content_layout
        self._diag_rows: dict[str, QLabel] = {}
        for key in (
            "Configured Sample Rate",
            "Measured Sample Rate",
            "Update Frequency",
            "Staleness",
            "Last Error",
        ):
            value = _add_metric_row(diag_layout, key)
            value.setWordWrap(True)
            self._diag_rows[key] = value

        data_card = WorkspacePanel("Data Stream", heading="Live Key Values", variant="inspect", tokens=self._tokens)
        right_col.addWidget(data_card, 1)
        data_layout = data_card.content_layout
        self._data_table = QTableWidget(0, 2)
        self._data_table.setHorizontalHeaderLabels(["VARIABLE", "VALUE"])
        self._data_table.horizontalHeader().setStretchLastSection(True)
        self._data_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._data_table.verticalHeader().setVisible(False)
        self._data_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._data_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._data_table.setMinimumHeight(260)
        data_layout.addWidget(self._data_table)

        self.setStyleSheet(workspace_page_styles("LiveWorkspacePage", tokens=self._tokens))

    def set_shell_status(self, *, status: str, detail: str, monitoring_active: bool) -> None:
        if self._top_strip is not None:
            self._top_strip.set_status(status=status, detail=detail, monitoring_active=monitoring_active)
