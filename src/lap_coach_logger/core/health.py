"""Application health / status snapshot.

Provides a single thread-safe object that any component can update
and the UI / logs can read at any time.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class HealthStatus:
    """Live snapshot of system state."""
    state: str = "idle"
    sim: str | None = None
    sample_count: int = 0
    dropped_samples: int = 0
    session_started_at: str | None = None
    last_save_path: str | None = None
    last_save_samples: int = 0
    last_error: str | None = None
    uptime_started: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class HealthMonitor:
    """Thread-safe wrapper around ``HealthStatus``."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._status = HealthStatus()

    def snapshot(self) -> HealthStatus:
        with self._lock:
            # Return a shallow copy
            import dataclasses
            return dataclasses.replace(self._status)

    def update(self, **kwargs: object) -> None:
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self._status, k):
                    setattr(self._status, k, v)

    @property
    def state(self) -> str:
        with self._lock:
            return self._status.state

    @property
    def status_line(self) -> str:
        """One-line human-readable status for tray tooltip."""
        with self._lock:
            s = self._status
            parts = [s.state.replace("_", " ").title()]
            if s.sim:
                parts.append(f"({s.sim})")
            if s.sample_count > 0:
                parts.append(f"• {s.sample_count} samples")
            return " ".join(parts)
