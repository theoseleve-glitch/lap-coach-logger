"""Log deduplication handler.

Suppresses identical exceptions firing in a tight loop. Logs the
first occurrence at its natural level, suppresses duplicates for
a configurable window, and emits a summary count when the window
expires.
"""
from __future__ import annotations

import logging
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Any


@dataclass
class _Entry:
    first_logged_at: float
    count: int
    last_record: logging.LogRecord | None


class DedupFilter(logging.Filter):
    """Logging filter that suppresses repeated error signatures.

    Signature = exception type + message + top 3 stack frames.
    Different signatures are never suppressed. Thread-safe.
    """

    def __init__(self, window_s: float = 30.0) -> None:
        super().__init__()
        self._window_s = window_s
        self._entries: dict[str, _Entry] = {}
        self._lock = threading.Lock()

    @property
    def window_s(self) -> float:
        return self._window_s

    def set_window(self, window_s: float) -> None:
        self._window_s = max(0.1, float(window_s))

    def filter(self, record: logging.LogRecord) -> bool:
        # Only dedupe records that have exception info
        if record.exc_info is None:
            return True
        sig = self._signature(record)
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(sig)
            if entry is None:
                self._entries[sig] = _Entry(first_logged_at=now, count=1, last_record=None)
                return True
            elapsed = now - entry.first_logged_at
            if elapsed > self._window_s:
                # Window expired — emit summary and reset
                count = entry.count
                self._entries[sig] = _Entry(first_logged_at=now, count=1, last_record=None)
                if count > 1:
                    # Mutate record to become the summary
                    record.msg = f"Repeated error suppressed {count} times in {elapsed:.0f}s"
                    record.exc_info = None
                    record.exc_text = None
                    return True
                return True
            # Still in window — suppress
            entry.count += 1
            entry.last_record = record
            return False

    @staticmethod
    def _signature(record: logging.LogRecord) -> str:
        if record.exc_info is None:
            return f"{record.levelno}::{record.getMessage()}"
        exc_type, exc_value, exc_tb = record.exc_info
        if exc_type is None:
            return f"{record.levelno}::{record.getMessage()}"
        type_name = exc_type.__name__
        message = str(exc_value) if exc_value is not None else ""
        # Top 3 frames
        frames = traceback.extract_tb(exc_tb, limit=3)
        frame_sig = "|".join(f"{f.filename}:{f.lineno}:{f.name}" for f in frames)
        return f"{type_name}::{message}::{frame_sig}"

    def snapshot(self) -> dict[str, Any]:
        """Return current dedup state — useful for tests/debugging."""
        with self._lock:
            return {
                sig: {"count": e.count, "first_logged_at": e.first_logged_at}
                for sig, e in self._entries.items()
            }

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()
