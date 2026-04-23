"""Pit-call state machine — stable progression through the pit sequence.

Takes the noisy raw signals (``laps_to_pit``, ``pit_now``, ``is_in_pits``,
``was_in_pits``) and produces a stable, monotonic state label the
overlay can render without flicker.

States (progression is one-way until the stop completes):

    on_plan           — no pit coming up
    pit_in_5 / 4 / 3  — distant advisory window
    pit_in_2          — close advisory
    pit_in_1          — "PIT NEXT LAP"
    box_this_lap      — "BOX BOX BOX"
    in_pit_sequence   — car is on pit road
    stop_completed    — just exited the pits

Guarantees:
- Never bounces backward within a stint (e.g. pit_in_2 → pit_in_3).
- Transitions to ``box_this_lap`` only after ``pit_in_1`` was seen at
  least once (unless ``laps_to_pit == 0`` on first observation).
- Latches ``stop_completed`` briefly after pit exit, then falls back
  to ``on_plan`` on the next tick.

Pure function — the state is a small frozen dataclass caller keeps.
"""

from __future__ import annotations

from dataclasses import dataclass


STATE_ON_PLAN = "on_plan"
STATE_PIT_IN_5 = "pit_in_5"
STATE_PIT_IN_4 = "pit_in_4"
STATE_PIT_IN_3 = "pit_in_3"
STATE_PIT_IN_2 = "pit_in_2"
STATE_PIT_IN_1 = "pit_in_1"
STATE_BOX_THIS_LAP = "box_this_lap"
STATE_IN_PIT_SEQUENCE = "in_pit_sequence"
STATE_STOP_COMPLETED = "stop_completed"


# Rank used to prevent backwards transitions within a stint. Higher =
# closer to pit. Anchor stop_completed ABOVE the pit states so once the
# driver has stopped we don't fall back to a "pit_in_N" label.
_STATE_RANK = {
    STATE_ON_PLAN: 0,
    STATE_PIT_IN_5: 5,
    STATE_PIT_IN_4: 6,
    STATE_PIT_IN_3: 7,
    STATE_PIT_IN_2: 8,
    STATE_PIT_IN_1: 9,
    STATE_BOX_THIS_LAP: 10,
    STATE_IN_PIT_SEQUENCE: 11,
    STATE_STOP_COMPLETED: 12,
}


_LAPS_TO_STATE = {
    5: STATE_PIT_IN_5,
    4: STATE_PIT_IN_4,
    3: STATE_PIT_IN_3,
    2: STATE_PIT_IN_2,
    1: STATE_PIT_IN_1,
    0: STATE_BOX_THIS_LAP,
}


@dataclass(frozen=True)
class PitCallState:
    """Current pit-call state + the carryover bookkeeping."""
    state: str = STATE_ON_PLAN
    # Highest rank reached during the current stint — prevents bouncing
    # backward.
    stint_high_water: int = 0
    # Stable flag set once we've seen pit_in_1 so box_this_lap isn't
    # triggered from nowhere.
    saw_pit_in_1: bool = False


def _in_window(laps_to_pit: int | None) -> bool:
    """True when laps_to_pit is within the 0..5 advisory window."""
    return laps_to_pit is not None and 0 <= laps_to_pit <= 5


def advance_pit_call_state(
    previous: PitCallState,
    *,
    laps_to_pit: int,
    is_in_pits: bool,
    was_in_pits: bool,
) -> PitCallState:
    """Deterministic transition — returns the next ``PitCallState``.

    Priority ladder (first match wins):
    1. Pit exit → stop_completed (latches one tick).
    2. In pits  → in_pit_sequence.
    3. laps_to_pit maps to a pit_in_N state (with backward-motion guard).
    4. Otherwise → on_plan (resets the stint high-water mark).
    """
    # Pit-exit latch — one tick of stop_completed so the UI can celebrate.
    if was_in_pits and not is_in_pits:
        return PitCallState(
            state=STATE_STOP_COMPLETED,
            stint_high_water=_STATE_RANK[STATE_STOP_COMPLETED],
            saw_pit_in_1=previous.saw_pit_in_1,
        )

    if is_in_pits:
        return PitCallState(
            state=STATE_IN_PIT_SEQUENCE,
            stint_high_water=max(previous.stint_high_water, _STATE_RANK[STATE_IN_PIT_SEQUENCE]),
            saw_pit_in_1=previous.saw_pit_in_1,
        )

    # Fresh stint after a stop — reinitialise from scratch.
    if previous.state == STATE_STOP_COMPLETED:
        if not _in_window(laps_to_pit):
            return PitCallState()
        target = _LAPS_TO_STATE[laps_to_pit]
        return PitCallState(
            state=target,
            stint_high_water=_STATE_RANK[target],
            saw_pit_in_1=target == STATE_PIT_IN_1,
        )

    if not _in_window(laps_to_pit):
        # Far from pit — on_plan, reset high-water mark.
        return PitCallState(state=STATE_ON_PLAN, stint_high_water=0, saw_pit_in_1=False)

    target_state = _LAPS_TO_STATE[laps_to_pit]
    target_rank = _STATE_RANK[target_state]

    # Backward-motion guard: never drop to a lower-ranked pit state within
    # the same stint (e.g. pit_in_2 → pit_in_3 from a burn-rate wobble).
    if target_rank < previous.stint_high_water:
        return previous

    saw_pit_in_1 = previous.saw_pit_in_1 or target_state == STATE_PIT_IN_1

    # Gate box_this_lap: must have seen pit_in_1 first, unless this is
    # the very first tick of the stint (cold start allows a direct jump).
    if target_state == STATE_BOX_THIS_LAP and not saw_pit_in_1 and previous.state != STATE_ON_PLAN:
        return previous

    return PitCallState(
        state=target_state,
        stint_high_water=max(previous.stint_high_water, target_rank),
        saw_pit_in_1=saw_pit_in_1,
    )
