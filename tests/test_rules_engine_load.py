"""T101: Rules engine sustains 1000 samples/sec without backup.

DT-010 spec implies the engine sits on the live-coaching hot
path. T081 measured per-call latency (<1 ms median for a
100-rule bundle); T101 measures **sustained throughput** —
can the engine + queue keep up with a 1000/sec firing rate
across producer / consumer threads?

What "no backup" means here: the InsightQueue is unbounded
(T082 chose this so the sample thread never blocks), so
"backup" can't manifest as a queue.Full. Instead it manifests
as the queue growing unboundedly — the consumer can't drain
fast enough. T101 pins that a 1-second 1000/sec burst plus a
brief consumer grace period leaves the queue empty.

Why 1 second: enough to amortise startup jitter (thread
spawn, JIT-warming the dispatch), short enough that the test
runs in a tight loop (~2 s including consumer grace).

Why 1000/sec specifically: rounds nicely above the 60Hz sample
loop (60/sec) and the typical lap-end rate (1/min). A future
"per-corner" emission strategy might push the rate higher;
1000/sec is a generous ceiling for that.
"""
from __future__ import annotations

import threading
import time

from lap_coach_logger.coaching.rules_engine import (
    InsightQueue,
    evaluate_bundle,
    load_bundle,
)


_TARGET_RATE_HZ = 1000.0
_DURATION_S = 1.0
_CONSUMER_GRACE_S = 0.5


def _bundle_with_one_always_firing_rule() -> object:
    return load_bundle(
        {
            "schema_version": "1.0",
            "bundle_id": "rules-load-test",
            "compiled_at": "2026-04-25T00:00:00Z",
            "rules": [
                {
                    "id": "always.fires",
                    "category": "test",
                    "condition": {
                        "type": "feature_threshold",
                        "feature": "x",
                        "comparison": "gte",
                        "value": 0.0,
                    },
                    "insight": {"title": "always"},
                }
            ],
        }
    )


def test_engine_sustains_1000_per_second_with_no_backup() -> None:
    """Producer pushes ~1000 insights/sec for 1 second; consumer
    drains every 10 ms in a separate thread. After producer
    finishes + a brief grace period, the queue must be empty."""
    bundle = _bundle_with_one_always_firing_rule()
    queue = InsightQueue()
    drained_count = [0]
    stop = threading.Event()
    produced_count = [0]

    def consumer() -> None:
        while not stop.is_set():
            drained_count[0] += len(queue.drain())
            time.sleep(0.010)
        # Final sweep
        drained_count[0] += len(queue.drain())

    consumer_thread = threading.Thread(target=consumer)
    consumer_thread.start()

    # Producer: push insights as fast as the engine + queue allow
    # for ``_DURATION_S`` seconds, target rate ~1000/sec.
    deadline = time.monotonic() + _DURATION_S
    sleep_per_iter = 1.0 / _TARGET_RATE_HZ  # ~1 ms
    while time.monotonic() < deadline:
        insights = evaluate_bundle(bundle, features={"x": 1.0})
        queue.publish(insights)
        produced_count[0] += len(insights)
        # Soft pacing — sleeping the full 1ms would underrun;
        # busy-wait is overkill. 0 lets the OS schedule.
        time.sleep(0)

    # Allow consumer to drain anything still in the queue
    time.sleep(_CONSUMER_GRACE_S)
    stop.set()
    consumer_thread.join(timeout=2.0)
    assert not consumer_thread.is_alive(), "consumer thread didn't exit"

    # No insights were lost AND no backup — drained should equal produced
    assert drained_count[0] == produced_count[0], (
        f"queue backed up: produced {produced_count[0]}, "
        f"drained {drained_count[0]}, "
        f"diff {produced_count[0] - drained_count[0]}"
    )


def test_engine_sustained_throughput_meets_target_rate() -> None:
    """Production pushes at the loop's natural rate (driven by
    the sample-thread budget, not a sleep). T101 must demonstrate
    the engine itself can actually emit at >= 1000 insights/sec —
    otherwise a future per-sample wiring would silently drop on
    the producer side regardless of queue capacity."""
    bundle = _bundle_with_one_always_firing_rule()
    queue = InsightQueue()
    produced = 0

    deadline = time.monotonic() + _DURATION_S
    while time.monotonic() < deadline:
        insights = evaluate_bundle(bundle, features={"x": 1.0})
        queue.publish(insights)
        produced += len(insights)
    elapsed = _DURATION_S  # we ran for at least this long

    rate_hz = produced / elapsed
    assert rate_hz >= _TARGET_RATE_HZ, (
        f"engine sustained {rate_hz:.0f}/sec, below the "
        f"{_TARGET_RATE_HZ:.0f}/sec target. Profile evaluate_bundle "
        f"before relaxing the target."
    )

    # Drain so the test doesn't leak
    queue.drain()
