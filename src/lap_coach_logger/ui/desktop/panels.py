"""Reusable desktop panels following the LAP COACH brand charter."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QFrame,
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

# ── Charter colours (local aliases) ──────────────────────────────────
_ASPHALT = "#000000"
_CONCRETE = "#141414"
_STEEL = "#949494"
_CHALK = "#F0EDE5"
_PIT_ORANGE = "#C9A84C"
_ACID_GREEN = "#22C55E"
_SAFETY_RED = "#FF2A2A"
_MARSHAL_YELLOW = "#FACC15"

_STATUS_COLORS = {
    "Idle": _STEEL,
    "Simulator Detected": _PIT_ORANGE,
    "Waiting": _PIT_ORANGE,
    "Arming": _MARSHAL_YELLOW,
    "Recording": _ACID_GREEN,
    "Finalizing": _MARSHAL_YELLOW,
    "Ready for Review": _PIT_ORANGE,
    "Failed": _SAFETY_RED,
    "Error": _SAFETY_RED,
}


# ── Helpers ──────────────────────────────────────────────────────────

def _card(section_title: str, *, heading: str | None = None) -> QFrame:
    """Create a Card frame with an uppercase section label and optional heading."""
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(10)

    sec = QLabel(section_title.upper())
    sec.setObjectName("SectionTitle")
    layout.addWidget(sec)

    if heading:
        h = QLabel(heading)
        h.setObjectName("CardHeading")
        layout.addWidget(h)

    return frame


def _metric_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("MetricLabel")
    return lbl


def _metric_value(text: str = "—", *, mono: bool = True) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("MetricValue")
    if mono:
        lbl.setStyleSheet(
            "font-size:15px; font-weight:700;"
            " font-family:'Consolas','Space Mono',monospace;"
            f" color:{_CHALK};"
        )
    else:
        lbl.setStyleSheet(f"font-size:14px; font-weight:600; color:{_CHALK};")
    return lbl


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color: rgba(240, 237, 229, 0.06);")
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


# ═══════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════════════════════════════

class DashboardPanel(QWidget):
    """Primary dashboard with hero status, live recording card, and session report."""

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
        self.btn_start = QPushButton("START MONITORING")
        self.btn_start.setObjectName("PrimaryButton")
        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setObjectName("DangerButton")
        self.btn_output = QPushButton("OUTPUT")
        self.btn_logs = QPushButton("LOGS")
        self.btn_config = QPushButton("CONFIG")
        self.btn_settings = QPushButton("SETTINGS")
        for b in (self.btn_start, self.btn_stop, self.btn_output,
                  self.btn_logs, self.btn_config, self.btn_settings):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        hl.addLayout(btn_row)

        root.addWidget(hero)

        # ── Live recording card ──────────────────────────────────────
        live_card = _card("Telemetry", heading="Live Recording")
        ll = live_card.layout()

        self._live_rows: dict[str, QLabel] = {}
        for key in ("Track", "Car", "Lap", "Speed", "Throttle", "Brake", "Gear"):
            val = _add_metric_row(ll, key)
            self._live_rows[key] = val

        root.addWidget(live_card)

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

        # Live telemetry
        live = snap.get("live") or {}
        self._live_rows["Track"].setText(str(live.get("track_name") or "—"))
        self._live_rows["Car"].setText(str(live.get("car_name") or "—"))
        self._live_rows["Lap"].setText(str(live.get("lap_number") or "—"))
        speed = live.get("speed_kph")
        self._live_rows["Speed"].setText(f"{speed:.0f} km/h" if speed else "—")
        throttle = live.get("throttle_pct")
        self._live_rows["Throttle"].setText(f"{throttle:.0%}" if throttle is not None else "—")
        brake = live.get("brake_pct")
        self._live_rows["Brake"].setText(f"{brake:.0%}" if brake is not None else "—")
        self._live_rows["Gear"].setText(str(live.get("gear") or "—"))

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
        ("clutch_pct", "Clutch"),
        ("steering_deg", "Steering °"),
        ("lap_number", "Lap"),
        ("lap_time_s", "Lap Time"),
        ("fuel_level", "Fuel Level"),
        ("water_temp", "Water Temp"),
        ("oil_temp", "Oil Temp"),
        ("track_temp_c", "Track Temp"),
        ("air_temp_c", "Air Temp"),
        ("world_pos_x", "World Pos X"),
        ("world_pos_y", "World Pos Y"),
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

        # Health diagnostics
        cfg_hz = snap.get("sample_rate_hz_config")
        self._diag_rows["Configured Sample Rate"].setText(f"{cfg_hz:.2f} Hz" if isinstance(cfg_hz, (int, float)) else "—")
        rate_hz = snap.get("sample_rate_hz_est")
        self._diag_rows["Measured Sample Rate"].setText(f"{rate_hz:.2f} Hz" if isinstance(rate_hz, (int, float)) else "—")
        upd_hz = snap.get("update_hz_est")
        self._diag_rows["Update Frequency"].setText(f"{upd_hz:.2f} Hz" if isinstance(upd_hz, (int, float)) else "—")
        stale = snap.get("data_staleness_s")
        self._diag_rows["Staleness"].setText(f"{stale:.2f}s" if isinstance(stale, (int, float)) else "—")
        self._diag_rows["Last Error"].setText(str(snap.get("last_error") or "—"))

        # Stream health cue
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

        # Signal traces (works with partial channels by pushing None)
        self._plots["speed_kph"].push(_as_float(live.get("speed_kph")))
        self._plots["throttle_pct"].push(_as_float(live.get("throttle_pct")))
        self._plots["brake_pct"].push(_as_float(live.get("brake_pct")))
        self._plots["steering_deg"].push(_as_float(live.get("steering_deg")))
        self._plots["rpm"].push(_as_float(live.get("rpm")))

        # Key-value table
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
        self.filter_simulator.addItems(["ALL", "iRacing", "ACC", "-"])
        self.filter_adapter = QComboBox()
        self.filter_adapter.addItems(["ALL", "IRacingAdapter", "ACCAdapter", "-"])
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
        self.btn_reprocess = QPushButton("REPROCESS SESSION")
        self.btn_ignore = QPushButton("MARK IGNORED")
        self.btn_delete = QPushButton("DELETE LOCAL COPY")
        self.btn_delete.setObjectName("DangerButton")
        self.btn_return = QPushButton("RETURN TO HISTORY")
        for button in (
            self.btn_open_folder,
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
        self.btn_export = QPushButton("EXPORT CSV")
        self.btn_copy_id = QPushButton("COPY ID")
        self.btn_delete = QPushButton("DELETE")

        for btn in [self.btn_review, self.btn_open, self.btn_reprocess, 
                    self.btn_marked, self.btn_export, self.btn_copy_id, self.btn_delete]:
            btn.setObjectName("SecondaryButton")

        action_layout.addWidget(self.btn_refresh)
        action_layout.addWidget(self.btn_review)
        action_layout.addWidget(self.btn_open)
        action_layout.addWidget(self.btn_reprocess)
        action_layout.addWidget(self.btn_marked)
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
                    item.setForeground(color)
                
                # Color status column
                if col_name == "review_status":
                    if "IGNORED" in str(value):
                        item.setForeground(_MARSHAL_YELLOW)
                    else:
                        item.setForeground(_ACID_GREEN)
                if col_name == "sync_status":
                    sync_text = str(value).lower()
                    if "synced" in sync_text:
                        item.setForeground(_ACID_GREEN)
                    elif "failed" in sync_text or "blocked" in sync_text:
                        item.setForeground(_SAFETY_RED)
                    elif "ready" in sync_text or "queued" in sync_text:
                        item.setForeground(_MARSHAL_YELLOW)
                    else:
                        item.setForeground(_STEEL)
                
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


def _format_lap_time(value: object) -> str:
    return f"{value:.3f}s" if isinstance(value, (int, float)) else "—"


def _quality_color(quality: str) -> str:
    quality = quality.lower()
    if quality == "accepted":
        return _ACID_GREEN
    if quality == "accepted_with_warnings":
        return _MARSHAL_YELLOW
    if quality == "rejected":
        return _SAFETY_RED
    return _PIT_ORANGE
