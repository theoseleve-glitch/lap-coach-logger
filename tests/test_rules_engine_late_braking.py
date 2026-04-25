"""T085: Late-braking detection — rule ``br.late_braking`` fires
when the driver releases brake later than reference by ≥ 150 ms.

The actual late-braking rule will be authored server-side and
shipped via the bundle (per ADR-009). T085 pins the *shape* of
that rule on the desktop side: which feature key the engine
expects (``brake_release_lateness_s``) and the firing threshold
the test suite considers "late" (≥ 0.15 s).

When the server's compiled bundle ships the real rule, the test
either:
- still passes if it uses the same feature name and threshold —
  the contract held; or
- fails loudly, which forces a coordinated bundle-version /
  feature-extractor update on the desktop side.

Either way the gap between server-authored rules and client-side
feature plumbing surfaces in test suite output, not in silent
no-fires during a real session.
"""
from __future__ import annotations

import pytest

from tests._rules_engine_harness import RuleSpec, build_bundle, emit_for_features


_BR_LATE_BRAKING = RuleSpec(
    rule_id="br.late_braking",
    feature="brake_release_lateness_s",
    comparison="gte",
    value=0.15,  # seconds late vs reference lap
    insight_title="Brake later — you're releasing too late",
    category="braking",
)


def test_br_late_braking_fires_at_threshold() -> None:
    """Boundary value — at exactly 0.15s the rule fires (gte).
    Pinning the boundary catches off-by-epsilon refactors."""
    bundle = build_bundle(_BR_LATE_BRAKING)

    run = emit_for_features(bundle, {"brake_release_lateness_s": 0.15})

    assert run.fired_rule_ids() == ["br.late_braking"]


def test_br_late_braking_fires_when_substantially_late() -> None:
    """Realistic firing case: 220 ms late on T1 — well past the
    threshold, should fire and reach the VM."""
    bundle = build_bundle(_BR_LATE_BRAKING)

    run = emit_for_features(bundle, {"brake_release_lateness_s": 0.22})

    assert run.fired_rule_ids() == ["br.late_braking"]
    insight = run.insights[0]
    assert insight.payload["title"] == "Brake later — you're releasing too late"


@pytest.mark.parametrize(
    "lateness_s",
    [
        0.0,    # exactly on reference — clean
        0.05,   # 50ms late, within natural lap-to-lap variance
        0.149,  # just below the 0.15s threshold
        -0.10,  # 100ms *earlier* than reference (good)
    ],
)
def test_br_late_braking_does_not_fire_below_threshold(
    lateness_s: float,
) -> None:
    """Sweep the no-fire region below the threshold. The negative
    value (releasing earlier than reference) is critical: the rule
    must not invert and fire when the driver is *better* than
    reference."""
    bundle = build_bundle(_BR_LATE_BRAKING)

    run = emit_for_features(bundle, {"brake_release_lateness_s": lateness_s})

    assert run.fired_rule_ids() == []


def test_br_late_braking_dormant_when_feature_missing() -> None:
    """A lap that didn't hit the brake zone (e.g., out lap, pit
    in/out) won't have ``brake_release_lateness_s`` in its
    feature dict. The rule must sit silent rather than crash —
    T079's missing-feature path is a False, not a raise."""
    bundle = build_bundle(_BR_LATE_BRAKING)

    run = emit_for_features(bundle, {"some_other_feature": 999})

    assert run.fired_rule_ids() == []
