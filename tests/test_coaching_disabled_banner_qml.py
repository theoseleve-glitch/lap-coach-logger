"""T171: Global "Coaching disabled — check backend" banner.

When the coaching backend is unavailable (offline, mis-
configured, server down), the user has no way to know why
coaching widgets are quiet. T171 adds a frontend-only banner
to OverlayWindow.qml that renders prominently when the
``coachingDisabled`` flag is true.

The banner is wired to ``overlayVM.coachingDisabled`` — a VM
property the backend health check (or a settings toggle) can
drive. Default false → banner hidden, no behaviour change for
existing call sites.

File-content QML pin (rendering tests need a Qt visual context
the test runner doesn't have, established T141-T170 pattern).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_OVERLAY_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Overlay" / "OverlayWindow.qml"
)


@pytest.fixture(scope="module")
def overlay_qml() -> str:
    return _OVERLAY_PATH.read_text(encoding="utf-8")


def test_banner_includes_coaching_disabled_text(overlay_qml: str) -> None:
    """The banner uses the literal "Coaching disabled — check
    backend" string. Tolerant: case-insensitive on the prefix
    so the implementation can match Figma styling later."""
    assert re.search(
        r'Coaching disabled\s*[—–-]\s*check backend',
        overlay_qml,
        re.IGNORECASE,
    ), (
        "OverlayWindow must include the literal banner text "
        "`Coaching disabled — check backend`"
    )


def test_banner_visible_binding_uses_coaching_disabled(
    overlay_qml: str,
) -> None:
    """The banner visibility is bound to ``overlayVM
    .coachingDisabled``. Tolerant: any element using
    ``overlayVM.coachingDisabled`` in its visibility expression
    proves the wiring."""
    # Search for `visible:` line with `coachingDisabled` reference
    assert re.search(
        r'visible\s*:\s*[^\n]*overlayVM[^\n]*coachingDisabled',
        overlay_qml,
    ), (
        "An element must toggle visibility based on "
        "overlayVM.coachingDisabled (the coaching-disabled banner)"
    )
