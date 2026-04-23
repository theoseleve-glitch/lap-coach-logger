# QML Frontend Rewrite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the entire PySide6 QWidgets UI layer with a QML declarative frontend, producing an Apple-quality desktop experience with GPU-accelerated animations, unified navigation, and progressive disclosure — while leaving the Python backend 100% untouched.

**Architecture:** Three-layer separation: QML frontend (declarative, GPU-accelerated) ↔ ViewModel bridge (Python QObject subclasses with `@Property`/`@Signal`/`@Slot`) ↔ existing Python backend (adapters, coordinator, writers, config). ViewModels wrap `DesktopService` and expose reactive properties that QML binds to automatically.

**Tech Stack:** PySide6 >= 6.7 (QML/Qt Quick), Python 3.12+, QQmlApplicationEngine, PyInstaller, Inno Setup

**Spec:** `docs/superpowers/specs/2026-04-06-apple-quality-qml-rewrite-design.md`

---

## File Map

### New Files — ViewModels (`src/lap_coach_logger/viewmodels/`)

| File | Responsibility |
|------|---------------|
| `__init__.py` | Package exports |
| `service_vm.py` | Wraps `DesktopService`, exposes snapshot/status as QML properties |
| `session_vm.py` | Live session state: lap times, telemetry, current lap |
| `history_vm.py` | Session history list model for QML ListView |
| `review_vm.py` | Single session review data + section navigation |
| `settings_vm.py` | Config read/write, settings sections, sim toggles |
| `overlay_vm.py` | Overlay HUD state: times, sectors, inputs |
| `onboarding_vm.py` | First-run state tracking, sim selection |
| `tray_vm.py` | System tray icon and menu |

### New Files — QML (`src/lap_coach_logger/qml/`)

| File | Responsibility |
|------|---------------|
| `main.qml` | ApplicationWindow entry point |
| `AppShell.qml` | NavBar + StackView + status pill + settings slide-over |
| `Theme/Tokens.qml` | Singleton — colors, spacing, radii, border styles |
| `Theme/Typography.qml` | Singleton — font families, sizes, weights |
| `Theme/Motion.qml` | Singleton — easing curves, durations |
| `Theme/qmldir` | Module declaration for Theme imports |
| `Components/NavBar.qml` | Top navigation bar with brand, tabs, status pill, gear |
| `Components/StatusPill.qml` | Animated status indicator with color morph |
| `Components/MetricCard.qml` | Reusable data card with label + mono value |
| `Components/SessionCard.qml` | History list row: sim badge, track, best lap, grade |
| `Components/SectionTabs.qml` | Chip tab bar for Review page sections |
| `Components/SlideOver.qml` | Animated right-edge panel with dim overlay |
| `Components/ToggleSwitch.qml` | iOS-style animated toggle |
| `Components/SearchBar.qml` | Search input with icon |
| `Components/Sparkline.qml` | Canvas-based real-time sparkline |
| `Components/SectorBars.qml` | Three colored progress bars |
| `Components/ThrottleBrakeBar.qml` | Dual horizontal progress bars |
| `Components/LapTimeChart.qml` | Vertical bar chart for lap progression |
| `Components/ConfirmDialog.qml` | Scale+fade modal with yes/no |
| `Components/qmldir` | Module declaration |
| `Pages/DashboardPage.qml` | Hero card + metrics + quick actions |
| `Pages/LivePage.qml` | Real-time session view |
| `Pages/HistoryPage.qml` | Session library with search + filter |
| `Pages/ReviewPage.qml` | Session deep-dive with section tabs |
| `Pages/qmldir` | Module declaration |
| `Panels/SettingsPanel.qml` | Slide-over settings form |
| `Panels/DiagnosticsPanel.qml` | Logs + health + export |
| `Panels/AboutPanel.qml` | Product info |
| `Overlay/OverlayWindow.qml` | Frameless QML window |
| `Overlay/OverlayContent.qml` | HUD data layout |
| `Onboarding/OnboardingFlow.qml` | 3-step first-run |

### New Files — Bootstrap

| File | Responsibility |
|------|---------------|
| `src/lap_coach_logger/qml_bootstrap.py` | `run_qml_shell()` replaces `run_desktop_shell()` |

