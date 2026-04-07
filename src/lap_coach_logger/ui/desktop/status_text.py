"""Pure helpers for user-facing status copy (no Qt dependencies)."""

from __future__ import annotations


def build_status_detail(
    *,
    raw_state: str,
    sim: str | None,
    session_state: str,
    last_error: str | None,
    is_monitoring: bool,
    latest_session: dict[str, object],
) -> str:
    if last_error:
        return f"Last error: {last_error}"
    if not is_monitoring:
        return "Monitoring paused. Use Start Monitoring to resume."
    if sim:
        if raw_state == "arming":
            return f"Connected to {sim}  \u2022  Session detected, waiting for first telemetry sample"
        if raw_state == "ready_for_review":
            return f"Connected to {sim}  \u2022  Session finalized and ready for review"
        if raw_state == "failed":
            return f"Connected to {sim}  \u2022  Last session failed"
        return f"Connected to {sim}  \u2022  Session state: {session_state}"
    if raw_state == "idle" and latest_session:
        ended = latest_session.get("ended") or "last run"
        return f"Waiting for a simulator  \u2022  Last saved session: {ended}"
    return "Waiting for a supported simulator"
