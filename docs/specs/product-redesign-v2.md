# Product Redesign v2 — Lap Coach Logger

> **Status:** Implementation-ready spec. Derived from the 2026-04-17 product audit.
> **Constraint:** No new physics, no black-box AI, no feature bloat. Wire what exists. Cut what distracts.

---

## 1. Product Positioning

**One sentence:**

> Lap Coach is a race engineer that rides with you — it builds your strategy from practice, calls your pit stops live, and shows you exactly where you're losing time.

**One paragraph:**

Lap Coach connects the gap between practice and race day. During practice, it measures your fuel burn, tire wear, and lap consistency to build a data-driven race plan. When the green flag drops, it doesn't go silent — it tracks your actual consumption against the plan, warns you when conditions shift, and tells you the lap to pit, how much fuel to take, and whether to push or save. Between sessions, it shows you the exact corners where you lose time compared to your own best, so you know what to work on next. It works offline, runs on your machine, and supports iRacing, Le Mans Ultimate, ACC, and Assetto Corsa.

**What changes from current identity:**
- Drops "telemetry logger + overlays + strategy + coaching" — that's a feature list, not a product
- Leads with the race-day value prop: live strategy + pit calls
- "Race engineer that rides with you" is the identity test: every feature must serve that metaphor or be cut

---

## 2. Redesigned User Workflows

### A. Practice workflow

**What the user sees first:**
App launches → sim detected → Coaching mode auto-selected for practice sessions. The Strategy page opens to the **Practice tab**, which shows a live readiness dashboard: a single card per concern (fuel model, tire model, pit time, consistency) with a fill bar and a count ("Fuel: 8/10 laps — 2 more for confident model").

**What the system decides automatically:**
- Mode: Coaching (for practice/qualifying)
- Recording: on
- Stint detection: on (auto-records pit stops for pit-time model)
- Coaching plan: generated after lap 3, re-evaluated every 5 laps
- Canonical resolution: at finalize, from bundled LUT

**What the user decides manually:**
- Nothing required. Zero-config works.
- Optional: set target lap count, choose a compound to focus on, override mode

**What changes:**
- Readiness now has CONSEQUENCES. When a model reaches "confident" (fuel: 10+ laps, tires: 10+ laps, pit: 1+ measured stop), the Practice tab shows a green checkmark and the text: **"Fuel model ready — race strategy can optimize fuel loads."** When ALL models are confident, a banner appears: **"Ready to race. Switch to Sprint or Endurance to build your plan."** This is not a gate — the user can race without it — but it's a visible, satisfying milestone that gives the practice purpose.
- Coaching overlay shows **technique comparison**, not just variance labels (see §5)
- After session: bundle v2 written, analysis.json computed, uploaded if sync enabled

**What gets removed:**
- The "nudges" system (text strings like "Run 5 more laps on soft") — replaced by the visual readiness dashboard which communicates the same information without reading text

### B. Sprint race workflow

**What the user sees first:**
User enters a race session in the sim → app auto-detects → ModeBanner suggests Sprint. Strategy page opens to **Race Plan tab** showing:

```
┌──────────────────────────────────────────────────────────┐
│  MONZA · Ferrari 296 GT3 · Sprint 20 laps                │
│                                                          │
│  STINT 1: Laps 1–12 · Soft · Start 55L                  │
│  ──── PIT ──── 38L fuel · Keep tires ────                │
│  STINT 2: Laps 13–20 · Soft · Grip 78% at finish        │
│                                                          │
│  Total time: 31:42  ·  Fuel at finish: 2.1L             │
│  Confidence: HIGH (12 practice laps on this compound)    │
│                                                          │
│  [Edit Plan]  [Re-optimize]                              │
└──────────────────────────────────────────────────────────┘
```

If no practice data exists: plan shows "Insufficient data — using fallback estimates" with LOW confidence badge. The plan still generates (using 25s pit time, 2%/lap wear, flat fuel average from first 3 laps) but the user sees exactly what's estimated vs measured.