### Modified Files

| File | Change |
|------|--------|
| `src/lap_coach_logger/bootstrap.py` | Call `run_qml_shell()` instead of `run_desktop_shell()` |
| `src/lap_coach_logger/assets.py` | Add `qml_dir()` resolver for bundled QML |
| `lap_coach_logger.spec` | Add QML files to PyInstaller `datas` |

### Test Files

| File | What it tests |
|------|--------------|
| `tests/test_service_vm.py` | ServiceViewModel property bindings |
| `tests/test_session_vm.py` | SessionViewModel lap/telemetry data |
| `tests/test_history_vm.py` | HistoryViewModel list model |
| `tests/test_review_vm.py` | ReviewViewModel data exposure |
| `tests/test_settings_vm.py` | SettingsViewModel read/write roundtrip |
| `tests/test_overlay_vm.py` | OverlayViewModel state |
| `tests/test_onboarding_vm.py` | OnboardingViewModel flow |
| `tests/test_qml_bootstrap.py` | QML engine initialization |
| `tests/test_qml_integration.py` | Full wiring smoke test |
| `tests/test_bootstrap_qml.py` | Bootstrap calls QML shell |

---

## Task 1: Theme Singleton — Design Tokens in QML

**Files:**
- Create: `src/lap_coach_logger/qml/Theme/Tokens.qml`
- Create: `src/lap_coach_logger/qml/Theme/Typography.qml`
- Create: `src/lap_coach_logger/qml/Theme/Motion.qml`
- Create: `src/lap_coach_logger/qml/Theme/qmldir`

- [ ] **Step 1: Create Theme directory and qmldir module file**

Write `src/lap_coach_logger/qml/Theme/qmldir`:
```
module Theme
singleton Tokens 1.0 Tokens.qml
singleton Typography 1.0 Typography.qml
singleton Motion 1.0 Motion.qml
```

- [ ] **Step 2: Write Tokens.qml — colors, spacing, radii, borders**

```qml
pragma Singleton
import QtQuick

QtObject {
    readonly property color void_: "#050607"
    readonly property color surface: "#0A0B0E"
    readonly property color elevated: "#141519"
    readonly property color raised: "#1E1F25"
    readonly property color chalk: "#F0EDE5"
    readonly property color steel: "#949494"
    readonly property color pitOrange: "#C9A84C"
    readonly property color acidGreen: "#22C55E"
    readonly property color safetyRed: "#FF2A2A"
    readonly property color marshalYellow: "#FACC15"
    readonly property color racingPurple: "#8B5CF6"
    readonly property int xs: 4
    readonly property int sm: 8
    readonly property int md: 12
    readonly property int lg: 16
    readonly property int xl: 24
    readonly property int xxl: 32
    readonly property int xxxl: 48
    readonly property int xxxxl: 64
    readonly property int radiusSm: 6
    readonly property int radiusMd: 10
    readonly property int radiusLg: 14
    readonly property int radiusXl: 20
    function subtle(c, a) { return Qt.rgba(c.r, c.g, c.b, a === undefined ? 0.06 : a) }
    function medium(c, a) { return Qt.rgba(c.r, c.g, c.b, a === undefined ? 0.10 : a) }
}
```

- [ ] **Step 3: Write Typography.qml**

```qml
pragma Singleton
import QtQuick

QtObject {
    readonly property string displayFamily: "Segoe UI"
    readonly property string bodyFamily: "Segoe UI"
    readonly property string monoFamily: "Consolas"
    readonly property int displaySize: 32
    readonly property int displayWeight: Font.Bold
    readonly property int titleSize: 22
    readonly property int titleWeight: Font.Bold
    readonly property int headingSize: 17
    readonly property int headingWeight: Font.DemiBold
    readonly property int bodySize: 14
    readonly property int bodyWeight: Font.Normal
    readonly property int captionSize: 12
    readonly property int captionWeight: Font.Normal
    readonly property int dataSize: 28
    readonly property int dataWeight: Font.Bold
    readonly property int microSize: 10
    readonly property int microWeight: Font.Bold
    readonly property real microSpacing: 1.5
}
```

