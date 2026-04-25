"""T054: ``IngestClient.upload`` per-status path coverage.

The existing test files cover behaviour by *topic* — retries
(T048), token refresh (T049), resume (T045), happy path (T042).
This file complements them by enumerating the per-status contract
in one place so a future reader can answer "what happens on a 403?
on a 500? on malformed JSON?" without grepping five files.

Status-code contract:

  * 2xx                — typed success; ``session_id`` /
                          ``ingest_job_id`` extracted from JSON body.
  * 4xx (400/403/404)  — permanent failure; no retry; surfaces with
                          ``error_code = "http_<code>"``.
  * 401                — handled by T049 token-refresh path
                          (covered in test_ingest_client_token_refresh).
  * 5xx 500 (and other
    non-listed 5xx)    — permanent failure; no retry. Distinct from
                          502/503/504 because 500 means "the server
                          processed the request and it broke" —
                          retrying won't change the outcome.
  * 5xx 502/503/504    — transient; retried with exponential backoff
                          per the T048 ``_TRANSIENT_HTTP_STATUSES`` set.
  * Network            — ``URLError`` / ``OSError`` →
                          ``error_code = "connection_error"`` (retried).
  * Malformed 2xx body — typed failure with
                          ``error_code = "malformed_response"`` rather
                          than an unhandled ``json.JSONDecodeError``.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

import pytest


class _StatusHandler(BaseHTTPRequestHandler):
    """Mock that returns ``status`` with ``body`` for every POST.

    Counts requests so tests can assert "did/didn't retry".
    """

    status: int = 200
    body: bytes = b"{}"
    content_type: str = "application/json"
    post_count: int = 0

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        type(self).post_count += 1
        self.send_response(type(self).status)
        if type(self).body:
            self.send_header("Content-Type", type(self).content_type)
            self.send_header("Content-Length", str(len(type(self).body)))
            self.end_headers()
            self.wfile.write(type(self).body)
        else:
            self.send_header("Content-Length", "0")
            self.end_headers()

    def log_message(self, *args: object, **kwargs: object) -> None:  # noqa: ANN001
        pass


@pytest.fixture
def status_server() -> Iterator[tuple[str, type[_StatusHandler]]]:
    _StatusHandler.status = 202
    _StatusHandler.body = json.dumps(
        {
            "session_id": "01900000-0000-7000-8000-00000000a054",
            "ingest_job_id": "01900000-0000-7000-8000-00000000a055",
            "status_stream": "/api/v1/jobs/01900000-0000-7000-8000-00000000a055/events",
        }
    ).encode("utf-8")
    _StatusHandler.content_type = "application/json"
    _StatusHandler.post_count = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StatusHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}", _StatusHandler
    finally:
        server.shutdown()
        server.server_close()


def _seed_bundle(tmp_path: Path) -> Path:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "manifest.json").write_text(
        json.dumps({"session_id": "01900000-0000-7000-8000-00000000a054"}),
        encoding="utf-8",
    )
    (bundle_dir / "telemetry.parquet").write_bytes(b"\x00" * 32)
    return bundle_dir


def _client(base_url: str, sleeps: list[float]):
    from lap_coach_logger.infra.ingest import IngestClient

    return IngestClient(
        base_url=base_url,
        auth_token="t",
        max_retries=2,
        base_backoff_s=0.001,
        sleep=sleeps.append,
    )


# ---------------------------------------------------------------------------
# Happy path: 200 and 202 both treated as success
# ---------------------------------------------------------------------------


def test_2xx_200_is_treated_as_success_just_like_202(
    tmp_path: Path,
    status_server: tuple[str, type[_StatusHandler]],
) -> None:
    """ADR-012 mandates 202, but the client must not crash if the
    server happens to respond 200."""
    base_url, handler = status_server
    handler.status = 200

    sleeps: list[float] = []
    result = _client(base_url, sleeps).upload(bundle_dir=_seed_bundle(tmp_path))

    assert result.success is True
    assert result.http_status == 200
    assert result.session_id == "01900000-0000-7000-8000-00000000a054"


# ---------------------------------------------------------------------------
# 4xx — permanent failures, no retry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [400, 403, 404])
def test_4xx_returns_typed_failure_with_no_retry(
    tmp_path: Path,
    status_server: tuple[str, type[_StatusHandler]],
    status: int,
) -> None:
    """400/403/404 are misconfiguration / auth / route problems —
    surface them immediately so they don't hide under retry noise."""
    base_url, handler = status_server
    handler.status = status
    handler.body = b""

    sleeps: list[float] = []
    result = _client(base_url, sleeps).upload(bundle_dir=_seed_bundle(tmp_path))

    assert result.success is False
    assert result.http_status == status
    assert result.error_code == f"http_{status}"
    assert handler.post_count == 1, "permanent failure must not trigger retries"
    assert sleeps == []


