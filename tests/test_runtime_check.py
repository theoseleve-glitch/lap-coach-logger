"""Tests for runtime version check."""
from __future__ import annotations

import sys
import pytest

from lap_coach_logger.utils.runtime_check import check_runtime, current_version


def test_check_runtime_returns_bool():
    result = check_runtime(strict=False)
    assert isinstance(result, bool)


def test_check_runtime_matches_current():
    # On the test runner, current Python should pass if it's 3.12
    result = check_runtime(strict=False)
    expected = (sys.version_info.major, sys.version_info.minor) == (3, 12)
    assert result == expected


def test_current_version_format():
    version = current_version()
    assert version.count(".") == 2
    parts = version.split(".")
    assert all(p.isdigit() for p in parts)


def test_strict_raises_on_mismatch(monkeypatch):
    # Patch sys.version_info to fake a wrong version
    class FakeVI:
        major = 3
        minor = 15
        micro = 0
    monkeypatch.setattr(sys, "version_info", FakeVI)
    with pytest.raises(RuntimeError, match="Unsupported Python"):
        check_runtime(strict=True)


def test_non_strict_warns_on_mismatch(monkeypatch, caplog):
    import logging
    class FakeVI:
        major = 3
        minor = 15
        micro = 0
    monkeypatch.setattr(sys, "version_info", FakeVI)
    with caplog.at_level(logging.WARNING):
        result = check_runtime(strict=False)
    assert result is False
    assert any("Unsupported Python" in r.message for r in caplog.records)
