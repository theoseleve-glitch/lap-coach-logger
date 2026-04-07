"""SettingsViewModel -- config read/write bridge for the QML settings panel.

Exposes config values as a flat dict and provides typed accessors for QML.
The bootstrap layer wires:

    settings_vm.saveRequested.connect(service.save_settings)
    service.settings_saved.connect(lambda _: settings_vm.load(service.settings_snapshot()))
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal, Slot

log = logging.getLogger(__name__)


class SettingsViewModel(QObject):
    """Exposes application config as QML-bindable properties with typed accessors."""

    # -- change signals --------------------------------------------------------
    valuesChanged = Signal()
    isFirstRunChanged = Signal()
    saveRequested = Signal(dict)

    # -- construction ----------------------------------------------------------

    def __init__(self) -> None:
        super().__init__()

        self._values: dict = {}
        self._is_first_run: bool = False

    # -- QML properties --------------------------------------------------------

    @property
    def values(self) -> dict:
        """The full config values dict."""
        return self._values

    @property
    def isFirstRun(self) -> bool:  # noqa: N802
        """Whether the app is running for the first time."""
        return self._is_first_run

    @isFirstRun.setter
    def isFirstRun(self, value: bool) -> None:  # noqa: N802
        if value != self._is_first_run:
            self._is_first_run = value
            self.isFirstRunChanged.emit()

    # -- slots (QML callable) --------------------------------------------------

    @Slot(str, result=str)
    def getString(self, key: str) -> str:  # noqa: N802
        """Return the config value for *key* as a string, or ``''`` if missing."""
        val = self._values.get(key)
        if val is None:
            return ""
        return str(val)

    @Slot(str, result=float)
    def getFloat(self, key: str) -> float:  # noqa: N802
        """Return the config value for *key* as a float, or ``0.0`` if missing."""
        val = self._values.get(key)
        if val is None:
            return 0.0
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    @Slot(str, result=bool)
    def getBool(self, key: str) -> bool:  # noqa: N802
        """Return the config value for *key* as a bool, or ``False`` if missing."""
        val = self._values.get(key)
        if val is None:
            return False
        return bool(val)

    @Slot(str, "QVariant")
    def setValue(self, key: str, value: object) -> None:  # noqa: N802
        """Update a single config key and emit ``valuesChanged``."""
        self._values[key] = value
        self.valuesChanged.emit()

    @Slot()
    def save(self) -> None:
        """Emit ``saveRequested`` with a copy of the current values dict."""
        self.saveRequested.emit(dict(self._values))

    # -- public API ------------------------------------------------------------

    def load(self, values: dict) -> None:
        """Populate internal dict from a settings snapshot and emit ``valuesChanged``."""
        self._values = dict(values)
        self.valuesChanged.emit()
