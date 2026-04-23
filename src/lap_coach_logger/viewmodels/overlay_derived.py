"""Derived overlay state — pure functions for widget content.

These helpers translate strategy VM state into the compact, glanceable
values that QML widgets render. Decision thresholds are *race-tuned
defaults* — not exact science, but calibrated to typical GT3 sprint /
endurance scenarios from consumer sim data.

Everything here is a pure function. No Qt, no state, no I/O. This is
what makes alert logic deterministic and testable.

Strategy Runtime Consolidation sprint: pit-window + fuel-deficit
thresholds now come from ``StrategyConfig`` (single source of truth).
"""

from __future__ import annotations

from dataclasses import dataclass

from lap_coach_logger.core.pit_call_state import (
    PitCallState,
    STATE_BOX_THIS_LAP,
    STATE_IN_PIT_SEQUENCE,
    STATE_ON_PLAN,
    STATE_PIT_IN_1,
    STATE_PIT_IN_2,
    STATE_PIT_IN_3,
    STATE_PIT_IN_4,
    STATE_PIT_IN_5,
    STATE_STOP_COMPLETED,
    _LAPS_TO_STATE,
)
from lap_coach_logger.core.strategy_config import DEFAULT_STRATEGY


# ---------------------------------------------------------------------------
# Fuel-margin calibration (per car class)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClassCalibration:
    """Fuel-margin thresholds scaled by typical per-lap consumption.

    Thresholds are in LITERS. ``ok_l`` is the margin below which the
    state becomes TIGHT; ``tight_l`` is the boundary down to SAVE; below
    0 the state is DEFICIT regardless of class.

    Rule of thumb: ``ok_l`` ≈ one lap's worth of fuel for the class.
    """
    ok_l: float         # SAFE/TIGHT boundary
    tight_l: float      # TIGHT/SAVE boundary
    typical_burn_l: float  # informational — typical L/lap for this class


# GT3 is the reference (from measured iRacing GT3 sprints)
_GT3 = ClassCalibration(ok_l=1.5, tight_l=0.5, typical_burn_l=2.3)

# Class-specific profiles. Unlisted classes fall back to GT3.
# Values chosen from community-typical per-lap burn rates.
CLASS_CALIBRATIONS: dict[str, ClassCalibration] = {
    "GT3":       _GT3,
    "GT4":       ClassCalibration(ok_l=1.3, tight_l=0.4, typical_burn_l=2.0),
    "GTE":       ClassCalibration(ok_l=2.0, tight_l=0.7, typical_burn_l=2.8),
    "LMP2":      ClassCalibration(ok_l=2.2, tight_l=0.8, typical_burn_l=3.2),
    "Hypercar":  ClassCalibration(ok_l=1.8, tight_l=0.6, typical_burn_l=2.6),
    "Formula":   ClassCalibration(ok_l=1.0, tight_l=0.3, typical_burn_l=1.6),
    "Cup":       ClassCalibration(ok_l=1.4, tight_l=0.5, typical_burn_l=2.1),
    "Touring":   ClassCalibration(ok_l=1.0, tight_l=0.3, typical_burn_l=1.5),
}

# Legacy module-level constants preserved for callers that used them
# directly. These remain GT3-tuned so pre-existing behaviour is unchanged
# when no class is supplied. ``FUEL_SAVE_MARGIN_L`` now sources from
# ``StrategyConfig`` so the DEFICIT boundary has a single home.
FUEL_OK_MARGIN_L = _GT3.ok_l
FUEL_TIGHT_MARGIN_L = _GT3.tight_l
FUEL_SAVE_MARGIN_L = DEFAULT_STRATEGY.fuel_deficit_margin_l


def get_class_calibration(car_class: str | None) -> ClassCalibration:
    """Look up thresholds for a class, falling back to GT3 safely.

    Accepts case-insensitive class strings. Unknown or empty class →
    GT3 defaults (the safest middle-ground for a misc race car).
    """
    if not car_class:
        return _GT3
    # Case-insensitive lookup
    key = car_class.strip()
    if key in CLASS_CALIBRATIONS:
        return CLASS_CALIBRATIONS[key]
    # Try title-case normalisation (e.g. "gt3" → "GT3")
    upper = key.upper()
    if upper in CLASS_CALIBRATIONS:
        return CLASS_CALIBRATIONS[upper]
    title = key.title()
    if title in CLASS_CALIBRATIONS:
        return CLASS_CALIBRATIONS[title]
    return _GT3


