"""Windows-specific overlay window flags for sim racing.

Sets WS_EX_TOPMOST + WS_EX_NOACTIVATE + WS_EX_TOOLWINDOW so overlay
windows float above borderless-fullscreen games without stealing focus
or appearing in the taskbar/Alt-Tab list.

Usage from QML bootstrap:
    from lap_coach_logger.utils.overlay_hwnd import apply_overlay_flags
    # Call after each OverlayWidget.visible = true
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import sys

log = logging.getLogger(__name__)

if sys.platform == "win32":
    _user32 = ctypes.windll.user32

    # Window style constants
    GWL_EXSTYLE = -20
    WS_EX_TOPMOST = 0x00000008
    WS_EX_NOACTIVATE = 0x08000000
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020

    HWND_TOPMOST = -1
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOACTIVATE = 0x0010
    SWP_SHOWWINDOW = 0x0040

    def apply_overlay_flags(hwnd: int, *, click_through: bool = False) -> bool:
        """Apply overlay window flags to a native window handle.

        Args:
            hwnd: Native window handle (HWND).
            click_through: If True, mouse events pass through the window.

        Returns:
            True if flags were applied successfully.
        """
        if not hwnd:
            return False
        try:
            # Get current extended style
            ex_style = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)

            # Add overlay flags
            ex_style |= WS_EX_TOPMOST | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_LAYERED
            if click_through:
                ex_style |= WS_EX_TRANSPARENT

            _user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)

            # Force TOPMOST position
            _user32.SetWindowPos(
                hwnd, HWND_TOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
            )
            return True
        except Exception:
            log.warning("Failed to apply overlay flags to hwnd=%s", hwnd, exc_info=True)
            return False

    def remove_overlay_flags(hwnd: int) -> bool:
        """Remove overlay flags (restore normal window behavior)."""
        if not hwnd:
            return False
        try:
            ex_style = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex_style &= ~(WS_EX_NOACTIVATE | WS_EX_TRANSPARENT)
            _user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
            return True
        except Exception:
            log.warning("Failed to remove overlay flags from hwnd=%s", hwnd, exc_info=True)
            return False

    def apply_overlay_flags_to_all_overlays() -> int:
        """Find all Qt Tool windows in this process and apply overlay flags.

        Returns the number of windows flagged.
        """
        import os
        pid = os.getpid()
        flagged = 0

        @ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        def _enum_cb(hwnd, _lparam):
            nonlocal flagged
            # Check if window belongs to our process
            proc_id = ctypes.wintypes.DWORD()
            _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
            if proc_id.value != pid:
                return True
            # Check if it's a tool window (our overlays use Qt.Tool)
            style = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if style & WS_EX_TOOLWINDOW:
                apply_overlay_flags(hwnd)
                flagged += 1
            return True

        _user32.EnumWindows(_enum_cb, 0)
        return flagged

else:
    # Non-Windows: no-op
    def apply_overlay_flags(hwnd: int, *, click_through: bool = False) -> bool:
        return False

    def remove_overlay_flags(hwnd: int) -> bool:
        return False

    def apply_overlay_flags_to_all_overlays() -> int:
        return 0
