"""T081: Rules engine performance benchmark.

DT-010 spec: ``<1ms overhead per sample``. Per ADR-009, live
coaching must compute locally with no server round-trip during
the session, so the rules engine sits on the hot path: the live
processor (T083) will call ``evaluate_bundle`` per lap-end. The
60 Hz sample loop is upstream of that; if a future task ever moves
evaluation per-sample, this benchmark keeps the budget tight.

This isn't a micro-benchmark — it's a regression pin. The threshold
(2 ms median) is double the spec to absorb CI noise without
masking real regressions; if someone adds an expensive op (a
network call, a list copy of a 10k-element feature dict, a
regex compile inside the inner loop), the median doubles and
this test fails.

Why median, not mean: garbage collection bursts and OS scheduling
hiccups make individual samples noisy on Windows / CI. Median over
1000 iterations is robust to those outliers.
"""
from __future__ import annotations

import time
from statistics import median

from lap_coach_logger.coaching.rules_engine import evaluate_bundle, load_bundle


_SPEC_BUDGET_MS = 1.0
"""Per DT-010 spec — published target."""

_TEST_BUDGET_MS = 2.0
"""CI/Windows headroom over the spec — fails on real regressions
(spec doubled), passes through normal noise."""


def _build_synthetic_bundle(rule_count: int) -> dict:
    """Build a bundle approximating the server's eventual size.

    Server target is 80–150 rules per ADR-009. Half of them have
    composite conditions (and/or) to exercise the recursive path.
    Feature names rotate so the inner threshold check actually
    has to look up varied keys, not the same one cached in the
    interpreter's hash table.
    """
    rules: list[dict] = []
    feature_names = [f"f_{i}" for i in range(20)]

    for i in range(rule_count):
        feat = feature_names[i % len(feature_names)]
        leaf = {
            "type": "feature_threshold",
            "feature": feat,
            "comparison": "lt" if i % 2 else "gt",
            "value": 0.5,
        }
        if i % 2 == 0:
            condition = leaf
        else:
            # Half: composite of two leaves with and/or
            other_feat = feature_names[(i + 7) % len(feature_names)]
            other_leaf = {
                "type": "feature_threshold",
                "feature": other_feat,
                "comparison": "gte",
                "value": 0.25,
            }
            op = "and" if i % 4 == 1 else "or"
            condition = {"type": op, "conditions": [leaf, other_leaf]}

        rules.append(
            {
                "id": f"rule.{i}",
                "category": "test",
                "condition": condition,
                "insight": {"title": f"Insight {i}"},
            }
        )

    return {
        "schema_version": "1.0",
        "bundle_id": "rules-perf-test",
        "compiled_at": "2026-04-25T00:00:00Z",
        "rules": rules,
    }


def test_evaluate_bundle_under_1ms_for_100_rules() -> None:
    """Hot-path budget: 100-rule bundle, full feature dict, called
    1000 times. Measure median per-call wall time.

    Why 100 rules: midpoint of the 80–150 target. Why a populated
    feature dict (20 keys): leaves rarely no-fire on missing
    features, exercising the comparison path. A sparse dict would
    give a misleadingly fast number (most leaves bail early)."""
    bundle = load_bundle(_build_synthetic_bundle(rule_count=100))
    features = {f"f_{i}": (i % 10) / 10 for i in range(20)}

    iterations = 1000
    timings_ns: list[int] = [0] * iterations
    for i in range(iterations):
        t0 = time.perf_counter_ns()
        evaluate_bundle(bundle, features=features)
        timings_ns[i] = time.perf_counter_ns() - t0

    median_ns = median(timings_ns)
    median_ms = median_ns / 1_000_000

    assert median_ms < _TEST_BUDGET_MS, (
        f"rules engine median per-call time was {median_ms:.3f} ms, "
        f"budget {_TEST_BUDGET_MS} ms (spec {_SPEC_BUDGET_MS} ms). "
        "If a recent change touches evaluate_bundle / evaluate_condition, "
        "profile to find the regression rather than relaxing the budget."
    )


def test_evaluate_bundle_under_1ms_for_50_rules_with_no_matches() -> None:
    """Worst-case still-cold path: 50 rules, none match (every
    one walks the full condition without early exit on the
    composite). Faster than the 100-rule case, but pinning a
    smaller-bundle datapoint guards against a regression that
    would specifically punish small bundles (e.g., a one-time
    expensive setup in evaluate_bundle's allocator)."""
    bundle = load_bundle(_build_synthetic_bundle(rule_count=50))
    features = {f"f_{i}": 0.999 for i in range(20)}  # nothing matches < 0.5

    iterations = 1000
    timings_ns: list[int] = [0] * iterations
    for i in range(iterations):
        t0 = time.perf_counter_ns()
        evaluate_bundle(bundle, features=features)
        timings_ns[i] = time.perf_counter_ns() - t0

    median_ns = median(timings_ns)
    median_ms = median_ns / 1_000_000

    assert median_ms < _TEST_BUDGET_MS, (
        f"rules engine median per-call time was {median_ms:.3f} ms, "
        f"budget {_TEST_BUDGET_MS} ms (spec {_SPEC_BUDGET_MS} ms)."
    )
