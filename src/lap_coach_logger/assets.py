"""Centralized asset resolution for runtime and packaging."""

from __future__ import annotations

from pathlib import Path

from lap_coach_logger.utils.paths import bundle_resource_path

APP_ICON_CANDIDATES = (
    "assets/branding/app.ico",
    "assets/icon.ico",
)
TRAY_ICON_CANDIDATES = (
    "assets/branding/tray.ico",
    "assets/branding/app.ico",
    "assets/icon.ico",
)
INSTALLER_ICON_CANDIDATES = (
    "assets/branding/installer.ico",
    "assets/branding/app.ico",
    "assets/icon.ico",
)
ABOUT_ART_CANDIDATES = (
    "assets/branding/about-panel.txt",
)
MONOGRAM_CANDIDATES = (
    "assets/branding/monogram.svg",
)
OVERLAY_WORKSPACE_HERO_CANDIDATES = (
    "assets/overlay_workspace/hero-placeholder.svg",
)


def resolve_asset(*candidates: str) -> Path | None:
    for candidate in candidates:
        path = bundle_resource_path(candidate)
        if path.exists():
            return path
    return None


def app_icon_path() -> Path | None:
    return resolve_asset(*APP_ICON_CANDIDATES)


def tray_icon_path() -> Path | None:
    return resolve_asset(*TRAY_ICON_CANDIDATES)


def installer_icon_path() -> Path | None:
    return resolve_asset(*INSTALLER_ICON_CANDIDATES)


def about_art_path() -> Path | None:
    return resolve_asset(*ABOUT_ART_CANDIDATES)


def monogram_path() -> Path | None:
    return resolve_asset(*MONOGRAM_CANDIDATES)


def overlay_workspace_hero_path() -> Path | None:
    """Return the hero/banner image for the overlay workspace panel."""
    return resolve_asset(*OVERLAY_WORKSPACE_HERO_CANDIDATES)


def overlay_workspace_icon_path(name: str) -> Path | None:
    """Return the icon for a named workspace section."""
    cleaned = str(name or "").strip()
    if not cleaned:
        return None
    return resolve_asset(f"assets/overlay_workspace/icons/{cleaned}.svg")


def qml_dir() -> Path:
    """Return the root QML directory (for QQmlApplicationEngine import paths)."""
    candidate = bundle_resource_path("src/lap_coach_logger/qml")
    if candidate.exists():
        return candidate
    return Path(__file__).parent / "qml"
