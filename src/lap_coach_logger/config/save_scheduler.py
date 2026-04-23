"""Debounced save scheduler for config (and anything else that writes JSON).

**Problem it solves.** Qt ``Q_PROPERTY`` setters frequently emit multiple
``settingsSaveRequested`` signals in response to a single user action
(e.g. ``OverlayViewModel.autoArrange`` touches every widget and fires once
per widget). Directly calling :meth:`ConfigManager.save` on every signal
produces a burst of 4-8 full disk writes per user gesture.

**Design.**

    request_save()  ->  mark dirty, (re)arm a single-shot timer

    (timer fires, off the Qt thread)

    flush_locked()  ->  dirty? run writer, clear dirty; else no-op

A single :class:`threading.RLock` guards the dirty flag, the timer
reference, and the shutdown flag. The writer callback runs *outside*
the lock so a slow disk write cannot block main-thread requests; the
dirty flag is re-checked after the write so requests arriving during
the write are not dropped.

The scheduler is intentionally decoupled from the config model: callers
pass a zero-arg ``writer`` that captures whatever state they want to
persist. That state is read at flush time, so the final write always
reflects the latest in-memory state — this is what makes coalescing safe.

Thread safety: ``request_save()``, ``flush()``, and ``shutdown()`` may all
be called from any thread. The writer itself must be thread-safe (the
existing :meth:`ConfigManager.save` is, because atomic rename is).
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Timer abstraction — injected for tests; duck-typed around ``threading.Timer``
# ---------------------------------------------------------------------------


# Factory signature: (delay_s, callback) -> object with start() and cancel().
# We rely on duck typing rather than a Protocol because the real and fake
# implementations differ only structurally and no polymorphic dispatch is needed.
TimerFactory = Callable[[float, Callable[[], None]], Any]


def _default_timer_factory(delay_s: float, callback: Callable[[], None]) -> threading.Timer:
    """Real-world timer: a daemon ``threading.Timer``.

    Daemon so the timer thread never blocks process exit.
    """
    timer = threading.Timer(delay_s, callback)
    timer.daemon = True
    return timer


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


class SaveScheduler:
    """Debounce + coalesce save requests into a single disk write.

    Parameters
    ----------
    writer:
        Zero-arg callable that performs the actual persistence. Typically a
        ``lambda: config_manager.save(config)``. Called off the requester's
        thread. May raise; exceptions are logged and the dirty flag is
        preserved so shutdown flush will retry.
    delay_s:
        Debounce window. A save scheduled within this window of a previous
        request resets the timer. Default 0.5s is long enough to coalesce
        typical UI bursts without feeling laggy.
    timer_factory:
        Injected for tests. Receives ``(delay_s, callback)`` and returns an
        object with ``start()`` / ``cancel()``. Defaults to ``threading.Timer``.
    name:
        Optional logger label; useful if you wire multiple schedulers.
    """

    def __init__(
        self,
        writer: Callable[[], None],
        *,
        delay_s: float = 0.5,
        timer_factory: TimerFactory = _default_timer_factory,
        name: str = "config",
    ) -> None:
        if delay_s < 0:
            raise ValueError(f"delay_s must be >= 0, got {delay_s}")
        self._writer = writer
        self._delay_s = delay_s
        self._timer_factory = timer_factory
        self._name = name

        self._lock = threading.RLock()
        self._dirty = False
        self._timer: Any = None  # whatever the factory returns
        self._shutdown = False
        # Latches so repeated failures don't spam the log.
        self._failure_logged = False

    # -- observable state (diagnostics only) --------------------------------

    @property
    def is_dirty(self) -> bool:
        """True if a write is pending (either armed or waiting for flush)."""
        with self._lock:
            return self._dirty

    @property
    def pending(self) -> bool:
        """True if a debounce timer is currently armed."""
        with self._lock:
            return self._timer is not None

    # -- public API ---------------------------------------------------------

    def request_save(self) -> None:
        """Mark state dirty and (re)arm the debounce timer.

        Safe to call from any thread. Repeated calls inside the debounce
        window coalesce into a single write.
        """
        new_timer: Any = None
        with self._lock:
            if self._shutdown:
                # After shutdown, refuse silent scheduling. Caller should
                # have called flush() already; log once per late request.
                log.debug("[%s] save requested after shutdown — ignored", self._name)
                return

            if self._dirty and self._timer is not None:
                # Pure coalesce: keep the existing timer, don't reschedule.
                # This bounds the worst-case latency between the first
                # request in a burst and the write to ``delay_s``.
                log.debug("[%s] save coalesced (timer already armed)", self._name)
                return

            self._dirty = True
            log.debug("[%s] save requested", self._name)
            self._arm_timer_locked()
            new_timer = self._timer

        # Start the timer outside the lock so a slow thread-spawn does
        # not block concurrent requesters. Safe because we only start a
        # fresh timer; cancellation is still lock-guarded.
        if new_timer is not None:
            new_timer.start()

    def flush(self) -> bool:
        """Write immediately if dirty. Cancels any pending debounce timer.

        Returns True if a write happened, False if nothing was pending.
        Safe to call from any thread. Exceptions from the writer are
        logged and re-raised so callers that care (e.g. save buttons)
        can surface them to the user.
        """
        with self._lock:
            self._cancel_timer_locked()
            if not self._dirty:
                return False
            # Clear dirty optimistically; if the write fails we set it back
            # inside _run_writer so shutdown / next request retries.
            self._dirty = False

        # Writer call is deliberately outside the lock so a slow disk
        # cannot block a concurrent request_save() from marking dirty.
        self._run_writer(source="flush")
        return True

    def flush_now(self) -> None:
        """Unconditionally write the current state, cancelling any debounce.

        For explicit user-initiated saves (e.g. a Settings "Save" button)
        where the caller needs the write to land *now* regardless of
        whether the scheduler considered itself dirty. The caller is
        assumed to have just mutated state; we mark dirty, cancel any
        pending timer, and write synchronously.

        Raises whatever the writer raises, so the UI can surface errors.
        After shutdown this becomes a logged no-op — critical saves during
        exit should go through :meth:`flush` in the shutdown handler.
        """
        with self._lock:
            if self._shutdown:
                log.debug("[%s] flush_now after shutdown — ignored", self._name)
                return
            self._cancel_timer_locked()
            # Clear any previously pending dirty state — we are writing
            # the full current state *now*. On failure _run_writer will
            # re-set dirty so a later request/shutdown retries.
            self._dirty = False

        self._run_writer(source="flush_now")

    def shutdown(self) -> None:
        """Final flush + stop accepting new requests.

        Idempotent. Call from ``app.aboutToQuit`` / ``register_cleanup``.
        Exceptions from the final write are logged but not re-raised —
        we do not want a failing flush to block process exit.
        """
        with self._lock:
            if self._shutdown:
                return
            self._shutdown = True
            self._cancel_timer_locked()
            dirty = self._dirty
            self._dirty = False

        if not dirty:
            log.debug("[%s] shutdown — nothing to flush", self._name)
            return

        try:
            self._run_writer(source="shutdown")
        except Exception:
            # Already logged inside _run_writer; swallow to protect exit.
            log.debug("[%s] shutdown flush raised — suppressed at exit", self._name)

    # -- internals ----------------------------------------------------------

    def _arm_timer_locked(self) -> None:
        """Create a fresh one-shot timer. Caller holds the lock.

        ``timer.start()`` happens after the lock is released in
        :meth:`request_save` via :meth:`_start_armed_timer`. This keeps
        the thread-spawn off the critical section so concurrent requesters
        do not block on it.
        """
        self._timer = self._timer_factory(self._delay_s, self._on_timer_fire)

    def _cancel_timer_locked(self) -> None:
        """Cancel any armed timer. Caller holds the lock."""
        if self._timer is not None:
            try:
                self._timer.cancel()
            except Exception:
                # threading.Timer.cancel() is no-op if already fired; any
                # other exception is from an injected fake and is harmless.
                pass
            self._timer = None

    def _on_timer_fire(self) -> None:
        """Timer callback. Runs on the timer thread."""
        with self._lock:
            # Another thread may have already flushed us.
            if not self._dirty or self._shutdown:
                self._timer = None
                return
            self._timer = None
            self._dirty = False

        try:
            self._run_writer(source="debounce")
        except Exception:
            # _run_writer already logged + re-set dirty. Swallow on timer
            # thread so threading.Timer doesn't complain about unhandled.
            pass

    def _run_writer(self, *, source: str) -> None:
        """Call the writer, handling failures without losing state.

        On success: log once at DEBUG ("save flushed"), clear the
        failure-logged latch.

        On failure: log at WARNING with exc_info the first time (and
        only the first time until a write succeeds again), mark dirty
        so the next request / shutdown retries, and re-raise.
        """
        try:
            self._writer()
        except Exception:
            with self._lock:
                self._dirty = True  # preserve state for retry
                first_failure = not self._failure_logged
                self._failure_logged = True
            if first_failure:
                log.warning(
                    "[%s] save failed (source=%s) — will retry on next request",
                    self._name, source,
                    exc_info=True,
                )
            else:
                log.debug("[%s] save failed again (source=%s)", self._name, source)
            raise

        with self._lock:
            self._failure_logged = False
        log.debug("[%s] save flushed (source=%s)", self._name, source)