**What the system decides automatically:**
- Pit lap, fuel load, compound selection — from `optimize_strategy()`
- Live recalculation fires every lap (see §3)
- Alerts fire when divergence exceeds thresholds

**What the user decides manually:**
- Accept or edit the pre-race plan (stint lengths, fuel amounts)
- Override a pit call if they disagree ("I'll stay out 1 more lap")

**During race — what changes:**
The Race Plan tab transforms into a **Live Strategy Dashboard**:

```
┌──────────────────────────────────────────────────────────┐
│  LAP 9/20 · P5 · Stint 1                                │
│                                                          │
│  PIT IN 3 LAPS (end of lap 12)                          │
│  Fuel load: 38L · Tires: KEEP                           │
│                                                          │
│  FUEL: 2.31 L/lap (plan: 2.28) · +0.5L over plan       │
│  GRIP: 82% (plan: 84%) · on track                       │
│  PACE: 1:32.1 avg (plan: 1:32.0) · on track            │
│                                                          │
│  ⚠ Fuel burn +1.3% vs plan — pit lap unchanged          │
└──────────────────────────────────────────────────────────┘
```

**Overlay during race:**
- **Pit countdown widget** (always visible in last 5 laps of stint): "PIT IN 3"
- **Strategy status line** (compact, top of screen): "P5 · L9/20 · Fuel 3.1L margin · Grip 82%"
- Sector deltas: "S1 -0.2 · S2 +0.3 · S3 flat"

**Post-race:**
- Strategy page shows **Plan vs Actual** comparison:
  - Planned pit lap vs actual pit lap
  - Planned fuel load vs actual
  - Predicted race time vs actual
  - "Strategy cost you 0 seconds" or "Pitting 2 laps early cost ~3.2s"

**What gets removed:**
- Static pre-race plan that doesn't update. The plan is now live
- Manual "re-optimize" button during race — recalculation is automatic

### C. Endurance workflow

**What the user sees first:**
Same as Sprint but ModeBanner suggests Endurance (triggered by timed race or race > 45 min). Strategy page opens to **Build tab** during practice, showing per-compound stint profiles with thermal/degradation model confidence.

**Pre-race → Race Plan tab:**
Multi-stint plan with compound rotation, fuel loads per stop, estimated grip at end of each stint. Weather timeline if available (placeholder for future adapter work).

**During race — what's different from Sprint:**
- **Stint health indicator** on overlay: "Stint lap 14/18 · Grip 71% · Target: pit at 18"
- **Fuel-save coaching** when fuel margin is tight: "SAVE 0.15 L/lap to reach pit window — lift and coast on main straight"
- **Stint extension/shortening advisory**: "At current wear rate, extend stint by 2 laps (grip still above 65% threshold)"
- Live recalculation factors in actual tire degradation curve, not just the pre-race model — if tires are holding up better than expected, the system recommends extending

**What the user decides:**
- Accept live pit recommendation or override
- Whether to fuel-save or push (system recommends, driver decides)

**Post-race:**
- Full stint-by-stint comparison: planned vs actual for each stop
- Fuel efficiency per stint
- "Best strategy decision: extending stint 2 by 2 laps saved 14s total"

**What gets removed:**
- Team/driver-swap assumptions (single-driver only for v2; team features deferred)

### D. Post-session review workflow

**What the user sees first:**
After finalize, app navigates to **Review page** for the session just completed. Three cards:

1. **Strategy review** (Sprint/Endurance only): Plan vs actual, strategy cost/gain
2. **Consistency report**: Best lap, median, std dev, worst corners, improvement trend
3. **Technique comparison**: Top 3 time-loss corners with brake/throttle traces vs best lap

**Cross-session comparison (NEW):**
History page gains a "Compare" action. User selects 2 sessions on the same track → side-by-side:
- Lap time distribution overlay
- Best-lap sector comparison
- Fuel consumption comparison
- Consistency trend (improving? plateauing?)

