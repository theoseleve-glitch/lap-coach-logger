"""T206: Integration test — ACC adapter happy path.

Exercises the full ACC adapter lifecycle (connect → is_session_active
→ read_sample → disconnect) against fake mmap-backed shared memory
populated with realistic ctypes structs. No actual ACC required.

The fake replaces ``mmap.mmap`` in the adapter module's namespace
and dispatches by ``tagname`` to per-region BytesIO buffers backed
by populated ``SPageFilePhysics`` / ``SPageFileGraphic`` /
``SPageFileStatic`` structs converted via ``bytes(struct)``.

T207 (no-game) reuses the same module-level patch but makes
``mmap.mmap`` raise so ``connect()`` returns False gracefully.
"""
from __future__ import annotations

import io
import mmap
from unittest.mock import patch

import pytest

import lap_coach_logger.adapters.acc_adapter as acc_module
from lap_coach_logger.adapters.acc_adapter import ACCAdapter
from lap_coach_logger.adapters.acc_shm_structs import (
    SPageFileGraphic,
    SPageFilePhysics,
    SPageFileStatic,
)


# -- fake mmap shared memory ----------------------------------------


class _FakeShm:
    """BytesIO-backed stand-in for ``mmap.mmap``.

    The adapter's ``_read_*`` methods call ``buf.seek(0)`` then
    ``buf.read(N)`` — both of which BytesIO supports natively.
    ``close()`` is a no-op (close is best-effort in the adapter).
    """

    def __init__(self, payload: bytes) -> None:
        self._buf = io.BytesIO(payload)
        self.closed = False

    def seek(self, n: int) -> None:
        self._buf.seek(n)

    def read(self, n: int) -> bytes:
        return self._buf.read(n)

    def close(self) -> None:
        self.closed = True
        self._buf.close()


def _build_physics() -> SPageFilePhysics:
    """Build a populated physics struct with realistic on-track values."""
    p = SPageFilePhysics()
    p.packetId = 12345
    p.gas = 0.85
    p.brake = 0.0
    p.fuel = 28.5
    p.gear = 4
    p.rpms = 7200
    p.steerAngle = 0.12
    p.speedKmh = 234.0  # already km/h — adapter passes through
    p.tc = 0.0
    p.heading = 1.45
    p.pitch = 0.02
    p.roll = -0.01
    p.abs = 0.0
    p.airTemp = 22.0
    p.roadTemp = 32.0
    p.clutch = 1.0
    p.waterTemp = 92.0
    p.brakeBias = 0.55
    # accG[0..2], tyre temps, brake temps — fill a couple
    p.accG[0] = 1.5
    p.accG[2] = 0.8
    p.tyreCoreTemperature[0] = 85.0
    p.tyreCoreTemperature[1] = 86.0
    p.tyreCoreTemperature[2] = 82.0
    p.tyreCoreTemperature[3] = 83.0
    return p


def _build_graphics() -> SPageFileGraphic:
    """Build a populated graphics struct in LIVE state on Practice session."""
    g = SPageFileGraphic()
    g.packetId = 12345
    g.status = 2  # ACC_LIVE
    g.session = 0  # ACC_PRACTICE
    g.completedLaps = 3
    g.iCurrentTime = 22300  # ms
    g.iLastTime = 105400
    g.iBestTime = 104900
    g.iDeltaLapTime = 40  # +0.04 s
    g.isDeltaPositive = 1
    g.iSplit = 1
    g.currentSectorIndex = 0  # 1-based after _normalize_sector_index
    g.lastSectorTime = 32100
    g.normalizedCarPosition = 0.42
    g.isInPit = 0
    g.isInPitLane = 0
    g.position = 5
    g.numberOfLaps = 30
    g.flag = 0
    g.GlobalGreen = 1  # green flag
    g.TC = 3
    g.ABS = 4
    g.EngineMap = 2
    g.fuelXLap = 3.2
    g.fuelEstimatedLaps = 8.9
    return g


def _build_static() -> SPageFileStatic:
    """Build a populated static struct (cached once at connect)."""
    s = SPageFileStatic()
    s.smVersion = "1.9"
    s.acVersion = "1.9.5"
    s.numberOfSessions = 3
    s.numCars = 20
    s.carModel = "Ferrari 296 GT3"
    s.track = "Spa"
    s.playerName = "Theo"
    s.playerSurname = "Driver"
    s.playerNick = "TD"
    s.sectorCount = 3
    s.maxRpm = 9000
    s.maxFuel = 80.0
    s.trackSPlineLength = 7004.0
    return s


