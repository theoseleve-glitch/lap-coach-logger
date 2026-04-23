"""Immersive dashboard workspace."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from lap_coach_logger.ui.desktop.panels import DashboardPanel as _LegacyDashboardPanel
from lap_coach_logger.ui.desktop.panels import _ACID_GREEN, _CHALK, _PIT_ORANGE, _SAFETY_RED, _STEEL
from lap_coach_logger.ui.desktop.panels import _add_metric_row, _metric_label, _metric_value, _separator
from lap_coach_logger.ui.desktop.workspaces.common import (
    ScenicArtworkWidget,
    WorkspacePanel,
    WorkspaceSectionTabs,
    WorkspaceShellCallbacks,
    WorkspaceTopStrip,
    wire_shell_callbacks,
    workspace_page_styles,
)
from lap_coach_logger.ui.desktop.workspaces.design_system import WorkspaceDesignTokens, default_workspace_tokens
from lap_coach_logger.ui.desktop.workspaces.telemetry_widgets import (
    FrictionCircleWidget,
    MiniTrackMapWidget,
    TelemetryTraceWidget,
)


class DashboardWorkspace(_LegacyDashboardPanel):
    """Sectioned immersive dashboard built on the legacy snapshot contract."""

    start_monitoring_requested = Signal()
    stop_monitoring_requested = Signal()
    toggle_overlay_requested = Signal()
    open_output_requested = Signal()
    open_logs_requested = Signal()
    open_config_requested = Signal()
    open_settings_requested = Signal()
    refresh_setup_requested = Signal()
    favorite_setup_requested = Signal()
    install_setup_requested = Signal()
    duplicate_setup_requested = Signal()
    rollback_setup_requested = Signal()
    save_setup_bundle_requested = Signal()
    refresh_operations_requested = Signal()
    toggle_raw_requested = Signal()
    save_profile_requested = Signal()
    apply_profile_requested = Signal()
    setup_diff_requested = Signal()

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
        self._section_tabs: WorkspaceSectionTabs | None = None
        self._section_stack: QStackedWidget | None = None
        self._operations_profile_ids: list[str] = []
        super().__init__(parent)

    def _build(self) -> None:
        self.setObjectName("DashboardWorkspacePage")

        root = QVBoxLayout(self)
        root.setContentsMargins(
            self._tokens.layout.shell_margin_px,
            self._tokens.layout.shell_margin_px,
            self._tokens.layout.shell_margin_px,
            self._tokens.layout.shell_margin_px,
        )
        root.setSpacing(self._tokens.spacing.md)

        self._top_strip = WorkspaceTopStrip(active_page="dashboard", tokens=self._tokens)
        wire_shell_callbacks(self._top_strip, self._shell_callbacks)
        root.addWidget(self._top_strip)

        self._section_tabs = WorkspaceSectionTabs(
            (("overview", "Overview"), ("engineering", "Engineering"), ("setup", "Setup")),
            current="overview",
            tokens=self._tokens,
        )
        self._section_tabs.section_requested.connect(self._switch_section)
        root.addWidget(self._section_tabs)

        self._section_stack = QStackedWidget()
        root.addWidget(self._section_stack, 1)
        self._section_stack.addWidget(self._make_scroll(self._build_overview_page()))
        self._section_stack.addWidget(self._make_scroll(self._build_engineering_page()))
        self._section_stack.addWidget(self._make_scroll(self._build_setup_page()))

        self.setStyleSheet(workspace_page_styles("DashboardWorkspacePage", tokens=self._tokens))

    def _make_scroll(self, content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        return scroll

    def _switch_section(self, section_id: str) -> None:
        mapping = {"overview": 0, "engineering": 1, "setup": 2}
        index = mapping.get(section_id, 0)
        if self._section_stack is not None:
            self._section_stack.setCurrentIndex(index)
        if self._section_tabs is not None:
            self._section_tabs.set_current(section_id)

    def _button(self, label: str, *, object_name: str | None = None):
        from PySide6.QtWidgets import QPushButton

        button = QPushButton(label)
        if object_name:
            button.setObjectName(object_name)
        return button

    def set_shell_status(self, *, status: str, detail: str, monitoring_active: bool) -> None:
        if self._top_strip is not None:
            self._top_strip.set_status(status=status, detail=detail, monitoring_active=monitoring_active)

    def set_overlay_toggle_label(self, label: str) -> None:
        self.btn_overlay.setText(str(label))

    def _build_overview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self._tokens.spacing.md)

        hero = WorkspacePanel("Dashboard", heading="System Status", variant="hero", tokens=self._tokens)
        layout.addWidget(hero)
        hero_row = QHBoxLayout()
        hero_row.setContentsMargins(0, 0, 0, 0)
        hero_row.setSpacing(self._tokens.layout.shell_gap_px)
        hero.content_layout.addLayout(hero_row)

        status_col = QVBoxLayout()
        status_col.setContentsMargins(0, 0, 0, 0)
        status_col.setSpacing(self._tokens.spacing.sm)
        hero_row.addLayout(status_col, 1)

        status_row = QHBoxLayout()
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"font-size: 18px; color: {_STEEL};")
        self._status_label = QLabel("IDLE")
        self._status_label.setStyleSheet(f"font-size: 16px; font-weight: 700; letter-spacing: 2px; color: {_STEEL};")
        status_row.addWidget(self._status_dot)
        status_row.addWidget(self._status_label)
        status_row.addStretch(1)
        status_col.addLayout(status_row)

        self._status_detail = QLabel("Waiting for simulator")
        self._status_detail.setStyleSheet(f"color: {_STEEL}; font-size: 12px;")
        status_col.addWidget(self._status_detail)
        status_col.addWidget(_separator())

        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(26)
        for label_text in ("SAMPLES", "ELAPSED", "SIM"):
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(_metric_label(label_text))
            value = _metric_value()
            col.addWidget(value)
            metrics_row.addLayout(col)
            if label_text == "SAMPLES":
                self._hero_samples = value
            elif label_text == "ELAPSED":
                self._hero_elapsed = value
            else:
                self._hero_sim = value
        metrics_row.addStretch(1)
        status_col.addLayout(metrics_row)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.btn_start = self._button("RESUME MONITORING", object_name="PrimaryButton")
        self.btn_stop = self._button("PAUSE MONITORING", object_name="DangerButton")
        self.btn_overlay = self._button("OVERLAY")
        self.btn_output = self._button("OUTPUT")
        self.btn_logs = self._button("LOGS")
        self.btn_config = self._button("CONFIG")
        self.btn_settings = self._button("SETTINGS")
        for button in (
            self.btn_start,
            self.btn_stop,
            self.btn_overlay,
            self.btn_output,
            self.btn_logs,
            self.btn_config,
            self.btn_settings,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        status_col.addLayout(actions)

        scenic = ScenicArtworkWidget(tokens=self._tokens, compact=False)
        scenic.setMinimumHeight(280)
        hero_row.addWidget(scenic, 1)

        headline = QHBoxLayout()
        headline.setSpacing(18)
        self._headline_rows: dict[str, QLabel] = {}
        for key, label in (("Speed", "SPEED"), ("Gear", "GEAR"), ("RPM", "RPM")):
            col = QVBoxLayout()
            col.setSpacing(3)
            col.addWidget(_metric_label(label))
            value = _metric_value("—")
            value.setStyleSheet(f"font-size: 28px; font-weight: 800; color: {_CHALK};")
            col.addWidget(value)
            headline.addLayout(col)
            self._headline_rows[key] = value
        headline.addStretch(1)
        hero.content_layout.addLayout(headline)

        live_panel = WorkspacePanel("Live Session", heading="Current Run", variant="panel", tokens=self._tokens)
        layout.addWidget(live_panel)
        live_layout = live_panel.content_layout
        live_grid = QGridLayout()
        live_grid.setHorizontalSpacing(12)
        live_grid.setVerticalSpacing(12)
        live_layout.addLayout(live_grid)

        summary_panel = WorkspacePanel("Summary", heading="Telemetry", variant="inspect", tokens=self._tokens)
        live_grid.addWidget(summary_panel, 0, 0)
        summary_layout = summary_panel.content_layout
        self._live_rows: dict[str, QLabel] = {}
        for key in ("Track", "Car", "Lap", "Session", "Flag", "Throttle", "Brake", "Steering"):
            self._live_rows[key] = _add_metric_row(summary_layout, key)

        traces_panel = WorkspacePanel("Graphs", heading="Signal Traces", variant="inspect", tokens=self._tokens)
        live_grid.addWidget(traces_panel, 0, 1, 2, 2)
        traces_layout = traces_panel.content_layout
        self._graph_traces: dict[str, TelemetryTraceWidget] = {
            "speed": TelemetryTraceWidget(series_colors=(_ACID_GREEN,), min_value=0.0, max_value=340.0),
            "pedals": TelemetryTraceWidget(series_colors=(_PIT_ORANGE, _SAFETY_RED), min_value=0.0, max_value=1.0),
            "steering": TelemetryTraceWidget(series_colors=("#F5BE4B",), min_value=-540.0, max_value=540.0),
            "rpm": TelemetryTraceWidget(series_colors=("#7AA3C8",), min_value=0.0, max_value=12000.0),
            "g": TelemetryTraceWidget(series_colors=("#8B5CF6", "#F97316"), min_value=-3.0, max_value=3.0),
        }
        trace_grid = QGridLayout()
        trace_grid.setHorizontalSpacing(10)
        trace_grid.setVerticalSpacing(8)
        for row, (label, widget) in enumerate(
            (
                ("SPEED TRACE", self._graph_traces["speed"]),
                ("THROTTLE / BRAKE", self._graph_traces["pedals"]),
                ("STEERING ANGLE", self._graph_traces["steering"]),
                ("RPM TRACE", self._graph_traces["rpm"]),
                ("LONG G / LAT G", self._graph_traces["g"]),
            )
        ):
            lbl = _metric_label(label)
            lbl.setMinimumWidth(128)
            trace_grid.addWidget(lbl, row, 0)
            trace_grid.addWidget(widget, row, 1)
        traces_layout.addLayout(trace_grid)

        timing_panel = WorkspacePanel("Timing", heading="Lap Feed", variant="inspect", tokens=self._tokens)
        live_grid.addWidget(timing_panel, 1, 0)
        self._timing_rows = {}
        for key in ("Lap Time", "Live Delta", "Best Lap", "Sector 1", "Sector 2", "Sector 3"):
            self._timing_rows[key] = _add_metric_row(timing_panel.content_layout, key)

        support_grid = QGridLayout()
        support_grid.setHorizontalSpacing(12)
        support_grid.setVerticalSpacing(12)
        live_layout.addLayout(support_grid)

        fuel_panel = WorkspacePanel("Fuel", heading="Run Plan", variant="inspect", tokens=self._tokens)
        self._fuel_rows = {}
        for key in ("Fuel Level", "Fuel / Lap", "Laps Left"):
            self._fuel_rows[key] = _add_metric_row(fuel_panel.content_layout, key)
        support_grid.addWidget(fuel_panel, 0, 0)

        electronics_panel = WorkspacePanel("Electronics", heading="Driver Aids", variant="inspect", tokens=self._tokens)
        self._electronics_rows = {}
        for key in ("TC", "ABS", "Map", "Brake Bias"):
            self._electronics_rows[key] = _add_metric_row(electronics_panel.content_layout, key)
        support_grid.addWidget(electronics_panel, 0, 1)

        alerts_panel = WorkspacePanel("Live Alerts", heading="Risk Flags", variant="inspect", tokens=self._tokens)
        self._alerts_label = QLabel("No active alerts.")
        self._alerts_label.setWordWrap(True)
        self._alerts_label.setTextFormat(Qt.TextFormat.RichText)
        alerts_panel.content_layout.addWidget(self._alerts_label)
        support_grid.addWidget(alerts_panel, 0, 2)

        coaching_panel = WorkspacePanel("Live Coaching", heading="Corner Feedback", variant="inspect", tokens=self._tokens)
        self._coaching_label = QLabel("Complete a clean reference lap to unlock live coaching.")
        self._coaching_label.setWordWrap(True)
        self._coaching_label.setTextFormat(Qt.TextFormat.RichText)
        coaching_panel.content_layout.addWidget(self._coaching_label)
        support_grid.addWidget(coaching_panel, 1, 0, 1, 2)

        summary_panel = WorkspacePanel("Lap-End Summary", heading="Next Lap Focus", variant="inspect", tokens=self._tokens)
        self._summary_rows = {}
        for key in ("Biggest Loss", "Technique Issue", "Next Focus"):
            value = _add_metric_row(summary_panel.content_layout, key)
            value.setWordWrap(True)
            self._summary_rows[key] = value
        support_grid.addWidget(summary_panel, 1, 2)

        report_card = WorkspacePanel("Session Report", heading="Last Completed", variant="dock", tokens=self._tokens)
        layout.addWidget(report_card)
        self._report_rows = {}
        report_row = QGridLayout()
        report_row.setHorizontalSpacing(12)
        report_row.setVerticalSpacing(10)
        report_card.content_layout.addLayout(report_row)
        keys = (
            "Samples",
            "Duration",
            "Laps",
            "Clean Laps",
            "Best Clean",
            "Track",
            "Car",
            "Quality",
            "Sync",
            "File",
        )
        for index, key in enumerate(keys):
            card = WorkspacePanel(key, heading=key, variant="inspect", tokens=self._tokens)
            value = _metric_value("—", mono=False)
            card.content_layout.addWidget(value)
            self._report_rows[key] = value
            report_row.addWidget(card, index // 5, index % 5)
        self._report_card = report_card

        return page

    def _build_dashboard_corner_table(
        self, parent_layout: QVBoxLayout, *, columns: tuple[str, ...]
    ) -> dict[str, dict[str, QLabel]]:
        """Build a 4-corner (LF/RF/LR/RR) data table and return label refs."""
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        parent_layout.addLayout(grid)

        corners = ("LF", "RF", "LR", "RR")
        for col_idx, col_name in enumerate(columns, start=1):
            header = QLabel(col_name)
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(header, 0, col_idx)

        rows: dict[str, dict[str, QLabel]] = {}
        for row_idx, corner in enumerate(corners, start=1):
            corner_label = QLabel(corner)
            grid.addWidget(corner_label, row_idx, 0)
            rows[corner] = {}
            for col_idx, col_name in enumerate(columns, start=1):
                value = QLabel("--")
                value.setAlignment(Qt.AlignmentFlag.AlignCenter)
                grid.addWidget(value, row_idx, col_idx)
                rows[corner][col_name] = value
        return rows

    def _build_engineering_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self._tokens.spacing.md)

        dynamics = WorkspacePanel("Vehicle Dynamics", heading="Grip, Map, and Corners", variant="hero", tokens=self._tokens)
        layout.addWidget(dynamics)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        dynamics.content_layout.addLayout(grid)

        friction_card = WorkspacePanel("Grip Usage", heading="Friction Circle", variant="inspect", tokens=self._tokens)
        self._friction_circle = FrictionCircleWidget()
        friction_card.content_layout.addWidget(self._friction_circle)
        grid.addWidget(friction_card, 0, 0)

        map_card = WorkspacePanel("Track Map", heading="Auto-Generated", variant="inspect", tokens=self._tokens)
        self._track_map = MiniTrackMapWidget()
        map_card.content_layout.addWidget(self._track_map)
        grid.addWidget(map_card, 0, 1)

        corner_card = WorkspacePanel("Corner Table", heading="Live After Lap 1", variant="inspect", tokens=self._tokens)
        self._corner_table = QTableWidget(0, 5)
        self._corner_table.setHorizontalHeaderLabels(["CORNER", "LAST", "BEST", "APEX", "PEAK G"])
        self._corner_table.verticalHeader().setVisible(False)
        self._corner_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._corner_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._corner_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._corner_table.setMinimumHeight(220)
        corner_card.content_layout.addWidget(self._corner_table)
        grid.addWidget(corner_card, 1, 0, 1, 2)

        tyres_brakes = QGridLayout()
        tyres_brakes.setHorizontalSpacing(12)
        tyres_brakes.setVerticalSpacing(12)
        layout.addLayout(tyres_brakes)

        tyre_card = WorkspacePanel("Tyres", heading="Temps / Pressures / Wear", variant="panel", tokens=self._tokens)
        self._tyre_rows = self._build_dashboard_corner_table(tyre_card.content_layout, columns=("Temp", "Press", "Wear"))
        tyres_brakes.addWidget(tyre_card, 0, 0)

        brake_card = WorkspacePanel("Brakes", heading="Brake Temperatures", variant="panel", tokens=self._tokens)
        self._brake_rows = self._build_dashboard_corner_table(brake_card.content_layout, columns=("Temp",))
        tyres_brakes.addWidget(brake_card, 0, 1)

        hardware_card = WorkspacePanel("Hardware / Input / FFB", heading="Control Diagnostics", variant="panel", tokens=self._tokens)
        layout.addWidget(hardware_card)
        hardware_grid = QGridLayout()
        hardware_grid.setHorizontalSpacing(12)
        hardware_grid.setVerticalSpacing(12)
        hardware_card.content_layout.addLayout(hardware_grid)

        pedal_card = WorkspacePanel("Pedals", heading="Brake / Throttle", variant="inspect", tokens=self._tokens)
        self._hardware_input_rows = {}
        for key in ("Brake Trace", "Throttle Mod", "Pedal Overlap", "Deadzone"):
            value = _add_metric_row(pedal_card.content_layout, key)
            value.setWordWrap(True)
            self._hardware_input_rows[key] = value
        hardware_grid.addWidget(pedal_card, 0, 0)

        steering_card = WorkspacePanel("Steering / FFB", heading="Wheel Behavior", variant="inspect", tokens=self._tokens)
        self._hardware_steering_rows = {}
        for key in ("Steering Linearity", "Steering Saturation", "FFB Clipping", "Wheel Oscillation"):
            value = _add_metric_row(steering_card.content_layout, key)
            value.setWordWrap(True)
            self._hardware_steering_rows[key] = value
        hardware_grid.addWidget(steering_card, 0, 1)

        flags_card = WorkspacePanel("Flags", heading="Instability Warnings", variant="inspect", tokens=self._tokens)
        self._hardware_flags_label = QLabel("No hardware/input warnings.")
        self._hardware_flags_label.setWordWrap(True)
        self._hardware_flags_label.setTextFormat(Qt.TextFormat.RichText)
        flags_card.content_layout.addWidget(self._hardware_flags_label)
        hardware_grid.addWidget(flags_card, 0, 2)

        platform_card = WorkspacePanel("Ride Height / Balance / Platform", heading="Platform Analysis", variant="panel", tokens=self._tokens)
        layout.addWidget(platform_card)
        self._platform_rows = {}
        for key in (
            "Rake Trend",
            "Compression / Bottoming",
            "Chassis Balance",
            "Front vs Rear",
            "Roll Asymmetry",
            "Aero Balance",
        ):
            value = _add_metric_row(platform_card.content_layout, key)
            value.setWordWrap(True)
            self._platform_rows[key] = value
        platform_card.content_layout.addWidget(_separator())
        self._platform_flags_label = QLabel("No platform warnings.")
        self._platform_flags_label.setWordWrap(True)
        self._platform_flags_label.setTextFormat(Qt.TextFormat.RichText)
        platform_card.content_layout.addWidget(self._platform_flags_label)

        return page

    def _build_setup_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self._tokens.spacing.md)

        operations_card = WorkspacePanel("Local Runtime", heading="Operations & Profiles", variant="panel", tokens=self._tokens)
        layout.addWidget(operations_card)
        self._operations_rows = {}
        for key in (
            "Autodetect",
            "Auto-Start With Sim",
            "Pin Mode",
            "Profiles",
            "Safe Update",
            "Crash Recovery",
            "Low-Resource Mode",
            "Raw Recorder",
        ):
            value = _add_metric_row(operations_card.content_layout, key)
            value.setWordWrap(True)
            self._operations_rows[key] = value
        operations_card.content_layout.addWidget(_separator())
        self._operations_feature_label = QLabel("No capability summary yet.")
        self._operations_feature_label.setWordWrap(True)
        self._operations_feature_label.setTextFormat(Qt.TextFormat.RichText)
        operations_card.content_layout.addWidget(self._operations_feature_label)
        operations_card.content_layout.addWidget(_separator())

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(8)
        operations_card.content_layout.addLayout(controls)
        self.btn_ops_refresh = self._button("REFRESH OPS")
        self.btn_ops_toggle_raw = self._button("TOGGLE RAW")
        self.btn_ops_save_profile = self._button("SAVE PROFILE")
        self.btn_ops_apply_profile = self._button("APPLY PROFILE")
        self.ops_profile_scope = QComboBox()
        self.ops_profile_scope.addItem("SIM", "sim")
        self.ops_profile_scope.addItem("CAR", "car")
        self.ops_profile_scope.addItem("DRIVER", "driver")
        self.ops_profile_name = QLineEdit()
        self.ops_profile_name.setPlaceholderText("Profile name")
        self.ops_profile_select = QComboBox()
        self.ops_profile_select.setMinimumWidth(280)
        for widget in (
            self.btn_ops_refresh,
            self.btn_ops_toggle_raw,
            self.btn_ops_save_profile,
            self.btn_ops_apply_profile,
            self.ops_profile_scope,
            self.ops_profile_name,
            self.ops_profile_select,
        ):
            controls.addWidget(widget)
        controls.addStretch(1)

        setup_card = WorkspacePanel("Local Library", heading="Setup Tools", variant="hero", tokens=self._tokens)
        layout.addWidget(setup_card)
        self._setup_rows = {}
        for key in ("Sim", "Current", "Folder"):
            value = _add_metric_row(setup_card.content_layout, key)
            value.setWordWrap(True)
            self._setup_rows[key] = value

        setup_buttons = QHBoxLayout()
        setup_buttons.setContentsMargins(0, 0, 0, 0)
        setup_buttons.setSpacing(8)
        setup_card.content_layout.addLayout(setup_buttons)
        self.btn_setup_refresh = self._button("REFRESH SETUPS")
        self.btn_setup_favorite = self._button("FAVORITE")
        self.btn_setup_install = self._button("INSTALL FILE")
        self.btn_setup_duplicate = self._button("DUPLICATE")
        self.btn_setup_rollback = self._button("ROLLBACK")
        self.btn_setup_bundle = self._button("SAVE + LAP")
        self.setup_duplicate_name = QLineEdit()
        self.setup_duplicate_name.setPlaceholderText("Duplicate name")
        self.setup_duplicate_name.setMinimumWidth(180)
        for widget in (
            self.btn_setup_refresh,
            self.btn_setup_favorite,
            self.btn_setup_install,
            self.btn_setup_duplicate,
            self.btn_setup_rollback,
            self.btn_setup_bundle,
            self.setup_duplicate_name,
        ):
            setup_buttons.addWidget(widget)
        setup_buttons.addStretch(1)
        setup_card.content_layout.addWidget(_separator())

        setup_grid = QGridLayout()
        setup_grid.setHorizontalSpacing(12)
        setup_grid.setVerticalSpacing(12)
        setup_card.content_layout.addLayout(setup_grid)

        library_card = WorkspacePanel("Library", heading="Native Setup Files", variant="inspect", tokens=self._tokens)
        self._setup_table = QTableWidget(0, 7)
        self._setup_table.setHorizontalHeaderLabels(["FAV", "LIVE", "NAME", "CAR", "TRACK", "MODIFIED", "FORMAT"])
        self._setup_table.verticalHeader().setVisible(False)
        self._setup_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._setup_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._setup_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._setup_table.setWordWrap(False)
        self._setup_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._setup_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for column in (2, 3, 4):
            self._setup_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        self._setup_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._setup_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self._setup_table.setMinimumHeight(220)
        library_card.content_layout.addWidget(self._setup_table)
        setup_grid.addWidget(library_card, 0, 0, 1, 2)

        current_setup_card = WorkspacePanel("Current Setup", heading="Structured Snapshot", variant="inspect", tokens=self._tokens)
        self._setup_current_table = QTableWidget(0, 2)
        self._setup_current_table.setHorizontalHeaderLabels(["SETTING", "VALUE"])
        self._setup_current_table.verticalHeader().setVisible(False)
        self._setup_current_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._setup_current_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._setup_current_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._setup_current_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        current_setup_card.content_layout.addWidget(self._setup_current_table)
        setup_grid.addWidget(current_setup_card, 0, 2)

        diff_card = WorkspacePanel("Setup Diff", heading="Changed Values Only", variant="inspect", tokens=self._tokens)
        diff_controls = QHBoxLayout()
        diff_controls.setContentsMargins(0, 0, 0, 0)
        diff_controls.setSpacing(8)
        diff_controls.addWidget(_metric_label("A"))
        self.setup_diff_a = QComboBox()
        diff_controls.addWidget(self.setup_diff_a, 1)
        diff_controls.addWidget(_metric_label("B"))
        self.setup_diff_b = QComboBox()
        diff_controls.addWidget(self.setup_diff_b, 1)
        diff_card.content_layout.addLayout(diff_controls)
        self._setup_diff_table = QTableWidget(0, 4)
        self._setup_diff_table.setHorizontalHeaderLabels(["SETTING", "A", "B", "LIKELY EFFECT"])
        self._setup_diff_table.verticalHeader().setVisible(False)
        self._setup_diff_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._setup_diff_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._setup_diff_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._setup_diff_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._setup_diff_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._setup_diff_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        diff_card.content_layout.addWidget(self._setup_diff_table)
        setup_grid.addWidget(diff_card, 1, 0, 1, 3)

        coach_card = WorkspacePanel("Setup Coach", heading="Latest Saved Bundle", variant="inspect", tokens=self._tokens)
        self._setup_coach_rows = {}
        for key in ("Status", "Bundle", "Issues"):
            value = _add_metric_row(coach_card.content_layout, key)
            value.setWordWrap(True)
            self._setup_coach_rows[key] = value
        self._setup_coach_table = QTableWidget(0, 6)
        self._setup_coach_table.setHorizontalHeaderLabels(["LEVER", "NOW", "SUGGESTED", "CONF", "WHY", "LIKELY EFFECT"])
        self._setup_coach_table.verticalHeader().setVisible(False)
        self._setup_coach_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._setup_coach_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._setup_coach_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._setup_coach_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._setup_coach_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._setup_coach_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._setup_coach_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._setup_coach_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        coach_card.content_layout.addWidget(self._setup_coach_table)
        self._setup_coach_notes = QLabel("No setup coach analysis yet.")
        self._setup_coach_notes.setWordWrap(True)
        self._setup_coach_notes.setTextFormat(Qt.TextFormat.RichText)
        coach_card.content_layout.addWidget(self._setup_coach_notes)
        setup_grid.addWidget(coach_card, 2, 0, 1, 3)

        self.btn_start.clicked.connect(self.start_monitoring_requested.emit)
        self.btn_stop.clicked.connect(self.stop_monitoring_requested.emit)
        self.btn_overlay.clicked.connect(self.toggle_overlay_requested.emit)
        self.btn_output.clicked.connect(self.open_output_requested.emit)
        self.btn_logs.clicked.connect(self.open_logs_requested.emit)
        self.btn_config.clicked.connect(self.open_config_requested.emit)
        self.btn_settings.clicked.connect(self.open_settings_requested.emit)
        self.btn_setup_refresh.clicked.connect(self.refresh_setup_requested.emit)
        self.btn_setup_favorite.clicked.connect(self.favorite_setup_requested.emit)
        self.btn_setup_install.clicked.connect(self.install_setup_requested.emit)
        self.btn_setup_duplicate.clicked.connect(self.duplicate_setup_requested.emit)
        self.btn_setup_rollback.clicked.connect(self.rollback_setup_requested.emit)
        self.btn_setup_bundle.clicked.connect(self.save_setup_bundle_requested.emit)
        self.btn_ops_refresh.clicked.connect(self.refresh_operations_requested.emit)
        self.btn_ops_toggle_raw.clicked.connect(self.toggle_raw_requested.emit)
        self.btn_ops_save_profile.clicked.connect(self.save_profile_requested.emit)
        self.btn_ops_apply_profile.clicked.connect(self.apply_profile_requested.emit)
        self.setup_diff_a.currentIndexChanged.connect(lambda _index: self.setup_diff_requested.emit())
        self.setup_diff_b.currentIndexChanged.connect(lambda _index: self.setup_diff_requested.emit())

        return page
