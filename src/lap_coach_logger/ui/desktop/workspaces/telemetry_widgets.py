"""Shared telemetry visualization widgets for immersive desktop workspaces."""

from __future__ import annotations

from collections import deque
import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

_STEEL = "#949494"
_CHALK = "#F0EDE5"
_PIT_ORANGE = "#C9A84C"
_ACID_GREEN = "#22C55E"


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


__all__ = [
    "FrictionCircleWidget",
    "MiniTrackMapWidget",
    "TelemetrySparkline",
    "TelemetryTraceWidget",
]
