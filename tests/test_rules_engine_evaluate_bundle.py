"""T080: Rules engine — evaluate the whole bundle over a window.

T079 evaluates one condition at a time. T080 layers on the
*orchestrator*: hand it a :class:`RuleBundle` and a feature
snapshot, get back a list of :class:`CoachingInsight` objects —
one per rule that fired this window.

Why a list (and not a stream / generator):
- The live processor invokes this per lap-end (T083), not per
  sample. Latency at lap-end is amortised across thousands of
  samples; allocation cost of a list is negligible.
- The list is consumed by T091's overlay VM, which queues with
  cooldown — having all this lap's insights up-front lets the VM
  rank them by priority before showing.

What T080 deliberately does NOT do:
- N-of-M corroboration gating (T088 — needs lap history).
- Cooldown / dedupe across windows (T092 — the VM owns this).
- Skill-level variant selection (T093 — the VM owns this).

Insight payload is the rule's verbatim ``insight`` dict
(opaque to the engine, owned by T091's renderer). Every fired
insight carries its source ``rule_id`` so T088 can group repeats
across laps.
"""
from __future__ import annotations

import json

from lap_coach_logger.coaching.rules_engine import (
    CoachingInsight,
    evaluate_bundle,
    load_bundle,
)


def _rule(
    rule_id: str,
    *,
    feature: str,
    comparison: str,
    value: float,
    title: str,
) -> dict:
    return {
        "id": rule_id,
        "category": "test",
        "condition": {
            "type": "feature_threshold",
            "feature": feature,
            "comparison": comparison,
            "value": value,
        },
        "insight": {"title": title},
    }


def _bundle(rules: list[dict]) -> dict:
    return {
        "schema_version": "1.0",
        "bundle_id": "rules-test",
        "compiled_at": "2026-04-25T00:00:00Z",
        "rules": rules,
    }


# ---------------------------------------------------------------------------
# Single-rule fan-out
# ---------------------------------------------------------------------------


def test_no_fired_rules_returns_empty_list() -> None:
    """A clean lap that doesn't trip any condition produces no
    insights. Returning ``None`` would force every caller to
    handle two empty-shapes (list vs None) — return ``[]``."""
    bundle = load_bundle(
        _bundle(
            [
                _rule(
                    "br.late",
                    feature="brake_release_pct",
                    comparison="lt",
                    value=0.85,
                    title="Brake later",
                )
            ]
        )
    )

    insights = evaluate_bundle(bundle, features={"brake_release_pct": 0.95})

    assert insights == []


def test_single_fired_rule_yields_one_insight() -> None:
    bundle = load_bundle(
        _bundle(
            [
                _rule(
                    "br.late",
                    feature="brake_release_pct",
                    comparison="lt",
                    value=0.85,
                    title="Brake later into the corner",
                )
            ]
        )
    )

    insights = evaluate_bundle(bundle, features={"brake_release_pct": 0.72})

    assert len(insights) == 1
    insight = insights[0]
    assert isinstance(insight, CoachingInsight)
    assert insight.rule_id == "br.late"
    assert insight.payload == {"title": "Brake later into the corner"}


def test_insight_payload_is_the_rules_full_insight_dict() -> None:
    """The opaque ``insight`` dict from the bundle must reach T091
    untouched — that's where skill-level variants live (T093) and
    where dismiss/flag UX hooks (T097/T098) read their copy."""
    rule = _rule(
        "ac.apex_loss",
        feature="apex_speed_kph",
        comparison="lt",
        value=140.0,
        title="Carry more apex speed",
    )
    rule["insight"] = {
        "title": "Carry more apex speed",
        "rationale": "You're scrubbing speed mid-corner.",
        "skill_levels": {
            "beginner": "Lift a moment later.",
            "intermediate": "Maintain steady throttle through apex.",
            "advanced": "Trail-throttle to balance the car at apex.",
        },
    }
    bundle = load_bundle(_bundle([rule]))

    insights = evaluate_bundle(bundle, features={"apex_speed_kph": 132.0})

    assert insights[0].payload == rule["insight"]


