# Widget degraded-state audit (T156)

**Sprint task:** T156 — Audit all 40+ widgets: each has degraded-state rendering (stale/missing data) ⇒ list complete.

**Source:** `src/lap_coach_logger/qml/Overlay/widgets/*.qml`

**Total widgets covered:** 51 (excludes `GlassSurface.qml`, which is a base mixin component, not a user-facing widget).

**Method:** Pattern grep for the conventions the existing widgets use to render absent/missing/invalid data, classified into four buckets:

| Marker pattern | What it means |
| --- | --- |
| `em-dash placeholder` | Explicit `text: "—"` fallback when data is absent (the strongest signal that a widget thought about empty state) |
| `NO DATA / "--" text` | Explicit text marker when the source value is unavailable |
| `stale marker` | The widget reads a `freshness`/`stale` property and adjusts rendering |
| `isFinite / isNaN / safeFix` | Numeric guard — catches NaN / Infinity from missing telemetry but doesn't necessarily render a labelled fallback |
| `visible data check` | Whole sub-elements hidden when underlying data is empty (e.g. `visible: list.length > 0`) |
| `NONE` | No degraded-state handling found — renders raw bound values, blanks/zeroes are visible to the user |

The buckets aren't mutually exclusive — some widgets combine multiple techniques. The follow-up tasks T157–T170 act on the widgets in the `NONE` row first (they currently leak missing-data state to the user) and harden the `isFinite-only` widgets second (numerically guarded but no user-facing "no data" label).

## Per-widget classification

| Widget | Markers found | Block I follow-up |
| --- | --- | --- |
| AdvancedPanelWidget | visible data check | none scheduled |
| BlindSpotWidget | **NONE** | T156 audit only — no T157+ entry |
| BoostBoxWidget | isFinite | hardening candidate |
| ChatHighlightWidget | **NONE** | T156 audit only |
| ChatRaceGameWidget | visible data check | none scheduled |
| ChatRaceStandingWidget | visible data check | none scheduled |
| ChatWidget | visible data check | none scheduled |
| CoachingWidget | visible data check | T160 — "insights not available" banner |
| CustomTextWidget | **NONE** | T156 audit only (intentional — user-supplied text) |
| CustomUrlWidget | **NONE** | T156 audit only (intentional — user-supplied URL) |
| DataBlocksWidget | NO DATA, visible data check | none scheduled |
| DeltaBarWidget | isFinite | T157 — gray "—" |
| DeltaTimeWidget | isNaN | T157 — gray "—" (lap-delta widget) |
| DigiflagWidget | visible data check | T165 — flags degraded |
| FlagsWidget | visible data check | T165 — flags degraded |
| FlatMapWidget | isFinite | none scheduled |
| FuelCalculatorWidget | isFinite, safeFix, NO DATA | T158 — gray fuel widget |
| FuelWidget | isNaN, visible data check | T158 — gray fuel widget |
| GForceMeterWidget | isFinite | T162 — g-g degraded |
| GapTimingWidget | em-dash placeholder, isNaN | T167 — gap degraded |
| GarageCoverWidget | visible data check | none scheduled |
| HeadToHeadWidget | **NONE** | hardening candidate |
| HeartRateWidget | NO DATA | none scheduled |
| InputTelemetryWidget | **NONE** | T161 — "sensor stale" |
| InputsWidget | **NONE** | T161 — "sensor stale" |
| LapTimingWidget | visible data check | T157 (related — lap timing) |
| LaptimeGraphWidget | NO DATA | T163 — live trace degraded |
| LaptimeLogWidget | visible data check | none scheduled |
| LaptimeSpreadWidget | isFinite, NO DATA | none scheduled |
| LeaderboardWidget | visible data check | none scheduled |
| MicVisualizerWidget | **NONE** | none scheduled |
| MiniMapWidget | isFinite | none scheduled |
| OvertakeAlertWidget | **NONE** | none scheduled |
| PitCountdownWidget | em-dash placeholder, visible data check | none scheduled |
| PitboxHelperWidget | isFinite, NO DATA | none scheduled |
| PromoCodeAlertWidget | **NONE** | none scheduled |
| PushManageWidget | visible data check | none scheduled |
| RaceReminderWidget | stale marker, visible data check | reference — already exemplary |
| RaceScheduleWidget | visible data check | none scheduled |
| RaceStrategyWidget | isFinite, safeFix, NO DATA, visible data check | reference — well-handled (carries T148/T151/T152 work) |
| RadarBarsWidget | **NONE** | none scheduled |
| RadarWidget | **NONE** | none scheduled |
| RelativesWidget | visible data check | none scheduled |
| SectorDeltaWidget | em-dash placeholder, isFinite | T164 — sector colors degraded |
| SessionTimerWidget | isNaN | T168 — stint timer degraded |
| StandingsWidget | visible data check | T166 — position degraded |
| StrategyStatusWidget | **NONE** | hardening candidate |
| TireLifeWidget | NO DATA | T169 — tire life degraded; T159 — tire degraded |
| TrackMapWidget | isFinite | none scheduled |
| WeatherMonitorWidget | isFinite, safeFix, NO DATA | reference — well-handled |
| WorldMapWidget | isNaN, NO DATA, visible data check | none scheduled |

