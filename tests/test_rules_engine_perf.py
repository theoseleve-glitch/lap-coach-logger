"""T212: Perf profile — rules engine overhead <1ms per evaluation.

Sprint target: ``evaluate_bundle`` (the per-lap rules-engine entry
point) must add less than 1 ms of overhead per call, even with a
realistic-size bundle (~30 rules) against a typical feature
snapshot. This file pins the budget plus per-condition micro-
benchmarks so any algorithmic regression (accidental O(n²) loop,
runaway allocation) is caught in CI before reaching production.

Per the engine's docstring (T080-T088), evaluate_bundle runs
"at lap-end on the sample thread" — the budget there is the
inter-sample interval (~16 ms at 60 fps), but the design goal
is much tighter (<1 ms) so that future per-sample evaluation
remains feasible. Tests use a generous CI budget (5 ms) to
allow for slow runners while still catching regressions of
> 5x typical perf.

Sample evaluation order:
  load_bundle(json) → bundle  (one-time, NOT in hot path)
  evaluate_bundle(bundle, features=...) → list[CoachingInsight]  (HOT)
"""
from __future__ import annotations

import time

import pytest

from lap_coach_logger.coaching.rules_engine import (
    Rule,
    RuleBundle,
    evaluate_bundle,
    evaluate_condition,
)


# ---------------------------------------------------------------------------
# Budgets (CI-safe wall-clock)
# ---------------------------------------------------------------------------

_ITERATIONS = 5000
# Per-call target is <1ms; CI budget is 5ms/call to allow slow runners
# while still catching > 5× regressions.
_PER_CALL_BUDGET_MS = 5.0
_PER_CALL_TARGET_MS = 1.0  # informational, not asserted

# Total budget for N iterations at the per-call ceiling.
_TOTAL_BUDGET_S = _ITERATIONS * _PER_CALL_BUDGET_MS / 1000.0


# ---------------------------------------------------------------------------
# Realistic test fixtures
# ---------------------------------------------------------------------------


def _build_realistic_bundle(num_rules: int = 30) -> RuleBundle:
    """Build a bundle representing a realistic coaching library:
    feature_threshold rules + nested AND/OR composites, mixing
    comparisons across typical telemetry-derived features."""
    rules: list[Rule] = []
    features = [
        "max_brake_pressure_lap", "min_corner_speed_kph",
        "throttle_lift_pct", "brake_release_smoothness",
        "apex_speed_kph", "exit_speed_kph",
        "tyre_temp_lf", "tyre_temp_rf", "tyre_temp_lr", "tyre_temp_rr",
        "fuel_per_lap_l", "lap_time_s",
    ]
    comparisons = ["lt", "lte", "gt", "gte", "eq"]

    for i in range(num_rules):
        feat = features[i % len(features)]
        comp = comparisons[i % len(comparisons)]
        threshold = float((i % 50) + 10) * 1.5

        if i % 4 == 0:
            # Plain feature_threshold (most common shape).
            condition = {
                "type": "feature_threshold",
                "feature": feat,
                "comparison": comp,
                "value": threshold,
            }
        elif i % 4 == 1:
            # AND of two thresholds.
            condition = {
                "type": "and",
                "conditions": [
                    {
                        "type": "feature_threshold",
                        "feature": feat,
                        "comparison": "gt",
                        "value": threshold,
                    },
                    {
                        "type": "feature_threshold",
                        "feature": features[(i + 3) % len(features)],
                        "comparison": "lt",
                        "value": threshold * 1.1,
                    },
                ],
            }
        elif i % 4 == 2:
            # OR of two thresholds.
            condition = {
                "type": "or",
                "conditions": [
                    {
                        "type": "feature_threshold",
                        "feature": feat,
                        "comparison": "lt",
                        "value": threshold,
                    },
                    {
                        "type": "feature_threshold",
                        "feature": features[(i + 5) % len(features)],
                        "comparison": "gt",
                        "value": threshold * 0.9,
                    },
                ],
            }
        else:
            # Nested AND( OR(a, b), threshold ) — depth 3.
            condition = {
                "type": "and",
                "conditions": [
                    {
                        "type": "or",
                        "conditions": [
                            {
                                "type": "feature_threshold",
                                "feature": feat,
                                "comparison": "lt",
                                "value": threshold,
                            },
                            {
                                "type": "feature_threshold",
                                "feature": features[(i + 2) % len(features)],
                                "comparison": "gte",
                                "value": threshold * 1.05,
                            },
                        ],
                    },
                    {
                        "type": "feature_threshold",
                        "feature": features[(i + 7) % len(features)],
                        "comparison": "lte",
                        "value": threshold * 0.8,
                    },
                ],
            }

        rules.append(Rule(
            id=f"rule-{i:03d}",
            category=("braking", "cornering", "throttle", "tyres")[i % 4],
            condition=condition,
            insight={
                "summary": f"Coaching insight #{i}",
                "detail": (
                    f"Compare {feat} against {threshold} via {comp} — "
                    f"this is rule {i} in the test bundle."
                ),
                "severity": ("info", "advisory", "critical")[i % 3],
            },
            min_corroborating_laps=1,
        ))

    return RuleBundle(
        schema_version="1.0",
        bundle_id="perf-test-bundle",
        compiled_at="2026-04-26T00:00:00Z",
        rules=rules,
    )


