"""T076: Rules engine client — compiled-bundle parser.

ADR-009 splits the coaching library across server (authors rules)
and client (executes rules during live session). This module is
the client's **parser**: hand it a JSON dict (or raw text) and
get back a typed :class:`RuleBundle`. Downstream tasks layer on
top:

- T077 — disk cache (fetch once, reuse for 7 days)
- T078 — signature verification of the cached bundle
- T079 — condition evaluation against a feature dict
- T080 — wiring to the live telemetry processor

The :attr:`Rule.condition` and :attr:`Rule.insight` payloads stay as
plain ``dict`` values at this layer — T079 owns the condition DSL,
T091 owns the insight presentation shape, and locking either of
them in T076 would force a Block-F rework when those land.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


class RuleBundleParseError(ValueError):
    """Raised when a bundle payload can't be parsed into a typed
    :class:`RuleBundle` — invalid JSON, missing required fields,
    wrong types, etc. Wraps the underlying error so callers don't
    have to depend on the ``json`` module to pattern-match."""


@dataclass(frozen=True)
class Rule:
    """One coaching rule from the bundle."""

    id: str
    category: str
    condition: dict[str, Any]
    insight: dict[str, Any]
    min_corroborating_laps: int = 1


@dataclass(frozen=True)
class RuleBundle:
    """Versioned, server-authored bundle of coaching rules."""

    schema_version: str
    bundle_id: str
    compiled_at: str
    rules: list[Rule] = field(default_factory=list)


_REQUIRED_BUNDLE_FIELDS = ("schema_version", "bundle_id", "compiled_at", "rules")
_REQUIRED_RULE_FIELDS = ("id", "category", "condition", "insight")


def load_bundle(data: str | dict[str, Any]) -> RuleBundle:
    """Parse a JSON bundle (text or already-decoded dict) into
    a :class:`RuleBundle`.

    Forward-compat by design: unknown top-level and per-rule
    fields are silently ignored so the server can add metadata
    (signatures, telemetry requirements, …) without forcing a
    coordinated client release.
    """
    payload = _decode(data)
    _require_fields(payload, _REQUIRED_BUNDLE_FIELDS, context="bundle")

    raw_rules = payload["rules"]
    if not isinstance(raw_rules, list):
        raise RuleBundleParseError(
            f"bundle 'rules' must be a list, got {type(raw_rules).__name__}"
        )

    rules = [_build_rule(entry, index=i) for i, entry in enumerate(raw_rules)]

    return RuleBundle(
        schema_version=str(payload["schema_version"]),
        bundle_id=str(payload["bundle_id"]),
        compiled_at=str(payload["compiled_at"]),
        rules=rules,
    )


def _decode(data: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        try:
            decoded = json.loads(data)
        except json.JSONDecodeError as exc:
            raise RuleBundleParseError(f"invalid JSON: {exc}") from exc
        if not isinstance(decoded, dict):
            raise RuleBundleParseError(
                f"bundle root must be an object, got {type(decoded).__name__}"
            )
        return decoded
    raise RuleBundleParseError(
        f"bundle must be a dict or JSON string, got {type(data).__name__}"
    )


def _require_fields(
    payload: dict[str, Any], fields: tuple[str, ...], *, context: str
) -> None:
    missing = [f for f in fields if f not in payload]
    if missing:
        raise RuleBundleParseError(
            f"{context} missing required field(s): {', '.join(missing)}"
        )


def _build_rule(entry: Any, *, index: int) -> Rule:
    if not isinstance(entry, dict):
        raise RuleBundleParseError(
            f"rules[{index}] must be an object, got {type(entry).__name__}"
        )
    _require_fields(entry, _REQUIRED_RULE_FIELDS, context=f"rules[{index}]")

    condition = entry["condition"]
    insight = entry["insight"]
    if not isinstance(condition, dict):
        raise RuleBundleParseError(
            f"rules[{index}].condition must be an object, "
            f"got {type(condition).__name__}"
        )
    if not isinstance(insight, dict):
        raise RuleBundleParseError(
            f"rules[{index}].insight must be an object, "
            f"got {type(insight).__name__}"
        )

    return Rule(
        id=str(entry["id"]),
        category=str(entry["category"]),
        condition=condition,
        insight=insight,
        min_corroborating_laps=int(entry.get("min_corroborating_laps", 1)),
    )


__all__ = ["Rule", "RuleBundle", "RuleBundleParseError", "load_bundle"]
