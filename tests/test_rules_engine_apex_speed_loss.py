"""T087: Apex-speed-loss detection — rule ``ac.apex_speed_loss``
fires when the driver carries less speed at apex than the
reference lap by ≥ 3 km/h.

Mechanically: ``apex_speed_kph_delta`` is the signed difference
between this lap's apex speed and the reference lap's apex speed.
Negative = slower (loss); positive = faster (gain). The rule
fires on losses ≤ -3.0 km/h — small enough to flag a real
mistake, large enough to ignore lap-to-lap noise.

Distinct from T085 (late-braking) and T086 (early-release):
those are *cause* rules; T087 is an *outcome* rule. They can
all fire on the same lap (the textbook narrative: braking late,
releasing early, apex speed scrubbed). Useful for the user
because the outcome rule confirms the entry-rules' diagnosis —
"yes, the late braking actually cost you speed at apex".

The 3 km/h threshold is the smallest integer step that's both
above the natural lap-to-lap apex-speed variance (~1-2 km/h on
a clean track in stable conditions) and below "noticeable to
the driver" (~5 km/h). Smaller would spam, larger would miss.
"""
from __future__ import annotations

import pytest

from tests._rules_engine_harness import RuleSpec, build_bundle, emit_for_features


_AC_APEX_SPEED_LOSS = RuleSpec(
    rule_id="ac.apex_speed_loss",
    feature="apex_speed_kph_delta",
    comparison="lte",
    value=-3.0,
    insight_title="Carry more apex speed — you're scrubbing speed mid-corner",
    category="apex",
)


def test_ac_apex_speed_loss_fires_on_substantial_loss() -> None:
    """Realistic firing case: 4.5 km/h slower than reference at
    apex — clearly above noise, should fire."""
    bundle = build_bundle(_AC_APEX_SPEED_LOSS)

    run = emit_for_features(bundle, {"apex_speed_kph_delta": -4.5})

    assert run.fired_rule_ids() == ["ac.apex_speed_loss"]


@pytest.mark.parametrize(
    ("delta_kph", "should_fire"),
    [
        (-10.0, True),    # massive loss (panic-slow corner) — fires
        (-3.0, True),     # boundary: lte includes equal
        (-2.99, False),   # just above threshold — within noise
        (-1.5, False),    # natural lap-to-lap variance
        (0.0, False),     # exactly matched reference
        (1.5, False),     # carrying *more* apex speed — clean
        (4.0, False),     # significant gain — definitely don't fire
    ],
)
def test_ac_apex_speed_loss_threshold_sweep(
    delta_kph: float, should_fire: bool
) -> None:
    """Sweep across the loss/gain spectrum.

    The boundary at -3.0 (lte includes equal) is critical: a
    refactor flipping ``lte`` → ``lt`` would silently reduce
    coverage at the threshold value, and a flip to ``gte`` would
    invert the rule entirely (firing on *gains*, suppressing
    losses)."""
    bundle = build_bundle(_AC_APEX_SPEED_LOSS)

    run = emit_for_features(bundle, {"apex_speed_kph_delta": delta_kph})

    assert (run.fired_rule_ids() == ["ac.apex_speed_loss"]) is should_fire


def test_ac_apex_speed_loss_dormant_when_no_reference_lap() -> None:
    """Out-lap, first lap of a session, or laps in a session
    where reference data is missing — no
    ``apex_speed_kph_delta`` to evaluate. Must sit dormant
    (T079's missing-feature contract)."""
    bundle = build_bundle(_AC_APEX_SPEED_LOSS)

    run = emit_for_features(bundle, {})

    assert run.fired_rule_ids() == []


def test_ac_apex_speed_loss_co_fires_with_braking_rules() -> None:
    """Textbook coaching narrative: late braking + early release
    + apex speed scrubbed → all three fire. This pins the
    multi-rule emission path for the canonical entry-mistake
    sequence."""
    from tests.test_rules_engine_early_release import _BR_EARLY_RELEASE
    from tests.test_rules_engine_late_braking import _BR_LATE_BRAKING

    bundle = build_bundle(_BR_LATE_BRAKING, _BR_EARLY_RELEASE, _AC_APEX_SPEED_LOSS)

    run = emit_for_features(
        bundle,
        {
            "brake_release_lateness_s": 0.18,
            "brake_release_pct": 0.30,
            "apex_speed_kph_delta": -4.0,
        },
    )

    assert sorted(run.fired_rule_ids()) == [
        "ac.apex_speed_loss",
        "br.early_release",
        "br.late_braking",
    ]