- [ ] **Step 4: Write Motion.qml**

```qml
pragma Singleton
import QtQuick

QtObject {
    readonly property int pageOutDuration: 200
    readonly property int pageInDuration: 250
    readonly property int pageSlideOffset: 30
    readonly property int pageOverlap: 40
    readonly property int pageCurve: Easing.OutCubic
    readonly property int pushDuration: 300
    readonly property int pushCurve: Easing.OutQuint
    readonly property int popCurve: Easing.InQuad
    readonly property int hoverDuration: 120
    readonly property int pressDuration: 80
    readonly property real hoverScale: 1.02
    readonly property real pressScale: 0.98
    readonly property int focusDuration: 150
    readonly property int statusColorDuration: 400
    readonly property int recordingPulseDuration: 1500
    readonly property int metricCountUpDuration: 300
    readonly property int slideOverOpenDuration: 300
    readonly property int slideOverCloseDuration: 200
    readonly property int dimDuration: 250
    readonly property real dimOpacity: 0.4
    readonly property int dialogDuration: 200
    readonly property real dialogStartScale: 0.95
}
```

- [ ] **Step 5: Commit**

Message: `feat(qml): add Theme singleton — design tokens, typography, motion`

---

## Task 2: ServiceViewModel — Bridge to Backend

Full code provided in the plan body above. See the spec for the `DesktopService` signals interface: `snapshot_changed(dict)`, `history_changed(list)`, `review_changed(dict)`, `settings_saved(str)`, `settings_failed(str)`, `action_message(str)`, `action_failed(str)`.

**Files:**
- Create: `src/lap_coach_logger/viewmodels/__init__.py`
- Create: `src/lap_coach_logger/viewmodels/service_vm.py`
- Create: `tests/test_service_vm.py`

Key properties exposed to QML: `status: str`, `statusDetail: str`, `isMonitoring: bool`, `sim: str`, `elapsedSeconds: int`, `elapsedFormatted: str`, `greeting: str`.

Key slots: `resumeMonitoring()`, `pauseMonitoring()`, `openOutputFolder()`, `openLogsFolder()`, `openConfigFolder()`.

The `_on_snapshot(snap: dict)` handler reads keys: `status`, `status_detail`, `is_monitoring`, `sim`, `elapsed_s`, `sample_count`, `sample_rate_hz_est`.

- [ ] **Step 1:** Write failing test (test default properties and `_on_snapshot` behavior)
- [ ] **Step 2:** Run test, verify FAIL
- [ ] **Step 3:** Write `viewmodels/__init__.py` and `service_vm.py`
- [ ] **Step 4:** Run test, verify PASS
- [ ] **Step 5:** Commit — `feat(vm): add ServiceViewModel — root QML bridge`

---

## Task 3: SessionViewModel — Live Telemetry State

**Files:**
- Create: `src/lap_coach_logger/viewmodels/session_vm.py`
- Create: `tests/test_session_vm.py`

Key properties: `track`, `car`, `sim`, `currentLap`, `lastLapTime`, `bestLapTime`, `bestLapNumber`, `lastLapDelta`, `consistencyPct`, `consistencySigma`, `speedKph`, `throttlePct`, `brakePct`, `laps: list`, `speedHistory: list`.

The `update_from_snapshot(snap)` method reads: `sim`, `track`, `car`, `current_lap`, `sample_rate_hz_est`, `live.speed_kph`, `live.throttle_pct`, `live.brake_pct`, `lap_times` (list of `{lap, time_s, sectors, status}`).

Lap time formatting: `_format_time(seconds)` returns `M:SS.mmm`. Delta formatting: `_format_delta(seconds)` returns `+X.XXX` or `BEST`.

Consistency: `(1 - stdev/mean) * 100` for 2+ valid laps.

- [ ] **Step 1:** Write failing test
- [ ] **Step 2:** Run test, verify FAIL
- [ ] **Step 3:** Write `session_vm.py`
- [ ] **Step 4:** Run test, verify PASS
- [ ] **Step 5:** Commit — `feat(vm): add SessionViewModel — live telemetry for QML`

---

## Task 4: HistoryViewModel — Session List Model

