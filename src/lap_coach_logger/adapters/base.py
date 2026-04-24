"""Abstract base class for sim telemetry adapters.

Each supported sim implements this interface.  The adapter is
responsible for:
1. Detecting whether the sim process is running.
2. Connecting to the sim's telemetry source (shared memory, UDP, etc.).
3. Reading individual telemetry samples.
4. Reporting whether a driving session is currently active.
5. Cleaning up OS-level resources on disconnect.
"""

from __future__ import annotations

import abc
from typing import Any

from lap_coach_logger.core.schema import TelemetrySample


class SimAdapter(abc.ABC):
    """Contract that every sim-specific adapter must fulfil."""

    @property
    @abc.abstractmethod
    def sim_name(self) -> str:
        """Human-readable sim identifier (e.g. 'iRacing', 'ACC')."""

    @property
    @abc.abstractmethod
    def process_names(self) -> list[str]:
        """Executable names to look for (e.g. ['iRacingSim64DX11.exe'])."""

    @abc.abstractmethod
    def connect(self) -> bool:
        """Attempt to open the telemetry data source.

        Returns True if the connection is ready for reading.
        """

    @abc.abstractmethod
    def disconnect(self) -> None:
        """Release handles, sockets, or shared-memory mappings."""

    @abc.abstractmethod
    def is_session_active(self) -> bool:
        """Return True if the sim is currently in an active driving session."""

    @abc.abstractmethod
    def read_sample(self) -> TelemetrySample | None:
        """Read one normalised telemetry frame.

        Returns None when no data is available (e.g. loading screen).
        Must never raise on missing channels — fill with None instead.
        """

    # -- extended capture (optional, overridden by iRacing) ----------------

    def supports_raw_capture(self) -> bool:
        """Return True if this adapter can produce a raw telemetry dict."""
        return False

    def wait_for_new_tick(self, timeout_s: float = 1.0) -> bool:
        """Block until a new SDK buffer tick is available. Return False on timeout."""
        return False

    def read_raw_sample(self) -> dict[str, Any] | None:
        """Read a flat dict of all available raw telemetry vars. None if unavailable."""
        return None

    def read_session_info_snapshot(self) -> dict[str, Any] | None:
        """Return the flattened session-info YAML as a dict. None if unavailable."""
        return None

    def read_relative(self) -> dict[str, Any] | None:
        """Read gap-to-neighbour data. None when the sim doesn't expose it.

        When available, returns a dict with any subset of:
          - gap_ahead_s: float (seconds behind car in front; > 0 if behind)
          - gap_behind_s: float (seconds ahead of car behind; > 0)
          - position_ahead: int
          - position_behind: int
        Adapters must NOT fabricate values — omit keys rather than guess.
        """
        return None

    def get_sdk_metadata(self) -> dict[str, Any]:
        """Return SDK runtime metadata (tick rate, buffer info, etc.)."""
        return {}

    def read_dashboard_state(self) -> dict[str, Any] | None:
        """Return UI-focused live state that does not belong in TelemetrySample."""
        return None

    # -- convenience (non-abstract) ----------------------------------------

    @property
    def connected(self) -> bool:   # noqa: D401
        """Override in subclass if connection state tracking is needed."""
        return False
