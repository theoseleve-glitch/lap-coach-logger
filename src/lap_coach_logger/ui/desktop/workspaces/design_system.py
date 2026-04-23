"""Shared design tokens for immersive desktop workspaces."""

from __future__ import annotations

from lap_coach_logger.ui.desktop.overlay_browser.design_system import (
    OverlayBrowserColorTokens as WorkspaceColorTokens,
    OverlayBrowserDesignTokens as WorkspaceDesignTokens,
    OverlayBrowserLayoutTokens as WorkspaceLayoutTokens,
    OverlayBrowserRadiusTokens as WorkspaceRadiusTokens,
    OverlayBrowserSpacingTokens as WorkspaceSpacingTokens,
    OverlayBrowserSurfaceTokens as WorkspaceSurfaceTokens,
    OverlayBrowserTypographyTokens as WorkspaceTypographyTokens,
    default_overlay_browser_tokens,
    rgba,
)


def default_workspace_tokens() -> WorkspaceDesignTokens:
    return default_overlay_browser_tokens()


__all__ = [
    "WorkspaceColorTokens",
    "WorkspaceDesignTokens",
    "WorkspaceLayoutTokens",
    "WorkspaceRadiusTokens",
    "WorkspaceSpacingTokens",
    "WorkspaceSurfaceTokens",
    "WorkspaceTypographyTokens",
    "default_workspace_tokens",
    "rgba",
]
