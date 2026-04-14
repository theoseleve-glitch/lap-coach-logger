"""Offline-first sync queue with retry logic.

Queue entries are SyncEnvelopes persisted to disk. Failed sends
are retried with exponential backoff. Duplicate envelope_ids are
rejected (idempotent).
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Callable

from lap_coach_logger.sync.schema import SyncEnvelope

log = logging.getLogger(__name__)

MAX_RETRIES = 5
QUEUE_FILENAME = "sync_queue.json"


class SyncQueue:
    """Thread-safe persistent sync queue."""

    def __init__(self, storage_dir: Path) -> None:
        self._storage_dir = storage_dir
        self._queue_path = storage_dir / QUEUE_FILENAME
        self._lock = threading.Lock()
        self._queue: list[dict[str, Any]] = []
        self._seen_ids: set[str] = set()
        self._load()

    def _load(self) -> None:
        if self._queue_path.exists():
            try:
                data = json.loads(self._queue_path.read_text(encoding="utf-8"))
                self._queue = data if isinstance(data, list) else []
                self._seen_ids = {e.get("envelope_id", "") for e in self._queue}
            except Exception:
                log.warning("Failed to load sync queue", exc_info=True)
                self._queue = []

    def _save(self) -> None:
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._queue_path.write_text(
            json.dumps(self._queue, indent=2), encoding="utf-8"
        )

    def enqueue(self, envelope: SyncEnvelope) -> bool:
        """Add an envelope to the queue. Returns False if duplicate."""
        with self._lock:
            if envelope.envelope_id in self._seen_ids:
                return False
            self._queue.append(envelope.to_dict())
            self._seen_ids.add(envelope.envelope_id)
            self._save()
            return True

    def peek(self) -> SyncEnvelope | None:
        """Return the next envelope without removing it."""
        with self._lock:
            if not self._queue:
                return None
            return SyncEnvelope.from_dict(self._queue[0])

    def ack(self, envelope_id: str) -> None:
        """Remove a successfully sent envelope."""
        with self._lock:
            self._queue = [e for e in self._queue if e.get("envelope_id") != envelope_id]
            self._save()

    def nack(self, envelope_id: str) -> None:
        """Mark a failed send — increment attempt_count."""
        with self._lock:
            for e in self._queue:
                if e.get("envelope_id") == envelope_id:
                    e["attempt_count"] = e.get("attempt_count", 0) + 1
                    if e["attempt_count"] >= MAX_RETRIES:
                        self._queue.remove(e)
                        log.warning("Dropping envelope %s after %d retries", envelope_id, MAX_RETRIES)
                    break
            self._save()

    @property
    def depth(self) -> int:
        with self._lock:
            return len(self._queue)

    @property
    def is_empty(self) -> bool:
        return self.depth == 0

    def clear(self) -> None:
        with self._lock:
            self._queue.clear()
            self._seen_ids.clear()
            self._save()
