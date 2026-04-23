"""Design tokens for the immersive overlay workspace."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OverlayBrowserColorTokens:
    page_bg: str = "#06080B"
    page_bg_alt: str = "#0A0D12"
    rail_bg: str = "#0B1119"
    rail_bg_alt: str = "#101825"
    hero_bg: str = "#070A0E"
    controls_bg: str = "#0B0E13"
    dock_bg: str = "#0A0D11"
    canvas_bg: str = "#090C11"
    canvas_frame: str = "#121821"
    chalk: str = "#F2F4F7"
    steel: str = "#9AA5B4"
    text_muted: str = "#7C8695"
    text_dim: str = "#5E6673"
    pit_orange: str = "#C6A24C"
    safety_red: str = "#CE2D2D"
    marshal_yellow: str = "#E0AF47"
    acid_green: str = "#35C978"
    accent_blue: str = "#7A9ABD"
    line_soft: str = "#161B23"
    line: str = "#222933"
    line_strong: str = "#313946"


@dataclass(frozen=True, slots=True)
class OverlayBrowserTypographyTokens:
    display_family: str = "Space Grotesk"
    body_family: str = "Segoe UI"
    mono_family: str = "Consolas"
    hero_px: int = 24
    section_px: int = 17
    title_px: int = 14
    body_px: int = 12
    caption_px: int = 11
    micro_px: int = 10
    mono_px: int = 11


@dataclass(frozen=True, slots=True)
class OverlayBrowserSpacingTokens:
    xxs: int = 2
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 20
    xxl: int = 28


@dataclass(frozen=True, slots=True)
class OverlayBrowserRadiusTokens:
    xs: int = 4
    sm: int = 6
    md: int = 8
    lg: int = 12
    xl: int = 16


@dataclass(frozen=True, slots=True)
class OverlayBrowserSurfaceTokens:
    border_soft_alpha: float = 0.06
    border_mid_alpha: float = 0.10
    border_strong_alpha: float = 0.18
    fill_soft_alpha: float = 0.72
    fill_mid_alpha: float = 0.90
    fill_strong_alpha: float = 0.97
    shadow_alpha: float = 0.20
    shadow_blur_px: int = 14
    dot_grid_alpha: float = 0.035
    vignette_alpha: float = 0.22


@dataclass(frozen=True, slots=True)
class OverlayBrowserLayoutTokens:
    shell_margin_px: int = 18
    shell_gap_px: int = 18
    top_strip_height_px: int = 66
    sidebar_width_px: int = 342
    settings_width_px: int = 388
    hero_min_height_px: int = 620
    bottom_dock_height_px: int = 92
    overlay_shell_margin_px: int = 12
    overlay_pane_gap_px: int = 8
    overlay_top_strip_height_px: int = 44
    overlay_sidebar_width_px: int = 320
    overlay_settings_width_px: int = 360
    overlay_canvas_min_height_px: int = 480
    overlay_bottom_dock_height_px: int = 42
    overlay_list_row_height_px: int = 60
    overlay_inspector_label_width_px: int = 116
    overlay_canvas_frame_inset_px: int = 24
    overlay_control_height_px: int = 30
    overlay_tab_min_width_px: int = 92
    overlay_tab_max_width_px: int = 220


@dataclass(frozen=True, slots=True)
class OverlayBrowserDesignTokens:
    colors: OverlayBrowserColorTokens = OverlayBrowserColorTokens()
    typography: OverlayBrowserTypographyTokens = OverlayBrowserTypographyTokens()
    spacing: OverlayBrowserSpacingTokens = OverlayBrowserSpacingTokens()
    radii: OverlayBrowserRadiusTokens = OverlayBrowserRadiusTokens()
    surface: OverlayBrowserSurfaceTokens = OverlayBrowserSurfaceTokens()
    layout: OverlayBrowserLayoutTokens = OverlayBrowserLayoutTokens()


def default_overlay_browser_tokens() -> OverlayBrowserDesignTokens:
    return OverlayBrowserDesignTokens()


def rgba(hex_color: str, alpha: float) -> str:
    """Convert a #RRGGBB color to an rgba() stylesheet string."""

    value = str(hex_color).strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Expected 6-digit hex color, got '{hex_color}'")
    red = int(value[0:2], 16)
    green = int(value[2:4], 16)
    blue = int(value[4:6], 16)
    clamped = max(0.0, min(1.0, float(alpha)))
    return f"rgba({red}, {green}, {blue}, {clamped:.3f})"
