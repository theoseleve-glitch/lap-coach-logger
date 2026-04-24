"""T045: Resume-on-interrupt via persisted completion cursor.

After a successful upload ``IngestClient.upload`` writes
``{bundle_dir}/.ingest_cursor.json`` carrying the 202-response
fields. A subsequent call for the same bundle short-circuits and
returns the cached ``IngestResult`` without re-hitting the server
(true per-chunk resume requires backend per-chunk ACKs that the
backend sprint adds later — this client-side cursor prevents
re-uploading a session that already landed).
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

import pytest


class _CountingIngestHandler(BaseHTTPRequestHandler):
    """Ingestion mock that keeps a post counter + last-request snapshot."""

    post_count: int = 0
    response_body: dict[str, str] = {}
    response_status: int = 202

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        # Drain the body so the socket stays healthy for the next request.
        self.rfile.read(length)
        type(self).post_count += 1
        payload = json.dumps(type(self).response_body).encode("utf-8")
        self.send_response(type(self).response_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args: object, **kwargs: object) -> None:  # noqa: ANN001
        pass


@pytest.fixture
def counting_server() -> Iterator[tuple[str, type[_CountingIngestHandler]]]:
    _CountingIngestHandler.post_count = 0
    _CountingIngestHandler.response_body = {
        "session_id": "01900000-0000-7000-8000-00000000cc01",
        "ingest_job_id": "01900000-0000-7000-8000-00000000cc02",
        "status_stream": "/api/v1/jobs/01900000-0000-7000-8000-00000000cc02/events",
    }
    _CountingIngestHandler.response_status = 202
    server = ThreadingHTTPServer(("127.0.0.1", 0), _CountingIngestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}", _CountingIngestHandler
    finally:
        server.shutdown()
        server.server_close()


def _seed_bundle(tmp_path: Path) -> Path:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "manifest.json").write_text(
        json.dumps({"session_id": "01900000-0000-7000-8000-00000000cc01"}),
        encoding="utf-8",
    )
    (bundle_dir / "telemetry.parquet").write_bytes(b"\x00" * 64)
    return bundle_dir


def test_upload_writes_completion_cursor_on_success(
    tmp_path: Path,
    counting_server: tuple[str, type[_CountingIngestHandler]],
) -> None:
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, _ = counting_server
    bundle_dir = _seed_bundle(tmp_path)

    client = IngestClient(base_url=base_url, auth_token="t")
    result = client.upload(bundle_dir=bundle_dir)

    assert result.success is True
    cursor_path = bundle_dir / ".ingest_cursor.json"
    assert cursor_path.exists(), "successful upload must persist cursor"
    cursor = json.loads(cursor_path.read_text(encoding="utf-8"))
    assert cursor["session_id"] == "01900000-0000-7000-8000-00000000cc01"
    assert cursor["ingest_job_id"] == "01900000-0000-7000-8000-00000000cc02"


def test_second_upload_skips_server_when_cursor_exists(
    tmp_path: Path,
    counting_server: tuple[str, type[_CountingIngestHandler]],
) -> None:
    """Cursor short-circuits the retry — mock server sees one POST, not two."""
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = counting_server
    bundle_dir = _seed_bundle(tmp_path)

    client = IngestClient(base_url=base_url, auth_token="t")
    client.upload(bundle_dir=bundle_dir)
    first_count = handler.post_count

    second = client.upload(bundle_dir=bundle_dir)

    assert first_count == 1
    assert handler.post_count == 1, "cursor must prevent a second POST"
    assert second.success is True
    assert second.ingest_job_id == "01900000-0000-7000-8000-00000000cc02"


def test_upload_does_not_write_cursor_on_http_error(
    tmp_path: Path,
    counting_server: tuple[str, type[_CountingIngestHandler]],
) -> None:
    """A 5xx must leave the cursor absent so the next call retries."""
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = counting_server
    handler.response_status = 500
    handler.response_body = {}

    bundle_dir = _seed_bundle(tmp_path)
    client = IngestClient(base_url=base_url, auth_token="t")
    result = client.upload(bundle_dir=bundle_dir)

    assert result.success is False
    cursor_path = bundle_dir / ".ingest_cursor.json"
    assert not cursor_path.exists(), (
        "cursor must be absent after failure so retry re-hits the server"
    )


def test_upload_ignores_cursor_from_different_session(
    tmp_path: Path,
    counting_server: tuple[str, type[_CountingIngestHandler]],
) -> None:
    """A stale cursor pointing at a different session_id must not short-circuit."""
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = counting_server
    bundle_dir = _seed_bundle(tmp_path)

    # Seed a cursor for a *different* session (simulates bundle rename/reuse).
    (bundle_dir / ".ingest_cursor.json").write_text(
        json.dumps(
            {
                "session_id": "deadbeef-dead-beef-dead-beefdeadbeef",
                "ingest_job_id": "old-job",
            }
        ),
        encoding="utf-8",
    )

    client = IngestClient(base_url=base_url, auth_token="t")
    client.upload(bundle_dir=bundle_dir)

    assert handler.post_count == 1, (
        "cursor for a different session_id must not short-circuit the upload"
    )