**What gets removed:**
- Event timeline (system lifecycle events) — moved to a debug drawer, hidden by default
- Sync debug section — moved to Settings
- Raw channel inspection in Data mode — kept but de-emphasized (accessible but not the default view)

---

## 3. Strategy System Redesign

### Before race

**Strategy page — Race Plan tab shows:**

| Element | Source | Manual or auto? |
|---|---|---|
| Track + car + race distance | From sim telemetry | Auto (editable) |
| Fuel capacity | From sim telemetry (first sample) | Auto |
| Fuel per lap | From `CompoundProfile.fuel_per_lap` | Auto (measured) |
| Tire degradation model | From `DegradationModel` fitted data | Auto (measured) |
| Pit stop time | From `PitProfile` or 25s fallback | Auto (measured if available) |
| Compound selection | From available `CompoundProfile` entries | Auto (editable) |
| Number of stops | From `optimize_strategy()` | Auto |
| Stint lengths + fuel loads | From `optimize_strategy()` | Auto (editable) |

**Confidence display:**
Each input shows a confidence badge:
- 🟢 **Measured** — "12 practice laps, fitted model"
- 🟡 **Estimated** — "3 laps, linear extrapolation"
- 🔴 **Fallback** — "No data, using default"

The overall plan confidence is the MINIMUM of its inputs. A plan with one red input shows: "Plan confidence: LOW — pit time is using 25s default. Run a practice pit stop to improve."

### During race — live recalculation

**When it fires:**
- **Every completed lap** during a race session
- Trigger: `update_live()` receives a new lap_number increment
- Calls `recalculate_live_plan()` with:
  - Current lap, current fuel level (from telemetry)
  - Actual fuel deltas (measured per-lap consumption this race)
  - Actual tire wear estimate (from grip proxy or stint lap count)
  - Same profiles + pit_profile as pre-race

**What exact states are tracked (per lap):**

| State | Formula | Display |
|---|---|---|
| Fuel burn rate (actual) | rolling 3-lap average of `fuel_delta` | "2.31 L/lap" |
| Fuel burn divergence | `(actual_avg - planned_avg) / planned_avg × 100` | "+1.3% vs plan" |
| Fuel margin | `current_fuel - (remaining_laps × actual_burn_rate)` | "3.1L margin" or "DEFICIT 0.8L" |
| Grip estimate | `1.0 - (stint_lap / max_viable_stint)` from DegradationModel | "82%" |
| Grip divergence | actual grip proxy vs planned grip at this lap | "on track" or "-4% vs plan" |
| Predicted pit lap | recalculated from actual burn + grip | "Lap 12" (updated live) |
| Pit lap shift | `new_pit_lap - original_pit_lap` | "unchanged" or "shifted +2" |
| Laps to pit | `pit_lap - current_lap` | "3 laps" |

**Exact alerts (fired when state crosses threshold):**

| Alert | Trigger | Severity | Overlay display |
|---|---|---|---|
| Pit countdown | laps_to_pit ≤ 5 | advisory | **"PIT IN 3"** (overlay widget, large, persistent) |
| Box this lap | laps_to_pit == 1 | critical | **"BOX BOX BOX"** (full-width banner, flashing) |
| Fuel margin tight | fuel_margin < 1.5L AND laps_remaining > 3 | advisory | **"FUEL TIGHT — save 0.1 L/lap"** |
| Fuel deficit | fuel_margin < 0 | critical | **"FUEL DEFICIT — box now or save 0.3 L/lap"** |
| Pit lap shifted | abs(pit_lap_shift) >= 2 | advisory | **"Pit lap shifted: 18 → 16 (higher fuel burn)"** |
| Stint extension possible | grip > threshold AND fuel > needed | advisory (endurance only) | **"Extend stint by 2 laps — grip and fuel sufficient"** |
| Strategy on track | all divergences < 3% | silent | Status line shows green "ON PLAN" |