def compute_fuel_state(
    fuel_margin_l: float,
    car_class: str | None = None,
) -> str:
    """Map fuel margin to an overlay state word using class calibration.

    Returns one of: "SAFE", "TIGHT", "SAVE", "DEFICIT".
    Unknown car_class → GT3 thresholds.
    """
    cal = get_class_calibration(car_class)
    if fuel_margin_l >= cal.ok_l:
        return "SAFE"
    if fuel_margin_l >= cal.tight_l:
        return "TIGHT"
    if fuel_margin_l >= FUEL_SAVE_MARGIN_L:
        return "SAVE"
    return "DEFICIT"


# ---------------------------------------------------------------------------
# Strategy status (compact one-liner for always-on banner)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StrategyStatusContent:
    """Compact strategy state for the always-on status banner."""
    line: str                # "P5 · L9/20 · Fuel SAFE · Grip 82%"
    severity: str            # "ok" / "advisory" / "critical" — drives color


def build_strategy_status(
    *,
    position: int | None,
    current_lap: int,
    total_laps: int,
    fuel_state: str,
    grip_pct: float | None = None,
    laps_to_pit: int = -1,
    pit_now: bool = False,
) -> StrategyStatusContent:
    """Build the compact strategy status line and severity.

    Severity is the highest-priority signal:
    - critical: pit now OR fuel deficit
    - advisory: fuel tight/save OR pit in ≤3 laps
    - ok: everything on plan
    """
    parts: list[str] = []

    if position and position > 0:
        parts.append(f"P{position}")
    if total_laps > 0 and current_lap > 0:
        parts.append(f"L{current_lap}/{total_laps}")
    elif current_lap > 0:
        parts.append(f"L{current_lap}")

    parts.append(f"Fuel {fuel_state}")

    if grip_pct is not None and grip_pct > 0:
        parts.append(f"Grip {int(round(grip_pct))}%")

    # Severity ladder (highest wins)
    if pit_now or fuel_state == "DEFICIT":
        severity = "critical"
    elif fuel_state in ("SAVE", "TIGHT") or (0 < laps_to_pit <= 3):
        severity = "advisory"
    else:
        severity = "ok"

    return StrategyStatusContent(
        line=" \u00b7 ".join(parts),  # "·" separator
        severity=severity,
    )


# Severity for each pit-call state — single source of truth so the
# status banner and countdown widget can never disagree. Pit-in-4/5
# are "ok" for the banner (the widget still renders them, but the
# one-liner isn't loud about it). Pit-in-2/3 raise advisory.
_PIT_STATE_SEVERITY = {
    STATE_ON_PLAN: "ok",
    STATE_PIT_IN_5: "ok",
    STATE_PIT_IN_4: "ok",
    STATE_PIT_IN_3: "advisory",
    STATE_PIT_IN_2: "advisory",
    STATE_PIT_IN_1: "critical",
    STATE_BOX_THIS_LAP: "critical",
    STATE_IN_PIT_SEQUENCE: "advisory",
    STATE_STOP_COMPLETED: "ok",
}


def build_strategy_status_from_state(
    *,
    position: int | None,
    current_lap: int,
    total_laps: int,
    fuel_state: str,
    pit_state: PitCallState,
    grip_pct: float | None = None,
) -> StrategyStatusContent:
    """PitCallState-driven strategy status — the consolidated path.

    Derives severity from the same state machine the pit_countdown
    widget uses, so the two widgets can't show contradictory levels
    (e.g. "BOX BOX BOX" + calm steel banner).
    """
    parts: list[str] = []
    if position and position > 0:
        parts.append(f"P{position}")
    if total_laps > 0 and current_lap > 0:
        parts.append(f"L{current_lap}/{total_laps}")
    elif current_lap > 0:
        parts.append(f"L{current_lap}")
    parts.append(f"Fuel {fuel_state}")
    if grip_pct is not None and grip_pct > 0:
        parts.append(f"Grip {int(round(grip_pct))}%")

    # Severity ladder (highest wins): pit-state critical or fuel deficit,
    # then fuel save/tight or pit advisory, else ok.
    pit_severity = _PIT_STATE_SEVERITY.get(pit_state.state, "ok")
    if pit_severity == "critical" or fuel_state == "DEFICIT":
        severity = "critical"
    elif fuel_state in ("SAVE", "TIGHT") or pit_severity == "advisory":
        severity = "advisory"
    else:
        severity = "ok"

    return StrategyStatusContent(
        line=" \u00b7 ".join(parts),
        severity=severity,
    )


