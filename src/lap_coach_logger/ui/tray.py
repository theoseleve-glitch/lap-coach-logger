"""System-tray integration using pystray.

Provides the tray icon with a context menu for:
  - Viewing current status and last session info
  - Start / Stop monitoring
  - Opening the settings window
  - Opening the session output folder
  - Opening the log folder
  - Exiting the app

The icon runs on its own thread; all Tk/CTk interactions are
dispatched back to the main thread via a callback queue.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw
import pystray

from lap_coach_logger import APP_NAME, __version__
from lap_coach_logger.utils.paths import bundle_resource_path

log = logging.getLogger(__name__)

# Status label → human-readable display
_STATUS_LABELS: dict[str, str] = {
    "idle": "Idle",
    "detected": "Sim Detected",
    "waiting_for_session": "Waiting for Session",
    "recording": "Logging Session",
    "finalizing": "Finalizing Save",
    "cooldown": "Cooldown",
    "error": "Error",
}


def _create_default_icon(size: int = 64) -> Image.Image:
    """Generate a simple coloured circle as a fallback tray icon."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, size - 4, size - 4], fill=(30, 144, 255))
    draw.text((size // 4, size // 4), "LC", fill="white")
    return img


def _load_tray_icon() -> Image.Image:
    """Load packaged icon if present; otherwise use generated fallback."""
    icon_path = bundle_resource_path("assets/icon.ico")
    if icon_path.exists():
        try:
            return Image.open(icon_path)
        except Exception:
            log.debug("Failed to load icon at %s", icon_path, exc_info=True)
    return _create_default_icon()


class TrayApp:
    """Manages the pystray icon lifecycle."""

    def __init__(
        self,
        *,
        on_open_settings: Callable[[], None] | None = None,
        on_exit: Callable[[], None] | None = None,
        on_start_monitoring: Callable[[], None] | None = None,
        on_stop_monitoring: Callable[[], None] | None = None,
        output_dir: Path | None = None,
        logs_dir: Path | None = None,
        status_provider: Callable[[], str] | None = None,
        detail_provider: Callable[[], str] | None = None,
    ) -> None:
        self._on_open_settings = on_open_settings
        self._on_exit = on_exit
        self._on_start_monitoring = on_start_monitoring
        self._on_stop_monitoring = on_stop_monitoring
        self._output_dir = output_dir
        self._logs_dir = logs_dir
        self._status_provider = status_provider
        self._detail_provider = detail_provider
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None
        self._monitoring_active = True

    # -- public ------------------------------------------------------------

    def start(self) -> None:
        """Spawn the tray icon on a background thread."""
        self._icon = pystray.Icon(
            APP_NAME,
            icon=_load_tray_icon(),
            title=f"{APP_NAME} v{__version__}",
            menu=self._build_menu(),
        )
        self._thread = threading.Thread(
            target=self._icon.run, name="tray-icon", daemon=True
        )
        self._thread.start()
        log.info("Tray icon started")

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        log.info("Tray icon stopped")

    def update_menu(self) -> None:
        """Rebuild the menu (e.g. after status change)."""
        if self._icon:
            self._icon.menu = self._build_menu()
            self._icon.update_menu()

    # -- menu construction -------------------------------------------------

    def _build_menu(self) -> pystray.Menu:
        status_text = "Idle"
        if self._status_provider:
            try:
                raw = self._status_provider()
                status_text = _STATUS_LABELS.get(raw, raw.replace("_", " ").title())
            except Exception:
                status_text = "unknown"

        detail_text = ""
        if self._detail_provider:
            try:
                detail_text = self._detail_provider()
            except Exception:
                pass

        items: list[pystray.MenuItem] = [
            pystray.MenuItem(f"Status: {status_text}", None, enabled=False),
        ]
        if detail_text:
            items.append(pystray.MenuItem(f"  {detail_text}", None, enabled=False))

        items.append(pystray.Menu.SEPARATOR)

        # Start / Stop monitoring
        if self._monitoring_active:
            items.append(pystray.MenuItem("Stop Monitoring", self._on_stop_click))
        else:
            items.append(pystray.MenuItem("Start Monitoring", self._on_start_click))

        items.extend([
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings…", self._on_settings_click),
            pystray.MenuItem("Open Sessions Folder", self._on_open_output),
            pystray.MenuItem("Open Logs Folder", self._on_open_logs),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self._on_exit_click),
        ])

        return pystray.Menu(*items)

    # -- callbacks ---------------------------------------------------------

    def _on_settings_click(self, _icon: object, _item: object) -> None:
        if self._on_open_settings:
            self._on_open_settings()

    def _on_open_output(self, _icon: object, _item: object) -> None:
        self._open_folder(self._output_dir)

    def _on_open_logs(self, _icon: object, _item: object) -> None:
        self._open_folder(self._logs_dir)

    def _on_start_click(self, _icon: object, _item: object) -> None:
        self._monitoring_active = True
        if self._on_start_monitoring:
            self._on_start_monitoring()
        self.update_menu()

    def _on_stop_click(self, _icon: object, _item: object) -> None:
        self._monitoring_active = False
        if self._on_stop_monitoring:
            self._on_stop_monitoring()
        self.update_menu()

    def _on_exit_click(self, _icon: object, _item: object) -> None:
        if self._on_exit:
            self._on_exit()

    @staticmethod
    def _open_folder(path: Path | None) -> None:
        if path and path.exists():
            os.startfile(str(path))  # noqa: S606 – Windows-only, opening a folder
        else:
            log.warning("Folder does not exist: %s", path)
