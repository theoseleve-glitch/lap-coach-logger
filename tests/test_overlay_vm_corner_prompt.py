"""T152: ``OverlayViewModel.cornerPrompt`` — Qt-bindable
projection of :func:`format_corner_prompt`.

Same wiring shape as T148/T151: VM owns the QML-facing string
state, the pure formatter owns the logic. The VM picks the
highest-time-loss insight from the per-lap list and refreshes
the prompt; ``cornerPromptChanged`` fires only on transition.

Tests poke ``_refresh_corner_prompt`` directly with
hand-built insight lists (mirrors how T148/T151 VM tests poke
internal state to avoid replaying the full telemetry pipeline).
"""
from __future__ import annotations

from tests.qt_mock import install
install()

from lap_coach_logger.coaching.corner_insights import CornerInsight  # noqa: E402
from lap_coach_logger.viewmodels.overlay_vm import OverlayViewModel  # noqa: E402


def test_corner_prompt_defaults_to_empty() -> None:
    """No insights pushed yet ⇒ no prompt. Widget hides label
    rather than showing a stale "losing X at —"."""
    vm = OverlayViewModel()

    assert vm.cornerPrompt == ""


def test_refresh_corner_prompt_picks_highest_loss_insight() -> None:
    """Per-lap insight lists have one entry per corner. The
    prompt should reflect the *worst* corner (biggest time
    loss) — that's where the next-lap focus belongs."""
    vm = OverlayViewModel()

    insights = [
        CornerInsight(
            corner_name="T1", time_loss_s=0.10,
            loss_zone="entry", brake_onset_delta_pct=-0.005,
        ),
        CornerInsight(
            corner_name="T3", time_loss_s=0.42,
            loss_zone="mid", min_speed_delta_kph=-3.5,
        ),
        CornerInsight(
            corner_name="T5", time_loss_s=0.20,
            loss_zone="exit", throttle_pickup_delta_pct=0.005,
        ),
    ]
    vm._refresh_corner_prompt(insights)

    assert vm.cornerPrompt == "losing 0.4s at T3 — carry more speed"


def test_refresh_corner_prompt_with_empty_list_clears_prompt() -> None:
    """No insights this lap (e.g. lap aborted before
    finalisation) ⇒ clear the prompt. Avoids a stale message
    surviving an out-lap."""
    vm = OverlayViewModel()
    # Establish a prompt
    vm._refresh_corner_prompt([
        CornerInsight(
            corner_name="T1", time_loss_s=0.32,
            loss_zone="entry", brake_onset_delta_pct=0.005,
        ),
    ])
    assert vm.cornerPrompt != ""

    vm._refresh_corner_prompt([])

    assert vm.cornerPrompt == ""


def test_corner_prompt_changed_fires_on_transition() -> None:
    """QML rebinds on the change signal — pin that the signal
    fires when the prompt changes between consecutive laps."""
    vm = OverlayViewModel()
    vm._refresh_corner_prompt([
        CornerInsight(
            corner_name="T1", time_loss_s=0.32,
            loss_zone="entry", brake_onset_delta_pct=0.005,
        ),
    ])
    baseline = vm.cornerPromptChanged.call_count

    vm._refresh_corner_prompt([
        CornerInsight(
            corner_name="T3", time_loss_s=0.42,
            loss_zone="mid", min_speed_delta_kph=-3.5,
        ),
    ])

    assert vm.cornerPrompt == "losing 0.4s at T3 — carry more speed"
    assert vm.cornerPromptChanged.call_count > baseline


def test_corner_prompt_changed_does_not_fire_on_no_op() -> None:
    """Identical insight list across consecutive laps ⇒
    identical prompt ⇒ no signal. QML doesn't rebind when
    nothing has changed."""
    vm = OverlayViewModel()
    insights = [
        CornerInsight(
            corner_name="T1", time_loss_s=0.32,
            loss_zone="entry", brake_onset_delta_pct=0.005,
        ),
    ]
    vm._refresh_corner_prompt(insights)
    baseline = vm.cornerPromptChanged.call_count

    vm._refresh_corner_prompt(insights)

    assert vm.cornerPromptChanged.call_count == baseline


def test_refresh_corner_prompt_skips_insights_below_threshold() -> None:
    """If every insight is below the significance threshold
    (formatter returns ``None`` for each), the prompt should
    clear — no spurious "losing 0.0s at —" surfacing."""
    vm = OverlayViewModel()

    insights = [
        CornerInsight(corner_name="T1", time_loss_s=0.04, loss_zone="entry"),
        CornerInsight(corner_name="T2", time_loss_s=0.05, loss_zone="mid"),
    ]
    vm._refresh_corner_prompt(insights)

    assert vm.cornerPrompt == ""
