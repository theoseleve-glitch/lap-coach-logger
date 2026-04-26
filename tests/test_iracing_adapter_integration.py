"""T204: Integration test — iRacing adapter happy path.

Exercises the full adapter lifecycle (connect → is_session_active
→ read_sample → disconnect) against a hand-rolled fake of the
``irsdk.IRSDK`` interface. Real ``pyirsdk`` is not required.

The fake replaces ``irsdk.IRSDK`` in the adapter module's
namespace and flips ``_HAS_IRSDK = True`` so the connect()
guard passes. The fake's ``__getitem__`` returns realistic
values for telemetry channels — the adapter normalizes these
into a ``TelemetrySample`` exactly as it would with the real
SDK.

T205 (sim-disconnect mid-session) reuses the fake with failure
injection.
"""
from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import patch

import pytest

from lap_coach_logger.adapters.iracing_adapter import IRacingAdapter


# -- fake IRSDK -------------------------------------------------------


class _FakeVarHeader:
    def __init__(self, name: str, count: int = 1) -> None:
        self.name = name
        self.count = count


class _FakeHeader:
    """Mimics irsdk's _header — exposes tick_rate + var_buf."""

    def __init__(self, tick_rate: int = 60) -> None:
        self.tick_rate = tick_rate
        self.num_buf = 1
        self.session_info_update = 1
        # var_buf is a list of objects with tick_count.
        bt = types.SimpleNamespace(tick_count=42)
        self.var_buf = [bt]


class _FakeIRSDK:
    """Hand-rolled stand-in for ``irsdk.IRSDK`` that replays
    a static set of channel values via ``__getitem__``.

    Designed so:
    - ``startup()`` returns True → adapter connect succeeds.
    - ``__getitem__`` returns realistic values for the channels
      the adapter reads. Unknown keys return None (matches
      pyirsdk's "missing var" behavior).
    - ``shutdown()`` is a no-op.
    - ``freeze_var_buffer_latest()`` is a no-op.
    - ``var_headers_names`` is a small dict so ``_cache_var_headers``
      finds something to cache.
    - ``_header`` exposes a tick_rate.
    """

    # Realistic happy-path values for the channels the adapter
    # touches in read_sample / read_dashboard_state /
    # is_session_active.
    _CHANNELS: dict[str, Any] = {
        # state
        "IsOnTrack": True,
        "OnPitRoad": False,
        "SessionTick": 12345,
        "SessionNum": 0,
        # core telemetry
        "SessionTime": 42.5,
        "Lap": 3,
        "LapDist": 1500.0,
        "LapDistPct": 0.42,
        "Speed": 65.0,  # m/s — adapter normalizes to km/h
        "Throttle": 0.85,
        "Brake": 0.0,
        "SteeringWheelAngle": 0.12,
        "Clutch": 1.0,
        "Gear": 4,
        "RPM": 7200.0,
        # position / orientation
        "Lat": 50.4365,
        "Lon": 5.9714,
        "Alt": 415.0,
        "Yaw": 1.45,
        "Pitch": 0.02,
        "Roll": -0.01,
        "LongAccel": 1.5,
        "LatAccel": 0.8,
        # tyres
        "LFtempCL": 85.0,
        "RFtempCL": 86.0,
        "LRtempCL": 82.0,
        "RRtempCL": 83.0,
        # car state
        "FuelLevel": 28.5,
        "WaterTemp": 92.0,
        "OilTemp": 105.0,
        # weather
        "TrackTempCrew": 32.0,
        "AirTemp": 22.0,
        # driver-aids
        "dcABS": 0.0,
        "dcTractionControl": 0.0,
        # dashboard fields
        "LapCurrentLapTime": 22.3,
        "LapLastLapTime": 105.4,
        "LapBestLapTime": 104.9,
        "LapDeltaToBestLap": 0.04,
        "LapDeltaToSessionBestLap": 0.04,
        "LapCurrentSector": 1,
        # session info — these are dicts (from session info YAML)
        "WeekendInfo": {
            "TrackDisplayName": "Spa-Francorchamps",
            "TrackName": "spa",
        },
        "DriverInfo": {
            "DriverCarIdx": 0,
            "DriverCarFuelMaxLtr": 80.0,
            "Drivers": [
                {
                    "CarIdx": 0,
                    "CarScreenName": "Ferrari 296 GT3",
                    "CarPath": "ferrari296gt3",
                },
            ],
        },
        "SessionInfo": {
            "Sessions": [
                {"SessionType": "Practice"},
            ],
        },
    }

    def __init__(self) -> None:
        self._started = False
        self.var_headers_names = {
            "Speed": _FakeVarHeader("Speed"),
            "Throttle": _FakeVarHeader("Throttle"),
            "Brake": _FakeVarHeader("Brake"),
        }
        self._header = _FakeHeader(tick_rate=60)
        # pyirsdk also exposes header (no underscore).
        self.header = self._header

    def startup(self) -> bool:
        self._started = True
        return True

    def shutdown(self) -> None:
        self._started = False

    def freeze_var_buffer_latest(self) -> None:
        pass

    def __getitem__(self, key: str) -> Any:
        # Mirrors pyirsdk: missing keys return None, not raise.
        return self._CHANNELS.get(key)


