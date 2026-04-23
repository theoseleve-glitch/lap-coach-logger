"""Tests for the LiveProcessor ABC (sprint T002).

Verifies the abstract contract: three required hooks
(on_sample, on_lap_end, on_session_end), abstract instantiation guard,
and a minimal concrete subclass happy path.
"""

from __future__ import annotations

import pytest

from lap_coach_logger.core.live_processor import LiveProcessor
from lap_coach_logger.core.schema import TelemetrySample


def test_live_processor_is_abstract() -> None:
    """LiveProcessor cannot be instantiated directly."""
    with pytest.raises(TypeError):
        LiveProcessor()  # type: ignore[abstract]


def test_live_processor_requires_on_sample() -> None:
    """Subclass missing on_sample cannot be instantiated."""

    class MissingSample(LiveProcessor):
        def on_lap_end(self, lap_number: int, lap_time_s: float | None) -> None:
            return None

        def on_session_end(self) -> None:
            return None

    with pytest.raises(TypeError):
        MissingSample()  # type: ignore[abstract]


def test_live_processor_requires_on_lap_end() -> None:
    """Subclass missing on_lap_end cannot be instantiated."""

    class MissingLap(LiveProcessor):
        def on_sample(
            self,
            sample: TelemetrySample,
            *,
            dashboard_state: dict | None = None,
            derived_state: dict | None = None,
        ) -> None:
            return None

        def on_session_end(self) -> None:
            return None

    with pytest.raises(TypeError):
        MissingLap()  # type: ignore[abstract]


def test_live_processor_requires_on_session_end() -> None:
    """Subclass missing on_session_end cannot be instantiated."""

    class MissingSession(LiveProcessor):
        def on_sample(
            self,
            sample: TelemetrySample,
            *,
            dashboard_state: dict | None = None,
            derived_state: dict | None = None,
        ) -> None:
            return None

        def on_lap_end(self, lap_number: int, lap_time_s: float | None) -> None:
            return None

    with pytest.raises(TypeError):
        MissingSession()  # type: ignore[abstract]


def test_live_processor_concrete_subclass_receives_events() -> None:
    """Minimal concrete subclass implementing all hooks routes events correctly."""

    class Recorder(LiveProcessor):
        def __init__(self) -> None:
            self.samples: list[TelemetrySample] = []
            self.laps: list[tuple[int, float | None]] = []
            self.ended: bool = False

        def on_sample(
            self,
            sample: TelemetrySample,
            *,
            dashboard_state: dict | None = None,
            derived_state: dict | None = None,
        ) -> None:
            self.samples.append(sample)

        def on_lap_end(self, lap_number: int, lap_time_s: float | None) -> None:
            self.laps.append((lap_number, lap_time_s))

        def on_session_end(self) -> None:
            self.ended = True

    recorder = Recorder()
    sample = TelemetrySample(sim="iracing", session_uid="x", session_time_s=0.0)
    recorder.on_sample(sample)
    recorder.on_lap_end(1, 62.5)
    recorder.on_session_end()

    assert recorder.samples == [sample]
    assert recorder.laps == [(1, 62.5)]
    assert recorder.ended is True