**Files:**
- Create: `src/lap_coach_logger/viewmodels/history_vm.py`
- Create: `tests/test_history_vm.py`

Key properties: `sessions: list` (filtered), `count: int`, `searchText: str`, `simFilter: str`.

Key slots: `setSearchText(str)`, `setSimFilter(str)`, `folderAt(int) -> str`, `sessionIdAt(int) -> str`.

`update_sessions(list)` called by ServiceVM. `_apply_filters()` filters by search text (track, sim, car) and sim name.

- [ ] **Step 1:** Write failing tests (populate, search filter, sim filter)
- [ ] **Step 2:** Run test, verify FAIL
- [ ] **Step 3:** Write `history_vm.py`
- [ ] **Step 4:** Run test, verify PASS
- [ ] **Step 5:** Commit — `feat(vm): add HistoryViewModel — filterable session list`

---

## Task 5: SettingsViewModel — Config Read/Write

**Files:**
- Create: `src/lap_coach_logger/viewmodels/settings_vm.py`
- Create: `tests/test_settings_vm.py`

Key properties: `isFirstRun: bool`, `values: dict`.

Key slots: `getString(key) -> str`, `getFloat(key) -> float`, `getBool(key) -> bool`, `setValue(key, value)`, `save()`.

`load(values: dict)` populates from `DesktopService.settings_snapshot()`. `save()` emits `saveRequested(dict)` which the bootstrap wires to `DesktopService.save_settings()`.

- [ ] **Step 1:** Write failing tests
- [ ] **Step 2:** Run test, verify FAIL
- [ ] **Step 3:** Write `settings_vm.py`
- [ ] **Step 4:** Run test, verify PASS
- [ ] **Step 5:** Commit — `feat(vm): add SettingsViewModel — config read/write`

---

## Task 6: ReviewViewModel + OverlayViewModel + OnboardingViewModel

**Files:**
- Create: `src/lap_coach_logger/viewmodels/review_vm.py`
- Create: `src/lap_coach_logger/viewmodels/overlay_vm.py`
- Create: `src/lap_coach_logger/viewmodels/onboarding_vm.py`
- Create: `tests/test_review_vm.py`
- Create: `tests/test_overlay_vm.py`
- Create: `tests/test_onboarding_vm.py`

**ReviewViewModel:** Properties: `data: dict`, `section: str`, `path: str`. Slots: `setSection(str)`, `clear()`. `load(review: dict)` populates from service.

**OverlayViewModel:** Properties: `speedKph`, `throttlePct`, `brakePct`, `lastTime`, `bestTime`, `lastDelta`, `sectorStates: list`, `lapNumber`, `track`, `isRecording`, `elapsed`. `update_from_snapshot(snap)` reads `live.*` and `status`.

**OnboardingViewModel:** Properties: `step: int`, `totalSteps: int`, `sims: dict`, `completed: bool`. Slots: `nextStep()`, `prevStep()`, `toggleSim(str)`, `finish()`.

Also update `viewmodels/__init__.py` with all 7 exports.

- [ ] **Step 1:** Write failing tests for all three
- [ ] **Step 2:** Run tests, verify FAIL
- [ ] **Step 3:** Write all three ViewModels
- [ ] **Step 4:** Update `__init__.py` exports
- [ ] **Step 5:** Run tests, verify PASS
- [ ] **Step 6:** Commit — `feat(vm): add Review, Overlay, Onboarding ViewModels`

---

## Task 7: QML Bootstrap — Engine Setup

**Files:**
- Create: `src/lap_coach_logger/qml_bootstrap.py`
- Modify: `src/lap_coach_logger/assets.py` (add `qml_dir()`)
- Create: `tests/test_qml_bootstrap.py`

`qml_dir()` in assets.py: returns `bundle_resource_path("src/lap_coach_logger/qml")` if exists, else `Path(__file__).parent / "qml"`.

`build_view_models(service)` instantiates all 7 ViewModels, wires service signals to child VMs, loads initial settings, returns dict.

`run_qml_shell(config, config_manager, coordinator, watcher, on_exit)`: creates QGuiApplication, DesktopService, ViewModels, QQmlApplicationEngine, registers context properties as `{name}VM`, loads `main.qml`, runs event loop.