@pytest.fixture
def patched_irsdk():
    """Install the fake irsdk module + flip _HAS_IRSDK True."""
    fake_irsdk_module = types.SimpleNamespace(IRSDK=_FakeIRSDK)
    with patch.object(
        sys.modules["lap_coach_logger.adapters.iracing_adapter"],
        "_HAS_IRSDK", True,
    ), patch.object(
        sys.modules["lap_coach_logger.adapters.iracing_adapter"],
        "irsdk", fake_irsdk_module,
    ):
        yield


# -- adapter identity ------------------------------------------------


def test_adapter_reports_iracing_sim_name() -> None:
    """``sim_name`` must be exactly ``iRacing`` so consumers
    can route by string match."""
    adapter = IRacingAdapter()
    assert adapter.sim_name == "iRacing"


def test_adapter_reports_iracing_process_names() -> None:
    """Process detection needs the iRacing exe name(s)."""
    adapter = IRacingAdapter()
    procs = adapter.process_names
    assert isinstance(procs, list)
    assert len(procs) > 0
    # iRacingSim64DX11.exe is the canonical 64-bit DX11
    # process; the list may include legacy alternatives.
    assert any("iRacing" in p for p in procs), (
        f"process_names must include an iRacing exe; got {procs}"
    )


# -- connect happy path ---------------------------------------------


def test_connect_succeeds_with_running_irsdk(patched_irsdk) -> None:
    """When pyirsdk is available and shared memory is up,
    ``connect()`` must return True and flip ``connected``."""
    adapter = IRacingAdapter()
    assert adapter.connect() is True
    assert adapter.connected is True


def test_connect_caches_session_metadata(patched_irsdk) -> None:
    """``connect()`` reads the WeekendInfo / DriverInfo /
    SessionInfo blocks and caches track / car / session_type."""
    adapter = IRacingAdapter()
    adapter.connect()
    # Internal cache attributes are part of the adapter's
    # contract — they're consumed by read_sample's passthrough.
    assert adapter._track_name == "Spa-Francorchamps"
    assert adapter._car_name == "Ferrari 296 GT3"
    assert adapter._session_type == "Practice"
    assert adapter._fuel_capacity == pytest.approx(80.0)


def test_connect_reads_sdk_tick_rate(patched_irsdk) -> None:
    """Tick-rate cache is what the sample-rate budget uses to
    avoid over-polling the SDK."""
    adapter = IRacingAdapter()
    adapter.connect()
    assert adapter._sdk_tick_rate_hz == 60


def test_connect_returns_false_when_pyirsdk_missing() -> None:
    """If ``_HAS_IRSDK`` is False (pyirsdk not installed),
    connect must short-circuit to False without raising."""
    with patch.object(
        sys.modules["lap_coach_logger.adapters.iracing_adapter"],
        "_HAS_IRSDK", False,
    ):
        adapter = IRacingAdapter()
        assert adapter.connect() is False
        assert adapter.connected is False


# -- session active state -------------------------------------------


