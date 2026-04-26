"""Boot splash progress model (T239).

The application boot is a sequence of coarse user-facing
phases. The splash window shows the current label and an
0-100 progress bar derived from the phase index. This module
is the pure, testable kernel — the QML splash window and
the bootstrap-callsite wiring are deliberate follow-up.

Why a hand-curated phase list rather than auto-discovering
bootstrap.py's numbered comments: the splash is a UX surface,
not a debug trace. ``Loading configuration`` is what the user
should see; ``ConfigManager.load()`` is not.
"""
from __future__ import annotations


# Ordered, user-facing labels. Roughly aligned with the phases
# in ``bootstrap.run()`` but coarser and friendlier.
BOOT_PHASES: tuple[str, ...] = (
    "Starting up",
    "Loading configuration",
    "Preparing logs",
    "Connecting to sims",
    "Loading session history",
    "Preparing UI",
    "Ready",
)


def progress_pct(phase_index: int) -> int:
    """Map a phase index in ``[0, len(BOOT_PHASES))`` to an
    integer percentage in ``[0, 100]``.

    Phase 0 is 0% (nothing has happened yet); the last phase
    is exactly 100. Intermediate phases are spread evenly so
    the bar advances at a steady visual pace.
    """
    if phase_index < 0 or phase_index >= len(BOOT_PHASES):
        raise IndexError(
            f"phase_index {phase_index} out of range "
            f"[0, {len(BOOT_PHASES)})"
        )
    last = len(BOOT_PHASES) - 1
    if last == 0:
        return 100
    return round(phase_index * 100 / last)


def next_phase(current_label: str) -> str | None:
    """Return the label of the phase after ``current_label``,
    or ``None`` if the current phase is the last one.

    Raises ``ValueError`` if ``current_label`` is not a known
    phase — silently returning ``None`` would mask the bug
    where someone passes a stale or misspelled label.
    """
    try:
        idx = BOOT_PHASES.index(current_label)
    except ValueError as exc:
        raise ValueError(
            f"unknown boot phase {current_label!r}; "
            f"known phases: {list(BOOT_PHASES)}"
        ) from exc
    if idx == len(BOOT_PHASES) - 1:
        return None
    return BOOT_PHASES[idx + 1]


__all__ = ["BOOT_PHASES", "progress_pct", "next_phase"]
