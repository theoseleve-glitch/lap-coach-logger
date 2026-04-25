"""SSE consumer for ``GET /api/v1/jobs/:id/events`` (T046).

Streams progress events from the backend job status endpoint and
emits one Qt signal per decoded event. Designed to run on a worker
thread: ``consume_stream()`` blocks until the server closes the
connection (clean end) or the HTTP request errors (network failure),
at which point ``stream_ended`` or ``stream_failed`` fires exactly
once respectively. Main-thread Qt widgets consume the progress by
connecting to ``event_received`` — T047 hooks the progress dial
into that signal.

Wire format: ``text/event-stream`` per the HTML5 SSE spec. Lines
starting with ``data:`` carry JSON payloads; ``id:`` and ``:``
(comment) lines are ignored. Events are delimited by blank lines.
"""

from __future__ import annotations

import json
import logging
from typing import Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, Signal

log = logging.getLogger(__name__)

_EVENTS_ENDPOINT_TEMPLATE = "/api/v1/jobs/{job_id}/events"


class SseProgressConsumer(QObject):
    """Consumes the SSE job-status stream; emits one Qt signal per event."""

    # Emitted once per parsed ``data:`` event. Payload is the decoded
    # JSON dict (e.g. ``{"type": "processing", "stage": 2, ...}``).
    event_received = Signal(dict)

    # Emitted once when the stream closes without error.
    stream_ended = Signal()

    # Emitted once when the stream fails (connection refused, HTTP
    # error, parse failure); payload is a human-readable reason.
    stream_failed = Signal(str)

    def __init__(
        self,
        *,
        base_url: str,
        job_id: str,
        auth_token: str,
        timeout_s: float = 600.0,
    ) -> None:
        super().__init__()
        self._url = (
            base_url.rstrip("/") + _EVENTS_ENDPOINT_TEMPLATE.format(job_id=job_id)
        )
        self._auth_token = auth_token
        self._timeout_s = timeout_s

    def consume_stream(self) -> None:
        """Block until the SSE stream ends, emitting one signal per event.

        Either ``stream_ended`` or ``stream_failed`` fires exactly once
        before this method returns.
        """
        req = Request(
            self._url,
            headers={
                "Authorization": f"Bearer {self._auth_token}",
                "Accept": "text/event-stream",
            },
        )
        try:
            with urlopen(req, timeout=self._timeout_s) as resp:
                for event in _parse_sse_events(resp):
                    self.event_received.emit(event)
            self.stream_ended.emit()
        except HTTPError as exc:
            self.stream_failed.emit(f"HTTP {exc.code}: {exc.reason}")
        except (URLError, OSError) as exc:
            self.stream_failed.emit(str(exc))


def _parse_sse_events(stream: Iterator[bytes]) -> Iterator[dict[str, object]]:
    """Yield one decoded event dict per ``data: {...}\\n\\n`` frame.

    Ignores SSE comment lines (``:`` prefix) and framing metadata
    (``id:``, ``event:``, ``retry:``). A malformed JSON payload logs
    a warning and is skipped rather than aborting the whole stream.
    """
    data_buffer: list[str] = []
    for raw_line in stream:
        line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
        if line == "":
            if data_buffer:
                payload = "\n".join(data_buffer)
                data_buffer.clear()
                try:
                    yield json.loads(payload)
                except ValueError:
                    log.warning("Dropping malformed SSE payload: %r", payload)
            continue
        if line.startswith(":"):  # comment line — skip
            continue
        field, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if field == "data":
            data_buffer.append(value)
        # id:, event:, retry: are accepted-and-ignored for T046.
    # EOF — flush any pending data buffer.
    if data_buffer:
        payload = "\n".join(data_buffer)
        try:
            yield json.loads(payload)
        except ValueError:
            log.warning("Dropping malformed trailing SSE payload: %r", payload)


__all__ = ["SseProgressConsumer"]
