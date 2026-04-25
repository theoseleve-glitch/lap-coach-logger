"""T076: Rules engine client — ``coaching/rules_engine.py`` loads
a compiled JSON bundle into typed dataclasses.

Per ADR-009, the coaching library is *authored* server-side and
*executed* client-side via a versioned bundle (JSON + embedded
DSL). T076 is just the **parser**: hand it a JSON dict, get back
a ``RuleBundle`` with typed metadata + a list of ``Rule`` objects.

T077 layers disk caching on top, T078 layers signature verification,
T079 layers condition evaluation, T080 wires it to the live processor.
T076 ships none of that — minimal diffs, no scope creep.

Bundle shape (locked here for downstream tasks to evaluate against):

    {
      "schema_version": "1.0",
      "bundle_id": "rules-2026-q1-v1",
      "compiled_at": "2026-04-25T00:00:00Z",
      "rules": [
        {
          "id": "br.late_braking",
          "category": "braking",
          "condition": { ... opaque to T076, T079 evaluates ... },
          "insight": { ... opaque to T076, T091 renders ... },
          "min_corroborating_laps": 3   # optional, T088 gating
        }
      ]
    }

``condition`` and ``insight`` are kept as plain dicts at this layer
because T079/T091 own their internal shapes — locking them now would
force a Block-F rework when those land.
"""
from __future__ import annotations

import json

import pytest