**Pit call behavior:**
- At `laps_to_pit == 3`: advisory overlay "PIT IN 3" appears, strategy dashboard highlights the pit stop row
- At `laps_to_pit == 1`: critical overlay "BOX BOX BOX" appears with fuel load amount: "BOX — 38L — KEEP TIRES"
- At `laps_to_pit == 0 AND is_in_pits == false`: alert escalates: "MISSED PIT WINDOW — recalculating"
- If user pits: system detects `is_in_pits == true`, records actual pit lap, measures fuel added, transitions to next stint. Recalculates remaining plan from new position
- If user ignores: system recalculates assuming extended stint. Alert: "Staying out — next pit window: lap 21 (fuel critical at lap 23)"

### After race — plan vs actual

**Strategy Review card shows:**

| Metric | Planned | Actual | Delta |
|---|---|---|---|
| Pit lap | 12 | 12 | — |
| Fuel added | 38.0 L | 39.2 L | +1.2 L |
| Fuel at finish | 2.1 L | 0.8 L | -1.3 L |
| Race time | 31:42 | 31:38 | -4s ✓ |
| Average pace | 1:32.0 | 1:31.9 | -0.1s ✓ |

**Strategy lessons (auto-generated from delta analysis):**
- "Fuel burn was 1.3% higher than practice model. Consider fuel-save laps 8-10 in future."
- "Pit timing was optimal — actual pit lap matched plan."
- "Grip at end of stint 1 was 78% vs predicted 82%. Tire model may need more practice data."

These are NOT AI-generated — they're template sentences filled from the plan-vs-actual comparison. Each template maps to a divergence category (fuel, timing, grip, pace).

---

## 4. Overlay System Redesign

### A. Final overlay taxonomy — 3 buckets

**Core Race** (15 widgets) — the product. Always available, smart-defaulted per mode.
**Coaching** (4 widgets) — practice-specific, automatically enabled in Coaching mode.
**Optional Pack** (keep but hidden from default catalog) — streamer, social, debug, aspirational.

### B. Core widgets to keep

| Widget | Category | Refresh | Purpose |
|---|---|---|---|
| `delta_bar` | Timing | 60 Hz | Aggregate delta to best — primary timing reference |
| `sector_delta` | Timing | per sector | **NEW** — "S1: -0.2 · S2: +0.3 · S3: +0.1" |
| `lap_timing` | Timing | per lap | Last/best/current lap |
| `pit_countdown` | Strategy | per lap | **NEW** — "PIT IN 3" / "BOX BOX BOX" |
| `strategy_status` | Strategy | per lap | **NEW** — compact one-line: "P5 · L9/20 · Fuel OK · Grip 82%" |
| `fuel_state` | Strategy | 1 Hz | Current fuel, L/lap, laps remaining, margin |
| `tire_life` | Strategy | per lap | Grip %, stint lap count, visual degradation curve |
| `push_manage` | Strategy | per lap | **NEW** — "PUSH" / "MANAGE" / "SAVE" banner (endurance) |
| `radar` | Awareness | 60 Hz | Relative car positions around driver |
| `blind_spot` | Awareness | 60 Hz | Left/right traffic warning |
| `gap_timing` | Awareness | per sector | **NEW** — "+1.2s to P4 · -0.8s to P6" |
| `standings` | Awareness | per lap | Position in class, compact |
| `flags` | Awareness | real-time | Flag state (yellow, blue, black) |
| `track_map` | Awareness | 1 Hz | Miniature circuit with car positions |
| `session_timer` | Awareness | 1 Hz | Remaining time (endurance) |

### C. Widgets to hide or remove from main catalog

