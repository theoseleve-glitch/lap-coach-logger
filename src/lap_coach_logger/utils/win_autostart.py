"""Windows-specific utilities: autostart (Run registry key).

Isolated here so the rest of the app stays platform-neutral.
"""

from __future__ import annotations

import logging
import sys

from lap_coach_logger.app_identity import APP_ID

log = logging.getLogger(__name__)

_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _current_exe() -> str:
    """Return current executable path."""
    return sys.executable


def _command_for_exe(exe: str) -> str:
    return f'"{exe}"'


def current_autostart_command() -> str:
    """Return autostart command for the currently running executable."""
    return _command_for_exe(_current_exe())


def set_autostart(enable: bool) -> bool:
    """Add or remove the app from Windows startup.  Returns True on success."""
    try:
        import winreg
    except ImportError:
        log.warning("winreg not available — not on Windows?")
        return False

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_SET_VALUE
        )
        if enable:
            exe = _current_exe()
            winreg.SetValueEx(key, APP_ID, 0, winreg.REG_SZ, _command_for_exe(exe))
            log.info("Autostart enabled: %s", exe)
        else:
            try:
                winreg.DeleteValue(key, APP_ID)
                log.info("Autostart disabled")
            except FileNotFoundError:
                pass  # already absent
        winreg.CloseKey(key)
        return True
    except OSError:
        log.exception("Failed to update autostart registry key")
        return False


def is_autostart_enabled() -> bool:
    """Check if the app is registered for Windows startup."""
    try:
        import winreg
    except ImportError:
        return False

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_READ
        )
        try:
            winreg.QueryValueEx(key, APP_ID)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except OSError:
        return False


def registered_autostart_command() -> str | None:
    """Return registered autostart command for this app, if present."""
    try:
        import winreg
    except ImportError:
        return None

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_READ)
        try:
            value, _ = winreg.QueryValueEx(key, APP_ID)
            return value
        except FileNotFoundError:
            return None
        finally:
            winreg.CloseKey(key)
    except OSError:
        return None


def is_registered_for_current_executable() -> bool:
    value = registered_autostart_command()
    return value == current_autostart_command()


def validate_autostart() -> None:
    """If autostart is enabled, ensure the registry points to the current exe.

    Called once at startup so that after a reinstall or move the registry
    entry is silently corrected.
    """
    try:
        import winreg
    except ImportError:
        return

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_READ
        )
        try:
            value, _ = winreg.QueryValueEx(key, APP_ID)
        except FileNotFoundError:
            return  # not registered — nothing to fix
        finally:
            winreg.CloseKey(key)

        expected = current_autostart_command()
        if value != expected:
            log.info("Autostart path outdated (%s) — updating to %s", value, expected)
            set_autostart(True)
    except OSError:
        log.debug("Could not validate autostart registry entry", exc_info=True)


def sync_autostart(config_enabled: bool) -> bool:
    """Synchronize OS autostart state with config intent; return final OS state."""
    if config_enabled:
        if not is_autostart_enabled():
            set_autostart(True)
        validate_autostart()
    else:
        if is_autostart_enabled():
            set_autostart(False)
    return is_autostart_enabled()
