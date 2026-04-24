"""Legacy panel base classes and UI helpers.

Provides QWidget base classes for workspace panels and metric row helpers
used throughout the desktop UI.  Also re-exports telemetry widgets that
were originally defined here before being moved to workspaces/.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import html
import math
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from lap_coach_logger.ui.desktop.theme import (
    ACID_GREEN,
    CHALK,
    MARSHAL_YELLOW,
    PIT_ORANGE,
    SAFETY_RED,
    STEEL,
)
from lap_coach_logger.ui.desktop.workspaces.telemetry_widgets import (
    FrictionCircleWidget,
    MiniTrackMapWidget,
    TelemetryTraceWidget,
)
from lap_coach_logger.core.live_dashboard import LiveCornerTracker

# Private color aliases expected by workspace modules
_ACID_GREEN = ACID_GREEN
_CHALK = CHALK
_MARSHAL_YELLOW = MARSHAL_YELLOW
_PIT_ORANGE = PIT_ORANGE
_SAFETY_RED = SAFETY_RED
_STEEL = STEEL


# ---------------------------------------------------------------------------
# Legacy panel base classes
# ---------------------------------------------------------------------------

class DashboardPanel(QWidget):
    """Base class for the dashboard workspace."""

    def __init__(self, parent: QWidget | None = None, **kwargs: object) -> None:
        super().__init__(parent)
        self.setObjectName("DashboardWorkspacePage")


class LivePanel(QWidget):
    """Base class for the live tracking workspace."""

    def __init__(self, parent: QWidget | None = None, **kwargs: object) -> None:
        super().__init__(parent)
        self.setObjectName("LiveWorkspacePage")


class HistoryPanel(QWidget):
    """Base class for the session history workspace."""

    def __init__(self, parent: QWidget | None = None, **kwargs: object) -> None:
        super().__init__(parent)
        self.setObjectName("HistoryWorkspacePage")


class ReviewPanel(QWidget):
    """Base class for the session review workspace."""

    def __init__(self, parent: QWidget | None = None, **kwargs: object) -> None:
        super().__init__(parent)
        self.setObjectName("ReviewWorkspacePage")


class LogsPanel(QWidget):
    """Base class for the application logs workspace."""

    def __init__(self, parent: QWidget | None = None, **kwargs: object) -> None:
        super().__init__(parent)
        self.setObjectName("LogsWorkspacePage")


# ---------------------------------------------------------------------------
# Metric row helpers
# ---------------------------------------------------------------------------

def _metric_label(text: str = "") -> QLabel:
    """Create a styled label for metric names."""
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {STEEL}; font-size: 11px;")
    lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    return lbl


def _metric_value(text: str = "\u2014", *, mono: bool = True) -> QLabel:
    """Create a styled label for metric values."""
    lbl = QLabel(text)
    family = "Consolas, monospace" if mono else "Segoe UI"
    lbl.setStyleSheet(f"color: {CHALK}; font-size: 13px; font-family: {family};")
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return lbl


def _add_metric_row(layout: QVBoxLayout, label_text: str) -> QLabel:
    """Add a label + value row to a layout and return the value label."""
    row = QHBoxLayout()
    row.addWidget(_metric_label(label_text))
    value = _metric_value()
    row.addWidget(value)
    layout.addLayout(row)
    return value


def _separator() -> QFrame:
    """Create a horizontal line separator."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color: #222933;")
    line.setFixedHeight(1)
    return line


def _metric_row(label_text: str, value_text: str = "—") -> tuple[QLabel, QLabel]:
    """Return (label, value) pair laid out side-by-side in a row."""
    lbl = _metric_label(label_text)
    val = _metric_value(value_text)
    return lbl, val


def _add_metric_row(layout: QVBoxLayout, label_text: str, value_text: str = "—") -> QLabel:
    """Add a label + value row to layout and return the value widget."""
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    lbl = _metric_label(label_text)
    val = _metric_value(value_text)
    row.addWidget(lbl)
    row.addStretch(1)
    row.addWidget(val)
    layout.addLayout(row)
    return val


class TelemetrySparkline(QWidget):
    """Minimal, low-overhead sparkline chart for one telemetry channel."""

    def __init__(
        self,
        *,
        color: str,
        min_value: float,
        max_value: float,
        max_points: int = 180,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._series: deque[float | None] = deque(maxlen=max_points)
        self._min = min_value
        self._max = max_value
        self._line_color = QColor(color)
        self.setMinimumHeight(58)
        self.setMaximumHeight(58)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def push(self, value: float | None) -> None:
        if isinstance(value, (int, float)):
            self._series.append(float(value))
        else:
            self._series.append(None)
        self.update()

    def clear(self) -> None:
        self._series.clear()
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(2, 2, -2, -2)

        # Background and border
        painter.fillRect(rect, QColor(20, 20, 20, 220))
        painter.setPen(QPen(QColor(240, 237, 229, 30), 1.0))
        painter.drawRoundedRect(rect, 6, 6)

        if not self._series:
            painter.setPen(QPen(QColor(148, 148, 148), 1.0))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "NO DATA")
            return

        points = list(self._series)
        value_range = max(0.001, self._max - self._min)
        dx = rect.width() / max(1, len(points) - 1)

        path = QPainterPath()
        started = False
        for i, value in enumerate(points):
            if value is None:
                started = False
                continue
            x = rect.left() + i * dx
            norm = (float(value) - self._min) / value_range
            norm = max(0.0, min(1.0, norm))
            y = rect.bottom() - norm * rect.height()
            if not started:
                path.moveTo(x, y)
                started = True
            else:
                path.lineTo(x, y)

        painter.setPen(QPen(self._line_color, 1.6))
        painter.drawPath(path)


class TelemetryTraceWidget(QWidget):
    """Compact multi-series trace widget for live dashboard graphs."""

    def __init__(
        self,
        *,
        series_colors: tuple[str, ...],
        min_value: float,
        max_value: float,
        max_points: int = 240,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._series = [deque(maxlen=max_points) for _ in series_colors]
        self._colors = [QColor(color) for color in series_colors]
        self._min = min_value
        self._max = max_value
        self.setMinimumHeight(88)
        self.setMaximumHeight(88)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def push(self, *values: float | None) -> None:
        for index, series in enumerate(self._series):
            value = values[index] if index < len(values) else None
            if isinstance(value, (int, float)):
                series.append(float(value))
            else:
                series.append(None)
        self.update()

    def clear(self) -> None:
        for series in self._series:
            series.clear()
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(2, 2, -2, -2)
        painter.fillRect(rect, QColor(20, 20, 20, 220))
        painter.setPen(QPen(QColor(240, 237, 229, 30), 1.0))
        painter.drawRoundedRect(rect, 6, 6)

        if not any(series for series in self._series):
            painter.setPen(QPen(QColor(148, 148, 148), 1.0))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "NO DATA")
            return

        value_range = max(0.001, self._max - self._min)
        if self._min < 0.0 < self._max:
            zero_ratio = (0.0 - self._min) / value_range
            zero_y = rect.bottom() - zero_ratio * rect.height()
            painter.setPen(QPen(QColor(240, 237, 229, 28), 1.0))
            painter.drawLine(rect.left(), int(zero_y), rect.right(), int(zero_y))

        max_len = max(len(series) for series in self._series)
        dx = rect.width() / max(1, max_len - 1)
        has_data = False
        for color, series in zip(self._colors, self._series):
            path = QPainterPath()
            started = False
            for idx, value in enumerate(series):
                if value is None:
                    started = False
                    continue
                x = rect.left() + idx * dx
                norm = (float(value) - self._min) / value_range
                norm = max(0.0, min(1.0, norm))
                y = rect.bottom() - norm * rect.height()
                if not started:
                    path.moveTo(x, y)
                    started = True
                    has_data = True
                else:
                    path.lineTo(x, y)
            painter.setPen(QPen(color, 1.55))
            painter.drawPath(path)

        if not has_data:
            painter.setPen(QPen(QColor(148, 148, 148), 1.0))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "NO DATA")


