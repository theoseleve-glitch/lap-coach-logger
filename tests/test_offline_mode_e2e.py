"""T208: Integration test — offline mode (no network) captures
+ queues upload.

Pins the offline-first contract: even with no network reachable,
the app must:
  - finalize bundles to disk (already covered by T201-T203 e2e tests)
  - persist queue state to ``.sync_queue.json`` so entries survive
    restart
  - mark failed-upload entries as retryable when sync_service
    reports ``retryable=True``
  - keep retryable entries in the queue across multiple
    ``process_queue`` calls (until network returns or
    ``MAX_SYNC_ATTEMPTS`` is reached)
  - process queued entries when network returns

Tests bypass the v1 finalizer (which has known quality-gate
failures unrelated to offline mode — see baseline failures in
test_sync_queue.py) and construct minimal valid bundle dirs
directly. The behavior under test is the queue persistence +
retry logic, not finalize itself.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from lap_coach_logger.core.sync_queue import (
    MAX_SYNC_ATTEMPTS,
    SyncQueueManager,
)
from lap_coach_logger.core.sync_service import SyncAttemptResult


# -- helpers --------------------------------------------------------


def _make_offline_bundle(
    output_root: Path,
    *,
    session_id: str = "session-offline-001",
    telemetry_data: bytes = b"telemetry-fake-bytes",
) -> Path:
    """Build a minimal-yet-valid bundle directory.

    Includes ``session.json`` with ``quality_classification=accepted``
    so ``derive_sync_status`` resolves to ``sync_ready`` (not blocked).
    Without this the queue would refuse to enqueue. T208 tests the
    OFFLINE-MODE contract; the quality-gate path is unrelated and
    already covered elsewhere.
    """
    bundle_dir = output_root / f"bundle-{session_id}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    telemetry_path = bundle_dir / "telemetry.parquet"
    telemetry_path.write_bytes(telemetry_data)
    telemetry_sha256 = hashlib.sha256(telemetry_data).hexdigest()

    session_payload = {
        "session_id": session_id,
        "telemetry_sha256": telemetry_sha256,
        "review_status": "approved",
        "quality_classification": "accepted",
        "sync_status": "not_queued",
    }
    (bundle_dir / "session.json").write_text(
        json.dumps(session_payload), encoding="utf-8",
    )
    (bundle_dir / "metadata.json").write_text(
        json.dumps({
            "session_uid": session_id,
            "telemetry_sha256": telemetry_sha256,
            "review_status": "approved",
            "quality_classification": "accepted",
        }),
        encoding="utf-8",
    )
    return bundle_dir


class _OfflineSyncService:
    """Simulates network unreachable — every upload fails retryable."""

    def __init__(self) -> None:
        self.upload_count = 0

    @property
    def enabled(self) -> bool:
        return True

    def upload_bundle(
        self, *, bundle_dir: Path, session_id: str, bundle_hash: str,
    ) -> SyncAttemptResult:
        self.upload_count += 1
        return SyncAttemptResult(
            success=False,
            error="connection refused: backend unreachable",
            retryable=True,
        )


class _OnlineSyncService:
    """Network back up — every upload succeeds with a remote_id."""

    def __init__(self) -> None:
        self.upload_count = 0

    @property
    def enabled(self) -> bool:
        return True

    def upload_bundle(
        self, *, bundle_dir: Path, session_id: str, bundle_hash: str,
    ) -> SyncAttemptResult:
        self.upload_count += 1
        return SyncAttemptResult(
            success=True,
            remote_id=f"remote-{session_id}",
        )


# -- queue_session works regardless of network ---------------------


def test_queue_session_works_when_sync_disabled(tmp_path: Path) -> None:
    """sync_enabled=False is the canonical offline-mode default.
    Bundles must still be enqueueable for later upload."""
    bundle = _make_offline_bundle(tmp_path, session_id="off-1")
    queue = SyncQueueManager(output_root=tmp_path, sync_enabled=False)
    ok, msg = queue.queue_session(bundle)
    assert ok is True, f"queue must accept bundle when offline; got {msg!r}"
    assert queue.queue_depth() == 1


def test_queue_session_works_with_offline_service(tmp_path: Path) -> None:
    """sync_enabled=True with an unreachable backend → queue still
    accepts the bundle. Upload happens on subsequent process_queue,
    not on enqueue."""
    bundle = _make_offline_bundle(tmp_path, session_id="off-2")
    offline = _OfflineSyncService()
    queue = SyncQueueManager(
        output_root=tmp_path, sync_enabled=True, sync_service=offline,
    )
    ok, _ = queue.queue_session(bundle)
    assert ok is True
    assert queue.queue_depth() == 1
    # queue_session must NOT call upload_bundle — uploads are deferred.
    assert offline.upload_count == 0


def test_queue_persists_entry_to_disk(tmp_path: Path) -> None:
    """``.sync_queue.json`` must be written so entries survive restart."""
    bundle = _make_offline_bundle(tmp_path, session_id="off-disk")
    queue = SyncQueueManager(output_root=tmp_path, sync_enabled=False)
    queue.queue_session(bundle)

    queue_file = tmp_path / ".sync_queue.json"
    assert queue_file.is_file(), (
        ".sync_queue.json must be written so the queue survives restart"
    )
    payload = json.loads(queue_file.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert len(payload["entries"]) == 1
    entry = payload["entries"][0]
    assert entry["session_id"] == "off-disk"
    assert entry["bundle_hash"]


# -- queue survives a "restart" via fresh manager ------------------


def test_queue_loads_from_disk_after_restart(tmp_path: Path) -> None:
    """A fresh SyncQueueManager pointed at the same output_root must
    re-read .sync_queue.json — offline-mode bundles must NOT be lost
    when the user closes the app between sessions."""
    bundle = _make_offline_bundle(tmp_path, session_id="restart-1")
    queue1 = SyncQueueManager(output_root=tmp_path, sync_enabled=False)
    queue1.queue_session(bundle)
    assert queue1.queue_depth() == 1

    # Simulate restart: new SyncQueueManager instance, same root.
    queue2 = SyncQueueManager(output_root=tmp_path, sync_enabled=False)
    assert queue2.queue_depth() == 1, (
        "queue must reload entries from disk on restart"
    )


# -- multiple offline sessions accumulate --------------------------


def test_multiple_offline_sessions_accumulate(tmp_path: Path) -> None:
    """User does 3 offline sessions before reconnecting → all 3 must
    be queued. Caller's polling loop will drain them on next process."""
    bundles = [
        _make_offline_bundle(tmp_path, session_id=f"acc-{i}")
        for i in range(3)
    ]
    queue = SyncQueueManager(output_root=tmp_path, sync_enabled=False)
    for b in bundles:
        ok, _ = queue.queue_session(b)
        assert ok is True

    assert queue.queue_depth() == 3


