"""ReviewViewModel -- session review panel bridge for QML.

Loads a completed session review dict and exposes its data as
QML-bindable properties.  The ``section`` property drives which
sub-panel (overview, laps, quality, etc.) the QML UI displays.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Property, QObject, Signal, Slot

log = logging.getLogger(__name__)


class ReviewViewModel(QObject):
    """Exposes a session review as flat, QML-bindable properties."""

    # -- change signals --------------------------------------------------------
    dataChanged = Signal()
    sectionChanged = Signal()

    # -- construction ----------------------------------------------------------

    def __init__(self) -> None:
        super().__init__()

        self._data: dict = {}
        self._section: str = ""
        self._path: str = ""

    # -- QML properties --------------------------------------------------------

    @Property("QVariant", notify=dataChanged)
    def data(self) -> dict:
        """The full review data dict."""
        return self._data

    @Property(str, notify=sectionChanged)
    def section(self) -> str:
        """Active sub-panel section name, e.g. ``'overview'``, ``'laps'``."""
        return self._section

    @Property(str, notify=dataChanged)
    def path(self) -> str:
        """Session folder path extracted from the review."""
        return self._path

    # -- slots (QML callable) --------------------------------------------------

    @Slot(str)
    def setSection(self, section: str) -> None:  # noqa: N802
        """Switch to a different review sub-panel."""
        self._section = section
        self.sectionChanged.emit()

    @Slot()
    def clear(self) -> None:
        """Reset all state to defaults."""
        self._data = {}
        self._section = ""
        self._path = ""
        self.dataChanged.emit()
        self.sectionChanged.emit()

    @Slot(str)
    def notifyInsightViewed(self, insight_id: str) -> None:  # noqa: N802
        """T064: stub seam for the future coaching UI.

        QML calls this when an insight card becomes visible (or is
        clicked) so PostHog records the impression. Each call is one
        event — repeat views of the same insight are intentional
        (impressions, not state). Blank ids are dropped because they
        signal a QML wiring bug, not data we want to record.
        ``analytics.track`` is safe-noop when PostHog isn't wired.
        """
        if not insight_id or not insight_id.strip():
            return
        from lap_coach_logger import analytics
        analytics.track(
            "coaching_insight_viewed", insight_id=insight_id.strip()
        )

    # -- public API ------------------------------------------------------------

    def load(self, review: dict) -> None:
        """Populate from a review dict.  Resets section to ``'overview'``."""
        self._data = review
        self._path = review.get("folder", "")
        self._section = "overview"
        self.dataChanged.emit()
        self.sectionChanged.emit()
