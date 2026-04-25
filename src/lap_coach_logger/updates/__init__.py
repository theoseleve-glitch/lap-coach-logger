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

__all__ = [
    "DEFAULT_MANIFEST_URL",
    "UpdateCheckResult",
    "check_for_updates",
]
