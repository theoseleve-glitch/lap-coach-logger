"""T083: ``LiveTelemetryProcessor`` invokes the rules engine per
lap-end and publishes insights to the VM thread.

T080 produces ``CoachingInsight`` from a feature dict; T082 carries
them across threads via :class:`InsightQueue`; T083 wires both into
the live pipeline. The integration point is the existing lap-end
detection in :meth:`LiveTelemetryProcessor.process` (the same point
that recomputes corner insights).

Three new constructor params (all optional, default ``None``):

- ``rule_bundle``: the parsed :class:`RuleBundle` from T076-T078.
- ``insight_queue``: the :class:`InsightQueue` from T082.
- ``feature_extractor``: a callback that turns a finished
  :class:`LapProfile` into the feature dict T079 evaluates against.
  The shape of that dict is owned downstream (T084 / T085-T087);
  T083 just plumbs values through.

Backwards compat: when any of the three is ``None``, the rules
engine is bypassed and the processor behaves exactly like before.
This lets the existing ``test_live_telemetry_processor_composition``
suite stay green without rewiring.

Tests use :meth:`emit_lap_insights` directly (the public method
T083 adds) rather than driving ``process()`` through fake snapshots
because the lap-boundary detection inside ``process()`` depends on
private LapTracker state — fragile to setup, easy to mis-mock.
"""
from __future__ import annotations

from typing import Callable

from lap_coach_logger.coaching.rules_engine import (
    InsightQueue,
    RuleBundle,
    load_bundle,
)
from lap_coach_logger.core.live_lap_compare import LapProfile
from lap_coach_logger.core.live_telemetry_processor import LiveTelemetryProcessor


def _bundle_with_one_rule(*, threshold: float) -> RuleBundle:
    """Bundle with a single rule that fires when ``lap_time_s``
    is below ``threshold`` — fastest lap detector, easy to wire
    against any LapProfile fixture."""
    return load_bundle(
        {
            "schema_version": "1.0",
            "bundle_id": "rules-test",
            "compiled_at": "2026-04-25T00:00:00Z",
            "rules": [
                {
                    "id": "perf.fast_lap",
                    "category": "performance",
                    "condition": {
                        "type": "feature_threshold",
                        "feature": "lap_time_s",
                        "comparison": "lt",
                        "value": threshold,
                    },
                    "insight": {"title": "Fastest lap so far"},
                },
            ],
        }
    )


def _profile(lap_number: int = 1, lap_time_s: float = 90.0) -> LapProfile:
    return LapProfile(
        source_id="test",
        label="lap-fixture",
        lap_number=lap_number,
        lap_time_s=lap_time_s,
        points=[],
    )


def _basic_extractor() -> Callable[[LapProfile], dict[str, float]]:
    return lambda profile: {"lap_time_s": profile.lap_time_s}


# ---------------------------------------------------------------------------
# Backwards compat: no rules-engine deps wired
# ---------------------------------------------------------------------------


def test_processor_constructs_without_rules_engine_args() -> None:
    """Existing callers and tests that don't pass the new args
    must keep working unchanged. ``LiveTelemetryProcessor()`` with
    no args remains the canonical constructor for the non-coaching
    path."""
    proc = LiveTelemetryProcessor()  # must not raise
    proc.emit_lap_insights(_profile())  # also must not raise — no-op


def test_emit_lap_insights_is_noop_when_bundle_missing() -> None:
    """All three deps must be wired to enable emission. A queue
    + extractor without a bundle is a programmer setup bug, not
    an emission opportunity — silently no-fire so a half-wired
    deployment doesn't queue garbage."""
    queue = InsightQueue()
    proc = LiveTelemetryProcessor(
        insight_queue=queue,
        feature_extractor=_basic_extractor(),
        # rule_bundle missing
    )

    proc.emit_lap_insights(_profile(lap_time_s=60.0))

    assert queue.drain() == []


