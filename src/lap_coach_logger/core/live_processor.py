"""Abstract base for composable live telemetry processors (sprint T002).

``LiveProcessor`` defines the minimal lifecycle surface that every
sub-processor (coaching, dashboard, input diagnostics) must expose so
``LiveTelemetryProcessor`` can fan events out uniformly once T006 lands.

Three hooks form the contract:

* ``on_sample`` -- every raw ``TelemetrySample`` emitted by the coordinator.
* ``on_lap_end`` -- a completed lap, with its number and optional lap time.
* ``on_session_end`` -- session teardown, equivalent to a ``reset`` call.

Sub-processors are expected to be lightweight enough to live on the
sample thread. Uses ``__slots__ = ()`` so concrete subclasses can freely
declare their own ``__slots__`` without paying for an empty dict.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from lap_coach_logger.core.schema import TelemetrySample


class LiveProcessor(ABC):
    """Lifecycle contract for a sub-processor in the live telemetry pipeline."""

    __slots__ = ()

    @abstractmethod
    def on_sample(
        self,
        sample: TelemetrySample,
        *,
        dashboard_state: dict[str, Any] | None = None,
        derived_state: dict[str, Any] | None = None,
    ) -> None:
        """Handle one live telemetry sample."""

    @abstractmethod
    def on_lap_end(self, lap_number: int, lap_time_s: float | None) -> None:
        """Handle a completed lap boundary."""

    @abstractmethod
    def on_session_end(self) -> None:
        """Tear down any per-session state (equivalent to ``reset``)."""


__all__ = ["LiveProcessor"]
