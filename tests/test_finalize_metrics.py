"""T225: Analytics — session-finalization success rate metric.

Pins the metric primitives so we can answer "how often does
session finalization succeed?" — a critical health signal: a
crashed save means the user just lost their lap data.

Contract:

  - ``record_success()`` and ``record_failure()`` accumulate
    counters across a process run
  - ``success_rate()`` returns the fraction successes /
    (successes + failures), or ``None`` when no calls have been
    recorded (avoids a meaningless 0/0 reading on idle launches)
  - ``snapshot()`` returns a dict suitable for shipping to
    PostHog or logging at exit, with the three primitives any
    chart needs: success_count, failure_count, total
  - ``reset()`` zeroes the counters (for tests AND for the
    "stats reset" entry point in Settings — out of scope here)

The metric is *computed* in the sense that the primitive exists
and is correct. Wiring SessionFinalizer to bump the counters on
each finalize() call is a follow-up (small change, but it
crosses module boundaries and deserves its own test).
"""
from __future__ import annotations

import pytest

from lap_coach_logger.analytics import finalize_metrics as fm


@pytest.fixture(autouse=True)
def _clean_state() -> None:
    """Reset module-level counters so tests don't leak."""
    fm.reset()
    yield
    fm.reset()


# ---------------------------------------------------------------------------
# success_rate edge cases
# ---------------------------------------------------------------------------


def test_success_rate_is_none_with_no_data() -> None:
    """0 / 0 is undefined — return None so dashboards can skip
    plotting rather than show a misleading 0%."""
    assert fm.success_rate() is None


def test_success_rate_is_one_when_only_successes() -> None:
    fm.record_success()
    assert fm.success_rate() == 1.0


def test_success_rate_is_zero_when_only_failures() -> None:
    fm.record_failure()
    assert fm.success_rate() == 0.0


def test_success_rate_is_half_when_one_each() -> None:
    fm.record_success()
    fm.record_failure()
    assert fm.success_rate() == 0.5


def test_success_rate_accumulates_across_calls() -> None:
    """3 / (3+1) = 0.75 — the metric must accumulate, not just
    track the most recent call."""
    for _ in range(3):
        fm.record_success()
    fm.record_failure()
    assert fm.success_rate() == 0.75


# ---------------------------------------------------------------------------
# Counter primitives
# ---------------------------------------------------------------------------


def test_record_success_increments_success_count() -> None:
    fm.record_success()
    fm.record_success()
    snap = fm.snapshot()
    assert snap["success_count"] == 2


def test_record_failure_increments_failure_count() -> None:
    fm.record_failure()
    fm.record_failure()
    fm.record_failure()
    snap = fm.snapshot()
    assert snap["failure_count"] == 3


def test_total_is_sum_of_success_and_failure() -> None:
    """``total`` is what dashboards plot on the X-axis (sample
    size). Must equal successes + failures, never desynced."""
    fm.record_success()
    fm.record_failure()
    fm.record_failure()
    snap = fm.snapshot()
    assert snap["total"] == 3
    assert snap["total"] == snap["success_count"] + snap["failure_count"]


# ---------------------------------------------------------------------------
# snapshot()
# ---------------------------------------------------------------------------


def test_snapshot_includes_success_rate() -> None:
    """The snapshot is the canonical PostHog payload — must
    bundle the rate alongside the raw counts so downstream
    queries don't have to recompute it."""
    fm.record_success()
    fm.record_failure()
    snap = fm.snapshot()
    assert snap["success_rate"] == 0.5


def test_snapshot_success_rate_is_none_when_no_data() -> None:
    """A snapshot with zero observations must signal that
    explicitly so analytics dashboards drop the row rather than
    plot a 0% rate from no data."""
    snap = fm.snapshot()
    assert snap["success_rate"] is None
    assert snap["total"] == 0


def test_snapshot_keys_are_stable() -> None:
    """The PostHog event schema is a public contract — pin the
    key set so a rename doesn't silently break dashboards."""
    snap = fm.snapshot()
    expected_keys = {"success_count", "failure_count", "total", "success_rate"}
    assert set(snap.keys()) == expected_keys


# ---------------------------------------------------------------------------
# reset()
# ---------------------------------------------------------------------------


def test_reset_zeroes_both_counters() -> None:
    """``reset`` is the test-isolation primitive — must clear
    BOTH counters, not just one (caught a real bug once)."""
    fm.record_success()
    fm.record_failure()
    fm.reset()
    snap = fm.snapshot()
    assert snap["success_count"] == 0
    assert snap["failure_count"] == 0
    assert snap["total"] == 0
    assert snap["success_rate"] is None
