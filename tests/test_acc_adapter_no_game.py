"""T207: Integration test — ACC adapter no-game graceful behavior.

When ACC is not running, the three ``Local\\acpmf_*`` shared-memory
regions cannot be opened. The adapter must:
  - return False from connect() without raising
  - clean up any partially-opened mappings (no resource leaks)
  - keep all read methods returning None
  - tolerate repeated connect attempts (polling for sim launch)
  - tolerate disconnect when never connected (idempotent)

T206 covered the all-three-fail case at module level. T207 covers
the per-region partial-failure variants and the dependent read
methods (read_dashboard_state, read_raw_sample, etc.) — these are
the surfaces a UI or main loop would touch while waiting for the
sim to come up.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

import lap_coach_logger.adapters.acc_adapter as acc_module
from lap_coach_logger.adapters.acc_adapter import ACCAdapter


# -- helpers --------------------------------------------------------


def _patch_mmap_to_raise(exc: Exception):
    """Patch acc_adapter's mmap.mmap to always raise the given exception."""
    return patch.object(
        acc_module.mmap, "mmap", side_effect=exc,
    )


# -- connect returns False on every fault variant -------------------


def test_connect_returns_false_when_filenotfound() -> None:
    """ACC not running → mmap raises FileNotFoundError → graceful False."""
    with _patch_mmap_to_raise(FileNotFoundError("acpmf_physics not found")):
        adapter = ACCAdapter()
        assert adapter.connect() is False
        assert adapter.connected is False


def test_connect_returns_false_when_oserror() -> None:
    """Permission denied / handle exhaustion → OSError → graceful False."""
    with _patch_mmap_to_raise(OSError("access denied")):
        adapter = ACCAdapter()
        assert adapter.connect() is False
        assert adapter.connected is False


def test_connect_returns_false_when_value_error() -> None:
    """Adapter's broad except catches even unexpected types like ValueError."""
    with _patch_mmap_to_raise(ValueError("invalid size argument")):
        adapter = ACCAdapter()
        assert adapter.connect() is False
        assert adapter.connected is False


# -- partial mapping cleanup ----------------------------------------


def test_connect_cleans_up_when_graphics_mmap_fails() -> None:
    """If physics opens but graphics fails, the partial physics
    mapping must be closed — otherwise repeated connect attempts
    would leak handles. Track this via the adapter's internal slots
    being None after a failed connect."""
    open_calls: list[object] = []

    class _FakeShm:
        def __init__(self) -> None:
            self.closed = False
            open_calls.append(self)

        def seek(self, n: int) -> None:
            pass

        def read(self, n: int) -> bytes:
            return b"\x00" * n

        def close(self) -> None:
            self.closed = True

    def _selective_mmap(fileno, size, *args, **kwargs):
        tagname = kwargs.get("tagname")
        if tagname == "Local\\acpmf_physics":
            return _FakeShm()
        if tagname == "Local\\acpmf_graphics":
            raise FileNotFoundError("graphics shm missing")
        if tagname == "Local\\acpmf_static":
            return _FakeShm()
        raise OSError(f"unexpected: {tagname}")

    with patch.object(acc_module.mmap, "mmap", side_effect=_selective_mmap):
        adapter = ACCAdapter()
        assert adapter.connect() is False

    # Internal slots must all be None after the cleanup.
    assert adapter._shm_physics is None
    assert adapter._shm_graphics is None
    assert adapter._shm_static is None
    # The successfully-opened physics mapping was closed.
    assert all(f.closed for f in open_calls), (
        "partial mappings must be closed when connect fails"
    )


