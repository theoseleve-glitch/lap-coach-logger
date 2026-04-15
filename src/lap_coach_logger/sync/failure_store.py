"""Persistent failure store for sync envelopes.

Envelopes that hit permanent failures (4xx) or exhaust retries
are recorded here with their failure reason. The user can retry
them manually or discard them. Never silently drop data.
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_FAILURE_FILENAME = "sync_failures.json"


@dataclass
class FailureRecord:
    """A sync envelope that couldn't be delivered."""
    envelope_id: str
    envelope: dict[str, Any]       # the original SyncEnvelope dict
    failure_reason: str            # human-readable error message
    failure_category: str          # "permanent" | "exhausted_retries" | "auth" | "corrupted"
    http_status: int | None
    first_attempt_at: str
    last_attempt_at: str
    attempt_count: int
    manually_retried_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "envelope": self.envelope,
            "failure_reason": self.failure_reason,
            "failure_category": self.failure_category,
            "http_status": self.http_status,
            "first_attempt_at": self.first_attempt_at,
            "last_attempt_at": self.last_attempt_at,
            "attempt_count": self.attempt_count,
            "manually_retried_count": self.manually_retried_count,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FailureRecord:
        return cls(
            envelope_id=d["envelope_id"],
            envelope=d.get("envelope", {}),
            failure_reason=d.get("failure_reason", ""),
            failure_category=d.get("failure_category", "exhausted_retries"),
            http_status=d.get("http_status"),
            first_attempt_at=d.get("first_attempt_at", ""),
            last_attempt_at=d.get("last_attempt_at", ""),
            attempt_count=d.get("attempt_count", 0),
            manually_retried_count=d.get("manually_retried_count", 0),
        )


class SyncFailureStore:
    """Thread-safe persistent store of failed sync envelopes."""

    def __init__(self, storage_dir: Path) -> None:
        self._storage_dir = storage_dir
        self._path = storage_dir / _FAILURE_FILENAME
        self._lock = threading.Lock()
        self._records: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._records = data if isinstance(data, list) else []
            except Exception:
                log.warning("Failed to load sync failure store", exc_info=True)
                self._records = []

    def _save(self) -> None:
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._records, indent=2), encoding="utf-8"
        )

    def record(
        self,
        envelope: dict[str, Any],
        reason: str,
        category: str,
        http_status: int | None = None,
        attempt_count: int = 1,
    ) -> None:
        """Record a failed envelope. Idempotent per envelope_id."""
        envelope_id = envelope.get("envelope_id", "")
        if not envelope_id:
            log.warning("Failure has no envelope_id, skipping")
            return
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            # Update existing record if already tracked
            for rec in self._records:
                if rec.get("envelope_id") == envelope_id:
                    rec["last_attempt_at"] = now
                    rec["attempt_count"] = attempt_count
                    rec["failure_reason"] = reason
                    rec["failure_category"] = category
                    rec["http_status"] = http_status
                    self._save()
                    return
            # New record
            record = FailureRecord(
                envelope_id=envelope_id,
                envelope=envelope,
                failure_reason=reason,
                failure_category=category,
                http_status=http_status,
                first_attempt_at=now,
                last_attempt_at=now,
                attempt_count=attempt_count,
            )
            self._records.append(record.to_dict())
            self._save()

    def list_failures(self) -> list[FailureRecord]:
        """Return all recorded failures, newest first."""
        with self._lock:
            return [FailureRecord.from_dict(r) for r in reversed(self._records)]

    def count(self) -> int:
        with self._lock:
            return len(self._records)

    def get(self, envelope_id: str) -> FailureRecord | None:
        with self._lock:
            for r in self._records:
                if r.get("envelope_id") == envelope_id:
                    return FailureRecord.from_dict(r)
        return None

    def discard(self, envelope_id: str) -> bool:
        """Remove a failure permanently. Returns True if removed."""
        with self._lock:
            before = len(self._records)
            self._records = [r for r in self._records if r.get("envelope_id") != envelope_id]
            if len(self._records) < before:
                self._save()
                return True
        return False

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self._save()

    def mark_retried(self, envelope_id: str) -> None:
        """Increment manually_retried_count and bump last_attempt_at."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            for rec in self._records:
                if rec.get("envelope_id") == envelope_id:
                    rec["manually_retried_count"] = rec.get("manually_retried_count", 0) + 1
                    rec["last_attempt_at"] = now
                    self._save()
                    return

    def categorize_counts(self) -> dict[str, int]:
        """Return count by failure_category for UI display."""
        with self._lock:
            counts: dict[str, int] = {}
            for r in self._records:
                cat = r.get("failure_category", "unknown")
                counts[cat] = counts.get(cat, 0) + 1
            return counts
