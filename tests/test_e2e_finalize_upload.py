"""T055: End-to-end integration — finalize → upload → server confirms.

The unit-test files (T041–T054) exercise ``IngestClient`` against
hand-crafted bundles (``manifest.json`` + a single
``telemetry.parquet`` of zeros). T055 instead chains the *real*
``SessionFinalizer`` into a *real* ``IngestClient`` against a mock
ADR-012 ingest server, so the integration seam between
``writers/finalizer.py`` and ``infra/ingest.py`` is exercised:

  * the finalizer writes a multi-file bundle (manifest + parquet +
    channels.json + optional laps/events) to disk;
  * the client streams that whole bundle as multipart/form-data;
  * the mock server parses the multipart, records the manifest
    JSON it received, and returns 202 with a session_id /
    ingest_job_id payload;
  * the test asserts that the session_id the server saw is the
    same UUID that the finalizer wrote into the manifest — proving
    the manifest survived the serialize → upload → parse roundtrip.

The backend isn't live yet (T035 is BLOCKED), so the "server
confirms" half is satisfied by the mock. When the real backend
lands this same test shape can point at a staging URL and stay
green; only the fixture changes.
"""
from __future__ import annotations

import json
import re
import threading
from email.parser import BytesParser
from email.policy import default as default_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

import pytest

from tests.helpers import finalize_session


_BOUNDARY_RE = re.compile(r"boundary=(.+)$")


class _IntegrationIngestHandler(BaseHTTPRequestHandler):
    """Mock ADR-012 ingest endpoint that parses real multipart bodies."""

    last_path: str | None = None
    last_idempotency_key: str | None = None
    last_authorization: str | None = None
    last_manifest_json: dict | None = None
    last_chunk_filenames: list[str] = []
    response_status: int = 202
    response_payload: dict[str, str] = {}
    post_count: int = 0

    def do_POST(self) -> None:  # noqa: N802
        type(self).post_count += 1
        type(self).last_path = self.path
        type(self).last_idempotency_key = self.headers.get("Idempotency-Key")
        type(self).last_authorization = self.headers.get("Authorization")

        ctype = self.headers.get("Content-Type", "")
        match = _BOUNDARY_RE.search(ctype)
        if match is None:
            self.send_response(400)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)

        # Parse the multipart body using the stdlib email machinery.
        synthetic = (
            f"Content-Type: {ctype}\r\nMIME-Version: 1.0\r\n\r\n".encode()
            + body
        )
        msg = BytesParser(policy=default_policy).parsebytes(synthetic)
        manifest_json: dict | None = None
        chunk_filenames: list[str] = []
        for part in msg.iter_parts():
            disposition = part.get("Content-Disposition", "")
            field_name = part.get_param("name", header="Content-Disposition")
            filename = part.get_param("filename", header="Content-Disposition")
            payload = part.get_payload(decode=True) or b""
            if field_name == "manifest":
                try:
                    manifest_json = json.loads(payload.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    manifest_json = None
            elif field_name == "chunks[]" and filename:
                chunk_filenames.append(filename)
        type(self).last_manifest_json = manifest_json
        type(self).last_chunk_filenames = chunk_filenames

        body_bytes = json.dumps(type(self).response_payload).encode("utf-8")
        self.send_response(type(self).response_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, *args: object, **kwargs: object) -> None:  # noqa: ANN001
        pass


@pytest.fixture
def ingest_server() -> Iterator[tuple[str, type[_IntegrationIngestHandler]]]:
    H = _IntegrationIngestHandler
    H.last_path = None
    H.last_idempotency_key = None
    H.last_authorization = None
    H.last_manifest_json = None
    H.last_chunk_filenames = []
    H.response_status = 202
    H.response_payload = {
        "session_id": "01900000-0000-7000-8000-00000000a055",
        "ingest_job_id": "01900000-0000-7000-8000-00000000a056",
        "status_stream": "/api/v1/jobs/01900000-0000-7000-8000-00000000a056/events",
    }
    H.post_count = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), H)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}", H
    finally:
        server.shutdown()
        server.server_close()


def test_finalize_then_upload_returns_typed_success(
    tmp_path: Path,
    ingest_server: tuple[str, type[_IntegrationIngestHandler]],
) -> None:
    """The full chain: synthetic samples → finalize → upload → 202."""
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = ingest_server
    bundle_dir = finalize_session(tmp_path / "out", session_uid="t055-end-to-end")

    client = IngestClient(
        base_url=base_url,
        auth_token="t055-token",
        max_retries=0,
        sleep=lambda _s: None,
        manifest_filename="session.json",
    )
    result = client.upload(bundle_dir=bundle_dir)

    assert result.success is True, result.error_message
    assert result.session_id == "01900000-0000-7000-8000-00000000a055"
    assert result.ingest_job_id == "01900000-0000-7000-8000-00000000a056"
    assert result.status_stream_url == (
        "/api/v1/jobs/01900000-0000-7000-8000-00000000a056/events"
    )
    assert handler.post_count == 1
    assert handler.last_path == "/api/v1/sessions/ingest"


