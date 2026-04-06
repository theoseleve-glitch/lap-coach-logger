# Lap Coach Logger — Apple-Quality QML Rewrite

**Date:** 2026-04-06
**Status:** Approved
**Approach:** Revolutionary — full QML frontend rewrite

## Goal

Transform the Lap Coach Logger from a functional PySide6 QWidgets desktop app into an Apple-quality, frictionless product that feels like it was designed by Apple's Human Interface team. The app should embody the warmth of Apple Health and the minimalism of the Tesla app — premium but not cold, data-rich but never overwhelming.

## Constraints

- Python backend (adapters, coordinator, writers, config, health, sync) remains 100% untouched
- Windows 10/11 only
- PySide6 >= 6.7 (QML support)
- Must preserve all existing functionality: telemetry capture for iRacing, ACC, Assetto Corsa, Le Mans Ultimate
- Must preserve: single-instance behavior, start-with-Windows, tray integration, overlay window
- Build pipeline (PyInstaller + Inno Setup) must continue to work

## Architecture

### Three-Layer Separation

```
┌─────────────────────────────────────────────────┐
│  QML Frontend (NEW)                              │
│  AppShell.qml, pages, components, theme          │
│  GPU-accelerated, declarative, 60fps animations  │
├─────────────────────────────────────────────────┤
│  ViewModel Bridge (NEW)                          │
│  QObject subclasses with @Property/@Signal/@Slot │
│  Wraps existing services, exposes reactive props │
├─────────────────────────────────────────────────┤
│  Python Backend (UNCHANGED)                      │
│  Adapters, SessionCoordinator, ProcessWatcher,   │
│  Writers, ConfigManager, HealthMonitor, Sync     │
└─────────────────────────────────────────────────┘
```

### QML Engine Integration

- `QQmlApplicationEngine` replaces `QApplication` + `QMainWindow`
- ViewModels registered as QML context properties
- Python types exposed via `qmlRegisterType` where needed
- Existing `DesktopService` adapted into a `ServiceViewModel` that exposes all state as QML-bindable properties

### File Structure (New QML Layer)

```
src/lap_coach_logger/
├── qml/
│   ├── main.qml                    # Entry point
│   ├── AppShell.qml                # Window + nav bar + page stack
│   ├── Theme/
│   │   ├── Tokens.qml              # Colors, spacing, radii, motion
│   │   ├── Typography.qml          # Type scale definitions
│   │   └── Motion.qml              # Easing curves, durations
│   ├── Components/
│   │   ├── NavBar.qml              # Unified top navigation
│   │   ├── StatusPill.qml          # Animated status indicator
│   │   ├── MetricCard.qml          # Reusable data card
│   │   ├── SessionCard.qml         # History list item
│   │   ├── SectionTabs.qml         # Chip-style tab bar
│   │   ├── SlideOver.qml           # Animated slide-over panel
│   │   ├── ToggleSwitch.qml        # iOS-style toggle
│   │   ├── SearchBar.qml           # Search input with filter
│   │   ├── Sparkline.qml           # Real-time sparkline chart
│   │   ├── SectorBars.qml          # Colored sector progress
│   │   ├── ThrottleBrakeBar.qml    # Input visualization
│   │   ├── LapTimeChart.qml        # Bar chart for lap progression
│   │   └── ConfirmDialog.qml       # Scale + fade confirmation
│   ├── Pages/
│   │   ├── DashboardPage.qml       # Hero card + metrics + actions
│   │   ├── LivePage.qml            # Real-time telemetry during session
│   │   ├── HistoryPage.qml         # Session library with search
│   │   └── ReviewPage.qml          # Session deep-dive (push nav)
│   ├── Panels/
│   │   ├── SettingsPanel.qml       # Slide-over settings
│   │   ├── DiagnosticsPanel.qml    # Logs + health + support bundle
│   │   └── AboutPanel.qml          # Product info
│   ├── Overlay/
│   │   ├── OverlayWindow.qml       # Frameless HUD window
│   │   └── OverlayContent.qml      # HUD layout + data binding
│   └── Onboarding/
│       └── OnboardingFlow.qml      # 3-step first-run flow
├── viewmodels/
│   ├── __init__.py
│   ├── service_vm.py               # Wraps DesktopService
│   ├── session_vm.py               # Live session state
│   ├── history_vm.py               # Session history list
│   ├── review_vm.py                # Session review data
│   ├── settings_vm.py              # Config read/write
│   └── overlay_vm.py               # Overlay state
└── qml_bootstrap.py                # QML engine setup, replaces run_desktop_shell
```

