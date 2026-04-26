"""T217: UI polish — dark theme consistency.

Pins the dark-theme contract via the ``Theme.Tokens`` singleton:

  - 4-tier surface elevation (void → surface → elevated → raised)
    is monotonic-darker so panels read as nested correctly
  - All surface colors are genuinely dark (low luminance) — no
    accidental light grey leaking into the palette
  - The 8 px spacing grid is internally consistent (multiples of 4)
  - Border-radius scale is monotonic
  - QML files don't hardcode dark-theme-violating colors
    (#FFF / #FFFFFF / pure white) outside the chalk accent

"No artifacts" is what a visual review checks; this file pins the
underlying contracts that make the absence of artifacts deterministic.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parent.parent
_QML_DIR = _REPO_ROOT / "src" / "lap_coach_logger" / "qml"
_TOKENS_QML = _QML_DIR / "Theme" / "Tokens.qml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_HEX_COLOR_RE = re.compile(r'"#([0-9A-Fa-f]{6,8})"')


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Parse 6 or 8-hex string (#RRGGBB or #AARRGGBB) → RGB."""
    s = hex_str.lstrip("#")
    if len(s) == 8:
        s = s[2:]  # drop alpha (Qt uses #AARRGGBB)
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    return (r, g, b)


def _luminance(hex_str: str) -> float:
    """Approximate relative luminance (0-255 scale)."""
    r, g, b = _hex_to_rgb(hex_str)
    # ITU-R BT.601 weights — close enough for "dark vs light".
    return 0.299 * r + 0.587 * g + 0.114 * b


def _read_token_color(content: str, name: str) -> str:
    """Extract a named token's color hex from Tokens.qml."""
    pattern = rf'readonly\s+property\s+color\s+{name}_?\s*:\s*"(#[0-9A-Fa-f]+)"'
    m = re.search(pattern, content)
    if m is None:
        return ""
    return m.group(1)


# ---------------------------------------------------------------------------
# Tokens singleton: 4-tier dark surface scale
# ---------------------------------------------------------------------------


def test_tokens_singleton_exists() -> None:
    """The Tokens singleton is the design-system source of truth
    for colors, spacing, and radii."""
    assert _TOKENS_QML.is_file(), (
        f"Tokens singleton missing at {_TOKENS_QML}"
    )
    content = _TOKENS_QML.read_text(encoding="utf-8")
    assert "pragma Singleton" in content


def test_surface_elevation_4_tier_present() -> None:
    """Dark theme defines 4 surface tiers. Removing any tier
    would force panels to fall back to ad-hoc greys."""
    content = _TOKENS_QML.read_text(encoding="utf-8")
    expected = ("void", "surface", "elevated", "raised")
    missing = []
    for name in expected:
        # void uses trailing underscore in QML (reserved word avoidance).
        suffix = "_" if name == "void" else ""
        if not re.search(
            rf'readonly\s+property\s+color\s+{name}{suffix}\s*:',
            content,
        ):
            missing.append(name)
    assert not missing, (
        f"Tokens missing surface tiers: {missing} — "
        f"dark theme cannot render layered panels"
    )


def test_surface_colors_are_dark() -> None:
    """All surface tiers must be dark (luminance < 50/255 ≈ 20%
    of white). A 'surface' that's actually mid-grey would
    catastrophically clash with the rest of the dark UI."""
    content = _TOKENS_QML.read_text(encoding="utf-8")
    too_light = []
    for name in ("void", "surface", "elevated", "raised"):
        suffix = "_" if name == "void" else ""
        # Match the trailing-underscore form too.
        m = re.search(
            rf'readonly\s+property\s+color\s+{name}{suffix}\s*:\s*"(#[0-9A-Fa-f]+)"',
            content,
        )
        if m is None:
            continue
        hex_str = m.group(1)
        lum = _luminance(hex_str)
        # 50 / 255 ≈ 0.20 — anything brighter is no longer "dark surface"
        if lum >= 50:
            too_light.append((name, hex_str, lum))
    assert not too_light, (
        f"surface tiers brighter than dark-theme target: {too_light} "
        f"— theme would render as mid-grey"
    )