def test_uploaded_manifest_matches_what_finalizer_wrote_on_disk(
    tmp_path: Path,
    ingest_server: tuple[str, type[_IntegrationIngestHandler]],
) -> None:
    """Manifest must survive the serialize → multipart → parse roundtrip."""
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = ingest_server
    bundle_dir = finalize_session(tmp_path / "out", session_uid="t055-roundtrip")

    on_disk = json.loads((bundle_dir / "session.json").read_text(encoding="utf-8"))
    client = IngestClient(
        base_url=base_url,
        auth_token="t",
        max_retries=0,
        manifest_filename="session.json",
    )
    client.upload(bundle_dir=bundle_dir)

    assert handler.last_manifest_json is not None, (
        "server should have received a 'manifest' form field"
    )
    # The manifest the server sees must be byte-for-byte the same JSON
    # the finalizer wrote: same session_id, same sim/track, etc.
    assert handler.last_manifest_json == on_disk


def test_upload_streams_real_bundle_chunks_not_just_manifest(
    tmp_path: Path,
    ingest_server: tuple[str, type[_IntegrationIngestHandler]],
) -> None:
    """A finalized bundle has telemetry.parquet + channels.json plus
    optional laps/events. The upload must surface them as ``chunks[]``
    so the backend can reassemble the bundle."""
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = ingest_server
    bundle_dir = finalize_session(tmp_path / "out", session_uid="t055-chunks")

    expected_extras = {p.name for p in bundle_dir.iterdir() if p.name != "session.json"}
    assert expected_extras, "fixture should produce more than just the manifest"

    IngestClient(
        base_url=base_url,
        auth_token="t",
        max_retries=0,
        manifest_filename="session.json",
    ).upload(bundle_dir=bundle_dir)

    # T044 splits chunks at 5 MiB; for a small fixture each file lands as
    # exactly one chunk with a ``part1of1`` suffix. The base names must
    # all be present.
    received_bases = {
        re.sub(r"\.part\d+of\d+$", "", f) for f in handler.last_chunk_filenames
    }
    assert expected_extras.issubset(received_bases)


def test_upload_sends_bearer_auth_and_idempotency_key(
    tmp_path: Path,
    ingest_server: tuple[str, type[_IntegrationIngestHandler]],
) -> None:
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = ingest_server
    bundle_dir = finalize_session(tmp_path / "out", session_uid="t055-headers")

    IngestClient(
        base_url=base_url,
        auth_token="bearer-tok-7",
        max_retries=0,
        manifest_filename="session.json",
    ).upload(bundle_dir=bundle_dir)

    assert handler.last_authorization == "Bearer bearer-tok-7"
    # T043: Idempotency-Key is the UUID7 session_id from the manifest.
    on_disk = json.loads((bundle_dir / "session.json").read_text(encoding="utf-8"))
    assert handler.last_idempotency_key == str(on_disk["session_id"])


def test_second_upload_for_same_bundle_is_short_circuited_by_cursor(
    tmp_path: Path,
    ingest_server: tuple[str, type[_IntegrationIngestHandler]],
) -> None:
    """T045 cursor: a successful upload writes ``.ingest_cursor.json``;
    a subsequent ``upload(bundle_dir=...)`` must skip the network.

    The cursor matches on ``session_id`` — in production the backend
    echoes back the client-supplied session_id, so we mirror that
    here by sharing one UUID7 between the manifest and the mock
    response.
    """
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = ingest_server
    shared_session_id = "01900000-0000-7000-8000-00000000cc55"
    bundle_dir = finalize_session(tmp_path / "out", session_uid=shared_session_id)
    handler.response_payload = {
        **handler.response_payload,
        "session_id": shared_session_id,
    }
    client = IngestClient(
        base_url=base_url,
        auth_token="t",
        max_retries=0,
        manifest_filename="session.json",
    )

    first = client.upload(bundle_dir=bundle_dir)
    assert first.success is True

    second = client.upload(bundle_dir=bundle_dir)
    assert second.success is True
    assert second.session_id == first.session_id
    assert handler.post_count == 1, (
        "second upload must short-circuit on the cursor written by the first"
    )


def test_server_failure_surfaces_typed_error_through_the_full_pipeline(
    tmp_path: Path,
    ingest_server: tuple[str, type[_IntegrationIngestHandler]],
) -> None:
    """Permanent server-side error from a real bundle still returns a
    typed IngestResult, never an exception."""
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = ingest_server
    handler.response_status = 500
    handler.response_payload = {}
    bundle_dir = finalize_session(tmp_path / "out", session_uid="t055-server-fail")

    result = IngestClient(
        base_url=base_url,
        auth_token="t",
        max_retries=0,
        manifest_filename="session.json",
    ).upload(bundle_dir=bundle_dir)

    assert result.success is False
    assert result.http_status == 500
    assert result.error_code == "http_500"
