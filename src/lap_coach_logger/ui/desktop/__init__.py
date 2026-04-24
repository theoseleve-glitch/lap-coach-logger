"""PySide6 desktop shell package."""

from __future__ import annotations

from lap_coach_logger.ui.desktop.overlay_browser import build_overlay_browser_frontend


def run_desktop_shell(*args, **kwargs):  # noqa: ANN002, ANN003
    from lap_coach_logger.ui.desktop.main_window import run_desktop_shell as _run_desktop_shell

    return _run_desktop_shell(*args, **kwargs)


__all__ = ["build_overlay_browser_frontend", "run_desktop_shell"]