## Navigation Architecture

### Primary Navigation — Unified Top Nav Bar

One bar replaces the previous three layers (sidebar + top bar + workspace strip):

```
[Logo] LAP COACH  |  Dashboard · Live · History  |  [status pill]  |  [⚙]
```

- **Brand mark** — 28×28px monogram + "LAP COACH" wordmark
- **Nav items** — three page buttons with active highlight (Pit Orange tint)
- **Status pill** — animated indicator showing current state (Idle/Recording/etc.)
- **Gear icon** — opens Settings slide-over

### Page Flow

| Route | Type | Entry |
|-------|------|-------|
| Dashboard | Tab | Nav bar |
| Live | Tab | Nav bar |
| History | Tab | Nav bar |
| Review | Push | Tap session card in History (← back to History) |
| Settings | Slide-over | ⚙ gear icon |
| Diagnostics | Sub-panel | Settings → Diagnostics link |
| About | Sub-panel | Settings → About link |
| Onboarding | Modal flow | First launch only |

### What Moved

| Old Location | New Location | Rationale |
|-------------|-------------|-----------|
| LOGS (top-level nav) | Settings → Diagnostics | Power-user concern, not primary navigation |
| OVERLAY (top-level nav) | Toggle from Settings or tray | Not a page you navigate to |
| CONFIG button (top bar) | Settings → General | Lives with other settings |
| Engineering tab (dashboard) | Review → Engineering tab | Contextual to a specific session |
| Setup tab (dashboard) | Review → Setup tab | Contextual to a specific session |

## Design System v2

### Color Palette — Surface Elevation