**Move to Optional Pack (hidden by default, accessible via Settings → Overlay → Show Optional):**
- `chat`, `chat_highlight`, `chat_race_game`, `chat_race_standing` (streamer)
- `promo_code_alert`, `mic_visualizer` (streamer)
- `custom_text`, `custom_url` (user-defined, risky content)
- `advanced_panel`, `data_blocks` (debug/data mode only)
- `laptime_graph`, `laptime_log`, `laptime_spread` (post-session analysis, not for in-car)
- `heart_rate`, `world_map`, `garage_cover`, `race_schedule` (no data source)
- `weather_monitor`, `weather` (no adapter populates live weather)
- `flat_map`, `mini_map` (redundant with `track_map`)
- `radar_bars` (redundant with `radar`)
- `leaderboard`, `standings_table`, `head_to_head` (text-heavy, dangerous while driving)
- `overtake_alert` (useful concept but not implemented with real gap data)
- `fuel_calculator` (redundant now that `fuel_state` + `strategy_status` cover it)
- `pitbox_helper` (static pit setup — replaced by live `pit_countdown` with fuel load)
- `race_strategy` (static plan display — replaced by `strategy_status`)
- `boost_box`, `digiflag` (niche, keep but hide)

**Remove entirely (dead code, no data, confuse product):**
- `gforce_meter_full` (duplicate of `gforce_meter`)

**Result: 54 widgets → 15 Core + 4 Coaching + ~25 Optional Pack + 1 removed = cleaner catalog**

### D. New widgets required (5)

| Widget | Size | Refresh | Behavior |
|---|---|---|---|
| `sector_delta` | 300×60 | per sector completion | Shows S1/S2/S3 deltas color-coded green/red. Resets each lap |
| `pit_countdown` | 240×80 | per lap | Shows "PIT IN N" for last 5 laps of stint. "BOX BOX BOX" on final lap. Includes fuel load amount. Invisible when not in pit window |
| `strategy_status` | 400×40 | per lap | Compact banner: position, lap, fuel state word (OK/TIGHT/SAVE/DEFICIT), grip %. Always visible in race modes. Color-coded: green = on plan, yellow = advisory, red = critical |
| `gap_timing` | 280×60 | per sector | "+1.2s to P4 ahead · -0.8s to P6 behind". Uses relative position data from the adapter. Falls back to "N/A" when data unavailable (non-iRacing sims) |
| `push_manage` | 200×60 | per lap | Single word: "PUSH" (green) / "MANAGE" (yellow) / "SAVE" (red). Driven by fuel margin + tire state + race position. Endurance mode only. Invisible in Sprint (Sprint is always push) |

### E. Per-mode default overlay sets

**Sprint:**
`delta_bar`, `sector_delta`, `pit_countdown`, `strategy_status`, `fuel_state`, `radar`, `blind_spot`, `gap_timing`, `standings`, `flags`

**Endurance:**
All of Sprint + `tire_life`, `push_manage`, `session_timer`

**Coaching:**
`delta_bar`, `sector_delta`, `coaching_card`, `technique_trace`, `inputs_grip`
(Coaching overlay is deliberately stripped — no standings, no radar, no strategy. Pure self-improvement.)

**Data:**
`delta_bar`, `inputs_grip`, `fuel_state`, `track_map`
(Minimal — Data mode is for post-session analysis; overlays are secondary.)

### F. Alert priority rules

| Priority | Behavior | Examples |
|---|---|---|
| **Critical** | Full-width banner, stays until dismissed or condition clears, audio tone if available | "BOX BOX BOX — 38L — KEEP TIRES", "FUEL DEFICIT", "BLACK FLAG" |
| **Advisory** | Compact toast, auto-dismiss after 5s unless condition persists | "PIT IN 3", "Fuel tight — save 0.1 L/lap", "Pit lap shifted: 18→16", "Stint extension: +2 laps possible" |
| **Silent** | Not shown during driving. Logged in session events. Visible in post-session review | "Strategy on plan", "Consistency improved 12% this stint", "Coaching plan succeeded — new focus: Sector 1" |

**Alert suppression rules:**
- In Coaching mode: suppress ALL strategy alerts. Only coaching feedback surfaces
- During first 2 laps of race: suppress advisory alerts (driver is in traffic, cognitive load is peak)
- Within 500m of pit entry: suppress non-critical alerts (driver is committed to a decision)

### G. Visibility rules

