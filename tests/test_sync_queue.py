"""Tests for the offline-first sync queue.

This file covers TWO sync-queue implementations that currently coexist:

1. ``lap_coach_logger.core.sync_queue.SyncQueueManager`` — the original
   session-bundle queue (finalized-bundle uploads). Tests live in
   :class:`TestSyncQueueManager` below.

2. ``lap_coach_logger.sync.queue.SyncQueue`` — the newer envelope-based
   queue introduced as part of the webapp-sync v1 work. Tests are the
   module-level ``test_*`` functions.

Conflict-merge note (2026-04-23, cycle-1 remediation): origin's PR #1
added the ``test_process_queue_drops_entry_after_max_retry_attempts`` test
to the old implementation; local commit ``6b2b459`` introduced the new
subsystem with its own test suite. Both sets are preserved here.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Imports for the old SyncQueueManager subsystem (origin PR #1):
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.core.sync_queue import MAX_SYNC_ATTEMPTS, SyncQueueManager
from lap_coach_logger.core.sync_service import SyncAttemptResult
from lap_coach_logger.writers.finalizer import SessionFinalizer

# Imports for the new SyncQueue subsystem (local 6b2b459):
from lap_coach_logger.sync.queue import MAX_RETRIES, SyncQueue
from lap_coach_logger.sync.schema import SyncEnvelope


# -- Helpers -----------------------------------------------------------------

def _make_samples() -> list[TelemetrySample]:
    """Build a ~3-minute synthetic telemetry sample stream for bundle tests."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    samples: list[TelemetrySample] = []
    for i in range(180):
        samples.append(
            TelemetrySample(
                timestamp_utc=(start + timedelta(seconds=i)).isoformat(),
                sim="iRacing",
                session_uid="sync-test",
                session_time_s=float(i),
                lap_number=1 + (i // 30),
                lap_distance_m=float((i % 30) * 120),
                lap_dist_pct=float((i % 30) / 29),
                speed_kph=125.0,
                throttle_pct=0.7,
                brake_pct=0.0,
                steering_deg=0.0,
                gear=4,
                rpm=5300.0,
                world_pos_x=float(i),
                world_pos_y=0.0,
                world_pos_z=0.0,
                yaw_deg=0.0,
                long_accel_g=0.1,
                lat_accel_g=0.1,
                is_on_track=True,
                is_in_pits=False,
                track_name="Spa",
                car_name="GT3",
                session_type="Race",
            )
        )
    return samples


def _finalize_bundle(tmp_path: Path) -> Path:
    """Finalize a session bundle in ``tmp_path`` and return its directory."""
    finalizer = SessionFinalizer(tmp_path)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = finalizer.finalize(
        _make_samples(),
        started_at=now,
        ended_at=now + timedelta(seconds=179),
        sim="iRacing",
        track="Spa",
        session_type="Race",
        session_uid="sync-test",
        extra_metadata={"car": "GT3", "sample_rate_hz": 1.0},
    )
    assert result is not None
    return result


def _make_queue(tmp_path: Path) -> SyncQueue:
    """Construct a fresh envelope-based SyncQueue rooted at ``tmp_path``."""
    return SyncQueue(tmp_path)


# -- Tests for the new envelope-based SyncQueue (from 6b2b459) ---------------

def test_enqueue_and_peek(tmp_path: Path):
    q = _make_queue(tmp_path)
    env = SyncEnvelope(payload_type="session", payload={"id": "s1"})
    assert q.enqueue(env) is True
    peeked = q.peek()
    assert peeked is not None
    assert peeked.envelope_id == env.envelope_id


def test_ack_removes_from_queue(tmp_path: Path):
    q = _make_queue(tmp_path)
    env = SyncEnvelope(payload_type="lap")
    q.enqueue(env)
    q.ack(env.envelope_id)
    assert q.is_empty


def test_nack_increments_attempt(tmp_path: Path):
    q = _make_queue(tmp_path)
    env = SyncEnvelope(payload_type="lap")
    q.enqueue(env)
    q.nack(env.envelope_id)
    peeked = q.peek()
    assert peeked is not None
    assert peeked.attempt_count == 1


def test_nack_drops_after_max_retries(tmp_path: Path):
    q = _make_queue(tmp_path)
    env = SyncEnvelope(payload_type="lap")
    q.enqueue(env)
    for _ in range(MAX_RETRIES):
        q.nack(env.envelope_id)
    assert q.is_empty


def test_duplicate_envelope_rejected(tmp_path: Path):
    q = _make_queue(tmp_path)
    env = SyncEnvelope(payload_type="session")
    assert q.enqueue(env) is True
    assert q.enqueue(env) is False
    assert q.depth == 1


def test_persist_and_reload(tmp_path: Path):
    q1 = _make_queue(tmp_path)
    env = SyncEnvelope(payload_type="event", payload={"k": "v"})
    q1.enqueue(env)

    q2 = SyncQueue(tmp_path)
    peeked = q2.peek()
    assert peeked is not None
    assert peeked.envelope_id == env.envelope_id
    assert peeked.payload == {"k": "v"}


def test_clear_empties_queue(tmp_path: Path):
    q = _make_queue(tmp_path)
    q.enqueue(SyncEnvelope(payload_type="a"))
    q.enqueue(SyncEnvelope(payload_type="b"))
    q.clear()
    assert q.is_empty
    assert q.depth == 0


def test_depth_property(tmp_path: Path):
    q = _make_queue(tmp_path)
    assert q.depth == 0
    q.enqueue(SyncEnvelope(payload_type="x"))
    q.enqueue(SyncEnvelope(payload_type="y"))
    assert q.depth == 2


def test_thread_safety(tmp_path: Path):
    q = _make_queue(tmp_path)
    errors: list[str] = []

    def worker(n: int) -> None:
        try:
            for i in range(20):
                env = SyncEnvelope(payload_type=f"t{n}-{i}")
                q.enqueue(env)
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert q.depth == 100  # 5 threads x 20 envelopes


# -- Tests for the legacy SyncQueueManager subsystem (from origin PR #1) -----

class TestSyncQueueManager:

    def test_ensure_sync_metadata_persists_required_fields(self, tmp_path: Path) -> None:
        bundle = _finalize_bundle(tmp_path)
        queue = SyncQueueManager(output_root=tmp_path, sync_enabled=False)

        manifest = queue.ensure_sync_metadata(bundle)

        assert manifest["sync_status"] in {"not_queued", "sync_ready", "sync_blocked"}
        assert manifest["sync_attempt_count"] == 0
        assert manifest["last_sync_attempt_at"] is None
        assert manifest["last_sync_error"] is None
        assert manifest["remote_id"] is None
        assert isinstance(manifest["bundle_hash"], str)
        assert len(manifest["bundle_hash"]) == 64

    def test_queue_session_is_deduplicated_by_session_and_bundle_hash(self, tmp_path: Path) -> None:
        bundle = _finalize_bundle(tmp_path)
        queue = SyncQueueManager(output_root=tmp_path, sync_enabled=False)

        ok1, msg1 = queue.queue_session(bundle)
        ok2, msg2 = queue.queue_session(bundle)

        assert ok1 is True
        assert msg1 in {"Queued", "Session already queued"}
        assert ok2 is True
        assert msg2 == "Session already queued"
        assert queue.queue_depth() == 1

        manifest = json.loads((bundle / "session.json").read_text(encoding="utf-8"))
        assert manifest["sync_status"] == "queued"

    def test_process_queue_skips_when_sync_feature_disabled(self, tmp_path: Path) -> None:
        bundle = _finalize_bundle(tmp_path)
        queue = SyncQueueManager(output_root=tmp_path, sync_enabled=False)
        queue.queue_session(bundle)

        results = queue.process_queue(max_items=3)

        assert results == []
        assert queue.queue_depth() == 1

    def test_process_queue_drops_entry_after_max_retry_attempts(self, tmp_path: Path) -> None:
        """Entries should be removed from the queue after MAX_SYNC_ATTEMPTS failures."""
        bundle = _finalize_bundle(tmp_path)

        class _FailingSync:
            enabled = True

            def upload_bundle(self, **kw: object) -> SyncAttemptResult:
                return SyncAttemptResult(success=False, error="server error", retryable=True)

        queue = SyncQueueManager(
            output_root=tmp_path, sync_enabled=True, sync_service=_FailingSync(),
        )
        queue.queue_session(bundle)
        assert queue.queue_depth() == 1

        for _ in range(MAX_SYNC_ATTEMPTS):
            results = queue.process_queue(max_items=5)
            assert len(results) == 1
            assert results[0]["status"] == "failed"

        # After MAX_SYNC_ATTEMPTS the entry should be permanently dropped
        assert queue.queue_depth() == 0
