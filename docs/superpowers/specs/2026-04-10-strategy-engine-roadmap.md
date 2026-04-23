# Race Strategy Engine — Full Roadmap

## Overview

Roadmap to bring the race strategy engine to ATLAS-level capability,
decomposed into three independent sub-projects in priority order.

## Sub-Project A: Realistic Pit + Tire + Endurance Model (Priority 1)

Foundation accuracy improvements. Everything else depends on these.

### A1. Variable Pit Time Model
- Decompose pit time: pit lane transit + tire change + fuel fill time
- Fuel fill time proportional to liters added (~0.5-1.0s/L, sim-dependent)
- Tire change adds fixed delta (~2-3s) vs. fuel-only stop
- Each planned stop costed individually by the optimizer
- Measure components from actual pit stop telemetry (is_in_pits timing + fuel delta during stop)

### A2. Endurance / Time-Based Races
- Race length in hours → estimated total laps = race_time / avg_lap_time
- Recalculate estimated laps as average pace changes
- Support driver swap time (configurable per series)
- Strategy page: toggle between "lap race" and "timed race" modes
- For timed races: show estimated laps remaining, not fixed lap count

### A3. Temperature-Driven Tire Performance Model
- Replace flat 2%/lap heuristic with temperature-dependent grip curve
- Cold tire penalty: map tire temp → lap time delta from logged stint data
  - First 1-3 laps after pit: tires below optimal → grip loss → slower pace
  - Derive the curve from per-lap times + per-lap tire temps in logged stints
- Overheating penalty: temps above optimal → accelerated degradation
- Optimal temperature window per compound (from aggregated stint data)
- Wrong compound penalty: softs in wet, wets on dry → massive time loss
  - Cross-reference compound vs. track_state from weather model
  - Apply multiplier to lap time when compound doesn't match conditions

## Sub-Project B: Race Simulation + Traffic (Priority 2)

Transforms the engine from a pit calculator into a stochastic strategy simulator.

### B1. Track Position / Undercut-Overcut Model
- Use position + gap_to_car_ahead from telemetry
- Model pit stop position change: "pit now → emerge behind car X" vs.
  "wait 3 laps → overcut car X"
- Factor track-specific overtaking difficulty (some tracks = easy pass,
  others = stuck behind for laps)
- Undercut value: fresh tires give N seconds of pace advantage × M laps
  before the rival pits

### B2. Safety Car Probability
- Historical SC probability per track per race distance
- For sim racing: configurable SC probability (user sets based on series/lobby)
- Impact on strategy: short-fill stops become cheaper if SC likely
  (SC bunches field, negates time loss)
- "Opportunistic pit" alert: if SC happens, recommend pitting immediately

### B3. Monte Carlo Race Simulation
- Run N simulated races (1000+) with stochastic variables:
  - Safety car timing (random, weighted by probability)
  - Tire degradation variance (±10% from profile)
  - Fuel consumption variance (±5%)
  - Weather change timing (if forecast uncertain)
- Score each strategy by: median finish position, worst-case position,
  probability of making target (e.g., "75% chance of finishing on podium")
- Present results: "Strategy A wins in 62% of simulations, Strategy B
  wins in 38% — A is more robust"

## Sub-Project C: Intelligence Layer (Priority 3)

Refinements that add the last 5% of accuracy.

### C1. Competitor Strategy Prediction
- Track other cars' tire age and fuel load from session info
- Predict rival pit windows based on their consumption rate
- Alert: "Car ahead likely pitting in 2-3 laps — consider undercut"
- iRacing: use session info for competitor data
- ACC: use broadcast data for competitor info

### C2. Track Evolution Model
- Track grip improves as rubber builds up over a session
- Model lap time improvement over time (from practice → qualifying → race)
- Affects compound choice: "early laps on hards when track is green,
  switch to softs when track is rubbered and grip peaks"
- Derive from historical session data at the same track

### C3. Driver Fatigue / Consistency Model
- Compute lap time standard deviation from logged stints
- Model consistency degradation over long stints (fatigue)
- Factor into strategy: "shorter stints = more consistent laps"
- For endurance: model driver swap timing based on fatigue curve

### C4. Setup-Strategy Link
- Connect setup_coach.py analysis to strategy impact
- "This setup change gives +0.2s/lap but increases tire wear by 15%"
- Feed setup sensitivity into the optimizer: optimal setup for the
  chosen strategy, not just fastest single-lap pace

## Implementation Order

1. **Sub-Project A** — spec + implement first (current focus)
2. **Sub-Project B** — after A is stable and tested with real sessions
3. **Sub-Project C** — iterative additions as data accumulates

## Dependencies

- A is independent (builds on existing stint store + strategy engine)
- B depends on A (needs accurate tire/fuel/pit models for simulation)
- C depends on A + B (needs simulation framework for competitor modeling)