| Widget | Always | Conditional | Never while driving |
|---|---|---|---|
| `strategy_status` | Sprint/Endurance | — | Coaching/Data |
| `pit_countdown` | — | Last 5 laps of stint | Outside pit window |
| `push_manage` | — | Endurance only, when fuel/tire state warrants | Sprint (always push) |
| `sector_delta` | Sprint/Endurance/Coaching | — | — |
| `gap_timing` | Sprint/Endurance | Only when adapter provides gap data (iRacing/LMU) | Data |
| `radar` | Sprint/Endurance | — | Coaching (distraction) |
| `standings` | Sprint/Endurance | — | Coaching/Data |
| `technique_trace` | — | Coaching mode only, when reference lap exists | Race modes |

---

## 5. Coaching System Redesign

### A. What coaching should detect

Using existing telemetry at 10 Hz and distance-based self-comparison:

| Detection | Data source | Method |
|---|---|---|
| Braking point consistency | `brake_pct` transition 0→>0.1 at each corner | Distance-from-corner-entry where braking begins, compare to best lap ±N meters |
| Minimum corner speed | `speed_kph` local minimum per corner | Compare to best-lap minimum at same corner |
| Throttle application point | `throttle_pct` transition 0→>0.2 post-apex | Distance-from-apex where throttle opens, compare to best lap |
| Sector time loss concentration | Per-sector delta breakdown | Already computed in `LiveTelemetryProcessor` — promote to per-sector |
| Consistency trend | Rolling 5-lap std dev vs prior 5-lap window | Already in `consistency_analyzer.py` |
| Tire-induced degradation vs driver error | Std dev increase correlated with stint lap count | If std dev increases linearly with stint progression, it's mechanical; if random, it's driver |

**No new ML.** All comparisons are the driver's current lap vs their own best lap at the same track distance. The 10 Hz sample rate gives ~1m resolution at 100 km/h — sufficient for braking point detection.

### B. What coaching should say

Replace the 3 generic templates with **data-driven coaching sentences** built from the detection above:

**Current (generic):**
> "Focus area: Sector 2 — Stabilize braking point"

**Redesigned (specific, data-driven):**

> **"Turn 3: You're braking 14m later than your best lap. That costs 0.3s and destabilizes the entry. Try matching your best brake point — you'll feel slower but exit faster."**

> **"Turn 7: Your minimum speed is 8 km/h lower than your best. You're over-slowing the car. Trust the grip and carry 4-5 km/h more through the apex."**

> **"Sector 2: You lose 0.4s here every lap. The loss is concentrated at T5 exit — your throttle opens 0.8s later than your best lap. Focus on getting on power earlier."**

> **"Good consistency in Sector 1 (±0.12s). Sector 3 is your opportunity — 0.6s gap between your median and your best."**

**Template structure:**
```
[Corner/Sector]: [Observation from data]. [Quantified delta]. [One actionable instruction].
```

Every coaching output includes:
1. **WHERE** — corner number or sector
2. **WHAT** — the measured difference from their own best
3. **HOW MUCH** — quantified in meters, km/h, or seconds
4. **WHAT TO DO** — one concrete instruction

The instruction library is NOT free-text AI. It's a lookup table:
- Braking too late → "Try matching your best brake point"
- Braking too early → "You can brake 8m later — trust the grip"
- Min speed too low → "Carry N km/h more through the apex"
- Min speed too high → "Your corner speed is good — focus on exit instead"
- Throttle too late → "Get on power earlier — you have grip headroom"
- Throttle too early → "You're getting on throttle before the apex — patience"

~12 templates total, parameterized with corner number, delta value, and best-lap reference. Covers 90%+ of amateur driver errors.

### C. What supporting data should be shown

**On the coaching overlay (visible while driving):**
- `coaching_card` widget: the current coaching instruction (1 sentence, large text, updated per lap)
- `technique_trace` widget (**NEW**): mini brake/throttle trace for the current focus corner, overlaid with the best-lap trace. Visible on the straight BEFORE the focus corner, auto-hides during the corner itself

