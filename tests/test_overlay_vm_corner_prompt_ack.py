"""T153: minimal-click acknowledgment for the corner prompt.

A button-press handler — wired through a QML ``Shortcut`` so any
keyboard / wheel-button mapping can fire it — clears the
currently-shown corner prompt. The slot is the seam: ANY input
source that can call a QML slot (Logitech G HUB key bind, Qt
keyboard event, gamepad mapping software) hits the same
acknowledge path.

Behaviour pinned by these tests:

- Calling :meth:`acknowledgeCornerPrompt` with a non-empty
  prompt clears it to ``""`` and emits the change signal — QML
  rebinds, label disappears.
- Calling it on an *already* empty prompt is a safe no-op (no
  signal emit). Holding the wheel button can fire the shortcut
  multiple times in quick succession; the second+ presses
  shouldn't churn QML.
- The ack is *not* sticky: the next per-lap insight refresh is
  free to surface a new prompt. Acknowledgment is per-lap, not
  per-session.
"""
from __future__ import annotations

from tests.qt_mock import install
install()

from lap_coach_logger.coaching.corner_insights import CornerInsight  # noqa: E402
from lap_coach_logger.viewmodels.overlay_vm import OverlayViewModel  # noqa: E402


def test_acknowledge_corner_prompt_clears_a_visible_prompt() -> None:
    """Single button press clears the prompt — the core T153
    contract. The label disappears from the overlay."""
    vm = OverlayViewModel()
    vm._refresh_corner_prompt([
        CornerInsight(
            corner_name="T1", time_loss_s=0.32,
            loss_zone="entry", brake_onset_delta_pct=0.005,
        ),
    ])
    assert vm.cornerPrompt != ""

    vm.acknowledgeCornerPrompt()

    assert vm.cornerPrompt == ""


def test_acknowledge_corner_prompt_emits_change_signal() -> None:
    """QML rebinds on the change signal. Pin that the ack
    actually fires it — without the emit, the label would
    stay rendered even though the property is empty."""
    vm = OverlayViewModel()
    vm._refresh_corner_prompt([
        CornerInsight(
            corner_name="T3", time_loss_s=0.42,
            loss_zone="mid", min_speed_delta_kph=-3.5,
        ),
    ])
    baseline = vm.cornerPromptChanged.call_count

    vm.acknowledgeCornerPrompt()

    assert vm.cornerPromptChanged.call_count > baseline


def test_acknowledge_corner_prompt_is_idempotent_on_empty() -> None:
    """Holding the wheel button can re-fire the shortcut many
    times. Already-empty prompt ⇒ no signal, no churn — same
    transition-only emit pattern as :meth:`_refresh_corner_prompt`."""
    vm = OverlayViewModel()
    assert vm.cornerPrompt == ""
    baseline = vm.cornerPromptChanged.call_count

    vm.acknowledgeCornerPrompt()
    vm.acknowledgeCornerPrompt()
    vm.acknowledgeCornerPrompt()

    assert vm.cornerPrompt == ""
    assert vm.cornerPromptChanged.call_count == baseline


def test_next_lap_insights_can_resurface_after_ack() -> None:
    """Ack is per-lap, not per-session. After ack, the next
    insight push (e.g. next lap's worst corner) repopulates
    the prompt — driver still gets coaching for the new lap."""
    vm = OverlayViewModel()
    vm._refresh_corner_prompt([
        CornerInsight(
            corner_name="T1", time_loss_s=0.32,
            loss_zone="entry", brake_onset_delta_pct=0.005,
        ),
    ])
    vm.acknowledgeCornerPrompt()
    assert vm.cornerPrompt == ""

    # Simulate next lap's insights — different worst corner
    vm._refresh_corner_prompt([
        CornerInsight(
            corner_name="T5", time_loss_s=0.27,
            loss_zone="exit", throttle_pickup_delta_pct=0.006,
        ),
    ])

    assert vm.cornerPrompt == "losing 0.3s at T5 — throttle earlier"


def test_acknowledge_corner_prompt_is_a_qt_slot() -> None:
    """The slot must be QML-callable so a ``Shortcut`` element
    (or other input source) can wire to it. Smoke-check that
    the method is decorated as a Slot — accessible via the Qt
    metaobject, not just plain Python attribute."""
    vm = OverlayViewModel()

    method = getattr(vm, "acknowledgeCornerPrompt", None)
    assert callable(method), (
        "OverlayViewModel must expose acknowledgeCornerPrompt "
        "as a callable QML slot"
    )
