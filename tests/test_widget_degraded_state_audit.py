"""T156: pin that the widget degraded-state audit document
covers every widget in ``qml/Overlay/widgets/``.

Block I (T156–T170) iterates per-widget improvements to
degraded-state rendering. The audit is the *source of truth*
for "which widgets need work" — if a widget is missing from
the audit, its T157+ follow-up task can't be scheduled. This
test ensures the audit stays in sync with the actual widget
inventory: adding a new ``.qml`` file under ``widgets/`` and
forgetting to add it to the audit fails CI, not the next
sprint review.

The audit lives at ``docs/audits/widget-degraded-state-audit.md``
(checked into the repo so it's reviewable in PRs and survives
across sprints).
"""
from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_WIDGETS_DIR = (
    _REPO_ROOT / "src" / "lap_coach_logger" / "qml" / "Overlay" / "widgets"
)
_AUDIT_PATH = _REPO_ROOT / "docs" / "audits" / "widget-degraded-state-audit.md"

# GlassSurface is a base/mixin component, not a user-facing widget.
# Excluded from the audit by design (T157+ won't touch it).
_NON_WIDGET_FILES = frozenset({"GlassSurface.qml"})


def _discovered_widgets() -> list[str]:
    """Every widget filename (sans extension) in the widgets/ dir,
    excluding base-component files."""
    return sorted(
        path.stem
        for path in _WIDGETS_DIR.glob("*.qml")
        if path.name not in _NON_WIDGET_FILES
    )


@pytest.fixture(scope="module")
def audit_text() -> str:
    assert _AUDIT_PATH.exists(), (
        f"T156 audit document missing at {_AUDIT_PATH}. "
        "Block I depends on this list being current."
    )
    return _AUDIT_PATH.read_text(encoding="utf-8")


def test_audit_document_exists() -> None:
    """The audit must exist so reviewers can find it without
    grepping the codebase. Pinning the canonical path makes
    the test failure point straight at the missing file."""
    assert _AUDIT_PATH.exists(), (
        f"T156 audit must live at {_AUDIT_PATH.relative_to(_REPO_ROOT)}"
    )


def test_audit_covers_every_widget(audit_text: str) -> None:
    """Adding a new widget without updating the audit fails this
    test — keeps Block I's scope honest as the codebase
    evolves. Each widget's stem (e.g. ``DeltaTimeWidget``) must
    appear somewhere in the audit text."""
    widgets = _discovered_widgets()
    missing = [name for name in widgets if name not in audit_text]
    assert not missing, (
        f"Audit at {_AUDIT_PATH.relative_to(_REPO_ROOT)} is missing "
        f"these widgets: {missing}. Add them with their current "
        f"degraded-state status."
    )


def test_audit_count_matches_actual_widget_count(audit_text: str) -> None:
    """The audit's stated total should match the discovered
    count. Catches a stale 'Total: 40 widgets' header after
    new widgets get added — small but easy-to-miss drift."""
    widgets = _discovered_widgets()
    expected = len(widgets)
    assert str(expected) in audit_text, (
        f"Audit must state the actual widget count ({expected}). "
        f"If you renamed widgets or excluded base components, update "
        f"the audit's count line."
    )


def test_audit_meets_block_i_minimum_widget_count() -> None:
    """T156 spec: 'Audit all 40+ widgets'. Sanity-check the
    discovered count holds the lower bound — if it dropped to
    20 we'd want to investigate the regression rather than
    silently let the sprint task become trivial."""
    widgets = _discovered_widgets()
    assert len(widgets) >= 40, (
        f"Block I expects 40+ widgets; only {len(widgets)} discovered. "
        f"Investigate widget removals before continuing."
    )
