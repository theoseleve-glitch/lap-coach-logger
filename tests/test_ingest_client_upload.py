"""T042: ``IngestClient.upload`` returns ``ingest_job_id`` from 202 response.

Tests the happy-path POST to ``/api/v1/sessions/ingest`` (ADR-012) using
an in-process HTTP mock server bound to an OS-chosen port. Idempotency
(T043), chunk streaming (T044), resume-on-interrupt (T045), retry
backoff (T048), and 4xx/5xx/network error coverage (T054) land in
subsequent sprint tasks.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

import pytest


class _MockIngestHandler(BaseHTTPRequestHandler):
    """Capture incoming ingestion requests; return a canned 202 payload."""

    # Class-level state so tests can inspect what the client sent.
    last_path: str | None = None
    last_headers: dict[str, str] | None = None
    last_body: bytes | None = None
    response_body: dict[str, str] = {}
    response_status: int = 202

    def do_POST(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
        length = int(self.headers.get("Content-Length", "0"))
        type(self).last_path = self.path
        type(self).last_headers = dict(self.headers)
        type(self).last_body = self.rfile.read(length)
        payload = json.dumps(type(self).response_body).encode("utf-8")
        self.send_response(type(self).response_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args: object, **kwargs: object) -> None:  # noqa: ANN001
        pass


@pytest.fixture
def mock_ingest_server() -> Iterator[tuple[str, type[_MockIngestHandler]]]:
    _MockIngestHandler.last_path = None
    _MockIngestHandler.last_headers = None
    _MockIngestHandler.last_body = None
    _MockIngestHandler.response_body = {
        "session_id": "01900000-0000-7000-8000-000000000001",
        "ingest_job_id": "01900000-0000-7000-8000-000000000002",
        "status_stream": "/api/v1/jobs/01900000-0000-7000-8000-000000000002/events",
    }
    _MockIngestHandler.response_status = 202
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockIngestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}", _MockIngestHandler
    finally:
        server.shutdown()
        server.server_close()


def _seed_bundle(tmp_path: Path) -> Path:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "manifest.json").write_text(
        json.dumps({"session_id": "01900000-0000-7000-8000-000000000001"}),
        encoding="utf-8",
    )
    (bundle_dir / "telemetry.parquet").write_bytes(b"\x00" * 128)
    return bundle_dir


def test_upload_returns_ingest_job_id_from_202_response(
    tmp_path: Path,
    mock_ingest_server: tuple[str, type[_MockIngestHandler]],
) -> None:
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, _ = mock_ingest_server
    client = IngestClient(base_url=base_url, auth_token="test-token")

    result = client.upload(bundle_dir=_seed_bundle(tmp_path))

    assert result.success is True
    assert result.http_status == 202
    assert result.ingest_job_id == "01900000-0000-7000-8000-000000000002"
    assert result.session_id == "01900000-0000-7000-8000-000000000001"
    assert (
        result.status_stream_url
        == "/api/v1/jobs/01900000-0000-7000-8000-000000000002/events"
    )


def test_upload_posts_to_adr012_endpoint(
    tmp_path: Path,
    mock_ingest_server: tuple[str, type[_MockIngestHandler]],
) -> None:
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = mock_ingest_server
    client = IngestClient(base_url=base_url, auth_token="test-token")

    client.upload(bundle_dir=_seed_bundle(tmp_path))

    assert handler.last_path == "/api/v1/sessions/ingest"


def test_upload_includes_authorization_header(
    tmp_path: Path,
    mock_ingest_server: tuple[str, type[_MockIngestHandler]],
) -> None:
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = mock_ingest_server
    client = IngestClient(base_url=base_url, auth_token="my-bearer-token")

    client.upload(bundle_dir=_seed_bundle(tmp_path))

    auth = (handler.last_headers or {}).get("Authorization", "")
    assert auth == "Bearer my-bearer-token"


def test_upload_body_is_multipart_with_manifest_field(
    tmp_path: Path,
    mock_ingest_server: tuple[str, type[_MockIngestHandler]],
) -> None:
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = mock_ingest_server
    client = IngestClient(base_url=base_url, auth_token="test-token")

    client.upload(bundle_dir=_seed_bundle(tmp_path))

    content_type = (handler.last_headers or {}).get("Content-Type", "")
    assert content_type.startswith("multipart/form-data; boundary=")
    body = handler.last_body or b""
    assert b'name="manifest"' in body
    assert b"01900000-0000-7000-8000-000000000001" in body  # session_id from manifest


def test_upload_returns_failure_when_manifest_missing(tmp_path: Path) -> None:
    from lap_coach_logger.infra.ingest import IngestClient

    empty_bundle = tmp_path / "empty"
    empty_bundle.mkdir()

    client = IngestClient(base_url="http://unused.test", auth_token="t")
    result = client.upload(bundle_dir=empty_bundle)

    assert result.success is False
    assert result.error_code == "no_manifest"


def test_upload_sets_idempotency_key_from_manifest_session_id(
    tmp_path: Path,
    mock_ingest_server: tuple[str, type[_MockIngestHandler]],
) -> None:
    """T043: Idempotency-Key header must equal manifest.session_id (UUID7).

    The backend uses this header to deduplicate retries — every attempt
    for the same session must present the same key so server-side
    idempotency short-circuits after a successful ingest.
    """
    from lap_coach_logger.infra.ingest import IngestClient

    session_uuid7 = "01900000-0000-7000-8000-000000000abc"
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "manifest.json").write_text(
        json.dumps({"session_id": session_uuid7}),
        encoding="utf-8",
    )
    (bundle_dir / "telemetry.parquet").write_bytes(b"\x00" * 64)

    base_url, handler = mock_ingest_server
    client = IngestClient(base_url=base_url, auth_token="t")

    client.upload(bundle_dir=bundle_dir)

    assert (
        (handler.last_headers or {}).get("Idempotency-Key") == session_uuid7
    )


def test_upload_splits_large_telemetry_into_multiple_chunks(
    tmp_path: Path,
    mock_ingest_server: tuple[str, type[_MockIngestHandler]],
) -> None:
    """T044: telemetry > chunk_size_bytes sent as multiple chunks[] parts.

    Uses a small chunk_size in the test so we don't need to generate
    real 5MB blobs. A 10000-byte telemetry file with 4096-byte chunks
    must produce 3 chunks[] parts (4096 + 4096 + 1808 bytes).
    """
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = mock_ingest_server
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "manifest.json").write_text(
        json.dumps({"session_id": "01900000-0000-7000-8000-00000000c044"}),
        encoding="utf-8",
    )
    (bundle_dir / "telemetry.parquet").write_bytes(b"x" * 10000)

    client = IngestClient(base_url=base_url, auth_token="t", chunk_size_bytes=4096)
    client.upload(bundle_dir=bundle_dir)

    body = handler.last_body or b""
    chunk_count = body.count(b'name="chunks[]"')
    assert chunk_count == 3, f"expected 3 chunks[] parts, got {chunk_count}"


def test_upload_small_telemetry_stays_single_chunk(
    tmp_path: Path,
    mock_ingest_server: tuple[str, type[_MockIngestHandler]],
) -> None:
    """T044: telemetry ≤ chunk_size_bytes stays as one chunks[] part."""
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = mock_ingest_server
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "manifest.json").write_text(
        json.dumps({"session_id": "01900000-0000-7000-8000-00000000c045"}),
        encoding="utf-8",
    )
    (bundle_dir / "telemetry.parquet").write_bytes(b"x" * 100)

    client = IngestClient(base_url=base_url, auth_token="t", chunk_size_bytes=4096)
    client.upload(bundle_dir=bundle_dir)

    body = handler.last_body or b""
    assert body.count(b'name="chunks[]"') == 1


def test_upload_chunk_filenames_include_index_and_total(
    tmp_path: Path,
    mock_ingest_server: tuple[str, type[_MockIngestHandler]],
) -> None:
    """T044: each chunk's filename carries its index so the backend can reassemble."""
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = mock_ingest_server
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "manifest.json").write_text(
        json.dumps({"session_id": "01900000-0000-7000-8000-00000000c046"}),
        encoding="utf-8",
    )
    (bundle_dir / "telemetry.parquet").write_bytes(b"x" * 10000)

    client = IngestClient(base_url=base_url, auth_token="t", chunk_size_bytes=4096)
    client.upload(bundle_dir=bundle_dir)

    body = handler.last_body or b""
    # Each chunk part must have a filename that identifies its place in the sequence.
    assert b"telemetry.parquet.part0of3" in body
    assert b"telemetry.parquet.part1of3" in body
    assert b"telemetry.parquet.part2of3" in body