def test_surface_elevation_is_monotonic_darker_to_lighter() -> None:
    """Layered panels rely on void < surface < elevated < raised
    (darker → lighter). If raised happened to be darker than void,
    the visual depth cue inverts and panels read flat or wrong."""
    content = _TOKENS_QML.read_text(encoding="utf-8")
    void_lum = _luminance(_read_token_color(content, "void"))
    surface_lum = _luminance(_read_token_color(content, "surface"))
    elevated_lum = _luminance(_read_token_color(content, "elevated"))
    raised_lum = _luminance(_read_token_color(content, "raised"))
    assert void_lum < surface_lum, (
        f"void ({void_lum:.1f}) must be darker than surface "
        f"({surface_lum:.1f})"
    )
    assert surface_lum < elevated_lum, (
        f"surface ({surface_lum:.1f}) must be darker than elevated "
        f"({elevated_lum:.1f})"
    )
    assert elevated_lum < raised_lum, (
        f"elevated ({elevated_lum:.1f}) must be darker than raised "
        f"({raised_lum:.1f})"
    )


# ---------------------------------------------------------------------------
# Accent palette: contract for the named colors
# ---------------------------------------------------------------------------


def test_accent_palette_present() -> None:
    """Named accent colors anchor every alert / state visualisation.
    Removing one would force ad-hoc colors at the call site."""
    content = _TOKENS_QML.read_text(encoding="utf-8")
    expected = (
        "chalk", "steel", "pitOrange", "acidGreen",
        "safetyRed", "marshalYellow",
    )
    missing = []
    for name in expected:
        if not re.search(
            rf'readonly\s+property\s+color\s+{name}\s*:',
            content,
        ):
            missing.append(name)
    assert not missing, (
        f"accent palette missing: {missing} — "
        f"alerts and state visualisations rely on these"
    )


def test_chalk_is_the_only_near_white_token() -> None:
    """Dark theme has exactly one near-white color (chalk, the
    foreground). Adding another light token would create
    dark-theme inconsistency — multiple "what's the foreground"
    answers."""
    content = _TOKENS_QML.read_text(encoding="utf-8")
    # Find every property color line.
    pattern = re.compile(
        r'readonly\s+property\s+color\s+(\w+)_?\s*:\s*"(#[0-9A-Fa-f]+)"'
    )
    near_white = []
    for m in pattern.finditer(content):
        name = m.group(1)
        hex_str = m.group(2)
        if _luminance(hex_str) >= 200:  # quite light
            near_white.append((name, hex_str))
    # chalk is allowed; nothing else.
    near_white_names = [n for n, _ in near_white]
    assert near_white_names == ["chalk"] or near_white_names == [], (
        f"multiple near-white tokens detected: {near_white} — "
        f"only chalk should be near-white in dark theme"
    )


# ---------------------------------------------------------------------------
# Spacing grid: 8px base, all values multiples of 4
# ---------------------------------------------------------------------------


def test_spacing_grid_multiples_of_four() -> None:
    """The spacing grid must use multiples of 4 px so adjacent
    tokens align on the same baseline. Off-grid values cause
    1-2 px misalignment that reads as 'jittery layout'."""
    content = _TOKENS_QML.read_text(encoding="utf-8")
    pattern = re.compile(
        r'readonly\s+property\s+int\s+(xs|sm|md|lg|xl|xxl|xxxl|xxxxl)\s*:\s*(\d+)'
    )
    bad = []
    for m in pattern.finditer(content):
        name = m.group(1)
        value = int(m.group(2))
        if value % 4 != 0:
            bad.append((name, value))
    assert not bad, (
        f"spacing grid off-4: {bad} — alignment will jitter"
    )


