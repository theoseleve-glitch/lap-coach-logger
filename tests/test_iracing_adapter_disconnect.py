"""T205: Integration test — iRacing adapter sim-disconnect mid-session.

Pins the adapter's contract under three disconnect scenarios:
  1. Driver leaves the track (sim still running, IsOnTrack flips False).
  2. Sim crashes (freeze_var_buffer_latest raises).
  3. Shared memory dies (__getitem__ raises during sample read).

For each scenario the caller's session loop must terminate cleanly:
  - ``is_session_active()`` returns False (loop exits)
  - ``read_sample()`` returns None (no garbage samples)
  - ``disconnect()`` does not raise even if shutdown() raises
  - State is wiped so a fresh connect produces a NEW session_uid

T204 covered the happy path. This file uses the same fake-IRSDK
pattern but adds failure-injection hooks (``freeze_should_raise``,
``getitem_should_raise``, ``shutdown_should_raise``, mutable
``channels`` dict).
"""
from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import patch

import pytest

from lap_coach_logger.adapters.iracing_adapter import IRacingAdapter


# -- fake IRSDK with failure injection -------------------------------


_BASE_CHANNELS: dict[str, Any] = {
    "IsOnTrack": True,
    "OnPitRoad": False,
    "SessionTick": 12345,
    "SessionNum": 0,
    "SessionTime": 42.5,
    "Lap": 3,
    "LapDist": 1500.0,
    "LapDistPct": 0.42,
    "Speed": 65.0,
    "Throttle": 0.85,
    "Brake": 0.0,
    "SteeringWheelAngle": 0.12,
    "Clutch": 1.0,
    "Gear": 4,
    "RPM": 7200.0,
    "Lat": 50.4365,
    "Lon": 5.9714,
    "Alt": 415.0,
    "Yaw": 1.45,
    "Pitch": 0.02,
    "Roll": -0.01,
    "LongAccel": 1.5,
    "LatAccel": 0.8,
    "LFtempCL": 85.0,
    "RFtempCL": 86.0,
    "LRtempCL": 82.0,
    "RRtempCL": 83.0,
    "FuelLevel": 28.5,
    "WaterTemp": 92.0,
    "OilTemp": 105.0,
    "TrackTempCrew": 32.0,
    "AirTemp": 22.0,
    "dcABS": 0.0,
    "dcTractionControl": 0.0,
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


class _FakeVarHeader:
    def __init__(self, name: str, count: int = 1) -> None:
        self.name = name
        self.count = count


class _FakeHeader:
    def __init__(self, tick_rate: int = 60) -> None:
        self.tick_rate = tick_rate
        self.num_buf = 1
        self.session_info_update = 1
        bt = types.SimpleNamespace(tick_count=42)
        self.var_buf = [bt]


class _FakeIRSDKWithFailureInjection:
    """Like T204's _FakeIRSDK but with mutation hooks.

    Tests can flip ``freeze_should_raise`` / ``getitem_should_raise``
    / ``shutdown_should_raise`` mid-session to simulate the sim
    going away.  ``channels`` is a per-instance mutable dict so
    individual values (like IsOnTrack) can be flipped without
    affecting other tests.
    """

    def __init__(self) -> None:
        self._started = False
        self.channels: dict[str, Any] = dict(_BASE_CHANNELS)
        self.var_headers_names = {
            "Speed": _FakeVarHeader("Speed"),
            "Throttle": _FakeVarHeader("Throttle"),
            "Brake": _FakeVarHeader("Brake"),
        }
        self._header = _FakeHeader(tick_rate=60)
        self.header = self._header
        # Failure injection knobs
        self.freeze_should_raise = False
        self.getitem_should_raise = False
        self.shutdown_should_raise = False
        self.shutdown_call_count = 0

    def startup(self) -> bool:
        self._started = True
        return True

    def shutdown(self) -> None:
        self.shutdown_call_count += 1
        if self.shutdown_should_raise:
            raise RuntimeError("simulated sim crash during shutdown")
        self._started = False

    def freeze_var_buffer_latest(self) -> None:
        if self.freeze_should_raise:
            raise RuntimeError(
                "simulated freeze error: sim disconnected"
            )

    def __getitem__(self, key: str) -> Any:
        if self.getitem_should_raise:
            raise RuntimeError(
                "simulated SDK read failure: shared memory gone"
            )
        return self.channels.get(key)


@pytest.fixture
def fake_factory():
    """Yield a list that captures every fake IRSDK instance created.

    The adapter's ``connect()`` calls ``irsdk.IRSDK()`` internally —
    this fixture's capturing class appends ``self`` so the test
    can grab the live fake and flip its failure knobs.
    """
    instances: list[_FakeIRSDKWithFailureInjection] = []

    class _CapturingFake(_FakeIRSDKWithFailureInjection):
        def __init__(self) -> None:
            super().__init__()
            instances.append(self)

    fake_module = types.SimpleNamespace(IRSDK=_CapturingFake)
    with patch.object(
        sys.modules["lap_coach_logger.adapters.iracing_adapter"],
        "_HAS_IRSDK", True,
    ), patch.object(
        sys.modules["lap_coach_logger.adapters.iracing_adapter"],
        "irsdk", fake_module,
    ):
        yield instances


# -- driver leaves track (sim still alive) --------------------------


def test_is_session_active_flips_when_driver_leaves_track(
    fake_factory,
) -> None:
    """When IsOnTrack flips False mid-session (driver pauses, opens
    menu, exits to garage) the adapter must report inactive — caller's
    main loop uses this to break out and finalize."""
    adapter = IRacingAdapter()
    adapter.connect()
    fake = fake_factory[0]

    assert adapter.is_session_active() is True, (
        "pre-condition: adapter must be active when on track"
    )
    # Driver leaves track — sim still running, IsOnTrack flips
    fake.channels["IsOnTrack"] = False
    assert adapter.is_session_active() is False, (
        "active state must reflect IsOnTrack flip mid-session"
    )


def test_read_sample_still_works_after_driver_leaves_track(
    fake_factory,
) -> None:
    """Off-track ≠ disconnected. Sample reads keep working so the
    caller can flush a final sample if it wants — read_sample only
    gates on _connected, not on IsOnTrack."""
    adapter = IRacingAdapter()
    adapter.connect()
    fake = fake_factory[0]

    fake.channels["IsOnTrack"] = False
    sample = adapter.read_sample()
    assert sample is not None, (
        "off-track but connected adapter must still return samples"
    )


# -- sim crashes — freeze raises ------------------------------------


def test_read_sample_returns_none_when_freeze_raises(
    fake_factory,
) -> None:
    """When the sim process dies, ``freeze_var_buffer_latest``
    raises (shared memory is gone). The adapter MUST swallow this
    and return None — never raise into the caller's session loop."""
    adapter = IRacingAdapter()
    adapter.connect()
    fake = fake_factory[0]

    # Confirm pre-condition: sample reads work before the crash.
    pre_crash = adapter.read_sample()
    assert pre_crash is not None

    # Simulate sim crash: freeze raises on every subsequent call.
    fake.freeze_should_raise = True
    sample = adapter.read_sample()
    assert sample is None, (
        "read_sample must return None when freeze raises, "
        "not propagate the exception"
    )


def test_dashboard_state_returns_none_when_freeze_raises(
    fake_factory,
) -> None:
    """``read_dashboard_state`` shares the same defensive pattern —
    a sim crash mid-overlay-render must not bring down the UI thread."""
    adapter = IRacingAdapter()
    adapter.connect()
    fake = fake_factory[0]

    fake.freeze_should_raise = True
    state = adapter.read_dashboard_state()
    assert state is None


# -- shared memory dies — __getitem__ raises ------------------------


def test_read_sample_does_not_raise_when_getitem_raises(
    fake_factory,
) -> None:
    """If the underlying shared-memory mapping is torn down between
    freeze and indexed reads, ``ir[key]`` raises per call. The
    adapter's per-key ``_get_*`` helpers each catch individually,
    so ``read_sample`` returns a degraded sample (SDK fields → None)
    rather than None overall — but it MUST NOT propagate the
    exception. This test pins the no-raise contract; sample-level
    None gating is the freeze-raises path."""
    adapter = IRacingAdapter()
    adapter.connect()
    fake = fake_factory[0]

    fake.getitem_should_raise = True
    # No exception must escape — that's the defensive contract.
    sample = adapter.read_sample()
    # Sample is returned with degraded telemetry — speed/throttle
    # come from None SDK reads. Cached metadata (track/car/uid)
    # still populated because they were captured at connect time.
    assert sample is not None
    assert sample.speed_kph is None
    assert sample.throttle_pct is None
    # Cached at connect — still present.
    assert sample.track_name == "Spa-Francorchamps"
    assert sample.session_uid != ""


def test_is_session_active_returns_false_when_getitem_raises(
    fake_factory,
) -> None:
    """A getitem failure during ``is_session_active`` must return
    False (not propagate) — caller's loop uses this as the
    terminate-on-error signal."""
    adapter = IRacingAdapter()
    adapter.connect()
    fake = fake_factory[0]

    fake.getitem_should_raise = True
    assert adapter.is_session_active() is False


# -- disconnect after sim crash -------------------------------------


def test_disconnect_does_not_raise_when_shutdown_raises(
    fake_factory,
) -> None:
    """If the sim crashed and the SDK shutdown call now raises
    (e.g., COM object invalid), ``disconnect()`` MUST swallow it.
    Otherwise the caller's finalize-on-shutdown chain breaks."""
    adapter = IRacingAdapter()
    adapter.connect()
    fake = fake_factory[0]
    fake.shutdown_should_raise = True

    # Must not raise.
    adapter.disconnect()
    assert fake.shutdown_call_count == 1, (
        "shutdown was attempted exactly once"
    )
    assert adapter.connected is False


def test_read_sample_returns_none_after_disconnect_following_crash(
    fake_factory,
) -> None:
    """Post-disconnect cleanup must wipe state even if disconnect
    itself encountered an error — no zombie samples after."""
    adapter = IRacingAdapter()
    adapter.connect()
    fake = fake_factory[0]
    fake.shutdown_should_raise = True
    adapter.disconnect()

    assert adapter.read_sample() is None
    assert adapter.is_session_active() is False


def test_disconnect_clears_metadata_after_mid_session_crash(
    fake_factory,
) -> None:
    """Cached track/car/session_type must be cleared so a fresh
    reconnect to a different track doesn't serve stale data."""
    adapter = IRacingAdapter()
    adapter.connect()
    fake = fake_factory[0]
    assert adapter._track_name == "Spa-Francorchamps"

    fake.shutdown_should_raise = True
    adapter.disconnect()

    assert adapter._track_name is None
    assert adapter._car_name is None
    assert adapter._session_type is None


# -- session UID continuity & post-crash reconnect ------------------


def test_session_uid_preserved_across_pre_crash_samples(
    fake_factory,
) -> None:
    """Samples taken BEFORE a sim crash must share the same
    session_uid — caller groups them by UID into one session bundle."""
    adapter = IRacingAdapter()
    adapter.connect()

    s1 = adapter.read_sample()
    s2 = adapter.read_sample()
    assert s1 is not None and s2 is not None
    assert s1.session_uid == s2.session_uid

    # Now sim crashes — the next read returns None, but UID-grouping
    # of s1/s2 is still coherent.
    fake_factory[0].freeze_should_raise = True
    assert adapter.read_sample() is None


def test_reconnect_after_crash_produces_new_session_uid(
    fake_factory,
) -> None:
    """A fresh connect after a mid-session crash must mint a NEW
    session_uid — old samples and new samples must NOT collide."""
    adapter = IRacingAdapter()
    adapter.connect()
    pre_sample = adapter.read_sample()
    assert pre_sample is not None
    pre_uid = pre_sample.session_uid

    # Sim crashes, caller finalizes & disconnects.
    fake_factory[0].freeze_should_raise = True
    adapter.disconnect()

    # User reconnects (sim came back).
    assert adapter.connect() is True
    post_sample = adapter.read_sample()
    assert post_sample is not None
    assert post_sample.session_uid != pre_uid, (
        "post-crash reconnect must produce a new session_uid; "
        f"got same uid {pre_uid} on both sides of the crash"
    )


def test_reconnect_after_crash_re_reads_metadata(fake_factory) -> None:
    """A reconnect after sim crash must re-fetch track/car from
    session-info YAML — caller might have changed track between sessions."""
    adapter = IRacingAdapter()
    adapter.connect()
    fake1 = fake_factory[0]

    # Sim crashes.
    fake1.freeze_should_raise = True
    adapter.disconnect()
    assert adapter._track_name is None  # cache cleared

    # Reconnect (creates a 2nd fake instance with its own metadata).
    # We mutate the second fake's track BEFORE connect to prove
    # the adapter actually re-reads YAML on every connect().
    # Trick: we patch _BASE_CHANNELS via the live class so the next
    # _CapturingFake init copies the new track.
    # Easier: just verify the cache is repopulated after reconnect.
    adapter.connect()
    assert adapter._track_name == "Spa-Francorchamps"
    assert adapter._car_name == "Ferrari 296 GT3"
    assert adapter._session_type == "Practice"


# -- caller's session loop terminates naturally ---------------------


def test_session_loop_terminates_on_mid_session_crash(
    fake_factory,
) -> None:
    """Simulate the canonical caller loop:

        while adapter.is_session_active():
            sample = adapter.read_sample()
            if sample: samples.append(sample)
        adapter.disconnect()
        finalize(samples)

    Mid-loop the sim crashes. The loop must terminate with the
    samples-collected-so-far intact — no exceptions, no zombie reads."""
    adapter = IRacingAdapter()
    adapter.connect()
    fake = fake_factory[0]
    samples: list[Any] = []

    iteration = 0
    while adapter.is_session_active():
        sample = adapter.read_sample()
        if sample is not None:
            samples.append(sample)
        iteration += 1
        # Simulate sim crash on iteration 3 (sets BOTH the raise
        # flag and IsOnTrack=False — what would actually happen
        # when the sim process dies).
        if iteration == 3:
            fake.freeze_should_raise = True
            fake.channels["IsOnTrack"] = False
        # Safety: bail out if loop runs away.
        if iteration > 10:
            pytest.fail("session loop did not terminate")

    # We must have at least 3 pre-crash samples + at most one
    # final read attempt that may have failed.
    assert len(samples) >= 3, (
        f"loop should have collected pre-crash samples, got {len(samples)}"
    )
    # Disconnect must not raise even though shutdown is fine here.
    adapter.disconnect()
    assert adapter.connected is False
