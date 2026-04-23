# Market Research Findings — Sim Racing Community Signal

## Source

Reddit (r/simracing, r/iRacing, r/ACCompetizione, r/LeMansUltimate),
RaceDepartment forums, OverTake community polls, tool-specific communities.

## Key Findings

### 1. Fragmented stack is the #1 complaint

Users run 3-4 separate tools: overlay (iOverlay/RaceLab/Kapps/SimHub),
telemetry (Garage61/VRS), spotter (Crew Chief), plus manual spreadsheets
for strategy. Multiple subscriptions, stitching tools together.

### 2. Consistency > max pace for race readiness

Competitive drivers spend 2-3 hours practicing per combo. They compare
telemetry against drivers 1-2s faster (not aliens). The key readiness
metric is repeatability, not personal best.

### 3. Fuel, pit timing, stint management = top race-day pain

iRacing's AutoFuel is used but debated — its fill is based on leader
pace and recent average, which can drift. Crew Chief's deterministic
pit/fuel commands are heavily used because drivers want control + guidance.

### 4. Minimal HUD wins

OverTake's Feb 2026 poll: limited HUD was top preference, full HUD
least popular. Must-haves: relative gaps, radar, standings, track map,
fuel. Everything else is noise during a race.

### 5. Two coaching camps

Camp A: Manual comparison tools (Garage61/VRS). Want to read their own data.
Camp B: Prescriptive help (Trophi-style). Want fast answers without reading traces.
Both exist. The tool needs to serve both.

### 6. Self-vs-self consistency analyzer = clear gap

Existing tools are biased toward "you vs faster driver." Multiple users
explicitly want: "Where am I not repeating?" — consistency analysis.

### 7. Second screen / pitwall demand is real

LMU Engineer Mode (Dec 2025 v1.2) validated remote pit-stop control.
Users want minimal in-car clutter + rich info on second screen/webapp.

### 8. Trust in strategy tools is fragile

Even AutoFuel gets debated. The lesson: make the math deterministic
first, let AI explain/summarize around it. Never let AI be the source
of truth for fuel math.

### 9. Performance matters

Users switch overlay tools because of FPS cost. Some stop using heavier
coaching tools during races. Desktop must be lightweight.

## Recommended Mode Priority

1. **Sprint Race** — broadest daily use, lowest cognitive load
2. **Endurance** — pit wall + team ops, validated by LMU engineer mode
3. **Coaching** — shorten practice time, self-vs-self consistency
4. **Just Data** — raw traces, exports, trust-building for advanced users
5. **Hotlap/Time Trial** — fold into Coaching as a preset, not standalone

## Recommended Product Split

**Desktop = acquisition + live overlay + deterministic race ops + low latency**
**Webapp = history + coaching review + collaboration + shared strategy + remote engineer**

## Features to Add (Missing from Current Design)

1. Self-vs-self consistency analyzer
2. Second-screen / pitwall workspace
3. Deterministic strategy engine + explainable layer (not AI-first)
4. Lightweight local runtime with background sync to webapp

## Features to Delay (v2+)

- Competitor strategy prediction
- Safety car probability
- Fully automatic mid-race strategy changes
- Deep setup-strategy linkage as a hero feature

## UX Principles

- Auto-detect suggested mode, always let user override
- Default to minimal overlay
- Deep analysis on second screen or webapp
- Prescriptive coaching BEFORE the race, informational prompts DURING
- Deterministic math first, AI explains around it
