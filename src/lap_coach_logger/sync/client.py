"""Sync client — routes envelopes through typed endpoints with retry.

Pulls envelopes from the SyncQueue, groups same-type envelopes into
batches, routes each batch to its endpoint via HttpTransport, and
moves permanent failures to SyncFailureStore.

Runs in a daemon thread. Never blocks the UI.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

from lap_coach_logger.sync.endpoints import (
    build_request_body,
    get_endpoint,
)
from lap_coach_logger.sync.failure_store import SyncFailureStore
from lap_coach_logger.sync.http_transport import (
    HttpTransport,
    TransportConfig,
    TransportOutcome,
    TransportResult,
)
from lap_coach_logger.sync.queue import SyncQueue
from lap_coach_logger.sync.schema import SyncEnvelope

log = logging.getLogger(__name__)

_IDLE_SLEEP_S = 3.0
_RETRY_SLEEP_S = 15.0


class SyncClient:
    """Background sync client. Drains SyncQueue through typed endpoints."""

    def __init__(
        self,
        queue: SyncQueue,
        failure_store: SyncFailureStore,
        transport: HttpTransport,
        *,
        idle_sleep_s: float = _IDLE_SLEEP_S,
        retry_sleep_s: float = _RETRY_SLEEP_S,
    ) -> None:
        self._queue = queue
        self._failure_store = failure_store
        self._transport = transport
        self._idle_sleep_s = idle_sleep_s
        self._retry_sleep_s = retry_sleep_s
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._last_sync_time: str | None = None
        self._last_outcome: str | None = None
        self._last_error: str = ""
        # unknown / online / offline / auth_failed
        self._connection_state: str = "unknown"

    # -- public API ---------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def queue_depth(self) -> int:
        return self._queue.depth

    @property
    def failed_count(self) -> int:
        return self._failure_store.count()

    @property
    def last_sync_time(self) -> str | None:
        with self._lock:
            return self._last_sync_time

    @property
    def last_outcome(self) -> str | None:
        with self._lock:
            return self._last_outcome

    @property
    def last_error(self) -> str:
        with self._lock:
            return self._last_error

    @property
    def connection_state(self) -> str:
        with self._lock:
            return self._connection_state

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, name="sync-client", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def retry_failure(self, envelope_id: str) -> bool:
        """Re-enqueue a failed envelope. Returns True if re-queued."""
        record = self._failure_store.get(envelope_id)
        if record is None:
            return False
        envelope = SyncEnvelope.from_dict(record.envelope)
        # Reset attempt count so transport gets a fresh window
        envelope = SyncEnvelope(
            envelope_id=envelope.envelope_id,
            payload_type=envelope.payload_type,
            payload=envelope.payload,
            created_at=envelope.created_at,
            attempt_count=0,
        )
        # SyncQueue dedup tracks seen_ids; remove so re-enqueue is accepted.
        self._queue._seen_ids.discard(envelope_id)  # type: ignore[attr-defined]
        success = self._queue.enqueue(envelope)
        if success:
            self._failure_store.mark_retried(envelope_id)
            self._failure_store.discard(envelope_id)
        return success

    # -- internal loop ------------------------------------------------------

    def _run(self) -> None:
        while self._running:
            batch = self._peek_batch()
            if not batch:
                time.sleep(self._idle_sleep_s)
                continue
            self._process_batch(batch)

    def _peek_batch(self) -> list[SyncEnvelope]:
        """Peek the next envelope to send.

        v1 sends one envelope at a time because SyncQueue only exposes
        ``peek()`` for the head. True same-type batching would require a
        ``peek_many`` API; left as a follow-up.
        """
        first = self._queue.peek()
        if first is None:
            return []
        spec = get_endpoint(first.payload_type)
        if spec is None:
            # Unknown payload_type — move to failure store
            self._move_to_failures(
                first,
                reason=f"Unknown payload_type: {first.payload_type}",
                category="corrupted",
                http_status=None,
            )
            return []
        return [first]

    def _process_batch(self, batch: list[SyncEnvelope]) -> None:
        if not batch:
            return
        first = batch[0]
        spec = get_endpoint(first.payload_type)
        if spec is None:
            for env in batch:
                self._move_to_failures(
                    env,
                    reason=f"Unknown payload_type: {env.payload_type}",
                    category="corrupted",
                    http_status=None,
                )
            return

        # Build request body
        try:
            env_dicts = [e.to_dict() for e in batch]
            body = build_request_body(first.payload_type, env_dicts)
        except ValueError as e:
            for env in batch:
                self._move_to_failures(
                    env, reason=str(e), category="corrupted", http_status=None
                )
            return

        # Use the first envelope's ID as the batch idempotency key
        idempotency_key = first.envelope_id

        result = self._transport.post(
            path=spec.path,
            body=body,
            idempotency_key=idempotency_key,
            idempotency_header=spec.idempotency_header,
        )

        self._record_result(result)

        if result.outcome == TransportOutcome.SUCCESS:
            for env in batch:
                self._queue.ack(env.envelope_id)
        elif result.outcome == TransportOutcome.PERMANENT_FAILURE:
            for env in batch:
                # remove from queue first, then record failure
                self._queue.ack(env.envelope_id)
                self._move_to_failures(
                    env,
                    reason=result.error_message,
                    category="permanent",
                    http_status=result.http_status,
                    attempt_count=result.attempt_count,
                )
        elif result.outcome == TransportOutcome.AUTH_FAILURE:
            # Don't drop — sit in queue until token is fixed
            for env in batch:
                self._queue.nack(env.envelope_id)
            time.sleep(self._retry_sleep_s)
        elif result.outcome == TransportOutcome.RETRY:
            for env in batch:
                self._queue.nack(env.envelope_id)
                # If a single envelope hits max_retries via SyncQueue, it
                # gets dropped. Catch that by checking if it's still in the
                # queue — if not, record failure.
                still_queued = any(
                    e.get("envelope_id") == env.envelope_id
                    for e in self._queue._queue  # type: ignore[attr-defined]
                )
                if not still_queued:
                    self._move_to_failures(
                        env,
                        reason=result.error_message,
                        category="exhausted_retries",
                        http_status=result.http_status,
                        attempt_count=result.attempt_count,
                    )
            time.sleep(self._retry_sleep_s)

    def _record_result(self, result: TransportResult) -> None:
        with self._lock:
            self._last_sync_time = datetime.now(timezone.utc).isoformat()
            self._last_outcome = result.outcome.value
            self._last_error = result.error_message
            if result.outcome == TransportOutcome.SUCCESS:
                self._connection_state = "online"
            elif result.outcome == TransportOutcome.AUTH_FAILURE:
                self._connection_state = "auth_failed"
            elif result.outcome == TransportOutcome.RETRY:
                self._connection_state = "offline"
            # PERMANENT_FAILURE: leave connection_state as-is

    def _move_to_failures(
        self,
        envelope: SyncEnvelope,
        reason: str,
        category: str,
        http_status: int | None,
        attempt_count: int = 1,
    ) -> None:
        self._failure_store.record(
            envelope=envelope.to_dict(),
            reason=reason,
            category=category,
            http_status=http_status,
            attempt_count=attempt_count,
        )
        # Remove from queue if still there
        self._queue.ack(envelope.envelope_id)


def build_sync_client(
    queue: SyncQueue,
    failure_store: SyncFailureStore,
    base_url: str,
    device_token: str = "",
    api_key: str = "",
) -> SyncClient:
    """Factory — constructs a SyncClient with default transport config."""
    config = TransportConfig(
        base_url=base_url,
        device_token=device_token,
        api_key=api_key,
    )
    transport = HttpTransport(config)
    return SyncClient(queue=queue, failure_store=failure_store, transport=transport)
