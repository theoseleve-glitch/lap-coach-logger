"""Regression guard: ViewModel property/slot name collisions (sprint T010).

Earlier in the sprint, ``tests/test_qml_bootstrap.py`` failed at
collection time with a ``TypeError`` because a ViewModel class had a
property whose name collided with an attribute/slot, raising at class
construction. The pre-sprint integration merge (304c0a9) resolved the
collision; this guard ensures the condition cannot resurface silently:
importing and instantiating every exported ViewModel class must not
raise ``TypeError`` at module import, class definition, or
construction time.
"""
from __future__ import annotations

from tests.qt_mock import install

install(mock_gui=True)


def test_viewmodels_importable_without_typeerror() -> None:
    # Import alone would raise TypeError at class-body time if a
    # pyqtProperty/attribute collision existed. If this import succeeds,
    # all VM classes are well-formed.
    from lap_coach_logger import viewmodels

    expected = {
        "HistoryViewModel",
        "ModeViewModel",
        "OnboardingViewModel",
        "OverlayViewModel",
        "ReviewViewModel",
        "ServiceViewModel",
        "SessionViewModel",
        "SettingsViewModel",
        "StrategyViewModel",
    }
    assert expected.issubset(set(viewmodels.__all__))


def test_viewmodel_classes_construct_without_typeerror() -> None:
    from lap_coach_logger.viewmodels import (
        HistoryViewModel,
        ModeViewModel,
        OnboardingViewModel,
        OverlayViewModel,
        ReviewViewModel,
        SessionViewModel,
        SettingsViewModel,
    )

    # Parameter-less constructors must not raise TypeError. A property/slot
    # name collision typically raises at class-definition time (covered by
    # the import test above) but can also surface at construction when Qt
    # resolves property descriptors — instantiate to cover both paths.
    for cls in (
        HistoryViewModel,
        ModeViewModel,
        OnboardingViewModel,
        OverlayViewModel,
        ReviewViewModel,
        SessionViewModel,
        SettingsViewModel,
    ):
        instance = cls()
        assert instance is not None, f"{cls.__name__} failed to construct"
