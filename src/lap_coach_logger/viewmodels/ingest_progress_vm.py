"""Ingest progress view model — bridges SSE events to a Qt-bindable surface.

Reads ADR-012 ``GET /api/v1/jobs/:id/events`` event types
(``queued`` / ``processing`` / ``stage:N`` / ``completed`` /
``failed``) emitted by ``infra.sse_progress.SseProgressConsumer``
and exposes them as ``progress_pct`` (0–100) + ``stage_label``
properties so the Finalize/Upload screen can render a progress
dial without knowing anything about HTTP/SSE.

Backend events may carry an explicit ``progress_pct`` — when
present it overrides the default schedule, letting later sprint
work (more granular stages) refine progress without changing the
view model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from lap_coach_logger.infra.sse_progress import SseProgressConsumer


_PROCESSING_BASELINE_PCT = 10
_LAST_STAGE_PCT = 90  # stage:N where N == _DEFAULT_STAGE_TOTAL
_DEFAULT_STAGE_TOTAL = 5
_COMPLETED_PCT = 100


class IngestProgressViewModel(QObject):
    """Holds progress state derived from SSE events; emits change signal."""

    # (progress_pct, stage_label) — fires whenever either changes.
    progress_changed = Signal(int, str)

    def __init__(self) -> None:
        super().__init__()
        self._progress_pct = 0
        self._stage_label = "Idle"

    @property
    def progress_pct(self) -> int:
        return self._progress_pct

    @property
    def stage_label(self) -> str:
        return self._stage_label

    def on_event(self, event: dict) -> None:
        """Slot connected to ``SseProgressConsumer.event_received``."""
        next_pct, next_label = self._derive(event)
        if next_pct == self._progress_pct and next_label == self._stage_label:
            return
        self._progress_pct = next_pct
        self._stage_label = next_label
        self.progress_changed.emit(next_pct, next_label)

    # ------------------------------------------------------------------
    def _derive(self, event: dict) -> tuple[int, str]:
        """Map one SSE event to the next ``(pct, label)`` pair.

        Honours ``progress_pct`` from the payload when the backend
        sets it explicitly. Unknown event types pass through (no
        state change) so the view model is forward-compatible.
        """
        kind = str(event.get("type") or "")
        explicit_pct = event.get("progress_pct")

        if kind == "queued":
            pct = 0
            label = "Queued"
        elif kind == "processing":
            pct = _PROCESSING_BASELINE_PCT
            label = "Processing"
        elif kind.startswith("stage:"):
            try:
                stage_idx = int(kind.split(":", 1)[1])
            except ValueError:
                return self._progress_pct, self._stage_label
            stage_span = _LAST_STAGE_PCT - _PROCESSING_BASELINE_PCT
            stage_step = stage_span / _DEFAULT_STAGE_TOTAL
            pct = round(_PROCESSING_BASELINE_PCT + stage_idx * stage_step)
            label = f"Stage {stage_idx}"
        elif kind == "completed":
            pct = _COMPLETED_PCT
            label = "Completed"
        elif kind == "failed":
            # Freeze progress at last known position so the dial
            # doesn't snap backwards on failure; just relabel.
            pct = self._progress_pct
            label = "Failed"
        else:
            return self._progress_pct, self._stage_label

        if isinstance(explicit_pct, int) and 0 <= explicit_pct <= 100:
            pct = explicit_pct
        return pct, label


def bind_to_consumer(
    vm: IngestProgressViewModel, consumer: SseProgressConsumer
) -> None:
    """Wire ``consumer.event_received`` → ``vm.on_event``."""
    consumer.event_received.connect(vm.on_event)


__all__ = ["IngestProgressViewModel", "bind_to_consumer"]
