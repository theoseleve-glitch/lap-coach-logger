"""T215: UI polish — icon pack consistent.

Pins the visual-design contract for the overlay workspace icon
pack so a "visual review" passes deterministically:

  - All icons present in ``assets/overlay_workspace/icons/``
  - Each icon is a valid SVG with a 24×24 viewBox
  - Each uses the brand cream color ``#F3EFE7`` for stroke/fill
  - Each uses a stroke-width in the design-system range [1.4, 1.8]
  - Names are kebab-case lowercase (no underscores, no caps)
  - Every icon name referenced from production code exists on disk

Without this test, a single icon added with the wrong size /
color / casing would silently render the workspace nav
inconsistent — exactly the "visual review fails" symptom the
sprint task targets.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parent.parent
_ICONS_DIR = _REPO_ROOT / "assets" / "overlay_workspace" / "icons"

# Design-system constants — the brand defines these.
_BRAND_FOREGROUND_HEX = "#F3EFE7"
_VIEWBOX_EXPECTED = "0 0 24 24"
_STROKE_WIDTH_MIN = 1.4
_STROKE_WIDTH_MAX = 1.8

# Names referenced from production code (workspaces/common.py +
# overlay_browser/widgets.py) — must all exist as files.
# Updating production code without adding the icon would break
# the UI; updating the icon set without referencing it bloats
# the bundle. Either way this list catches drift.
_REFERENCED_ICON_NAMES = (
    "arrow-left",
    "arrow-right",
    "dashboard",
    "live",
    "logs",
    "history",
    "overlay",
)


# ---------------------------------------------------------------------------
# Icon presence + filesystem layout
# ---------------------------------------------------------------------------


def test_icons_directory_exists() -> None:
    """Foundational: the icon directory must exist where the
    asset resolver looks for it."""
    assert _ICONS_DIR.is_dir(), (
        f"icon directory missing: {_ICONS_DIR}"
    )


def test_icon_pack_is_non_empty() -> None:
    """If the directory is empty, every icon-rendering code path
    silently falls back to no-icon. Catch this immediately."""
    svgs = list(_ICONS_DIR.glob("*.svg"))
    assert len(svgs) > 0, (
        f"no SVG icons in {_ICONS_DIR} — workspace nav would render blank"
    )


def test_all_referenced_icons_exist_on_disk() -> None:
    """Every icon name referenced from production code must have
    a matching SVG file. Drift here = silently-blank nav buttons."""
    missing = []
    for name in _REFERENCED_ICON_NAMES:
        path = _ICONS_DIR / f"{name}.svg"
        if not path.exists():
            missing.append(name)
    assert not missing, (
        f"referenced icons missing from disk: {missing} — "
        f"workspace nav has hidden broken references"
    )


# ---------------------------------------------------------------------------
# Naming convention: kebab-case lowercase
# ---------------------------------------------------------------------------


_KEBAB_CASE_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def test_icon_names_are_kebab_case_lowercase() -> None:
    """Consistent naming = consistent lookups. A new ``Settings.svg``
    or ``arrow_left.svg`` would silently fail to resolve via the
    overlay_workspace_icon_path() helper which expects lowercase."""
    bad_names = []
    for svg in sorted(_ICONS_DIR.glob("*.svg")):
        stem = svg.stem
        if not _KEBAB_CASE_RE.match(stem):
            bad_names.append(stem)
    assert not bad_names, (
        f"icons with non-kebab-case names: {bad_names} — "
        f"convention is lowercase + hyphens (e.g., 'arrow-left')"
    )


# ---------------------------------------------------------------------------
# Visual-design contract: viewBox, color, stroke-width
# ---------------------------------------------------------------------------


def _all_svgs() -> list[Path]:
    return sorted(_ICONS_DIR.glob("*.svg"))


def test_all_icons_have_24x24_viewbox() -> None:
    """All icons MUST share a 24×24 viewBox so they line up at
    every render size. A 16×16 or 32×32 outlier would render at
    the wrong relative scale next to its neighbors."""
    bad = []
    for svg in _all_svgs():
        content = svg.read_text(encoding="utf-8")
        if f'viewBox="{_VIEWBOX_EXPECTED}"' not in content:
            bad.append(svg.name)
    assert not bad, (
        f"icons not on 24×24 viewBox: {bad} — would render at "
        f"wrong scale next to other icons"
    )


def test_all_icons_use_brand_foreground_color() -> None:
    """All icons MUST use the brand cream ``#F3EFE7`` as their
    stroke / fill. Hardcoded #FFF or theme-mismatched colors
    would render as visual outliers in the workspace nav."""
    bad = []
    for svg in _all_svgs():
        content = svg.read_text(encoding="utf-8")
        # Either as stroke or fill — both forms are accepted.
        if (
            f'stroke="{_BRAND_FOREGROUND_HEX}"' not in content
            and f'fill="{_BRAND_FOREGROUND_HEX}"' not in content
        ):
            bad.append(svg.name)
    assert not bad, (
        f"icons not using brand color {_BRAND_FOREGROUND_HEX}: "
        f"{bad} — would visually clash with consistent icons"
    )


_STROKE_WIDTH_RE = re.compile(r'stroke-width="([\d.]+)"')


def test_all_icons_use_stroke_width_in_design_range() -> None:
    """Stroke width must stay in the design-system range
    [1.4, 1.8] so icons read at consistent visual weight.
    A 0.5 or 3.0 stroke would either disappear or dominate."""
    bad: list[tuple[str, float]] = []
    for svg in _all_svgs():
        content = svg.read_text(encoding="utf-8")
        widths = [float(m.group(1)) for m in _STROKE_WIDTH_RE.finditer(content)]
        if not widths:
            # Some pure-fill icons may have no stroke at all (e.g.,
            # a solid dot). That's allowed.
            continue
        for w in widths:
            if not (_STROKE_WIDTH_MIN <= w <= _STROKE_WIDTH_MAX):
                bad.append((svg.name, w))
    assert not bad, (
        f"icons with stroke-width outside [{_STROKE_WIDTH_MIN}, "
        f"{_STROKE_WIDTH_MAX}]: {bad} — would render at "
        f"inconsistent visual weight"
    )


def test_all_icons_use_round_line_caps_when_specified() -> None:
    """When linecap is set, it must be 'round' — square or butt
    caps would jar against the rounded design system. Not all
    icons need a linecap (closed shapes don't), so missing
    linecap is allowed."""
    bad = []
    _LINECAP_RE = re.compile(r'stroke-linecap="([^"]+)"')
    for svg in _all_svgs():
        content = svg.read_text(encoding="utf-8")
        for m in _LINECAP_RE.finditer(content):
            if m.group(1) != "round":
                bad.append((svg.name, m.group(1)))
    assert not bad, (
        f"icons with non-round linecap: {bad} — design system "
        f"requires round caps for consistency"
    )


# ---------------------------------------------------------------------------
# Asset resolver integration
# ---------------------------------------------------------------------------


def test_resolver_finds_each_icon() -> None:
    """The overlay_workspace_icon_path() helper must return a
    real path for each icon. Catches accidental rename of either
    the file or the resolver-internal subpath."""
    from lap_coach_logger.assets import overlay_workspace_icon_path

    for name in _REFERENCED_ICON_NAMES:
        path = overlay_workspace_icon_path(name)
        assert path is not None, (
            f"resolver returned None for '{name}' — broken path "
            f"in overlay_workspace_icon_path()"
        )
        assert path.exists(), (
            f"resolver returned non-existent path for '{name}': {path}"
        )


def test_resolver_returns_none_for_unknown_icon() -> None:
    """Defensive check: unknown icon name → None (not raise),
    so callers can fall back to a no-icon button gracefully."""
    from lap_coach_logger.assets import overlay_workspace_icon_path

    path = overlay_workspace_icon_path("definitely-not-an-icon")
    assert path is None


def test_resolver_handles_empty_string() -> None:
    """Empty input → None — guards against accidental ``""``
    bindings from QML or settings."""
    from lap_coach_logger.assets import overlay_workspace_icon_path

    assert overlay_workspace_icon_path("") is None
    assert overlay_workspace_icon_path("   ") is None
