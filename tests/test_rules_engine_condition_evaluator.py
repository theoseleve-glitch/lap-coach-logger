"""T079: Rules engine condition evaluator.

Evaluates the opaque ``condition`` dict on a :class:`Rule` against
a session-feature dict (``{"brake_release_pct": 0.72, ...}``) and
returns whether the rule fires.

T076 deferred the condition shape; T079 locks it as a tiny DSL:

- ``feature_threshold``: compare one feature against a constant.
  Comparisons: ``lt``, ``lte``, ``gt``, ``gte``, ``eq``.
- ``and`` / ``or``: composite. Children are themselves conditions.

Why this minimal DSL:
- All three Block-F detection tests (T085 late-braking,
  T086 early-release, T087 apex-speed-loss) are expressible as
  ``feature_threshold`` with `<` or `>`. Composite operators
  cover N-of-M sensor logic without introducing a full expression
  parser.
- Unknown operators raise — not silent — because rules are
  *server-published*. A typo in production rules should fail
  loudly during evaluator dev rather than silently no-fire.
- Missing features return False — not raise — because feature
  dicts are *snapshot views* and a rule can legitimately depend
  on a metric that's not yet computed for this lap (e.g., a
  pre-corner brake metric on a turn the driver hasn't reached).
"""
from __future__ import annotations

import pytest

from lap_coach_logger.coaching.rules_engine import (
    RuleConditionError,
    evaluate_condition,
)


# ---------------------------------------------------------------------------
# feature_threshold: per-comparison happy paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("comparison", "feature_value", "threshold", "expected"),
    [
        ("lt", 0.72, 0.85, True),    # 0.72 < 0.85 → fires
        ("lt", 0.85, 0.85, False),   # boundary: lt is strict
        ("lt", 0.91, 0.85, False),
        ("lte", 0.85, 0.85, True),   # boundary: lte includes equal
        ("lte", 0.86, 0.85, False),
        ("gt", 142.5, 140.0, True),
        ("gt", 140.0, 140.0, False), # boundary: gt is strict
        ("gte", 140.0, 140.0, True),
        ("gte", 139.9, 140.0, False),
        ("eq", 5, 5, True),
        ("eq", 5, 6, False),
        ("eq", 5.0, 5, True),         # int / float interop
    ],
)
def test_feature_threshold_each_comparison(
    comparison: str, feature_value: float, threshold: float, expected: bool
) -> None:
    """One parametrize sweep covers all five comparison ops at
    both their happy path *and* their boundary value — that's
    where off-by-one bugs hide (lt=False at equal, lte=True at
    equal). Splitting these into a dozen named tests would obscure
    that pattern."""
    condition = {
        "type": "feature_threshold",
        "feature": "x",
        "comparison": comparison,
        "value": threshold,
    }

    assert (
        evaluate_condition(condition, features={"x": feature_value})
        is expected
    )


def test_feature_threshold_missing_feature_does_not_fire() -> None:
    """A rule depending on ``brake_release_pct`` shouldn't fire
    when the feature isn't in the dict — most likely the metric
    isn't computed for this lap yet, not "the metric is zero".

    Returning False (rather than raising) lets a rule sit dormant
    on irrelevant laps without the engine swallowing every call
    in a try/except."""
    condition = {
        "type": "feature_threshold",
        "feature": "brake_release_pct",
        "comparison": "lt",
        "value": 0.85,
    }

    assert evaluate_condition(condition, features={"other": 0.5}) is False


def test_feature_threshold_non_numeric_feature_does_not_fire() -> None:
    """Defensive: a feature the upstream code intended to be a
    float but landed as a string (e.g., ``None`` serialised as
    ``""``) shouldn't crash the engine."""
    condition = {
        "type": "feature_threshold",
        "feature": "x",
        "comparison": "lt",
        "value": 0.85,
    }

    assert evaluate_condition(condition, features={"x": "oops"}) is False


# ---------------------------------------------------------------------------
# and / or: composite logic
# ---------------------------------------------------------------------------


def test_and_fires_only_when_all_children_fire() -> None:
    condition = {
        "type": "and",
        "conditions": [
            {
                "type": "feature_threshold",
                "feature": "x",
                "comparison": "lt",
                "value": 1.0,
            },
            {
                "type": "feature_threshold",
                "feature": "y",
                "comparison": "gt",
                "value": 5.0,
            },
        ],
    }

    assert evaluate_condition(condition, features={"x": 0.5, "y": 6.0}) is True
    assert evaluate_condition(condition, features={"x": 0.5, "y": 4.0}) is False
    assert evaluate_condition(condition, features={"x": 1.5, "y": 6.0}) is False


