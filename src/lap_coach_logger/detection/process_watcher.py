"""Sim process detection service.

Periodically scans running processes to determine which (if any)
supported sim is active.  Emits state-change callbacks so the
session coordinator can react.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

import psutil

from lap_coach_logger.adapters.base import SimAdapter
from lap_coach_logger.utils.shutdown import shutdown_requested

log = logging.getLogger(__name__)

# Callback signature: (adapter, detected: bool)
DetectionCallback = Callable[[SimAdapter, bool], bool | None]


class ProcessWatcher:
    """Background thread that watches for sim processes."""

    def __init__(
        self,
        adapters: list[SimAdapter],
        *,
        poll_interval: float = 1.0,
        on_sim_found: DetectionCallback | None = None,
        on_sim_lost: DetectionCallback | None = None,
    ) -> None:
        self._adapters = adapters
        self._poll_interval = poll_interval
        self._on_sim_found = on_sim_found
        self._on_sim_lost = on_sim_lost
        self._thread: threading.Thread | None = None
        self._active_adapter: SimAdapter | None = None
        self._stop_event = threading.Event()
        self._running = False

    # -- public API ---------------------------------------------------------

    def start(self) -> None:
        if self._running and self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._run, name="process-watcher", daemon=True
        )
        self._thread.start()
        log.info("ProcessWatcher started (interval=%.1fs)", self._poll_interval)

    def stop(self) -> None:
        self._stop_event.set()
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self._poll_interval * 3)
            log.info("ProcessWatcher stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def active_adapter(self) -> SimAdapter | None:
        return self._active_adapter

    def set_poll_interval(self, interval_s: float) -> None:
        self._poll_interval = max(0.1, float(interval_s))

    # -- internals ----------------------------------------------------------

    def _run(self) -> None:
        while not shutdown_requested() and not self._stop_event.is_set():
            try:
                self._poll_once()
            except Exception:
                log.exception("ProcessWatcher poll error")
            time.sleep(self._poll_interval)
        self._running = False

    def _poll_once(self) -> None:
        """Check all adapters against running processes."""
        running_procs = self._snapshot_process_names()

        if self._active_adapter is not None:
            # Check if the currently active sim is still running
            if not self._is_any_running(self._active_adapter, running_procs):
                log.info(
                    "%s process no longer detected",
                    self._active_adapter.sim_name,
                )
                if self._on_sim_lost:
                    self._on_sim_lost(self._active_adapter, False)
                self._active_adapter = None
            return  # one sim at a time

        # Look for a newly appeared sim
        for adapter in self._adapters:
            if self._is_any_running(adapter, running_procs):
                log.info("%s process detected", adapter.sim_name)
                accepted = True
                if self._on_sim_found:
                    result = self._on_sim_found(adapter, True)
                    accepted = True if result is None else bool(result)
                if accepted:
                    self._active_adapter = adapter
                else:
                    log.info(
                        "%s telemetry not ready yet — will retry while process remains active",
                        adapter.sim_name,
                    )
                return

    @staticmethod
    def _snapshot_process_names() -> set[str]:
        """Return lowered names of all running processes (best-effort)."""
        names: set[str] = set()
        for proc in psutil.process_iter(attrs=["name"]):
            try:
                n = proc.info["name"]  # type: ignore[index]
                if n:
                    names.add(n.lower())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return names

    @staticmethod
    def _is_any_running(adapter: SimAdapter, running: set[str]) -> bool:
        return any(p.lower() in running for p in adapter.process_names)
