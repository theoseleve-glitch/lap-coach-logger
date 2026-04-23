"""Ghost Coach overlay widget — shows theoretical targets vs actual."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from lap_coach_logger.ui.desktop.theme import (
    ACID_GREEN, CHALK, CONCRETE, MARSHAL_YELLOW, PIT_ORANGE, SAFETY_RED, STEEL,
)


class GhostBarWidget(QWidget):
    """Horizontal bar showing actual (filled) vs theoretical (ghost marker)."""

    def __init__(self, color: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._color = color
        self._actual = 0.0   # 0-1
        self._ghost = 0.0    # 0-1
        self.setFixedHeight(14)
        self.setMinimumWidth(120)

    def set_values(self, actual: float, ghost: float) -> None:
        self._actual = max(0.0, min(1.0, actual))
        self._ghost = max(0.0, min(1.0, ghost))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background track
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 15))
        p.drawRoundedRect(0, 0, w, h, 3, 3)

        # Actual fill
        fill_w = int(self._actual * w)
        if fill_w > 0:
            color = QColor(self._color)
            color.setAlpha(180)
            p.setBrush(color)
            p.drawRoundedRect(0, 0, fill_w, h, 3, 3)

        # Ghost marker (vertical line)
        ghost_x = int(self._ghost * w)
        if 0 < ghost_x < w:
            pen = QPen(QColor(CHALK))
            pen.setWidth(2)
            pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.drawLine(ghost_x, 1, ghost_x, h - 1)

        p.end()


class GhostCoachOverlay(QFrame):
    """Compact ghost coaching overlay panel."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("GhostCoachSurface")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(280, 160)
        self.setStyleSheet(f"""
            QFrame#GhostCoachSurface {{
                background-color: rgba(10, 10, 10, 230);
                border: 1px solid rgba(240, 237, 229, 25);
                border-radius: 10px;
            }}
            QLabel#GhostKicker {{
                color: {PIT_ORANGE};
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 1.8px;
            }}
            QLabel#GhostSpeedDelta {{
                color: {CHALK};
                font-size: 20px;
                font-weight: 800;
                font-family: 'Consolas', 'Space Mono', monospace;
            }}
            QLabel#GhostSpeedDetail {{
                color: {STEEL};
                font-size: 11px;
                font-family: 'Consolas', monospace;
            }}
            QLabel#GhostBarLabel {{
                color: {STEEL};
                font-size: 9px;
                font-weight: 600;
                letter-spacing: 1px;
            }}
            QLabel#GhostBarValue {{
                color: {CHALK};
                font-size: 10px;
                font-family: 'Consolas', monospace;
            }}
            QLabel#GhostTimeDelta {{
                color: {CHALK};
                font-size: 16px;
                font-weight: 800;
                font-family: 'Consolas', monospace;
            }}
            QLabel#GhostNotLoaded {{
                color: {STEEL};
                font-size: 10px;
            }}
        """)
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        # Kicker
        kicker = QLabel("GHOST COACH")
        kicker.setObjectName("GhostKicker")
        root.addWidget(kicker)

        # Speed delta row
        speed_row = QHBoxLayout()
        speed_row.setSpacing(8)
        lbl = QLabel("SPD")
        lbl.setObjectName("GhostBarLabel")
        speed_row.addWidget(lbl)
        self._speed_delta = QLabel("-")
        self._speed_delta.setObjectName("GhostSpeedDelta")
        speed_row.addWidget(self._speed_delta)
        speed_row.addStretch(1)
        self._speed_detail = QLabel("")
        self._speed_detail.setObjectName("GhostSpeedDetail")
        speed_row.addWidget(self._speed_detail)
        root.addLayout(speed_row)

        # Throttle bar
        thr_row = QHBoxLayout()
        thr_row.setSpacing(6)
        thr_lbl = QLabel("THR")
        thr_lbl.setObjectName("GhostBarLabel")
        thr_lbl.setFixedWidth(28)
        thr_row.addWidget(thr_lbl)
        self._thr_bar = GhostBarWidget(ACID_GREEN)
        thr_row.addWidget(self._thr_bar)
        self._thr_value = QLabel("")
        self._thr_value.setObjectName("GhostBarValue")
        self._thr_value.setFixedWidth(70)
        self._thr_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        thr_row.addWidget(self._thr_value)
        root.addLayout(thr_row)

        # Brake bar
        brk_row = QHBoxLayout()
        brk_row.setSpacing(6)
        brk_lbl = QLabel("BRK")
        brk_lbl.setObjectName("GhostBarLabel")
        brk_lbl.setFixedWidth(28)
        brk_row.addWidget(brk_lbl)
        self._brk_bar = GhostBarWidget(SAFETY_RED)
        brk_row.addWidget(self._brk_bar)
        self._brk_value = QLabel("")
        self._brk_value.setObjectName("GhostBarValue")
        self._brk_value.setFixedWidth(70)
        self._brk_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        brk_row.addWidget(self._brk_value)
        root.addLayout(brk_row)

        # Time delta
        delta_row = QHBoxLayout()
        delta_row.addStretch(1)
        self._time_delta = QLabel("-")
        self._time_delta.setObjectName("GhostTimeDelta")
        delta_row.addWidget(self._time_delta)
        delta_row.addStretch(1)
        root.addLayout(delta_row)

        # Not-loaded message (hidden when data is available)
        self._not_loaded = QLabel("No ghost reference loaded")
        self._not_loaded.setObjectName("GhostNotLoaded")
        self._not_loaded.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._not_loaded)
        self._not_loaded.hide()

    def update_from_snapshot(self, snapshot: dict) -> None:
        """Update all display elements from ghost_coaching_snapshot() data."""
        if not snapshot or not snapshot.get("ghost_loaded"):
            # Show not-loaded state
            self._speed_delta.setText("-")
            self._speed_detail.setText("")
            self._thr_bar.set_values(0, 0)
            self._brk_bar.set_values(0, 0)
            self._thr_value.setText("")
            self._brk_value.setText("")
            self._time_delta.setText("-")
            self._not_loaded.show()
            return

        self._not_loaded.hide()

        # Speed delta
        spd_delta = snapshot.get("ghost_speed_delta_kph", 0)
        theo_spd = snapshot.get("ghost_theoretical_speed_kph", 0)
        arrow = "▲" if spd_delta > 0 else "▼" if spd_delta < 0 else "="
        sign = "+" if spd_delta > 0 else ""
        self._speed_delta.setText(f"{arrow}{sign}{spd_delta:.0f}")
        # Color: red if you're slow (positive delta), green if you're fast
        if spd_delta > 2:
            self._speed_delta.setStyleSheet(f"color: {SAFETY_RED}; font-size: 20px; font-weight: 800; font-family: Consolas;")
        elif spd_delta < -2:
            self._speed_delta.setStyleSheet(f"color: {ACID_GREEN}; font-size: 20px; font-weight: 800; font-family: Consolas;")
        else:
            self._speed_delta.setStyleSheet(f"color: {CHALK}; font-size: 20px; font-weight: 800; font-family: Consolas;")
        self._speed_detail.setText(f"{theo_spd:.0f} km/h")

        # Throttle bar: actual from snapshot needs to come from the main sample
        # We only have the ghost values here, so show ghost target vs delta
        theo_thr = snapshot.get("ghost_theoretical_throttle_pct", 0)
        thr_delta = snapshot.get("ghost_throttle_delta_pct", 0)
        actual_thr = max(0, theo_thr - thr_delta)
        self._thr_bar.set_values(actual_thr, theo_thr)
        self._thr_value.setText(f"{actual_thr*100:.0f}→{theo_thr*100:.0f}%")

        # Brake bar
        theo_brk = snapshot.get("ghost_theoretical_brake_pct", 0)
        brk_delta = snapshot.get("ghost_brake_delta_pct", 0)
        actual_brk = max(0, theo_brk - brk_delta)
        self._brk_bar.set_values(actual_brk, theo_brk)
        self._brk_value.setText(f"{actual_brk*100:.0f}→{theo_brk*100:.0f}%")

        # Time delta
        cum_delta = snapshot.get("ghost_cumulative_delta_s", 0)
        sign = "+" if cum_delta > 0 else ""
        self._time_delta.setText(f"{sign}{cum_delta:.3f}s")
        if cum_delta > 0.1:
            self._time_delta.setStyleSheet(f"color: {SAFETY_RED}; font-size: 16px; font-weight: 800; font-family: Consolas;")
        elif cum_delta < -0.1:
            self._time_delta.setStyleSheet(f"color: {ACID_GREEN}; font-size: 16px; font-weight: 800; font-family: Consolas;")
        else:
            self._time_delta.setStyleSheet(f"color: {CHALK}; font-size: 16px; font-weight: 800; font-family: Consolas;")
