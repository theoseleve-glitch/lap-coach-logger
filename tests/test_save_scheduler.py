"""Tests for :class:`SaveScheduler`.

Coalescing and timer cancellation are tested deterministically with a
manual timer fake (no wall-clock waits). One end-to-end test uses the
real ``threading.Timer`` to prove the default factory wires up
correctly.
"""

from __future__ import annotations

import threading
import time
from typing import Callable

import pytest

from lap_coach_logger.config.save_scheduler import SaveScheduler


# ---------------------------------------------------------------------------
# Manual timer fake — deterministic control
# ---------------------------------------------------------------------------


class _ManualTimer:
    """Records start/cancel; fires only when test calls ``.fire()``."""

    def __init__(self, delay_s: float, callback: Callable[[], None]) -> None:
        self.delay_s = delay_s
        self.callback = callback
        self.started = False
        self.cancelled = False

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True

    def fire(self) -> None:
        """Simulate timer expiry. No-op if cancelled or not started."""
        if self.started and not self.cancelled:
            self.callback()


class _TimerRecorder:
    """Factory that records every ``_ManualTimer`` it creates."""

    def __init__(self) -> None:
        self.timers: list[_ManualTimer] = []

    def __call__(self, delay_s: float, callback: Callable[[], None]) -> _ManualTimer:
        t = _ManualTimer(delay_s, callback)
        self.timers.append(t)
        return t

    @property
    def last(self) -> _ManualTimer:
        return self.timers[-1]

    @property
    def active(self) -> list[_ManualTimer]:
        """Timers that were started and not cancelled and haven't fired."""
        return [t for t in self.timers if t.started and not t.cancelled]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _CountingWriter:
    """Records call count + lets a test inject failures."""

    def __init__(self) -> None:
        self.calls = 0
        self.fail_next = 0  # fail this many upcoming calls

    def __call__(self) -> None:
        self.calls += 1
        if self.fail_next > 0:
            self.fail_next -= 1
            raise RuntimeError("disk full (simulated)")


# ---------------------------------------------------------------------------
# Coalescing
# ---------------------------------------------------------------------------


class TestCoalescing:
    """Multiple rapid requests must collapse into a single writer call."""

    def test_ten_requests_arm_single_timer(self) -> None:
        writer = _CountingWriter()
        recorder = _TimerRecorder()
        sched = SaveScheduler(writer, delay_s=0.5, timer_factory=recorder)

        for _ in range(10):
            sched.request_save()

        # Only the first request arms a timer. Subsequent requests inside
        # the debounce window reuse it. That bounds worst-case latency.
        assert len(recorder.timers) == 1
        assert sched.is_dirty is True
        assert sched.pending is True
        assert writer.calls == 0  # no write until timer fires

    def test_timer_fire_runs_writer_once(self) -> None:
        writer = _CountingWriter()
        recorder = _TimerRecorder()
        sched = SaveScheduler(writer, delay_s=0.5, timer_factory=recorder)

        for _ in range(10):
            sched.request_save()
        recorder.last.fire()

        assert writer.calls == 1
        assert sched.is_dirty is False
        assert sched.pending is False

    def test_second_burst_after_fire_arms_new_timer(self) -> None:
        """After a flush, a new burst should create a fresh timer."""
        writer = _CountingWriter()
        recorder = _TimerRecorder()
        sched = SaveScheduler(writer, delay_s=0.5, timer_factory=recorder)

        sched.request_save()
        recorder.last.fire()
        assert writer.calls == 1

        for _ in range(5):
            sched.request_save()
        recorder.last.fire()

        assert writer.calls == 2
        assert len(recorder.timers) == 2


# ---------------------------------------------------------------------------
# Explicit flush
# ---------------------------------------------------------------------------


