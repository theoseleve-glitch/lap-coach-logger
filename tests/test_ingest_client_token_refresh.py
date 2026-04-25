"""T049: Silent Clerk token refresh on 401.

When the backend rejects an upload with ``401 Unauthorized``, the
client invokes the injected ``auth_refresh`` callable to mint a
fresh token, then re-issues the same upload with the new
Authorization header. The refresh is silent: from the caller's
perspective the upload simply succeeds (or surfaces a final error
if even the refreshed token is rejected).

The refresh callable is injected (not imported from a Clerk SDK)
so unit tests stay hermetic and the production wiring can be a
real ``Clerk.create_client().sessions.create_token()`` call when
the auth dependency lands.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

import pytest


class _AuthIngestHandler(BaseHTTPRequestHandler):
    """Mock that returns 401 until a request arrives with ``valid_token``."""

    valid_token: str = "fresh-token"
    last_auth_header: str | None = None
    post_count: int = 0
    response_body: dict[str, str] = {}

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        type(self).post_count += 1
        type(self).last_auth_header = self.headers.get("Authorization")
        if type(self).last_auth_header != f"Bearer {type(self).valid_token}":
            self.send_response(401)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        payload = json.dumps(type(self).response_body).encode("utf-8")
        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args: object, **kwargs: object) -> None:  # noqa: ANN001
        pass


@pytest.fixture
def auth_server() -> Iterator[tuple[str, type[_AuthIngestHandler]]]:
    _AuthIngestHandler.valid_token = "fresh-token"
    _AuthIngestHandler.last_auth_header = None
    _AuthIngestHandler.post_count = 0
    _AuthIngestHandler.response_body = {
        "session_id": "01900000-0000-7000-8000-00000000a049",
        "ingest_job_id": "01900000-0000-7000-8000-00000000a04a",
        "status_stream": "/api/v1/jobs/01900000-0000-7000-8000-00000000a04a/events",
    }
    server = ThreadingHTTPServer(("127.0.0.1", 0), _AuthIngestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}", _AuthIngestHandler
    finally:
        server.shutdown()
        server.server_close()


def _seed_bundle(tmp_path: Path) -> Path:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "manifest.json").write_text(
        json.dumps({"session_id": "01900000-0000-7000-8000-00000000a049"}),
        encoding="utf-8",
    )
    (bundle_dir / "telemetry.parquet").write_bytes(b"\x00" * 32)
    return bundle_dir


def test_401_triggers_refresh_and_retry_with_new_token(
    tmp_path: Path,
    auth_server: tuple[str, type[_AuthIngestHandler]],
) -> None:
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = auth_server
    refresh_calls = 0

    def _refresh() -> str:
        nonlocal refresh_calls
        refresh_calls += 1
        return "fresh-token"

    client = IngestClient(
        base_url=base_url,
        auth_token="stale-token",
        auth_refresh=_refresh,
        max_retries=0,
        sleep=lambda _s: None,
    )
    result = client.upload(bundle_dir=_seed_bundle(tmp_path))

    assert result.success is True, result.error_message
    assert refresh_calls == 1
    assert handler.post_count == 2  # original 401 + retry with new token
    assert handler.last_auth_header == "Bearer fresh-token"


def test_no_auth_refresh_means_401_surfaces_immediately(
    tmp_path: Path,
    auth_server: tuple[str, type[_AuthIngestHandler]],
) -> None:
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = auth_server
    handler.valid_token = "never-going-to-match"

    client = IngestClient(
        base_url=base_url,
        auth_token="stale-token",
        max_retries=0,  # T049 refresh path is independent of T048 retries
        sleep=lambda _s: None,
    )
    result = client.upload(bundle_dir=_seed_bundle(tmp_path))

    assert result.success is False
    assert result.http_status == 401
    assert handler.post_count == 1, "no auth_refresh → no retry"


def test_refresh_called_at_most_once_per_upload(
    tmp_path: Path,
    auth_server: tuple[str, type[_AuthIngestHandler]],
) -> None:
    """If the refreshed token is also rejected, fail — don't loop."""
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = auth_server
    handler.valid_token = "this-server-rejects-everything"
    refresh_calls = 0

    def _refresh() -> str:
        nonlocal refresh_calls
        refresh_calls += 1
        return "still-not-good-enough"

    client = IngestClient(
        base_url=base_url,
        auth_token="stale-token",
        auth_refresh=_refresh,
        max_retries=0,
        sleep=lambda _s: None,
    )
    result = client.upload(bundle_dir=_seed_bundle(tmp_path))

    assert result.success is False
    assert result.http_status == 401
    assert refresh_calls == 1, "refresh must be called exactly once"
    assert handler.post_count == 2  # original + one refreshed retry


def test_refresh_failure_surfaces_original_401(
    tmp_path: Path,
    auth_server: tuple[str, type[_AuthIngestHandler]],
) -> None:
    """If the refresh callable raises, the upload returns the original 401."""
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, _ = auth_server

    def _refresh() -> str:
        raise RuntimeError("Clerk session expired; re-login required")

    client = IngestClient(
        base_url=base_url,
        auth_token="stale-token",
        auth_refresh=_refresh,
        max_retries=0,
        sleep=lambda _s: None,
    )
    result = client.upload(bundle_dir=_seed_bundle(tmp_path))

    assert result.success is False
    assert result.http_status == 401


def test_successful_refresh_updates_persistent_token_for_next_upload(
    tmp_path: Path,
    auth_server: tuple[str, type[_AuthIngestHandler]],
) -> None:
    """After a refresh, the new token is reused without re-refreshing."""
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = auth_server
    refresh_calls = 0

    def _refresh() -> str:
        nonlocal refresh_calls
        refresh_calls += 1
        return "fresh-token"

    client = IngestClient(
        base_url=base_url,
        auth_token="stale-token",
        auth_refresh=_refresh,
        max_retries=0,
        sleep=lambda _s: None,
    )
    # First upload: 401 → refresh → 202. Cached cursor written.
    client.upload(bundle_dir=_seed_bundle(tmp_path))
    # Second upload uses a different bundle so the cursor doesn't short-circuit.
    second_bundle = tmp_path / "bundle2"
    second_bundle.mkdir()
    (second_bundle / "manifest.json").write_text(
        json.dumps({"session_id": "01900000-0000-7000-8000-0000000049ff"}),
        encoding="utf-8",
    )
    (second_bundle / "telemetry.parquet").write_bytes(b"\x00" * 16)
    handler.response_body = {
        "session_id": "01900000-0000-7000-8000-0000000049ff",
        "ingest_job_id": "01900000-0000-7000-8000-000000004a00",
        "status_stream": "/api/v1/jobs/01900000-0000-7000-8000-000000004a00/events",
    }

    result = client.upload(bundle_dir=second_bundle)

    assert result.success is True
    assert refresh_calls == 1, "refreshed token persists; no second refresh needed"