# -- process_queue while offline retains entries -------------------


def test_process_queue_retains_entry_when_upload_retryable(
    tmp_path: Path,
) -> None:
    """Backend unreachable → upload returns retryable=True →
    entry STAYS in queue for the next attempt. Without this the
    user would lose data the moment they tried to sync offline."""
    bundle = _make_offline_bundle(tmp_path, session_id="retry-1")
    offline = _OfflineSyncService()
    queue = SyncQueueManager(
        output_root=tmp_path, sync_enabled=True, sync_service=offline,
    )
    queue.queue_session(bundle)
    assert queue.queue_depth() == 1

    results = queue.process_queue(max_items=5)
    assert len(results) == 1
    assert results[0]["status"] == "failed"
    # Entry still in queue (retryable) — caller can retry.
    assert queue.queue_depth() == 1
    assert offline.upload_count == 1


def test_process_queue_can_be_called_multiple_times_offline(
    tmp_path: Path,
) -> None:
    """Caller polls process_queue periodically. While offline, each
    call increments upload_count but the queue retains the entry
    until either success or MAX_SYNC_ATTEMPTS."""
    bundle = _make_offline_bundle(tmp_path, session_id="retry-2")
    offline = _OfflineSyncService()
    queue = SyncQueueManager(
        output_root=tmp_path, sync_enabled=True, sync_service=offline,
    )
    queue.queue_session(bundle)

    # Two attempts, both retryable failures (under MAX).
    queue.process_queue(max_items=5)
    queue.process_queue(max_items=5)
    assert offline.upload_count == 2
    assert queue.queue_depth() == 1