def _build_realistic_features() -> dict[str, float]:
    """Build a realistic feature dict — what the live processor
    hands to evaluate_bundle at lap-end."""
    return {
        "max_brake_pressure_lap": 0.95,
        "min_corner_speed_kph": 65.0,
        "throttle_lift_pct": 0.12,
        "brake_release_smoothness": 0.88,
        "apex_speed_kph": 78.0,
        "exit_speed_kph": 165.0,
        "tyre_temp_lf": 88.0,
        "tyre_temp_rf": 92.0,
        "tyre_temp_lr": 84.0,
        "tyre_temp_rr": 86.0,
        "fuel_per_lap_l": 3.2,
        "lap_time_s": 105.4,
        # Some features the bundle doesn't reference (real session has
        # extras that no rule cares about — must not slow the engine).
        "session_uid": 12345,
        "track_temp_c": 32.0,
        "air_temp_c": 22.0,
    }


# ---------------------------------------------------------------------------
# evaluate_bundle: per-call budget on a realistic-size bundle
# ---------------------------------------------------------------------------


def test_evaluate_bundle_meets_per_call_budget() -> None:
    """Pin the per-call wall-clock for evaluate_bundle on a 30-rule
    bundle. Each call processes all rules and returns insights for
    the ones that fired."""
    bundle = _build_realistic_bundle(num_rules=30)
    features = _build_realistic_features()

    # Warm-up to amortise import cost / JIT-like effects.
    for _ in range(50):
        evaluate_bundle(bundle, features=features)

    start = time.perf_counter()
    for _ in range(_ITERATIONS):
        evaluate_bundle(bundle, features=features)
    elapsed = time.perf_counter() - start

    per_call_ms = (elapsed * 1000.0) / _ITERATIONS
    assert elapsed < _TOTAL_BUDGET_S, (
        f"evaluate_bundle slow: {elapsed:.3f}s for {_ITERATIONS} calls "
        f"({per_call_ms:.3f}ms/call) — CI budget {_PER_CALL_BUDGET_MS}ms; "
        f"sprint target {_PER_CALL_TARGET_MS}ms"
    )


def test_evaluate_bundle_scales_linearly_with_rule_count() -> None:
    """A 60-rule bundle should take ~2x of a 30-rule bundle (within
    2x slack). If it takes 10x the cost the engine has an O(n²)
    cliff that needs investigation."""
    features = _build_realistic_features()

    bundle_small = _build_realistic_bundle(num_rules=15)
    bundle_large = _build_realistic_bundle(num_rules=60)

    # Warm up both.
    for _ in range(50):
        evaluate_bundle(bundle_small, features=features)
        evaluate_bundle(bundle_large, features=features)

    iters = 1000

    t0 = time.perf_counter()
    for _ in range(iters):
        evaluate_bundle(bundle_small, features=features)
    small_elapsed = time.perf_counter() - t0

    t0 = time.perf_counter()
    for _ in range(iters):
        evaluate_bundle(bundle_large, features=features)
    large_elapsed = time.perf_counter() - t0

    # 4× the rules ≈ 4× the work, allow up to 8× for headroom.
    ratio = large_elapsed / max(small_elapsed, 1e-6)
    assert ratio < 8.0, (
        f"evaluate_bundle scales worse than O(n): 4× the rules took "
        f"{ratio:.1f}× the time ({small_elapsed*1000:.1f}ms small, "
        f"{large_elapsed*1000:.1f}ms large) — check for hidden O(n²)"
    )


# ---------------------------------------------------------------------------
# evaluate_condition: per-condition micro-benchmarks
# ---------------------------------------------------------------------------