from lap_coach_logger.coaching.rules_engine import (
    Rule,
    RuleBundle,
    RuleBundleParseError,
    load_bundle,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _minimal_rule_dict(rule_id: str = "br.late_braking") -> dict:
    """Smallest valid rule the loader will accept."""
    return {
        "id": rule_id,
        "category": "braking",
        "condition": {"type": "feature_threshold"},
        "insight": {"title": "Brake later"},
    }


def _minimal_bundle_dict(rules: list[dict] | None = None) -> dict:
    return {
        "schema_version": "1.0",
        "bundle_id": "rules-2026-q1-v1",
        "compiled_at": "2026-04-25T00:00:00Z",
        "rules": rules if rules is not None else [_minimal_rule_dict()],
    }


# ---------------------------------------------------------------------------
# Bundle metadata round-trip
# ---------------------------------------------------------------------------


def test_load_bundle_returns_typed_bundle_with_metadata() -> None:
    """The bundle's three identity fields (schema, id, timestamp)
    must come back on a ``RuleBundle`` so T078 can sig-verify
    against ``compiled_at`` and T077 can disk-cache by ``bundle_id``."""
    bundle = load_bundle(_minimal_bundle_dict())

    assert isinstance(bundle, RuleBundle)
    assert bundle.schema_version == "1.0"
    assert bundle.bundle_id == "rules-2026-q1-v1"
    assert bundle.compiled_at == "2026-04-25T00:00:00Z"


def test_load_bundle_returns_list_of_rule_objects() -> None:
    """``rules`` must be a list of typed ``Rule`` objects, not
    raw dicts — that's the whole point of the parser. T079 will
    iterate this list per sample."""
    bundle = load_bundle(
        _minimal_bundle_dict(
            rules=[
                _minimal_rule_dict("br.late_braking"),
                _minimal_rule_dict("ac.apex_speed_loss"),
            ]
        )
    )

    assert len(bundle.rules) == 2
    assert all(isinstance(r, Rule) for r in bundle.rules)
    assert [r.id for r in bundle.rules] == [
        "br.late_braking",
        "ac.apex_speed_loss",
    ]


def test_load_bundle_accepts_json_string_input() -> None:
    """Callers shouldn't have to ``json.loads`` first — the
    parser should accept the raw text form too. Mirrors the
    server-side ``response.text`` shape T077 will fetch."""
    raw = json.dumps(_minimal_bundle_dict())

    bundle = load_bundle(raw)

    assert bundle.bundle_id == "rules-2026-q1-v1"
    assert len(bundle.rules) == 1


# ---------------------------------------------------------------------------
# Per-rule field round-trip
# ---------------------------------------------------------------------------


def test_rule_carries_id_and_category() -> None:
    bundle = load_bundle(_minimal_bundle_dict())

    rule = bundle.rules[0]

    assert rule.id == "br.late_braking"
    assert rule.category == "braking"


def test_rule_keeps_condition_dict_opaque() -> None:
    """``condition`` is owned by T079's evaluator — T076 must
    just round-trip it unmodified, not validate or reshape it.

    Locking the condition shape here would force a Block-F
    rework when T079 settles on its DSL."""
    condition_dict = {
        "type": "feature_threshold",
        "feature": "brake_release_pct",
        "comparison": "lt",
        "value": 0.85,
    }
    bundle = load_bundle(
        _minimal_bundle_dict(
            rules=[{**_minimal_rule_dict(), "condition": condition_dict}]
        )
    )

    assert bundle.rules[0].condition == condition_dict


def test_rule_keeps_insight_dict_opaque() -> None:
    """``insight`` is owned by T091's overlay VM — same reasoning
    as ``condition``. Round-trip unchanged."""
    insight_dict = {
        "title": "Trail-brake later",
        "rationale": "Releasing brake too early carries less energy mid-corner.",
        "skill_levels": {
            "beginner": "Hold the brake later.",
            "intermediate": "Trail-brake to the apex.",
            "advanced": "Modulate trailing brake until tip-in.",
        },
    }
    bundle = load_bundle(
        _minimal_bundle_dict(
            rules=[{**_minimal_rule_dict(), "insight": insight_dict}]
        )
    )

    assert bundle.rules[0].insight == insight_dict


def test_rule_min_corroborating_laps_defaults_to_one() -> None:
    """T088 will gate emission on N corroborating laps. Most
    rules need only 1 (immediate firing); the optional override
    bumps it for noisy detectors. Default-1 means most rules
    can omit the field entirely from the JSON."""
    bundle = load_bundle(_minimal_bundle_dict())

    assert bundle.rules[0].min_corroborating_laps == 1


def test_rule_min_corroborating_laps_round_trips_when_present() -> None:
    bundle = load_bundle(
        _minimal_bundle_dict(
            rules=[{**_minimal_rule_dict(), "min_corroborating_laps": 3}]
        )
    )

    assert bundle.rules[0].min_corroborating_laps == 3


# ---------------------------------------------------------------------------
# Forward compatibility: unknown fields ignored
# ---------------------------------------------------------------------------


def test_unknown_top_level_fields_are_ignored() -> None:
    """The server will eventually add fields T076 doesn't know
    about (signature blob, telemetry-feature requirements, etc.).
    The parser must NOT explode on them — silent forward compat."""
    payload = {**_minimal_bundle_dict(), "future_field": "ignore me"}

    bundle = load_bundle(payload)

    assert bundle.bundle_id == "rules-2026-q1-v1"


def test_unknown_per_rule_fields_are_ignored() -> None:
    """Same forward-compat reasoning at the rule level."""
    payload = _minimal_bundle_dict(
        rules=[{**_minimal_rule_dict(), "future_telemetry_req": ["GPS"]}]
    )

    bundle = load_bundle(payload)

    assert bundle.rules[0].id == "br.late_braking"


# ---------------------------------------------------------------------------
# Error handling — clean exceptions, never raw KeyError / json error
# ---------------------------------------------------------------------------


def test_invalid_json_string_raises_parse_error() -> None:
    """Malformed JSON is the most common loader failure. The
    parser must wrap ``json.JSONDecodeError`` in our own
    exception so callers can pattern-match without depending on
    the ``json`` module."""
    with pytest.raises(RuleBundleParseError):
        load_bundle("{not valid json")


def test_missing_required_top_level_field_raises_parse_error() -> None:
    """Server bug or partial download must surface as a typed
    error, not as a raw ``KeyError``."""
    payload = _minimal_bundle_dict()
    del payload["schema_version"]

    with pytest.raises(RuleBundleParseError):
        load_bundle(payload)


def test_missing_required_rule_field_raises_parse_error() -> None:
    payload = _minimal_bundle_dict(rules=[{"category": "braking"}])  # no id

    with pytest.raises(RuleBundleParseError):
        load_bundle(payload)


def test_rules_must_be_a_list() -> None:
    """A scalar where a list is expected is a sign of bundle
    corruption — fail loudly."""
    payload = {**_minimal_bundle_dict(), "rules": "not a list"}

    with pytest.raises(RuleBundleParseError):
        load_bundle(payload)


def test_empty_rules_list_is_allowed() -> None:
    """An empty bundle is *valid* — could legitimately mean
    "all rules disabled" via server-side feature flag. Don't
    treat it as a parse error."""
    bundle = load_bundle(_minimal_bundle_dict(rules=[]))

    assert bundle.rules == []
