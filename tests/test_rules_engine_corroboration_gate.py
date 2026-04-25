"""T088: False-positive gating — a rule with
``min_corroborating_laps > 1`` only emits an insight after firing
on N consecutive laps.

Why consecutive (not "N-of-M sliding window"):
- Consecutive is interpretable: "I've been doing this every lap
  since lap 5". A sliding window with one outlier would look like
  "I did this 3 of the last 5 laps" — harder to reason about.
- Consecutive resets on a clean lap, which is the user signal
  that matters: "I fixed it" (good), or "I just got lucky once"
  (good — wait for it to recur).

This gate suppresses **first-fire spam**, not steady-state spam.
T092 (overlay VM cooldown) handles "stop telling me the same
thing every lap forever" — separate concern, separate layer.

Default ``min_corroborating_laps = 1`` (T076) means "emit
immediately" so the gate is a no-op for most rules. A noisy
detector (apex-speed-loss with tight conditions, weather noise)
ships with N > 1 to require persistence before nagging.
"""
from __future__ import annotations

import pytest

from lap_coach_logger.coaching.rules_engine import (
    CoachingInsight,
    CorroborationGate,
    load_bundle,
)


def _bundle(rule_specs: list[tuple[str, int]]) -> dict:
    """Build a bundle from ``[(rule_id, min_corroborating_laps), ...]``.

    Conditions are placeholders — the gate doesn't evaluate them;
    callers feed firing insights directly.
    """
    return load_bundle(
        {
            "schema_version": "1.0",
            "bundle_id": "tests-corroboration",
            "compiled_at": "2026-04-25T00:00:00Z",
            "rules": [
                {
                    "id": rule_id,
                    "category": "test",
                    "condition": {"type": "feature_threshold"},
                    "insight": {"title": rule_id},
                    "min_corroborating_laps": min_laps,
                }
                for rule_id, min_laps in rule_specs
            ],
        }
    )


def _insight(rule_id: str) -> CoachingInsight:
    return CoachingInsight(rule_id=rule_id, payload={"title": rule_id})


# ---------------------------------------------------------------------------
# Default min=1: gate is a no-op
# ---------------------------------------------------------------------------


def test_default_min_one_emits_on_first_fire() -> None:
    """Most rules ship with ``min_corroborating_laps = 1`` —
    fire-and-emit, no gating. The gate must pass them straight
    through; otherwise every rule would sit dormant for one lap."""
    gate = CorroborationGate(_bundle([("br.late_braking", 1)]))

    out = gate.process([_insight("br.late_braking")])

    assert [i.rule_id for i in out] == ["br.late_braking"]


# ---------------------------------------------------------------------------
# min=3: suppress until 3 consecutive fires
# ---------------------------------------------------------------------------


def test_min_three_suppresses_first_two_fires() -> None:
    gate = CorroborationGate(_bundle([("ac.apex_speed_loss", 3)]))

    assert gate.process([_insight("ac.apex_speed_loss")]) == []  # lap 1
    assert gate.process([_insight("ac.apex_speed_loss")]) == []  # lap 2


def test_min_three_emits_on_third_consecutive_fire() -> None:
    gate = CorroborationGate(_bundle([("ac.apex_speed_loss", 3)]))

    gate.process([_insight("ac.apex_speed_loss")])
    gate.process([_insight("ac.apex_speed_loss")])
    out = gate.process([_insight("ac.apex_speed_loss")])  # lap 3

    assert [i.rule_id for i in out] == ["ac.apex_speed_loss"]


def test_min_three_keeps_emitting_after_corroboration() -> None:
    """Once corroborated, every subsequent lap that fires the rule
    re-emits — the user is still making the mistake, the gate
    has done its job suppressing the first-fire noise. T092 (VM
    cooldown) is the layer that says "OK stop telling me every
    lap"."""
    gate = CorroborationGate(_bundle([("ac.apex_speed_loss", 3)]))

    for _ in range(3):
        gate.process([_insight("ac.apex_speed_loss")])

    # laps 4, 5, 6 — all should emit
    for _ in range(3):
        out = gate.process([_insight("ac.apex_speed_loss")])
        assert [i.rule_id for i in out] == ["ac.apex_speed_loss"]


