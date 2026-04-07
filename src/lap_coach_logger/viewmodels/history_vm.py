"""HistoryViewModel -- filterable session list for QML.

Receives session-history lists from ``DesktopService.history_changed`` and
exposes a filtered, searchable list to QML.  The bootstrap layer wires
``service.history_changed.connect(history_vm.update_sessions)``.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Property, QObject, Signal, Slot

log = logging.getLogger(__name__)


class HistoryViewModel(QObject):
    """Exposes session history as a filtered, QML-bindable list."""

    # -- change signals --------------------------------------------------------
    sessionsChanged = Signal()
    searchTextChanged = Signal()
    simFilterChanged = Signal()

    # -- construction ----------------------------------------------------------

    def __init__(self) -> None:
        super().__init__()

        self._all_sessions: list[dict] = []
        self._filtered: list[dict] = []
        self._search_text: str = ""
        self._sim_filter: str = ""

    # -- QML properties --------------------------------------------------------

    @Property("QVariant", notify=sessionsChanged)
    def sessions(self) -> list[dict]:
        """The filtered session list."""
        return self._filtered

    @Property(int, notify=sessionsChanged)
    def count(self) -> int:
        """Total number of sessions (unfiltered)."""
        return len(self._all_sessions)

    @Property(str, notify=searchTextChanged)
    def searchText(self) -> str:  # noqa: N802
        """Current search text."""
        return self._search_text

    @Property(str, notify=simFilterChanged)
    def simFilter(self) -> str:  # noqa: N802
        """Current sim filter value."""
        return self._sim_filter

    # -- slots (QML callable) --------------------------------------------------

    @Slot(str)
    def setSearchText(self, text: str) -> None:  # noqa: N802
        """Set and apply search text filter (lowercased, stripped)."""
        text = text.strip().lower()
        self._search_text = text
        self.searchTextChanged.emit()
        self._apply_filters()

    @Slot(str)
    def setSimFilter(self, sim: str) -> None:  # noqa: N802
        """Set and apply exact sim-name filter. Empty string = all."""
        self._sim_filter = sim
        self.simFilterChanged.emit()
        self._apply_filters()

    @Slot(int, result=str)
    def folderAt(self, index: int) -> str:  # noqa: N802
        """Return the folder path at *index* in the filtered list."""
        if index < 0 or index >= len(self._filtered):
            return ""
        return self._filtered[index].get("folder", "")

    @Slot(int, result=str)
    def sessionIdAt(self, index: int) -> str:  # noqa: N802
        """Return the session_id at *index* in the filtered list."""
        if index < 0 or index >= len(self._filtered):
            return ""
        return self._filtered[index].get("session_id", "")

    # -- public API ------------------------------------------------------------

    def update_sessions(self, sessions: list[dict]) -> None:
        """Replace the full session list and re-apply active filters."""
        self._all_sessions = list(sessions)
        self._apply_filters()

    # -- internal --------------------------------------------------------------

    def _apply_filters(self) -> None:
        """Filter ``_all_sessions`` by search text and sim filter, store result."""
        result = self._all_sessions

        if self._sim_filter:
            result = [s for s in result if s.get("sim") == self._sim_filter]

        if self._search_text:
            query = self._search_text
            result = [
                s for s in result
                if query in (s.get("track") or "").lower()
                or query in (s.get("sim") or "").lower()
                or query in (s.get("car") or "").lower()
            ]

        self._filtered = result
        self.sessionsChanged.emit()
