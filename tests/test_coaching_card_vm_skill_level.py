"""T093: Coaching card VM resolves the insight's text to the
user's skill-level variant.

Server-shipped rules carry a ``skill_levels`` dict in their
``insight`` payload — beginner / intermediate / advanced
variants of the same coaching point:

    skill_levels: {
      "beginner": "Hold the brake later into the corner.",
      "intermediate": "Trail-brake to the apex.",
      "advanced": "Modulate trailing brake until apex tip-in."
    }

The VM resolves which one to display based on the user's
configured skill level. T093 ships:

- ``CoachingCardViewModel.skill_level`` constructor param
  (default ``"intermediate"``).
- ``insight.text`` derived field — the resolved variant, with a
  graceful fallback to the rule's ``title`` when the variant
  isn't available (e.g., a legacy rule without skill_levels).

Why fallback to title (not empty / not "<missing>"): a rule
without skill-level variants still has a useful coaching message
in its title — that's the original T091 contract. Skill-level
variants enhance, they don't replace.

T093 doesn't ship a way to *change* skill_level on a live VM
(the user setting is read at session start; mid-session changes
are out of scope) — keep that path simple.
"""
from __future__ import annotations

import pytest

from lap_coach_logger.coaching.rules_engine import (
    CoachingInsight,
    InsightQueue,
)
from lap_coach_logger.viewmodels.coaching_card_vm import CoachingCardViewModel


def _insight_with_levels(
    rule_id: str = "br.late_braking",
) -> CoachingInsight:
    return CoachingInsight(
        rule_id=rule_id,
        payload={
            "title": "Brake later",  # generic fallback
            "skill_levels": {
                "beginner": "Hold the brake later into the corner.",
                "intermediate": "Trail-brake to the apex.",
                "advanced": "Modulate trailing brake until tip-in.",
            },
        },
    )


# ---------------------------------------------------------------------------
# Skill-level variant resolution
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("skill_level", "expected_text"),
    [
        ("beginner", "Hold the brake later into the corner."),
        ("intermediate", "Trail-brake to the apex."),
        ("advanced", "Modulate trailing brake until tip-in."),
    ],
)
def test_insight_text_matches_user_skill_level(
    skill_level: str, expected_text: str
) -> None:
    """Sweep across the three supported skill levels — each
    resolves to its own variant. A typo'd skill_level constant
    on the VM side would silently fall through to the title;
    the parametrize sweep catches that immediately."""
    queue = InsightQueue()
    queue.publish([_insight_with_levels()])
    vm = CoachingCardViewModel(queue=queue, skill_level=skill_level)

    vm.poll()

    assert vm.insight["text"] == expected_text


def test_default_skill_level_is_intermediate() -> None:
    """Most users sit between hardcore and brand-new — the
    intermediate variant is the safest default and matches the
    coaching library's authoring guidance."""
    queue = InsightQueue()
    queue.publish([_insight_with_levels()])
    vm = CoachingCardViewModel(queue=queue)

    vm.poll()

    assert vm.insight["text"] == "Trail-brake to the apex."


# ---------------------------------------------------------------------------
# Fallback when variant unavailable
# ---------------------------------------------------------------------------


def test_falls_back_to_title_when_no_skill_levels_in_payload() -> None:
    """A legacy rule (or a rule the server didn't bother
    skill-tiering) carries only ``title``. The VM must still
    show something — the title is the documented base contract
    from T091."""
    queue = InsightQueue()
    queue.publish(
        [
            CoachingInsight(
                rule_id="legacy.no_levels",
                payload={"title": "Braking too late vs reference"},
            )
        ]
    )
    vm = CoachingCardViewModel(queue=queue, skill_level="advanced")

    vm.poll()

    assert vm.insight["text"] == "Braking too late vs reference"


def test_falls_back_to_title_when_skill_level_missing_from_levels() -> None:
    """Server might ship only beginner+intermediate variants for
    some rules. An advanced user reading those rules falls back
    to the title rather than getting an empty card."""
    queue = InsightQueue()
    queue.publish(
        [
            CoachingInsight(
                rule_id="partial",
                payload={
                    "title": "Carry more apex speed",
                    "skill_levels": {"beginner": "Lift later."},
                },
            )
        ]
    )
    vm = CoachingCardViewModel(queue=queue, skill_level="advanced")

    vm.poll()

    assert vm.insight["text"] == "Carry more apex speed"


def test_falls_back_to_empty_string_when_no_title_or_levels() -> None:
    """Pathological case: a rule with no title AND no skill
    variants. Must not crash QML — fall back to empty string
    (QML's ``|| "—"`` then takes over)."""
    queue = InsightQueue()
    queue.publish(
        [
            CoachingInsight(
                rule_id="empty.payload",
                payload={"category": "braking"},  # no title, no levels
            )
        ]
    )
    vm = CoachingCardViewModel(queue=queue)

    vm.poll()

    assert vm.insight["text"] == ""


# ---------------------------------------------------------------------------
# Other QML-bindable fields still flow through
# ---------------------------------------------------------------------------


def test_insight_still_carries_rule_id() -> None:
    """T091 contract: rule_id reaches QML alongside payload.
    T093 must not strip it while injecting ``text``."""
    queue = InsightQueue()
    queue.publish([_insight_with_levels(rule_id="br.late_braking")])
    vm = CoachingCardViewModel(queue=queue)

    vm.poll()

    assert vm.insight["rule_id"] == "br.late_braking"


def test_insight_still_carries_other_payload_fields() -> None:
    """A rule's ``insight`` payload may carry rationale, drill
    links, etc. — fields T097 / T098 will read. T093 augments
    with ``text`` but must not drop other fields."""
    queue = InsightQueue()
    queue.publish(
        [
            CoachingInsight(
                rule_id="rich",
                payload={
                    "title": "Brake later",
                    "rationale": "You're losing time at T1 entry.",
                    "drill_template_id": "drill.t1_brake_zone",
                    "skill_levels": {"intermediate": "Trail to apex."},
                },
            )
        ]
    )
    vm = CoachingCardViewModel(queue=queue)

    vm.poll()

    assert vm.insight["rationale"] == "You're losing time at T1 entry."
    assert vm.insight["drill_template_id"] == "drill.t1_brake_zone"
    assert vm.insight["text"] == "Trail to apex."


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_unknown_skill_level_string_falls_back_to_title() -> None:
    """Defensive: a user-config typo or a future skill level
    shouldn't crash the VM. Fall back to title."""
    queue = InsightQueue()
    queue.publish([_insight_with_levels()])
    vm = CoachingCardViewModel(queue=queue, skill_level="grandmaster")

    vm.poll()

    assert vm.insight["text"] == "Brake later"
