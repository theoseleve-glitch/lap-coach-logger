"""Sync service abstraction for future remote upload integration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class SyncAttemptResult:
    success: bool
    remote_id: str | None = None
    error: str | None = None
    retryable: bool = False


class SyncService(Protocol):
    @property
    def enabled(self) -> bool:
        ...

    def upload_bundle(self, *, bundle_dir: Path, session_id: str, bundle_hash: str) -> SyncAttemptResult:
        ...


class DisabledSyncService:
    """Default sync service that keeps the app fully offline."""

    @property
    def enabled(self) -> bool:
        return False

    def upload_bundle(self, *, bundle_dir: Path, session_id: str, bundle_hash: str) -> SyncAttemptResult:
        return SyncAttemptResult(
            success=False,
            error="Remote sync is disabled by feature flag.",
            retryable=False,
        )
