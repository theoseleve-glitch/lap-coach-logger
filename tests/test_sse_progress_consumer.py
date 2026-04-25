"""T046: SSE progress consumer emits one Qt signal per server event.

Listens on ``GET /api/v1/jobs/:id/events`` (ADR-012 response.status_stream),
parses the ``text/event-stream`` wire format, and emits a Qt signal
for each decoded event. A subsequent sprint task (T047) wires the
signal into the progress dial on the finalize/upload screen.

Tests use an in-process ``ThreadingHTTPServer`` that writes SSE
framing then closes the connection — the consumer's blocking
``consume_stream()`` returns naturally when the stream ends.
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterator

import pytest


class _MockSseHandler(BaseHTTPRequestHandler):
    """Write a canned SSE stream, then close the connection."""

    events_to_send: list[dict[str, object]] = []
    last_auth_header: str | None = None
    last_path: str | None = None
    # Optional delay between events (seconds); used by the "streaming"
    # test to prove emits are incremental.
    inter_event_delay_s: float = 0.0

    def do_GET(self) -> None:  # noqa: N802
        type(self).last_path = self.path
        type(self).last_auth_header = self.headers.get("Authorization")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        for event in type(self).events_to_send:
            frame = f"data: {json.dumps(event)}\n\n".encode("utf-8")
            self.wfile.write(frame)
            self.wfile.flush()
            if type(self).inter_event_delay_s > 0:
                time.sleep(type(self).inter_event_delay_s)
        # Closing the response end_headers/write cleanly signals EOF
        # to the client; BaseHTTPRequestHandler closes the socket on return.

    def log_message(self, *args: object, **kwargs: object) -> None:  # noqa: ANN001
        pass


@pytest.fixture
def sse_server() -> Iterator[tuple[str, type[_MockSseHandler]]]:
    _MockSseHandler.events_to_send = []
    _MockSseHandler.last_auth_header = None
    _MockSseHandler.last_path = None
    _MockSseHandler.inter_event_delay_s = 0.0
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockSseHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}", _MockSseHandler
    finally:
        server.shutdown()
        server.server_close()


def test_consume_stream_emits_one_signal_per_event(
    sse_server: tuple[str, type[_MockSseHandler]],
) -> None:
    from lap_coach_logger.infra.sse_progress import SseProgressConsumer

    base_url, handler = sse_server
    handler.events_to_send = [
        {"type": "queued", "ts": "2026-04-25T12:00:00Z"},
        {"type": "processing", "ts": "2026-04-25T12:00:05Z"},
        {"type": "completed", "ts": "2026-04-25T12:00:30Z"},
    ]

    consumer = SseProgressConsumer(
        base_url=base_url,
        job_id="01900000-0000-7000-8000-000000000046",
        auth_token="test-token",
    )
    received: list[dict[str, object]] = []
    consumer.event_received.connect(received.append)

    consumer.consume_stream()

    assert received == handler.events_to_send


def test_consume_stream_hits_adr012_events_path(
    sse_server: tuple[str, type[_MockSseHandler]],
) -> None:
    from lap_coach_logger.infra.sse_progress import SseProgressConsumer

    base_url, handler = sse_server
    handler.events_to_send = [{"type": "queued"}]

    consumer = SseProgressConsumer(
        base_url=base_url,
        job_id="the-job-id",
        auth_token="t",
    )
    consumer.consume_stream()

    assert handler.last_path == "/api/v1/jobs/the-job-id/events"


def test_consume_stream_sends_bearer_auth(
    sse_server: tuple[str, type[_MockSseHandler]],
) -> None:
    from lap_coach_logger.infra.sse_progress import SseProgressConsumer

    base_url, handler = sse_server
    handler.events_to_send = [{"type": "queued"}]

    consumer = SseProgressConsumer(
        base_url=base_url, job_id="j", auth_token="bearer-token-value"
    )
    consumer.consume_stream()

    assert handler.last_auth_header == "Bearer bearer-token-value"


def test_consume_stream_emits_stream_ended_on_clean_close(
    sse_server: tuple[str, type[_MockSseHandler]],
) -> None:
    """When the server closes the stream cleanly, ``stream_ended`` fires once."""
    from lap_coach_logger.infra.sse_progress import SseProgressConsumer

    base_url, handler = sse_server
    handler.events_to_send = [{"type": "completed"}]

    consumer = SseProgressConsumer(base_url=base_url, job_id="j", auth_token="t")
    end_count = 0

    def _on_end() -> None:
        nonlocal end_count
        end_count += 1

    consumer.stream_ended.connect(_on_end)
    consumer.consume_stream()

    assert end_count == 1


def test_consume_stream_ignores_non_data_framing(
    sse_server: tuple[str, type[_MockSseHandler]],
) -> None:
    """Comment / event-id lines must not produce an event_received emission."""
    from lap_coach_logger.infra.sse_progress import SseProgressConsumer

    # Patch the handler to write a stream with comments and id lines.
    class _CommentEmbellishedHandler(_MockSseHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            # ``:`` starts a comment line per SSE spec — must be ignored.
            self.wfile.write(b": heartbeat comment\n")
            self.wfile.write(b"id: 1\n")
            self.wfile.write(b'data: {"type": "queued"}\n\n')
            self.wfile.write(b": another comment\n")
            self.wfile.write(b'data: {"type": "completed"}\n\n')

    server = ThreadingHTTPServer(("127.0.0.1", 0), _CommentEmbellishedHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        consumer = SseProgressConsumer(
            base_url=f"http://{host}:{port}", job_id="j", auth_token="t"
        )
        events: list[dict[str, object]] = []
        consumer.event_received.connect(events.append)
        consumer.consume_stream()
    finally:
        server.shutdown()
        server.server_close()

    assert events == [{"type": "queued"}, {"type": "completed"}]


def test_consume_stream_emits_failure_on_connection_error() -> None:
    """Connection refused / unreachable URL must surface via ``stream_failed``."""
    from lap_coach_logger.infra.sse_progress import SseProgressConsumer

    # Port 1 is "tcpmux" — conventionally closed; connection will be refused.
    consumer = SseProgressConsumer(
        base_url="http://127.0.0.1:1", job_id="unreachable", auth_token="t"
    )
    failures: list[str] = []
    consumer.stream_failed.connect(failures.append)

    consumer.consume_stream()

    assert len(failures) == 1
    assert failures[0]  # non-empty error message