class TestFlushNow:
    """``flush_now()`` is the explicit-Save primitive used by UI buttons."""

    def test_flush_now_writes_even_when_clean(self) -> None:
        writer = _CountingWriter()
        sched = SaveScheduler(writer, delay_s=0.5, timer_factory=_TimerRecorder())

        sched.flush_now()

        assert writer.calls == 1
        assert sched.is_dirty is False

    def test_flush_now_cancels_pending_timer(self) -> None:
        writer = _CountingWriter()
        recorder = _TimerRecorder()
        sched = SaveScheduler(writer, delay_s=0.5, timer_factory=recorder)

        sched.request_save()
        sched.flush_now()

        assert writer.calls == 1
        assert recorder.last.cancelled is True
        assert sched.is_dirty is False
        assert sched.pending is False

    def test_flush_now_propagates_writer_failure(self) -> None:
        """Failures must surface so UI can show an error toast."""
        writer = _CountingWriter()
        writer.fail_next = 1
        sched = SaveScheduler(writer, delay_s=0.5, timer_factory=_TimerRecorder())

        with pytest.raises(RuntimeError):
            sched.flush_now()

        # Dirty preserved so retry (e.g. shutdown flush) persists state.
        assert sched.is_dirty is True

    def test_flush_now_after_shutdown_is_noop(self) -> None:
        writer = _CountingWriter()
        sched = SaveScheduler(writer, delay_s=0.5, timer_factory=_TimerRecorder())

        sched.shutdown()
        sched.flush_now()  # must not raise, must not write

        assert writer.calls == 0


class TestFlush:
    def test_flush_cancels_timer_and_writes(self) -> None:
        writer = _CountingWriter()
        recorder = _TimerRecorder()
        sched = SaveScheduler(writer, delay_s=0.5, timer_factory=recorder)

        sched.request_save()
        assert recorder.last.started is True
        assert recorder.last.cancelled is False

        wrote = sched.flush()

        assert wrote is True
        assert writer.calls == 1
        assert recorder.last.cancelled is True
        assert sched.is_dirty is False

    def test_flush_is_noop_when_clean(self) -> None:
        writer = _CountingWriter()
        sched = SaveScheduler(writer, delay_s=0.5, timer_factory=_TimerRecorder())

        wrote = sched.flush()

        assert wrote is False
        assert writer.calls == 0

    def test_flush_after_fire_does_not_double_write(self) -> None:
        """A fired timer clears dirty; a following flush must not rewrite."""
        writer = _CountingWriter()
        recorder = _TimerRecorder()
        sched = SaveScheduler(writer, delay_s=0.5, timer_factory=recorder)

        sched.request_save()
        recorder.last.fire()
        wrote = sched.flush()

        assert wrote is False
        assert writer.calls == 1


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------


class TestShutdown:
    def test_shutdown_flushes_pending_write(self) -> None:
        writer = _CountingWriter()
        recorder = _TimerRecorder()
        sched = SaveScheduler(writer, delay_s=0.5, timer_factory=recorder)

        sched.request_save()
        sched.shutdown()

        assert writer.calls == 1
        assert recorder.last.cancelled is True
        assert sched.is_dirty is False

    def test_shutdown_ignores_later_requests(self) -> None:
        writer = _CountingWriter()
        recorder = _TimerRecorder()
        sched = SaveScheduler(writer, delay_s=0.5, timer_factory=recorder)

        sched.shutdown()
        sched.request_save()  # should be ignored silently
        sched.request_save()

        assert writer.calls == 0
        # No timers should have been armed after shutdown.
        assert len(recorder.timers) == 0

    def test_shutdown_is_idempotent(self) -> None:
        writer = _CountingWriter()
        sched = SaveScheduler(writer, delay_s=0.5, timer_factory=_TimerRecorder())

        sched.request_save()
        sched.shutdown()
        sched.shutdown()  # second call must not re-write or raise

        assert writer.calls == 1

    def test_shutdown_clean_is_noop(self) -> None:
        writer = _CountingWriter()
        sched = SaveScheduler(writer, delay_s=0.5, timer_factory=_TimerRecorder())

        sched.shutdown()

        assert writer.calls == 0

    def test_shutdown_swallows_final_write_failure(self) -> None:
        """Failing final write must not block process exit."""
        writer = _CountingWriter()
        writer.fail_next = 1
        sched = SaveScheduler(writer, delay_s=0.5, timer_factory=_TimerRecorder())

        sched.request_save()
        sched.shutdown()  # must not raise

        assert writer.calls == 1  # attempt was made


