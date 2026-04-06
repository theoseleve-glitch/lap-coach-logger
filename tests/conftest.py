"""Project-wide pytest fixtures providing ready-made telemetry samples and bundles.

These fixtures are available automatically to all test modules under tests/.
Shared helper functions live in tests/helpers.py so they can be imported by any
test module without going through conftest's special-file import mechanism.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lap_coach_logger.core.schema import TelemetrySample
from tests.helpers import finalize_session, make_quality_samples  # noqa: F401

__all__ = ["make_quality_samples", "finalize_session"]


@pytest.fixture
def quality_samples() -> list[TelemetrySample]:
    """200 high-quality iRacing samples that pass all quality gates."""
    return make_quality_samples()


@pytest.fixture
def bundled_session(tmp_path: Path) -> Path:
    """A complete finalized iRacing session bundle under a fresh tmp directory."""
    output_root = tmp_path / "sessions"
    output_root.mkdir(parents=True)
    return finalize_session(output_root, session_uid="fixture-uid")
