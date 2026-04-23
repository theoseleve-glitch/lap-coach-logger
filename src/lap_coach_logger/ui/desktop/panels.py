"""Legacy panel base classes and UI helpers.

Provides QWidget base classes for workspace panels and metric row helpers
used throughout the desktop UI.  Also re-exports telemetry widgets that
were originally defined here before being moved to workspaces/.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

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
