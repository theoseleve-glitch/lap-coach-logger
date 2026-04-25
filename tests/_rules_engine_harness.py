"""T084: Rules-engine test harness.

A small builder API for the Block-F detection tests (T085 late
braking, T086 early release, T087 apex speed loss, T088 false-
positive gating). Each detection test wires the same three pieces:

1. A bundle with one (or a few) rule(s) under test.
2. A LapProfile fixture with controllable feature values.
3. A LiveTelemetryProcessor + InsightQueue + extractor wired to
   emit insights at lap-end.

Without this harness each test re-derives all three. With it,
tests reduce to "rule-spec + feature-values → expected insights".

The harness deliberately stays in ``tests/`` (not in
``src/``) — this is test-only infrastructure, not production
plumbing, and putting it in src would conflate the two.

Naming: ``_rules_engine_harness`` (leading underscore) signals
"private to the test suite" by convention; only test files
should import from here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from lap_coach_logger.coaching.rules_engine import (
    CoachingInsight,
    InsightQueue,
    RuleBundle,
    load_bundle,
)
from lap_coach_logger.core.live_lap_compare import LapProfile
from lap_coach_logger.core.live_telemetry_processor import LiveTelemetryProcessor


@dataclass(frozen=True)
class RuleSpec:
    """Terse rule description — shorter than the JSON shape, just
    enough for the detection-test stories."""

    rule_id: str
    feature: str
    comparison: str  # lt / lte / gt / gte / eq
    value: float
    insight_title: str = ""
    category: str = "test"

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.rule_id,
            "category": self.category,
            "condition": {
                "type": "feature_threshold",
                "feature": self.feature,
                "comparison": self.comparison,
                "value": self.value,
            },
            "insight": {
                "title": self.insight_title or self.rule_id,
            },
        }


def build_bundle(*specs: RuleSpec) -> RuleBundle:
    """Build a parsed :class:`RuleBundle` from one or more terse
    :class:`RuleSpec` entries. Bundle metadata is fixed — tests
    don't care about ``compiled_at`` or ``bundle_id``."""
    return load_bundle(
        {
            "schema_version": "1.0",
            "bundle_id": "tests-harness",
            "compiled_at": "2026-04-25T00:00:00Z",
            "rules": [spec.to_json() for spec in specs],
        }
    )


def build_profile(
    *,
    lap_number: int = 1,
    lap_time_s: float = 90.0,
    label: str = "harness-lap",
) -> LapProfile:
    """Build a minimal :class:`LapProfile` — empty points list,
    no segment metrics. Tests that need richer profiles can pass
    a custom one straight to :func:`emit_for_features` instead."""
    return LapProfile(
        source_id="harness",
        label=label,
        lap_number=lap_number,
        lap_time_s=lap_time_s,
        points=[],
    )


def fixed_features_extractor(
    features: dict[str, Any],
) -> Callable[[LapProfile], dict[str, Any]]:
    """Build a feature_extractor that ignores its profile arg and
    always returns the same dict. The detection tests vary
    features per call — this is the simplest way to drive that."""
    return lambda _profile: features


@dataclass
class HarnessRun:
    """Result of one harness run — parsed for assertions."""

    insights: list[CoachingInsight]

    def fired_rule_ids(self) -> list[str]:
        return [i.rule_id for i in self.insights]


def emit_for_features(
    bundle: RuleBundle,
    features: dict[str, Any],
    *,
    profile: LapProfile | None = None,
) -> HarnessRun:
    """End-to-end one-call helper: wire processor + queue + bundle,
    drive ``emit_lap_insights`` once, return the drained queue.

    Equivalent to constructing ``LiveTelemetryProcessor(...)``,
    calling ``proc.emit_lap_insights(profile)``, and draining the
    queue — three lines of boilerplate that every detection test
    would otherwise repeat.
    """
    queue = InsightQueue()
    processor = LiveTelemetryProcessor(
        rule_bundle=bundle,
        insight_queue=queue,
        feature_extractor=fixed_features_extractor(features),
    )
    processor.emit_lap_insights(profile or build_profile())
    return HarnessRun(insights=queue.drain())


__all__ = [
    "HarnessRun",
    "RuleSpec",
    "build_bundle",
    "build_profile",
    "emit_for_features",
    "fixed_features_extractor",
]
