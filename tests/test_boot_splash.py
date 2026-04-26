"""T239: Splash screen during boot with progress.

Pins the testable kernel of the boot-splash feature:

  - ``BOOT_PHASES`` is the canonical, ordered list of phase
    labels a splash window can show.
  - ``progress_pct(phase_index)`` maps a phase index to 0-100,
    monotonic so progress only ever advances.
  - ``next_phase(label)`` advances by name (so callers don't
    have to track an integer cursor across module boundaries).

The actual QML splash window (``Components/SplashScreen.qml``)
that subscribes to a ``BootProgressViewModel`` is deliberate
follow-up — T239 ensures the testable progress model is sound
so the visual layer has something correct to bind to.
"""
from __future__ import annotations

import pytest

from lap_coach_logger.ui import boot_splash as bs


# ---------------------------------------------------------------------------
# BOOT_PHASES: ordered, non-empty, no duplicates
# ---------------------------------------------------------------------------


def test_boot_phases_is_non_empty_ordered_list() -> None:
    """The splash needs *something* to show — an empty phase
    list would mean the splash flashes with no labels."""
    assert isinstance(bs.BOOT_PHASES, tuple)
    assert len(bs.BOOT_PHASES) >= 3, (
        f"BOOT_PHASES is too short ({len(bs.BOOT_PHASES)}) — "
        f"a splash with one phase tells the user nothing"
    )


def test_boot_phases_has_no_duplicates() -> None:
    """Duplicate labels would make ``next_phase`` ambiguous and
    the visible label would seem to stutter."""
    seen = set()
    duplicates = []
    for label in bs.BOOT_PHASES:
        if label in seen:
            duplicates.append(label)
        seen.add(label)
    assert not duplicates, (
        f"BOOT_PHASES contains duplicate labels: {duplicates}"
    )


def test_boot_phases_labels_are_user_facing_strings() -> None:
    """Phase labels are shown verbatim on the splash — they
    must be human-readable, not internal identifiers."""
    for label in bs.BOOT_PHASES:
        assert isinstance(label, str)
        assert label.strip() == label, f"phase {label!r} has whitespace at edges"
        assert len(label) >= 4, f"phase {label!r} is too short to be a UI label"
        # internal identifiers like 'load_config' (snake_case lowercase) are
        # forbidden — UI labels should be capitalized-words
        assert not (
            label.islower() and "_" in label
        ), f"phase {label!r} looks like an internal identifier, not a UI label"


# ---------------------------------------------------------------------------
# progress_pct: monotonic 0..100
# ---------------------------------------------------------------------------


def test_progress_pct_zero_at_start_hundred_at_end() -> None:
    """The splash bar fills to full only at the last phase —
    otherwise the user sees "100% — still loading…"."""
    assert bs.progress_pct(0) == 0
    assert bs.progress_pct(len(bs.BOOT_PHASES) - 1) == 100


def test_progress_pct_is_monotonic_non_decreasing() -> None:
    """Progress can pause but must never jump back; a backwards
    bar means the user thinks the boot crashed and restarted."""
    last = -1
    for i in range(len(bs.BOOT_PHASES)):
        pct = bs.progress_pct(i)
        assert pct >= last, (
            f"progress_pct({i})={pct} regressed from previous {last}"
        )
        assert 0 <= pct <= 100
        last = pct


def test_progress_pct_rejects_out_of_range_index() -> None:
    """A bad index from a caller should raise, not silently
    return -1 or 200 (which would corrupt the splash bar)."""
    with pytest.raises((IndexError, ValueError)):
        bs.progress_pct(-1)
    with pytest.raises((IndexError, ValueError)):
        bs.progress_pct(len(bs.BOOT_PHASES))


# ---------------------------------------------------------------------------
# next_phase: callers advance by label, not index
# ---------------------------------------------------------------------------


def test_next_phase_advances_by_label() -> None:
    """Bootstrap callers shouldn't need to track an integer
    cursor across modules — they pass the label they just
    finished, get back the next one."""
    first = bs.BOOT_PHASES[0]
    second = bs.BOOT_PHASES[1]
    assert bs.next_phase(first) == second


def test_next_phase_returns_none_at_end() -> None:
    """The last phase has no successor — a sentinel rather than
    raising lets the caller cleanly end the splash."""
    last = bs.BOOT_PHASES[-1]
    assert bs.next_phase(last) is None


def test_next_phase_rejects_unknown_label() -> None:
    """An unknown label is a programming error — raise so the
    bug surfaces in tests rather than the splash silently
    freezing on a stale label."""
    with pytest.raises(ValueError):
        bs.next_phase("not a real phase")
