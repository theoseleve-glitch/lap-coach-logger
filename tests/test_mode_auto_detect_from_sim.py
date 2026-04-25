"""T118: Auto-detect a starting mode from the sim's session hint.

When the desktop boots into a sim session, the active sim
exposes a session_type field — iRacing's "Race" / "Practice" /
"Qualifying" / "Time Trial", ACC's "Race"/"Practice", etc.
Per T118 the desktop should *suggest* a sensible starting mode
from that hint so the user doesn't have to flip the dropdown
every time they join a race.

The deliverable is **optional** (per the sprint doc): the user's
manual choice (T116) and the persisted last-mode (T117) take
priority. This function only fires on a true cold start with
no persisted mode AND a sim that's announced its session type.

Rules (per spec — "iRacing Race session → SprintMode default"):
- ``Race`` (any sim) → ``"sprint"``
- ``Race`` + ``race_duration_s > 2700`` (>45 min) → ``"endurance"``
- ``Race`` + ``is_timed=True``                → ``"endurance"``
- ``Practice``/``Qualifying``/``Time Trial``/etc. → ``"practice"``
- Unknown / empty hints                     → ``None``

The 2700s threshold matches the legacy ``mode_detector``'s
``_ENDURANCE_THRESHOLD_S`` so the new mode-engine path doesn't
disagree with the legacy ``ModeViewModel`` path on the same
input — until the legacy system gets retired (post-T120 E2E).

Returns are mode IDs from the ``ModeEngine`` registry
(``"practice" / "sprint" / "endurance" / "review"``); ``review``
isn't auto-detected because it's a UI-only post-session state,
never an in-sim signal.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Race session → sprint by default
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sim",
    ["iRacing", "ACC", "Le Mans Ultimate", "Assetto Corsa"],
)
def test_race_session_defaults_to_sprint(sim: str) -> None:
    """The headline T118 contract: iRacing Race → Sprint mode.
    Sweep across all four supported sims so a per-sim quirk
    doesn't slip in — the spec calls iRacing out by name but
    the rule is sim-agnostic for known session types."""
    from lap_coach_logger.core.modes.auto_detect import (
        suggest_mode_from_sim_hint,
    )

    assert suggest_mode_from_sim_hint(sim, "Race") == "sprint"


# ---------------------------------------------------------------------------
# Race + duration / timed → endurance
# ---------------------------------------------------------------------------


def test_race_with_long_duration_picks_endurance() -> None:
    """A 60-min race shouldn't drop you into Sprint mode — the
    fuel/strategy assumptions are different. Threshold matches
    the legacy mode_detector (2700s = 45 min) so behaviour stays
    consistent across the two parallel mode systems."""
    from lap_coach_logger.core.modes.auto_detect import (
        suggest_mode_from_sim_hint,
    )

    assert suggest_mode_from_sim_hint(
        "iRacing", "Race", race_duration_s=3600.0
    ) == "endurance"


def test_race_at_threshold_stays_sprint() -> None:
    """At exactly 2700s (45 min), still sprint — strict greater-
    than for the endurance bump matches the legacy detector."""
    from lap_coach_logger.core.modes.auto_detect import (
        suggest_mode_from_sim_hint,
    )

    assert suggest_mode_from_sim_hint(
        "iRacing", "Race", race_duration_s=2700.0
    ) == "sprint"


def test_timed_race_picks_endurance_regardless_of_duration() -> None:
    """Timed races (e.g. 'Race in 60:00 + 1 lap') signal
    endurance even when the announced duration is short — the
    timer means the race ends *at* a wall-clock target, which
    is the endurance assumption (Code-60s, slow out-laps, etc.).
    """
    from lap_coach_logger.core.modes.auto_detect import (
        suggest_mode_from_sim_hint,
    )

    assert suggest_mode_from_sim_hint(
        "iRacing", "Race", is_timed=True
    ) == "endurance"


# ---------------------------------------------------------------------------
# Non-race sessions → practice
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "session_type",
    ["Practice", "Qualifying", "Lone Qualify", "Open Qualify", "Time Trial"],
)
def test_non_race_sim_sessions_pick_practice(session_type: str) -> None:
    """All the iRacing non-race types funnel into Practice mode —
    that's the verbose-coaching, no-strategy-pressure mode for
    learning a track or working a setup. Catches both case-
    insensitivity AND the multi-token forms (Lone Qualify /
    Open Qualify) that iRacing actually emits."""
    from lap_coach_logger.core.modes.auto_detect import (
        suggest_mode_from_sim_hint,
    )

    assert suggest_mode_from_sim_hint("iRacing", session_type) == "practice"


# ---------------------------------------------------------------------------
# Unknown / empty hints → None (caller falls back to default)
# ---------------------------------------------------------------------------


def test_unknown_session_type_returns_none() -> None:
    """Unknown session types — return None so the caller falls
    back to either the persisted mode (T117) or the hardcoded
    default. Don't guess; a wrong guess is worse than no guess."""
    from lap_coach_logger.core.modes.auto_detect import (
        suggest_mode_from_sim_hint,
    )

    assert suggest_mode_from_sim_hint("iRacing", "Endurance Race Special") is None


def test_empty_session_type_returns_none() -> None:
    """Empty hint = sim hasn't reported a session yet. Definitely
    no auto-detect — return None."""
    from lap_coach_logger.core.modes.auto_detect import (
        suggest_mode_from_sim_hint,
    )

    assert suggest_mode_from_sim_hint("iRacing", "") is None


# ---------------------------------------------------------------------------
# Case-insensitivity (defensive — sim adapters vary)
# ---------------------------------------------------------------------------


def test_session_type_match_is_case_insensitive() -> None:
    """Different sim adapters report 'Race' / 'race' / 'RACE'.
    Don't let a casing drift break mode detection."""
    from lap_coach_logger.core.modes.auto_detect import (
        suggest_mode_from_sim_hint,
    )

    assert suggest_mode_from_sim_hint("iRacing", "race") == "sprint"
    assert suggest_mode_from_sim_hint("iRacing", "RACE") == "sprint"
    assert suggest_mode_from_sim_hint("iRacing", "  Race  ") == "sprint"


# ---------------------------------------------------------------------------
# Returns must always be valid ModeEngine ids (or None)
# ---------------------------------------------------------------------------


def test_every_returned_id_is_a_real_mode_in_the_engine() -> None:
    """Cross-check: whatever this function returns must be
    accept-able by ``ModeEngine.set_mode`` — otherwise the
    auto-detect can suggest a dead string and the engine
    raises UnknownModeError on apply."""
    from lap_coach_logger.core.modes.auto_detect import (
        suggest_mode_from_sim_hint,
    )
    from lap_coach_logger.core.modes.engine import ModeEngine

    engine = ModeEngine()
    candidates = [
        suggest_mode_from_sim_hint("iRacing", "Race"),
        suggest_mode_from_sim_hint("iRacing", "Race", race_duration_s=4000.0),
        suggest_mode_from_sim_hint("iRacing", "Practice"),
    ]

    for mode_id in candidates:
        assert mode_id is not None
        engine.set_mode(mode_id)  # raises if id isn't registered