# ---------------------------------------------------------------------------
# Push / Manage / Save (endurance only)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PushManageState:
    """PUSH / MANAGE / SAVE / HOLD decision for endurance driving.

    `state` is one of:
      - PUSH    — drive it; everything is fine
      - MANAGE  — tires are fading; back off 1-2 tenths per lap
      - SAVE    — fuel critical; lift-and-coast
      - HOLD    — gaps are stable; protect position (deferred — requires
                  reliable gap data from adapter)

    `confidence` reflects how much the inputs can be trusted:
      - "high"   — all live signals present (fuel + grip + stint + plan)
      - "medium" — some inputs missing but decision still clear
      - "low"    — working from defaults / stale data; hint the driver
    """
    state: str
    reason: str
    confidence: str = "medium"
    hint: str = ""          # one-line driver instruction


def compute_push_manage(
    *,
    fuel_margin_l: float,
    fuel_state: str,
    grip_pct: float | None = None,
    laps_remaining_in_stint: int | None = None,
    stint_lap: int | None = None,
    stint_total_laps: int | None = None,
    has_live_stint_data: bool | None = None,
) -> PushManageState:
    """Decide whether the driver should PUSH, MANAGE, SAVE, or HOLD.

    Priority ladder (first match wins):
    1. Fuel DEFICIT           → SAVE (critical fuel)
    2. Fuel SAVE or TIGHT     → SAVE (margin shrinking)
    3. Tire grip < 55%        → MANAGE (rubber going)
    4. Late stint + grip<70%  → MANAGE (preserve what's left)
    5. All inputs nominal     → PUSH (drive it)

    Confidence:
    - `has_live_stint_data=True` + grip known + fuel_state known → high
    - Partial inputs → medium
    - Only fuel_state known → low (but still outputs a safe decision)

    Hint strings are short enough for a 200×60 widget. They complement
    the one-word state so the driver knows WHAT to do, not just that
    something is wrong.
    """
    # Confidence baseline from input completeness
    live_stint = has_live_stint_data if has_live_stint_data is not None else (
        stint_lap is not None and stint_total_laps is not None
    )
    have_grip = grip_pct is not None
    if live_stint and have_grip:
        base_conf = "high"
    elif have_grip or live_stint:
        base_conf = "medium"
    else:
        base_conf = "low"

    # 1. Fuel critical
    if fuel_state == "DEFICIT":
        return PushManageState(
            state="SAVE",
            reason="Fuel deficit — pit early or lift heavily",
            confidence=base_conf,
            hint="Lift and coast; short-shift on straights",
        )

    # 2. Fuel tight but recoverable
    if fuel_state in ("SAVE", "TIGHT"):
        return PushManageState(
            state="SAVE",
            reason=f"Fuel {fuel_state.lower()} — 0.1 L/lap save needed",
            confidence=base_conf,
            hint="Lift 50m earlier on main straight",
        )

    # 3. Grip collapsed
    if have_grip and grip_pct < 55.0:
        return PushManageState(
            state="MANAGE",
            reason=f"Grip {int(round(grip_pct))}% — nurse tires to pit window",
            confidence=base_conf,
            hint="Smooth inputs, earlier apex, protect rears",
        )

    # 4. Late stint + grip fading
    if (
        live_stint
        and stint_total_laps is not None
        and stint_total_laps > 0
        and have_grip
        and stint_lap is not None
        and stint_lap > (stint_total_laps * 2 / 3)
        and grip_pct < 70.0
    ):
        return PushManageState(
            state="MANAGE",
            reason="Late-stint tire preservation",
            confidence=base_conf,
            hint="Trade 1-2 tenths for tire life",
        )

    # 5. All clear — drive it
    return PushManageState(
        state="PUSH",
        reason="All systems on plan",
        confidence=base_conf,
        hint="Full attack",
    )


# ---------------------------------------------------------------------------
# Pit countdown display rules
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PitCountdownDisplay:
    """Rules for when and how to render the pit countdown widget."""
    visible: bool               # show the widget at all?
    headline: str               # "PIT IN 3" / "BOX BOX BOX" / ""
    sub: str                    # "38L · Keep tires" / ""
    severity: str               # "ok" / "advisory" / "critical"