class FrictionCircleWidget(QWidget):
    """Shows current and recent combined lateral/longitudinal load."""

    def __init__(
        self,
        *,
        max_g: float = 2.8,
        max_points: int = 120,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._max_g = max_g
        self._history: deque[tuple[float, float]] = deque(maxlen=max_points)
        self.setMinimumSize(180, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def push(self, lat_g: float | None, long_g: float | None) -> None:
        if isinstance(lat_g, (int, float)) and isinstance(long_g, (int, float)):
            self._history.append((float(lat_g), float(long_g)))
        self.update()

    def clear(self) -> None:
        self._history.clear()
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(4, 4, -4, -4)
        painter.fillRect(rect, QColor(20, 20, 20, 220))
        painter.setPen(QPen(QColor(240, 237, 229, 30), 1.0))
        painter.drawRoundedRect(rect, 8, 8)

        radius = min(rect.width(), rect.height()) * 0.38
        center_x = rect.center().x()
        center_y = rect.center().y()
        painter.setPen(QPen(QColor(240, 237, 229, 28), 1.0))
        painter.drawEllipse(rect.center(), int(radius), int(radius))
        painter.drawEllipse(rect.center(), int(radius * 0.5), int(radius * 0.5))
        painter.drawLine(int(center_x - radius), int(center_y), int(center_x + radius), int(center_y))
        painter.drawLine(int(center_x), int(center_y - radius), int(center_x), int(center_y + radius))

        if not self._history:
            painter.setPen(QPen(QColor(148, 148, 148), 1.0))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "NO DATA")
            return

        for index, (lat_g, long_g) in enumerate(self._history):
            alpha = 45 + int(165 * (index + 1) / len(self._history))
            dot = QColor(_PIT_ORANGE if index + 1 < len(self._history) else _ACID_GREEN)
            dot.setAlpha(alpha)
            x = center_x + max(-1.0, min(1.0, lat_g / self._max_g)) * radius
            y = center_y - max(-1.0, min(1.0, long_g / self._max_g)) * radius
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(dot)
            painter.drawEllipse(int(x - 2), int(y - 2), 4, 4)

        lat_g, long_g = self._history[-1]
        usage_pct = min(999, int(round((math.hypot(lat_g, long_g) / self._max_g) * 100.0)))
        painter.setPen(QPen(QColor(_CHALK), 1.0))
        painter.drawText(
            rect.adjusted(8, 8, -8, -8),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            f"GRIP {usage_pct}%",
        )


class MiniTrackMapWidget(QWidget):
    """Build a small track map from live world-position samples."""

    def __init__(self, *, max_points: int = 4000, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._points: deque[tuple[float, float]] = deque(maxlen=max_points)
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def push(self, x: float | None, y: float | None) -> None:
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return
        point = (float(x), float(y))
        if self._points:
            last_x, last_y = self._points[-1]
            if abs(last_x - point[0]) < 0.2 and abs(last_y - point[1]) < 0.2:
                return
        self._points.append(point)
        self.update()

    def clear(self) -> None:
        self._points.clear()
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(4, 4, -4, -4)
        painter.fillRect(rect, QColor(20, 20, 20, 220))
        painter.setPen(QPen(QColor(240, 237, 229, 30), 1.0))
        painter.drawRoundedRect(rect, 8, 8)

        if len(self._points) < 2:
            painter.setPen(QPen(QColor(148, 148, 148), 1.0))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "MAP BUILDING")
            return

        xs = [point[0] for point in self._points]
        ys = [point[1] for point in self._points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(1.0, max_x - min_x)
        span_y = max(1.0, max_y - min_y)
        margin = 16.0
        scale = min((rect.width() - 2 * margin) / span_x, (rect.height() - 2 * margin) / span_y)

        def _map_point(point: tuple[float, float]) -> tuple[float, float]:
            px = rect.left() + margin + (point[0] - min_x) * scale
            py = rect.bottom() - margin - (point[1] - min_y) * scale
            return px, py

        path = QPainterPath()
        start_x, start_y = _map_point(self._points[0])
        path.moveTo(start_x, start_y)
        for point in list(self._points)[1:]:
            px, py = _map_point(point)
            path.lineTo(px, py)

        painter.setPen(QPen(QColor(_STEEL), 1.5))
        painter.drawPath(path)

        start_x, start_y = _map_point(self._points[0])
        cur_x, cur_y = _map_point(self._points[-1])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(_PIT_ORANGE))
        painter.drawEllipse(int(start_x - 3), int(start_y - 3), 6, 6)
        painter.setBrush(QColor(_ACID_GREEN))
        painter.drawEllipse(int(cur_x - 4), int(cur_y - 4), 8, 8)


# ═══════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════════════════════════════

class DashboardPanel(QWidget):
    """Primary dashboard with hero status, live recording card, and session report."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._live_session_uid: str | None = None
        self._last_live_sample_token: object | None = None
        self._corner_tracker = LiveCornerTracker()
        self._setup_entry_ids: list[str] = []
        self._setup_diff_ids: list[str] = []
        self._build()

    def _build(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        root = QVBoxLayout(inner)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        # ── Hero card: system status ─────────────────────────────────
        hero = _card("System Status", heading="Dashboard")
        hl = hero.layout()

        # Status row
        status_row = QHBoxLayout()
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"font-size:18px; color:{_STEEL};")
        self._status_label = QLabel("IDLE")
        self._status_label.setStyleSheet(
            f"font-size:16px; font-weight:700; letter-spacing:2px;"
            f" font-family:'Consolas','Space Mono',monospace; color:{_STEEL};"
        )
        status_row.addWidget(self._status_dot)
        status_row.addWidget(self._status_label)
        status_row.addStretch(1)
        hl.addLayout(status_row)

        self._status_detail = QLabel("Waiting for simulator")
        self._status_detail.setStyleSheet(f"color:{_STEEL}; font-size:12px;")
        hl.addWidget(self._status_detail)

        hl.addWidget(_separator())

        # Quick metrics row
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(32)

        for label_text in ("SAMPLES", "ELAPSED", "SIM"):
            col = QVBoxLayout()
            col.setSpacing(2)
            lbl = _metric_label(label_text)
            val = _metric_value()
            col.addWidget(lbl)
            col.addWidget(val)
            metrics_row.addLayout(col)
            if label_text == "SAMPLES":
                self._hero_samples = val
            elif label_text == "ELAPSED":
                self._hero_elapsed = val
            else:
                self._hero_sim = val

        metrics_row.addStretch(1)
        hl.addLayout(metrics_row)

        hl.addWidget(_separator())

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_start = QPushButton("RESUME MONITORING")
        self.btn_start.setObjectName("PrimaryButton")
        self.btn_stop = QPushButton("PAUSE MONITORING")
        self.btn_stop.setObjectName("DangerButton")
        self.btn_overlay = QPushButton("OVERLAY")
        self.btn_output = QPushButton("OUTPUT")
        self.btn_logs = QPushButton("LOGS")
        self.btn_config = QPushButton("CONFIG")
        self.btn_settings = QPushButton("SETTINGS")
        for b in (self.btn_start, self.btn_stop, self.btn_overlay, self.btn_output,
                  self.btn_logs, self.btn_config, self.btn_settings):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        hl.addLayout(btn_row)

        root.addWidget(hero)

        operations_card = _card("App Operations", heading="Local Runtime")
        operations_layout = operations_card.layout()
        self._operations_rows: dict[str, QLabel] = {}
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
            value = _add_metric_row(operations_layout, key)
            value.setWordWrap(True)
            value.setStyleSheet(f"font-size:13px; font-weight:600; color:{_CHALK};")
            self._operations_rows[key] = value
        operations_layout.addWidget(_separator())
        self._operations_feature_label = QLabel("No capability summary yet.")
        self._operations_feature_label.setWordWrap(True)
        self._operations_feature_label.setTextFormat(Qt.TextFormat.RichText)
        self._operations_feature_label.setStyleSheet(f"font-size:13px; font-weight:600; color:{_CHALK};")
        operations_layout.addWidget(self._operations_feature_label)
        operations_layout.addWidget(_separator())

        profile_controls = QHBoxLayout()
        profile_controls.setSpacing(8)
        self.btn_ops_refresh = QPushButton("REFRESH OPS")
        self.btn_ops_toggle_raw = QPushButton("TOGGLE RAW")
        self.btn_ops_save_profile = QPushButton("SAVE PROFILE")
        self.btn_ops_apply_profile = QPushButton("APPLY PROFILE")
        self.ops_profile_scope = QComboBox()
        self.ops_profile_scope.addItem("SIM", "sim")
        self.ops_profile_scope.addItem("CAR", "car")
        self.ops_profile_scope.addItem("DRIVER", "driver")
        self.ops_profile_name = QLineEdit()
        self.ops_profile_name.setPlaceholderText("Profile name")
        self.ops_profile_select = QComboBox()
        self.ops_profile_select.setMinimumWidth(280)
        for button in (
            self.btn_ops_refresh,
            self.btn_ops_toggle_raw,
            self.btn_ops_save_profile,
            self.btn_ops_apply_profile,
        ):
            profile_controls.addWidget(button)
        profile_controls.addWidget(self.ops_profile_scope)
        profile_controls.addWidget(self.ops_profile_name)
        profile_controls.addWidget(self.ops_profile_select, 1)
        operations_layout.addLayout(profile_controls)
        self._operations_profile_ids: list[str] = []
        root.addWidget(operations_card)

        # ── Live recording card ──────────────────────────────────────
        live_card = _card("Telemetry", heading="Live Session")
        ll = live_card.layout()

        headline = QHBoxLayout()
        headline.setSpacing(20)
        self._headline_rows: dict[str, QLabel] = {}
        for key, label in (("Speed", "SPEED"), ("Gear", "GEAR"), ("RPM", "RPM")):
            col = QVBoxLayout()
            col.setSpacing(3)
            col.addWidget(_metric_label(label))
            value = _metric_value("—")
            value.setStyleSheet(
                f"font-size:28px; font-weight:800;"
                " font-family:'Consolas','Space Mono',monospace;"
                f" color:{_CHALK};"
            )
            col.addWidget(value)
            headline.addLayout(col)
            self._headline_rows[key] = value
        headline.addStretch(1)
        ll.addLayout(headline)
        ll.addWidget(_separator())

        self._live_rows: dict[str, QLabel] = {}
        for key in ("Track", "Car", "Lap", "Session", "Flag", "Throttle", "Brake", "Steering"):
            self._live_rows[key] = _add_metric_row(ll, key)

        ll.addWidget(_separator())
        graph_grid = QGridLayout()
        graph_grid.setHorizontalSpacing(12)
        graph_grid.setVerticalSpacing(12)

        traces_card = _card("Graphs", heading="Live Telemetry")
        traces_layout = traces_card.layout()
        self._graph_traces: dict[str, TelemetryTraceWidget] = {
            "speed": TelemetryTraceWidget(series_colors=(_ACID_GREEN,), min_value=0.0, max_value=340.0),
            "pedals": TelemetryTraceWidget(series_colors=(_PIT_ORANGE, _SAFETY_RED), min_value=0.0, max_value=1.0),
            "steering": TelemetryTraceWidget(series_colors=(_MARSHAL_YELLOW,), min_value=-540.0, max_value=540.0),
            "rpm": TelemetryTraceWidget(series_colors=("#6CC0FF",), min_value=0.0, max_value=12000.0),
            "g": TelemetryTraceWidget(series_colors=("#8B5CF6", "#F97316"), min_value=-3.0, max_value=3.0),
        }
        trace_grid = QGridLayout()
        trace_grid.setHorizontalSpacing(10)
        trace_grid.setVerticalSpacing(8)
        trace_items = [
            ("SPEED TRACE", self._graph_traces["speed"]),
            ("THROTTLE / BRAKE", self._graph_traces["pedals"]),
            ("STEERING ANGLE", self._graph_traces["steering"]),
            ("RPM TRACE", self._graph_traces["rpm"]),
            ("LONG G / LAT G", self._graph_traces["g"]),
        ]
        for row, (label, widget) in enumerate(trace_items):
            lbl = QLabel(label)
            lbl.setObjectName("MetricLabel")
            lbl.setMinimumWidth(124)
            trace_grid.addWidget(lbl, row, 0)
            trace_grid.addWidget(widget, row, 1)
        traces_layout.addLayout(trace_grid)
        graph_grid.addWidget(traces_card, 0, 0, 1, 2)

        friction_card = _card("Grip Usage", heading="Friction Circle")
        friction_layout = friction_card.layout()
        self._friction_circle = FrictionCircleWidget()
        friction_layout.addWidget(self._friction_circle)
        graph_grid.addWidget(friction_card, 0, 2)

        map_card = _card("Track Map", heading="Auto-Generated")
        map_layout = map_card.layout()
        self._track_map = MiniTrackMapWidget()
        map_layout.addWidget(self._track_map)
        graph_grid.addWidget(map_card, 1, 0)

        corner_card = _card("Corner Table", heading="Live After Lap 1")
        corner_layout = corner_card.layout()
        self._corner_table = QTableWidget(0, 5)
        self._corner_table.setHorizontalHeaderLabels(["CORNER", "LAST", "BEST", "APEX", "PEAK G"])
        self._corner_table.verticalHeader().setVisible(False)
        self._corner_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._corner_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._corner_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._corner_table.setMinimumHeight(220)
        corner_layout.addWidget(self._corner_table)
        graph_grid.addWidget(corner_card, 1, 1, 1, 2)

        ll.addLayout(graph_grid)
        ll.addWidget(_separator())

        detail_grid = QGridLayout()
        detail_grid.setHorizontalSpacing(12)
        detail_grid.setVerticalSpacing(12)

        timing_card = _card("Timing", heading="Lap Feed")
        tl = timing_card.layout()
        self._timing_rows: dict[str, QLabel] = {}
        for key in ("Lap Time", "Live Delta", "Best Lap", "Sector 1", "Sector 2", "Sector 3"):
            self._timing_rows[key] = _add_metric_row(tl, key)
        detail_grid.addWidget(timing_card, 0, 0)

        fuel_card = _card("Fuel", heading="Run Plan")
        fl = fuel_card.layout()
        self._fuel_rows: dict[str, QLabel] = {}
        for key in ("Fuel Level", "Fuel / Lap", "Laps Left"):
            self._fuel_rows[key] = _add_metric_row(fl, key)
        detail_grid.addWidget(fuel_card, 0, 1)

        electronics_card = _card("Electronics", heading="Driver Aids")
        el = electronics_card.layout()
        self._electronics_rows: dict[str, QLabel] = {}
        for key in ("TC", "ABS", "Map", "Brake Bias"):
            self._electronics_rows[key] = _add_metric_row(el, key)
        detail_grid.addWidget(electronics_card, 0, 2)

        tyre_card = _card("Tyres", heading="Temps / Pressures / Wear")
        tyre_layout = tyre_card.layout()
        self._tyre_rows = self._build_dashboard_corner_table(
            tyre_layout,
            columns=("Temp", "Press", "Wear"),
        )
        detail_grid.addWidget(tyre_card, 1, 0, 1, 2)

        brake_card = _card("Brakes", heading="Brake Temperatures")
        brake_layout = brake_card.layout()
        self._brake_rows = self._build_dashboard_corner_table(
            brake_layout,
            columns=("Temp",),
        )
        detail_grid.addWidget(brake_card, 1, 2)

        ll.addLayout(detail_grid)
        ll.addWidget(_separator())

        coach_grid = QGridLayout()
        coach_grid.setHorizontalSpacing(12)
        coach_grid.setVerticalSpacing(12)

        alerts_card = _card("Live Alerts", heading="Real-Time Risk Flags")
        alerts_layout = alerts_card.layout()
        self._alerts_label = QLabel("No active alerts.")
        self._alerts_label.setWordWrap(True)
        self._alerts_label.setTextFormat(Qt.TextFormat.RichText)
        self._alerts_label.setStyleSheet(f"font-size:13px; font-weight:600; color:{_CHALK};")
        alerts_layout.addWidget(self._alerts_label)
        coach_grid.addWidget(alerts_card, 0, 0)

        coaching_card = _card("Live Coaching", heading="Corner Feedback")
        coaching_layout = coaching_card.layout()
        self._coaching_label = QLabel("Complete a clean reference lap to unlock live coaching.")
        self._coaching_label.setWordWrap(True)
        self._coaching_label.setTextFormat(Qt.TextFormat.RichText)
        self._coaching_label.setStyleSheet(f"font-size:13px; font-weight:600; color:{_CHALK};")
        coaching_layout.addWidget(self._coaching_label)
        coach_grid.addWidget(coaching_card, 0, 1)

        summary_card = _card("Lap-End Summary", heading="Next Lap Focus")
        summary_layout = summary_card.layout()
        self._summary_rows: dict[str, QLabel] = {}
        for key in ("Biggest Loss", "Technique Issue", "Next Focus"):
            value = _add_metric_row(summary_layout, key)
            value.setWordWrap(True)
            value.setStyleSheet(f"font-size:13px; font-weight:600; color:{_CHALK};")
            self._summary_rows[key] = value
        coach_grid.addWidget(summary_card, 0, 2)

        ll.addLayout(coach_grid)
        root.addWidget(live_card)

        hardware_card = _card("Hardware / Input / FFB", heading="Control Diagnostics")
        hardware_layout = hardware_card.layout()
        hardware_grid = QGridLayout()
        hardware_grid.setHorizontalSpacing(12)
        hardware_grid.setVerticalSpacing(12)

        pedal_card = _card("Pedals", heading="Brake / Throttle")
        pedal_layout = pedal_card.layout()
        self._hardware_input_rows: dict[str, QLabel] = {}
        for key in ("Brake Trace", "Throttle Mod", "Pedal Overlap", "Deadzone"):
            value = _add_metric_row(pedal_layout, key)
            value.setWordWrap(True)
            value.setStyleSheet(f"font-size:13px; font-weight:600; color:{_CHALK};")
            self._hardware_input_rows[key] = value
        hardware_grid.addWidget(pedal_card, 0, 0)

        steering_card = _card("Steering / FFB", heading="Wheel Behavior")
        steering_layout = steering_card.layout()
        self._hardware_steering_rows: dict[str, QLabel] = {}
        for key in ("Steering Linearity", "Steering Saturation", "FFB Clipping", "Wheel Oscillation"):
            value = _add_metric_row(steering_layout, key)
            value.setWordWrap(True)
            value.setStyleSheet(f"font-size:13px; font-weight:600; color:{_CHALK};")
            self._hardware_steering_rows[key] = value
        hardware_grid.addWidget(steering_card, 0, 1)

        flags_card = _card("Flags", heading="Instability Warnings")
        flags_layout = flags_card.layout()
        self._hardware_flags_label = QLabel("No hardware/input warnings.")
        self._hardware_flags_label.setWordWrap(True)
        self._hardware_flags_label.setTextFormat(Qt.TextFormat.RichText)
        self._hardware_flags_label.setStyleSheet(f"font-size:13px; font-weight:600; color:{_CHALK};")
        flags_layout.addWidget(self._hardware_flags_label)
        hardware_grid.addWidget(flags_card, 0, 2)

        hardware_layout.addLayout(hardware_grid)
        root.addWidget(hardware_card)

        platform_card = _card("Ride Height / Balance / Platform", heading="Platform Analysis")
        platform_layout = platform_card.layout()
        self._platform_rows: dict[str, QLabel] = {}
        for key in (
            "Rake Trend",
            "Compression / Bottoming",
            "Chassis Balance",
            "Front vs Rear",
            "Roll Asymmetry",
            "Aero Balance",
        ):
            value = _add_metric_row(platform_layout, key)
            value.setWordWrap(True)
            value.setStyleSheet(f"font-size:13px; font-weight:600; color:{_CHALK};")
            self._platform_rows[key] = value
        platform_layout.addWidget(_separator())
        self._platform_flags_label = QLabel("No platform warnings.")
        self._platform_flags_label.setWordWrap(True)
        self._platform_flags_label.setTextFormat(Qt.TextFormat.RichText)
        self._platform_flags_label.setStyleSheet(f"font-size:13px; font-weight:600; color:{_CHALK};")
        platform_layout.addWidget(self._platform_flags_label)
        root.addWidget(platform_card)

        setup_card = _card("Setup Tools", heading="Local Library")
        setup_layout = setup_card.layout()
        self._setup_rows: dict[str, QLabel] = {}
        for key in ("Sim", "Current", "Folder"):
            value = _add_metric_row(setup_layout, key)
            value.setWordWrap(True)
            value.setStyleSheet(f"font-size:13px; font-weight:600; color:{_CHALK};")
            self._setup_rows[key] = value

        setup_buttons = QHBoxLayout()
        setup_buttons.setSpacing(8)
        self.btn_setup_refresh = QPushButton("REFRESH SETUPS")
        self.btn_setup_favorite = QPushButton("FAVORITE")
        self.btn_setup_install = QPushButton("INSTALL FILE")
        self.btn_setup_duplicate = QPushButton("DUPLICATE")
        self.btn_setup_rollback = QPushButton("ROLLBACK")
        self.btn_setup_bundle = QPushButton("SAVE + LAP")
        self.setup_duplicate_name = QLineEdit()
        self.setup_duplicate_name.setPlaceholderText("Duplicate name")
        self.setup_duplicate_name.setMinimumWidth(180)
        for button in (
            self.btn_setup_refresh,
            self.btn_setup_favorite,
            self.btn_setup_install,
            self.btn_setup_duplicate,
            self.btn_setup_rollback,
            self.btn_setup_bundle,
        ):
            setup_buttons.addWidget(button)
        setup_buttons.addWidget(self.setup_duplicate_name)
        setup_buttons.addStretch(1)
        setup_layout.addLayout(setup_buttons)
        setup_layout.addWidget(_separator())

        setup_grid = QGridLayout()
        setup_grid.setHorizontalSpacing(12)
        setup_grid.setVerticalSpacing(12)

        library_card = _card("Library", heading="Native Setup Files")
        library_layout = library_card.layout()
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
        self._setup_table.setMinimumHeight(230)
        library_layout.addWidget(self._setup_table)
        setup_grid.addWidget(library_card, 0, 0, 1, 2)

        current_setup_card = _card("Current Setup", heading="Structured Snapshot")
        current_setup_layout = current_setup_card.layout()
        self._setup_current_table = QTableWidget(0, 2)
        self._setup_current_table.setHorizontalHeaderLabels(["SETTING", "VALUE"])
        self._setup_current_table.verticalHeader().setVisible(False)
        self._setup_current_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._setup_current_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._setup_current_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._setup_current_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._setup_current_table.setMinimumHeight(230)
        current_setup_layout.addWidget(self._setup_current_table)
        setup_grid.addWidget(current_setup_card, 0, 2)

        diff_card = _card("Setup Diff", heading="Changed Values Only")
        diff_layout = diff_card.layout()
        diff_controls = QHBoxLayout()
        diff_controls.setSpacing(8)
        diff_controls.addWidget(_metric_label("A"))
        self.setup_diff_a = QComboBox()
        diff_controls.addWidget(self.setup_diff_a, 1)
        diff_controls.addWidget(_metric_label("B"))
        self.setup_diff_b = QComboBox()
        diff_controls.addWidget(self.setup_diff_b, 1)
        diff_layout.addLayout(diff_controls)
        self._setup_diff_table = QTableWidget(0, 4)
        self._setup_diff_table.setHorizontalHeaderLabels(["SETTING", "A", "B", "LIKELY EFFECT"])
        self._setup_diff_table.verticalHeader().setVisible(False)
        self._setup_diff_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._setup_diff_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._setup_diff_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._setup_diff_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._setup_diff_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._setup_diff_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._setup_diff_table.setMinimumHeight(220)
        diff_layout.addWidget(self._setup_diff_table)
        setup_grid.addWidget(diff_card, 1, 0, 1, 3)

        coach_card = _card("Setup Coach", heading="Latest Saved Bundle")
        coach_layout = coach_card.layout()
        self._setup_coach_rows: dict[str, QLabel] = {}
        for key in ("Status", "Bundle", "Issues"):
            value = _add_metric_row(coach_layout, key)
            value.setWordWrap(True)
            value.setStyleSheet(f"font-size:13px; font-weight:600; color:{_CHALK};")
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
        self._setup_coach_table.setMinimumHeight(180)
        coach_layout.addWidget(self._setup_coach_table)
        self._setup_coach_notes = QLabel("No setup coach analysis yet.")
        self._setup_coach_notes.setWordWrap(True)
        self._setup_coach_notes.setTextFormat(Qt.TextFormat.RichText)
        self._setup_coach_notes.setStyleSheet(f"font-size:13px; font-weight:600; color:{_CHALK};")
        coach_layout.addWidget(self._setup_coach_notes)
        setup_grid.addWidget(coach_card, 2, 0, 1, 3)

        setup_layout.addLayout(setup_grid)
        root.addWidget(setup_card)

        # ── Session report card ──────────────────────────────────────
        report_card = _card("Session Report", heading="Last Completed")
        rl = report_card.layout()

        self._report_rows: dict[str, QLabel] = {}
        for key in (
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
        ):
            val = _add_metric_row(rl, key)
            self._report_rows[key] = val

        self._report_card = report_card
        root.addWidget(report_card)

        root.addStretch(1)
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _build_dashboard_corner_table(
        self,
        layout: QVBoxLayout,
        *,
        columns: tuple[str, ...],
    ) -> dict[str, dict[str, QLabel]]:
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.addWidget(_metric_label("Wheel"), 0, 0)
        for idx, heading in enumerate(columns, start=1):
            head = _metric_label(heading)
            head.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(head, 0, idx)

        rows: dict[str, dict[str, QLabel]] = {}
        for row_idx, wheel in enumerate(("LF", "RF", "LR", "RR"), start=1):
            grid.addWidget(_metric_label(wheel), row_idx, 0)
            rows[wheel] = {}
            for col_idx, heading in enumerate(columns, start=1):
                value = _metric_value("—")
                value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                grid.addWidget(value, row_idx, col_idx)
                rows[wheel][heading] = value

        layout.addLayout(grid)
        return rows

    def _reset_live_visuals(self, session_uid: str | None = None) -> None:
        self._live_session_uid = session_uid
        self._last_live_sample_token = None
        self._corner_tracker.reset(session_uid)
        for widget in self._graph_traces.values():
            widget.clear()
        self._friction_circle.clear()
        self._track_map.clear()
        self._corner_table.setRowCount(0)

    def _push_live_visuals(self, live: dict[str, object]) -> None:
        self._graph_traces["speed"].push(_as_float(live.get("speed_kph")))
        self._graph_traces["pedals"].push(
            _as_float(live.get("throttle_pct")),
            _as_float(live.get("brake_pct")),
        )
        self._graph_traces["steering"].push(_as_float(live.get("steering_deg")))
        self._graph_traces["rpm"].push(_as_float(live.get("rpm")))
        self._graph_traces["g"].push(
            _as_float(live.get("long_accel_g")),
            _as_float(live.get("lat_accel_g")),
        )
        self._friction_circle.push(
            _as_float(live.get("lat_accel_g")),
            _as_float(live.get("long_accel_g")),
        )
        track_y = _as_float(live.get("world_pos_z"))
        if track_y is None:
            track_y = _as_float(live.get("world_pos_y"))
        self._track_map.push(_as_float(live.get("world_pos_x")), track_y)
        self._corner_tracker.push_snapshot(live)
        self._update_corner_table()

    def _update_corner_table(self) -> None:
        rows = self._corner_tracker.rows()
        self._corner_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                str(row.get("corner") or "-"),
                _format_lap_time(row.get("last_time_s")),
                _format_lap_time(row.get("best_time_s")),
                _format_whole_number(row.get("apex_speed_kph"), suffix=" km/h"),
                _format_signed_number(row.get("peak_lat_g"), suffix=" g"),
            ]
            for col_index, text in enumerate(values):
                item = QTableWidgetItem(text)
                alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                if col_index > 0:
                    alignment = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                item.setTextAlignment(alignment)
                self._corner_table.setItem(row_index, col_index, item)

    def selected_setup_id(self) -> str | None:
        row = self._setup_table.currentRow()
        if 0 <= row < len(self._setup_entry_ids):
            return self._setup_entry_ids[row]
        return None

    def selected_operations_profile_id(self) -> str | None:
        index = self.ops_profile_select.currentIndex()
        if 0 <= index < len(self._operations_profile_ids):
            return self._operations_profile_ids[index]
        return None

    def operations_profile_name(self) -> str:
        return self.ops_profile_name.text().strip()

    def operations_profile_scope(self) -> str:
        return str(self.ops_profile_scope.currentData() or "sim")

    def selected_diff_pair(self) -> tuple[str | None, str | None]:
        a_index = self.setup_diff_a.currentIndex()
        b_index = self.setup_diff_b.currentIndex()
        setup_a = self._setup_diff_ids[a_index] if 0 <= a_index < len(self._setup_diff_ids) else None
        setup_b = self._setup_diff_ids[b_index] if 0 <= b_index < len(self._setup_diff_ids) else None
        return setup_a, setup_b

    def duplicate_setup_name(self) -> str:
        return self.setup_duplicate_name.text().strip()

    def _update_setup_tools(self, setup_tools: dict[str, object]) -> None:
        status = str(setup_tools.get("status") or "missing")
        entries = list(setup_tools.get("entries") or [])
        self._setup_rows["Sim"].setText(str(setup_tools.get("sim") or "-"))
        self._setup_rows["Current"].setText(str(setup_tools.get("current_setup_name") or "-"))
        self._setup_rows["Folder"].setText(str(setup_tools.get("root") or "-"))
        self.btn_setup_favorite.setEnabled(bool(entries))
        self.btn_setup_install.setEnabled(status == "ready")
        self.btn_setup_duplicate.setEnabled(bool(entries))
        self.btn_setup_bundle.setEnabled(bool(entries))
        self.btn_setup_rollback.setEnabled(bool(setup_tools.get("rollback_available")))

        selected_setup_id = self.selected_setup_id()
        current_setup_id = str(setup_tools.get("current_setup_id") or "") or None
        target_setup_id = selected_setup_id or current_setup_id

        self._setup_entry_ids = []
        self._setup_table.setRowCount(len(entries))
        for row_index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            setup_id = str(entry.get("id") or "")
            self._setup_entry_ids.append(setup_id)
            values = [
                "YES" if entry.get("is_favorite") else "-",
                "LIVE" if entry.get("is_current") else "-",
                str(entry.get("name") or "-"),
                str(entry.get("car") or "-"),
                str(entry.get("track") or "-"),
                _format_datetime_short(entry.get("modified_ts")),
                str(entry.get("format") or "-"),
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col_index in (0, 1, 5, 6):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col_index == 0 and entry.get("is_favorite"):
                    item.setForeground(QColor(_PIT_ORANGE))
                if col_index == 1 and entry.get("is_current"):
                    item.setForeground(QColor(_ACID_GREEN))
                self._setup_table.setItem(row_index, col_index, item)

        if target_setup_id and target_setup_id in self._setup_entry_ids:
            self._setup_table.setCurrentCell(self._setup_entry_ids.index(target_setup_id), 0)
        elif self._setup_entry_ids:
            self._setup_table.setCurrentCell(0, 0)
        else:
            self._setup_table.clearSelection()

        current_rows = list(setup_tools.get("current_setup_rows") or [])
        self._setup_current_table.setRowCount(len(current_rows))
        for row_index, row in enumerate(current_rows):
            if not isinstance(row, dict):
                continue
            key_item = QTableWidgetItem(str(row.get("key") or "-"))
            value_item = QTableWidgetItem(str(row.get("display") or "-"))
            value_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._setup_current_table.setItem(row_index, 0, key_item)
            self._setup_current_table.setItem(row_index, 1, value_item)

        diff_a_id = str(setup_tools.get("selected_diff_a_id") or "") or None
        diff_b_id = str(setup_tools.get("selected_diff_b_id") or "") or None
        self.setup_diff_a.blockSignals(True)
        self.setup_diff_b.blockSignals(True)
        self.setup_diff_a.clear()
        self.setup_diff_b.clear()
        self._setup_diff_ids = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            setup_id = str(entry.get("id") or "")
            label = str(entry.get("name") or "-")
            self.setup_diff_a.addItem(label)
            self.setup_diff_b.addItem(label)
            self._setup_diff_ids.append(setup_id)
        if diff_a_id and diff_a_id in self._setup_diff_ids:
            self.setup_diff_a.setCurrentIndex(self._setup_diff_ids.index(diff_a_id))
        elif self._setup_diff_ids:
            self.setup_diff_a.setCurrentIndex(0)
        if diff_b_id and diff_b_id in self._setup_diff_ids:
            self.setup_diff_b.setCurrentIndex(self._setup_diff_ids.index(diff_b_id))
        elif len(self._setup_diff_ids) > 1:
            self.setup_diff_b.setCurrentIndex(1)
        elif self._setup_diff_ids:
            self.setup_diff_b.setCurrentIndex(0)
        self.setup_diff_a.blockSignals(False)
        self.setup_diff_b.blockSignals(False)

        diff_rows = list(setup_tools.get("diff_rows") or [])
        self._setup_diff_table.setRowCount(len(diff_rows))
        for row_index, row in enumerate(diff_rows):
            if not isinstance(row, dict):
                continue
            values = [
                str(row.get("key") or "-"),
                str(row.get("value_a") or "-"),
                str(row.get("value_b") or "-"),
                str(row.get("effect") or "-"),
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col_index in (1, 2):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self._setup_diff_table.setItem(row_index, col_index, item)

        recommendation = setup_tools.get("recommendation")
        recommendation = recommendation if isinstance(recommendation, dict) else {}
        self._setup_coach_rows["Status"].setText(str(recommendation.get("status") or "-"))
        self._setup_coach_rows["Bundle"].setText(str(recommendation.get("bundle_name") or "-"))
        issues = list(recommendation.get("issue_tags") or [])
        self._setup_coach_rows["Issues"].setText(", ".join(str(issue) for issue in issues) if issues else "-")
        candidates = list(recommendation.get("candidates") or [])
        self._setup_coach_table.setRowCount(len(candidates))
        for row_index, candidate in enumerate(candidates):
            if not isinstance(candidate, dict):
                continue
            confidence = candidate.get("confidence")
            confidence_text = f"{float(confidence):.2f}" if isinstance(confidence, (int, float)) else "-"
            suggested = str(candidate.get("suggested_display") or candidate.get("suggested_value") or "-")
            diff_hint = str(candidate.get("diff_hint") or "").strip()
            if diff_hint and suggested != "-":
                suggested = f"{suggested} ({diff_hint})"
            values = [
                str(candidate.get("label") or "-"),
                str(candidate.get("current_display") or candidate.get("current_value") or "-"),
                suggested,
                confidence_text,
                str(candidate.get("rationale") or "-"),
                str(candidate.get("likely_effect") or "-"),
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col_index in (1, 2, 3):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._setup_coach_table.setItem(row_index, col_index, item)
        notes = list(recommendation.get("notes") or [])
        if notes:
            self._setup_coach_notes.setText("<br>".join(f"&bull; {html.escape(str(note))}" for note in notes[:3]))
        else:
            self._setup_coach_notes.setText("No setup coach notes.")

    # ── Public API ───────────────────────────────────────────────────

    def update_snapshot(self, snap: dict) -> None:
        status = str(snap.get("status", "Idle"))
        color = _STATUS_COLORS.get(status, _STEEL)

        self._status_dot.setStyleSheet(f"font-size:18px; color:{color};")
        self._status_label.setText(status.upper())
        self._status_label.setStyleSheet(
            f"font-size:16px; font-weight:700; letter-spacing:2px;"
            f" font-family:'Consolas','Space Mono',monospace; color:{color};"
        )
        self._status_detail.setText(str(snap.get("status_detail") or "Ready"))

        samples = snap.get("sample_count", 0)
        elapsed = snap.get("elapsed_s", 0)
        sim = snap.get("sim") or snap.get("detected_sim") or "—"
        self._hero_samples.setText(f"{samples:,}" if samples else "—")
        mins, secs = divmod(int(elapsed), 60)
        self._hero_elapsed.setText(f"{mins}:{secs:02d}" if elapsed else "—")
        self._hero_sim.setText(str(sim))

        operations = snap.get("operations")
        operations = operations if isinstance(operations, dict) else {}
        op_rows = operations.get("rows")
        op_rows = op_rows if isinstance(op_rows, dict) else {}
        self._operations_rows["Autodetect"].setText(_format_diag_metric(op_rows.get("autodetect")))
        self._operations_rows["Auto-Start With Sim"].setText(_format_diag_metric(op_rows.get("auto_start")))
        self._operations_rows["Pin Mode"].setText(_format_diag_metric(op_rows.get("pin_mode")))
        self._operations_rows["Profiles"].setText(_format_diag_metric(op_rows.get("profiles")))
        self._operations_rows["Safe Update"].setText(_format_diag_metric(op_rows.get("safe_update")))
        self._operations_rows["Crash Recovery"].setText(_format_diag_metric(op_rows.get("crash_recovery")))
        self._operations_rows["Low-Resource Mode"].setText(_format_diag_metric(op_rows.get("low_resource")))
        self._operations_rows["Raw Recorder"].setText(_format_diag_metric(op_rows.get("raw_recorder")))
        feature_list = operations.get("feature_list")
        feature_list = feature_list if isinstance(feature_list, list) else []
        if feature_list:
            escaped = [html.escape(str(item)) for item in feature_list[:6]]
            self._operations_feature_label.setText(
                "<span style='color:{0}; font-weight:800;'>FIRST-CLASS LOCAL</span><br>{1}".format(
                    _PIT_ORANGE,
                    " | ".join(escaped),
                )
            )
        else:
            self._operations_feature_label.setText(f"<span style='color:{_STEEL};'>No capability summary yet.</span>")
        profiles = operations.get("profiles")
        profiles = profiles if isinstance(profiles, list) else []
        current_profile_id = self.selected_operations_profile_id()
        self.ops_profile_select.blockSignals(True)
        self.ops_profile_select.clear()
        self._operations_profile_ids = []
        for profile in profiles:
            if not isinstance(profile, dict):
                continue
            self.ops_profile_select.addItem(str(profile.get("label") or "Profile"))
            self._operations_profile_ids.append(str(profile.get("id") or ""))
        if current_profile_id and current_profile_id in self._operations_profile_ids:
            self.ops_profile_select.setCurrentIndex(self._operations_profile_ids.index(current_profile_id))
        else:
            matched_index = next(
                (index for index, profile in enumerate(profiles) if isinstance(profile, dict) and profile.get("matched")),
                -1,
            )
            if matched_index >= 0:
                self.ops_profile_select.setCurrentIndex(matched_index)
            elif self._operations_profile_ids:
                self.ops_profile_select.setCurrentIndex(0)
        self.ops_profile_select.blockSignals(False)
        self.btn_ops_apply_profile.setEnabled(bool(self._operations_profile_ids))
        self.btn_ops_toggle_raw.setEnabled(bool(str(snap.get("sim") or "").strip()))

        # Live telemetry
        live = snap.get("live") or {}
        self._headline_rows["Speed"].setText(_format_whole_number(live.get("speed_kph"), suffix=" km/h"))
        self._headline_rows["Gear"].setText(_format_gear(live.get("gear")))
        self._headline_rows["RPM"].setText(_format_whole_number(live.get("rpm")))
        self._live_rows["Track"].setText(str(live.get("track_name") or "—"))
        self._live_rows["Car"].setText(str(live.get("car_name") or "—"))
        self._live_rows["Lap"].setText(str(live.get("lap_number") or "—"))
        self._live_rows["Session"].setText(str(live.get("session_status") or live.get("session_type") or "—"))
        self._live_rows["Flag"].setText(str(live.get("flag_state") or "—").replace("_", " ").upper())
        self._live_rows["Throttle"].setText(_format_percent(live.get("throttle_pct")))
        self._live_rows["Brake"].setText(_format_percent(live.get("brake_pct")))
        self._live_rows["Steering"].setText(_format_signed_number(live.get("steering_deg"), suffix="°"))
        self._timing_rows["Lap Time"].setText(_format_lap_time(live.get("lap_time_s")))
        self._timing_rows["Live Delta"].setText(_format_delta(live.get("live_delta_s")))
        self._timing_rows["Best Lap"].setText(_format_lap_time(live.get("best_lap_time_s")))
        self._timing_rows["Sector 1"].setText(_format_lap_time(live.get("sector_1_time_s")))
        self._timing_rows["Sector 2"].setText(_format_lap_time(live.get("sector_2_time_s")))
        self._timing_rows["Sector 3"].setText(_format_lap_time(live.get("sector_3_time_s")))
        self._fuel_rows["Fuel Level"].setText(_format_signed_number(live.get("fuel_level"), suffix=" L"))
        self._fuel_rows["Fuel / Lap"].setText(_format_signed_number(live.get("fuel_per_lap_l"), suffix=" L"))
        self._fuel_rows["Laps Left"].setText(_format_signed_number(live.get("laps_remaining_est")))
        self._electronics_rows["TC"].setText(_format_signed_number(live.get("tc_level")))
        self._electronics_rows["ABS"].setText(_format_signed_number(live.get("abs_level")))
        self._electronics_rows["Map"].setText(_format_signed_number(live.get("engine_map")))
        self._electronics_rows["Brake Bias"].setText(_format_signed_number(live.get("brake_bias_pct"), suffix="%"))
        session_uid = str(live.get("session_uid") or "") or None
        if session_uid != self._live_session_uid:
            self._reset_live_visuals(session_uid)
        sample_token = _live_sample_token(live)
        if sample_token is not None and sample_token != self._last_live_sample_token:
            self._push_live_visuals(live)
            self._last_live_sample_token = sample_token
        for wheel in ("LF", "RF", "LR", "RR"):
            slug = wheel.lower()
            self._tyre_rows[wheel]["Temp"].setText(_format_signed_number(live.get(f"tyre_temp_{slug}"), suffix="°C"))
            self._tyre_rows[wheel]["Press"].setText(_format_signed_number(live.get(f"tyre_pressure_{slug}")))
            self._tyre_rows[wheel]["Wear"].setText(_format_signed_number(live.get(f"tyre_wear_{slug}")))
            self._brake_rows[wheel]["Temp"].setText(_format_signed_number(live.get(f"brake_temp_{slug}"), suffix="°C"))

        coach = snap.get("live_coaching")
        coach = coach if isinstance(coach, dict) else {}
        self._alerts_label.setText(_format_alert_items(coach.get("alerts")))
        self._coaching_label.setText(_format_coaching_items(coach.get("coaching"), coach.get("active_corner")))
        lap_end_summary = coach.get("lap_end_summary")
        lap_end_summary = lap_end_summary if isinstance(lap_end_summary, dict) else {}
        self._summary_rows["Biggest Loss"].setText(_format_summary_text(lap_end_summary.get("biggest_time_loss_corner")))
        self._summary_rows["Technique Issue"].setText(_format_summary_text(lap_end_summary.get("biggest_technique_issue")))
        self._summary_rows["Next Focus"].setText(_format_summary_text(lap_end_summary.get("recommended_focus")))
        hardware = snap.get("hardware_diagnostics")
        hardware = hardware if isinstance(hardware, dict) else {}
        rows = hardware.get("rows")
        rows = rows if isinstance(rows, dict) else {}
        self._hardware_input_rows["Brake Trace"].setText(_format_diag_metric(rows.get("brake_trace")))
        self._hardware_input_rows["Throttle Mod"].setText(_format_diag_metric(rows.get("throttle_modulation")))
        self._hardware_input_rows["Pedal Overlap"].setText(_format_diag_metric(rows.get("pedal_overlap")))
        self._hardware_input_rows["Deadzone"].setText(_format_diag_metric(rows.get("deadzone")))
        self._hardware_steering_rows["Steering Linearity"].setText(_format_diag_metric(rows.get("steering_linearity")))
        self._hardware_steering_rows["Steering Saturation"].setText(_format_diag_metric(rows.get("steering_saturation")))
        self._hardware_steering_rows["FFB Clipping"].setText(_format_diag_metric(rows.get("ffb_clipping")))
        self._hardware_steering_rows["Wheel Oscillation"].setText(_format_diag_metric(rows.get("wheel_oscillation")))
        self._hardware_flags_label.setText(_format_diag_flags(hardware.get("flags")))
        platform = snap.get("platform_analysis")
        platform = platform if isinstance(platform, dict) else {}
        platform_rows = platform.get("rows")
        platform_rows = platform_rows if isinstance(platform_rows, dict) else {}
        self._platform_rows["Rake Trend"].setText(_format_diag_metric(platform_rows.get("rake_trend")))
        self._platform_rows["Compression / Bottoming"].setText(_format_diag_metric(platform_rows.get("ride_height_compression")))
        self._platform_rows["Chassis Balance"].setText(_format_diag_metric(platform_rows.get("chassis_balance")))
        self._platform_rows["Front vs Rear"].setText(_format_diag_metric(platform_rows.get("front_rear_limitation")))
        self._platform_rows["Roll Asymmetry"].setText(_format_diag_metric(platform_rows.get("roll_asymmetry")))
        self._platform_rows["Aero Balance"].setText(_format_diag_metric(platform_rows.get("aero_balance")))
        self._platform_flags_label.setText(_format_diag_flags(platform.get("flags")))
        setup_tools = snap.get("setup_tools")
        self._update_setup_tools(setup_tools if isinstance(setup_tools, dict) else {})

        # Completed session report
        report = snap.get("completed_session")
        if report:
            self._report_rows["Samples"].setText(str(report.get("samples", "—")))
            dur = report.get("duration_s", 0)
            if isinstance(dur, (int, float)) and dur > 0:
                m, s = divmod(int(dur), 60)
                self._report_rows["Duration"].setText(f"{m}:{s:02d}")
            else:
                self._report_rows["Duration"].setText("—")
            self._report_rows["Laps"].setText(str(report.get("laps", "—")))
            self._report_rows["Clean Laps"].setText(str(report.get("clean_laps", "—")))
            best_clean = report.get("best_clean_lap_time_s")
            self._report_rows["Best Clean"].setText(
                f"{best_clean:.3f}s" if isinstance(best_clean, (int, float)) else "—"
            )
            self._report_rows["Track"].setText(str(report.get("track", "—")))
            self._report_rows["Car"].setText(str(report.get("car", "—")))
            self._report_rows["Quality"].setText(str(report.get("quality", "—")))
            sync_status = str(report.get("sync_status") or "not_queued")
            self._report_rows["Sync"].setText(sync_status.replace("_", " ").upper())
            path = snap.get("last_save_path") or ""
            self._report_rows["File"].setText(path.split("\\")[-1] if path else "—")


# ═══════════════════════════════════════════════════════════════════════
#  LIVE TELEMETRY
# ═══════════════════════════════════════════════════════════════════════

class LivePanel(QWidget):
    """Operator-focused telemetry diagnostics panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        root = QVBoxLayout(inner)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        # ── Runtime card ─────────────────────────────────────────────
        feed = _card("Runtime", heading="Live Diagnostics")
        fl = feed.layout()

        self._feed_rows: dict[str, QLabel] = {}
        for key in ("Status", "State", "Adapter", "Detection", "Track", "Car", "Lap", "Samples", "Elapsed"):
            val = _add_metric_row(fl, key)
            self._feed_rows[key] = val

        self._stream_badge = QLabel("NO DATA")
        self._stream_badge.setStyleSheet(
            f"padding: 4px 10px; border-radius: 6px; font-weight:700;"
            f" background-color: rgba(250,204,21,0.15); color:{_MARSHAL_YELLOW};"
            " letter-spacing:1px;"
        )
        fl.addWidget(self._stream_badge)

        root.addWidget(feed)

        # ── Signal plots card ───────────────────────────────────────
        plots = _card("Signals", heading="Real-Time Traces")
        pl = plots.layout()

        self._plots: dict[str, TelemetrySparkline] = {
            "speed_kph": TelemetrySparkline(color=_ACID_GREEN, min_value=0.0, max_value=320.0),
            "throttle_pct": TelemetrySparkline(color=_PIT_ORANGE, min_value=0.0, max_value=1.0),
            "brake_pct": TelemetrySparkline(color=_SAFETY_RED, min_value=0.0, max_value=1.0),
            "steering_deg": TelemetrySparkline(color=_MARSHAL_YELLOW, min_value=-540.0, max_value=540.0),
            "rpm": TelemetrySparkline(color="#6CC0FF", min_value=0.0, max_value=11000.0),
        }

        plot_grid = QGridLayout()
        plot_grid.setHorizontalSpacing(10)
        plot_grid.setVerticalSpacing(8)
        plot_items = [
            ("SPEED", "speed_kph"),
            ("THROTTLE", "throttle_pct"),
            ("BRAKE", "brake_pct"),
            ("STEERING", "steering_deg"),
            ("RPM", "rpm"),
        ]
        for row, (label, key) in enumerate(plot_items):
            lbl = QLabel(label)
            lbl.setObjectName("MetricLabel")
            lbl.setMinimumWidth(86)
            plot_grid.addWidget(lbl, row, 0)
            plot_grid.addWidget(self._plots[key], row, 1)

        pl.addLayout(plot_grid)
        root.addWidget(plots)

        # ── Diagnostics card ───────────────────────────────────────
        diag = _card("Health", heading="Capture Quality")
        dl = diag.layout()
        self._diag_rows: dict[str, QLabel] = {}
        for key in (
            "Configured Sample Rate",
            "Measured Sample Rate",
            "Update Frequency",
            "Staleness",
            "Last Error",
        ):
            value = _add_metric_row(dl, key)
            self._diag_rows[key] = value
        root.addWidget(diag)

        # ── Data stream card ─────────────────────────────────────────
        data_card = _card("Data Stream", heading="Live Key Values")
        dsl = data_card.layout()

        self._data_table = QTableWidget(0, 2)
        self._data_table.setHorizontalHeaderLabels(["VARIABLE", "VALUE"])
        self._data_table.horizontalHeader().setStretchLastSection(True)
        self._data_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._data_table.verticalHeader().setVisible(False)
        self._data_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._data_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._data_table.setMinimumHeight(180)
        dsl.addWidget(self._data_table)

        root.addWidget(data_card)

        root.addStretch(1)
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    _LIVE_KEYS = [
        ("speed_kph", "Speed (km/h)"),
        ("rpm", "RPM"),
        ("gear", "Gear"),
        ("throttle_pct", "Throttle"),
        ("brake_pct", "Brake"),
        ("steering_deg", "Steering °"),
        ("lap_number", "Lap"),
        ("lap_time_s", "Lap Time"),
        ("live_delta_s", "Live Delta"),
        ("best_lap_time_s", "Best Lap"),
        ("sector_1_time_s", "Sector 1"),
        ("sector_2_time_s", "Sector 2"),
        ("sector_3_time_s", "Sector 3"),
        ("fuel_level", "Fuel Level"),
        ("fuel_per_lap_l", "Fuel / Lap"),
        ("laps_remaining_est", "Laps Left"),
        ("session_status", "Session Status"),
        ("flag_state", "Flag"),
        ("brake_bias_pct", "Brake Bias"),
        ("engine_map", "Map"),
        ("abs_level", "ABS Level"),
        ("tc_level", "TC Level"),
    ]

    def update_snapshot(self, snap: dict) -> None:
        status = str(snap.get("status", "Idle"))
        self._feed_rows["Status"].setText(status.upper())
        color = _STATUS_COLORS.get(status, _STEEL)
        self._feed_rows["Status"].setStyleSheet(
            f"font-size:15px; font-weight:700;"
            f" font-family:'Consolas','Space Mono',monospace; color:{color};"
        )

        live = snap.get("live") or {}
        self._feed_rows["State"].setText(str(snap.get("raw_state") or "—"))
        self._feed_rows["Adapter"].setText(str(snap.get("adapter_health") or "—"))
        self._feed_rows["Detection"].setText(str(snap.get("sim_detection_status") or "—"))
        self._feed_rows["Track"].setText(str(live.get("track_name") or "—"))
        self._feed_rows["Car"].setText(str(live.get("car_name") or "—"))
        self._feed_rows["Lap"].setText(str(live.get("lap_number") or "—"))

        samples = snap.get("sample_count", 0)
        elapsed = snap.get("elapsed_s", 0)
        self._feed_rows["Samples"].setText(f"{samples:,}" if samples else "—")
        mins, secs = divmod(int(elapsed), 60)
        self._feed_rows["Elapsed"].setText(f"{mins}:{secs:02d}" if elapsed else "—")

        cfg_hz = snap.get("sample_rate_hz_config")
        self._diag_rows["Configured Sample Rate"].setText(
            f"{cfg_hz:.2f} Hz" if isinstance(cfg_hz, (int, float)) else "—"
        )
        rate_hz = snap.get("sample_rate_hz_est")
        self._diag_rows["Measured Sample Rate"].setText(
            f"{rate_hz:.2f} Hz" if isinstance(rate_hz, (int, float)) else "—"
        )
        upd_hz = snap.get("update_hz_est")
        self._diag_rows["Update Frequency"].setText(
            f"{upd_hz:.2f} Hz" if isinstance(upd_hz, (int, float)) else "—"
        )
        stale = snap.get("data_staleness_s")
        self._diag_rows["Staleness"].setText(
            f"{stale:.2f}s" if isinstance(stale, (int, float)) else "—"
        )
        self._diag_rows["Last Error"].setText(str(snap.get("last_error") or "—"))

        stream_status = str(snap.get("stream_status") or "no_data")
        if stream_status == "disconnect":
            self._stream_badge.setText("DISCONNECT")
            self._stream_badge.setStyleSheet(
                f"padding: 4px 10px; border-radius: 6px; font-weight:700;"
                f" background-color: rgba(255,42,42,0.15); color:{_SAFETY_RED}; letter-spacing:1px;"
            )
        elif stream_status == "invalid_stream":
            self._stream_badge.setText("INVALID STREAM")
            self._stream_badge.setStyleSheet(
                f"padding: 4px 10px; border-radius: 6px; font-weight:700;"
                f" background-color: rgba(255,42,42,0.15); color:{_SAFETY_RED}; letter-spacing:1px;"
            )
        elif stream_status == "stale_data":
            self._stream_badge.setText("STALE DATA")
            self._stream_badge.setStyleSheet(
                f"padding: 4px 10px; border-radius: 6px; font-weight:700;"
                f" background-color: rgba(250,204,21,0.15); color:{_MARSHAL_YELLOW}; letter-spacing:1px;"
            )
        elif stream_status == "no_data":
            self._stream_badge.setText("NO DATA")
            self._stream_badge.setStyleSheet(
                f"padding: 4px 10px; border-radius: 6px; font-weight:700;"
                f" background-color: rgba(148,148,148,0.18); color:{_STEEL}; letter-spacing:1px;"
            )
        else:
            self._stream_badge.setText("STREAM OK")
            self._stream_badge.setStyleSheet(
                f"padding: 4px 10px; border-radius: 6px; font-weight:700;"
                f" background-color: rgba(34,197,94,0.14); color:{_ACID_GREEN}; letter-spacing:1px;"
            )

        self._plots["speed_kph"].push(_as_float(live.get("speed_kph")))
        self._plots["throttle_pct"].push(_as_float(live.get("throttle_pct")))
        self._plots["brake_pct"].push(_as_float(live.get("brake_pct")))
        self._plots["steering_deg"].push(_as_float(live.get("steering_deg")))
        self._plots["rpm"].push(_as_float(live.get("rpm")))

        self._data_table.setRowCount(len(self._LIVE_KEYS))
        for i, (key, display) in enumerate(self._LIVE_KEYS):
            raw = live.get(key)
            if isinstance(raw, float):
                text = f"{raw:.2f}"
            elif raw is not None:
                text = str(raw)
            else:
                text = "—"
            name_item = QTableWidgetItem(display)
            val_item = QTableWidgetItem(text)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            val_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._data_table.setItem(i, 0, name_item)
            self._data_table.setItem(i, 1, val_item)


def _as_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _live_sample_token(snapshot: dict[str, object]) -> tuple[object, ...] | None:
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


# ═══════════════════════════════════════════════════════════════════════
#  LOGS VIEWER
# ═══════════════════════════════════════════════════════════════════════

class LogsPanel(QWidget):
    """Diagnostics-first log viewer with filtering, search, and export hooks."""

    export_support_requested = Signal(bool)

    _MAX_LINES = 3000
    _COL_TIME = 0
    _COL_LEVEL = 1
    _COL_SUBSYSTEM = 2
    _COL_SIM = 3
    _COL_ADAPTER = 4
    _COL_MODULE = 5
    _COL_MESSAGE = 6

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._auto_scroll = True
        self._entries: list[dict[str, object]] = []
        self._current_session_epoch: float | None = None
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        card = _card("Application Logs", heading="Diagnostics Console")
        cl = card.layout()

        # Filters row
        filters = QHBoxLayout()
        filters.setSpacing(8)

        self.filter_severity = QComboBox()
        self.filter_severity.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.filter_subsystem = QComboBox()
        self.filter_subsystem.addItems(["ALL", "system", "adapter", "session", "storage", "ui"])
        self.filter_simulator = QComboBox()
        self.filter_simulator.addItems(["ALL", "iRacing", "Assetto Corsa", "ACC", "Le Mans Ultimate", "-"])
        self.filter_adapter = QComboBox()
        self.filter_adapter.addItems(["ALL", "IRacingAdapter", "AssettoCorsaAdapter", "ACCAdapter", "LMUAdapter", "LMURecordingImport", "-"])
        self.filter_scope = QComboBox()
        self.filter_scope.addItems(["ALL LOGS", "CURRENT SESSION ONLY"])
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search logs...")

        filters.addWidget(self.filter_severity)
        filters.addWidget(self.filter_subsystem)
        filters.addWidget(self.filter_simulator)
        filters.addWidget(self.filter_adapter)
        filters.addWidget(self.filter_scope)
        filters.addWidget(self.search, 1)
        cl.addLayout(filters)

        # Actions row
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self._btn_clear = QPushButton("CLEAR")
        self._btn_clear.setObjectName("DangerButton")
        self._btn_scroll = QPushButton("AUTO-SCROLL: ON")
        self._btn_copy_selected = QPushButton("COPY SELECTED")
        self._btn_copy_visible = QPushButton("COPY VISIBLE")
        self._btn_export_bundle = QPushButton("EXPORT SUPPORT BUNDLE")
        self._btn_export_bundle.setObjectName("PrimaryButton")
        actions.addWidget(self._btn_clear)
        actions.addWidget(self._btn_scroll)
        actions.addWidget(self._btn_copy_selected)
        actions.addWidget(self._btn_copy_visible)
        actions.addWidget(self._btn_export_bundle)
        actions.addStretch(1)
        cl.addLayout(actions)

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
        cl.addWidget(self._table, 1)

        root.addWidget(card, 1)

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

    def append_line(self, text: str) -> None:
        # Backward-compatible sink for plain line logging.
        self.append_event({
            "time": text[:8] if len(text) >= 8 else "--:--:--",
            "severity": "INFO",
            "subsystem": "system",
            "simulator": "-",
            "module": "legacy",
            "message": text,
            "current_session": self._current_session_epoch is not None,
        })

    def append_event(self, event: dict) -> None:
        entry = {
            "time": str(event.get("time") or "--:--:--"),
            "severity": str(event.get("severity") or "INFO").upper(),
            "subsystem": str(event.get("subsystem") or "system"),
            "simulator": str(event.get("simulator") or "-"),
            "adapter": str(event.get("adapter") or "-"),
            "module": str(event.get("module") or "-"),
            "message": str(event.get("message") or ""),
            "current_session": bool(event.get("current_session")),
        }
        self._entries.append(entry)
        if len(self._entries) > self._MAX_LINES:
            self._entries = self._entries[-self._MAX_LINES:]
        self._refresh_view()

    def update_context(self, snap: dict) -> None:
        started = snap.get("raw_state")
        if started in {"arming", "recording", "finalizing"} and snap.get("elapsed_s"):
            self._current_session_epoch = time.time() - int(snap.get("elapsed_s") or 0)
        elif started in {"idle", "waiting_for_valid_session", "failed", "ready_for_review"}:
            self._current_session_epoch = None

    def _refresh_view(self) -> None:
        visible = [entry for entry in self._entries if self._matches_filters(entry)]
        self._table.setRowCount(len(visible))
        for row, entry in enumerate(visible):
            self._set_row(row, entry)

        if self._auto_scroll and self._table.rowCount() > 0:
            self._table.scrollToBottom()

    def _matches_filters(self, entry: dict[str, object]) -> bool:
        sev = self.filter_severity.currentText()
        if sev != "ALL" and str(entry.get("severity")) != sev:
            return False

        subsystem = self.filter_subsystem.currentText()
        if subsystem != "ALL" and str(entry.get("subsystem")) != subsystem:
            return False

        simulator = self.filter_simulator.currentText()
        if simulator != "ALL" and str(entry.get("simulator")) != simulator:
            return False

        adapter = self.filter_adapter.currentText()
        if adapter != "ALL" and str(entry.get("adapter")) != adapter:
            return False

        scope = self.filter_scope.currentText()
        if scope == "CURRENT SESSION ONLY" and not bool(entry.get("current_session")):
            return False

        query = self.search.text().strip().lower()
        if query:
            hay = " ".join(
                str(entry.get(k, "")).lower()
                for k in ("time", "severity", "subsystem", "simulator", "adapter", "module", "message")
            )
            if query not in hay:
                return False

        return True

    def _set_row(self, row: int, entry: dict[str, object]) -> None:
        cols = [
            str(entry.get("time") or "--:--:--"),
            str(entry.get("severity") or "INFO"),
            str(entry.get("subsystem") or "system"),
            str(entry.get("simulator") or "-"),
            str(entry.get("adapter") or "-"),
            str(entry.get("module") or "-"),
            str(entry.get("message") or ""),
        ]
        for col, text in enumerate(cols):
            item = QTableWidgetItem(text)
            if col < self._COL_MESSAGE:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            if col == self._COL_LEVEL:
                level = text.upper()
                if level in {"ERROR", "CRITICAL"}:
                    item.setForeground(QColor(_SAFETY_RED))
                elif level == "WARNING":
                    item.setForeground(QColor(_MARSHAL_YELLOW))
                elif level == "DEBUG":
                    item.setForeground(QColor(_STEEL))
                else:
                    item.setForeground(QColor(_ACID_GREEN))
            elif col == self._COL_SUBSYSTEM:
                subsystem_color = {
                    "system": _CHALK,
                    "adapter": _PIT_ORANGE,
                    "session": _ACID_GREEN,
                    "storage": _MARSHAL_YELLOW,
                    "ui": _STEEL,
                }.get(text.lower(), _CHALK)
                item.setForeground(QColor(subsystem_color))

            self._table.setItem(row, col, item)

    def _copy_selected(self) -> None:
        rows = sorted({idx.row() for idx in self._table.selectedIndexes()})
        if not rows:
            return
        lines = [self._row_to_text(row) for row in rows]
        QApplication.clipboard().setText("\n".join(lines))

    def _copy_visible(self) -> None:
        lines = [self._row_to_text(row) for row in range(self._table.rowCount())]
        if lines:
            QApplication.clipboard().setText("\n".join(lines))

    def _row_to_text(self, row: int) -> str:
        values: list[str] = []
        for col in range(self._table.columnCount()):
            item = self._table.item(row, col)
            values.append(item.text() if item else "")
        return " | ".join(values)

    def _clear(self) -> None:
        self._entries.clear()
        self._table.setRowCount(0)

    def _toggle_scroll(self) -> None:
        self._auto_scroll = not self._auto_scroll
        self._btn_scroll.setText("AUTO-SCROLL: ON" if self._auto_scroll else "AUTO-SCROLL: OFF")

    def _export_bundle(self) -> None:
        current_session_only = self.filter_scope.currentText() == "CURRENT SESSION ONLY"
        self.export_support_requested.emit(current_session_only)


# ═══════════════════════════════════════════════════════════════════════
#  SESSION REVIEW
# ═══════════════════════════════════════════════════════════════════════

class ReviewPanel(QWidget):
    """Saved-session review screen backed by bundle artifacts."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._review: dict[str, object] | None = None
        self._build()

    def _build(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        root = QVBoxLayout(inner)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        summary = _card("Session Review", heading="Recorded Session")
        sl = summary.layout()

        self._status_value = _metric_value("READY", mono=False)
        self._quality_value = _metric_value("—", mono=False)
        self._quality_value.setWordWrap(True)

        sl.addWidget(_metric_label("Session Status"))
        sl.addWidget(self._status_value)
        sl.addWidget(_separator())
        sl.addWidget(_metric_label("Quality Classification"))
        sl.addWidget(self._quality_value)
        root.addWidget(summary)

        issues = _card("Warnings", heading="Review Attention")
        il = issues.layout()
        self._issues_summary = QLabel("No quality warnings or errors recorded")
        self._issues_summary.setStyleSheet(f"font-size:13px; font-weight:700; color:{_MARSHAL_YELLOW};")
        self._issues_text = QTextEdit()
        self._issues_text.setReadOnly(True)
        self._issues_text.setMinimumHeight(140)
        il.addWidget(self._issues_summary)
        il.addWidget(self._issues_text)
        root.addWidget(issues)

        details = _card("Session Details", heading="Bundle Summary")
        dl = details.layout()
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
            value = _add_metric_row(dl, key)
            if key == "Local Folder":
                value.setWordWrap(True)
                value.setStyleSheet(f"font-size:12px; font-weight:600; color:{_CHALK};")
            self._detail_rows[key] = value
        root.addWidget(details)

        actions = _card("Actions", heading="Review Workflow")
        al = actions.layout()
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_open_folder = QPushButton("OPEN FOLDER")
        self.btn_open_folder.setObjectName("PrimaryButton")
        self.btn_queue_sync = QPushButton("QUEUE SYNC")
        self.btn_reprocess = QPushButton("REPROCESS SESSION")
        self.btn_ignore = QPushButton("MARK IGNORED")
        self.btn_delete = QPushButton("DELETE LOCAL COPY")
        self.btn_delete.setObjectName("DangerButton")
        self.btn_return = QPushButton("RETURN TO HISTORY")
        for button in (
            self.btn_open_folder,
            self.btn_queue_sync,
            self.btn_reprocess,
            self.btn_ignore,
            self.btn_delete,
            self.btn_return,
        ):
            btn_row.addWidget(button)
        btn_row.addStretch(1)
        al.addLayout(btn_row)
        root.addWidget(actions)

        root.addStretch(1)
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def update_review(self, review: dict) -> None:
        self._review = review
        status = str(review.get("session_status") or "Ready for Review")
        quality = str(review.get("quality_classification") or "-")
        warnings = list(review.get("warnings") or [])
        errors = list(review.get("errors") or [])

        status_color = _PIT_ORANGE if review.get("review_status") != "ignored" else _STEEL
        quality_color = _quality_color(quality)

        self._status_value.setText(status.upper())
        self._status_value.setStyleSheet(f"font-size:18px; font-weight:700; color:{status_color};")
        self._quality_value.setText(quality.replace("_", " ").upper())
        self._quality_value.setStyleSheet(f"font-size:18px; font-weight:700; color:{quality_color};")

        issue_lines: list[str] = []
        if errors:
            issue_lines.append("Errors")
            issue_lines.extend(f"- {line}" for line in errors)
        if warnings:
            if issue_lines:
                issue_lines.append("")
            issue_lines.append("Warnings")
            issue_lines.extend(f"- {line}" for line in warnings)
        if issue_lines:
            self._issues_summary.setText(
                f"{len(errors)} error(s)  •  {len(warnings)} warning(s)"
            )
            self._issues_summary.setStyleSheet(
                f"font-size:13px; font-weight:700; color:{_SAFETY_RED if errors else _MARSHAL_YELLOW};"
            )
            self._issues_text.setPlainText("\n".join(issue_lines))
        else:
            self._issues_summary.setText("No quality warnings or errors recorded")
            self._issues_summary.setStyleSheet(f"font-size:13px; font-weight:700; color:{_ACID_GREEN};")
            self._issues_text.setPlainText("Session bundle passed review checks without warnings.")

        self._detail_rows["Simulator"].setText(str(review.get("simulator") or "—"))
        self._detail_rows["Track"].setText(str(review.get("track") or "—"))
        self._detail_rows["Car"].setText(str(review.get("car") or "—"))
        self._detail_rows["Session Type"].setText(str(review.get("session_type") or "—"))
        self._detail_rows["Duration"].setText(_format_duration(review.get("duration_s")))
        self._detail_rows["Sample Count"].setText(f"{int(review.get('sample_count') or 0):,}")
        self._detail_rows["Total Laps"].setText(str(review.get("total_laps") or 0))
        self._detail_rows["Valid Laps"].setText(str(review.get("valid_laps") or 0))
        self._detail_rows["Clean Laps"].setText(str(review.get("clean_laps") or 0))
        self._detail_rows["Best Lap"].setText(_format_lap_time(review.get("best_lap_time_s")))
        self._detail_rows["Best Clean Lap"].setText(_format_lap_time(review.get("best_clean_lap_time_s")))
        self._detail_rows["Local Folder"].setText(str(review.get("local_folder_path") or "—"))

        ignored = review.get("review_status") == "ignored"
        self.btn_ignore.setText("RESTORE SESSION" if ignored else "MARK IGNORED")

        sync_status = str(review.get("sync_status") or "not_queued")
        if sync_status == "synced":
            self.btn_queue_sync.setText("SYNCED")
            self.btn_queue_sync.setEnabled(False)
        elif sync_status == "queued":
            self.btn_queue_sync.setText("SYNC QUEUED")
            self.btn_queue_sync.setEnabled(False)
        elif sync_status == "sync_blocked":
            self.btn_queue_sync.setText("SYNC BLOCKED")
            self.btn_queue_sync.setEnabled(False)
        else:
            self.btn_queue_sync.setText("QUEUE SYNC")
            self.btn_queue_sync.setEnabled(True)

    def current_path(self) -> str | None:
        if not self._review:
            return None
        path = self._review.get("folder") or self._review.get("local_folder_path")
        return str(path) if path else None


# ═══════════════════════════════════════════════════════════════════════
#  SESSION HISTORY
# ═══════════════════════════════════════════════════════════════════════

class HistoryPanel(QWidget):
    """Advanced session archive with filtering, sorting, and management."""

    # Extended columns for comprehensive archive view
    _COLUMNS = (
        "Date",
        "Simulator",
        "Track",
        "Car",
        "Type",
        "Duration",
        "Laps",
        "Clean",
        "Best Lap",
        "Quality",
        "Review",
        "Sync",
        "Folder",
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sessions: list[dict] = []
        self._filtered_sessions: list[dict] = []
        self._filters = {
            "simulator": None,
            "track": None,
            "car": None,
            "quality": None,
            "date_from": None,
            "date_to": None,
        }
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        card = _card("Session Archive", heading="History")
        cl = card.layout()

        # ── Filter Bar ─────────────────────────────────────────────
        filter_frame = QFrame()
        filter_frame.setObjectName("FilterFrame")
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(8)

        filter_label = _metric_label("Filters")
        filter_layout.addWidget(filter_label)

        from PySide6.QtWidgets import QComboBox, QDateEdit
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
        self.btn_clear_filters = QPushButton("Clear Filters")
        self.btn_clear_filters.setObjectName("SecondaryButton")
        self.btn_clear_filters.clicked.connect(self._clear_filters)
        filter_layout.addWidget(self.btn_clear_filters)
        
        cl.addWidget(filter_frame)

        # ── Action Bar ─────────────────────────────────────────────
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        self.btn_refresh = QPushButton("REFRESH")
        self.btn_refresh.setObjectName("PrimaryButton")
        self.btn_review = QPushButton("VIEW REVIEW")
        self.btn_open = QPushButton("OPEN FOLDER")
        self.btn_reprocess = QPushButton("REPROCESS")
        self.btn_marked = QPushButton("MARK IGNORED")
        self.btn_queue_sync = QPushButton("QUEUE SYNC")
        self.btn_export = QPushButton("EXPORT CSV")
        self.btn_copy_id = QPushButton("COPY ID")
        self.btn_delete = QPushButton("DELETE")

        for btn in [self.btn_review, self.btn_open, self.btn_reprocess,
                    self.btn_marked, self.btn_queue_sync, self.btn_export,
                    self.btn_copy_id, self.btn_delete]:
            btn.setObjectName("SecondaryButton")

        action_layout.addWidget(self.btn_refresh)
        action_layout.addWidget(self.btn_review)
        action_layout.addWidget(self.btn_open)
        action_layout.addWidget(self.btn_reprocess)
        action_layout.addWidget(self.btn_marked)
        action_layout.addWidget(self.btn_queue_sync)
        action_layout.addWidget(self.btn_export)
        action_layout.addWidget(self.btn_copy_id)
        action_layout.addWidget(self.btn_delete)
        action_layout.addStretch(1)
        
        cl.addLayout(action_layout)

        # ── Data Table ─────────────────────────────────────────────
        self._table = QTableWidget(0, len(self._COLUMNS))
        self._table.setHorizontalHeaderLabels(list(self._COLUMNS))
        hdr = self._table.horizontalHeader()
        hdr.setStretchLastSection(False)
        
        # Set column widths with smart sizing
        col_widths = {
            0: 135,  # Date
            1: 120,  # Simulator
            2: 120,  # Track
            3: 100,  # Car
            4: 80,   # Type
            5: 80,   # Duration
            6: 60,   # Laps
            7: 60,   # Clean
            8: 80,   # Best Lap
            9: 110,  # Quality
            10: 90,  # Review
            11: 110, # Sync
            12: 0,   # Folder (hidden, full path storage)
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
        
        # Enable word wrap and better row height
        self._table.setWordWrap(False)
        self._table.verticalHeader().setDefaultSectionSize(24)
        
        cl.addWidget(self._table, 1)

        # ── Empty State ────────────────────────────────────────────
        self._empty = QLabel("No sessions recorded yet")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(f"color:{_STEEL}; font-size:13px; padding:40px;")
        cl.addWidget(self._empty)

        root.addWidget(card, 1)

    def update_sessions(self, sessions: list[dict]) -> None:
        """Update session list and refresh filter options."""
        self._sessions = sessions
        self._update_filter_options()
        self._apply_filters()

    def _update_filter_options(self) -> None:
        """Update filter dropdown options based on available sessions."""
        sims = sorted(set(s.get("sim") for s in self._sessions if s.get("sim") and s.get("sim") != "-"))
        tracks = sorted(set(s.get("track") for s in self._sessions if s.get("track") and s.get("track") != "-"))
        cars = sorted(set(s.get("car") for s in self._sessions if s.get("car") and s.get("car") != "-"))
        
        # Update simulator filter
        current_sim = self.filter_sim.currentText()
        self.filter_sim.blockSignals(True)
        self.filter_sim.clear()
        self.filter_sim.addItem("All Simulators")
        for sim in sims:
            self.filter_sim.addItem(sim)
        idx = self.filter_sim.findText(current_sim)
        if idx >= 0:
            self.filter_sim.setCurrentIndex(idx)
        self.filter_sim.blockSignals(False)

        # Update track filter
        current_track = self.filter_track.currentText()
        self.filter_track.blockSignals(True)
        self.filter_track.clear()
        self.filter_track.addItem("All Tracks")
        for track in tracks:
            self.filter_track.addItem(track)
        idx = self.filter_track.findText(current_track)
        if idx >= 0:
            self.filter_track.setCurrentIndex(idx)
        self.filter_track.blockSignals(False)

        # Update car filter
        current_car = self.filter_car.currentText()
        self.filter_car.blockSignals(True)
        self.filter_car.clear()
        self.filter_car.addItem("All Cars")
        for car in cars:
            self.filter_car.addItem(car)
        idx = self.filter_car.findText(current_car)
        if idx >= 0:
            self.filter_car.setCurrentIndex(idx)
        self.filter_car.blockSignals(False)

    def _apply_filters(self) -> None:
        """Apply active filters to session list."""
        sim_filter = self.filter_sim.currentText()
        track_filter = self.filter_track.currentText()
        car_filter = self.filter_car.currentText()
        quality_filter = self.filter_quality.currentText()

        self._filtered_sessions = [
            s for s in self._sessions
            if (sim_filter == "All Simulators" or s.get("sim") == sim_filter)
            and (track_filter == "All Tracks" or s.get("track") == track_filter)
            and (car_filter == "All Cars" or s.get("car") == car_filter)
            and self._matches_quality_filter(s, quality_filter)
        ]

        self._populate_table()

    def _matches_quality_filter(self, session: dict, filter_text: str) -> bool:
        """Check if session matches quality filter."""
        if filter_text == "All Quality":
            return True
        quality = session.get("quality", "").lower()
        if filter_text == "Accepted" and quality == "accepted":
            return True
        if filter_text == "Warnings" and quality == "accepted_with_warnings":
            return True
        if filter_text == "Rejected" and quality == "rejected":
            return True
        if filter_text == "Unknown" and quality not in ["accepted", "accepted_with_warnings", "rejected"]:
            return True
        return False

    def _clear_filters(self) -> None:
        """Reset all filters to default."""
        self.filter_sim.blockSignals(True)
        self.filter_track.blockSignals(True)
        self.filter_car.blockSignals(True)
        self.filter_quality.blockSignals(True)
        
        self.filter_sim.setCurrentIndex(0)
        self.filter_track.setCurrentIndex(0)
        self.filter_car.setCurrentIndex(0)
        self.filter_quality.setCurrentIndex(0)
        
        self.filter_sim.blockSignals(False)
        self.filter_track.blockSignals(False)
        self.filter_car.blockSignals(False)
        self.filter_quality.blockSignals(False)
        
        self._apply_filters()

    def _populate_table(self) -> None:
        """Populate table with filtered sessions."""
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(self._filtered_sessions))

        col_map = {
            "ended_display": 0,    # Date
            "sim": 1,              # Simulator
            "track": 2,            # Track
            "car": 3,              # Car
            "session_type": 4,     # Type
            "duration_display": 5, # Duration
            "total_laps": 6,       # Laps
            "clean_laps": 7,       # Clean
            "best_lap": 8,         # Best Lap
            "quality": 9,          # Quality
            "review_status": 10,   # Review workflow status
            "sync_status": 11,     # Sync queue status
            "folder": 12,          # Folder (hidden)
        }

        for r, session in enumerate(self._filtered_sessions):
            for col_name, col_idx in col_map.items():
                value = session.get(col_name, "—")
                
                # Format special columns
                if col_name == "total_laps":
                    value = str(value) if value and value != "—" else "0"
                elif col_name == "clean_laps":
                    value = str(value) if value and value != "—" else "0"
                elif col_name == "review_status":
                    if value == "ignored":
                        value = "⊘ IGNORED"
                    else:
                        value = "✓ Ready"
                elif col_name == "sync_status":
                    value = str(value or "not_queued").replace("_", " ").upper()
                
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                
                # Color quality column based on classification
                if col_name == "quality":
                    quality_lower = str(session.get("quality", "")).lower()
                    if "accepted_with_warnings" in quality_lower or "warnings" in quality_lower.lower():
                        color = _MARSHAL_YELLOW
                    elif "rejected" in quality_lower:
                        color = _SAFETY_RED
                    elif "accepted" in quality_lower:
                        color = _ACID_GREEN
                    else:
                        color = _STEEL
                    item.setForeground(QColor(color))
                
                # Color status column
                if col_name == "review_status":
                    if "IGNORED" in str(value):
                        item.setForeground(QColor(_MARSHAL_YELLOW))
                    else:
                        item.setForeground(QColor(_ACID_GREEN))
                if col_name == "sync_status":
                    sync_text = str(value).lower()
                    if "synced" in sync_text:
                        item.setForeground(QColor(_ACID_GREEN))
                    elif "failed" in sync_text or "blocked" in sync_text:
                        item.setForeground(QColor(_SAFETY_RED))
                    elif "ready" in sync_text or "queued" in sync_text:
                        item.setForeground(QColor(_MARSHAL_YELLOW))
                    else:
                        item.setForeground(QColor(_STEEL))
                
                self._table.setItem(r, col_idx, item)

        self._table.setSortingEnabled(True)
        has_data = len(self._filtered_sessions) > 0
        self._table.setVisible(has_data)
        self._empty.setVisible(not has_data)

    def selected_folder(self) -> str | None:
        """Get folder path of selected session."""
        row = self._table.currentRow()
        if 0 <= row < len(self._filtered_sessions):
            return self._filtered_sessions[row].get("folder")
        return None

    def selected_session_id(self) -> str | None:
        """Get session ID (folder name) of selected session."""
        row = self._table.currentRow()
        if 0 <= row < len(self._filtered_sessions):
            return self._filtered_sessions[row].get("session_id")
        return None

    def selected_session_name(self) -> str | None:
        """Get name of selected session."""
        row = self._table.currentRow()
        if 0 <= row < len(self._filtered_sessions):
            return self._filtered_sessions[row].get("name")
        return None


def _format_duration(value: object) -> str:
    if not isinstance(value, (int, float)) or value <= 0:
        return "—"
    minutes, seconds = divmod(int(value), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _format_datetime_short(value: object) -> str:
    if not isinstance(value, (int, float)) or value <= 0:
        return "â€”"
    try:
        return datetime.fromtimestamp(float(value)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "â€”"


def _format_lap_time(value: object) -> str:
    return f"{value:.3f}s" if isinstance(value, (int, float)) else "—"


def _format_percent(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "—"
    return f"{float(value):.0%}"


def _format_whole_number(value: object, *, suffix: str = "") -> str:
    if not isinstance(value, (int, float)):
        return "—"
    return f"{float(value):.0f}{suffix}"


def _format_signed_number(value: object, *, suffix: str = "") -> str:
    if not isinstance(value, (int, float)):
        return "—"
    return f"{float(value):.2f}{suffix}"


def _format_delta(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "—"
    return f"{float(value):+.3f}s"


def _format_gear(value: object) -> str:
    if not isinstance(value, int):
        return "—"
    if value < 0:
        return "R"
    if value == 0:
        return "N"
    return str(value)


def _format_alert_items(items: object) -> str:
    if not isinstance(items, list) or not items:
        return f"<span style='color:{_STEEL};'>No active alerts.</span>"
    lines: list[str] = []
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity") or "info").lower()
        title = html.escape(str(item.get("title") or "Alert"))
        detail = html.escape(str(item.get("detail") or ""))
        color = _STEEL
        if severity == "error":
            color = _SAFETY_RED
        elif severity == "warning":
            color = _MARSHAL_YELLOW
        lines.append(
            f"<div style='margin-bottom:6px;'><span style='color:{color}; font-weight:800;'>{title}</span>"
            f"<br><span style='color:{_CHALK};'>{detail}</span></div>"
        )
    return "".join(lines) or f"<span style='color:{_STEEL};'>No active alerts.</span>"


def _format_coaching_items(items: object, active_corner: object) -> str:
    if not isinstance(items, list) or not items:
        if isinstance(active_corner, str) and active_corner:
            corner = html.escape(active_corner)
            return f"<span style='color:{_STEEL};'>Building live reference through {corner}.</span>"
        return f"<span style='color:{_STEEL};'>Complete a clean reference lap to unlock live coaching.</span>"
    lines: list[str] = []
    for item in items[:3]:
        if not isinstance(item, dict):
            continue
        title = html.escape(str(item.get("title") or "Coaching"))
        detail = html.escape(str(item.get("detail") or ""))
        lines.append(
            f"<div style='margin-bottom:6px;'><span style='color:{_PIT_ORANGE}; font-weight:800;'>{title}</span>"
            f"<br><span style='color:{_CHALK};'>{detail}</span></div>"
        )
    return "".join(lines) or f"<span style='color:{_STEEL};'>Complete a clean reference lap to unlock live coaching.</span>"


def _format_diag_metric(metric: object) -> str:
    if not isinstance(metric, dict):
        return "No data yet."
    label = str(metric.get("label") or "No data").strip()
    detail = str(metric.get("detail") or "").strip()
    score = metric.get("score")
    prefix = label
    if isinstance(score, (int, float)):
        prefix = f"{label} {int(round(float(score)))}/100"
    if detail:
        return f"{prefix} | {detail}"
    return prefix or "No data yet."


def _format_diag_flags(items: object) -> str:
    if not isinstance(items, list) or not items:
        return f"<span style='color:{_STEEL};'>No hardware/input warnings.</span>"
    lines: list[str] = []
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity") or "info").lower()
        color = _STEEL
        if severity == "error":
            color = _SAFETY_RED
        elif severity == "warning":
            color = _MARSHAL_YELLOW
        title = html.escape(str(item.get("title") or "Flag"))
        detail = html.escape(str(item.get("detail") or ""))
        lines.append(
            f"<div style='margin-bottom:6px;'><span style='color:{color}; font-weight:800;'>{title}</span>"
            f"<br><span style='color:{_CHALK};'>{detail}</span></div>"
        )
    return "".join(lines) or f"<span style='color:{_STEEL};'>No hardware/input warnings.</span>"


def _format_summary_text(value: object) -> str:
    if value is None:
        return "â€”"
    text = str(value).strip()
    if not text:
        return "â€”"
    return text


def _quality_color(quality: str) -> str:
    quality = quality.lower()
    if quality == "accepted":
        return _ACID_GREEN
    if quality == "accepted_with_warnings":
        return _MARSHAL_YELLOW
    if quality == "rejected":
        return _SAFETY_RED
    return _PIT_ORANGE
