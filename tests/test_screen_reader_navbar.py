"""T221: Accessibility — screen reader (NVDA on Windows) sees the
primary navigation surface.

QML's custom widgets (MouseArea-on-Rectangle "buttons") are
opaque to screen readers by default — Qt synthesizes nothing
because there's no QML control type to map to. Without explicit
``Accessible.role`` / ``Accessible.name`` attached properties,
NVDA on Windows reads our nav tabs and gear button as silence.

This test pins the contract on ``NavBar.qml`` (the only surface a
screen-reader user MUST traverse to use the app):

  - Every clickable element declares ``Accessible.role``
  - Every clickable element declares ``Accessible.name``
  - Specific names exist for the gear/pause/overlay/mode buttons
    so users hear "Settings button" rather than "rectangle"
  - The 5 nav tabs share an ``Accessible.role`` declaration in
    the Repeater delegate (one decl, applied per tab)

Manual NVDA verification on a real machine is still required to
ship the feature — this test catches the regression where an
``Accessible.*`` declaration is removed or forgotten on a new
button. CI cannot speak to a sound card.
"""
from __future__ import annotations

import re
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_NAVBAR = _REPO_ROOT / "src" / "lap_coach_logger" / "qml" / "Components" / "NavBar.qml"


def _read_navbar() -> str:
    assert _NAVBAR.exists(), f"missing NavBar.qml: {_NAVBAR}"
    return _NAVBAR.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Coverage: every interactive surface has an Accessible declaration
# ---------------------------------------------------------------------------


def test_navbar_declares_accessible_role() -> None:
    """At least one ``Accessible.role`` declaration must exist —
    a NavBar with zero is invisible to screen readers."""
    src = _read_navbar()
    assert "Accessible.role" in src, (
        "NavBar.qml has no Accessible.role declarations — every "
        "click target is opaque to NVDA"
    )


def test_navbar_declares_accessible_name() -> None:
    """At least one ``Accessible.name`` declaration must exist —
    role alone tells NVDA "button" but not which button."""
    src = _read_navbar()
    assert "Accessible.name" in src, (
        "NavBar.qml has no Accessible.name declarations — NVDA "
        "would announce 'button' with no label for every tab"
    )


def test_navbar_has_accessible_decls_for_each_click_target() -> None:
    """Count check: NavBar has 5 distinct primary interactive
    surfaces (5 nav tabs share one delegate decl + pause + overlay
    + mode dropdown + settings gear = 5 declarations minimum).

    The Repeater delegate counts as ONE Accessible.role decl
    even though it renders 5 tabs at runtime.
    """
    src = _read_navbar()
    role_decls = re.findall(r"Accessible\.role\s*:", src)
    # 1 (tabs delegate) + 1 (pause) + 1 (overlay toggle)
    # + 1 (mode dropdown) + 1 (settings gear) = 5 minimum.
    assert len(role_decls) >= 5, (
        f"NavBar.qml has only {len(role_decls)} Accessible.role "
        f"declarations; expected >= 5 (tabs delegate + pause + "
        f"overlay + mode + settings)"
    )


def test_navbar_role_count_matches_name_count() -> None:
    """Every role declaration should have a paired name —
    otherwise NVDA reads "button" with no useful label."""
    src = _read_navbar()
    role_count = len(re.findall(r"Accessible\.role\s*:", src))
    name_count = len(re.findall(r"Accessible\.name\s*:", src))
    assert role_count == name_count, (
        f"NavBar.qml has {role_count} Accessible.role decls but "
        f"{name_count} Accessible.name decls — every role needs a name"
    )


# ---------------------------------------------------------------------------
# Specific labels: critical buttons must be announceable by name
# ---------------------------------------------------------------------------


def test_navbar_settings_button_has_accessible_name() -> None:
    """The settings gear is a unicode glyph (\\u2699) with no text
    label — without Accessible.name, NVDA says 'button' or
    nothing. Must explicitly say 'Settings'."""
    src = _read_navbar()
    # Loose: any Accessible.name with "Settings" as substring.
    pattern = r'Accessible\.name\s*:\s*"[^"]*[Ss]ettings'
    assert re.search(pattern, src), (
        "NavBar.qml settings gear button is missing "
        'Accessible.name: "Settings" — NVDA cannot announce it'
    )


def test_navbar_pause_button_has_accessible_name() -> None:
    """The PAUSE button has visible text but for consistency
    declares Accessible.name explicitly so screen readers always
    hear the same label regardless of visible-text rendering."""
    src = _read_navbar()
    pattern = r'Accessible\.name\s*:\s*"[^"]*[Pp]ause'
    assert re.search(pattern, src), (
        "NavBar.qml pause button is missing Accessible.name "
        'containing "Pause"'
    )


def test_navbar_overlay_toggle_has_accessible_name() -> None:
    """The OVERLAY toggle needs a screen-reader-friendly name
    (single word "Overlay" reads ambiguously, so the contract
    is "overlay toggle" or "Toggle overlays" or similar — we
    just pin that "overlay" appears in the name)."""
    src = _read_navbar()
    pattern = r'Accessible\.name\s*:\s*"[^"]*[Oo]verlay'
    assert re.search(pattern, src), (
        "NavBar.qml overlay toggle is missing an Accessible.name "
        'containing "overlay"'
    )


def test_navbar_tab_delegate_uses_modelData_label_for_name() -> None:
    """Each of the 5 nav tabs must announce its own label
    (Dashboard / Live / Strategy / History / Overlays). The
    Repeater delegate has access to ``modelData.label`` — the
    Accessible.name MUST reference it (not a hard-coded string)
    so all 5 tabs differ."""
    src = _read_navbar()
    # The Accessible.name in the tabs delegate must reference
    # modelData.label (the per-row label property).
    pattern = r"Accessible\.name\s*:\s*[^\"\n]*modelData\.label"
    assert re.search(pattern, src), (
        "NavBar.qml tab delegate Accessible.name must reference "
        "modelData.label so each of the 5 tabs announces a unique "
        "label to NVDA"
    )


# ---------------------------------------------------------------------------
# Role values: announce as buttons / page tabs (not generic items)
# ---------------------------------------------------------------------------


def test_navbar_uses_button_or_pagetab_roles() -> None:
    """Roles must be Button or PageTab — declaring
    Accessible.role: Accessible.NoRole would tell NVDA to skip
    the element entirely, defeating the point."""
    src = _read_navbar()
    role_values = re.findall(r"Accessible\.role\s*:\s*([\w.]+)", src)
    valid = {"Accessible.Button", "Accessible.PageTab"}
    bad = [v for v in role_values if v not in valid]
    assert not bad, (
        f"NavBar.qml has Accessible.role values outside the valid "
        f"set {sorted(valid)}: {bad}"
    )