def test_or_fires_when_any_child_fires() -> None:
    condition = {
        "type": "or",
        "conditions": [
            {
                "type": "feature_threshold",
                "feature": "x",
                "comparison": "lt",
                "value": 0.1,
            },
            {
                "type": "feature_threshold",
                "feature": "y",
                "comparison": "gt",
                "value": 9.0,
            },
        ],
    }

    assert evaluate_condition(condition, features={"x": 0.05, "y": 0.0}) is True
    assert evaluate_condition(condition, features={"x": 5.0, "y": 9.5}) is True
    assert evaluate_condition(condition, features={"x": 5.0, "y": 5.0}) is False


def test_and_with_empty_children_is_vacuously_true() -> None:
    """Empty ``and`` over zero conditions is conventionally True
    (matches Python's ``all([])``). Server-side compilers may emit
    this as a degenerate case — don't make them special-case it."""
    assert evaluate_condition({"type": "and", "conditions": []}, features={}) is True


def test_or_with_empty_children_is_vacuously_false() -> None:
    """Empty ``or`` over zero conditions is conventionally False
    (matches Python's ``any([])``)."""
    assert evaluate_condition({"type": "or", "conditions": []}, features={}) is False


def test_nested_composites_evaluate_recursively() -> None:
    """``and(or(a, b), c)`` — guards against a flat-only
    evaluator that doesn't recurse."""
    condition = {
        "type": "and",
        "conditions": [
            {
                "type": "or",
                "conditions": [
                    {
                        "type": "feature_threshold",
                        "feature": "a",
                        "comparison": "gt",
                        "value": 1.0,
                    },
                    {
                        "type": "feature_threshold",
                        "feature": "b",
                        "comparison": "gt",
                        "value": 1.0,
                    },
                ],
            },
            {
                "type": "feature_threshold",
                "feature": "c",
                "comparison": "lt",
                "value": 10.0,
            },
        ],
    }

    # a=0, b=2 (or-true), c=5 (lt-true) → and-true
    assert evaluate_condition(condition, features={"a": 0, "b": 2, "c": 5}) is True
    # a=0, b=0 (or-false) → and-false
    assert (
        evaluate_condition(condition, features={"a": 0, "b": 0, "c": 5}) is False
    )
    # or-true but c=20 (lt-false) → and-false
    assert (
        evaluate_condition(condition, features={"a": 0, "b": 2, "c": 20}) is False
    )


# ---------------------------------------------------------------------------
# Error handling — server-published rule typos must surface loudly
# ---------------------------------------------------------------------------


def test_unknown_operator_type_raises() -> None:
    """A condition type the evaluator doesn't recognise is almost
    certainly a server bug or an out-of-date client. Failing
    silently (as no-fire) would mask that — a rule that should
    have fired never does, and the user sees no feedback. Raise
    so the engine logs / Sentry sees it and a fix ships."""
    condition = {"type": "feature_in_set", "feature": "x", "values": [1, 2]}

    with pytest.raises(RuleConditionError):
        evaluate_condition(condition, features={"x": 1})


def test_unknown_comparison_raises() -> None:
    """Same reasoning: a typo'd comparison op is a server-side
    error, not driver-side noise."""
    condition = {
        "type": "feature_threshold",
        "feature": "x",
        "comparison": "neq",  # not in the supported set
        "value": 1.0,
    }

    with pytest.raises(RuleConditionError):
        evaluate_condition(condition, features={"x": 5})


def test_feature_threshold_missing_required_keys_raises() -> None:
    """A condition without ``feature``/``comparison``/``value``
    can't be meaningfully evaluated — surface as an error rather
    than silently no-fire."""
    condition = {"type": "feature_threshold", "comparison": "lt", "value": 1.0}

    with pytest.raises(RuleConditionError):
        evaluate_condition(condition, features={"x": 0.5})


def test_non_dict_condition_raises() -> None:
    """The shape contract is a dict; anything else is a programmer
    bug worth surfacing."""
    with pytest.raises(RuleConditionError):
        evaluate_condition("not a dict", features={})  # type: ignore[arg-type]
