"""T213: Perf profile — memory stable over a 2-hour session.

Sprint target: a 2-hour session must not exhaust process memory.
At 10 Hz that is ~72,000 samples; at 60 Hz ~432,000 samples. The
production cap is ``_MAX_BUFFER_SAMPLES = 500_000`` (~120 MB at
240 bytes/sample), comfortably above either cadence.

Real 2-hour CI test is impossible (slow, flaky, expensive). This
file pins the *underlying memory contracts* that keep the process
bounded:

  - The session-coordinator sample buffer respects the hard cap
    and starts dropping (with a counter) past it.
  - The live-input-diagnostics tracker self-trims to 600 points
    regardless of total samples seen.
  - Per-sample push has no measurable steady-state heap growth
    after the cap saturates.
  - The cap constant exists at module level (drift-prevention —
    catches accidental removal).

To exercise the cap behavior in CI without allocating 500k
samples, the cap is monkey-patched down to a small value so the
contract can be verified in milliseconds.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import lap_coach_logger.core.session_coordinator as coord_mod
from lap_coach_logger.config.models import AppConfig, SessionConfig
from lap_coach_logger.core.live_input_diagnostics import (
    LiveInputDiagnosticsTracker,
)
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.core.session_coordinator import SessionCoordinator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig(output_dir=str(tmp_path), session=SessionConfig())


def _sample(*, idx: int = 0, raw_ts: float = 1.0) -> TelemetrySample:
    """Build a realistic sample carrying enough fields that the
    live trackers process it (otherwise input_diagnostics' point
    builder returns None and the cap behavior never engages)."""
    return TelemetrySample(
        sim="iRacing",
        session_uid="long-session-test",
        session_time_s=float(idx) * 0.1,
        raw_source_timestamp=raw_ts + float(idx),
        speed_kph=120.0 + float(idx % 30),
        throttle_pct=0.6 + float(idx % 5) * 0.05,
        brake_pct=0.0 if idx % 7 else 0.4,
        clutch_pct=1.0,
        steering_deg=float((idx % 20) - 10),
        long_accel_g=0.2,
        lat_accel_g=0.3,
        gear=4,
        rpm=6000.0 + float(idx % 500),
        track_name="Spa",
        car_name="GT3",
        session_type="Practice",
        lap_number=1 + (idx // 60),
        is_on_track=True,
        is_in_pits=False,
    )


# ---------------------------------------------------------------------------
# Sample-buffer cap behavior
# ---------------------------------------------------------------------------


def test_sample_buffer_respects_cap_and_drops_excess(
    tmp_path: Path,
) -> None:
    """The coordinator's sample buffer MUST NOT grow past the cap.
    Past that point, samples are dropped and the counter increments."""
    # Patch the cap down to a small value so we can exercise the
    # full code path without allocating 500k samples.
    SMALL_CAP = 100
    with patch.object(coord_mod, "_MAX_BUFFER_SAMPLES", SMALL_CAP):
        coord = SessionCoordinator(_config(tmp_path))
        # Push 2.5x the cap so we can observe both saturation and
        # the drop counter incrementing.
        for i in range(SMALL_CAP * 2 + 50):
            coord._append_sample(_sample(idx=i), {})

        assert len(coord._buffer) == SMALL_CAP, (
            f"buffer must saturate at cap {SMALL_CAP}, "
            f"got {len(coord._buffer)}"
        )
        # Pushed (SMALL_CAP * 2 + 50) total; first SMALL_CAP filled
        # the buffer, the rest were dropped.
        expected_dropped = SMALL_CAP + 50
        assert coord._dropped_samples == expected_dropped, (
            f"expected {expected_dropped} dropped samples, "
            f"got {coord._dropped_samples}"
        )


def test_max_buffer_constant_exists_and_is_bounded() -> None:
    """Drift-prevention: ``_MAX_BUFFER_SAMPLES`` must remain a
    module-level constant. If it gets renamed or removed, the
    coordinator becomes vulnerable to unbounded growth."""
    assert hasattr(coord_mod, "_MAX_BUFFER_SAMPLES")
    cap = coord_mod._MAX_BUFFER_SAMPLES
    assert isinstance(cap, int)
    # Sanity: cap must be at least 1 minute at 60 Hz (3,600 samples)
    # — anything less would limit short sessions, which is wrong.
    # Upper bound: 10 million samples (way above any realistic
    # session) — anything more suggests the cap has been removed.
    assert 3_600 <= cap <= 10_000_000, (
        f"_MAX_BUFFER_SAMPLES out of sane range: {cap}"
    )


def test_buffer_does_not_grow_after_saturation(tmp_path: Path) -> None:
    """Once saturated, EVERY additional push must NOT grow the
    buffer — the only growth allowed is in dropped_samples."""
    SMALL_CAP = 50
    with patch.object(coord_mod, "_MAX_BUFFER_SAMPLES", SMALL_CAP):
        coord = SessionCoordinator(_config(tmp_path))
        # Saturate.
        for i in range(SMALL_CAP):
            coord._append_sample(_sample(idx=i), {})
        assert len(coord._buffer) == SMALL_CAP

        # Push 1000 more — buffer length must stay flat.
        for i in range(SMALL_CAP, SMALL_CAP + 1000):
            coord._append_sample(_sample(idx=i), {})
            assert len(coord._buffer) == SMALL_CAP, (
                f"buffer grew past cap at iteration {i}: "
                f"len={len(coord._buffer)}"
            )


# ---------------------------------------------------------------------------
# Live-input-diagnostics tracker bounded-state contract
# ---------------------------------------------------------------------------


def test_live_input_diagnostics_self_trims_to_600_points() -> None:
    """The live tracker self-trims to its bounded window. Without
    this cap, a long session would accumulate per-sample state
    forever even though only the last few seconds are useful."""
    tracker = LiveInputDiagnosticsTracker()
    tracker.reset(session_uid="long-session")

    # Push 5000 samples spanning several minutes of session time.
    # _build_point requires at least 0.02s spacing between points
    # to dedupe — so use 0.1s spacing.
    for i in range(5000):
        s = _sample(idx=i)
        # Override session_time_s spacing to 0.1s to bypass the
        # 20ms dedupe filter.
        s = TelemetrySample(
            **{**s.to_dict(), "session_time_s": float(i) * 0.1}
        )
        # Ensure session_uid matches so tracker doesn't reset.
        s = TelemetrySample(
            **{**s.to_dict(), "session_uid": "long-session"}
        )
        tracker.push_sample(s)

    # Tracker must self-trim — internal points buffer ≤ 600.
    assert len(tracker._points) <= 600, (
        f"live diagnostics tracker did not self-trim: "
        f"{len(tracker._points)} points (cap 600)"
    )


def test_live_input_diagnostics_resets_on_session_change() -> None:
    """When the session UID changes (new session start) the
    tracker resets — old session's accumulator must not bleed
    into the new session's metrics."""
    tracker = LiveInputDiagnosticsTracker()

    # Session A: push 100 samples.
    for i in range(100):
        s = _sample(idx=i)
        s = TelemetrySample(**{
            **s.to_dict(),
            "session_uid": "session-A",
            "session_time_s": float(i) * 0.1,
        })
        tracker.push_sample(s)
    a_count = len(tracker._points)

    # Session B starts: first sample with new uid resets state.
    s = _sample(idx=0)
    s = TelemetrySample(**{
        **s.to_dict(),
        "session_uid": "session-B",
        "session_time_s": 0.0,
    })
    tracker.push_sample(s)

    # New session should have at most 1 point (the one we just pushed).
    assert len(tracker._points) <= 1, (
        f"session change did not reset live diagnostics: "
        f"{len(tracker._points)} points after session reset (had {a_count} before)"
    )


