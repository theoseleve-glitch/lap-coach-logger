"""Qt overlay browser frontend package."""

from __future__ import annotations

from lap_coach_logger.ui.desktop.overlay_browser.controller import (
    OverlayBrowserPageController,
    OverlayBrowserPreviewCardModel,
    OverlayBrowserPreviewStat,
)
from lap_coach_logger.ui.desktop.overlay_browser.design_system import (
    OverlayBrowserDesignTokens,
    default_overlay_browser_tokens,
)
from lap_coach_logger.ui.desktop.overlay_browser.integration import (
    OverlayBrowserFrontend,
    build_overlay_browser_frontend,
)
from lap_coach_logger.ui.desktop.overlay_browser.page import OverlayBrowserPage, OverlayWorkspaceShellCallbacks
from lap_coach_logger.ui.desktop.overlay_browser.settings_renderer import (
    AccordionSection,
    OverlaySettingsFormRenderer,
)
from lap_coach_logger.ui.desktop.overlay_browser.widgets import (
    BottomActionBar,
    GlassPanel,
    OverlaySettingsPanel,
    OverlaySidebar,
    OverlayWorkspaceTopStrip,
    PreviewCanvas,
    SearchFilterBar,
)

__all__ = [
    "AccordionSection",
    "BottomActionBar",
    "GlassPanel",
    "OverlayBrowserDesignTokens",
    "OverlayBrowserFrontend",
    "OverlayBrowserPage",
    "OverlayBrowserPageController",
    "OverlayBrowserPreviewCardModel",
    "OverlayBrowserPreviewStat",
    "OverlaySettingsFormRenderer",
    "OverlaySettingsPanel",
    "OverlaySidebar",
    "OverlayWorkspaceShellCallbacks",
    "OverlayWorkspaceTopStrip",
    "PreviewCanvas",
    "SearchFilterBar",
    "build_overlay_browser_frontend",
    "default_overlay_browser_tokens",
]
