"""T209: Integration test — freeze detection trips on stalled sim.

Pins the recording-loop's data-freeze contract over realistic
sample sequences:

  1. Healthy stream (changing raw_source_timestamp every sample)
     never trips the freeze detector.
  2. Stalled sim (sample stream where raw_source_timestamp stops
     incrementing) trips the detector after the configured
     ``data_freeze_timeout_s`` has elapsed.
  3. Brief stalls that resolve before the timeout do NOT trip the
     detector — the same raw_ts arriving again and then a fresh
     value resets the watcher.
  4. Multiple stalls within one session each independently trip
     the detector (state correctly resets after recovery).

The existing unit tests in test_session_coordinator.py cover the
``_is_data_frozen`` boolean returns at unit level (1-2 samples).
T209 covers the *sequence* behavior over a longer-running stream
— mirrors what the actual recording loop sees.

Tests use real ``time.sleep`` with a small (50 ms) timeout to
keep wall-clock fast. Patching ``time.monotonic`` would be more
deterministic but would couple to internal implementation; the
sleep-based pattern matches the existing freeze tests.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from lap_coach_logger.config.models import AppConfig, SessionConfig
from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.core.session_coordinator import SessionCoordinator


# Match the existing freeze tests — short enough to keep wall-clock
# fast but long enough to be reliable on CI.
_FREEZE_TIMEOUT_S = 0.05
_FREEZE_OVERSHOOT_S = 0.07  # > _FREEZE_TIMEOUT_S


def _config(tmp_path: Path, **session_overrides) -> AppConfig:
    scfg = SessionConfig(**session_overrides)
    return AppConfig(output_dir=str(tmp_path), session=scfg)


def _sample(*, raw_ts: float | None = 1.0) -> TelemetrySample:
    return TelemetrySample(
        sim="iRacing",
        session_uid="freeze-int",
        raw_source_timestamp=raw_ts,
        speed_kph=100.0,
        track_name="Test",
        car_name="Test",
        session_type="Practice",
    )


# -- healthy stream never trips ------------------------------------


def test_changing_raw_ts_stream_never_trips(tmp_path: Path) -> None:
    """A stream where every sample carries a fresh raw_source_timestamp
    — typical of a live sim — must never trip the freeze detector,
    even with a tight 50 ms timeout and many samples."""
    coord = SessionCoordinator(
        _config(tmp_path, data_freeze_timeout_s=_FREEZE_TIMEOUT_S),
    )
    for tick in range(20):
        sample = _sample(raw_ts=float(tick))
        assert coord._is_data_frozen(sample, _FREEZE_TIMEOUT_S) is False, (
            f"healthy stream tripped freeze detector at tick {tick}"
        )


def test_long_changing_stream_with_realistic_pace(tmp_path: Path) -> None:
    """Simulate ~5 ms of real wall-clock between samples — still no
    freeze trip because raw_ts keeps advancing."""
    coord = SessionCoordinator(
        _config(tmp_path, data_freeze_timeout_s=_FREEZE_TIMEOUT_S),
    )
    for tick in range(8):
        sample = _sample(raw_ts=float(tick))
        assert coord._is_data_frozen(
            sample, _FREEZE_TIMEOUT_S,
        ) is False
        time.sleep(0.005)


# -- stall → trip --------------------------------------------------


def test_stalled_stream_trips_after_timeout(tmp_path: Path) -> None:
    """The canonical stall: 3 healthy samples, then sim freezes —
    same raw_ts comes back. After the timeout elapses, the next
    same-raw_ts sample MUST trip the detector."""
    coord = SessionCoordinator(
        _config(tmp_path, data_freeze_timeout_s=_FREEZE_TIMEOUT_S),
    )
    # Healthy phase.
    for tick in range(3):
        coord._is_data_frozen(_sample(raw_ts=float(tick)), _FREEZE_TIMEOUT_S)

    # Stall: same raw_ts (3.0) repeated.
    coord._is_data_frozen(_sample(raw_ts=3.0), _FREEZE_TIMEOUT_S)
    # Within timeout — no trip yet.
    assert coord._is_data_frozen(
        _sample(raw_ts=3.0), _FREEZE_TIMEOUT_S,
    ) is False

    # Past timeout — trip.
    time.sleep(_FREEZE_OVERSHOOT_S)
    assert coord._is_data_frozen(
        _sample(raw_ts=3.0), _FREEZE_TIMEOUT_S,
    ) is True, "freeze detector did not trip after timeout"


def test_stalled_stream_does_not_trip_before_timeout(
    tmp_path: Path,
) -> None:
    """Repeated same-raw_ts samples within the timeout window must
    NOT trip — only when the wall-clock window elapses."""
    coord = SessionCoordinator(
        _config(tmp_path, data_freeze_timeout_s=_FREEZE_TIMEOUT_S),
    )
    coord._is_data_frozen(_sample(raw_ts=1.0), _FREEZE_TIMEOUT_S)
    # 5 rapid-fire same-raw_ts calls within ~25 ms — under 50 ms.
    for _ in range(5):
        assert coord._is_data_frozen(
            _sample(raw_ts=1.0), _FREEZE_TIMEOUT_S,
        ) is False
        time.sleep(0.005)


# -- recovery (brief stall, then fresh raw_ts) --------------------


def test_brief_stall_then_recovery_never_trips(tmp_path: Path) -> None:
    """Sim publishes a duplicate raw_ts (e.g., adapter polled faster
    than the SDK published) but immediately recovers with a fresh
    one before the timeout. Detector must NOT trip."""
    coord = SessionCoordinator(
        _config(tmp_path, data_freeze_timeout_s=_FREEZE_TIMEOUT_S),
    )
    coord._is_data_frozen(_sample(raw_ts=1.0), _FREEZE_TIMEOUT_S)
    # Brief stall: same raw_ts twice in a row.
    assert coord._is_data_frozen(
        _sample(raw_ts=1.0), _FREEZE_TIMEOUT_S,
    ) is False
    time.sleep(0.02)  # under timeout
    # Recovery: fresh raw_ts.
    assert coord._is_data_frozen(
        _sample(raw_ts=2.0), _FREEZE_TIMEOUT_S,
    ) is False
    # Continued stream stays healthy.
    time.sleep(_FREEZE_OVERSHOOT_S)
    assert coord._is_data_frozen(
        _sample(raw_ts=3.0), _FREEZE_TIMEOUT_S,
    ) is False


# -- recurrence: multiple stalls in one session -------------------


def test_recovery_resets_freeze_tracker(tmp_path: Path) -> None:
    """After a recovery (fresh raw_ts), a NEW stall must restart
    the freeze countdown from zero — otherwise a tiny stall after
    a previous near-miss would trip incorrectly."""
    coord = SessionCoordinator(
        _config(tmp_path, data_freeze_timeout_s=_FREEZE_TIMEOUT_S),
    )

    # Phase 1: stall almost to timeout, then recover.
    coord._is_data_frozen(_sample(raw_ts=1.0), _FREEZE_TIMEOUT_S)
    time.sleep(0.04)  # almost timeout
    coord._is_data_frozen(_sample(raw_ts=2.0), _FREEZE_TIMEOUT_S)  # recovery

    # Phase 2: tiny stall right after recovery — must NOT trip.
    coord._is_data_frozen(_sample(raw_ts=2.0), _FREEZE_TIMEOUT_S)
    time.sleep(0.02)
    assert coord._is_data_frozen(
        _sample(raw_ts=2.0), _FREEZE_TIMEOUT_S,
    ) is False, "recovery did not reset the freeze countdown"


def test_second_stall_in_same_session_trips(tmp_path: Path) -> None:
    """Two distinct stalls in one session — each independently
    times out. The session machine relies on this to handle sims
    that briefly stall, recover, then stall again terminally."""
    coord = SessionCoordinator(
        _config(tmp_path, data_freeze_timeout_s=_FREEZE_TIMEOUT_S),
    )

    # Stall 1: trip.
    coord._is_data_frozen(_sample(raw_ts=1.0), _FREEZE_TIMEOUT_S)
    time.sleep(_FREEZE_OVERSHOOT_S)
    assert coord._is_data_frozen(
        _sample(raw_ts=1.0), _FREEZE_TIMEOUT_S,
    ) is True

    # Recovery — fresh raw_ts resets the tracker.
    assert coord._is_data_frozen(
        _sample(raw_ts=2.0), _FREEZE_TIMEOUT_S,
    ) is False

    # Stall 2: must trip independently.
    time.sleep(_FREEZE_OVERSHOOT_S)
    assert coord._is_data_frozen(
        _sample(raw_ts=2.0), _FREEZE_TIMEOUT_S,
    ) is True, "second stall in same session did not trip"


# -- raw_ts None edge cases --------------------------------------


def test_first_sample_alone_never_trips(tmp_path: Path) -> None:
    """A single sample by itself can't possibly be 'frozen' — there's
    no prior raw_ts to compare against. Even after a long wait, the
    detector must return False on the first call."""
    coord = SessionCoordinator(
        _config(tmp_path, data_freeze_timeout_s=_FREEZE_TIMEOUT_S),
    )
    sample = _sample(raw_ts=1.0)
    # First call captures raw_ts → never trips.
    assert coord._is_data_frozen(sample, _FREEZE_TIMEOUT_S) is False
    time.sleep(_FREEZE_OVERSHOOT_S)
    # Wait elapsed but only one prior call → second call NOW could
    # trip. That's expected (this matches the spec). The 'first
    # sample alone' contract: the first call must return False
    # regardless of any prior wall-clock state.


def test_none_raw_ts_never_trips(tmp_path: Path) -> None:
    """Samples with raw_source_timestamp=None can't be checked for
    freeze (no signal). Detector must return False without raising,
    not even when the previous sample had a valid raw_ts."""
    coord = SessionCoordinator(
        _config(tmp_path, data_freeze_timeout_s=_FREEZE_TIMEOUT_S),
    )
    coord._is_data_frozen(_sample(raw_ts=1.0), _FREEZE_TIMEOUT_S)
    # Now feed a None — must not trip, must not raise.
    none_sample = _sample(raw_ts=None)
    assert coord._is_data_frozen(none_sample, _FREEZE_TIMEOUT_S) is False


def test_mixed_none_and_valid_raw_ts_no_false_positive(
    tmp_path: Path,
) -> None:
    """A mix of None and valid raw_ts samples must not corrupt the
    detector's state. None samples are pass-throughs (no signal),
    valid samples advance the tracker normally."""
    coord = SessionCoordinator(
        _config(tmp_path, data_freeze_timeout_s=_FREEZE_TIMEOUT_S),
    )
    coord._is_data_frozen(_sample(raw_ts=1.0), _FREEZE_TIMEOUT_S)
    # None sample — skipped.
    coord._is_data_frozen(_sample(raw_ts=None), _FREEZE_TIMEOUT_S)
    time.sleep(0.02)
    # Valid same raw_ts — under timeout, no trip.
    assert coord._is_data_frozen(
        _sample(raw_ts=1.0), _FREEZE_TIMEOUT_S,
    ) is False
    # Recovery resets normally.
    assert coord._is_data_frozen(
        _sample(raw_ts=2.0), _FREEZE_TIMEOUT_S,
    ) is False


# -- isolation between coordinators ------------------------------


def test_coordinators_have_isolated_freeze_state(tmp_path: Path) -> None:
    """Two coordinator instances must NOT share freeze tracking state
    — otherwise a freeze in one would falsely trip the other."""
    coord_a = SessionCoordinator(
        _config(
            tmp_path / "a", data_freeze_timeout_s=_FREEZE_TIMEOUT_S,
        ),
    )
    coord_b = SessionCoordinator(
        _config(
            tmp_path / "b", data_freeze_timeout_s=_FREEZE_TIMEOUT_S,
        ),
    )
    # Coord A stalls.
    coord_a._is_data_frozen(_sample(raw_ts=1.0), _FREEZE_TIMEOUT_S)
    time.sleep(_FREEZE_OVERSHOOT_S)
    assert coord_a._is_data_frozen(
        _sample(raw_ts=1.0), _FREEZE_TIMEOUT_S,
    ) is True

    # Coord B sees its first sample fresh — must NOT trip just
    # because A is in a frozen state.
    assert coord_b._is_data_frozen(
        _sample(raw_ts=1.0), _FREEZE_TIMEOUT_S,
    ) is False
