"""T092: Insight cooldown filter — same rule firing repeatedly is
suppressed for a configurable cooldown window.

T088's CorroborationGate suppresses *first-fire spam*: a rule
must fire on N consecutive laps before its first emission.
T092's CooldownFilter suppresses *steady-state spam*: once a
rule has been shown to the user, subsequent firings for the
same rule are dropped until the cooldown window expires.

Two reasons to layer these as separate filters:

- They have different semantics. CorroborationGate resets on
  a clean lap; CooldownFilter resets on a clock tick.
- They live at different layers. CorroborationGate is per-engine
  (multiple VMs share); CooldownFilter is per-VM (so the overlay
  card and a future audio cue can have independent cooldowns).

Default cooldown is 30 seconds — long enough that the same
coaching tip stops being useful (the driver heard it, they're
either fixing it or actively ignoring it for now), short enough
that a lap that fires the rule 30+ seconds later still surfaces.
"""
from __future__ import annotations

import pytest

from lap_coach_logger.coaching.rules_engine import (
    CoachingInsight,
    InsightCooldownFilter,
)


def _insight(rule_id: str) -> CoachingInsight:
    return CoachingInsight(rule_id=rule_id, payload={"title": rule_id})


# ---------------------------------------------------------------------------
# First fire always passes (cooldown is empty)
# ---------------------------------------------------------------------------


def test_first_insight_for_a_rule_always_passes() -> None:
    """No prior shown-at timestamp → no cooldown applies."""
    clock = [1000.0]
    filt = InsightCooldownFilter(cooldown_seconds=30.0, now=lambda: clock[0])

    out = filt.filter([_insight("br.late")])

    assert [i.rule_id for i in out] == ["br.late"]


def test_distinct_rules_each_pass_independently() -> None:
    """Cooldown is per-rule, not global. Two different rules
    firing in the same window both surface to the user."""
    clock = [1000.0]
    filt = InsightCooldownFilter(cooldown_seconds=30.0, now=lambda: clock[0])

    out = filt.filter([_insight("a"), _insight("b"), _insight("c")])

    assert sorted(i.rule_id for i in out) == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# Same rule within window: dropped
# ---------------------------------------------------------------------------


def test_same_rule_within_cooldown_is_dropped() -> None:
    """User just saw the "brake later" card 5 seconds ago — don't
    interrupt them with the same card again, they got it."""
    clock = [1000.0]
    filt = InsightCooldownFilter(cooldown_seconds=30.0, now=lambda: clock[0])

    filt.filter([_insight("br.late")])  # first fire
    clock[0] = 1005.0  # 5 seconds later
    out = filt.filter([_insight("br.late")])

    assert out == []


def test_same_rule_at_boundary_is_dropped_strict() -> None:
    """``cooldown_seconds=30`` means "at-or-after 30s elapsed".
    Pinning the boundary catches off-by-epsilon refactors."""
    clock = [1000.0]
    filt = InsightCooldownFilter(cooldown_seconds=30.0, now=lambda: clock[0])

    filt.filter([_insight("br.late")])
    clock[0] = 1029.999  # just before 30s

    out = filt.filter([_insight("br.late")])
    assert out == []


def test_same_rule_after_cooldown_passes_again() -> None:
    """After 30 seconds the cooldown expires — same rule firing
    again gets through."""
    clock = [1000.0]
    filt = InsightCooldownFilter(cooldown_seconds=30.0, now=lambda: clock[0])

    filt.filter([_insight("br.late")])
    clock[0] = 1030.5

    out = filt.filter([_insight("br.late")])
    assert [i.rule_id for i in out] == ["br.late"]


def test_repeated_passes_each_extend_the_cooldown() -> None:
    """Each emission resets the cooldown clock for that rule.
    Otherwise a rule firing every 31 seconds would surface
    constantly (each fire just inside the previous fire's
    expiry window)."""
    clock = [1000.0]
    filt = InsightCooldownFilter(cooldown_seconds=30.0, now=lambda: clock[0])

    filt.filter([_insight("br.late")])  # at 1000
    clock[0] = 1035.0
    filt.filter([_insight("br.late")])  # at 1035 — passes; cooldown reset

    clock[0] = 1050.0  # 15s after the second fire — still in cooldown
    out = filt.filter([_insight("br.late")])

    assert out == []  # second fire's cooldown still active


# ---------------------------------------------------------------------------
# Mixed rules: per-rule cooldown
# ---------------------------------------------------------------------------


def test_one_rule_in_cooldown_does_not_block_another() -> None:
    """Cooldown is keyed on rule_id. ``br.late`` cooldown doesn't
    suppress ``ac.apex_loss`` — they're distinct coaching points."""
    clock = [1000.0]
    filt = InsightCooldownFilter(cooldown_seconds=30.0, now=lambda: clock[0])

    filt.filter([_insight("br.late")])
    clock[0] = 1005.0

    out = filt.filter([_insight("br.late"), _insight("ac.apex_loss")])
    assert [i.rule_id for i in out] == ["ac.apex_loss"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_zero_cooldown_disables_filter() -> None:
    """``cooldown_seconds=0`` is the way to opt out — useful for
    test setups where the VM should pass everything through.
    Default value (30s) is the production setting."""
    clock = [1000.0]
    filt = InsightCooldownFilter(cooldown_seconds=0.0, now=lambda: clock[0])

    out_1 = filt.filter([_insight("br.late")])
    out_2 = filt.filter([_insight("br.late")])  # same instant

    assert out_1 == out_2  # both pass — no cooldown


def test_filter_preserves_insight_order_among_passing_ones() -> None:
    """T091's pending queue assumes order from drain(). Filter
    must preserve that order so the next-card flow is deterministic."""
    clock = [1000.0]
    filt = InsightCooldownFilter(cooldown_seconds=30.0, now=lambda: clock[0])

    out = filt.filter(
        [_insight("a"), _insight("b"), _insight("c"), _insight("d")]
    )

    assert [i.rule_id for i in out] == ["a", "b", "c", "d"]


def test_negative_cooldown_seconds_raises() -> None:
    """A negative cooldown is meaningless — fail loudly during
    construction rather than silently behave like zero."""
    with pytest.raises(ValueError):
        InsightCooldownFilter(cooldown_seconds=-1.0)
