"""T102: Rules engine memory residue stays < 100 MB across a
session-equivalent workload.

A 2-hour session is the spec window: roughly 120 laps (1/min)
or 432 000 samples (60 Hz). The engine itself runs at lap-end
(120 calls), but the emit_lap_insights → InsightQueue → VM
poll path passes ALL fired insights through. T102 simulates
that full path and bounds the memory residue.

Why 100 MB: low enough that the engine + queue can run on a
modest gaming PC without crowding the simulator's working set,
generous enough that natural CPython overhead (interned strings,
allocator pages) doesn't trip the threshold. The CoachingInsight
dataclass is small (rule_id str + payload dict), so 100 MB
budget covers ~500 000+ insights' worth of allocation.

What "residue" means here: peak allocation during the run minus
baseline allocation before the run, measured with stdlib
``tracemalloc``. Captures BOTH transient peaks (e.g., a queue
that briefly buffers 10k insights) and persistent leaks (e.g.,
a filter that accumulates per-rule state without bound).

We don't simulate the full 2 h wall-time — too slow for CI.
Instead we run an equivalent **work volume** (120 lap-equivalent
emit cycles + drain cycles) which exercises the same code paths
the real session would.
"""
from __future__ import annotations

import gc
import tracemalloc

from lap_coach_logger.coaching.rules_engine import (
    CorroborationGate,
    InsightCooldownFilter,
    InsightQueue,
    evaluate_bundle,
    load_bundle,
)


_MEMORY_BUDGET_BYTES = 100 * 1024 * 1024  # 100 MiB


def _build_session_bundle(rule_count: int = 50) -> object:
    """Mirror T081's perf bundle — 50 rules, half composite, so
    the memory profile sees realistic dispatch."""
    feature_names = [f"f_{i}" for i in range(20)]
    rules: list[dict] = []
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
            condition = {
                "type": "and",
                "conditions": [
                    leaf,
                    {
                        "type": "feature_threshold",
                        "feature": feature_names[(i + 7) % len(feature_names)],
                        "comparison": "gte",
                        "value": 0.25,
                    },
                ],
            }
        rules.append(
            {
                "id": f"rule.{i}",
                "category": "test",
                "condition": condition,
                "insight": {
                    "title": f"Insight {i}",
                    "rationale": "Some explanatory text the user reads.",
                    "skill_levels": {
                        "beginner": "Beginner-friendly variant.",
                        "intermediate": "Intermediate variant.",
                        "advanced": "Advanced variant.",
                    },
                },
            }
        )
    return load_bundle(
        {
            "schema_version": "1.0",
            "bundle_id": "rules-memory-test",
            "compiled_at": "2026-04-25T00:00:00Z",
            "rules": rules,
        }
    )


def test_rules_engine_2h_workload_under_100mb_residue() -> None:
    """Run a 2 h equivalent workload through the full pipeline
    (engine + corroboration + queue + cooldown) and assert peak
    memory delta stays under 100 MB.

    The workload pattern matches a real session:
    - 120 lap-end emit cycles (≈ 2 h at 1 lap/min)
    - features dict regenerated each cycle (mimics fresh
      lap-end stats)
    - corroboration + cooldown both wired (fully composed
      pipeline, not just evaluate_bundle in isolation)
    - VM-style drain after every cycle so the queue doesn't
      grow as a side effect of "no consumer"
    """
    bundle = _build_session_bundle(rule_count=50)
    queue = InsightQueue()
    gate = CorroborationGate(bundle)
    cooldown = InsightCooldownFilter(cooldown_seconds=30.0)

    gc.collect()
    tracemalloc.start()
    try:
        baseline_current, _ = tracemalloc.get_traced_memory()

        for lap_index in range(120):
            features = {f"f_{i}": (lap_index + i) / 100.0 for i in range(20)}
            insights = evaluate_bundle(bundle, features=features)
            insights = gate.process(insights)
            insights = cooldown.filter(insights)
            queue.publish(insights)
            queue.drain()  # consumer keeps up

        _, peak = tracemalloc.get_traced_memory()
        residue = peak - baseline_current
    finally:
        tracemalloc.stop()

    assert residue < _MEMORY_BUDGET_BYTES, (
        f"rules engine peak memory residue was "
        f"{residue / 1024 / 1024:.1f} MiB, "
        f"budget {_MEMORY_BUDGET_BYTES / 1024 / 1024:.0f} MiB. "
        f"Investigate which component (gate state, cooldown "
        f"timestamps, queue, bundle) is leaking before "
        f"relaxing the budget."
    )


def test_corroboration_gate_state_stays_bounded() -> None:
    """Specific drill-down: the gate keeps a per-rule consec-fire
    counter. After many cycles, the counter dict's size should
    stay equal to the number of rules — never grow with cycle
    count. Without this, a misindexed insight (unknown rule_id)
    could pollute the dict and grow it forever."""
    bundle = _build_session_bundle(rule_count=50)
    gate = CorroborationGate(bundle)

    # Run many cycles; gate's internal state should plateau at 50.
    for cycle in range(1000):
        features = {f"f_{i}": (cycle + i) / 1000.0 for i in range(20)}
        insights = evaluate_bundle(bundle, features=features)
        gate.process(insights)

    # _consec_fires + _min_laps_by_rule are the two state dicts.
    # Both should have at most one entry per known rule (50).
    consec_size = len(gate._consec_fires)  # noqa: SLF001
    min_laps_size = len(gate._min_laps_by_rule)  # noqa: SLF001
    assert consec_size == 50
    assert min_laps_size == 50


def test_cooldown_filter_state_stays_bounded() -> None:
    """The cooldown filter keeps a per-rule timestamp dict. It
    grows only as new rules pass the filter for the first time.
    A 50-rule bundle's worst case is 50 entries — never more,
    regardless of how many cycles run."""
    bundle = _build_session_bundle(rule_count=50)
    cooldown = InsightCooldownFilter(cooldown_seconds=30.0)

    for cycle in range(1000):
        features = {f"f_{i}": (cycle + i) / 1000.0 for i in range(20)}
        insights = evaluate_bundle(bundle, features=features)
        cooldown.filter(insights)

    last_shown_size = len(cooldown._last_shown_at)  # noqa: SLF001
    assert last_shown_size <= 50