def test_emit_lap_insights_is_noop_when_queue_missing() -> None:
    """Same reasoning as the missing-bundle case."""
    proc = LiveTelemetryProcessor(
        rule_bundle=_bundle_with_one_rule(threshold=120.0),
        feature_extractor=_basic_extractor(),
        # insight_queue missing
    )

    proc.emit_lap_insights(_profile(lap_time_s=60.0))  # must not raise


def test_emit_lap_insights_is_noop_when_extractor_missing() -> None:
    """No extractor = engine has no way to translate the lap to
    a feature dict, so emission is meaningless. Skip cleanly."""
    queue = InsightQueue()
    proc = LiveTelemetryProcessor(
        rule_bundle=_bundle_with_one_rule(threshold=120.0),
        insight_queue=queue,
        # feature_extractor missing
    )

    proc.emit_lap_insights(_profile(lap_time_s=60.0))

    assert queue.drain() == []


# ---------------------------------------------------------------------------
# Happy path: bundle + queue + extractor all wired
# ---------------------------------------------------------------------------


def test_emit_lap_insights_publishes_when_rule_fires() -> None:
    queue = InsightQueue()
    proc = LiveTelemetryProcessor(
        rule_bundle=_bundle_with_one_rule(threshold=90.0),
        insight_queue=queue,
        feature_extractor=_basic_extractor(),
    )

    proc.emit_lap_insights(_profile(lap_time_s=82.0))  # < 90 threshold

    drained = queue.drain()
    assert len(drained) == 1
    assert drained[0].rule_id == "perf.fast_lap"


def test_emit_lap_insights_publishes_nothing_when_no_rule_fires() -> None:
    """A clean lap that doesn't trip any threshold yields no
    queued insights — the queue stays empty for the VM to drain."""
    queue = InsightQueue()
    proc = LiveTelemetryProcessor(
        rule_bundle=_bundle_with_one_rule(threshold=90.0),
        insight_queue=queue,
        feature_extractor=_basic_extractor(),
    )

    proc.emit_lap_insights(_profile(lap_time_s=95.0))  # > 90 threshold

    assert queue.drain() == []


def test_emit_lap_insights_calls_extractor_with_profile() -> None:
    """The extractor sees the LapProfile, not a pre-flattened
    dict. T084 will plug richer extractors that need access to
    segment_metrics / sector_splits — the boundary must hand
    the full profile through."""
    queue = InsightQueue()
    captured: list[LapProfile] = []

    def capture_extractor(profile: LapProfile) -> dict[str, float]:
        captured.append(profile)
        return {"lap_time_s": profile.lap_time_s}

    proc = LiveTelemetryProcessor(
        rule_bundle=_bundle_with_one_rule(threshold=90.0),
        insight_queue=queue,
        feature_extractor=capture_extractor,
    )
    profile = _profile(lap_number=7, lap_time_s=82.0)

    proc.emit_lap_insights(profile)

    assert captured == [profile]


def test_multiple_lap_ends_publish_distinct_insights() -> None:
    """Each lap-end is an independent emission cycle. T091's VM
    polls the queue and gets *all* lap-end insights since the
    last poll, in order. T083 must not coalesce or dedupe across
    laps — that's T088's gating logic, downstream."""
    queue = InsightQueue()
    proc = LiveTelemetryProcessor(
        rule_bundle=_bundle_with_one_rule(threshold=90.0),
        insight_queue=queue,
        feature_extractor=_basic_extractor(),
    )

    proc.emit_lap_insights(_profile(lap_number=1, lap_time_s=82.0))
    proc.emit_lap_insights(_profile(lap_number=2, lap_time_s=85.0))
    proc.emit_lap_insights(_profile(lap_number=3, lap_time_s=95.0))  # no fire

    drained = queue.drain()
    assert [i.rule_id for i in drained] == ["perf.fast_lap", "perf.fast_lap"]
