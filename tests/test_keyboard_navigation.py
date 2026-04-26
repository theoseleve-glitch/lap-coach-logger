"""T220: Accessibility — keyboard-only navigation contract.

Pins the keyboard-shortcut contract so the app stays usable
without a mouse:

  - AppShell defines a Shortcut for every primary page (Ctrl+1..5)
  - Every page-nav Shortcut targets a known navBar page id
  - ShortcutHelpOverlay (F1) lists EVERY page-nav shortcut, with
    a description matching the page it actually navigates to —
    drift here means the help screen lies to the user
  - Essential shortcuts (Escape, F1) appear in both AppShell and
    the help overlay
  - No duplicate Shortcut sequences in AppShell — the second one
    silently wins, leading to "the docs say X but it does Y" bugs

This is a CI-safe drift-prevention pass over the QML source — we
parse string-literal sequences rather than running a Qt event
loop. The contract being pinned is "keyboard nav remains usable
and the help screen tells the truth", not "every QML control
gets a focus ring" (that's a follow-up visual scope).
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[1]
_QML_DIR = _REPO_ROOT / "src" / "lap_coach_logger" / "qml"
_APPSHELL = _QML_DIR / "AppShell.qml"
_HELP_OVERLAY = _QML_DIR / "Components" / "ShortcutHelpOverlay.qml"


# ---------------------------------------------------------------------------
# Helpers — extract Shortcut entries from QML source
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    assert path.exists(), f"missing QML file: {path}"
    return path.read_text(encoding="utf-8")


# Match `Shortcut { sequence: "Ctrl+1"; onActivated: navBar.pageRequested("dashboard") }`
# (also tolerates multi-line forms — sequence + onActivated may be on different lines).
_PAGE_NAV_SHORTCUT_RE = re.compile(
    r'sequence:\s*"(?P<seq>Ctrl\+\d+)"[^}]*?'
    r'navBar\.pageRequested\("(?P<page>[a-z]+)"\)',
    re.DOTALL,
)

# Any sequence literal in any QML file: `sequence: "X"`.
_ANY_SEQUENCE_RE = re.compile(r'sequence:\s*"([^"]+)"')

# ShortcutRow declarations in the help overlay:
# `ShortcutRow { key: "Ctrl+1"; desc: "Dashboard" }`
_SHORTCUT_ROW_RE = re.compile(
    r'ShortcutRow\s*\{\s*key:\s*"(?P<key>[^"]+)";\s*desc:\s*"(?P<desc>[^"]+)"',
)


def _extract_page_nav_shortcuts(source: str) -> dict[str, str]:
    """Return {sequence -> page_id} for every Ctrl+N page nav shortcut."""
    return {m.group("seq"): m.group("page") for m in _PAGE_NAV_SHORTCUT_RE.finditer(source)}


def _extract_all_sequences(source: str) -> list[str]:
    return _ANY_SEQUENCE_RE.findall(source)


def _extract_help_rows(source: str) -> dict[str, str]:
    """Return {key -> description} for every ShortcutRow in the help overlay."""
    return {m.group("key"): m.group("desc") for m in _SHORTCUT_ROW_RE.finditer(source)}


# Map navBar page ids → the human-readable label that should appear
# in the help overlay description. Kept loose (substring match in
# tests) so minor wording tweaks don't break the contract — we only
# care that the description names the right page.
_PAGE_LABEL_HINTS: dict[str, tuple[str, ...]] = {
    "dashboard": ("dashboard",),
    "live": ("live",),
    "strategy": ("strategy",),
    "history": ("history",),
    "overlays": ("overlay",),  # "Overlay manager", "Overlays", etc.
}


# ---------------------------------------------------------------------------
# AppShell — page-nav shortcuts exist and target known pages
# ---------------------------------------------------------------------------


def test_appshell_defines_page_nav_shortcuts_for_all_primary_pages() -> None:
    """Every primary page reachable from the navbar must be reachable
    via Ctrl+N too — without it, keyboard-only users can't switch
    pages without tab-traversing the navbar."""
    src = _read(_APPSHELL)
    page_nav = _extract_page_nav_shortcuts(src)

    expected_seqs = {f"Ctrl+{i}" for i in range(1, 6)}
    missing = expected_seqs - page_nav.keys()
    assert not missing, (
        f"AppShell.qml is missing page-nav shortcuts: {sorted(missing)}. "
        f"Found: {sorted(page_nav.keys())}"
    )


def test_appshell_page_nav_shortcuts_target_known_pages() -> None:
    """Each Ctrl+N page-nav shortcut must target a real navBar page id.
    Catches typos like ``pageRequested("liv")`` that silently no-op."""
    src = _read(_APPSHELL)
    page_nav = _extract_page_nav_shortcuts(src)

    known_pages = set(_PAGE_LABEL_HINTS.keys())
    unknown = {seq: page for seq, page in page_nav.items() if page not in known_pages}
    assert not unknown, (
        f"AppShell.qml page-nav shortcuts target unknown pages: {unknown}. "
        f"Known: {sorted(known_pages)}"
    )


def test_appshell_no_duplicate_shortcut_sequences() -> None:
    """Two Shortcut blocks with the same sequence => the second
    silently wins, and the help overlay claims one thing while
    the app does another. Forbid duplicates."""
    src = _read(_APPSHELL)
    sequences = _extract_all_sequences(src)
    counts = Counter(sequences)
    duplicates = {seq: n for seq, n in counts.items() if n > 1}
    assert not duplicates, (
        f"AppShell.qml has duplicate Shortcut sequences: {duplicates} — "
        f"only the last definition runs"
    )


def test_appshell_includes_essential_shortcuts() -> None:
    """Escape (close dialogs) and F1 (help) must always exist —
    losing them strands keyboard-only users in modals."""
    src = _read(_APPSHELL)
    sequences = set(_extract_all_sequences(src))
    for essential in ("Escape", "F1"):
        assert essential in sequences, (
            f"AppShell.qml is missing essential keyboard shortcut: {essential!r}"
        )


# ---------------------------------------------------------------------------
# ShortcutHelpOverlay — must accurately describe AppShell's contract
# ---------------------------------------------------------------------------


def test_help_overlay_lists_every_page_nav_shortcut() -> None:
    """If AppShell defines Ctrl+N for a page, the F1 help screen
    must list it. Otherwise the user has no way to discover it."""
    appshell_src = _read(_APPSHELL)
    help_src = _read(_HELP_OVERLAY)

    page_nav = _extract_page_nav_shortcuts(appshell_src)
    help_keys = set(_extract_help_rows(help_src).keys())

    missing_in_help = page_nav.keys() - help_keys
    assert not missing_in_help, (
        f"ShortcutHelpOverlay.qml is missing entries for: "
        f"{sorted(missing_in_help)} — users can't discover these shortcuts"
    )


def test_help_overlay_descriptions_match_actual_page_targets() -> None:
    """Drift-prevention: if AppShell maps Ctrl+3 to Strategy, the
    F1 help description for Ctrl+3 must mention Strategy. Catches
    the bug where a Strategy/History reorder leaves the help text
    wrong (and users navigate to the wrong page)."""
    appshell_src = _read(_APPSHELL)
    help_src = _read(_HELP_OVERLAY)

    page_nav = _extract_page_nav_shortcuts(appshell_src)
    help_rows = _extract_help_rows(help_src)

    drift: list[str] = []
    for seq, page_id in page_nav.items():
        if seq not in help_rows:
            continue  # caught by the "missing" test above
        desc = help_rows[seq].lower()
        hints = _PAGE_LABEL_HINTS.get(page_id, ())
        if not any(hint in desc for hint in hints):
            drift.append(
                f"{seq} -> page {page_id!r} but help says {help_rows[seq]!r} "
                f"(expected one of {hints})"
            )
    assert not drift, (
        "ShortcutHelpOverlay.qml descriptions don't match the actual "
        "page targets in AppShell.qml:\n  " + "\n  ".join(drift)
    )


def test_help_overlay_documents_essential_shortcuts() -> None:
    """Escape and F1 are essential — the help overlay must
    document them, otherwise users won't know how to dismiss it."""
    help_src = _read(_HELP_OVERLAY)
    help_keys = set(_extract_help_rows(help_src).keys())
    for essential in ("Escape", "F1"):
        assert essential in help_keys, (
            f"ShortcutHelpOverlay.qml is missing essential entry: {essential!r}"
        )


