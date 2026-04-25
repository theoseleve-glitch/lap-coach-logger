"""T172: Global "Offline — local only" banner.

When the network is unavailable (sync upload paused, cloud
features unreachable), the user should see a clear "Offline"
indicator so they understand why upstream features (sharing,
cloud-side coaching, leaderboards) are quiet. T172 adds a
frontend-only banner to OverlayWindow.qml that renders when
the ``offline`` flag is true.

The banner is wired to ``overlayVM.offline`` — a VM property
driven by the network health check (or a settings toggle).
Default false → banner hidden, no behaviour change for
existing call sites.

File-content QML pin (same shape as T171 coaching-disabled
banner). Distinct from T171's red "coaching disabled" banner —
this one is yellow/marshal "offline — local only".
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


def test_banner_includes_offline_local_only_text(overlay_qml: str) -> None:
    """The banner uses the literal "Offline — local only"
    string. Tolerant: case-insensitive on the prefix and
    flexible on the dash style."""
    assert re.search(
        r'Offline\s*[—–-]\s*local only',
        overlay_qml,
        re.IGNORECASE,
    ), (
        "OverlayWindow must include the literal banner text "
        "`Offline — local only`"
    )


def test_banner_visible_binding_uses_offline(overlay_qml: str) -> None:
    """The banner visibility is bound to ``overlayVM.offline``.
    Tolerant: any element using ``overlayVM.offline`` in its
    visibility expression proves the wiring."""
    assert re.search(
        r'visible\s*:\s*[^\n]*overlayVM[^\n]*\.offline\b',
        overlay_qml,
    ), (
        "An element must toggle visibility based on "
        "overlayVM.offline (the offline banner)"
    )
