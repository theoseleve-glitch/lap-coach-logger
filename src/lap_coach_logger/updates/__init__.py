"""Auto-update infrastructure (T185-T188).

T185: best-effort version check on app start (this module).
T186: UI notification when a newer version is available.
T187: download + signature verification.
T188: rollback on crash.
"""
from lap_coach_logger.updates.checker import (
    DEFAULT_MANIFEST_URL,
    UpdateCheckResult,
    check_for_updates,
)
from lap_coach_logger.updates.downloader import (
    PendingUpdate,
    clear_pending_update,
    download_update,
    mark_update_pending,
    read_pending_update,
    verify_signature,
)
from lap_coach_logger.updates.rollback import (
    ProbationStatus,
    confirm_version_stable,
    increment_probation_attempt,
    mark_version_on_probation,
    read_probation_status,
    should_rollback,
)
from lap_coach_logger.updates.runner import start_update_check_thread

__all__ = [
    "DEFAULT_MANIFEST_URL",
    "PendingUpdate",
    "ProbationStatus",
    "UpdateCheckResult",
    "check_for_updates",
    "clear_pending_update",
    "confirm_version_stable",
    "download_update",
    "increment_probation_attempt",
    "mark_update_pending",
    "mark_version_on_probation",
    "read_pending_update",
    "read_probation_status",
    "should_rollback",
    "start_update_check_thread",
    "verify_signature",
]