# ---------------------------------------------------------------------------
# Steady-state memory: no leak past saturation
# ---------------------------------------------------------------------------


def test_buffer_at_cap_no_per_sample_heap_growth(tmp_path: Path) -> None:
    """At-cap steady state: each rejected sample must NOT leak.
    The reject path increments a counter and returns; nothing
    else should accumulate."""
    import tracemalloc

    SMALL_CAP = 100
    with patch.object(coord_mod, "_MAX_BUFFER_SAMPLES", SMALL_CAP):
        coord = SessionCoordinator(_config(tmp_path))

        # Saturate buffer first.
        for i in range(SMALL_CAP):
            coord._append_sample(_sample(idx=i), {})

        # Warm up — first reject calls may pre-allocate logging.
        for i in range(200):
            coord._append_sample(_sample(idx=i + SMALL_CAP), {})

        tracemalloc.start()
        snap_before = tracemalloc.take_snapshot()

        # Steady state: 5000 samples all rejected.
        for i in range(5000):
            coord._append_sample(_sample(idx=i + SMALL_CAP + 200), {})

        snap_after = tracemalloc.take_snapshot()
        tracemalloc.stop()

        diff = snap_after.compare_to(snap_before, "lineno")
        total_bytes = sum(
            stat.size_diff for stat in diff if stat.size_diff > 0
        )
        total_kb = total_bytes / 1024

        # 5000 rejected samples must not grow past a small budget.
        # 500 KB ceiling — generous for log-related allocations
        # (the reject path logs every 1000 dropped samples).
        assert total_kb < 500, (
            f"buffer at cap leaked {total_kb:.1f} KB net over 5000 "
            f"rejected pushes — possible per-reject allocation"
        )


# ---------------------------------------------------------------------------
# 2h scaled simulation: bounded buffer growth
# ---------------------------------------------------------------------------


def test_simulated_long_session_buffer_stays_at_cap(
    tmp_path: Path,
) -> None:
    """Simulate a long session by pushing more samples than the
    (patched-down) cap, then assert the buffer plateau holds for
    sustained pushes — the canonical 'long session' contract."""
    SMALL_CAP = 200
    with patch.object(coord_mod, "_MAX_BUFFER_SAMPLES", SMALL_CAP):
        coord = SessionCoordinator(_config(tmp_path))

        # Simulate ~10x the cap over a long stream.
        TOTAL = SMALL_CAP * 10
        for i in range(TOTAL):
            coord._append_sample(_sample(idx=i), {})

        # Buffer plateaued at cap.
        assert len(coord._buffer) == SMALL_CAP
        # Drop counter shows the rest were rejected.
        assert coord._dropped_samples == TOTAL - SMALL_CAP, (
            f"expected {TOTAL - SMALL_CAP} dropped, "
            f"got {coord._dropped_samples}"
        )
