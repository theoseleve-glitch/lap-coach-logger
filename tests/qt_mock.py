"""Shared PySide6 mock for ViewModel unit tests.

Provides a fake Qt runtime so ViewModel modules can be imported without
a real PySide6 installation.  Call ``install()`` before importing any
ViewModel module.

Usage::

    from tests.qt_mock import install
    install()

    from lap_coach_logger.viewmodels.session_vm import SessionViewModel
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Fake Signal descriptor
# ---------------------------------------------------------------------------

class FakeSignalInstance:
    """Per-object signal instance that records emit() calls.

    When *propagate* is True (used by integration tests), connected slots
    are called automatically when ``emit()`` fires.
    """

    def __init__(self, *, propagate: bool | None = None) -> None:
        self._mock = MagicMock()
        self._connections: list = []
        # Default to the class-level setting from FakeSignal if not explicit
        self._propagate = propagate if propagate is not None else FakeSignal._propagate

    def emit(self, *args: object) -> None:
        self._mock(*args)
        if self._propagate:
            for slot in self._connections:
                slot(*args)

    def connect(self, slot: object) -> None:
        self._connections.append(slot)

    @property
    def call_count(self) -> int:
        return self._mock.call_count

    @property
    def call_args(self):  # noqa: ANN204
        return self._mock.call_args

    @property
    def call_args_list(self):  # noqa: ANN204
        return self._mock.call_args_list


class FakeSignal:
    """Descriptor that yields a fresh FakeSignalInstance per owner object."""

    _propagate = False  # class-level default; overridden by install()

    def __init__(self, *_args: object) -> None:
        self._name: str | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def __get__(self, obj: object, objtype: type | None = None) -> FakeSignal | FakeSignalInstance:
        if obj is None:
            return self
        attr = f"_sig_{self._name}"
        inst = obj.__dict__.get(attr)
        if inst is None:
            inst = FakeSignalInstance(propagate=FakeSignal._propagate)
            obj.__dict__[attr] = inst
        return inst


# ---------------------------------------------------------------------------
# Fake Property decorator
# ---------------------------------------------------------------------------

class _FakePropertyDescriptor:
    """Mimics PySide6 Property: a descriptor with a .setter() chain.

    PySide6 usage::

        @Property(str, notify=trackChanged)
        def track(self) -> str:
            return self._track

        @track.setter
        def track(self, value: str) -> None:
            self._track = value

    This fake reproduces both the decorator and the .setter chain so that
    ViewModel classes can be instantiated and their properties read/written
    without a real Qt runtime.
    """

    def __init__(self, fget=None, fset=None):  # noqa: ANN001
        self._fget = fget
        self._fset = fset

    def __get__(self, obj: object, objtype: type | None = None):  # noqa: ANN204
        if obj is None:
            return self
        if self._fget is None:
            raise AttributeError("unreadable attribute")
        return self._fget(obj)

    def __set__(self, obj: object, value: object) -> None:
        if self._fset is None:
            raise AttributeError("can't set attribute")
        self._fset(obj, value)

    def setter(self, fset):  # noqa: ANN001, ANN201
        """Return a new descriptor that adds a setter — mirrors @prop.setter."""
        return _FakePropertyDescriptor(fget=self._fget, fset=fset)


def _fake_property(*_args: object, **_kwargs: object):  # noqa: ANN202
    """Mimic ``@Property(type, notify=signal)`` — a decorator factory.

    Called as ``@Property(str, notify=changed)`` this returns a decorator
    that wraps the getter function into a ``_FakePropertyDescriptor``.
    """
    def decorator(fget):  # noqa: ANN001, ANN202
        return _FakePropertyDescriptor(fget=fget)
    return decorator


# ---------------------------------------------------------------------------
# Fake QObject base
# ---------------------------------------------------------------------------

class FakeQObject:
    def __init__(self, *_a: object, **_kw: object) -> None:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_installed = False
_qt_core_mock: MagicMock | None = None


def install(*, propagate_signals: bool = False, mock_gui: bool = False) -> None:
    """Inject fake PySide6 modules into ``sys.modules``.

    Parameters
    ----------
    propagate_signals:
        When True, ``emit()`` calls connected slots automatically.
        Use for integration tests that verify signal wiring.
    mock_gui:
        When True, also mock ``PySide6.QtGui``, ``PySide6.QtQml``,
        and ``PySide6.QtWidgets`` (needed by qml_bootstrap imports).

    Safe to call multiple times — only the first call has an effect.
    """
    global _installed, _qt_core_mock  # noqa: PLW0603
    if _installed:
        # Even if already installed, ensure PySide6.QtCore points at our mock
        # (guards against test-ordering pollution from bare MagicMock files).
        sys.modules["PySide6.QtCore"] = _qt_core_mock
        # Allow callers to upgrade propagation for integration tests
        if propagate_signals:
            FakeSignal._propagate = True
        if mock_gui:
            for submod in (
                "PySide6.QtGui", "PySide6.QtQml", "PySide6.QtWidgets",
                "PySide6.QtSvg", "PySide6.QtSvgWidgets",
            ):
                sys.modules.setdefault(submod, MagicMock())
        return
    _installed = True

    FakeSignal._propagate = propagate_signals

    _qt_core_mock = MagicMock()
    _qt_core_mock.QObject = FakeQObject
    _qt_core_mock.Signal = FakeSignal
    _qt_core_mock.Slot = lambda *a, **kw: (lambda fn: fn)
    _qt_core_mock.Property = _fake_property

    # Use direct assignment (not setdefault) so we always win even if
    # an earlier test file set a bare MagicMock() for PySide6.QtCore.
    if "PySide6" not in sys.modules:
        sys.modules["PySide6"] = MagicMock()
    sys.modules["PySide6.QtCore"] = _qt_core_mock
    if mock_gui:
        for submod in (
            "PySide6.QtGui", "PySide6.QtQml", "PySide6.QtWidgets",
            "PySide6.QtSvg", "PySide6.QtSvgWidgets",
        ):
            sys.modules.setdefault(submod, MagicMock())
