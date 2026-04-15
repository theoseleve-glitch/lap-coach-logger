"""SyncStatusViewModel — exposes sync state to QML."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from lap_coach_logger.sync.client import SyncClient
from lap_coach_logger.utils.qt_safe_slot import safe_slot


class SyncStatusViewModel(QObject):
    """Reports sync queue depth, last sync, failure count, connection state."""

    statusChanged = Signal()

    def __init__(
        self,
        client: SyncClient | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)  # 1 Hz

    def set_client(self, client: SyncClient) -> None:
        self._client = client
        self._tick()

    @Property(bool, notify=statusChanged)
    def isEnabled(self) -> bool:  # noqa: N802
        return self._client is not None and self._client.is_running

    @Property(int, notify=statusChanged)
    def queueDepth(self) -> int:  # noqa: N802
        return self._client.queue_depth if self._client else 0

    @Property(int, notify=statusChanged)
    def failedCount(self) -> int:  # noqa: N802
        return self._client.failed_count if self._client else 0

    @Property(str, notify=statusChanged)
    def lastSyncTime(self) -> str:  # noqa: N802
        if self._client and self._client.last_sync_time:
            return self._client.last_sync_time
        return ""

    @Property(str, notify=statusChanged)
    def connectionState(self) -> str:  # noqa: N802
        return self._client.connection_state if self._client else "unknown"

    @Property(str, notify=statusChanged)
    def lastError(self) -> str:  # noqa: N802
        return self._client.last_error if self._client else ""

    @safe_slot()
    @Slot(str, result=bool)
    def retryFailure(self, envelope_id: str) -> bool:  # noqa: N802
        if self._client is None:
            return False
        return self._client.retry_failure(envelope_id)

    def _tick(self) -> None:
        self.statusChanged.emit()