- [ ] **Step 1:** Write failing test for `build_view_models`
- [ ] **Step 2:** Run test, verify FAIL
- [ ] **Step 3:** Add `qml_dir()` to `assets.py`
- [ ] **Step 4:** Write `qml_bootstrap.py`
- [ ] **Step 5:** Run test, verify PASS
- [ ] **Step 6:** Commit — `feat: add QML bootstrap — engine setup, ViewModel registration`

---

## Task 8: QML Core Components

**Files:** Create all files in `src/lap_coach_logger/qml/Components/`

NavBar, StatusPill, MetricCard, ToggleSwitch, SlideOver, ConfirmDialog. All use `import "../Theme" as Theme` for token access. Full requirements in the spec mockups. Each component is self-contained QML.

- [ ] **Step 1:** Create `Components/qmldir` with all module entries
- [ ] **Step 2:** Write NavBar.qml (brand + tabs + StatusPill + gear)
- [ ] **Step 3:** Write StatusPill.qml (color morph + pulse animation)
- [ ] **Step 4:** Write MetricCard.qml (label + mono value + subtitle)
- [ ] **Step 5:** Write ToggleSwitch.qml (iOS-style 44x24 toggle)
- [ ] **Step 6:** Write SlideOver.qml (right-edge panel + dim)
- [ ] **Step 7:** Write ConfirmDialog.qml (scale + fade modal)
- [ ] **Step 8:** Commit — `feat(qml): add core Components`

---

## Task 9: QML Data Components

**Files:** Create remaining files in `src/lap_coach_logger/qml/Components/`

SessionCard, SectionTabs, SearchBar, Sparkline, SectorBars, ThrottleBrakeBar, LapTimeChart. Requirements in spec mockups.

- [ ] **Step 1:** Write SessionCard.qml
- [ ] **Step 2:** Write SectionTabs.qml
- [ ] **Step 3:** Write SearchBar.qml
- [ ] **Step 4:** Write Sparkline.qml (Canvas-based)
- [ ] **Step 5:** Write SectorBars.qml
- [ ] **Step 6:** Write ThrottleBrakeBar.qml
- [ ] **Step 7:** Write LapTimeChart.qml
- [ ] **Step 8:** Commit — `feat(qml): add data Components`

---

## Task 10: QML Pages

**Files:** Create `src/lap_coach_logger/qml/Pages/` with qmldir and all 4 pages.

DashboardPage binds to `serviceVM` + `sessionVM`. LivePage binds to `sessionVM`. HistoryPage binds to `historyVM`. ReviewPage binds to `reviewVM`. Full layout requirements in spec mockups.

- [ ] **Step 1:** Create Pages/qmldir
- [ ] **Step 2:** Write DashboardPage.qml
- [ ] **Step 3:** Write LivePage.qml
- [ ] **Step 4:** Write HistoryPage.qml
- [ ] **Step 5:** Write ReviewPage.qml
- [ ] **Step 6:** Commit — `feat(qml): add Pages`

---

## Task 11: QML AppShell

**Files:** Create `src/lap_coach_logger/qml/main.qml` and `AppShell.qml`.

main.qml: ApplicationWindow with AppShell filling it. AppShell: NavBar + StackView with animated transitions (crossfade+slide for tabs, push/pop for Review). SlideOver for Settings. Close-to-tray handling.

- [ ] **Step 1:** Write main.qml
- [ ] **Step 2:** Write AppShell.qml
- [ ] **Step 3:** Commit — `feat(qml): add AppShell — main window, nav, transitions`

---

## Task 12: QML Panels + Onboarding

**Files:** Create Settings, Diagnostics, About panels and OnboardingFlow.

SettingsPanel renders inside SlideOver, binds to `settingsVM`. DiagnosticsPanel shows logs and health. AboutPanel shows product info. OnboardingFlow: 3-step modal, binds to `onboardingVM`.

- [ ] **Step 1:** Write SettingsPanel.qml
- [ ] **Step 2:** Write DiagnosticsPanel.qml
- [ ] **Step 3:** Write AboutPanel.qml
- [ ] **Step 4:** Write OnboardingFlow.qml
- [ ] **Step 5:** Commit — `feat(qml): add Panels and Onboarding`

