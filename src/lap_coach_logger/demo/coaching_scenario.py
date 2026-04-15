"""Pre-scripted coaching narrative for the demo.

Exposes a timeline of scripted moments a presenter can use to
explain the product. The demo runner fires these events at
specific points in the session.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScriptedMoment:
    """A narrative moment during the demo."""
    after_lap: int
    title: str
    description: str


COACHING_ARC: list[ScriptedMoment] = [
    ScriptedMoment(
        after_lap=3,
        title="Early inconsistency detected",
        description="Sector 2 std dev is +/-1.6s - wide braking variance in T5.",
    ),
    ScriptedMoment(
        after_lap=5,
        title="Coaching plan generated",
        description="Focus: stabilize T5 braking point. Target: S2 +/-0.5s in 5 laps.",
    ),
    ScriptedMoment(
        after_lap=7,
        title="Plan on track",
        description="S2 variance dropped 40%. Driver is executing the plan.",
    ),
    ScriptedMoment(
        after_lap=10,
        title="Race-ready",
        description="All consistency checks passed. Readiness: READY.",
    ),
]


def moment_for_lap(lap_number: int) -> ScriptedMoment | None:
    """Return the scripted moment that fires at the end of this lap, if any."""
    for m in COACHING_ARC:
        if m.after_lap == lap_number:
            return m
    return None
