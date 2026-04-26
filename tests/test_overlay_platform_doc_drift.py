"""T227: Documentation — OVERLAY_PLATFORM.md is current.

Pins drift between the architecture doc and the actual
``src/lap_coach_logger/overlays/`` package so the doc stays a
useful reference instead of rotting into a misleading artifact.

Specifically:

  - Every ``.py`` module in the overlays package is mentioned by
    name in the doc (so newly-added modules don't go undocumented)
  - Every ``Overlay*`` class explicitly referenced in the doc
    (in backticks) must still exist in code
  - The doc carries a "Last reviewed" line so future readers
    can judge how stale it is

This is a CI-safe drift-prevention test. It does not check that
the prose accurately describes each module — humans still have
to read and write — but it catches the silent drift where a
new module ships and never gets a section in the doc.
"""
from __future__ import annotations

import re
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_OVERLAYS_DIR = _REPO_ROOT / "src" / "lap_coach_logger" / "overlays"
_DOC_PATH = _REPO_ROOT / "OVERLAY_PLATFORM.md"


# Modules that exist for plumbing reasons but don't warrant a
# section in the architecture doc (e.g. example fixtures, the
# package __init__).
_MODULE_DOC_EXEMPT: frozenset[str] = frozenset(
    {
        "__init__",
        "layout_examples",
        "settings_examples",
    }
)


def _read_doc() -> str:
    assert _DOC_PATH.exists(), f"missing {_DOC_PATH}"
    return _DOC_PATH.read_text(encoding="utf-8")


def _list_overlay_modules() -> list[str]:
    """Module stems (filenames without .py) for every .py in
    the overlays package, excluding documented exemptions."""
    return sorted(
        p.stem
        for p in _OVERLAYS_DIR.glob("*.py")
        if p.stem not in _MODULE_DOC_EXEMPT
    )


def _backtick_overlay_class_refs(doc_text: str) -> set[str]:
    """Extract names like ``OverlayDefinition`` from
    `\\`OverlayDefinition\\`` markdown spans."""
    return set(re.findall(r"`(Overlay[A-Za-z0-9_]+)`", doc_text))


# ---------------------------------------------------------------------------
# Module coverage
# ---------------------------------------------------------------------------


def test_every_overlay_module_is_mentioned_in_doc() -> None:
    """Each ``src/lap_coach_logger/overlays/<name>.py`` module
    must be referenced by name in OVERLAY_PLATFORM.md so newly-
    added modules don't ship undocumented."""
    doc = _read_doc()
    modules = _list_overlay_modules()

    missing: list[str] = []
    for stem in modules:
        # Match the module either as `name.py` (in lists / prose)
        # or as `name` (in backticks).
        patterns = (f"`{stem}.py`", f"`{stem}`", f"{stem}.py")
        if not any(p in doc for p in patterns):
            missing.append(stem)

    assert not missing, (
        f"OVERLAY_PLATFORM.md is missing references to these "
        f"overlay modules: {missing}. Add a one-line description "
        f"to the 'Module / Package Structure' section."
    )


# ---------------------------------------------------------------------------
# Class coverage: classes named in the doc must still exist
# ---------------------------------------------------------------------------


def test_every_class_named_in_doc_exists_in_code() -> None:
    """If the doc says ``OverlayFoo`` exists, the codebase
    must actually define it — otherwise the doc lies."""
    doc = _read_doc()
    refs = _backtick_overlay_class_refs(doc)

    # Skip refs that are clearly not class names (file paths,
    # property bag examples, etc.).
    refs = {r for r in refs if "/" not in r and "." not in r}

    declared: set[str] = set()
    for py in _OVERLAYS_DIR.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        for m in re.finditer(r"^class\s+(Overlay[A-Za-z0-9_]+)", text, re.MULTILINE):
            declared.add(m.group(1))

    missing = sorted(refs - declared)
    assert not missing, (
        f"OVERLAY_PLATFORM.md references classes that do not "
        f"exist in code: {missing}. Either the class was renamed "
        f"or the doc references a draft type — update both."
    )


# ---------------------------------------------------------------------------
# Freshness marker: doc has a "Last reviewed" line
# ---------------------------------------------------------------------------


def test_doc_has_last_reviewed_marker() -> None:
    """The doc must carry an explicit "Last reviewed: <date>"
    line so future readers can spot a multi-month-stale doc at
    a glance instead of having to diff against git history."""
    doc = _read_doc()
    pattern = r"Last reviewed:\s*\d{4}-\d{2}-\d{2}"
    assert re.search(pattern, doc), (
        "OVERLAY_PLATFORM.md is missing a 'Last reviewed: "
        "YYYY-MM-DD' line. Add one near the top so readers can "
        "judge staleness."
    )
