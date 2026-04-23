# Hero Workflow — Design Spec

## Positioning

**Desktop = capture + live overlay + deterministic race ops + low latency**
**Webapp = history + coaching review + collaboration + shared strategy + remote engineer**

The desktop app doesn't try to be everything. It captures data reliably,
shows the minimum needed during driving, runs deterministic strategy math,
and syncs to the webapp for everything else.

## Mode System

### How Modes Work

On session connect, the app auto-detects a suggested mode from the sim's
session type. The user can override at any time via a mode selector.

| Sim Session Type | Suggested Mode |
|-----------------|----------------|
| Practice | Coaching |
| Qualifying | Coaching |
| Race (< 45 min) | Sprint Race |
| Race (≥ 45 min) | Endurance |
| Time Trial | Coaching (hotlap preset) |
| Test Day | Just Data |

Each mode configures:
- Which overlays are enabled by default
- Which panels appear in the Strategy page
- What level of coaching feedback is active
- What alerts are shown vs suppressed

### Mode Selector UI

When the app first connects to a sim session, a brief mode banner appears:

```
┌──────────────────────────────────────────┐
│  Detected: Sprint Race · Monza · GT3     │
│                                          │
│  ● SPRINT  ○ ENDURANCE  ○ COACHING  ○ DATA │
│                                          │
│  [Continue]                              │
└──────────────────────────────────────────┘
```

This appears once per session. After that, mode is changeable from the
nav bar (small mode indicator next to the status).

---

## Mode 1: Sprint Race

**Goal:** Low cognitive load, at-a-glance execution.

### Default Overlays (minimal set)

| Overlay | Purpose |
|---------|---------|
| Relative | Gaps to cars ahead/behind |
| Radar | Proximity/blind spot awareness |
| Fuel | Fuel to end, laps remaining, state (SAFE/TIGHT/SAVE/BOX) |
| Standings | Position + class if multi-class |
| Track map | Current position on track |

All other overlays OFF by default. User can enable more.

### Strategy Page in Sprint Mode