def test_is_session_active_reports_on_track(patched_irsdk) -> None:
    """When IsOnTrack is True, the adapter reports active."""
    adapter = IRacingAdapter()
    adapter.connect()
    assert adapter.is_session_active() is True


def test_is_session_active_false_when_not_connected() -> None:
    """Without connect, adapter is not active — the fast-path
    on every cold launch."""
    adapter = IRacingAdapter()
    assert adapter.is_session_active() is False


# -- read_sample produces a TelemetrySample -------------------------


def test_read_sample_returns_telemetry_sample(patched_irsdk) -> None:
    """``read_sample()`` must return a non-None
    ``TelemetrySample`` populated from the SDK channels."""
    adapter = IRacingAdapter()
    adapter.connect()
    sample = adapter.read_sample()
    assert sample is not None, (
        "connected adapter with on-track state must produce a sample"
    )
    # sim field must reflect adapter identity.
    assert sample.sim == "iRacing"


def test_read_sample_carries_session_uid(patched_irsdk) -> None:
    """Each connect() generates a fresh session_uid; samples
    must carry it so downstream consumers can group samples
    by session."""
    adapter = IRacingAdapter()
    adapter.connect()
    sample = adapter.read_sample()
    assert sample is not None
    assert sample.session_uid, (
        "sample must carry a non-empty session_uid"
    )
    # The same adapter on the same connection must produce
    # the same session_uid across samples.
    sample2 = adapter.read_sample()
    assert sample2 is not None
    assert sample.session_uid == sample2.session_uid


def test_read_sample_includes_track_and_car(patched_irsdk) -> None:
    """Sample's track_name and car_name must come from the
    cached session metadata."""
    adapter = IRacingAdapter()
    adapter.connect()
    sample = adapter.read_sample()
    assert sample is not None
    assert sample.track_name == "Spa-Francorchamps"
    assert sample.car_name == "Ferrari 296 GT3"


def test_read_sample_normalizes_speed_to_kph(patched_irsdk) -> None:
    """iRacing reports Speed in m/s (65.0 in the fake); the
    adapter must normalize to km/h (65 × 3.6 = 234) — catches
    silent-unit-mismatch bugs that would corrupt every dashboard."""
    adapter = IRacingAdapter()
    adapter.connect()
    sample = adapter.read_sample()
    assert sample is not None
    # 65.0 m/s = 234 km/h.
    assert sample.speed_kph == pytest.approx(234.0, rel=0.01), (
        f"Speed normalization broken: 65 m/s should be ≈234 km/h, "
        f"got {sample.speed_kph}"
    )


def test_read_sample_returns_none_when_not_connected() -> None:
    """Without connect, no samples — caller's loop relies on
    None to mean 'try again later, maybe sim launched'."""
    adapter = IRacingAdapter()
    assert adapter.read_sample() is None


# -- disconnect cleans up -------------------------------------------


def test_disconnect_clears_connected_state(patched_irsdk) -> None:
    """After disconnect, all the cached state is wiped so the
    next connect() starts fresh."""
    adapter = IRacingAdapter()
    adapter.connect()
    assert adapter.connected is True
    adapter.disconnect()
    assert adapter.connected is False
    # Subsequent reads return None.
    assert adapter.read_sample() is None
    assert adapter.is_session_active() is False


def test_disconnect_clears_session_metadata(patched_irsdk) -> None:
    """Session metadata cache must be cleared on disconnect —
    otherwise a fresh connect to a different track would
    serve stale track_name from the previous session."""
    adapter = IRacingAdapter()
    adapter.connect()
    assert adapter._track_name == "Spa-Francorchamps"
    adapter.disconnect()
    assert adapter._track_name is None
    assert adapter._car_name is None
    assert adapter._session_type is None


def test_disconnect_is_idempotent(patched_irsdk) -> None:
    """Double-disconnect (e.g., on shutdown after a crash)
    must not raise — defensive cleanup must tolerate
    unexpected state."""
    adapter = IRacingAdapter()
    adapter.connect()
    adapter.disconnect()
    adapter.disconnect()  # must not raise
    assert adapter.connected is False