## Summary counts

- **Explicit degraded text** (em-dash, NO DATA, or stale marker): **14 widgets**
- **Numeric guards only** (isFinite / isNaN / safeFix without a labelled fallback): **5 widgets**
- **Visible-only guards** (sub-elements hidden but numbers/labels not gracefully degraded): **18 widgets**
- **No degraded-state handling** (`NONE`): **13 widgets** — *BlindSpotWidget, ChatHighlightWidget, CustomTextWidget, CustomUrlWidget, HeadToHeadWidget, InputTelemetryWidget, InputsWidget, MicVisualizerWidget, OvertakeAlertWidget, PromoCodeAlertWidget, RadarBarsWidget, RadarWidget, StrategyStatusWidget*

(Some widgets appear in multiple categories — e.g. `RaceStrategyWidget` has all four marker types.)

## Reference exemplars

When implementing T157–T170, model the affected widget after one of these:

- **`RaceStrategyWidget.qml`** — `safeFix` helper for finite checks, `"—"` placeholder, conditional rendering of sub-sections (`hasPit`), and the recently-added T148/T151/T152 prompt pills with truthy-string visibility gates.
- **`WeatherMonitorWidget.qml`** — `isFinite` numeric guards combined with `"NO DATA"` text fallback when track/air temps are absent.
- **`RaceReminderWidget.qml`** — explicit `freshness` enum (`"fresh"` / `"stale"`) drives a visual treatment; the only widget in the codebase with explicit stale handling.

## Block I follow-ups derived from this audit

T157–T170 each name one or more widgets. Mapping the audit to those tasks:

| Task | Widget(s) | Current bucket |
| --- | --- | --- |
| T157 lap-delta | DeltaTimeWidget, DeltaBarWidget, LapTimingWidget | numeric/visible only |
| T158 fuel | FuelWidget, FuelCalculatorWidget | mixed (already partial) |
| T159 tire | TireLifeWidget | NO DATA only |
| T160 coaching card | CoachingWidget | visible-only |
| T161 input | InputsWidget, InputTelemetryWidget | **NONE** |
| T162 g-g | GForceMeterWidget | numeric only |
| T163 live trace | LaptimeGraphWidget | NO DATA only |
| T164 sector colors | SectorDeltaWidget | partial (em-dash) |
| T165 flags | FlagsWidget, DigiflagWidget | visible-only |
| T166 position | StandingsWidget | visible-only |
| T167 gap | GapTimingWidget | partial (em-dash) |
| T168 stint timer | SessionTimerWidget | numeric only |
| T169 tire life | TireLifeWidget | NO DATA only |
| T170 long-run pace | LaptimeSpreadWidget, LaptimeGraphWidget | partial |

T161 (input widgets) is the largest gap — both `InputsWidget` and `InputTelemetryWidget` currently render raw 0s when telemetry stalls, with no "sensor stale" indication. The other follow-ups are hardening the existing partial coverage rather than starting from scratch.