Pure black (#000000) is retired. New 4-tier near-black elevation scale:

| Token | Hex | Usage |
|-------|-----|-------|
| `void` | `#050607` | App background |
| `surface` | `#0A0B0E` | Cards, nav bar |
| `elevated` | `#141519` | Hover states, slide-overs |
| `raised` | `#1E1F25` | Input fields, wells |

### Accent Colors (Unchanged, Roles Refined)

| Token | Hex | Role |
|-------|-----|------|
| `chalk` | `#F0EDE5` | Primary text |
| `steel` | `#949494` | Secondary text, labels |
| `pitOrange` | `#C9A84C` | Brand accent, best lap, active nav |
| `acidGreen` | `#22C55E` | Recording, success, positive delta |
| `safetyRed` | `#FF2A2A` | Danger, stop, negative delta |
| `marshalYellow` | `#FACC15` | Caution, arming, warnings |
| `racingPurple` | `#8B5CF6` | Insights, secondary sim badges |

### Typography Scale

| Token | Size | Weight | Family | Usage |
|-------|------|--------|--------|-------|
| `display` | 32px | 700 | Segoe UI | Hero headings, greeting |
| `title` | 22px | 700 | Segoe UI | Page titles, session names |
| `heading` | 17px | 600 | Segoe UI | Section headings |
| `body` | 14px | 400 | Segoe UI | Descriptions, body text |
| `caption` | 12px | 400 | Segoe UI | Metadata, secondary info |
| `data` | 28px | 700 | Consolas | Lap times, large metrics |
| `micro` | 10px | 700 | Consolas | Labels, status text (letter-spacing: 1.5px) |

### Spacing Scale (8px Base Grid)

| Token | Value | Usage |
|-------|-------|-------|
| `xs` | 4px | Tight gaps, inline spacing |
| `sm` | 8px | Component internal padding |
| `md` | 12px | Between related elements |
| `lg` | 16px | Card internal padding, gaps |
| `xl` | 24px | Between sections |
| `2xl` | 32px | Page padding |
| `3xl` | 48px | Major section breaks |
| `4xl` | 64px | Hero spacing |

### Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `sm` | 6px | Pills, tags, status badges |
| `md` | 10px | Buttons, inputs, nav items |
| `lg` | 14px | Cards, metric panels |
| `xl` | 20px | Hero cards, nav bar, overlay |

### Borders & Dividers

| Token | Value | Usage |
|-------|-------|-------|
| `subtle` | 1px rgba(chalk, 0.06) | Card borders, separators |
| `medium` | 1px rgba(chalk, 0.10) | Hover borders, input borders |
| `focus` | 2px pitOrange @ 0.5 | Focus rings |

## Motion System

All state changes are animated. Nothing snaps.

### Page Transitions

- **Crossfade + slide**: outgoing page fades out (200ms) while sliding 30px in direction of travel. Incoming page fades in (250ms) with 40ms overlap.
- **Easing**: `Easing.OutCubic`
- **Push navigation** (History → Review): slide from right (300ms, `Easing.OutQuint`). Back: slide from left.

### Micro-Interactions

| Interaction | Animation | Duration | Easing |
|-------------|-----------|----------|--------|
| Button hover | scale 1.0 → 1.02 | 120ms | `Easing.OutBack` |
| Button press | scale → 0.98 | 80ms | `Easing.InOutQuad` |
| Focus ring | 2px Pit Orange glow fade | 150ms | `Easing.InOutSine` |
| Card hover | border brightens, subtle lift | 150ms | `Easing.OutCubic` |

### Status Changes

| Change | Animation | Duration | Easing |
|--------|-----------|----------|--------|
| Status pill color | Color morph | 400ms | `Easing.InOutSine` |
| Recording indicator | Opacity pulse 1.0↔0.7 | 1500ms loop | `Easing.InOutSine` |
| New metric value | Count-up animation | 300ms | `Easing.OutCubic` |
| Quality badge appear | Scale 0→1 + fade | 200ms | `Easing.OutBack` |

### Slide-Overs & Dialogs

| Element | Animation | Duration | Easing |
|---------|-----------|----------|--------|
| Settings open | Slide from right edge | 300ms | `Easing.OutQuint` |
| Settings close | Slide to right edge | 200ms | `Easing.InQuad` |
| Background dim | Opacity 0→0.4 | 250ms | `Easing.OutCubic` |
| Confirm dialog | Scale 0.95→1.0 + fade | 200ms | `Easing.OutBack` |

## Page Designs

### Dashboard

The resting state of the app. Apple Health-inspired progressive disclosure.

**Layout:**
1. **Time-of-day greeting** — "Good morning/afternoon/evening" + monitoring status line
2. **Hero card** — last session with track name, sim, lap count, best lap time (large mono), lap time trend sparkline, two actions (Review Session →, Open Folder)
3. **4 metric cards** — Sessions today, Total laps, Drive time, Data captured. Large mono values with subtle trend indicators.
4. **Quick Actions row** — Open Output Folder, Toggle Overlay, Export Last Session

**Empty state (no sessions yet):** Hero card replaced with a warm welcome message and "Start any simulator to begin" prompt.

### Live Page

Second-monitor view during active recording.

**Layout:**
1. **Session context** — track name, sim, car, sample rate (left). Current lap number (large, right).
2. **Three primary metrics** — Last Lap (+ delta vs best), Best Lap (Pit Orange highlight), Consistency (percentage + σ)
3. **Two telemetry traces** — Speed sparkline (real-time animated), Throttle/Brake bars (real-time)
4. **Lap table** — compact rows with expandable sectors. Best lap row highlighted.

**Idle state (no recording):** Shows a calm "Waiting for simulator" message with the monitoring status. No empty tables or blank panels.

### History Page

A library of sessions, not a spreadsheet.

**Layout:**
1. **Page header** — "History" title + total count/size. Search bar + sim filter dropdown.
2. **Date-grouped session cards** — grouped by date (TODAY, YESTERDAY, APR 4, etc.)
3. **Session card** — sim badge (color-coded) → track name + metadata → best lap time → quality grade (A+/A/B+/B/C) → chevron
4. **Tap** pushes into Review page. **Right-click** opens context menu (Export CSV, Copy Session ID, Mark Ignored, Delete).

### Review Page

Full session deep-dive. Push navigation from History.

**Chrome:**
- `‹ History` back button replaces nav items
- Session actions in nav bar: Open Folder, Export CSV, Reprocess, Delete

**Layout:**
1. **Session header** — sim badge + quality grade, track name (title), car + lap count + date + duration, best lap time (huge mono)
2. **Section tabs** — Overview · Laps · Telemetry · Setup · Engineering
3. **Overview tab** — 4 summary metrics (median, consistency, clean laps, data size) + lap time progression chart
4. **Laps tab** — full lap table with sector times, deltas, status flags
5. **Telemetry tab** — trace visualizations (speed, throttle, brake, steering, g-force)
6. **Setup tab** — setup tools, favorites, install, diff (migrated from old dashboard)
7. **Engineering tab** — operations, raw capture toggle, profiles (migrated from old dashboard)

### Settings Slide-Over

Not a dialog. Slides from the right edge (300ms), dims background.

**Sections:**
1. **General** — Output directory (with Browse), Driver name, Start with Windows (toggle switch)
2. **Recording** — Sample rate (Hz), Detection poll (s), Min duration, Min samples, Disconnect timeout
3. **Overlay** — Opacity slider, Pin mode, Visible data rows
4. **Simulators** — Toggle switch per sim (iRacing, ACC, Assetto Corsa, LMU)
5. **Sync** — API key, base URL, auto-sync toggle (if sync is configured)
6. **Diagnostics** link → sub-panel with logs viewer, health status, support bundle export, About info

All inputs use the `raised` (#1E1F25) background. Toggle switches are iOS-style with animated knob.

### Overlay HUD

Frameless, always-on-top, semi-transparent (88% opacity) with backdrop blur.

**Layout (compact, ~380px wide):**
1. **Context line** — track · class · lap number | recording indicator with elapsed time
2. **Three times** — Current (counting), Last (+ delta), Best (Pit Orange)
3. **Sector bars** — three horizontal bars: green (faster), red (slower), grey (pending). Animate on sector completion.
4. **Speed + inputs** — speed value | throttle bar (green) + brake bar (red)

**Properties:**
- Draggable by any empty area
- Resizable
- Configurable visible rows (from Settings → Overlay)
- Position/size remembered between sessions
- Opacity adjustable

### First-Run Onboarding

Three-screen modal flow on first launch:

1. **Welcome** — "Welcome to Lap Coach. Local-first telemetry capture. No cloud. No account. Your data stays yours."
2. **Simulators** — "Which sims do you drive?" Toggle switches for each supported sim.
3. **Ready** — "You're all set. Start any sim and Lap Coach will begin recording automatically."

Each screen has a Continue/Done button. Total time: ~15 seconds. Config is saved, app opens to Dashboard.

## Tray Integration

Preserved from the current implementation:
- Closing the window minimizes to tray (with tray notification on first close)
- Tray icon unchanged (static icon). Recording state is communicated via the status pill in the nav bar and the tooltip on hover.
- Tray menu: Show | Toggle Overlay | Resume/Pause Monitoring | Open Output | Exit
- Double-click tray icon restores window
- Second launch sends restore signal to existing instance

## Existing Features Preserved

Every feature in the current app is preserved. Mapping:

| Current Feature | New Location |
|----------------|-------------|
| Dashboard overview metrics | Dashboard → metric cards |
| Dashboard engineering tab | Review → Engineering tab |
| Dashboard setup tools | Review → Setup tab |
| Dashboard operations | Review → Engineering tab |
| Live telemetry view | Live page |
| Logs viewer | Settings → Diagnostics |
| History table | History page (card layout) |
| Session review | Review page (push from History) |
| Settings dialog | Settings slide-over |
| About dialog | Settings → About |
| Overlay window | Overlay HUD (QML rewrite) |
| Start/Stop monitoring | Nav bar (PAUSE during recording) + tray menu |
| Open output/logs/config | Dashboard quick actions + Settings → Diagnostics |
| Support bundle export | Settings → Diagnostics |
| LMU import (CLI) | Unchanged (CLI-only) |
| Setup coach (CLI) | Unchanged (CLI-only) |

## What Gets Deleted

The entire `ui/desktop/` directory and `ui/qt_shell.py`, `ui/tray.py`, `ui/settings_window.py`, `ui/status_text.py` are replaced by the QML frontend. The `ui/desktop/overlay_browser/` subsystem (web-based overlay) is replaced by `Overlay/OverlayWindow.qml`.

Legacy UI dependencies (`customtkinter`, `pystray`, `Pillow`) in `[project.optional-dependencies]` can be removed.

## Build Considerations

- PyInstaller must bundle `.qml` files as data files in the spec
- QML import paths must be configured for frozen builds
- Qt Quick module must be included in PyInstaller hidden imports
- Inno Setup installer unchanged (still packages `dist/LapCoachLogger/`)

## Testing Strategy

- ViewModels are testable in isolation (pure Python, no QML dependency)
- QML components tested via `QQuickView` in headless mode where possible
- Integration tests verify ViewModel ↔ backend service contracts
- Visual regression testing via screenshot comparison (optional, manual)
- All existing backend tests remain unchanged
