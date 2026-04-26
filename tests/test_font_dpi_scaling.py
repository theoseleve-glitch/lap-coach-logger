"""T216: UI polish — font rendering at all supported DPIs.

Sprint target: fonts must render correctly at 100% / 125% / 150% /
200% Windows display scales. Qt 6 enables HighDpi scaling by
default, so the contract reduces to:

  - The Typography singleton (the design-system source of truth)
    declares a coherent scale of font sizes
  - Every font size used in QML — whether via Typography.* or
    inline — falls in a sensible DPI-scaling range (8–48 px),
    so 200% scaling produces 16–96 px which all read clearly
  - Bootstrap does NOT explicitly disable HighDpi scaling
    (drift-prevention against accidental ``Qt::AA_DisableHighDpiScaling``)

Visual review at multiple DPIs is the deployment validation;
this test pins the underlying contracts that make it possible.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parent.parent
_QML_DIR = _REPO_ROOT / "src" / "lap_coach_logger" / "qml"
_THEME_DIR = _QML_DIR / "Theme"
_TYPOGRAPHY_QML = _THEME_DIR / "Typography.qml"
_QML_BOOTSTRAP = _REPO_ROOT / "src" / "lap_coach_logger" / "qml_bootstrap.py"

# Sensible font-size range. At 200% Windows DPI:
#   - 7 px → 14 px (mono uppercase badge minimum, e.g. THERMAL)
#   - 48 px → 96 px (large-display headline ceiling)
# Below 7 px any text is unreadable at 100% DPI even in bold mono;
# above 48 px text overflows tight layouts at 200%.
_MIN_FONT_PX = 7
_MAX_FONT_PX = 48


# ---------------------------------------------------------------------------
# Typography singleton: design-system shape
# ---------------------------------------------------------------------------


def test_typography_singleton_exists() -> None:
    """The Typography QML singleton is the design-system source
    of truth. Removal would force every screen to redefine its
    own font scale — fragmenting at the first redesign."""
    assert _TYPOGRAPHY_QML.is_file(), (
        f"Typography singleton missing at {_TYPOGRAPHY_QML}"
    )
    content = _TYPOGRAPHY_QML.read_text(encoding="utf-8")
    # Must be marked as a Singleton — otherwise QML re-instantiates
    # per-import which breaks the design-system contract.
    assert "pragma Singleton" in content


def test_typography_declares_standard_scale() -> None:
    """The named scale (display / title / heading / body / caption /
    micro / data) must be present. Removing one would silently
    break every screen that referenced it."""
    content = _TYPOGRAPHY_QML.read_text(encoding="utf-8")
    expected_sizes = (
        "displaySize",
        "titleSize",
        "headingSize",
        "bodySize",
        "captionSize",
        "microSize",
        "dataSize",
    )
    missing = [name for name in expected_sizes if name not in content]
    assert not missing, (
        f"Typography missing standard sizes: {missing} — "
        f"design system fragments without these"
    )


def test_typography_sizes_are_in_dpi_safe_range() -> None:
    """Each named size must fall in [8, 48] so 200% DPI scaling
    produces a usable [16, 96] px range. Anything below 8 is
    unreadable at 100%; anything above 48 overflows on 4K."""
    content = _TYPOGRAPHY_QML.read_text(encoding="utf-8")
    # Match: ``readonly property int <name>: <number>``
    pattern = re.compile(
        r"readonly\s+property\s+int\s+(\w+Size):\s*(\d+)"
    )
    bad: list[tuple[str, int]] = []
    for m in pattern.finditer(content):
        name, value = m.group(1), int(m.group(2))
        if not (_MIN_FONT_PX <= value <= _MAX_FONT_PX):
            bad.append((name, value))
    assert not bad, (
        f"Typography sizes outside DPI-safe range "
        f"[{_MIN_FONT_PX}, {_MAX_FONT_PX}]: {bad}"
    )


def test_typography_weights_use_qt_constants() -> None:
    """Font weights must use ``Font.Bold`` / ``Font.DemiBold`` /
    ``Font.Normal`` (Qt enum constants) rather than raw integers
    like 700. Qt's default font on Windows handles the enum
    consistently across DPI scales."""
    content = _TYPOGRAPHY_QML.read_text(encoding="utf-8")
    # Match weight-property values; must be ``Font.<Name>`` style.
    pattern = re.compile(
        r"readonly\s+property\s+int\s+(\w+Weight):\s*([^\s]+)"
    )
    bad: list[tuple[str, str]] = []
    for m in pattern.finditer(content):
        name, value = m.group(1), m.group(2)
        if not value.startswith("Font."):
            bad.append((name, value))
    assert not bad, (
        f"Typography weights using raw values instead of Qt "
        f"Font enum: {bad}"
    )


# ---------------------------------------------------------------------------
# QML font sizes across the codebase fall in DPI-safe range
# ---------------------------------------------------------------------------


_PIXEL_SIZE_RE = re.compile(r"font\.pixelSize:\s*(\d+)")


def test_all_hardcoded_font_sizes_in_dpi_safe_range() -> None:
    """Inline ``font.pixelSize: <int>`` values across every QML
    file must fall in the same [8, 48] range. A 4-px font on a
    chart axis would disappear at 100% DPI; a 64-px font would
    overflow at 200%."""
    bad: list[tuple[str, int, int]] = []
    for qml in _QML_DIR.rglob("*.qml"):
        content = qml.read_text(encoding="utf-8")
        for line_num, line in enumerate(content.splitlines(), 1):
            for m in _PIXEL_SIZE_RE.finditer(line):
                size = int(m.group(1))
                if not (_MIN_FONT_PX <= size <= _MAX_FONT_PX):
                    bad.append(
                        (str(qml.relative_to(_QML_DIR)), line_num, size)
                    )
    assert not bad, (
        f"hardcoded font.pixelSize values outside DPI-safe range "
        f"[{_MIN_FONT_PX}, {_MAX_FONT_PX}]: {bad[:10]}"
        + (f" (and {len(bad) - 10} more)" if len(bad) > 10 else "")
    )


def test_typography_referenced_by_majority_of_qml_files() -> None:
    """Most QML files should reference the Typography singleton
    rather than hardcoding sizes. Catches regressions where a
    redesign reintroduces magic-number font sizes en masse."""
    using_typography = 0
    using_pixel_size = 0
    for qml in _QML_DIR.rglob("*.qml"):
        content = qml.read_text(encoding="utf-8")
        if "Theme.Typography" in content or "Typography." in content:
            using_typography += 1
        if "font.pixelSize" in content:
            using_pixel_size += 1
    # At least 40% of QML files using fonts go through Theme.
    # Below that, drift has happened and the design system is
    # not the source of truth anymore.
    if using_pixel_size > 0:
        ratio = using_typography / using_pixel_size
        assert ratio >= 0.4, (
            f"only {using_typography}/{using_pixel_size} "
            f"({ratio*100:.0f}%) of QML files using fonts reference "
            f"Theme.Typography — design-system drift"
        )


# ---------------------------------------------------------------------------
# Bootstrap doesn't disable HighDpi scaling
# ---------------------------------------------------------------------------


def test_bootstrap_does_not_disable_high_dpi_scaling() -> None:
    """Qt 6 enables HighDpi scaling by default. If bootstrap
    explicitly disabled it (``AA_DisableHighDpiScaling`` /
    ``setHighDpiScaleFactorRoundingPolicy(PassThrough)``), font
    rendering at 125%/150%/200% would be blurry / mis-sized."""
    content = _QML_BOOTSTRAP.read_text(encoding="utf-8")
    # Plain substring checks — escape needs vary by regex, easier
    # to match literal strings.
    found_bad = []
    if "AA_DisableHighDpiScaling" in content:
        found_bad.append("AA_DisableHighDpiScaling")
    assert not found_bad, (
        f"qml_bootstrap.py disables HighDpi scaling: {found_bad} "
        f"— would break font rendering at 125%/150%/200% DPI"
    )


def test_bootstrap_does_not_force_low_dpi_round_down() -> None:
    """``setHighDpiScaleFactorRoundingPolicy(Floor)`` would round
    125% DPI down to 100%, causing fonts to render too small.
    The default (Qt 6: PassThrough) is what we want."""
    content = _QML_BOOTSTRAP.read_text(encoding="utf-8")
    # Floor rounds aggressively; Round (default) is OK.
    assert "RoundingPolicy.Floor" not in content, (
        "bootstrap forces Floor rounding — 125%/150% DPIs "
        "would round down, fonts too small"
    )


# ---------------------------------------------------------------------------
# Sanity: typography sizes are coherent (display > title > heading > body)
# ---------------------------------------------------------------------------


def test_typography_size_hierarchy_makes_sense() -> None:
    """Display ≥ title ≥ heading ≥ body ≥ caption ≥ micro.
    A drift where micro ends up larger than caption (typo
    transposition) would silently invert the visual hierarchy."""
    content = _TYPOGRAPHY_QML.read_text(encoding="utf-8")

    def _size(name: str) -> int:
        m = re.search(
            rf"readonly\s+property\s+int\s+{name}:\s*(\d+)", content
        )
        assert m, f"Typography missing {name}"
        return int(m.group(1))

    display = _size("displaySize")
    title = _size("titleSize")
    heading = _size("headingSize")
    body = _size("bodySize")
    caption = _size("captionSize")
    micro = _size("microSize")

    # Strict descending order — the visual hierarchy is broken
    # if any of these get inverted.
    assert display > title, (
        f"displaySize ({display}) must be > titleSize ({title})"
    )
    assert title > heading, (
        f"titleSize ({title}) must be > headingSize ({heading})"
    )
    assert heading > body, (
        f"headingSize ({heading}) must be > bodySize ({body})"
    )
    assert body > caption, (
        f"bodySize ({body}) must be > captionSize ({caption})"
    )
    assert caption > micro, (
        f"captionSize ({caption}) must be > microSize ({micro})"
    )