def build_pit_countdown_display(
    *,
    laps_to_pit: int,
    pit_fuel_load: float,
    fuel_state: str,
    window_laps: int | None = None,
) -> PitCountdownDisplay:
    """Decide whether the pit countdown widget should show and what.

    Visibility:
    - Always hidden when laps_to_pit is unknown (-1) or > window_laps
    - Visible in final N laps of a stint
    - Critical on last lap: "BOX BOX BOX"

    ``fuel_state`` is from ``compute_fuel_state`` — flipping to DEFICIT
    while the widget is visible escalates severity to critical.

    ``window_laps`` defaults to ``DEFAULT_STRATEGY.pit_window_laps`` so
    the widget and state machine share a single horizon.
    """
    if window_laps is None:
        window_laps = DEFAULT_STRATEGY.pit_window_laps
    if laps_to_pit < 0:
        return PitCountdownDisplay(False, "", "", "ok")
    if laps_to_pit > window_laps:
        return PitCountdownDisplay(False, "", "", "ok")

    if laps_to_pit == 0:
        return PitCountdownDisplay(
            visible=True,
            headline="BOX BOX BOX",
            sub=(f"{pit_fuel_load:.1f}L" if pit_fuel_load > 0 else "pit now"),
            severity="critical",
        )
    if laps_to_pit == 1:
        return PitCountdownDisplay(
            visible=True,
            headline="PIT NEXT LAP",
            sub=(f"{pit_fuel_load:.1f}L fuel" if pit_fuel_load > 0 else "prepare to pit"),
            severity="critical",
        )

    # advisory window
    sub = f"{pit_fuel_load:.1f}L fuel" if pit_fuel_load > 0 else ""
    severity = "critical" if fuel_state == "DEFICIT" else "advisory"
    return PitCountdownDisplay(
        visible=True,
        headline=f"PIT IN {laps_to_pit}",
        sub=sub,
        severity=severity,
    )


# ---------------------------------------------------------------------------
# PitCallState → display (Strategy Runtime Consolidation)
# ---------------------------------------------------------------------------

# Map each state-machine label to the headline the widget renders.
# Keeps presentation-only wording out of the pure state machine.
_STATE_TO_HEADLINE = {
    STATE_BOX_THIS_LAP: "BOX BOX BOX",
    STATE_PIT_IN_1: "PIT NEXT LAP",
    STATE_IN_PIT_SEQUENCE: "IN PITS",
    STATE_STOP_COMPLETED: "STOP DONE",
}


def build_pit_countdown_from_state(
    *,
    state: PitCallState,
    pit_fuel_load: float,
    fuel_state: str,
) -> PitCountdownDisplay:
    """PitCallState-driven variant — the consolidated path.

    Returns the same ``PitCountdownDisplay`` shape as
    ``build_pit_countdown_display`` but sources visibility + headline
    from the deterministic state machine so the widget can't diverge
    from the machine's progression.
    """
    label = state.state
    if label == STATE_ON_PLAN:
        return PitCountdownDisplay(False, "", "", "ok")

    if label == STATE_BOX_THIS_LAP:
        return PitCountdownDisplay(
            visible=True,
            headline=_STATE_TO_HEADLINE[label],
            sub=(f"{pit_fuel_load:.1f}L" if pit_fuel_load > 0 else "pit now"),
            severity="critical",
        )
    if label == STATE_PIT_IN_1:
        return PitCountdownDisplay(
            visible=True,
            headline=_STATE_TO_HEADLINE[label],
            sub=(f"{pit_fuel_load:.1f}L fuel" if pit_fuel_load > 0 else "prepare to pit"),
            severity="critical",
        )
    if label in (STATE_IN_PIT_SEQUENCE, STATE_STOP_COMPLETED):
        return PitCountdownDisplay(
            visible=True,
            headline=_STATE_TO_HEADLINE[label],
            sub="",
            severity="ok",
        )

    # pit_in_5 / 4 / 3 / 2 — advisory countdown. Recover N from the
    # reverse map rather than string-splitting the label.
    n = next((k for k, v in _LAPS_TO_STATE.items() if v == label), None)
    if n is None:
        return PitCountdownDisplay(False, "", "", "ok")
    sub = f"{pit_fuel_load:.1f}L fuel" if pit_fuel_load > 0 else ""
    severity = "critical" if fuel_state == "DEFICIT" else "advisory"
    return PitCountdownDisplay(
        visible=True,
        headline=f"PIT IN {n}",
        sub=sub,
        severity=severity,
    )


# ---------------------------------------------------------------------------
# Alert priority classification
# ---------------------------------------------------------------------------

# Severity in descending priority. Used to cap how many simultaneous
# alerts the UI layer renders (critical never masks, advisory may stack,
# silent never renders while driving).
SEVERITY_ORDER = {"critical": 3, "advisory": 2, "ok": 1, "silent": 0}


def highest_severity(*severities: str) -> str:
    """Return the highest-priority severity from the given args."""
    if not severities:
        return "ok"
    return max(severities, key=lambda s: SEVERITY_ORDER.get(s, 0))
