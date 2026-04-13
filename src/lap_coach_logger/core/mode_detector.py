"""Session type -> mode detection."""
from __future__ import annotations

MODES = ("sprint", "endurance", "coaching", "data")

_COACHING_SESSIONS = frozenset({
    "practice", "qualifying", "lone qualify", "open qualify", "time trial",
})

_ENDURANCE_THRESHOLD_S = 2700  # 45 minutes


def suggest_mode(
    session_type: str,
    race_duration_s: float | None = None,
    is_timed: bool = False,
) -> str:
    normalized = session_type.strip().lower()
    if normalized in _COACHING_SESSIONS:
        return "coaching"
    if normalized == "race":
        if is_timed:
            return "endurance"
        if race_duration_s is not None and race_duration_s > _ENDURANCE_THRESHOLD_S:
            return "endurance"
        return "sprint"
    return "data"
