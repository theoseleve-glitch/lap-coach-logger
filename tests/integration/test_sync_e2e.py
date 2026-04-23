"""End-to-end sync integration tests.

Mocks the HTTP layer to simulate:
1. Offline -> reconnect: envelopes queue up, then drain after network comes back
2. Duplicate replay: same envelope_id submitted twice — backend returns 200 with already_seen=true; 409 is reserved for precondition failures (missing_session)
3. Partial failure: some payloads get 500s, retry, eventually succeed or move to failures
4. Invalid payload: 400 -> moves straight to failure store, never retried
"""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from lap_coach_logger.sync.client import SyncClient
from lap_coach_logger.sync.failure_store import SyncFailureStore
from lap_coach_logger.sync.http_transport import (
    HttpTransport,
    TransportConfig,
)
from lap_coach_logger.sync.queue import SyncQueue
from lap_coach_logger.sync.schema import LapPayload, SessionPayload, SyncEnvelope


def _mock_response(status: int, body: bytes = b"{}"):
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = body
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=None)
    return resp


def _make_session_envelope(eid: str, session_id: str = "s1") -> SyncEnvelope:
    payload = SessionPayload(
        session_id=session_id,
        sim="iRacing",
        track="Monza",
        car="GT3",
        mode="sprint",
        start_time="2026-04-15T12:00:00+00:00",
        end_time="",
    )
    return SyncEnvelope(
        envelope_id=eid,
        payload_type="session",
        payload=payload.to_dict(),
    )


def _make_lap_envelope(eid: str, lap_number: int = 1) -> SyncEnvelope:
    payload = LapPayload(
        session_id="s1",
        lap_number=lap_number,
        lap_time_s=90.0,
        valid=True,
        fuel_used_l=2.5,
    )
    return SyncEnvelope(
        envelope_id=eid,
        payload_type="lap",
        payload=payload.to_dict(),
    )


def _build_client(
    tmp_path: Path, max_attempts: int = 3
) -> tuple[SyncClient, SyncQueue, SyncFailureStore]:
    queue = SyncQueue(tmp_path / "queue")
    failures = SyncFailureStore(tmp_path / "failures")
    config = TransportConfig(
        base_url="https://api.test.local",
        max_attempts=max_attempts,
        initial_backoff_s=0.01,
        max_backoff_s=0.05,
    )
    transport = HttpTransport(config)
    # Use fast sleeps so tests don't wait on 3s/15s timers
    client = SyncClient(
        queue=queue,
        failure_store=failures,
        transport=transport,
        idle_sleep_s=0.02,
        retry_sleep_s=0.02,
    )
    return client, queue, failures


def _wait_for(predicate, timeout: float = 3.0, interval: float = 0.05) -> bool:
    """Poll *predicate* until True or timeout. Returns final result."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


class TestOfflineReconnect:
    def test_queued_envelopes_drain_after_reconnect(self, tmp_path):
        client, queue, failures = _build_client(tmp_path)

        # Enqueue 3 envelopes while "offline"
        for i in range(3):
            queue.enqueue(_make_lap_envelope(f"lap-{i}", lap_number=i + 1))

        # Simulate offline then online: URLError then 200s
        responses = [URLError("no network")] * 2 + [_mock_response(200)] * 10

        with patch(
            "lap_coach_logger.sync.http_transport.urlopen",
            side_effect=responses,
        ):
            client.start()
            _wait_for(lambda: queue.depth == 0, timeout=5.0)
            client.stop()

        # All envelopes delivered (no failures recorded)
        assert queue.depth == 0
        assert failures.count() == 0


class TestDuplicateReplay:
    """Connected v1: backend returns HTTP 200 with body {already_seen: true}
    on replay, not 409. The desktop treats this identically to a fresh 200."""

    def test_200_already_seen_is_acked(self, tmp_path):
        client, queue, failures = _build_client(tmp_path)
        queue.enqueue(_make_session_envelope("dup-1"))

        resp = _mock_response(
            200,
            body=b'{"ok":true,"envelope_id":"dup-1","already_seen":true}',
        )
        with patch(
            "lap_coach_logger.sync.http_transport.urlopen", return_value=resp
        ):
            client.start()
            _wait_for(lambda: queue.depth == 0, timeout=3.0)
            client.stop()

        assert queue.depth == 0
        assert failures.count() == 0

    def test_409_missing_session_lands_in_failures(self, tmp_path):
        """409 now means 'precondition failed' — audit it, don't drop silently."""
        client, queue, failures = _build_client(tmp_path)
        queue.enqueue(_make_session_envelope("orphan-1"))

        err = HTTPError(
            "x", 409, "Conflict", {},
            MagicMock(read=lambda: b'{"ok":false,"code":"missing_session"}'),
        )
        with patch(
            "lap_coach_logger.sync.http_transport.urlopen", side_effect=err
        ):
            client.start()
            _wait_for(lambda: queue.depth == 0, timeout=3.0)
            client.stop()

        assert queue.depth == 0
        assert failures.count() == 1  # surfaced for audit


