"""ServiceViewModel -- root QML bridge that wraps DesktopService state.

Accepts a ``DesktopService`` instance and re-publishes its periodic
snapshot as individual QML-bindable properties.  Change signals are
deduplicated so QML only redraws when a value actually changes.
"""

from __future__ import annotations

import datetime
import logging
import webbrowser
from typing import TYPE_CHECKING

from PySide6.QtCore import Property, QObject, Signal, Slot

from lap_coach_logger.utils.webapp_links import (
    view_session_url,
    view_sessions_url,
)

if TYPE_CHECKING:
    from lap_coach_logger.ui.desktop.service import DesktopService


# T070: indirected so tests can monkeypatch ``_open_url`` to a recorder
# instead of launching a real browser. Production wiring is
# ``webbrowser.open`` which respects the user's default browser.
_open_url = webbrowser.open

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_hour() -> int:
    """Return the current local hour (0-23).  Factored out for testability."""
    return datetime.datetime.now().hour  # noqa: DTZ005


def _format_elapsed(seconds: int) -> str:
    """Format seconds as ``M:SS`` or ``H:MM:SS``."""
    if seconds < 0:
        seconds = 0
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# ViewModel
# ---------------------------------------------------------------------------

class ServiceViewModel(QObject):
    """Exposes ``DesktopService`` state as flat, QML-friendly properties.

    Child view-models (SessionVM, HistoryVM, etc.) can reference
    ``latest_snapshot`` to derive their own properties without
    re-connecting to the service signal.
    """

    # -- change signals ----------------------------------------------------
    statusChanged = Signal()
    statusDetailChanged = Signal()
    isMonitoringChanged = Signal()
    simChanged = Signal()
    elapsedChanged = Signal()
    snapshotChanged = Signal()

    # -- toast / error signals (forwarded from service) --------------------
    toastRequested = Signal(str)
    errorRequested = Signal(str)

    # T069: emitted after a successful deleteSession() so QML can
    # navigate away from the now-deleted review (otherwise the UI
    # would still show the bundle's data after the underlying
    # folder is gone). Argument is the path that was deleted.
    sessionDeleted = Signal(str)

    # -- construction ------------------------------------------------------

    def __init__(self, service: DesktopService) -> None:
        super().__init__()
        self._service = service

        # Internal state (defaults before first snapshot)
        self._status: str = "Idle"
        self._status_detail: str = ""
        self._is_monitoring: bool = False
        self._sim: str = ""
        self._elapsed_s: int = 0
        self._latest_snapshot: dict | None = None

        # Wire service signals
        self._service.snapshot_changed.connect(self._on_snapshot)
        self._service.settings_saved.connect(self._on_toast)
        self._service.settings_failed.connect(self._on_error)
        # action_message / action_failed may not exist on all service versions
        if hasattr(self._service, "action_message"):
            self._service.action_message.connect(self._on_toast)
        if hasattr(self._service, "action_failed"):
            self._service.action_failed.connect(self._on_error)

    # -- QML properties ----------------------------------------------------

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(str, notify=statusDetailChanged)
    def statusDetail(self) -> str:  # noqa: N802
        return self._status_detail

    @Property(bool, notify=isMonitoringChanged)
    def isMonitoring(self) -> bool:  # noqa: N802
        return self._is_monitoring

    @Property(str, notify=simChanged)
    def sim(self) -> str:
        return self._sim

    @Property(int, notify=elapsedChanged)
    def elapsedSeconds(self) -> int:  # noqa: N802
        return self._elapsed_s

    @Property(str, notify=elapsedChanged)
    def elapsedFormatted(self) -> str:  # noqa: N802
        return _format_elapsed(self._elapsed_s)

    @Property(str, notify=snapshotChanged)
    def greeting(self) -> str:
        hour = _current_hour()
        if hour < 12:
            return "Good morning"
        if hour < 18:
            return "Good afternoon"
        return "Good evening"

    @property
    def service(self) -> DesktopService:
        """Python-only — not exposed to QML."""
        return self._service

    @property
    def latest_snapshot(self) -> dict | None:
        """Python-only — not exposed to QML."""
        return self._latest_snapshot

    # -- slots (QML callable) ----------------------------------------------

    @Slot()
    def resumeMonitoring(self) -> None:  # noqa: N802
        """Start the process watcher / monitoring loop."""
        self._service.start_monitoring()

    @Slot()
    def pauseMonitoring(self) -> None:  # noqa: N802
        """Stop the process watcher / monitoring loop."""
        self._service.stop_monitoring()

    @Slot()
    def openOutputFolder(self) -> None:  # noqa: N802
        """Open the session output folder in the system file manager."""
        self._service.open_output_folder()

    @Slot()
    def openLogsFolder(self) -> None:  # noqa: N802
        """Open the application logs folder."""
        self._service.open_logs_folder()

    @Slot()
    def openConfigFolder(self) -> None:  # noqa: N802
        """Open the config directory."""
        self._service.open_config_folder()

    @Slot(str)
    def deleteSession(self, path: str) -> None:  # noqa: N802
        """T069: delete the session bundle at ``path`` and announce it.

        QML calls this from the Review-page Delete button (after a
        confirm dialog) and listens for ``sessionDeleted`` to
        navigate away from the now-deleted review. Empty / blank
        paths are a defensive no-op so a missing-prop bug on the
        QML side can't trigger a delete on the wrong target.
        """
        if not path or not path.strip():
            return
        self._service.delete_review_session(path)
        self.sessionDeleted.emit(path)

    @Slot(str)
    def viewSessionInWebapp(self, session_id: str) -> None:  # noqa: N802
        """T070: open the webapp's per-session detail page.

        Replaces the desktop-side "Export CSV" CTA per Q95: export
        and deep-analysis flows live in lap-webapp. A blank
        ``session_id`` falls back to the sessions list (the
        ``view_session_url`` helper handles the fallback so QML
        callers can pass whatever the review data exposes without
        an extra null-check).
        """
        _open_url(view_session_url(session_id))

    @Slot()
    def viewSessionsInWebapp(self) -> None:  # noqa: N802
        """T070: open the webapp's sessions list.

        Used by the History-page context menu, where there's no
        single review-bound session_id in scope.
        """
        _open_url(view_sessions_url())

    # -- internal handlers -------------------------------------------------

    def _on_snapshot(self, snapshot: dict) -> None:
        """Process an incoming snapshot and selectively emit change signals."""
        self._latest_snapshot = snapshot

        new_status: str = snapshot.get("status", "Idle")
        new_detail: str = snapshot.get("status_detail", "")
        new_monitoring: bool = bool(snapshot.get("is_monitoring", False))
        new_sim: str = snapshot.get("sim") or ""
        new_elapsed: int = int(snapshot.get("elapsed_s", 0))

        if new_status != self._status:
            self._status = new_status
            self.statusChanged.emit()

        if new_detail != self._status_detail:
            self._status_detail = new_detail
            self.statusDetailChanged.emit()

        if new_monitoring != self._is_monitoring:
            self._is_monitoring = new_monitoring
            self.isMonitoringChanged.emit()

        if new_sim != self._sim:
            self._sim = new_sim
            self.simChanged.emit()

        if new_elapsed != self._elapsed_s:
            self._elapsed_s = new_elapsed
            self.elapsedChanged.emit()

        # Always fire -- child VMs listen on this for full-snapshot updates.
        self.snapshotChanged.emit()

    def _on_toast(self, message: str) -> None:
        self.toastRequested.emit(message)

    def _on_error(self, message: str) -> None:
        self.errorRequested.emit(message)
