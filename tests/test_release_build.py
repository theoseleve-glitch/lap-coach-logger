"""Tests for release-build detection and strict runtime enforcement."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from lap_coach_logger.utils.runtime_check import check_runtime


def _vi(major: int, minor: int, micro: int = 0) -> SimpleNamespace:
    """Build a sys.version_info-shaped stub. check_runtime only reads .major/.minor."""
    return SimpleNamespace(major=major, minor=minor, micro=micro,
                           releaselevel="final", serial=0)


class TestCheckRuntimeStrict:
    """``strict=True`` should raise on mismatch — the release-build path."""

    def test_strict_passes_on_correct_version(self) -> None:
        """3.12 (our target) must be accepted in strict mode."""
        with patch.object(sys, "version_info", _vi(3, 12, 9)):
            assert check_runtime(strict=True) is True

    def test_strict_raises_on_newer_version(self) -> None:
        """Even a NEWER Python must fail in strict (release) mode.

        We know 3.14 has traceback/signal quirks that break log dedup.
        A release binary pinned at 3.12 must not silently run there.
        """
        with patch.object(sys, "version_info", _vi(3, 14, 3)):
            with pytest.raises(RuntimeError, match="Unsupported Python version"):
                check_runtime(strict=True)

    def test_strict_raises_on_older_version(self) -> None:
        with patch.object(sys, "version_info", _vi(3, 11, 0)):
            with pytest.raises(RuntimeError, match="Unsupported Python version"):
                check_runtime(strict=True)

    def test_nonstrict_warns_and_returns_false(self, caplog: pytest.LogCaptureFixture) -> None:
        """Dev mode: warn but allow boot."""
        import logging
        with patch.object(sys, "version_info", _vi(3, 14, 3)):
            with caplog.at_level(logging.WARNING, logger="lap_coach_logger.utils.runtime_check"):
                assert check_runtime(strict=False) is False
        assert any("Unsupported Python" in r.message for r in caplog.records)


class TestReleaseBuildFlag:
    """``IS_FROZEN`` is derived from ``sys.frozen`` set by PyInstaller."""

    def test_is_frozen_false_in_dev(self) -> None:
        """Normal pytest run is not a frozen bundle."""
        # We import inside the test because the flag is evaluated at
        # module import time; a clean reimport is unnecessary here since
        # the dev interpreter never sets sys.frozen.
        from lap_coach_logger.utils import release_build
        assert release_build.IS_FROZEN is False
        assert release_build.BUILD_KIND == "development"

    def test_is_frozen_true_when_sys_frozen_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Simulate the PyInstaller bootloader by setting sys.frozen.

        Uses pytest's monkeypatch so cleanup is automatic even if the
        assertions raise — `sys.frozen` is restored on teardown.
        """
        import importlib
        import lap_coach_logger.utils.release_build as rb
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        try:
            reloaded = importlib.reload(rb)
            assert reloaded.IS_FROZEN is True
            assert reloaded.BUILD_KIND == "release"
        finally:
            # Remove the attr we may have created, then reload so the
            # rest of the test session sees the pristine module state.
            monkeypatch.delattr(sys, "frozen", raising=False)
            importlib.reload(rb)
