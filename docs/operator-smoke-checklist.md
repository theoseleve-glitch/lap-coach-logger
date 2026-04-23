# Operator Smoke Validation Checklist

> **Who:** release engineer or QA before pushing a build to users.
> **When:** after every change that touches `overlay_vm`, widget QML,
> or adapter signal plumbing.
> **Scope:** visual smoke only — verifies the new widgets render,
> receive state, degrade cleanly, and don't crash the overlay.

Unit tests cover the Python logic exhaustively. This checklist covers
the things only a human eye can verify: rendering, pulse animations,
alignment, and the "does it feel right while driving" gut check.

## Prerequisites

- [ ] Latest build launched (`scripts/run.bat` or the frozen exe)
- [ ] Overlay window visible
- [ ] Active mode set to **Endurance** (gives the widest widget set)
- [ ] Enable the 7 core widgets if not auto-enabled:
      `strategy_status`, `pit_countdown`, `delta_bar`, `sector_delta`,
      `fuel_strategy`, `radar`, `push_manage`

## Smoke scenarios

Trigger from the Overlay Manager page → **"Smoke test"** dropdown
(calls `overlayVM.injectSmokeState(scenario)`). Each scenario takes
< 5 seconds to observe.

### 0. Race reminder card (unified coaching surface)

| Scenario | Expected on race_reminder widget |
|---|---|
| `coaching_live` | Visible with accent-green headline "T5: …", focus label "T5", live freshness dot |
| `coaching_carryover` | Visible at ~80% opacity, amber freshness dot, focus label "T7" |
| `coaching_suppressed` | Widget hidden (simulates critical alert suppression) |
| `clear` | Widget hidden |

- [ ] All four render
- [ ] Freshness dot color changes live → carryover (accent green → amber)
- [ ] Headline truncation at ~48 chars with ellipsis
- [ ] Widget never overlaps with `strategy_status` or `pit_countdown`


### 1. Pit countdown rendering

| Scenario | Expected on pit_countdown widget |
|---|---|
| `pit_advisory` | Shows `PIT IN 3` in **amber**, sub-text `40.0L fuel` |
| `pit_now` | Shows `PIT NEXT LAP` in **red** with pulse, sub `40.0L fuel` |
| `box_box_box` | Shows `BOX BOX BOX` in **red** with pulse, sub `40.0L` |

- [ ] All three render
- [ ] Red pulse is visible but not frantic (≈1 Hz)
- [ ] Widget disappears when scenario = `clear`

### 2. Strategy status banner

| Scenario | Expected on strategy_status widget |
|---|---|
| `pit_now` | Severity dot turns red, text color red |
| `fuel_deficit` | Severity dot red, line contains `Fuel DEFICIT` |
| `push_manage_save` | Severity dot amber, line contains `Fuel SAVE` |
| `clear` | Severity dot grey/steel |

- [ ] Line always visible, text never overflows the 400×40 box
- [ ] Severity dot color matches the text color

### 3. Sector delta

| Scenario | Expected on sector_delta widget |
|---|---|
| `sector_delta` | S1=`-0.20` green, S2=`+0.30` red, S3=`—` muted |
| `clear` | All three cells show `—` at ~40% opacity |

- [ ] Values centered in their cells
- [ ] Green/red coloring correct
- [ ] `—` visible but muted (not prominent)

### 4. Gap timing

| Scenario | Expected on gap_timing widget |
|---|---|
| `gap_available` | Left cell `AHEAD P4 +1.2s`, right `BEHIND P6 +0.8s` |
| `gap_missing` | Both cells show `—` at ~40% opacity |

- [ ] Position numbers appear after the direction label
- [ ] Degraded state is distinguishable from zero

### 5. Push / Manage / Save

| Scenario | Expected on push_manage widget |
|---|---|
| `push_manage_save` | Big word `SAVE` red; hint mentions "Lift and coast" |
| `fuel_deficit` | Big word `SAVE` red; hint mentions "pit early" |
| `clear` | Big word `PUSH` green; hint `Full attack` |

- [ ] Word is the visual anchor (≈22px)
- [ ] Hint is legible but clearly secondary

### 6. No-crash / degraded path

- [ ] Without any sim running, open the overlay: every widget renders
      with `—` placeholders (no blank boxes, no error logs)
- [ ] Disable every widget, then re-enable all at once: no layout jump,
      no console errors

## Live session (if sim available)

Run a short session in iRacing AND one in ACC (no ACC gap data — so
gap widget will degrade):

- [ ] **iRacing sprint race (10 laps)**:
  - strategy_status shows `P? · L?/10 · Fuel SAFE` within 2 laps
  - In last 5 laps of stint: `PIT IN 5` appears, counts down
  - At pit lap 0: `BOX BOX BOX` appears with pulse
  - gap_timing populates with real values when you're within 5s of a car
- [ ] **ACC race**:
  - strategy_status works (fuel + lap)
  - gap_timing stays degraded (ACC adapter doesn't expose gap data —
    this is expected and correct)
- [ ] **LMU race**:
  - gap_timing populates when `mTimeBehindNext` has a valid value
  - position_ahead / position_behind derived from `mPlace` of neighbours

## Acceptance

A build ships when:
- [ ] All smoke scenarios above pass visually
- [ ] No uncontrolled CRITICAL log lines during the runs
- [ ] `python -m pytest tests/ -q` stays at 1163+ passed

## Rollback signal

If any scenario crashes the overlay window or produces a traceback in
`%LOCALAPPDATA%\LapCoachLogger\logs\lap_coach_logger.log`:
- Capture the log
- File the issue with the scenario name
- Revert to the previous build