def test_help_overlay_does_not_list_unknown_shortcuts() -> None:
    """If the help overlay advertises a shortcut, AppShell must
    actually implement it. Otherwise pressing it does nothing
    and the help is a lie."""
    appshell_src = _read(_APPSHELL)
    help_src = _read(_HELP_OVERLAY)

    appshell_seqs = set(_extract_all_sequences(appshell_src))
    help_keys = set(_extract_help_rows(help_src).keys())

    # Help overlay uses some friendly aliases. The QML source
    # holds them as literal text (QML resolves the unicode escape
    # at parse time), so the lookup keys here use the raw forms:
    #   "Alt+1-9"        - covered by an AppShell Repeater
    #                      (sequence "Alt+1"..."Alt+9")
    #   "Ctrl+\\u2191"   - Ctrl+Up arrow
    #   "Ctrl+\\u2193"   - Ctrl+Down arrow
    aliases: dict[str, set[str]] = {
        # Alt+1..9 is wired by a Repeater whose sequence is built
        # via string concatenation (`"Alt+" + (index + 1)`), so
        # the only literal sequence in the source is "Alt+".
        "Alt+1-9": {"Alt+"} | {f"Alt+{i}" for i in range(1, 10)},
        "Ctrl+\\u2191": {"Ctrl+Up"},
        "Ctrl+\\u2193": {"Ctrl+Down"},
    }

    missing_impl: list[str] = []
    for key in help_keys:
        if key in appshell_seqs:
            continue
        alias_set = aliases.get(key)
        if alias_set and any(a in appshell_seqs for a in alias_set):
            continue
        missing_impl.append(key)

    assert not missing_impl, (
        f"ShortcutHelpOverlay.qml advertises unimplemented shortcuts: "
        f"{sorted(missing_impl)}"
    )
