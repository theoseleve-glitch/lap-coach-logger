"""Compact always-on-top telemetry overlay."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from lap_coach_logger.core.live_dashboard import LiveCornerTracker
from lap_coach_logger.ui.desktop.panels import (
    FrictionCircleWidget,
    MiniTrackMapWidget,
    TelemetryTraceWidget,
)
from lap_coach_logger.ui.desktop.service import DesktopService
from lap_coach_logger.ui.desktop.theme import (
    ACID_GREEN,
    ASPHALT,
    CHALK,
    CONCRETE,
    MARSHAL_YELLOW,
    PIT_ORANGE,
    RACING_PURPLE,
    SAFETY_RED,
    STEEL,
)

_STATUS_COLORS = {
    "Idle": STEEL,
    "Simulator Detected": PIT_ORANGE,
    "Waiting": PIT_ORANGE,
    "Arming": MARSHAL_YELLOW,
    "Recording": ACID_GREEN,
    "Finalizing": MARSHAL_YELLOW,
    "Ready for Review": PIT_ORANGE,
    "Failed": SAFETY_RED,
    "Error": SAFETY_RED,
}


class OverlayPanel(QFrame):
    """Small, graph-first live telemetry surface for on-top use."""

    hide_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        show_hide_button: bool = True,
        kicker_text: str = "LIVE TELEMETRY OVERLAY",
    ) -> None:
        super().__init__(parent)
        self._show_hide_button = show_hide_button
        self._kicker_text = kicker_text
        self._live_session_uid: str | None = None
        self._last_sample_token: tuple[object, ...] | None = None
        self._last_status_key: tuple[object, ...] | None = None
        self._corner_tracker = LiveCornerTracker()
        self._corner_rows: dict[str, dict[str, QLabel]] = {}
        self._build()

    def _build(self) -> None:
        self.setObjectName("OverlaySurface")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(
            f"""
            QFrame#OverlaySurface {{
                background-color: rgba(20, 20, 20, 220);
                border: 1px solid rgba(240, 237, 229, 34);
                border-radius: 14px;
            }}
            QLabel#OverlayKicker {{
                color: {PIT_ORANGE};
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.8px;
            }}
            QLabel#OverlayStatus {{
                color: {CHALK};
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 1.6px;
                font-family: 'Consolas', 'Space Mono', monospace;
            }}
            QLabel#OverlayMetricLabel {{
                color: {STEEL};
                font-size: 9px;
                font-weight: 600;
                letter-spacing: 1.3px;
            }}
            QLabel#OverlayMetricValue {{
                color: {CHALK};
                font-size: 24px;
                font-weight: 800;
                font-family: 'Consolas', 'Space Mono', monospace;
            }}
            QLabel#OverlayTableHead {{
                color: {STEEL};
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 1.1px;
            }}
            QLabel#OverlayTableCell {{
                color: {CHALK};
                font-size: 11px;
                font-weight: 600;
                font-family: 'Consolas', 'Space Mono', monospace;
            }}
            QPushButton#OverlayButton {{
                background-color: rgba(240, 237, 229, 16);
                border: 1px solid rgba(240, 237, 229, 22);
                border-radius: 8px;
                padding: 6px 10px;
                color: {CHALK};
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.2px;
            }}
            QPushButton#OverlayButton:hover {{
                background-color: rgba(240, 237, 229, 26);
            }}
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        header_left = QVBoxLayout()
        header_left.setSpacing(2)
        kicker = QLabel(self._kicker_text)
        kicker.setObjectName("OverlayKicker")
        self._status_value = QLabel("IDLE")
        self._status_value.setObjectName("OverlayStatus")
        header_left.addWidget(kicker)
        header_left.addWidget(self._status_value)
        header.addLayout(header_left)
        header.addStretch(1)

        metrics = QHBoxLayout()
        metrics.setSpacing(16)
        self._metric_values: dict[str, QLabel] = {}
        for key, label in (("Speed", "SPEED"), ("Gear", "GEAR"), ("RPM", "RPM")):
            block = QVBoxLayout()
            block.setSpacing(0)
            label_widget = QLabel(label)
            label_widget.setObjectName("OverlayMetricLabel")
            value_widget = QLabel("-")
            value_widget.setObjectName("OverlayMetricValue")
            block.addWidget(label_widget)
            block.addWidget(value_widget)
            metrics.addLayout(block)
            self._metric_values[key] = value_widget
        header.addLayout(metrics)

        self._hide_button: QPushButton | None = None
        if self._show_hide_button:
            self._hide_button = QPushButton("HIDE")
            self._hide_button.setObjectName("OverlayButton")
            self._hide_button.clicked.connect(self.hide_requested.emit)
            header.addWidget(self._hide_button)
        root.addLayout(header)

        body = QGridLayout()
        body.setHorizontalSpacing(10)
        body.setVerticalSpacing(8)

        self._traces: dict[str, TelemetryTraceWidget] = {
            "speed": TelemetryTraceWidget(series_colors=(ACID_GREEN,), min_value=0.0, max_value=340.0, max_points=180),
            "pedals": TelemetryTraceWidget(series_colors=(PIT_ORANGE, SAFETY_RED), min_value=0.0, max_value=1.0, max_points=180),
            "steering": TelemetryTraceWidget(series_colors=(MARSHAL_YELLOW,), min_value=-540.0, max_value=540.0, max_points=180),
            "rpm": TelemetryTraceWidget(series_colors=("#6CC0FF",), min_value=0.0, max_value=12000.0, max_points=180),
            "g": TelemetryTraceWidget(series_colors=(RACING_PURPLE, "#F97316"), min_value=-3.0, max_value=3.0, max_points=180),
        }
        for trace in self._traces.values():
            trace.setMinimumHeight(54)
            trace.setMaximumHeight(54)

        trace_col = QVBoxLayout()
        trace_col.setSpacing(6)
        for label, key in (
            ("SPEED", "speed"),
            ("THROTTLE / BRAKE", "pedals"),
            ("STEERING", "steering"),
            ("RPM", "rpm"),
            ("LONG G / LAT G", "g"),
        ):
            row = QHBoxLayout()
            row.setSpacing(8)
            row_label = QLabel(label)
            row_label.setObjectName("OverlayMetricLabel")
            row_label.setFixedWidth(108)
            row.addWidget(row_label)
            row.addWidget(self._traces[key], 1)
            trace_col.addLayout(row)
        body.addLayout(trace_col, 0, 0, 2, 2)

        self._friction_circle = FrictionCircleWidget(max_points=90)
        self._friction_circle.setMinimumSize(160, 160)
        body.addWidget(self._friction_circle, 0, 2)

        self._track_map = MiniTrackMapWidget(max_points=2400)
        self._track_map.setMinimumHeight(160)
        body.addWidget(self._track_map, 1, 2)
        root.addLayout(body)

        self._corner_grid = QGridLayout()
        self._corner_grid.setHorizontalSpacing(8)
        self._corner_grid.setVerticalSpacing(4)
        root.addLayout(self._corner_grid)
        self._rebuild_corner_rows([])

    def apply_snapshot(self, payload: dict[str, object]) -> None:
        live = payload.get("live")
        live = live if isinstance(live, dict) else {}
        status = str(payload.get("status") or "Idle")
        monitoring = bool(payload.get("is_monitoring"))
        sim = str(payload.get("sim") or live.get("sim_name") or live.get("track_name") or "-")
        status_key = (status, monitoring, sim)
        if status_key != self._last_status_key:
            status_text = "PAUSED" if not monitoring else status.upper()
            status_color = _STATUS_COLORS.get(status, STEEL)
            self._status_value.setText(f"{status_text}  •  {sim}")
            self._status_value.setStyleSheet(
                f"color: {status_color}; font-size: 12px; font-weight: 800; "
                "letter-spacing: 1.6px; font-family: 'Consolas', 'Space Mono', monospace;"
            )
            self._last_status_key = status_key

        session_uid = str(live.get("session_uid") or "") or None
        if session_uid != self._live_session_uid:
            self._reset_live_state(session_uid)

        sample_token = _sample_token(live)
        if sample_token is None or sample_token == self._last_sample_token:
            return

        self._metric_values["Speed"].setText(_format_whole(live.get("speed_kph")))
        self._metric_values["Gear"].setText(_format_gear(live.get("gear")))
        self._metric_values["RPM"].setText(_format_whole(live.get("rpm")))

        self._traces["speed"].push(_as_float(live.get("speed_kph")))
        self._traces["pedals"].push(_as_float(live.get("throttle_pct")), _as_float(live.get("brake_pct")))
        self._traces["steering"].push(_as_float(live.get("steering_deg")))
        self._traces["rpm"].push(_as_float(live.get("rpm")))
        self._traces["g"].push(_as_float(live.get("long_accel_g")), _as_float(live.get("lat_accel_g")))

        self._friction_circle.push(_as_float(live.get("lat_accel_g")), _as_float(live.get("long_accel_g")))
        track_y = _as_float(live.get("world_pos_z"))
        if track_y is None:
            track_y = _as_float(live.get("world_pos_y"))
        self._track_map.push(_as_float(live.get("world_pos_x")), track_y)

        self._corner_tracker.push_snapshot(live)
        self._sync_corner_rows()
        self._last_sample_token = sample_token

    def _reset_live_state(self, session_uid: str | None) -> None:
        self._live_session_uid = session_uid
        self._last_sample_token = None
        self._corner_tracker.reset(session_uid)
        for widget in self._traces.values():
            widget.clear()
        self._friction_circle.clear()
        self._track_map.clear()
        self._metric_values["Speed"].setText("-")
        self._metric_values["Gear"].setText("-")
        self._metric_values["RPM"].setText("-")
        self._rebuild_corner_rows([])

    def _sync_corner_rows(self) -> None:
        rows = self._corner_tracker.rows()
        row_names = [str(row.get("corner") or "-") for row in rows]
        if row_names != list(self._corner_rows.keys()):
            self._rebuild_corner_rows(row_names)
        for row in rows:
            name = str(row.get("corner") or "-")
            cells = self._corner_rows.get(name)
            if not cells:
                continue
            cells["last"].setText(_format_lap_time(row.get("last_time_s")))
            cells["best"].setText(_format_lap_time(row.get("best_time_s")))
            cells["apex"].setText(_format_whole(row.get("apex_speed_kph"), suffix="k"))
            cells["g"].setText(_format_number(row.get("peak_lat_g"), suffix="g"))

    def _rebuild_corner_rows(self, row_names: list[str]) -> None:
        while self._corner_grid.count():
            item = self._corner_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        headers = ("CORNER", "LAST", "BEST", "APEX", "PEAK G")
        for col, heading in enumerate(headers):
            label = QLabel(heading)
            label.setObjectName("OverlayTableHead")
            alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            if col > 0:
                alignment = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            label.setAlignment(alignment)
            self._corner_grid.addWidget(label, 0, col)

        self._corner_rows = {}
        for row_index, name in enumerate(row_names, start=1):
            name_label = QLabel(name)
            name_label.setObjectName("OverlayTableCell")
            last = QLabel("-")
            best = QLabel("-")
            apex = QLabel("-")
            peak_g = QLabel("-")
            for widget in (last, best, apex, peak_g):
                widget.setObjectName("OverlayTableCell")
                widget.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._corner_grid.addWidget(name_label, row_index, 0)
            self._corner_grid.addWidget(last, row_index, 1)
            self._corner_grid.addWidget(best, row_index, 2)
            self._corner_grid.addWidget(apex, row_index, 3)
            self._corner_grid.addWidget(peak_g, row_index, 4)
            self._corner_rows[name] = {
                "name": name_label,
                "last": last,
                "best": best,
                "apex": apex,
                "g": peak_g,
            }


