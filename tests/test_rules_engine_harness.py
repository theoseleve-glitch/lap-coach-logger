"""T084: Tests for the rules-engine test harness itself.

The harness is test infrastructure (T085-T088 use it), not
production plumbing — but the harness must work correctly or
those downstream tests will give false confidence. This file
pins its public-API contract.
"""
from __future__ import annotations

from tests._rules_engine_harness import (
    RuleSpec,
    build_bundle,
    build_profile,
    emit_for_features,
    fixed_features_extractor,
)


# ---------------------------------------------------------------------------
# Bundle building
# ---------------------------------------------------------------------------


def test_build_bundle_with_one_rule_round_trips_through_loader() -> None:
    """``build_bundle`` must produce a real parsed RuleBundle —
    not a half-constructed dict the load_bundle path skipped."""
    bundle = build_bundle(
        RuleSpec(
            rule_id="br.late",
            feature="brake_release_pct",
            comparison="lt",
            value=0.85,
        ),
    )

    assert bundle.bundle_id == "tests-harness"
    assert len(bundle.rules) == 1
    assert bundle.rules[0].id == "br.late"


def test_build_bundle_preserves_spec_order() -> None:
    """Rule order is significant (T080 preserves bundle order on
    output for T091's priority queue). Pin that the harness
    doesn't reorder specs."""
    bundle = build_bundle(
        RuleSpec(rule_id="a", feature="x", comparison="lt", value=1.0),
        RuleSpec(rule_id="b", feature="y", comparison="lt", value=1.0),
        RuleSpec(rule_id="c", feature="z", comparison="lt", value=1.0),
    )

    assert [r.id for r in bundle.rules] == ["a", "b", "c"]


def test_build_bundle_uses_rule_id_as_default_insight_title() -> None:
    """When no ``insight_title`` is passed, the bundle's insight
    payload still has a non-empty title — useful for parametrized
    tests where the caller doesn't care about display copy."""
    bundle = build_bundle(
        RuleSpec(rule_id="br.late", feature="x", comparison="lt", value=1.0),
    )

    assert bundle.rules[0].insight == {"title": "br.late"}


# ---------------------------------------------------------------------------
# Profile building
# ---------------------------------------------------------------------------


def test_build_profile_defaults_to_lap_one() -> None:
    profile = build_profile()

    assert profile.lap_number == 1
    assert profile.lap_time_s == 90.0


def test_build_profile_overrides_apply() -> None:
    profile = build_profile(lap_number=5, lap_time_s=82.345, label="hot-lap")

    assert profile.lap_number == 5
    assert profile.lap_time_s == 82.345
    assert profile.label == "hot-lap"


# ---------------------------------------------------------------------------
# Feature extractor
# ---------------------------------------------------------------------------


def test_fixed_features_extractor_returns_same_dict_regardless_of_profile() -> None:
    """The extractor short-circuits the LapProfile → feature dict
    conversion that production code does. Tests vary features per
    call without bothering with a real extractor."""
    extractor = fixed_features_extractor({"x": 0.5})

    assert extractor(build_profile(lap_number=1)) == {"x": 0.5}
    assert extractor(build_profile(lap_number=99)) == {"x": 0.5}


# ---------------------------------------------------------------------------
# End-to-end one-call helper
# ---------------------------------------------------------------------------


def test_emit_for_features_returns_insight_when_rule_matches() -> None:
    bundle = build_bundle(
        RuleSpec(
            rule_id="br.late",
            feature="brake_release_pct",
            comparison="lt",
            value=0.85,
        ),
    )

    run = emit_for_features(bundle, {"brake_release_pct": 0.72})

    assert run.fired_rule_ids() == ["br.late"]


def test_emit_for_features_returns_empty_when_no_rule_matches() -> None:
    bundle = build_bundle(
        RuleSpec(
            rule_id="br.late",
            feature="brake_release_pct",
            comparison="lt",
            value=0.85,
        ),
    )

    run = emit_for_features(bundle, {"brake_release_pct": 0.95})

    assert run.fired_rule_ids() == []


def test_emit_for_features_handles_multiple_rules() -> None:
    bundle = build_bundle(
        RuleSpec(rule_id="a", feature="x", comparison="lt", value=1.0),
        RuleSpec(rule_id="b", feature="y", comparison="gt", value=5.0),
    )

    run = emit_for_features(bundle, {"x": 0.5, "y": 6.0})

    assert sorted(run.fired_rule_ids()) == ["a", "b"]


def test_emit_for_features_insight_payload_carries_through() -> None:
    """Detection tests will assert on insight content (title at
    minimum). Pin that the payload survives the harness wiring."""
    bundle = build_bundle(
        RuleSpec(
            rule_id="br.late",
            feature="x",
            comparison="lt",
            value=1.0,
            insight_title="Brake later into T1",
        ),
    )

    run = emit_for_features(bundle, {"x": 0.5})

    assert run.insights[0].payload == {"title": "Brake later into T1"}