Simplified 2-step flow (no Practice tab — sprint races don't have
2-3 hours of practice, you're often jumping straight in):

**SETUP tab** (pre-race):
- Fuel calculator: race laps × fuel/lap = starting fuel
- Pit window: mandatory stop helper (if applicable)
- One-click pit presets: "Fill to end", "Splash and go", "Full service"
- Tire compound selector (if mandatory compound change)
- Source: auto-populated from any prior stints on this track+car,
  or from the current session's opening laps

**LIVE tab** (during race):
- Fuel countdown: laps/fuel remaining, projected finish
- Pit window status: "Pit window opens lap 12-18"
- Only critical alerts: "FUEL SAVE", "PIT THIS LAP", "WRONG TIRE"
- Divergence from plan (if plan exists)

### Coaching Level: None

Sprint mode is execution-focused. No technique coaching during the race.
Pre-race coaching happens in Coaching mode if the user practices first.

---

## Mode 2: Endurance

**Goal:** Pit wall + team operations.

### Default Overlays

Same as Sprint, plus:
| Overlay | Purpose |
|---------|---------|
| Strategy | Stint timeline, next pit, fuel to add |
| Tire Life | Degradation state per corner |
| Session Timer | Race time remaining |

### Strategy Page in Endurance Mode

Full 3-tab workflow from the race weekend spec:

**PRACTICE tab:**
- Compound readiness dashboard
- Practice nudges
- Auto-capture of stint data
- Self-vs-self consistency view (lap time std dev over stints)

**BUILD tab:**
- Race parameters (timed race mode, duration)
- All compound profiles with fitted models
- Per-stop pit cost breakdown (transit + fuel rate + tire change)
- "Process Strategy" → generates plan

**RACE PLAN tab:**
- Full strategy timeline with pit windows
- Per-stop fuel to add (variable, from pit profile)
- Warmup penalty indicators
- Weather overlay (iRacing)
- Race statistics (estimated laps, targets, best/worst case)
- Live divergence tracking + auto-recalculation

### Second-Screen / Pitwall (Future — Webapp)

Endurance mode is where the webapp pitwall becomes essential:
- Shared strategy view for team members
- Remote pit commands (LMU Engineer Mode integration)
- Full stint history across drivers
- Strategy versioning ("Plan A" / "Plan B")

For now (desktop only): the Strategy page IS the pitwall. Webapp
integration comes later.

### Coaching Level: Pre-race only

During the practice phase (PRACTICE tab), show readiness + nudges.
During the race, switch to execution mode — informational only.

---

## Mode 3: Coaching

**Goal:** Shorten practice time, improve consistency.

### Default Overlays

| Overlay | Purpose |
|---------|---------|
| Delta | Lap delta vs personal best or reference |
| Inputs | Throttle/brake/steering trace |
| Coaching | Corner-by-corner tips (from LiveCoachTracker) |
| Sector bars | Sector comparison |

Strategy overlays (fuel, standings) OFF by default — this is practice.

### Strategy Page in Coaching Mode

Coaching mode replaces the Strategy page with a **Practice Lab**:

**CONSISTENCY tab:**
- Self-vs-self analysis: lap time distribution chart
- Std dev trend: is consistency improving over the session?
- Per-corner consistency: which corners have the most variance?
- "Your most inconsistent corner is T5: ±0.4s. Focus here."
- Repeatable section identification (where you're already locked in)

**PACE tab:**
- Best lap breakdown by sector
- Theoretical best (sum of best sectors)
- Delta to reference (if reference lap available)
- "Gain available" per sector: where the biggest improvements are
- Link to webapp for detailed telemetry comparison

**READINESS tab:**
- Same readiness dashboard as Endurance PRACTICE tab
- But contextual: "Ready for qualifying?" / "Ready for race?"
- Combines consistency + pace + data sufficiency
- "You're consistent enough to race. Your biggest gain is S2 entry."

### Hotlap Preset

When session type is Time Trial or user selects "Hotlap" preset:
- Only show PACE tab
- Delta overlay prominent
- No readiness/strategy — pure performance
- Track records display

### Coaching Level: Active

Prescriptive during practice:
- "Focus on braking consistency in T3-T4"
- "You're losing 0.3s in S2 from late throttle application"
- "Your last 5 laps were within ±0.2s — good consistency"

Informational during qualifying:
- Delta only, no prescriptive tips (don't distract)

---

## Mode 4: Just Data

**Goal:** Trust. Show everything, prescribe nothing.

### Default Overlays

All overlays available but minimal enabled by default:
- Relative
- Radar
- Fuel
- Track map

### Strategy Page in Just Data Mode

**TELEMETRY tab:**
- Raw channel viewer: select any telemetry channel, see the live trace
- Per-lap data table: every channel, every lap, exportable
- Data quality indicators: sample rate, gaps, staleness

**EXPORT tab:**
- Export current session to CSV/Parquet
- Export stint profiles to JSON
- Webapp sync status
- "Export to MoTeC format" (future)

**STRATEGY tab** (optional, same as Sprint SETUP):
- Available if user wants it
- No auto-suggestions — just the calculator

### Coaching Level: None

No prescriptions. The tool shows data with confidence indicators.
Advanced users want to see that the system isn't making things up.
This mode is how you build trust with the skeptics.

---

## Self-vs-Self Consistency Analyzer (New Feature)

This is the #1 gap identified in the research. Lives primarily in
Coaching mode but available in all modes.

### What it measures

Per-lap:
- Lap time vs. session median
- Sector times vs. sector median
- Corner entry speed vs. corner median
- Braking point vs. braking median
- Throttle application point vs. throttle median

Per-section (corner clusters):
- Standard deviation of lap time through each section
- "Variance score" = how repeatable you are through that section
- Trend: improving, stable, or deteriorating over the session

### How it's computed

From the existing `LiveCornerTracker` (corner detection) and
`LiveCoachTracker` (per-lap coaching points):

```python
def compute_consistency_analysis(
    lap_times: list[float],
    sector_times: list[list[float]],
    corner_metrics: list[dict],
) -> ConsistencyReport
```

Returns:
- `overall_std_dev_s`: standard deviation of lap times
- `consistency_pct`: 100 - (std_dev / median * 100), capped 0-100
- `per_sector_std_dev`: std dev per sector
- `worst_sector`: sector with highest variance
- `worst_corners`: top 3 corners by variance
- `trend`: "improving" / "stable" / "degrading" over last 10 laps
- `recommendation`: one-line coaching tip

### UI

In the CONSISTENCY tab (Coaching mode):

```
┌─ CONSISTENCY SCORE ───────────────────────┐
│                                           │
│  Overall: 87%  · ±0.38s                   │
│  ████████████████████░░░  Improving ↑     │
│                                           │
│  S1  ±0.12s  ████████████████████  98%    │
│  S2  ±0.45s  ████████████░░░░░░░  76%    ← Focus here
│  S3  ±0.22s  █████████████████░░  91%    │
│                                           │
│  Most variable corners:                   │
│  T5 (S2 entry)   ±0.31s                   │
│  T8 (chicane)    ±0.28s                   │
│  T3 (braking)    ±0.19s                   │
│                                           │
│  💡 S2 entry speed varies ±8 kph.         │
│     Lock braking point at the 80m board.  │
└───────────────────────────────────────────┘
```

---

## Mode Detection Logic

```python
def suggest_mode(
    session_type: str,
    race_duration_s: float | None,
    is_timed_race: bool,
) -> str:
    if session_type in ("practice", "qualifying", "lone qualify", "open qualify"):
        return "coaching"
    if session_type in ("time trial",):
        return "coaching"  # hotlap preset
    if session_type in ("race",):
        if is_timed_race or (race_duration_s and race_duration_s > 2700):
            return "endurance"
        return "sprint"
    return "data"  # test day, unknown
```

The user can override at any time. The override persists for the session.

---

## Implementation Scope

### What to build now (desktop v2.1)

1. **Mode selector UI** — banner on session connect + nav bar indicator
2. **Sprint mode** — simplified 2-tab strategy (Setup + Live)
3. **Consistency analyzer** — self-vs-self analysis module
4. **Coaching mode** — 3-tab practice lab (Consistency + Pace + Readiness)
5. **Mode-aware overlay defaults** — each mode pre-configures which overlays are on

### What exists and needs reorganization

- Endurance mode = the current 3-tab workflow (Practice/Build/Race Plan) — already built
- Just Data mode = raw data view + export — partially exists in the Logs page
- Overlay system — already has 44 widgets, just needs mode-aware defaults

### What to defer to webapp

- Second-screen pitwall
- Remote engineer (LMU)
- Shared strategy / team collaboration
- Deep telemetry comparison (VRS-style)
- Video replay integration
- Strategy versioning

### What to cut entirely

- Competitor strategy prediction (v2+)
- Safety car probability (v2+)
- Auto mid-race strategy changes (too fragile — trust issue)
- Deep setup-strategy linkage as hero (users want it as support, not primary)

## Files to Create

| File | Purpose |
|------|---------|
| `src/lap_coach_logger/core/consistency_analyzer.py` | Self-vs-self consistency computation |
| `src/lap_coach_logger/core/mode_detector.py` | Session type → suggested mode |
| `src/lap_coach_logger/viewmodels/mode_vm.py` | Mode state + QML properties |
| `src/lap_coach_logger/qml/Components/ModeBanner.qml` | Session-start mode selector |
| `src/lap_coach_logger/qml/Pages/StrategyPage.qml` | Restructured per-mode tabs |
| `tests/test_consistency_analyzer.py` | Consistency analysis tests |
| `tests/test_mode_detector.py` | Mode detection tests |

## Files to Modify

| File | Change |
|------|--------|
| `src/lap_coach_logger/viewmodels/strategy_vm.py` | Mode-aware tab selection, consistency data exposure |
| `src/lap_coach_logger/viewmodels/overlay_vm.py` | Mode-aware overlay defaults |
| `src/lap_coach_logger/qml/AppShell.qml` | Mode banner integration, nav bar mode indicator |
| `src/lap_coach_logger/qml/Components/NavBar.qml` | Mode indicator badge |
| `src/lap_coach_logger/qml_bootstrap.py` | ModeViewModel creation + wiring |