# ---------------------------------------------------------------------------
# 5xx — split: 500 is permanent, 502/503/504 are transient
# ---------------------------------------------------------------------------


def test_5xx_500_is_permanent_and_not_retried(
    tmp_path: Path,
    status_server: tuple[str, type[_StatusHandler]],
) -> None:
    """500 means the server processed and broke — retrying won't help."""
    base_url, handler = status_server
    handler.status = 500
    handler.body = b""

    sleeps: list[float] = []
    result = _client(base_url, sleeps).upload(bundle_dir=_seed_bundle(tmp_path))

    assert result.success is False
    assert result.http_status == 500
    assert result.error_code == "http_500"
    assert handler.post_count == 1
    assert sleeps == []


@pytest.mark.parametrize("status", [502, 503, 504])
def test_5xx_transient_statuses_are_retried_until_budget_exhausted(
    tmp_path: Path,
    status_server: tuple[str, type[_StatusHandler]],
    status: int,
) -> None:
    """502/503/504 are gateway/availability problems — retry with backoff."""
    base_url, handler = status_server
    handler.status = status
    handler.body = b""

    sleeps: list[float] = []
    client = _client(base_url, sleeps)  # max_retries=2
    result = client.upload(bundle_dir=_seed_bundle(tmp_path))

    assert result.success is False
    assert result.http_status == status
    assert handler.post_count == 3, "1 initial + 2 retries on transient 5xx"
    assert len(sleeps) == 2


# ---------------------------------------------------------------------------
# Malformed 2xx body — typed failure rather than unhandled exception
# ---------------------------------------------------------------------------


def test_2xx_with_invalid_json_body_returns_typed_malformed_response(
    tmp_path: Path,
    status_server: tuple[str, type[_StatusHandler]],
) -> None:
    """A 200/202 with garbled JSON must return ``error_code =
    "malformed_response"`` instead of letting ``json.JSONDecodeError``
    propagate to the caller."""
    base_url, handler = status_server
    handler.status = 202
    handler.body = b"<html>oh no, a misconfigured proxy</html>"
    handler.content_type = "text/html"

    sleeps: list[float] = []
    result = _client(base_url, sleeps).upload(bundle_dir=_seed_bundle(tmp_path))

    assert result.success is False
    assert result.http_status == 202
    assert result.error_code == "malformed_response"
    assert handler.post_count == 1, "malformed body is NOT a transient failure"


def test_2xx_with_empty_body_is_treated_as_success_with_no_payload_fields(
    tmp_path: Path,
    status_server: tuple[str, type[_StatusHandler]],
) -> None:
    """A 202 with an empty body is technically valid (no payload) —
    the call still succeeded, just without job tracking metadata."""
    base_url, handler = status_server
    handler.status = 202
    handler.body = b""

    sleeps: list[float] = []
    result = _client(base_url, sleeps).upload(bundle_dir=_seed_bundle(tmp_path))

    assert result.success is True
    assert result.http_status == 202
    assert result.session_id is None
    assert result.ingest_job_id is None


# ---------------------------------------------------------------------------
# Network errors — connection-level paths
# ---------------------------------------------------------------------------


def test_network_error_dns_resolution_failure_is_typed_connection_error(
    tmp_path: Path,
) -> None:
    """A non-resolvable hostname must surface as ``connection_error``,
    not a raw socket exception."""
    sleeps: list[float] = []
    client = _client("http://this-host-does-not-exist.invalid", sleeps)

    result = client.upload(bundle_dir=_seed_bundle(tmp_path))

    assert result.success is False
    assert result.error_code == "connection_error"
    # The .invalid TLD is reserved per RFC 6761 — DNS will fail fast.
    # All three attempts share the same error path; sleeps == [s1, s2].
    assert len(sleeps) == 2