# ---------------------------------------------------------------------------
# Write failure handling
# ---------------------------------------------------------------------------


class TestWriteFailure:
    def test_failed_flush_preserves_dirty(self) -> None:
        """If the writer raises, dirty must stay set so a retry persists."""
        writer = _CountingWriter()
        writer.fail_next = 1
        sched = SaveScheduler(writer, delay_s=0.5, timer_factory=_TimerRecorder())

        sched.request_save()
        with pytest.raises(RuntimeError):
            sched.flush()

        assert sched.is_dirty is True
        assert writer.calls == 1

        # Next flush succeeds and drains the dirty state.
        sched.flush()
        assert writer.calls == 2
        assert sched.is_dirty is False

    def test_failed_timer_fire_preserves_dirty_and_does_not_raise(self) -> None:
        """Timer-thread failure must not propagate (would crash daemon thread)."""
        writer = _CountingWriter()
        writer.fail_next = 1
        recorder = _TimerRecorder()
        sched = SaveScheduler(writer, delay_s=0.5, timer_factory=recorder)

        sched.request_save()
        recorder.last.fire()  # no exception should leak

        assert sched.is_dirty is True
        assert writer.calls == 1

    def test_persistent_failure_logs_only_once(self, caplog: pytest.LogCaptureFixture) -> None:
        """Rapid repeated failures must not spam the log."""
        import logging
        writer = _CountingWriter()
        writer.fail_next = 5
        sched = SaveScheduler(writer, delay_s=0.5, timer_factory=_TimerRecorder())

        with caplog.at_level(logging.WARNING, logger="lap_coach_logger.config.save_scheduler"):
            for _ in range(5):
                sched.request_save()
                try:
                    sched.flush()
                except RuntimeError:
                    pass

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1, f"Expected 1 warning, got {len(warnings)}"
        assert writer.calls == 5  # each attempt still happens


# ---------------------------------------------------------------------------
# Delayed flush — real timer path
# ---------------------------------------------------------------------------


class TestRealTimer:
    """One end-to-end test with the default ``threading.Timer`` factory."""

    def test_default_timer_fires_and_writes(self) -> None:
        writer = _CountingWriter()
        sched = SaveScheduler(writer, delay_s=0.05)  # 50ms

        sched.request_save()
        # Give the timer thread up to 500ms to fire. We poll instead of
        # a fixed sleep to keep the test fast when the timer is prompt.
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            if writer.calls == 1:
                break
            time.sleep(0.01)

        assert writer.calls == 1
        assert sched.is_dirty is False


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_request_save_does_not_crash(self) -> None:
        """Hammer the scheduler from 8 threads; all writes must coalesce."""
        writer = _CountingWriter()
        recorder = _TimerRecorder()
        sched = SaveScheduler(writer, delay_s=0.5, timer_factory=recorder)

        errors: list[BaseException] = []

        def worker() -> None:
            try:
                for _ in range(500):
                    sched.request_save()
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert not errors, f"Worker threads raised: {errors}"
        # At most one timer should be armed despite 4000 concurrent requests.
        assert len(recorder.active) <= 1
        # Flush drains any pending state; writer should run exactly once.
        sched.flush()
        assert writer.calls == 1


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_negative_delay_rejected(self) -> None:
        with pytest.raises(ValueError):
            SaveScheduler(lambda: None, delay_s=-1.0)

    def test_zero_delay_is_allowed(self) -> None:
        """delay_s=0 is valid — request_save → near-immediate write."""
        writer = _CountingWriter()
        recorder = _TimerRecorder()
        sched = SaveScheduler(writer, delay_s=0.0, timer_factory=recorder)

        sched.request_save()
        recorder.last.fire()

        assert writer.calls == 1
