"""T082: Thread-safe insight queue between rules engine and VM.

The rules engine runs on the sample thread (T083 — driven at the
simulator's tick rate, typically 60 Hz). The overlay VM (T091)
runs on Qt's main thread. Insights need to cross between them
without:

- Blocking the sample thread on a UI-thread mutex (would jitter
  the next sample read).
- Allocating shared mutable state (would bypass Qt's
  cross-thread safety contract).

T082 ships :class:`InsightQueue` — a thin wrapper around
:mod:`queue.Queue` that exposes only the two operations the
boundary actually uses (publish list, drain to list). The
``Queue`` underneath is thread-safe by construction (CPython
guarantees this for ``put`` and ``get_nowait``) so all this layer
adds is the engine-shaped API + a stdlib-only dependency.

Why a wrapper at all (and not raw ``queue.Queue``):
- ``put_nowait`` raises ``queue.Full`` — at the rules-engine
  boundary that's a programmer bug (we configure it unbounded);
  the wrapper hides that distinction.
- ``get_nowait`` raises ``queue.Empty`` — drain wants the
  empty-list shape, not an exception.
- T091's overlay VM stays decoupled from ``queue`` import — the
  threading mechanism becomes implementation detail.
"""
from __future__ import annotations

import threading
import time

import pytest

from lap_coach_logger.coaching.rules_engine import (
    CoachingInsight,
    InsightQueue,
)


def _make_insight(rule_id: str) -> CoachingInsight:
    return CoachingInsight(rule_id=rule_id, payload={"title": rule_id})


# ---------------------------------------------------------------------------
# Same-thread basic API
# ---------------------------------------------------------------------------


def test_drain_returns_empty_list_when_nothing_published() -> None:
    """Empty queue ⇒ ``[]`` (not ``None``, not raise) so the VM's
    polling loop doesn't have to special-case "first poll"."""
    q = InsightQueue()

    assert q.drain() == []


def test_publish_then_drain_returns_published_insights_in_order() -> None:
    """FIFO order — the engine publishes in bundle order (T080)
    and the VM expects to consume in priority order. Reordering
    here would break T091's deterministic display."""
    q = InsightQueue()

    q.publish([_make_insight("br.late"), _make_insight("ac.apex_loss")])

    assert [i.rule_id for i in q.drain()] == ["br.late", "ac.apex_loss"]


def test_drain_empties_the_queue() -> None:
    """A second drain after the first must return ``[]`` — the
    VM "consumes" insights once. Without this, T092's cooldown
    logic would fire on stale insights every poll cycle."""
    q = InsightQueue()
    q.publish([_make_insight("br.late")])
    q.drain()

    assert q.drain() == []


def test_multiple_publishes_accumulate_until_drain() -> None:
    """Three lap-ends fire before the VM's next poll — all six
    insights must reach the VM in the next drain. Otherwise
    insights from the in-between laps would silently disappear."""
    q = InsightQueue()
    q.publish([_make_insight("a"), _make_insight("b")])
    q.publish([_make_insight("c"), _make_insight("d")])
    q.publish([_make_insight("e"), _make_insight("f")])

    assert [i.rule_id for i in q.drain()] == ["a", "b", "c", "d", "e", "f"]


def test_publish_empty_list_is_a_noop() -> None:
    """A lap with no firing rules calls ``publish([])`` — must
    not raise, must not deposit anything in the queue."""
    q = InsightQueue()
    q.publish([])

    assert q.drain() == []


# ---------------------------------------------------------------------------
# Cross-thread: producer / consumer pattern
# ---------------------------------------------------------------------------


def test_insights_published_on_one_thread_are_drained_on_another() -> None:
    """The whole point of the queue: producer (sample) thread →
    consumer (VM) thread. Without this guarantee, insights
    crossing the thread boundary would race on shared state."""
    q = InsightQueue()
    expected_ids = [f"rule.{i}" for i in range(50)]

    def producer() -> None:
        for rule_id in expected_ids:
            q.publish([_make_insight(rule_id)])

    producer_thread = threading.Thread(target=producer)
    producer_thread.start()
    producer_thread.join()

    drained = q.drain()
    assert [i.rule_id for i in drained] == expected_ids


def test_concurrent_producers_dont_lose_insights() -> None:
    """Two sample-thread variants (e.g., a feature stream and a
    backup sensor stream) publishing simultaneously. Total count
    must equal sum of producers — no drops, no duplicates."""
    q = InsightQueue()
    per_producer = 100
    n_producers = 4

    def producer(prefix: str) -> None:
        for i in range(per_producer):
            q.publish([_make_insight(f"{prefix}.{i}")])

    threads = [
        threading.Thread(target=producer, args=(f"p{p}",))
        for p in range(n_producers)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    drained = q.drain()
    assert len(drained) == per_producer * n_producers
    # rule_ids must all be unique — no duplications from data races
    assert len({i.rule_id for i in drained}) == per_producer * n_producers


def test_concurrent_publish_and_drain_eventually_consumes_all() -> None:
    """VM polls while producer is still publishing — across many
    drain cycles, every published insight must eventually reach
    the consumer. Pinning this guards against a partial-drain bug
    where the consumer takes some but not all of what's pending."""
    q = InsightQueue()
    n_to_publish = 500
    drained_so_far: list[CoachingInsight] = []
    producer_done = threading.Event()

    def producer() -> None:
        for i in range(n_to_publish):
            q.publish([_make_insight(f"rule.{i}")])
        producer_done.set()

    producer_thread = threading.Thread(target=producer)
    producer_thread.start()

    # Mimic VM polling: drain repeatedly with tiny pauses
    deadline = time.monotonic() + 5.0  # generous; producer is fast
    while time.monotonic() < deadline:
        drained_so_far.extend(q.drain())
        if producer_done.is_set() and len(drained_so_far) == n_to_publish:
            break
        time.sleep(0.001)

    producer_thread.join()
    drained_so_far.extend(q.drain())  # final sweep

    assert len(drained_so_far) == n_to_publish
    assert {i.rule_id for i in drained_so_far} == {
        f"rule.{i}" for i in range(n_to_publish)
    }