def test_connect_cleans_up_when_static_mmap_fails() -> None:
    """Physics + graphics open, static fails → both must be closed."""
    open_calls: list[object] = []

    class _FakeShm:
        def __init__(self) -> None:
            self.closed = False
            open_calls.append(self)

        def seek(self, n: int) -> None:
            pass

        def read(self, n: int) -> bytes:
            return b"\x00" * n

        def close(self) -> None:
            self.closed = True

    def _selective_mmap(fileno, size, *args, **kwargs):
        tagname = kwargs.get("tagname")
        if tagname in ("Local\\acpmf_physics", "Local\\acpmf_graphics"):
            return _FakeShm()
        if tagname == "Local\\acpmf_static":
            raise FileNotFoundError("static shm missing")
        raise OSError(f"unexpected: {tagname}")

    with patch.object(acc_module.mmap, "mmap", side_effect=_selective_mmap):
        adapter = ACCAdapter()
        assert adapter.connect() is False

    # Both successfully-opened mappings closed.
    assert len(open_calls) == 2
    assert all(f.closed for f in open_calls)
    assert adapter._shm_physics is None
    assert adapter._shm_graphics is None
    assert adapter._shm_static is None


# -- read methods all return None when not connected ---------------


def test_is_session_active_false_when_no_game() -> None:
    """No connect → no active session — fast path on cold launch."""
    adapter = ACCAdapter()
    assert adapter.is_session_active() is False


def test_read_sample_returns_none_when_no_game() -> None:
    """Without connect, no samples — caller's loop polls until sim runs."""
    adapter = ACCAdapter()
    assert adapter.read_sample() is None


def test_read_dashboard_state_returns_none_when_no_game() -> None:
    """Dashboard state must also short-circuit — UI thread can't crash."""
    adapter = ACCAdapter()
    assert adapter.read_dashboard_state() is None


def test_read_raw_sample_returns_none_when_no_game() -> None:
    """Raw-capture API must also gate on connected."""
    adapter = ACCAdapter()
    assert adapter.read_raw_sample() is None


def test_read_session_info_snapshot_returns_none_when_no_game() -> None:
    """Session-info snapshot must gate on connected."""
    adapter = ACCAdapter()
    assert adapter.read_session_info_snapshot() is None


def test_read_methods_return_none_after_failed_connect() -> None:
    """A failed connect leaves the adapter in the same state as
    a fresh adapter — all reads return None."""
    with _patch_mmap_to_raise(FileNotFoundError("no acc")):
        adapter = ACCAdapter()
        adapter.connect()  # returns False; ignore

    assert adapter.read_sample() is None
    assert adapter.read_dashboard_state() is None
    assert adapter.read_raw_sample() is None
    assert adapter.read_session_info_snapshot() is None
    assert adapter.is_session_active() is False


# -- polling pattern: repeated connect attempts ---------------------


def test_repeated_connect_attempts_with_no_game_all_return_false() -> None:
    """Caller polls connect() while waiting for ACC to launch.
    Each attempt must return False without leaking — connect must
    be idempotently retryable from a no-game starting state."""
    with _patch_mmap_to_raise(FileNotFoundError("still no acc")):
        adapter = ACCAdapter()
        results = [adapter.connect() for _ in range(5)]

    assert all(r is False for r in results), (
        f"all 5 retry attempts must return False; got {results}"
    )
    assert adapter.connected is False
    # No internal state should be set after all-failed connects.
    assert adapter._shm_physics is None
    assert adapter._shm_graphics is None
    assert adapter._shm_static is None
    assert adapter._track_name is None
    assert adapter._car_name is None


def test_disconnect_safe_when_never_connected() -> None:
    """disconnect() before any connect must not raise — caller may
    call disconnect in a finally block regardless of connect outcome."""
    adapter = ACCAdapter()
    adapter.disconnect()  # must not raise
    assert adapter.connected is False


def test_disconnect_safe_after_failed_connect() -> None:
    """After a failed connect, disconnect must still be safe."""
    with _patch_mmap_to_raise(FileNotFoundError("no acc")):
        adapter = ACCAdapter()
        adapter.connect()
    adapter.disconnect()  # must not raise
    assert adapter.connected is False


# -- session UID not generated until first successful connect -------


def test_session_uid_empty_after_failed_connect() -> None:
    """A failed connect must not leave a half-baked session_uid that
    a later successful connect or downstream code might mistake for
    a real session."""
    with _patch_mmap_to_raise(FileNotFoundError("no acc")):
        adapter = ACCAdapter()
        adapter.connect()

    # Session UID is empty string (constructor default), not a uuid.
    assert adapter._session_uid == "", (
        f"failed connect must not set session_uid; got {adapter._session_uid!r}"
    )
