"""T118: Suggest a starting mode from the sim's session hint.

Cold-start convenience: when the sim adapter reports its
session type, surface a sensible starting mode for the
:class:`~lap_coach_logger.core.modes.engine.ModeEngine` so the
user doesn't have to flip the toolbar dropdown every time
they join a race.

The function is a *hint provider* — caller decides whether
to honour the suggestion. Per T118 priority:

    user manual choice (T116) > persisted mode (T117) > sim hint (T118) > default

Mirrors the legacy ``mode_detector.suggest_mode``'s thresholds
(``> 2700s`` for endurance) so the new mode-engine path doesn't
disagree with the legacy ``ModeViewModel`` path on the same
input. Returns ``None`` for hints we can't classify with
confidence — a wrong guess is worse than no guess.
"""

from __future__ import annotations

# Match the legacy mode_detector threshold so the parallel
# systems agree on what "endurance" means until the legacy
# path is retired post-T120 E2E.
_ENDURANCE_THRESHOLD_S = 2700  # 45 minutes

_PRACTICE_SESSION_TYPES = frozenset(
    {
        "practice",
        "qualifying",
        "lone qualify",
        "open qualify",
        "time trial",
        "warmup",
        "test",
    }
)


def suggest_mode_from_sim_hint(
    sim: str,
    session_type: str,
    *,
    race_duration_s: float | None = None,
    is_timed: bool = False,
) -> str | None:
    """Return a ModeEngine mode id (``"practice" / "sprint" /
    "endurance"``) or ``None`` if the hint is unrecognised."""
    normalized = (session_type or "").strip().lower()
    if not normalized:
        return None
    if normalized == "race":
        if is_timed:
            return "endurance"
        if race_duration_s is not None and race_duration_s > _ENDURANCE_THRESHOLD_S:
            return "endurance"
        return "sprint"
    if normalized in _PRACTICE_SESSION_TYPES:
        return "practice"
    return None


__all__ = ["suggest_mode_from_sim_hint"]
