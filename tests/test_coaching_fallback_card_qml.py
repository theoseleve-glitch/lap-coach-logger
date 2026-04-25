"""T104: ``CoachingFallbackCard.qml`` shows the
post-session-in-webapp message when no live insights are
currently visible.

Per Q95: deep analysis lives in the webapp; desktop coaching
is the live, latency-bounded path. When the live path has
nothing to surface (no insights yet, or coaching disabled),
the fallback card points the user to the webapp.

T071 (compact summary) + T072 (webapp CTA) already pin this
"deep analysis lives in the webapp" signal on the Review page.
T104 carries that signal to the LIVE coaching surface — same
copy intent, same destination.

Why a separate widget (not a fallback inside CoachingCard):
- T094/T095 pinned CoachingCard's opacity-fade lifecycle. A
  fallback inside the same widget would either fight the fade
  (always-visible parent vs faded children) or require
  inverting the visibility logic in ways that ripple through
  those tests.
- Two widgets at the same HUD slot is the standard QML idiom
  for "show A or B" — both bind to the VM's has_insight, one
  inverted.

Visibility: the fallback shows when ``has_insight === false``.
The two cards never overlap because their visibility predicates
are mutually exclusive — bound directly to the same property.
"""
from __future__ import annotations

from pathlib import Path

import pytest


_QML_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Components" / "CoachingFallbackCard.qml"
)


@pytest.fixture(scope="module")
def fallback_qml() -> str:
    return _QML_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# File presence + qmldir registration
# ---------------------------------------------------------------------------


def test_fallback_card_qml_file_exists() -> None:
    assert _QML_PATH.exists()


def test_qmldir_registers_fallback_card() -> None:
    qmldir = _QML_PATH.parent / "qmldir"
    text = qmldir.read_text(encoding="utf-8")
    assert "CoachingFallbackCard 1.0 CoachingFallbackCard.qml" in text


# ---------------------------------------------------------------------------
# Required copy (verbatim — pin to catch accidental drift)
# ---------------------------------------------------------------------------


def test_fallback_card_carries_post_session_webapp_copy(
    fallback_qml: str,
) -> None:
    """The exact copy string is the load-bearing user signal —
    "your live coaching gap is filled by post-session analysis
    in the webapp". Pinning verbatim catches accidental drift
    during refactors (e.g., a copy editor's "improvement" that
    weakens the message)."""
    assert "Insights available post-session in webapp" in fallback_qml


# ---------------------------------------------------------------------------
# Visibility: tied to has_insight (inverse)
# ---------------------------------------------------------------------------


def test_fallback_card_visibility_inverts_has_insight(
    fallback_qml: str,
) -> None:
    """The fallback only shows when there's NO live insight —
    otherwise the user would see both, which is confusing.
    Mutually exclusive visibility relies on the same VM
    property as CoachingCard."""
    assert "coachingCardVM.has_insight" in fallback_qml
    # The visibility predicate must be the *negation* — match
    # any common QML inversion pattern.
    assert any(
        pattern in fallback_qml
        for pattern in (
            "!coachingCardVM.has_insight",
            "coachingCardVM.has_insight === false",
            "coachingCardVM.has_insight == false",
        )
    )


# ---------------------------------------------------------------------------
# Theme integration
# ---------------------------------------------------------------------------


def test_fallback_card_imports_theme_tokens(fallback_qml: str) -> None:
    """All Components share Theme tokens for visual consistency.
    The fallback message is muted (steel / subtle) so it doesn't
    compete visually with active live coaching."""
    assert "Theme" in fallback_qml


def test_fallback_card_root_is_a_visual_container(fallback_qml: str) -> None:
    first_non_import = next(
        line.strip()
        for line in fallback_qml.splitlines()
        if line.strip() and not line.strip().startswith(("import", "//", "/*"))
    )
    assert first_non_import.startswith(("Rectangle", "Item", "Pane")), (
        f"unexpected root element: {first_non_import!r}"
    )


# ---------------------------------------------------------------------------
# T071 cross-link: same destination phrasing
# ---------------------------------------------------------------------------


def test_fallback_copy_aligns_with_review_page_cta_intent() -> None:
    """The Review page T072 CTA says 'See full analysis in webapp'.
    The live fallback says 'Insights available post-session in
    webapp'. Both point at the webapp; pinning that the live
    fallback at least mentions 'webapp' so the destination is
    obvious."""
    text = _QML_PATH.read_text(encoding="utf-8")
    assert "webapp" in text