**On the Coaching tab (between laps / post-session):**
- Full corner-by-corner comparison table: each corner's brake point delta, min speed delta, throttle point delta vs best lap
- Sector delta breakdown (persistent, not just per-lap flash)
- Consistency trend chart: 5-lap rolling std dev over the session
- "Time on the table" number: sum of per-sector gaps between median and best = theoretical improvement if consistency matched best

### D. How technique guidance works

**System flow (per lap completion):**

```
1. Compute per-corner metrics for completed lap:
   - brake_point_distance (from telemetry distance channel + brake transition)
   - min_corner_speed (from speed local minimum at known corner zones)
   - throttle_application_distance (from throttle transition post-apex)

2. Compare to the driver's own best lap (stored per-session):
   - delta_brake_m = current_brake_dist - best_brake_dist
   - delta_min_speed_kph = current_min_speed - best_min_speed
   - delta_throttle_s = current_throttle_time - best_throttle_time

3. Rank all corners by time-loss contribution:
   - Use sector deltas to weight corner importance

4. Select the TOP 1 coaching focus:
   - Highest time-loss corner with a detectable technique delta
   - Ignore corners where delta is <0.05s (noise floor)

5. Generate coaching sentence from template + data:
   - Select template by detection type (brake/speed/throttle)
   - Parameterize with corner number + delta value

6. Display on coaching_card widget
```

**Corner detection:**
Corners are identified by curvature (steering angle threshold) OR by pre-defined corner maps per track. iRacing and LMU provide track-position data sufficient for automated corner detection. For ACC/AC, fall back to sector-level analysis (no per-corner).

**Tier 1 (iRacing): per-corner technique coaching**
**Tier 2 (LMU): per-corner where track data supports it, else per-sector**
**Tier 3 (ACC/AC): per-sector only**

### E. How readiness affects product behavior

Readiness is no longer just a display — it drives transitions:

| Readiness state | Product behavior |
|---|---|
| **NOT_READY** (< 5 laps, no models) | Strategy page shows "Build your data first" with live progress bars. Plan generation disabled. Coaching shows "Drive consistently for 5 laps to start coaching." |
| **BUILDING** (5-10 laps, partial models) | Strategy page shows plan with LOW confidence. Warning: "Plan is based on limited data — fuel model has 6 laps, needs 10 for confidence." Coaching active with sector-level feedback |
| **READY** (10+ laps, core models confident) | Strategy page shows plan with HIGH confidence. Banner: "Ready to race." Full coaching with corner-level technique. Post-session review unlocked |

The state names change from NOT_READY/ALMOST/READY to NOT_READY/BUILDING/READY. BUILDING replaces ALMOST because "almost" communicates nothing about what to do.

### F. Coaching information that survives mode switch

When user switches from Coaching → Sprint or Endurance:

**What carries over:**
- Best-lap reference (stored per-session, accessible by strategy VM)
- Per-corner technique deltas (latest values cached in the coaching state)
- Consistency report (std dev, trend, worst corners)
- "Time on the table" number

**How it surfaces in race mode:**
- The `sector_delta` overlay widget shows per-sector deltas during the race — this IS coaching, just in race context
- The `strategy_status` widget incorporates consistency: if std dev spikes during the race, an advisory appears: "Consistency dropping — focus on [focus corner from coaching]"
- Post-race review includes coaching comparison: "Your T3 technique improved during the race — brake point was 8m closer to your best by lap 15"

**What does NOT carry over:**
- The `coaching_card` overlay (not shown in race modes — too text-heavy under race pressure)
- The `technique_trace` widget (not shown in race — distraction risk)
- Plan generation/evaluation (coaching plans are practice-only)

---

## 6. Prioritized Implementation Plan

### Top 10 changes