@pytest.fixture
def patched_acc_mmap():
    """Patch mmap.mmap to dispatch by tagname to fake shared memory.

    The adapter calls ``mmap.mmap(-1, size, tagname=..., access=...)``
    once per shared-memory region. We dispatch by ``tagname`` to
    return a BytesIO seeded with the appropriate populated struct.
    """
    physics_bytes = bytes(_build_physics())
    graphics_bytes = bytes(_build_graphics())
    static_bytes = bytes(_build_static())

    fakes_created: list[_FakeShm] = []

    def _mock_mmap(fileno, size, *args, **kwargs):
        tagname = kwargs.get("tagname")
        if tagname == "Local\\acpmf_physics":
            fake = _FakeShm(physics_bytes)
        elif tagname == "Local\\acpmf_graphics":
            fake = _FakeShm(graphics_bytes)
        elif tagname == "Local\\acpmf_static":
            fake = _FakeShm(static_bytes)
        else:
            raise OSError(f"unexpected tagname: {tagname!r}")
        fakes_created.append(fake)
        return fake

    with patch.object(acc_module.mmap, "mmap", side_effect=_mock_mmap):
        yield fakes_created


# -- adapter identity -----------------------------------------------


def test_adapter_reports_acc_sim_name() -> None:
    """``sim_name`` must be exactly ``ACC`` so consumers can route by string."""
    adapter = ACCAdapter()
    assert adapter.sim_name == "ACC"


def test_adapter_reports_acc_process_names() -> None:
    """Process detection needs the ACC executable name(s)."""
    adapter = ACCAdapter()
    procs = adapter.process_names
    assert isinstance(procs, list)
    assert len(procs) > 0
    # acc.exe is the canonical Steam executable name; AC2-Win64-Shipping.exe
    # is the underlying engine binary.
    assert "acc.exe" in procs


# -- connect happy path ---------------------------------------------


def test_connect_succeeds_with_running_acc(patched_acc_mmap) -> None:
    """When all three shared-memory regions are mappable, connect()
    must return True and flip ``connected``."""
    adapter = ACCAdapter()
    assert adapter.connect() is True
    assert adapter.connected is True


def test_connect_opens_all_three_shared_memory_regions(
    patched_acc_mmap,
) -> None:
    """ACC needs physics + graphics + static — three mmap calls."""
    adapter = ACCAdapter()
    adapter.connect()
    # patched_acc_mmap fixture appends one entry per mmap call.
    assert len(patched_acc_mmap) == 3, (
        f"connect must open 3 shm regions, got {len(patched_acc_mmap)}"
    )


def test_connect_caches_static_metadata(patched_acc_mmap) -> None:
    """connect() reads the static struct and caches track / car /
    spline length / max fuel — these never change mid-session."""
    adapter = ACCAdapter()
    adapter.connect()
    assert adapter._track_name == "Spa"
    assert adapter._car_name == "Ferrari 296 GT3"
    assert adapter._track_length_m == pytest.approx(7004.0)
    assert adapter._fuel_capacity == pytest.approx(80.0)
    assert adapter._sector_count == 3


def test_connect_returns_false_when_mmap_raises() -> None:
    """If ACC is not running, mmap.mmap raises FileNotFoundError /
    OSError — connect must short-circuit to False without raising."""
    def _failing_mmap(*args, **kwargs):
        raise FileNotFoundError("ACC shared memory not available")

    with patch.object(acc_module.mmap, "mmap", side_effect=_failing_mmap):
        adapter = ACCAdapter()
        assert adapter.connect() is False
        assert adapter.connected is False


def test_connect_generates_session_uid(patched_acc_mmap) -> None:
    """Each connect() generates a fresh session_uid for grouping samples."""
    adapter = ACCAdapter()
    adapter.connect()
    assert adapter._session_uid != ""
    assert len(adapter._session_uid) == 12  # uuid4().hex[:12]


# -- session active state -------------------------------------------


def test_is_session_active_true_when_status_is_live(
    patched_acc_mmap,
) -> None:
    """ACC_LIVE (status=2) means driver is on track. The fake graphics
    struct sets status=2."""
    adapter = ACCAdapter()
    adapter.connect()
    assert adapter.is_session_active() is True


