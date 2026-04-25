"""T063: ``ModeViewModel.setMode`` fires the ``mode_switched`` PostHog event.

The mode engine itself is still placeholder (current
``mode_detector.py`` is a stub), so this task ships the **analytics
seam** ready for when the real engine lands. The slot
``setMode(mode)`` is what every UI path — and the future engine —
will funnel through, so wiring the emission there means no further
analytics work when the engine arrives.

Funnel-friendly properties:

* ``mode``      — the mode after the switch
* ``from_mode`` — the mode before the switch (transition matrices)

Guard: emission only fires on **actual transitions** (not when the
user selects the already-active mode and not for invalid mode
strings) so funnels see real signal, not no-op clicks.

Tests record what reaches ``analytics.track`` via monkeypatch — no
real PostHog network traffic.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def track_recorder(monkeypatch: pytest.MonkeyPatch):
    """Replace ``analytics.track`` with a list-recorder for the test."""
    from lap_coach_logger import analytics

    calls: list[tuple[str, dict]] = []

    def _record(event_name: str, **properties: object) -> None:
        calls.append((event_name, properties))

    monkeypatch.setattr(analytics, "track", _record)
    return calls


def test_set_mode_to_a_new_mode_fires_mode_switched(
    track_recorder: list[tuple[str, dict]],
) -> None:
    from lap_coach_logger.viewmodels.mode_vm import ModeViewModel

    vm = ModeViewModel()  # default _active_mode == "sprint"
    track_recorder.clear()

    vm.setMode("endurance")

    events = [c for c in track_recorder if c[0] == "mode_switched"]
    assert len(events) == 1
    props = events[0][1]
    assert props["mode"] == "endurance"
    assert props["from_mode"] == "sprint"


def test_set_mode_to_the_same_mode_fires_nothing(
    track_recorder: list[tuple[str, dict]],
) -> None:
    """No-op selections (user clicked the active mode again) must not
    pollute funnels with phantom transitions."""
    from lap_coach_logger.viewmodels.mode_vm import ModeViewModel

    vm = ModeViewModel()  # _active_mode == "sprint"
    track_recorder.clear()

    vm.setMode("sprint")

    assert [c for c in track_recorder if c[0] == "mode_switched"] == []


def test_set_mode_with_invalid_string_fires_nothing(
    track_recorder: list[tuple[str, dict]],
) -> None:
    """Bad input (typo, future-mode-string) must not emit a transition
    event; setMode silently ignores invalid modes today."""
    from lap_coach_logger.viewmodels.mode_vm import ModeViewModel

    vm = ModeViewModel()
    track_recorder.clear()

    vm.setMode("teleport")  # not in MODES

    assert [c for c in track_recorder if c[0] == "mode_switched"] == []


def test_multiple_transitions_emit_one_event_each(
    track_recorder: list[tuple[str, dict]],
) -> None:
    from lap_coach_logger.viewmodels.mode_vm import ModeViewModel
    from lap_coach_logger.core.mode_detector import MODES

    vm = ModeViewModel()
    track_recorder.clear()

    # Walk every defined mode in turn so the test is robust to
    # MODES being expanded later.
    sequence = [m for m in MODES if m != vm._active_mode][:2]
    expected_chain = [vm._active_mode, *sequence]

    for target in sequence:
        vm.setMode(target)

    events = [c for c in track_recorder if c[0] == "mode_switched"]
    assert [e[1]["mode"] for e in events] == sequence
    assert [e[1]["from_mode"] for e in events] == expected_chain[:-1]


def test_mode_switched_is_safe_when_analytics_unconfigured() -> None:
    """If a mode flips before bootstrap has wired analytics
    (e.g. headless tests), the emission must be a no-op."""
    from lap_coach_logger import analytics
    from lap_coach_logger.viewmodels.mode_vm import ModeViewModel
    from lap_coach_logger.core.mode_detector import MODES

    analytics.reset()
    vm = ModeViewModel()
    target = next(m for m in MODES if m != vm._active_mode)

    # Must not raise.
    vm.setMode(target)
    assert vm.activeMode == target
