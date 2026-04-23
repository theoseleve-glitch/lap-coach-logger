"""Immersive desktop workspaces for the LAP COACH shell.

Uses lazy re-exports via ``__getattr__`` to avoid a circular import:
``panels.py`` imports ``workspaces.telemetry_widgets`` directly, and
would otherwise re-trigger the full workspace tree load through
eager imports here. Each workspace module still imports ``panels``
freely — we just stop forcing them all to load on package import.

Callers use ``from lap_coach_logger.ui.desktop.workspaces import DashboardPanel``
exactly as before; the resolution happens on first access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lap_coach_logger.ui.desktop.workspaces.common import WorkspaceShellCallbacks
    from lap_coach_logger.ui.desktop.workspaces.dashboard import DashboardWorkspace as DashboardPanel
    from lap_coach_logger.ui.desktop.workspaces.history import HistoryWorkspace as HistoryPanel
    from lap_coach_logger.ui.desktop.workspaces.live import LiveWorkspace as LivePanel
    from lap_coach_logger.ui.desktop.workspaces.logs import LogsWorkspace as LogsPanel
    from lap_coach_logger.ui.desktop.workspaces.review import ReviewWorkspace as ReviewPanel


__all__ = [
    "DashboardPanel",
    "HistoryPanel",
    "LivePanel",
    "LogsPanel",
    "ReviewPanel",
    "WorkspaceShellCallbacks",
]


# Map exposed names to their (module, attr) source so ``__getattr__``
# can resolve them on first access.
_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "DashboardPanel": ("lap_coach_logger.ui.desktop.workspaces.dashboard", "DashboardWorkspace"),
    "HistoryPanel":   ("lap_coach_logger.ui.desktop.workspaces.history",   "HistoryWorkspace"),
    "LivePanel":      ("lap_coach_logger.ui.desktop.workspaces.live",      "LiveWorkspace"),
    "LogsPanel":      ("lap_coach_logger.ui.desktop.workspaces.logs",      "LogsWorkspace"),
    "ReviewPanel":    ("lap_coach_logger.ui.desktop.workspaces.review",    "ReviewWorkspace"),
    "WorkspaceShellCallbacks": (
        "lap_coach_logger.ui.desktop.workspaces.common", "WorkspaceShellCallbacks",
    ),
}


def __getattr__(name: str):  # noqa: ANN202 — module-level __getattr__ (PEP 562)
    try:
        module_path, attr = _LAZY_IMPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module 'workspaces' has no attribute {name!r}") from exc
    import importlib
    module = importlib.import_module(module_path)
    value = getattr(module, attr)
    globals()[name] = value  # cache on the module so future access is direct
    return value
