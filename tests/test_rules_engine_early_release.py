"""T086: Early-release detection — rule ``br.early_release`` fires
when the driver lets off the brake too early in the brake zone,
leaving entry speed on the table.

Mechanically: ``brake_release_pct`` is the fraction of the brake
zone where brake pressure first drops below an "off" threshold
(typically < 5% pressure). A textbook trail-brake holds pressure
to ~80–90% of the zone (``brake_release_pct ≥ 0.80``); releasing
in the first 40% (``brake_release_pct < 0.40``) is the symptom
this rule detects.

Distinct from T085 (``br.late_braking``) — T085 is "released too
late vs reference"; T086 is "released too early relative to the
brake zone itself". Same insight category (braking), different
dimension. Both can fire on the same lap (rare but legal: a brief
panic stab early, full release before apex).
"""
from __future__ import annotations

import pytest

from tests._rules_engine_harness import RuleSpec, build_bundle, emit_for_features


_BR_EARLY_RELEASE = RuleSpec(
    rule_id="br.early_release",
    feature="brake_release_pct",
    comparison="lt",
    value=0.40,  # released in the first 40% of the brake zone
    insight_title="Trail-brake longer — you're releasing too early",
    category="braking",
)


def test_br_early_release_fires_when_well_below_threshold() -> None:
    """A textbook early-release case: released at 25% of the
    brake zone — well past the 40% trigger."""
    bundle = build_bundle(_BR_EARLY_RELEASE)

    run = emit_for_features(bundle, {"brake_release_pct": 0.25})

    assert run.fired_rule_ids() == ["br.early_release"]
    assert run.insights[0].payload["title"] == (
        "Trail-brake longer — you're releasing too early"
    )


@pytest.mark.parametrize(
    ("release_pct", "should_fire"),
    [
        (0.10, True),    # very early — fires
        (0.39, True),    # just below threshold — fires (lt is strict)
        (0.40, False),   # boundary: lt is strict, 0.40 does not fire
        (0.50, False),
        (0.85, False),   # textbook trail-brake — clean
        (1.00, False),   # full release at apex — clean
    ],
)
def test_br_early_release_threshold_sweep(
    release_pct: float, should_fire: bool
) -> None:
    """Sweep across the brake zone — fires for early-release
    cases (< 0.40), no-fire for trail-brakers and clean laps.

    The boundary (0.40 vs 0.39) is critical because ``lt`` is
    strict; an off-by-one comparison op (``lte``) would fire on
    every clean trail-brake at exactly 0.40, drowning the user
    in false positives."""
    bundle = build_bundle(_BR_EARLY_RELEASE)

    run = emit_for_features(bundle, {"brake_release_pct": release_pct})

    assert (run.fired_rule_ids() == ["br.early_release"]) is should_fire


def test_br_early_release_dormant_when_feature_missing() -> None:
    """Out-lap or pit lap with no brake event → no
    ``brake_release_pct`` in the feature dict. Stay dormant
    rather than crash (T079's missing-feature contract)."""
    bundle = build_bundle(_BR_EARLY_RELEASE)

    run = emit_for_features(bundle, {})

    assert run.fired_rule_ids() == []


def test_br_early_release_and_late_braking_can_co_fire() -> None:
    """A pathological lap could both release early (panic stab)
    and be late vs reference — both rules in one lap. The engine
    must emit both insights; downstream T088 gating decides
    whether to surface them or coalesce.

    This pins that T080's per-rule fan-out doesn't accidentally
    coalesce same-category insights into one — each rule fires
    independently."""
    from tests.test_rules_engine_late_braking import _BR_LATE_BRAKING

    bundle = build_bundle(_BR_LATE_BRAKING, _BR_EARLY_RELEASE)

    run = emit_for_features(
        bundle,
        {
            "brake_release_lateness_s": 0.20,  # late
            "brake_release_pct": 0.25,         # early
        },
    )

    assert sorted(run.fired_rule_ids()) == ["br.early_release", "br.late_braking"]