def test_evaluate_feature_threshold_meets_perf_budget() -> None:
    """The atomic operation: a single feature_threshold check. Must
    be very cheap — dict lookup + comparison + bool return."""
    condition = {
        "type": "feature_threshold",
        "feature": "max_brake_pressure_lap",
        "comparison": "gt",
        "value": 0.8,
    }
    features = _build_realistic_features()

    iters = 50000
    start = time.perf_counter()
    for _ in range(iters):
        evaluate_condition(condition, features=features)
    elapsed = time.perf_counter() - start

    per_call_us = (elapsed * 1e6) / iters
    # 50µs/call is generous on CI; production should be <5µs.
    assert per_call_us < 50.0, (
        f"evaluate_condition feature_threshold slow: "
        f"{per_call_us:.1f}µs/call for {iters} calls"
    )


def test_evaluate_condition_deeply_nested_still_cheap() -> None:
    """A pathologically deep condition (depth 4 nested AND/OR) must
    still evaluate in microseconds. Catches regressions from naive
    recursion overhead."""
    deep_condition = {
        "type": "and",
        "conditions": [
            {
                "type": "or",
                "conditions": [
                    {
                        "type": "and",
                        "conditions": [
                            {
                                "type": "feature_threshold",
                                "feature": "max_brake_pressure_lap",
                                "comparison": "gt",
                                "value": 0.5,
                            },
                            {
                                "type": "feature_threshold",
                                "feature": "lap_time_s",
                                "comparison": "lt",
                                "value": 200.0,
                            },
                        ],
                    },
                    {
                        "type": "feature_threshold",
                        "feature": "tyre_temp_lf",
                        "comparison": "gt",
                        "value": 50.0,
                    },
                ],
            },
            {
                "type": "feature_threshold",
                "feature": "fuel_per_lap_l",
                "comparison": "lt",
                "value": 10.0,
            },
        ],
    }
    features = _build_realistic_features()

    iters = 20000
    start = time.perf_counter()
    for _ in range(iters):
        evaluate_condition(deep_condition, features=features)
    elapsed = time.perf_counter() - start

    per_call_us = (elapsed * 1e6) / iters
    # Depth-4 condition: 50µs/call CI budget (typical: <10µs).
    assert per_call_us < 50.0, (
        f"deeply nested condition slow: {per_call_us:.1f}µs/call "
        f"for {iters} calls — recursion overhead regression?"
    )


# ---------------------------------------------------------------------------
# Memory: no per-call leak
# ---------------------------------------------------------------------------


def test_evaluate_bundle_does_not_leak_memory() -> None:
    """Steady-state evaluate_bundle calls must not retain memory.
    The output list is the only allocation per call (per docstring);
    anything beyond that indicates accidental cache, memo, or
    closure accumulation."""
    import tracemalloc

    bundle = _build_realistic_bundle(num_rules=30)
    features = _build_realistic_features()

    # Warm up.
    for _ in range(200):
        evaluate_bundle(bundle, features=features)

    tracemalloc.start()
    snap_before = tracemalloc.take_snapshot()

    for _ in range(2000):
        evaluate_bundle(bundle, features=features)

    snap_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    diff = snap_after.compare_to(snap_before, "lineno")
    total_bytes = sum(
        stat.size_diff for stat in diff if stat.size_diff > 0
    )
    total_kb = total_bytes / 1024
    # 200 KB ceiling — easily 10x above expected steady-state delta.
    assert total_kb < 200, (
        f"evaluate_bundle leaked {total_kb:.1f} KB net over 2000 calls "
        f"— possible memoization or closure accumulation"
    )


# ---------------------------------------------------------------------------
# Sanity: realistic bundle produces real insights
# ---------------------------------------------------------------------------


def test_evaluate_bundle_returns_some_insights_on_realistic_data() -> None:
    """If evaluate_bundle silently regressed to returning [] always,
    the perf benchmarks would still pass (empty list is fast). Pin
    that the realistic features fire at least one rule — otherwise
    the perf tests would be measuring a no-op."""
    bundle = _build_realistic_bundle(num_rules=30)
    features = _build_realistic_features()

    insights = evaluate_bundle(bundle, features=features)
    assert isinstance(insights, list)
    assert len(insights) > 0, (
        "realistic bundle + features must fire at least one rule "
        "— otherwise the perf benchmarks measure a no-op"
    )
    # Each insight has a rule_id and payload.
    for insight in insights:
        assert insight.rule_id.startswith("rule-")
        assert "summary" in insight.payload