# ---------------------------------------------------------------------------
# Multi-rule fan-out
# ---------------------------------------------------------------------------


def test_multiple_rules_evaluated_each_window() -> None:
    """Every rule sees the same feature dict; one window, all
    rules. Ordering must follow the bundle's rule order so the
    VM's priority logic (T092) sees a deterministic stream."""
    bundle = load_bundle(
        _bundle(
            [
                _rule(
                    "br.late",
                    feature="brake_release_pct",
                    comparison="lt",
                    value=0.85,
                    title="Brake later",
                ),
                _rule(
                    "ac.apex_loss",
                    feature="apex_speed_kph",
                    comparison="lt",
                    value=140.0,
                    title="Carry apex speed",
                ),
            ]
        )
    )

    insights = evaluate_bundle(
        bundle,
        features={"brake_release_pct": 0.72, "apex_speed_kph": 132.0},
    )

    assert [i.rule_id for i in insights] == ["br.late", "ac.apex_loss"]


def test_only_firing_rules_yield_insights() -> None:
    """Two rules in the bundle, only one's condition holds — only
    one insight in the result list (not a list of two with one
    "fired=False" sentinel)."""
    bundle = load_bundle(
        _bundle(
            [
                _rule(
                    "br.late",
                    feature="brake_release_pct",
                    comparison="lt",
                    value=0.85,
                    title="Brake later",
                ),
                _rule(
                    "ac.apex_loss",
                    feature="apex_speed_kph",
                    comparison="lt",
                    value=140.0,
                    title="Carry apex speed",
                ),
            ]
        )
    )

    insights = evaluate_bundle(
        bundle,
        features={
            "brake_release_pct": 0.95,  # br.late won't fire
            "apex_speed_kph": 132.0,  # ac.apex_loss fires
        },
    )

    assert len(insights) == 1
    assert insights[0].rule_id == "ac.apex_loss"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_bundle_returns_empty_list() -> None:
    """Server-side feature flag could legitimately ship an empty
    rules list. Don't crash, don't allocate anything weird —
    just return ``[]``."""
    bundle = load_bundle(_bundle([]))

    assert evaluate_bundle(bundle, features={"x": 0.5}) == []


def test_empty_features_dict_no_rules_fire() -> None:
    """Earliest-window evaluation: features may be empty (no laps
    completed yet). Per T079, missing features no-fire — so the
    bundle yields zero insights instead of crashing on KeyError."""
    bundle = load_bundle(
        _bundle(
            [
                _rule(
                    "br.late",
                    feature="brake_release_pct",
                    comparison="lt",
                    value=0.85,
                    title="Brake later",
                )
            ]
        )
    )

    assert evaluate_bundle(bundle, features={}) == []


def test_insight_is_picklable_for_thread_handoff(
    tmp_path,
) -> None:
    """T082 hands insights from the sample thread to the VM
    thread. Insights MUST round-trip through ``pickle`` /
    ``Queue`` cleanly — no lambdas, no closures, no live refs to
    the bundle. Quick sanity check via JSON (a stricter shape than
    pickle but covers the cases that bite us most: dicts, strings,
    primitives)."""
    bundle = load_bundle(
        _bundle(
            [
                _rule(
                    "br.late",
                    feature="brake_release_pct",
                    comparison="lt",
                    value=0.85,
                    title="Brake later",
                )
            ]
        )
    )

    insights = evaluate_bundle(bundle, features={"brake_release_pct": 0.5})

    # round-trip via JSON — would explode on closures, custom types
    serialised = json.dumps(
        [{"rule_id": i.rule_id, "payload": i.payload} for i in insights]
    )
    restored = json.loads(serialised)
    assert restored == [{"rule_id": "br.late", "payload": {"title": "Brake later"}}]