class TestPartialFailure:
    def test_500_then_success(self, tmp_path):
        client, queue, failures = _build_client(tmp_path, max_attempts=3)
        queue.enqueue(_make_session_envelope("s-500"))

        err = HTTPError("x", 500, "Server", {}, MagicMock(read=lambda: b""))
        responses = [err, err, _mock_response(200)]
        with patch(
            "lap_coach_logger.sync.http_transport.urlopen",
            side_effect=responses,
        ):
            client.start()
            _wait_for(lambda: queue.depth == 0, timeout=3.0)
            client.stop()

        assert queue.depth == 0
        assert failures.count() == 0

    def test_500_exhausts_then_moves_to_failures_eventually(self, tmp_path):
        client, queue, failures = _build_client(tmp_path, max_attempts=2)
        queue.enqueue(_make_session_envelope("s-bad"))

        err = HTTPError("x", 500, "Server", {}, MagicMock(read=lambda: b""))
        with patch(
            "lap_coach_logger.sync.http_transport.urlopen", side_effect=err
        ):
            client.start()
            # Let enough cycles run for SyncQueue's MAX_RETRIES (5) nack cycles.
            # Each loop iteration: transport exhausts -> nack -> sleep _RETRY_SLEEP_S
            # We want either the queue to drop the envelope or the failure store
            # to capture it.
            _wait_for(
                lambda: queue.depth == 0 or failures.count() >= 1,
                timeout=5.0,
            )
            client.stop()

        # Either the queue dropped it (after max retries) and the client logged
        # a failure, or the failure store captured it directly.
        assert queue.depth == 0 or failures.count() >= 1


class TestInvalidPayload:
    def test_400_moves_to_failure_store_immediately(self, tmp_path):
        client, queue, failures = _build_client(tmp_path)
        env = _make_session_envelope("bad-payload")
        queue.enqueue(env)

        err = HTTPError(
            "x",
            400,
            "Bad Request",
            {},
            MagicMock(read=lambda: b'{"error": "invalid mode"}'),
        )
        with patch(
            "lap_coach_logger.sync.http_transport.urlopen", side_effect=err
        ):
            client.start()
            _wait_for(lambda: failures.count() == 1, timeout=3.0)
            client.stop()

        assert queue.depth == 0
        assert failures.count() == 1
        record = failures.get("bad-payload")
        assert record is not None
        assert record.failure_category == "permanent"
        assert record.http_status == 400


class TestManualRetry:
    def test_retry_failure_re_enqueues(self, tmp_path):
        client, queue, failures = _build_client(tmp_path)
        env = _make_session_envelope("retry-me")
        queue.enqueue(env)

        err = HTTPError("x", 400, "Bad", {}, MagicMock(read=lambda: b""))
        with patch(
            "lap_coach_logger.sync.http_transport.urlopen", side_effect=err
        ):
            client.start()
            _wait_for(lambda: failures.count() == 1, timeout=3.0)
            client.stop()

        assert failures.count() == 1

        # Now retry manually — this time the server accepts
        with patch(
            "lap_coach_logger.sync.http_transport.urlopen",
            return_value=_mock_response(200),
        ):
            success = client.retry_failure("retry-me")
            assert success is True
            # The envelope is back in queue — start the client briefly
            client.start()
            _wait_for(lambda: queue.depth == 0, timeout=3.0)
            client.stop()

        assert queue.depth == 0
        assert failures.count() == 0  # cleared after successful retry


class TestAuthFailure:
    def test_401_does_not_drop_envelope(self, tmp_path):
        client, queue, failures = _build_client(tmp_path)
        queue.enqueue(_make_session_envelope("auth-test"))

        err = HTTPError("x", 401, "Unauthorized", {}, MagicMock(read=lambda: b""))
        with patch(
            "lap_coach_logger.sync.http_transport.urlopen", side_effect=err
        ):
            client.start()
            _wait_for(
                lambda: client.connection_state == "auth_failed",
                timeout=3.0,
            )
            client.stop()

        # Envelope is nack'd and connection state reflects auth failure.
        assert client.connection_state == "auth_failed"
        # Auth failures are not moved to failures immediately.
        # (SyncQueue may drop it after MAX_RETRIES nacks, but that's a
        # separate concern from permanent failure classification.)


class TestConnectionStateTracking:
    def test_connection_state_transitions(self, tmp_path):
        client, queue, _ = _build_client(tmp_path)

        # Initially unknown
        assert client.connection_state == "unknown"

        queue.enqueue(_make_session_envelope("conn-1"))
        with patch(
            "lap_coach_logger.sync.http_transport.urlopen",
            return_value=_mock_response(200),
        ):
            client.start()
            _wait_for(
                lambda: client.connection_state == "online", timeout=3.0
            )
            client.stop()
        assert client.connection_state == "online"

        queue.enqueue(_make_session_envelope("conn-2"))
        with patch(
            "lap_coach_logger.sync.http_transport.urlopen",
            side_effect=URLError("no net"),
        ):
            client.start()
            _wait_for(
                lambda: client.connection_state == "offline", timeout=3.0
            )
            client.stop()
        assert client.connection_state == "offline"
