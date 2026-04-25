"""T048: ``IngestClient.upload`` retries transient failures with exponential backoff.

Transient = URL/socket-level errors (``URLError``/``OSError``) plus
HTTP ``502 Bad Gateway`` / ``503 Service Unavailable`` /
``504 Gateway Timeout``. Permanent failures (4xx, other 5xx) bypass
retries so misconfiguration surfaces immediately. Tests inject a
recording fake ``sleep`` so the suite stays fast and the backoff
schedule is asserted directly.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

import pytest


class _FlappingIngestHandler(BaseHTTPRequestHandler):
    """Mock that returns ``fail_status`` for the first ``fail_count`` POSTs,
    then 202 with the canned payload for every subsequent POST."""

    fail_count: int = 0
    fail_status: int = 503
    post_count: int = 0
    response_body: dict[str, str] = {}

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        type(self).post_count += 1
        if type(self).post_count <= type(self).fail_count:
            self.send_response(type(self).fail_status)
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
def flapping_server() -> Iterator[tuple[str, type[_FlappingIngestHandler]]]:
    _FlappingIngestHandler.fail_count = 0
    _FlappingIngestHandler.fail_status = 503
    _FlappingIngestHandler.post_count = 0
    _FlappingIngestHandler.response_body = {
        "session_id": "01900000-0000-7000-8000-00000000a048",
        "ingest_job_id": "01900000-0000-7000-8000-00000000a049",
        "status_stream": "/api/v1/jobs/01900000-0000-7000-8000-00000000a049/events",
    }
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FlappingIngestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}", _FlappingIngestHandler
    finally:
        server.shutdown()
        server.server_close()


def _seed_bundle(tmp_path: Path) -> Path:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    (bundle_dir / "manifest.json").write_text(
        json.dumps({"session_id": "01900000-0000-7000-8000-00000000a048"}),
        encoding="utf-8",
    )
    (bundle_dir / "telemetry.parquet").write_bytes(b"\x00" * 32)
    return bundle_dir


def test_upload_retries_503_until_server_recovers(
    tmp_path: Path,
    flapping_server: tuple[str, type[_FlappingIngestHandler]],
) -> None:
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = flapping_server
    handler.fail_count = 2  # fail twice, then succeed

    sleeps: list[float] = []
    client = IngestClient(
        base_url=base_url,
        auth_token="t",
        max_retries=3,
        base_backoff_s=0.001,
        sleep=sleeps.append,
    )
    result = client.upload(bundle_dir=_seed_bundle(tmp_path))

    assert result.success is True
    assert handler.post_count == 3, "two 503s + one 202 = three total POSTs"


def test_upload_uses_exponential_backoff_schedule(
    tmp_path: Path,
    flapping_server: tuple[str, type[_FlappingIngestHandler]],
) -> None:
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = flapping_server
    handler.fail_count = 3  # three 503s before success

    sleeps: list[float] = []
    client = IngestClient(
        base_url=base_url,
        auth_token="t",
        max_retries=4,
        base_backoff_s=1.0,
        sleep=sleeps.append,
    )
    client.upload(bundle_dir=_seed_bundle(tmp_path))

    # 1.0, 2.0, 4.0 between the three failures; no sleep after the success.
    assert sleeps == [1.0, 2.0, 4.0]


def test_upload_does_not_retry_4xx_responses(
    tmp_path: Path,
    flapping_server: tuple[str, type[_FlappingIngestHandler]],
) -> None:
    """Permanent failures (400/401/403/404) must not consume retry budget."""
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = flapping_server
    handler.fail_status = 400
    handler.fail_count = 99

    sleeps: list[float] = []
    client = IngestClient(
        base_url=base_url,
        auth_token="t",
        max_retries=3,
        base_backoff_s=0.001,
        sleep=sleeps.append,
    )
    result = client.upload(bundle_dir=_seed_bundle(tmp_path))

    assert result.success is False
    assert result.http_status == 400
    assert handler.post_count == 1, "4xx must not trigger retries"
    assert sleeps == []


def test_upload_gives_up_after_max_retries_on_persistent_503(
    tmp_path: Path,
    flapping_server: tuple[str, type[_FlappingIngestHandler]],
) -> None:
    from lap_coach_logger.infra.ingest import IngestClient

    base_url, handler = flapping_server
    handler.fail_count = 99  # always fail

    sleeps: list[float] = []
    client = IngestClient(
        base_url=base_url,
        auth_token="t",
        max_retries=2,
        base_backoff_s=0.001,
        sleep=sleeps.append,
    )
    result = client.upload(bundle_dir=_seed_bundle(tmp_path))

    assert result.success is False
    assert result.http_status == 503
    assert handler.post_count == 3, "1 initial + 2 retries = 3 attempts"
    assert len(sleeps) == 2  # one sleep between each failure


def test_upload_retries_on_connection_refused(tmp_path: Path) -> None:
    """Connection-level errors (no server listening) must trigger retries."""
    from lap_coach_logger.infra.ingest import IngestClient

    sleeps: list[float] = []
    client = IngestClient(
        base_url="http://127.0.0.1:1",  # tcpmux — guaranteed refusal
        auth_token="t",
        max_retries=2,
        base_backoff_s=0.001,
        sleep=sleeps.append,
    )
    result = client.upload(bundle_dir=_seed_bundle(tmp_path))

    assert result.success is False
    assert result.error_code == "connection_error"
    assert len(sleeps) == 2, "two retries on persistent connection failure"