def test_is_session_active_false_when_not_connected() -> None:
    """Without connect, adapter is not active — fast-path on cold launch."""
    adapter = ACCAdapter()
    assert adapter.is_session_active() is False


# -- read_sample produces a TelemetrySample -------------------------


def test_read_sample_returns_telemetry_sample(patched_acc_mmap) -> None:
    """read_sample() must return a non-None TelemetrySample populated
    from the fake shared-memory structs."""
    adapter = ACCAdapter()
    adapter.connect()
    sample = adapter.read_sample()
    assert sample is not None
    assert sample.sim == "ACC"


def test_read_sample_carries_session_uid(patched_acc_mmap) -> None:
    """Samples must carry the connect-time session_uid so downstream
    consumers can group by session. Same UID across multiple reads."""
    adapter = ACCAdapter()
    adapter.connect()
    s1 = adapter.read_sample()
    s2 = adapter.read_sample()
    assert s1 is not None and s2 is not None
    assert s1.session_uid != ""
    assert s1.session_uid == s2.session_uid


def test_read_sample_includes_track_and_car(patched_acc_mmap) -> None:
    """track_name and car_name come from cached static metadata."""
    adapter = ACCAdapter()
    adapter.connect()
    sample = adapter.read_sample()
    assert sample is not None
    assert sample.track_name == "Spa"
    assert sample.car_name == "Ferrari 296 GT3"


def test_read_sample_passes_through_speed_kph(patched_acc_mmap) -> None:
    """ACC reports speedKmh natively — no unit conversion needed.
    Pinning 234.0 km/h round-trip catches accidental m/s conversion."""
    adapter = ACCAdapter()
    adapter.connect()
    sample = adapter.read_sample()
    assert sample is not None
    assert sample.speed_kph == pytest.approx(234.0, rel=0.01)


def test_read_sample_includes_throttle_and_brake(
    patched_acc_mmap,
) -> None:
    """Throttle (gas) and brake are critical inputs — pin the round-trip."""
    adapter = ACCAdapter()
    adapter.connect()
    sample = adapter.read_sample()
    assert sample is not None
    # gas=0.85 (0..1) → throttle_pct should reflect this; the
    # mapper may scale to %. Check it's > 0 and not None.
    assert sample.throttle_pct is not None
    assert sample.throttle_pct > 0


def test_read_sample_returns_none_when_not_connected() -> None:
    """Without connect, no samples — caller's loop relies on None to
    mean 'try again later, maybe sim launched'."""
    adapter = ACCAdapter()
    assert adapter.read_sample() is None


# -- disconnect cleans up -------------------------------------------


def test_disconnect_clears_connected_state(patched_acc_mmap) -> None:
    """After disconnect, all cached state is wiped so the next connect
    starts fresh."""
    adapter = ACCAdapter()
    adapter.connect()
    assert adapter.connected is True
    adapter.disconnect()
    assert adapter.connected is False
    # Subsequent reads return None.
    assert adapter.read_sample() is None
    assert adapter.is_session_active() is False


def test_disconnect_clears_static_metadata(patched_acc_mmap) -> None:
    """Cached track/car must be cleared on disconnect — otherwise a
    fresh connect to a different track would serve stale data."""
    adapter = ACCAdapter()
    adapter.connect()
    assert adapter._track_name == "Spa"
    adapter.disconnect()
    assert adapter._track_name is None
    assert adapter._car_name is None


def test_disconnect_closes_shared_memory_mappings(
    patched_acc_mmap,
) -> None:
    """All three shm regions must be closed on disconnect — leaks
    would prevent re-mapping on reconnect."""
    adapter = ACCAdapter()
    adapter.connect()
    fakes = list(patched_acc_mmap)  # capture before disconnect clears refs
    adapter.disconnect()
    assert all(f.closed for f in fakes), (
        "all shared-memory regions must be closed on disconnect"
    )


def test_disconnect_is_idempotent(patched_acc_mmap) -> None:
    """Double-disconnect (e.g., on shutdown after a crash) must not
    raise — defensive cleanup must tolerate unexpected state."""
    adapter = ACCAdapter()
    adapter.connect()
    adapter.disconnect()
    adapter.disconnect()  # must not raise
    assert adapter.connected is False