def test_process_queue_drops_entry_after_max_retry_attempts(
    tmp_path: Path,
) -> None:
    """After MAX_SYNC_ATTEMPTS retryable failures, the entry is
    permanently dropped — protects the queue from infinite growth
    for permanently-broken bundles. The entry's session.json keeps
    its sync_failed status so the user can re-queue manually."""
    bundle = _make_offline_bundle(tmp_path, session_id="dropped")
    offline = _OfflineSyncService()
    queue = SyncQueueManager(
        output_root=tmp_path, sync_enabled=True, sync_service=offline,
    )
    queue.queue_session(bundle)

    for _ in range(MAX_SYNC_ATTEMPTS):
        queue.process_queue(max_items=5)

    assert queue.queue_depth() == 0
    # Bundle's session.json still has sync_failed status (caller can
    # inspect to decide what to do).
    sj = json.loads((bundle / "session.json").read_text(encoding="utf-8"))
    assert sj["sync_status"] == "sync_failed"


# -- network recovery: offline → online drains queue ----------------


def test_queue_drains_when_network_returns(tmp_path: Path) -> None:
    """Queue accumulates while offline. When network returns, the
    same queue (swapped to online sync service) uploads everything."""
    # Build 2 offline sessions.
    bundle_a = _make_offline_bundle(tmp_path, session_id="recov-a")
    bundle_b = _make_offline_bundle(tmp_path, session_id="recov-b")

    offline = _OfflineSyncService()
    queue_offline = SyncQueueManager(
        output_root=tmp_path, sync_enabled=True, sync_service=offline,
    )
    queue_offline.queue_session(bundle_a)
    queue_offline.queue_session(bundle_b)
    queue_offline.process_queue(max_items=5)  # both fail retryable
    assert queue_offline.queue_depth() == 2  # both retained

    # Network returns — fresh queue manager pointed at same root, but
    # with an online sync service.
    online = _OnlineSyncService()
    queue_online = SyncQueueManager(
        output_root=tmp_path, sync_enabled=True, sync_service=online,
    )
    assert queue_online.queue_depth() == 2  # loaded from disk

    results = queue_online.process_queue(max_items=5)
    assert len(results) == 2
    assert all(r["status"] == "synced" for r in results)
    assert online.upload_count == 2
    # Both entries removed (success → not requeued).
    assert queue_online.queue_depth() == 0


# -- bundle session.json is updated to "queued" --------------------


def test_session_json_status_flips_to_queued(tmp_path: Path) -> None:
    """The queued bundle's session.json must reflect the new
    ``queued`` status — UI can show pending-upload chip from disk
    state alone, without consulting the queue manager."""
    bundle = _make_offline_bundle(tmp_path, session_id="queued-flag")
    queue = SyncQueueManager(output_root=tmp_path, sync_enabled=False)
    queue.queue_session(bundle)

    sj = json.loads((bundle / "session.json").read_text(encoding="utf-8"))
    assert sj["sync_status"] == "queued"


# -- dedup: same bundle queued twice → still 1 entry ---------------


def test_queue_dedupes_same_bundle(tmp_path: Path) -> None:
    """Re-queueing the same bundle (e.g., on UI refresh) must not
    create a duplicate entry — the queue is dedup'd on (session_id,
    bundle_hash)."""
    bundle = _make_offline_bundle(tmp_path, session_id="dedupe-1")
    queue = SyncQueueManager(output_root=tmp_path, sync_enabled=False)
    queue.queue_session(bundle)
    queue.queue_session(bundle)
    assert queue.queue_depth() == 1


# -- empty/missing queue file → fresh start -----------------------


def test_fresh_queue_has_empty_state(tmp_path: Path) -> None:
    """First-launch: no .sync_queue.json on disk → manager starts
    with depth 0, no errors."""
    queue = SyncQueueManager(output_root=tmp_path, sync_enabled=False)
    assert queue.queue_depth() == 0


def test_corrupted_queue_file_recovers_to_empty(tmp_path: Path) -> None:
    """If .sync_queue.json is corrupted (truncated, partial write
    after crash) the manager must recover gracefully — start empty
    rather than crash. Future fix may add a .corrupted backup."""
    (tmp_path / ".sync_queue.json").write_text(
        "{not valid json", encoding="utf-8",
    )
    queue = SyncQueueManager(output_root=tmp_path, sync_enabled=False)
    assert queue.queue_depth() == 0
