"""T094: ``CoachingCard.qml`` renders one insight at a time.

The widget binds to T091's ``CoachingCardViewModel`` (exposed
to QML as ``coachingCardVM``) and surfaces the current insight.
Per T093, it reads ``insight.text`` (skill-level resolved) for
the body, falling back through the resolution chain.

QML can't be rendered without QApplication, so this test pins
the file content — every binding the C++/Python side relies on
must be present, and the widget's visibility must hinge on
``has_insight`` so the card disappears cleanly when nothing's
shown.

T095 adds the fade animation; T096 the audio cue; T097 the
dismiss button; T098 the flag-as-wrong button. T094 ships the
static layout only.
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
# File presence + qmldir registration
# ---------------------------------------------------------------------------


def test_coaching_card_qml_file_exists() -> None:
    assert _QML_PATH.exists(), (
        "CoachingCard.qml must live in Components/ alongside "
        "MetricCard, SessionCard, and the rest"
    )


def test_qmldir_registers_coaching_card() -> None:
    """Without the qmldir entry the widget can't be imported as
    ``Components.CoachingCard``. Pin the registration line so a
    drift between filename and module name fails loudly."""
    qmldir = _QML_PATH.parent / "qmldir"
    text = qmldir.read_text(encoding="utf-8")
    assert "CoachingCard 1.0 CoachingCard.qml" in text


# ---------------------------------------------------------------------------
# Bindings to the VM properties
# ---------------------------------------------------------------------------


def test_card_binds_visibility_to_has_insight(card_qml: str) -> None:
    """Visibility hinges on T091's has_insight property — when
    nothing's shown the card must disappear (not just go blank).
    A persistent empty card would be a dead widget on the HUD."""
    assert "coachingCardVM.has_insight" in card_qml
    assert "visible:" in card_qml


def test_card_binds_text_to_insight_text(card_qml: str) -> None:
    """T093's ``insight.text`` is the resolved skill-level
    variant. The card must read THAT, not ``insight.title``,
    or skill-level variants never reach the user."""
    assert "coachingCardVM.insight.text" in card_qml


def test_card_displays_rule_category_or_id_for_context(card_qml: str) -> None:
    """The user needs to know what category of mistake the card
    is about (braking / cornering / throttle) — accept either
    ``rule_id`` (e.g., "br.late_braking") or a future
    ``category`` field."""
    assert (
        "coachingCardVM.insight.rule_id" in card_qml
        or "coachingCardVM.insight.category" in card_qml
    )


# ---------------------------------------------------------------------------
# Single-card render guarantee
# ---------------------------------------------------------------------------


def test_card_does_not_loop_over_a_list(card_qml: str) -> None:
    """T091 explicitly shows ONE insight at a time — the next
    one comes via dismiss. A Repeater or ListView in the card
    file would let multiple cards stack, breaking that contract."""
    assert "Repeater" not in card_qml
    assert "ListView" not in card_qml


# ---------------------------------------------------------------------------
# Theme integration — the card must look like the other Components
# ---------------------------------------------------------------------------


def test_card_imports_theme_tokens(card_qml: str) -> None:
    """All Components share the Theme module for tokens (colours,
    spacing, typography). A coaching card with hard-coded colours
    would drift out of sync on a theme change."""
    assert "Theme" in card_qml


def test_card_root_element_is_a_visual_container(card_qml: str) -> None:
    """The widget's root must be something QML can place on the
    overlay — Rectangle / Item / Pane. A pure logic root would
    crash when added to the HUD's layout."""
    first_non_import = next(
        line.strip()
        for line in card_qml.splitlines()
        if line.strip() and not line.strip().startswith(("import", "//"))
    )
    assert first_non_import.startswith(("Rectangle", "Item", "Pane")), (
        f"unexpected root element: {first_non_import!r}"
    )