---

## Task 13: QML Overlay HUD

**Files:** Create `src/lap_coach_logger/qml/Overlay/` with OverlayWindow.qml and OverlayContent.qml.

OverlayWindow: separate Window with frameless + stay-on-top flags, transparent background, draggable. OverlayContent: compact HUD layout binding to `overlayVM`.

- [ ] **Step 1:** Write OverlayWindow.qml
- [ ] **Step 2:** Write OverlayContent.qml
- [ ] **Step 3:** Commit — `feat(qml): add Overlay HUD`

---

## Task 14: Wire Bootstrap

**Files:** Modify `src/lap_coach_logger/bootstrap.py`.

Change import from `run_desktop_shell` to `run_qml_shell`. Change function call. Run backend tests to verify nothing breaks.

- [ ] **Step 1:** Write test verifying import changed
- [ ] **Step 2:** Modify bootstrap.py
- [ ] **Step 3:** Run backend tests
- [ ] **Step 4:** Commit — `feat: switch bootstrap to QML shell`

---

## Task 15: PyInstaller Bundling

**Files:** Modify `lap_coach_logger.spec`.

Add QML files to datas: `('src/lap_coach_logger/qml', 'lap_coach_logger/qml')`. Add hidden imports: `PySide6.QtQuick`, `PySide6.QtQml`.

- [ ] **Step 1:** Read current spec
- [ ] **Step 2:** Add QML datas and hidden imports
- [ ] **Step 3:** Test build compiles
- [ ] **Step 4:** Commit — `build: add QML to PyInstaller spec`

---

## Task 16: Tray Integration

**Files:** Create `src/lap_coach_logger/viewmodels/tray_vm.py`, modify `qml_bootstrap.py`.

TrayViewModel wraps QSystemTrayIcon. Signals: `showRequested`, `exitRequested`, `overlayToggleRequested`. Wire into bootstrap and AppShell close-to-tray.

- [ ] **Step 1:** Write TrayViewModel
- [ ] **Step 2:** Wire into qml_bootstrap.py
- [ ] **Step 3:** Add close-to-tray in main.qml
- [ ] **Step 4:** Commit — `feat: add TrayViewModel — system tray for QML`

---

## Task 17: Integration Smoke Tests

**Files:** Create `tests/test_qml_integration.py`.

Test all ViewModels instantiate via `build_view_models`. Test snapshot propagation from service through session and overlay VMs. Run all VM tests together.

- [ ] **Step 1:** Write integration tests
- [ ] **Step 2:** Run all VM + integration tests
- [ ] **Step 3:** Commit — `test: add QML integration smoke tests`

---

## Task 18: Cleanup Old UI

**Only after QML is verified working.** Delete `ui/desktop/`, old UI files, legacy test files. Remove legacy-ui optional dependency. Run all tests.

- [ ] **Step 1:** Manually verify QML app works
- [ ] **Step 2:** Delete old UI files
- [ ] **Step 3:** Clean up imports and pyproject.toml
- [ ] **Step 4:** Run all tests
- [ ] **Step 5:** Commit — `chore: remove legacy QWidgets UI`

---

## Execution Order

| Task | Dependencies | Can Parallelize With |
|------|-------------|---------------------|
| 1 | None | 2, 3, 4, 5, 6 |
| 2 | None | 1, 3, 4, 5, 6 |
| 3 | None | 1, 2, 4, 5, 6 |
| 4 | None | 1, 2, 3, 5, 6 |
| 5 | None | 1, 2, 3, 4, 6 |
| 6 | None | 1, 2, 3, 4, 5 |
| 7 | 2, 3, 4, 5, 6 | — |
| 8 | 1 | 9 |
| 9 | 1 | 8 |
| 10 | 8, 9 | 11, 12, 13 |
| 11 | 8, 10 | 12, 13 |
| 12 | 8, 11 | 13 |
| 13 | 9 | 10, 11, 12 |
| 14 | 7, 11, 12, 13 | — |
| 15 | 14 | 16 |
| 16 | 14 | 15 |
| 17 | All above | — |
| 18 | 17 (verified) | — |
