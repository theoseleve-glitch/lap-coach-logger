"""Tests for sync failure store."""
from __future__ import annotations

from pathlib import Path

from lap_coach_logger.sync.failure_store import FailureRecord, SyncFailureStore


def _envelope(eid: str = "e1") -> dict:
    return {
        "envelope_id": eid,
        "payload_type": "lap",
        "payload": {"lap_number": 1},
        "created_at": "2026-04-15T12:00:00",
        "attempt_count": 3,
    }


class TestRecord:

    def test_record_single_failure(self, tmp_path: Path):
        store = SyncFailureStore(tmp_path)
        store.record(_envelope("e1"), "Bad payload", "permanent", http_status=400, attempt_count=1)
        assert store.count() == 1

    def test_record_persists_to_disk(self, tmp_path: Path):
        store = SyncFailureStore(tmp_path)
        store.record(_envelope("e1"), "Bad payload", "permanent", http_status=400)
        # Reload from same path
        store2 = SyncFailureStore(tmp_path)
        assert store2.count() == 1

    def test_record_without_envelope_id_is_skipped(self, tmp_path: Path):
        store = SyncFailureStore(tmp_path)
        env = {"envelope_id": "", "payload": {}}
        store.record(env, "x", "permanent")
        assert store.count() == 0

    def test_record_duplicate_id_updates_existing(self, tmp_path: Path):
        store = SyncFailureStore(tmp_path)
        store.record(_envelope("e1"), "First reason", "permanent", attempt_count=1)
        store.record(_envelope("e1"), "Second reason", "exhausted_retries", attempt_count=5)
        assert store.count() == 1
        rec = store.get("e1")
        assert rec.failure_reason == "Second reason"
        assert rec.attempt_count == 5


class TestList:

    def test_list_empty_store(self, tmp_path: Path):
        store = SyncFailureStore(tmp_path)
        assert store.list_failures() == []

    def test_list_returns_newest_first(self, tmp_path: Path):
        store = SyncFailureStore(tmp_path)
        store.record(_envelope("e1"), "r1", "permanent")
        store.record(_envelope("e2"), "r2", "permanent")
        failures = store.list_failures()
        assert len(failures) == 2
        assert failures[0].envelope_id == "e2"  # newest first
        assert failures[1].envelope_id == "e1"


class TestDiscard:

    def test_discard_existing(self, tmp_path: Path):
        store = SyncFailureStore(tmp_path)
        store.record(_envelope("e1"), "r", "permanent")
        assert store.discard("e1") is True
        assert store.count() == 0

    def test_discard_nonexistent(self, tmp_path: Path):
        store = SyncFailureStore(tmp_path)
        assert store.discard("nonexistent") is False

    def test_discard_persists(self, tmp_path: Path):
        store = SyncFailureStore(tmp_path)
        store.record(_envelope("e1"), "r", "permanent")
        store.record(_envelope("e2"), "r", "permanent")
        store.discard("e1")
        store2 = SyncFailureStore(tmp_path)
        assert store2.count() == 1


class TestMarkRetried:

    def test_increments_retry_count(self, tmp_path: Path):
        store = SyncFailureStore(tmp_path)
        store.record(_envelope("e1"), "r", "permanent")
        store.mark_retried("e1")
        rec = store.get("e1")
        assert rec.manually_retried_count == 1
        store.mark_retried("e1")
        rec = store.get("e1")
        assert rec.manually_retried_count == 2


class TestCategories:

    def test_counts_by_category(self, tmp_path: Path):
        store = SyncFailureStore(tmp_path)
        store.record(_envelope("e1"), "r", "permanent")
        store.record(_envelope("e2"), "r", "permanent")
        store.record(_envelope("e3"), "r", "auth")
        store.record(_envelope("e4"), "r", "exhausted_retries")
        counts = store.categorize_counts()
        assert counts["permanent"] == 2
        assert counts["auth"] == 1
        assert counts["exhausted_retries"] == 1


class TestThreadSafety:

    def test_concurrent_record(self, tmp_path: Path):
        import threading
        store = SyncFailureStore(tmp_path)
        errors = []

        def worker(start: int):
            try:
                for i in range(20):
                    store.record(_envelope(f"e{start + i}"), "r", "permanent")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i * 100,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)
        assert not errors
        assert store.count() == 80


class TestClear:

    def test_clear_empties_store(self, tmp_path: Path):
        store = SyncFailureStore(tmp_path)
        store.record(_envelope("e1"), "r", "permanent")
        store.record(_envelope("e2"), "r", "permanent")
        store.clear()
        assert store.count() == 0