| # | Change | Impact | Difficulty | Type | Dependencies |
|---|---|---|---|---|---|
| **1** | **Wire `recalculate_live_plan()` to fire every lap during race** | Critical — transforms strategy from planning tool to live system | Low — code exists, needs 20 lines of wiring in `strategy_vm.update_live()` | Logic wiring | None — `recalculate_live_plan` and all models already exist |
| **2** | **Build `pit_countdown` overlay widget** | Critical — the most-requested missing feature; makes strategy visible during driving | Medium — new QML widget + strategy VM property `lapsToPit` | UI + logic wiring | #1 (needs live pit lap) |
| **3** | **Build `strategy_status` overlay widget** | High — compact live strategy visibility; replaces the static `race_strategy` widget | Medium — new QML widget, reads existing VM properties | UI wiring | #1 |
| **4** | **Build `sector_delta` overlay widget** | High — immediate per-sector feedback during driving | Medium — `LiveTelemetryProcessor` already computes sector deltas; new widget to render them | UI wiring | Sector delta data already exists in processor |
| **5** | **Replace generic coaching templates with technique comparison** | High — transforms coaching from "stabilize sector 2" to "braking 14m late at T3" | Medium-High — new per-corner metric computation + template library; reuses existing telemetry | New code (corner detection + comparison) + template library | Corner zone detection needed for iRacing/LMU |
| **6** | **Build `gap_timing` overlay widget** | High — live gap to car ahead/behind; critical for race decisions | Medium — iRacing adapter already provides relative position/speed; needs time-gap derivation | Logic + UI | iRacing adapter relative data; LMU partial; ACC/AC unavailable |
| **7** | **Overlay catalog cleanup: hide 25+ widgets behind Optional Pack** | Medium — reduces cognitive load on overlay config page; sharpens product identity | Low — move widgets to a hidden category, add Settings toggle | UI reorganization | None |
| **8** | **Strategy plan-vs-actual post-race review** | Medium — closes the feedback loop; builds trust in strategy | Medium — compare recorded events to pre-race plan, generate delta table | Logic + UI | #1 (live plan produces trackable events) |
| **9** | **Readiness as product gate** (BUILDING state, progress bars, "Ready to race" banner) | Medium — gives practice purpose and a satisfying milestone | Low-Medium — refactor readiness states, add progress UI to Practice tab | UI + state wiring | Existing readiness logic, minor refactor |
| **10** | **Build `push_manage` overlay widget** (endurance only) | Medium — fuel-save coaching during endurance stints | Medium — decision logic combining fuel margin + grip + position | Logic + UI | #1 (needs live fuel tracking) |

### What to delay (v2.1 milestone)

- **Cross-session comparison** — high value but requires history query infrastructure that's not race-day critical
- **Setup correlation** — valuable but needs setup-file parsing that's sim-specific and fragile
- **Weather-reactive strategy** — no adapter currently populates weather changes; infrastructure is ready but data isn't
- **Competitor strategy prediction** — undercut/overcut timing requires multi-car telemetry that only iRacing partially provides
- **Team/multi-driver endurance support** — real demand but doubles the strategy complexity

### What to remove

- `gforce_meter_full` — duplicate, dead code. Delete

### What to hide behind Optional Pack

The 25 widgets listed in §4.C. Accessible via `Settings → Overlays → Show Optional Pack`. Not shown in the default overlay catalog. No feature gates — just hidden from the default view to stop diluting the product.

### What becomes v2.0 vs v2.1

**v2.0 (this spec):**
1. Live strategy recalculation (wiring)
2. Pit countdown overlay
3. Strategy status overlay
4. Sector delta overlay
5. Technique coaching (corner-level for iRacing)
6. Gap timing overlay (iRacing first)
7. Overlay cleanup (hide optional pack)
8. Plan-vs-actual review
9. Readiness gates
10. Push/manage indicator (endurance)

**v2.1 (follow-on):**
- Cross-session comparison
- Setup correlation
- Corner detection for LMU (extending technique coaching)
- Fuel-save target pace calculator
- Custom alert thresholds (user-configurable pit countdown timing, fuel warning level)
- Export improvements (MoTeC-compatible export)

**v3.0 (future):**
- Weather-reactive strategy
- Competitor strategy awareness
- Team endurance mode
- Webapp-powered analysis (leveraging the Connected v1 pipeline)