class OverlayWorkspacePanel(QWidget):
    """Sidebar workspace for managing and previewing the floating overlay."""

    toggle_overlay_requested = Signal()
    settings_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: dict[str, QLabel] = {}
        self._build()

    def _build(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        root = QVBoxLayout(inner)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        summary = self._card("Overlay", heading="Floating Workspace")
        summary_layout = summary.layout()

        self._rows["Window"] = self._add_metric_row(summary_layout, "Window")
        self._rows["Pin Mode"] = self._add_metric_row(summary_layout, "Pin Mode")
        self._rows["Refresh"] = self._add_metric_row(summary_layout, "Refresh")
        self._rows["Opacity"] = self._add_metric_row(summary_layout, "Opacity")
        self._rows["Startup"] = self._add_metric_row(summary_layout, "Startup")
        self._rows["Resource Mode"] = self._add_metric_row(summary_layout, "Resource Mode")

        summary_layout.addWidget(self._separator())
        self._summary_note = QLabel(
            "Use this page to manage the floating overlay while keeping a live preview inside the shell."
        )
        self._summary_note.setWordWrap(True)
        self._summary_note.setStyleSheet(f"font-size:13px; font-weight:600; color:{CHALK};")
        summary_layout.addWidget(self._summary_note)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.btn_toggle_overlay = QPushButton("SHOW OVERLAY")
        self.btn_toggle_overlay.setObjectName("PrimaryButton")
        self.btn_overlay_settings = QPushButton("OVERLAY SETTINGS")
        actions.addWidget(self.btn_toggle_overlay)
        actions.addWidget(self.btn_overlay_settings)
        actions.addStretch(1)
        summary_layout.addLayout(actions)
        root.addWidget(summary)

        preview = self._card("Preview", heading="Overlay Surface")
        preview_layout = preview.layout()
        self._preview = OverlayPanel(show_hide_button=False, kicker_text="OVERLAY PREVIEW")
        preview_layout.addWidget(self._preview)
        root.addWidget(preview)

        root.addStretch(1)
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self.btn_toggle_overlay.clicked.connect(self.toggle_overlay_requested.emit)
        self.btn_overlay_settings.clicked.connect(self.settings_requested.emit)

    def update_overlay_state(
        self,
        *,
        snapshot: dict[str, object],
        settings: dict[str, object],
        overlay_visible: bool,
    ) -> None:
        pin_mode = str(settings.get("overlay_pin_mode") or "overlay_on_top")
        pin_mode_text = {
            "overlay_on_top": "Overlay on top",
            "dashboard_on_top": "Main window on top",
            "floating": "Floating windows",
        }.get(pin_mode, "Overlay on top")

        refresh_rate_hz = int(settings.get("overlay_refresh_rate_hz") or 60)
        if bool(settings.get("low_resource_mode")):
            refresh_text = f"{min(refresh_rate_hz, 30)} Hz effective (capped by low-resource mode)"
        else:
            refresh_text = f"{refresh_rate_hz} Hz target"

        opacity = float(settings.get("overlay_opacity") or 0.92)
        startup_enabled = bool(settings.get("overlay_enabled"))
        monitoring = bool(snapshot.get("is_monitoring"))

        self._rows["Window"].setText("VISIBLE" if overlay_visible else "HIDDEN")
        self._rows["Pin Mode"].setText(pin_mode_text)
        self._rows["Refresh"].setText(refresh_text)
        self._rows["Opacity"].setText(f"{round(opacity * 100):.0f}%")
        self._rows["Startup"].setText("SHOW ON STARTUP" if startup_enabled else "MANUAL")
        self._rows["Resource Mode"].setText("LOW RESOURCE" if bool(settings.get("low_resource_mode")) else "FULL RATE")

        if overlay_visible:
            self.btn_toggle_overlay.setText("HIDE OVERLAY")
            self.btn_toggle_overlay.setObjectName("DangerButton")
            self.btn_toggle_overlay.style().unpolish(self.btn_toggle_overlay)
            self.btn_toggle_overlay.style().polish(self.btn_toggle_overlay)
        else:
            self.btn_toggle_overlay.setText("SHOW OVERLAY")
            self.btn_toggle_overlay.setObjectName("PrimaryButton")
            self.btn_toggle_overlay.style().unpolish(self.btn_toggle_overlay)
            self.btn_toggle_overlay.style().polish(self.btn_toggle_overlay)

        live = snapshot.get("live")
        live = live if isinstance(live, dict) else {}
        sim = str(snapshot.get("sim") or live.get("sim_name") or "No simulator")
        detail = "Monitoring is armed." if monitoring else "Monitoring is paused."
        self._summary_note.setText(
            f"{sim} preview mirrors the floating overlay. {detail} Use the button above to show or hide the detached window."
        )
        self._preview.apply_snapshot(snapshot)

    @staticmethod
    def _card(section_title: str, *, heading: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        section = QLabel(section_title.upper())
        section.setObjectName("SectionTitle")
        heading_label = QLabel(heading)
        heading_label.setObjectName("CardHeading")
        layout.addWidget(section)
        layout.addWidget(heading_label)
        return frame

    @staticmethod
    def _separator() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: rgba(240, 237, 229, 0.06);")
        line.setFixedHeight(1)
        return line

    @staticmethod
    def _add_metric_row(layout: QVBoxLayout, label_text: str) -> QLabel:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        label = QLabel(label_text.upper())
        label.setObjectName("MetricLabel")
        value = QLabel("-")
        value.setStyleSheet(f"font-size:13px; font-weight:600; color:{CHALK};")
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(value)
        layout.addLayout(row)
        return value


class TelemetryOverlayWindow(QWidget):
    """Frameless always-on-top overlay that polls live telemetry at 60 Hz."""

    visibility_changed = Signal(bool)

    def __init__(self, *, service: DesktopService) -> None:
        super().__init__(None)
        self._service = service
        self._drag_offset: QPoint | None = None
        self._has_position = False

        self.setWindowTitle("Lap Coach Overlay")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self._panel = OverlayPanel()
        self._panel.hide_requested.connect(self.hide_overlay)
        root.addWidget(self._panel)

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)

        self.resize(960, 620)

    def apply_settings(self, settings: dict[str, object]) -> None:
        refresh_rate_hz = int(settings.get("overlay_refresh_rate_hz") or 60)
        refresh_rate_hz = max(15, min(120, refresh_rate_hz))
        if bool(settings.get("low_resource_mode")):
            refresh_rate_hz = min(refresh_rate_hz, 30)
        self._timer.setInterval(max(8, round(1000 / refresh_rate_hz)))
        opacity = float(settings.get("overlay_opacity") or 0.92)
        self.setWindowOpacity(max(0.3, min(1.0, opacity)))
        self._apply_pin_mode(str(settings.get("overlay_pin_mode") or "overlay_on_top"))

    def sync_from_settings(self, settings: dict[str, object]) -> None:
        self.apply_settings(settings)
        if bool(settings.get("overlay_enabled")):
            self.show_overlay()
        else:
            self.hide_overlay()

    def show_overlay(self) -> None:
        if not self._has_position:
            self._position_default()
        self.show()
        self.raise_()
        self._timer.start()
        self.visibility_changed.emit(True)

    def hide_overlay(self) -> None:
        if self.isVisible():
            self.hide()
        self._timer.stop()
        self.visibility_changed.emit(False)

    def toggle_visible(self) -> None:
        if self.isVisible():
            self.hide_overlay()
        else:
            self.show_overlay()

    def _apply_pin_mode(self, pin_mode: str) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if pin_mode == "overlay_on_top":
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, pin_mode == "overlay_on_top")
        if self.isVisible():
            self.show()

    def _position_default(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        self.move(
            available.right() - self.width() - 36,
            available.top() + 36,
        )
        self._has_position = True

    def _tick(self) -> None:
        if not self.isVisible():
            return
        self._panel.apply_snapshot(self._service.overlay_snapshot())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            self._has_position = True
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)


