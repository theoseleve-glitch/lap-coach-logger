"""T095: CoachingCard fades in/out smoothly.

Hard-cut visibility (``visible: has_insight``) flicks the card
on and off — visually jarring on the HUD overlay. T095 wires
opacity-based fading so the card eases in when an insight
arrives and eases out when dismissed.

Two primitives the QML must use:
- ``Behavior on opacity`` — gives Qt a default animation for any
  binding-driven opacity change.
- ``NumberAnimation`` with a duration — controls how long the
  fade takes. T071's ModeBanner uses ``Theme.Motion.bannerDuration``;
  the CoachingCard reuses the same token (or another Motion token)
  for visual consistency.

Visibility hinges on ``opacity > 0`` (not ``has_insight`` alone)
so the faded-out card doesn't capture mouse events but still
participates in the fade-out animation. Without this, the card
disappears instantly when ``has_insight`` flips false.
"""
from __future__ import annotations

from pathlib import Path

import pytest


_QML_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Components" / "CoachingCard.qml"
)


@pytest.fixture(scope="module")
def card_qml() -> str:
    return _QML_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Animation primitives must be present
# ---------------------------------------------------------------------------


def test_card_uses_opacity_for_show_hide(card_qml: str) -> None:
    """Hard ``visible: has_insight`` doesn't animate. Opacity
    binding is the QML idiom for fading."""
    assert "opacity:" in card_qml
    assert "coachingCardVM.has_insight" in card_qml


def test_card_has_behavior_on_opacity(card_qml: str) -> None:
    """``Behavior on <property>`` is QML's "animate any change to
    this property" wrapper. Without it, opacity binding changes
    instantly."""
    assert "Behavior on opacity" in card_qml


def test_card_uses_number_animation_for_fade(card_qml: str) -> None:
    """The Behavior block needs an animation type — NumberAnimation
    is the standard for opacity (which is a real number)."""
    assert "NumberAnimation" in card_qml


def test_card_animation_uses_theme_motion_token(card_qml: str) -> None:
    """Hard-coded duration drifts away from the rest of the HUD's
    motion language. Reading from ``Theme.Motion`` keeps the fade
    consistent with banners, modals, and other cards."""
    assert "Theme.Motion" in card_qml


# ---------------------------------------------------------------------------
# Visibility tied to opacity (not raw has_insight)
# ---------------------------------------------------------------------------


def test_visible_no_longer_uses_raw_has_insight(card_qml: str) -> None:
    """If ``visible:`` is bound to ``coachingCardVM.has_insight``
    directly, the card pops in/out instantly — defeating the
    fade. Visibility must be tied to opacity instead so the card
    stays rendered (visible) while it fades to 0."""
    # The card's visible binding must NOT be the raw has_insight.
    # Loose-match: any line that says ``visible: <something with
    # has_insight directly>`` would fail this test. The acceptable
    # form is ``visible: opacity > 0`` (or similar).
    for line in card_qml.splitlines():
        stripped = line.strip()
        if stripped.startswith("visible:") and "has_insight" in stripped:
            pytest.fail(
                "visible: must depend on opacity (not raw has_insight) "
                "so fade-out animations have time to play"
            )


def test_visible_uses_opacity_threshold(card_qml: str) -> None:
    """The faded-out card shouldn't capture mouse events. Tying
    ``visible`` to ``opacity > 0`` keeps it interactive only when
    actually shown."""
    assert "opacity > 0" in card_qml or "opacity != 0" in card_qml