def test_upload_default_chunk_size_is_5mb() -> None:
    """T044: default chunk size matches the ADR-012 5 MB target."""
    from lap_coach_logger.infra.ingest import IngestClient

    client = IngestClient(base_url="http://unused.test", auth_token="t")
    assert client.chunk_size_bytes == 5 * 1024 * 1024


def test_upload_idempotency_key_is_stable_across_retries(
    tmp_path: Path,
    mock_ingest_server: tuple[str, type[_MockIngestHandler]],
) -> None:
    """T043: Two calls with the same bundle must send the same key.

    Guards against the client ever minting a per-call UUID — the key
    is anchored to the session, not the attempt, so server-side
    deduplication works.
    """
    from lap_coach_logger.infra.ingest import IngestClient

    session_uuid7 = "01900000-0000-7000-8000-0000000000ff"
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "manifest.json").write_text(
        json.dumps({"session_id": session_uuid7}),
        encoding="utf-8",
    )
    (bundle_dir / "telemetry.parquet").write_bytes(b"\x00" * 32)

    base_url, handler = mock_ingest_server
    client = IngestClient(base_url=base_url, auth_token="t")

    client.upload(bundle_dir=bundle_dir)
    first = (handler.last_headers or {}).get("Idempotency-Key")

    client.upload(bundle_dir=bundle_dir)
    second = (handler.last_headers or {}).get("Idempotency-Key")

    assert first == session_uuid7
    assert first == second