def test_spacing_grid_is_monotonic() -> None:
    """xs < sm < md < lg < xl < xxl. A flipped pair would
    silently reverse layout density (e.g., xxl ending up
    smaller than lg)."""
    content = _TOKENS_QML.read_text(encoding="utf-8")

    def _spacing(name: str) -> int:
        m = re.search(
            rf'readonly\s+property\s+int\s+{name}\s*:\s*(\d+)', content
        )
        assert m, f"spacing token missing: {name}"
        return int(m.group(1))

    sizes = [_spacing(n) for n in ("xs", "sm", "md", "lg", "xl", "xxl")]
    for i in range(1, len(sizes)):
        assert sizes[i] > sizes[i - 1], (
            f"spacing tokens not monotonic at index {i}: {sizes}"
        )


# ---------------------------------------------------------------------------
# Border radius: monotonic + bounded
# ---------------------------------------------------------------------------


def test_border_radius_is_monotonic() -> None:
    """radiusSm < radiusMd < radiusLg < radiusXl. Violation
    would cause smaller-named tokens to render rounder than
    larger-named ones."""
    content = _TOKENS_QML.read_text(encoding="utf-8")

    def _radius(name: str) -> int:
        m = re.search(
            rf'readonly\s+property\s+int\s+{name}\s*:\s*(\d+)', content
        )
        assert m, f"radius token missing: {name}"
        return int(m.group(1))

    sm = _radius("radiusSm")
    md = _radius("radiusMd")
    lg = _radius("radiusLg")
    xl = _radius("radiusXl")
    assert sm < md < lg < xl, (
        f"radius tokens not monotonic: sm={sm}, md={md}, "
        f"lg={lg}, xl={xl}"
    )


# ---------------------------------------------------------------------------
# QML files don't hardcode pure white (would jar against dark theme)
# ---------------------------------------------------------------------------


_PURE_WHITE_LITERALS = ('"#FFFFFF"', '"#ffffff"', '"#FFF"', '"#fff"')


def test_qml_avoids_pure_white_literals() -> None:
    """Hardcoded pure white in QML clashes with the chalk-on-dark
    palette and makes the dark theme inconsistent. Use
    ``Theme.Tokens.chalk`` (which is the off-white #F0EDE5)."""
    bad: list[tuple[str, int, str]] = []
    for qml in _QML_DIR.rglob("*.qml"):
        # Skip Theme/Tokens.qml itself — it defines the palette.
        if qml.name == "Tokens.qml":
            continue
        content = qml.read_text(encoding="utf-8")
        for line_num, line in enumerate(content.splitlines(), 1):
            stripped = line.split("//", 1)[0]  # strip comments
            for literal in _PURE_WHITE_LITERALS:
                if literal in stripped:
                    bad.append(
                        (str(qml.relative_to(_QML_DIR)), line_num, literal)
                    )
    assert not bad, (
        f"pure-white literals in QML (use Theme.Tokens.chalk instead): "
        f"{bad[:5]}" + (f" (and {len(bad) - 5} more)" if len(bad) > 5 else "")
    )


# ---------------------------------------------------------------------------
# Tokens singleton is referenced by majority of QML files
# ---------------------------------------------------------------------------


def test_tokens_referenced_by_majority_of_qml_files() -> None:
    """Most QML files using colors should reference Theme.Tokens
    rather than hardcoding hex. Drift here = palette inconsistency
    that no visual review can untangle."""
    using_tokens = 0
    using_hardcoded_color = 0
    for qml in _QML_DIR.rglob("*.qml"):
        if qml.name == "Tokens.qml":
            continue
        content = qml.read_text(encoding="utf-8")
        if "Theme.Tokens" in content or "Tokens." in content:
            using_tokens += 1
        # Match `color: "#xxxxxx"` or `Color.fromString("#xxx")`.
        if re.search(r'color\s*:\s*"#', content):
            using_hardcoded_color += 1
    if using_hardcoded_color > 0:
        ratio = using_tokens / max(using_hardcoded_color, 1)
        # At least 50% of QML files using colors should reference
        # Theme.Tokens. Below that, drift is significant.
        assert ratio >= 0.5, (
            f"only {using_tokens}/{using_hardcoded_color} "
            f"({ratio*100:.0f}%) of QML files using colors reference "
            f"Theme.Tokens — palette consistency drift"
        )
