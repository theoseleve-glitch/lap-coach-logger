"""Sync status model and helpers for offline-first session synchronization."""

from __future__ import annotations

SYNC_STATUS_NOT_QUEUED = "not_queued"
SYNC_STATUS_QUEUED = "queued"
SYNC_STATUS_BLOCKED = "sync_blocked"
SYNC_STATUS_READY = "sync_ready"
SYNC_STATUS_SYNCED = "synced"
SYNC_STATUS_FAILED = "sync_failed"

ALL_SYNC_STATUSES = {
    SYNC_STATUS_NOT_QUEUED,
    SYNC_STATUS_QUEUED,
    SYNC_STATUS_BLOCKED,
    SYNC_STATUS_READY,
    SYNC_STATUS_SYNCED,
    SYNC_STATUS_FAILED,
}


def normalize_sync_status(value: str | None) -> str:
    if value in ALL_SYNC_STATUSES:
        return str(value)
    return SYNC_STATUS_NOT_QUEUED


def is_sync_ready(*, review_status: str | None, quality_classification: str | None) -> bool:
    if review_status == "ignored":
        return False
    quality = str(quality_classification or "").strip().lower()
    return quality in {"accepted", "accepted_with_warnings", "needs_review"}


def derive_sync_status(
    *,
    current_status: str | None,
    review_status: str | None,
    quality_classification: str | None,
    remote_id: str | None,
) -> str:
    status = normalize_sync_status(current_status)

    if remote_id:
        return SYNC_STATUS_SYNCED

    if not is_sync_ready(review_status=review_status, quality_classification=quality_classification):
        return SYNC_STATUS_BLOCKED

    if status in {SYNC_STATUS_QUEUED, SYNC_STATUS_FAILED, SYNC_STATUS_SYNCED}:
        return status

    return SYNC_STATUS_READY