# ---------------------------------------------------------------------------
# Reset semantics: a clean lap resets the counter
# ---------------------------------------------------------------------------


def test_clean_lap_resets_consecutive_count() -> None:
    """Two fires, one clean, two more fires — total 4 fires but
    NOT consecutive. The corroboration re-starts after the clean
    lap, so emission requires three more (laps 4, 5, 6) on top
    of the post-clean-lap tally."""
    gate = CorroborationGate(_bundle([("ac.apex_speed_loss", 3)]))

    gate.process([_insight("ac.apex_speed_loss")])  # lap 1: count 1
    gate.process([_insight("ac.apex_speed_loss")])  # lap 2: count 2
    gate.process([])                                # lap 3: clean → reset to 0
    out_lap_4 = gate.process([_insight("ac.apex_speed_loss")])  # count 1
    out_lap_5 = gate.process([_insight("ac.apex_speed_loss")])  # count 2

    assert out_lap_4 == []  # still gated
    assert out_lap_5 == []  # still gated


# ---------------------------------------------------------------------------
# Multiple rules with different thresholds
# ---------------------------------------------------------------------------


def test_each_rule_tracks_its_own_count() -> None:
    """Two rules, one with min=1 (immediate), one with min=2 (gated).
    Both fire every lap. The min=1 rule emits each lap; the min=2
    rule starts emitting at lap 2."""
    gate = CorroborationGate(
        _bundle([("br.late_braking", 1), ("ac.apex_speed_loss", 2)])
    )

    out_lap_1 = gate.process(
        [_insight("br.late_braking"), _insight("ac.apex_speed_loss")]
    )
    out_lap_2 = gate.process(
        [_insight("br.late_braking"), _insight("ac.apex_speed_loss")]
    )

    assert [i.rule_id for i in out_lap_1] == ["br.late_braking"]
    assert sorted(i.rule_id for i in out_lap_2) == [
        "ac.apex_speed_loss",
        "br.late_braking",
    ]


def test_one_rule_firing_does_not_reset_anothers_count() -> None:
    """Rule A and rule B both have min=2. A fires lap 1+2; B fires
    only lap 2. The gate must update counts independently — A
    emits on lap 2, B doesn't."""
    gate = CorroborationGate(_bundle([("a", 2), ("b", 2)]))

    out_lap_1 = gate.process([_insight("a")])  # a:1, b:0
    out_lap_2 = gate.process([_insight("a"), _insight("b")])  # a:2, b:1

    assert out_lap_1 == []
    assert [i.rule_id for i in out_lap_2] == ["a"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_unknown_rule_id_passes_through_with_default_min_one() -> None:
    """A rule fires that wasn't in the bundle the gate was built
    with — could happen during a hot reload. Default to min=1
    rather than crash so the system stays operational."""
    gate = CorroborationGate(_bundle([("known", 1)]))

    out = gate.process([_insight("unknown_rule_id_not_in_bundle")])

    assert [i.rule_id for i in out] == ["unknown_rule_id_not_in_bundle"]


def test_empty_insight_list_is_a_clean_lap() -> None:
    """A no-fire lap (empty insights) must reset the counter for
    every known rule — same semantics as the explicit "clean lap"
    case above."""
    gate = CorroborationGate(_bundle([("a", 3)]))

    gate.process([_insight("a")])
    gate.process([_insight("a")])
    gate.process([])  # empty = clean lap → resets a's count

    out = gate.process([_insight("a")])
    assert out == []  # back to count=1, still gated


def test_insight_payload_round_trips_unchanged() -> None:
    """Filtering must NOT mutate / rebuild the CoachingInsight —
    payload reaches T091 byte-identical."""
    gate = CorroborationGate(_bundle([("br.late", 1)]))

    rich_insight = CoachingInsight(
        rule_id="br.late",
        payload={"title": "Brake later", "rationale": "long-form coaching"},
    )

    [out] = gate.process([rich_insight])
    assert out is rich_insight  # same object, no copy
