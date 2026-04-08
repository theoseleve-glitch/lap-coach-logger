# Lap Coach Logger v2.0.0 -- User Guide

## Quick Start

### Running from source

```
python -m lap_coach_logger
```

### Running the built executable

```
dist\LapCoachLogger\LapCoachLogger.exe
```

Or double-click `run.bat` in the project root -- it will launch the exe if present, otherwise fall back to the Python source.

---

## Navigation

The main window has four tabs:

| Tab        | Description                              |
|------------|------------------------------------------|
| Dashboard  | Session overview and connection status    |
| Live       | Real-time telemetry while driving         |
| History    | Past session review and lap comparison    |
| Overlays   | Manage floating overlay widgets           |

**Keyboard:** Press **Ctrl+1** through **Ctrl+4** to switch between tabs.

---

## Overlay System

Overlays are transparent floating windows that sit on top of your sim.

### Managing widgets

1. Go to the **Overlays** tab.
2. Each widget has a toggle switch -- flip it to enable or disable.
3. Click the **OVERLAY** button (or press **Ctrl+O**) to show or hide all active floating windows.

### Positioning and resizing

- **Drag** any overlay window to reposition it on screen.
- **Corner grip** -- drag the bottom-right corner to resize.
- **Right-click** an overlay for a context menu with options to center, reset, or hide it.

---

## Overlay Settings

Each overlay widget exposes these settings:

| Setting       | Range        | Description                              |
|---------------|--------------|------------------------------------------|
| Scale         | 50% -- 200%  | Resize the widget proportionally          |
| Font Scale    | 0.7x -- 1.5x | Adjust text sizes within the widget       |
| Opacity       | 30% -- 100%  | Window transparency                       |
| Refresh Rate  | 30 / 60 Hz   | How often the widget redraws              |

---

## Layout Presets

The Overlays tab sidebar offers one-click layout presets:

- **Qualifying Focus** -- larger delta and sector widgets, minimal clutter.
- **Race Focus** -- gap, fuel, and tyre widgets front and center.
- **Streaming** -- layouts optimised for OBS/stream capture.
- **Minimal** -- only the essentials, smallest footprint.

Select a preset to instantly arrange and resize all active overlays.

---

## Keyboard Shortcuts

| Shortcut         | Action                                    |
|------------------|-------------------------------------------|
| Ctrl+O           | Toggle overlay visibility                  |
| Ctrl+L           | Toggle live telemetry recording            |
| Ctrl+G           | Toggle g-force widget                      |
| Ctrl+H           | Open history / session review              |
| Ctrl+Up          | Increase overlay opacity                   |
| Ctrl+Down        | Decrease overlay opacity                   |
| Ctrl+1           | Switch to Dashboard tab                    |
| Ctrl+2           | Switch to Live tab                         |
| Ctrl+3           | Switch to History tab                      |
| Ctrl+4           | Switch to Overlays tab                     |
| Alt+1 -- Alt+9   | Quick-toggle individual overlay widgets    |
| F1               | Open help / about                          |
| Escape           | Close current dialog or overlay            |

---

## Sim Compatibility

Lap Coach Logger supports the following simulators:

- iRacing
- Assetto Corsa Competizione (ACC)
- Assetto Corsa
- Le Mans Ultimate

### Important notes

- The sim **must run in borderless fullscreen** for overlays to appear on top of the game window.
- Overlays use the **TOPMOST + NOACTIVATE** window flags, so they will never steal focus from your sim.

---

## Tray Behavior

- **Closing the window** does not quit the application -- it minimises to the system tray.
- **Right-click** the tray icon to open a menu with quick actions.
- Select **Exit** from the tray menu to fully quit the application.