def _as_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _format_whole(value: object, *, suffix: str = "") -> str:
    if not isinstance(value, (int, float)):
        return "-"
    return f"{float(value):.0f}{suffix}"


def _format_number(value: object, *, suffix: str = "") -> str:
    if not isinstance(value, (int, float)):
        return "-"
    return f"{float(value):.2f}{suffix}"


def _format_lap_time(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "-"
    return f"{float(value):.3f}s"


def _format_gear(value: object) -> str:
    if not isinstance(value, int):
        return "-"
    if value < 0:
        return "R"
    if value == 0:
        return "N"
    return str(value)


def _sample_token(snapshot: dict[str, object]) -> tuple[object, ...] | None:
    timestamp_utc = snapshot.get("timestamp_utc")
    if isinstance(timestamp_utc, str) and timestamp_utc:
        return ("timestamp", timestamp_utc)
    lap_number = snapshot.get("lap_number")
    session_time_s = _as_float(snapshot.get("session_time_s"))
    lap_dist_pct = _as_float(snapshot.get("lap_dist_pct"))
    if lap_number is None and session_time_s is None and lap_dist_pct is None:
        return None
    return (
        "fallback",
        lap_number,
        round(session_time_s, 3) if session_time_s is not None else None,
        round(lap_dist_pct, 4) if lap_dist_pct is not None else None,
    )
