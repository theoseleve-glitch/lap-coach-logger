# Mode System + Sprint Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 4-mode system (Sprint/Endurance/Coaching/Data) with auto-detection from session type, a mode selector banner on session connect, mode-aware strategy tabs, and mode-aware overlay defaults. Sprint mode gets a simplified 2-tab strategy flow (Setup + Live).

**Architecture:** `mode_detector.py` is a pure function mapping session type → suggested mode. `ModeViewModel` (QObject) holds the active mode and exposes it to QML. `StrategyPage.qml` renders different tab sets based on mode. `OverlayViewModel` reads the mode to set default overlay visibility. `ModeBanner.qml` appears once on session connect for confirmation/override.

**Tech Stack:** Python 3.12 dataclasses, PySide6 QObject, QML.

**Spec:** `docs/superpowers/specs/2026-04-13-hero-workflow-design.md`

---

## Task 1: Mode Detector + Mode ViewModel

**Files:**
- Create: `src/lap_coach_logger/core/mode_detector.py`
- Create: `src/lap_coach_logger/viewmodels/mode_vm.py`
- Test: `tests/test_mode_detector.py`
- Test: `tests/test_mode_vm.py`

- [ ] **Step 1: Write failing tests for mode detection**

```python
# tests/test_mode_detector.py
"""Tests for session type → mode detection."""
from __future__ import annotations

from lap_coach_logger.core.mode_detector import suggest_mode


def test_practice_suggests_coaching():
    assert suggest_mode("practice") == "coaching"


def test_qualifying_suggests_coaching():
    assert suggest_mode("qualifying") == "coaching"


def test_short_race_suggests_sprint():
    assert suggest_mode("race", race_duration_s=1800) == "sprint"


def test_long_race_suggests_endurance():
    assert suggest_mode("race", race_duration_s=3600) == "endurance"


def test_race_without_duration_defaults_sprint():
    assert suggest_mode("race") == "sprint"


def test_timed_race_over_45min_suggests_endurance():
    assert suggest_mode("race", race_duration_s=2701, is_timed=True) == "endurance"


def test_time_trial_suggests_coaching():
    assert suggest_mode("time trial") == "coaching"


def test_unknown_session_suggests_data():
    assert suggest_mode("test day") == "data"
    assert suggest_mode("") == "data"
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_mode_detector.py -v`

- [ ] **Step 3: Implement mode_detector.py**

```python
# src/lap_coach_logger/core/mode_detector.py
"""Session type → mode detection.

Maps sim session types to one of four modes:
sprint, endurance, coaching, data.
"""
from __future__ import annotations

MODES = ("sprint", "endurance", "coaching", "data")

_COACHING_SESSIONS = frozenset({
    "practice", "qualifying", "lone qualify", "open qualify", "time trial",
})

_ENDURANCE_THRESHOLD_S = 2700  # 45 minutes


def suggest_mode(
    session_type: str,
    race_duration_s: float | None = None,
    is_timed: bool = False,
) -> str:
    """Return the suggested mode for a session type."""
    normalized = session_type.strip().lower()

    if normalized in _COACHING_SESSIONS:
        return "coaching"

    if normalized == "race":
        if race_duration_s is not None and race_duration_s > _ENDURANCE_THRESHOLD_S:
            return "endurance"
        if is_timed:
            return "endurance"
        return "sprint"

    return "data"
```

- [ ] **Step 4: Run mode detector tests**

Run: `.venv/Scripts/python -m pytest tests/test_mode_detector.py -v`
Expected: ALL PASS

- [ ] **Step 5: Write failing tests for ModeViewModel**

```python
# tests/test_mode_vm.py
"""Tests for ModeViewModel."""
from __future__ import annotations

from tests.qt_mock import install
install()

from lap_coach_logger.viewmodels.mode_vm import ModeViewModel


def test_default_mode_is_sprint():
    vm = ModeViewModel()
    assert vm.activeMode == "sprint"


def test_set_mode():
    vm = ModeViewModel()
    vm.setMode("endurance")
    assert vm.activeMode == "endurance"


def test_invalid_mode_rejected():
    vm = ModeViewModel()
    vm.setMode("invalid")
    assert vm.activeMode == "sprint"  # unchanged


def test_on_session_detected_sets_suggested_mode():
    vm = ModeViewModel()
    vm.onSessionDetected("practice", 0, False)
    assert vm.activeMode == "coaching"
    assert vm.bannerVisible is True


def test_dismiss_banner():
    vm = ModeViewModel()
    vm.onSessionDetected("practice", 0, False)
    assert vm.bannerVisible is True
    vm.dismissBanner()
    assert vm.bannerVisible is False


def test_session_info():
    vm = ModeViewModel()
    vm.onSessionDetected("race", 1800, False)
    assert vm.activeMode == "sprint"
    assert vm.sessionType == "race"
```

- [ ] **Step 6: Implement ModeViewModel**

```python
# src/lap_coach_logger/viewmodels/mode_vm.py
"""Mode state management for the hero workflow."""
from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot

from lap_coach_logger.core.mode_detector import MODES, suggest_mode


class ModeViewModel(QObject):
    """Holds the active mode and exposes it to QML."""

    modeChanged = Signal()
    bannerChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._active_mode = "sprint"
        self._banner_visible = False
        self._session_type = ""
        self._race_duration_s = 0.0

    @Property(str, notify=modeChanged)
    def activeMode(self) -> str:  # noqa: N802
        return self._active_mode

    @Property(bool, notify=bannerChanged)
    def bannerVisible(self) -> bool:  # noqa: N802
        return self._banner_visible

    @Property(str, notify=modeChanged)
    def sessionType(self) -> str:  # noqa: N802
        return self._session_type

    @Slot(str)
    def setMode(self, mode: str) -> None:  # noqa: N802
        if mode in MODES:
            self._active_mode = mode
            self.modeChanged.emit()

    @Slot()
    def dismissBanner(self) -> None:  # noqa: N802
        self._banner_visible = False
        self.bannerChanged.emit()

    def onSessionDetected(self, session_type: str, race_duration_s: float, is_timed: bool) -> None:  # noqa: N802
        self._session_type = session_type
        self._race_duration_s = race_duration_s
        self._active_mode = suggest_mode(session_type, race_duration_s, is_timed)
        self._banner_visible = True
        self.modeChanged.emit()
        self.bannerChanged.emit()
```

- [ ] **Step 7: Run all tests**

Run: `.venv/Scripts/python -m pytest tests/test_mode_detector.py tests/test_mode_vm.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/lap_coach_logger/core/mode_detector.py src/lap_coach_logger/viewmodels/mode_vm.py tests/test_mode_detector.py tests/test_mode_vm.py
git commit -m "feat: add mode detector and ModeViewModel (sprint/endurance/coaching/data)"
```

---

## Task 2: Register ModeViewModel + Wire to Session Lifecycle

**Files:**
- Modify: `src/lap_coach_logger/qml_bootstrap.py`
- Modify: `src/lap_coach_logger/ui/desktop/service.py`
- Modify: `src/lap_coach_logger/viewmodels/__init__.py`

- [ ] **Step 1: Add ModeViewModel to qml_bootstrap.py**

In `build_view_models()`, create ModeViewModel and add to the returned dict:

```python
from lap_coach_logger.viewmodels.mode_vm import ModeViewModel
```

Create it before the strategy VM:
```python
mode_vm = ModeViewModel()
```

Add to returned dict:
```python
"mode": mode_vm,
```

This makes `modeVM` available in QML (the existing loop does `ctx.setContextProperty(f"{name}VM", vm)`).

- [ ] **Step 2: Wire mode detection to DesktopService**

In `src/lap_coach_logger/ui/desktop/service.py`, where the strategy VM session lifecycle is triggered (search for `_strategy_session_active`), also trigger the mode VM:

```python
self._mode_vm = None  # set externally
```

In the session detection block (where `on_session_detected` is called):
```python
if hasattr(self, "_mode_vm") and self._mode_vm is not None:
    race_dur = 0.0  # extract from session info if available
    self._mode_vm.onSessionDetected(str(session_type), race_dur, False)
```

In `qml_bootstrap.py`, wire it:
```python
service._mode_vm = mode_vm
```

- [ ] **Step 3: Add ModeViewModel to __init__.py exports**

In `src/lap_coach_logger/viewmodels/__init__.py`, add `ModeViewModel` to the imports and `__all__`.

- [ ] **Step 4: Verify import and bootstrap**

Run: `.venv/Scripts/python -c "from lap_coach_logger.viewmodels.mode_vm import ModeViewModel; print('OK')"`
Run: `.venv/Scripts/python -m pytest tests/test_qml_bootstrap.py tests/test_qml_integration.py -q --tb=short`

- [ ] **Step 5: Commit**

```bash
git add src/lap_coach_logger/qml_bootstrap.py src/lap_coach_logger/ui/desktop/service.py src/lap_coach_logger/viewmodels/__init__.py
git commit -m "feat: register ModeViewModel and wire to session lifecycle"
```

---

## Task 3: Mode Banner QML

**Files:**
- Create: `src/lap_coach_logger/qml/Components/ModeBanner.qml`
- Modify: `src/lap_coach_logger/qml/AppShell.qml`

- [ ] **Step 1: Create ModeBanner.qml**

A floating banner that appears on session connect for mode confirmation:

```qml
// src/lap_coach_logger/qml/Components/ModeBanner.qml
import QtQuick
import QtQuick.Layouts
import "../Theme" as Theme

Rectangle {
    id: root

    property string detectedSession: ""
    property string activeMode: "sprint"
    property bool bannerVisible: false

    signal modeSelected(string mode)
    signal dismissed()

    visible: bannerVisible
    anchors.horizontalCenter: parent.horizontalCenter
    y: bannerVisible ? 60 : -height
    width: Math.min(parent.width - 48, 520)
    height: bannerCol.implicitHeight + Theme.Tokens.xl * 2
    radius: Theme.Tokens.radiusLg
    color: Theme.Tokens.elevated
    border.width: 1
    border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.25)
    z: 100

    Behavior on y { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }

    Column {
        id: bannerCol
        anchors {
            left: parent.left; right: parent.right; top: parent.top
            margins: Theme.Tokens.xl
        }
        spacing: Theme.Tokens.md

        Text {
            text: "Session Detected"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Theme.Typography.microSize
            font.weight: Font.Bold
            font.letterSpacing: 1.5
            color: Theme.Tokens.pitOrange
        }

        Text {
            text: root.detectedSession || "Unknown session"
            font.family: Theme.Typography.bodyFamily
            font.pixelSize: Theme.Typography.bodySize
            color: Theme.Tokens.chalk
        }

        Row {
            spacing: Theme.Tokens.sm

            Repeater {
                model: [
                    { mode: "sprint",    label: "SPRINT" },
                    { mode: "endurance", label: "ENDURANCE" },
                    { mode: "coaching",  label: "COACHING" },
                    { mode: "data",      label: "DATA" }
                ]

                delegate: Rectangle {
                    required property var modelData
                    width: modeBtnText.implicitWidth + Theme.Tokens.lg * 2
                    height: 32
                    radius: Theme.Tokens.radiusSm
                    color: root.activeMode === modelData.mode
                           ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.20)
                           : "transparent"
                    border.width: 1
                    border.color: root.activeMode === modelData.mode
                                  ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.40)
                                  : Theme.Tokens.subtle(Theme.Tokens.chalk, 0.10)

                    Text {
                        id: modeBtnText
                        anchors.centerIn: parent
                        text: modelData.label
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: Theme.Typography.microSize
                        font.weight: Font.Bold
                        font.letterSpacing: 1.2
                        color: root.activeMode === modelData.mode
                               ? Theme.Tokens.pitOrange
                               : Theme.Tokens.steel
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.modeSelected(modelData.mode)
                    }
                }
            }
        }

        Rectangle {
            width: continueText.implicitWidth + Theme.Tokens.xl * 2
            height: 36
            radius: Theme.Tokens.radiusMd
            color: continueArea.containsMouse
                   ? Qt.lighter(Theme.Tokens.pitOrange, 1.1)
                   : Theme.Tokens.pitOrange

            Text {
                id: continueText
                anchors.centerIn: parent
                text: "Continue"
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: Theme.Typography.captionSize
                font.weight: Font.DemiBold
                color: Theme.Tokens.void_
            }

            MouseArea {
                id: continueArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.dismissed()
            }
        }
    }
}
```

- [ ] **Step 2: Add ModeBanner to AppShell.qml**

In `src/lap_coach_logger/qml/AppShell.qml`, after the StackView and before the statusBar, add:

```qml
Components.ModeBanner {
    id: modeBanner
    detectedSession: {
        var track = typeof strategyVM !== "undefined" && strategyVM ? strategyVM.trackName : ""
        var car = typeof strategyVM !== "undefined" && strategyVM ? strategyVM.carName : ""
        var mode = typeof modeVM !== "undefined" && modeVM ? modeVM.sessionType : ""
        if (track && car) return mode + " · " + track + " · " + car
        return mode || "Connecting..."
    }
    activeMode: typeof modeVM !== "undefined" && modeVM ? modeVM.activeMode : "sprint"
    bannerVisible: typeof modeVM !== "undefined" && modeVM ? modeVM.bannerVisible : false

    onModeSelected: function(mode) {
        if (modeVM) modeVM.setMode(mode)
    }
    onDismissed: {
        if (modeVM) modeVM.dismissBanner()
    }
}
```

- [ ] **Step 3: Add mode indicator to NavBar**

In `src/lap_coach_logger/qml/Components/NavBar.qml`, add a small mode badge next to the version text (at the right end of the nav bar):

```qml
// Mode badge (after version text)
Rectangle {
    visible: typeof modeVM !== "undefined" && modeVM && modeVM.activeMode !== ""
    implicitWidth: modeBadgeText.implicitWidth + 12
    height: 20
    radius: 4
    color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.12)
    border.width: 1
    border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.25)

    Text {
        id: modeBadgeText
        anchors.centerIn: parent
        text: (typeof modeVM !== "undefined" && modeVM ? modeVM.activeMode : "").toUpperCase()
        font.family: Theme.Typography.monoFamily
        font.pixelSize: 8
        font.weight: Font.Bold
        font.letterSpacing: 0.8
        color: Theme.Tokens.pitOrange
    }
}
```

- [ ] **Step 4: Verify app launches with mode banner**

Run: `start "" .venv/Scripts/pythonw.exe -m lap_coach_logger`
Verify the mode badge appears in the nav bar.

- [ ] **Step 5: Commit**

```bash
git add src/lap_coach_logger/qml/Components/ModeBanner.qml src/lap_coach_logger/qml/AppShell.qml src/lap_coach_logger/qml/Components/NavBar.qml
git commit -m "feat: add mode selection banner and nav bar mode indicator"
```

---

## Task 4: Mode-Aware Strategy Tabs

**Files:**
- Modify: `src/lap_coach_logger/qml/Pages/StrategyPage.qml`
- Modify: `src/lap_coach_logger/viewmodels/strategy_vm.py`

- [ ] **Step 1: Update StrategyViewModel.activeTab to be mode-aware**

In `strategy_vm.py`, update the `activeTab` property to consider the mode:

```python
    @Property(str, notify=planChanged)
    def activeTab(self) -> str:  # noqa: N802
        if self._mode == "sprint":
            if self._plan is not None:
                return "live"
            return "setup"
        if self._mode == "data":
            return "telemetry"
        # endurance + coaching: existing logic
        if self._plan is not None:
            return "raceplan"
        if self._profiles:
            return "build"
        return "practice"
```

Add `self._mode = "sprint"` to `__init__` and a setter:

```python
    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.planChanged.emit()  # triggers activeTab recalculation

    @Property(str, notify=planChanged)
    def currentMode(self) -> str:  # noqa: N802
        return self._mode
```

Add a `tabsForMode` property that returns the available tabs:

```python
    @Property(list, notify=planChanged)
    def tabsForMode(self) -> list[dict]:  # noqa: N802
        if self._mode == "sprint":
            return [
                {"id": "setup", "label": "SETUP"},
                {"id": "live", "label": "LIVE"},
            ]
        if self._mode == "endurance":
            return [
                {"id": "practice", "label": "PRACTICE"},
                {"id": "build", "label": "BUILD"},
                {"id": "raceplan", "label": "RACE PLAN"},
            ]
        if self._mode == "coaching":
            return [
                {"id": "consistency", "label": "CONSISTENCY"},
                {"id": "pace", "label": "PACE"},
                {"id": "readiness", "label": "READINESS"},
            ]
        if self._mode == "data":
            return [
                {"id": "telemetry", "label": "TELEMETRY"},
                {"id": "export", "label": "EXPORT"},
            ]
        return []
```

- [ ] **Step 2: Wire mode from ModeViewModel to StrategyViewModel**

In `qml_bootstrap.py`, connect mode changes:

```python
mode_vm.modeChanged.connect(lambda: strategy_vm.set_mode(mode_vm.activeMode))
```

- [ ] **Step 3: Update StrategyPage.qml tab bar to be dynamic**

Replace the hardcoded 3-tab Repeater model with the dynamic `tabsForMode`:

```qml
Repeater {
    model: strategyVM ? strategyVM.tabsForMode : []

    delegate: Rectangle {
        required property var modelData
        required property int index
        // ... same styling as current, but using modelData.id and modelData.label
    }
}
```

- [ ] **Step 4: Add Sprint SETUP tab content**

Add a new section visible when `activeTabId === "setup"`:

Sprint Setup is a simplified pre-race view:
- **Fuel calculator**: Race laps × fuel/lap = starting fuel. Auto-populated from stint data if available.
- **Pit window**: If mandatory stop, show when the window opens/closes.
- **One-click pit presets**: "Fill to end", "Splash and go", "Full service" buttons.
- **Compound selector**: If multiple compounds available, pick starting compound.

This is lighter than the Endurance BUILD tab — no compound profiles card, no process strategy flow.

```qml
Column {
    visible: root.activeTabId === "setup"
    width: parent.width
    spacing: Theme.Tokens.xl

    // Fuel calculator card
    Rectangle {
        width: parent.width
        implicitHeight: fuelCalcCol.implicitHeight + Theme.Tokens.xl * 2
        radius: Theme.Tokens.radiusLg
        color: Theme.Tokens.surface
        border.width: 1
        border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

        Column {
            id: fuelCalcCol
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.Tokens.xl }
            spacing: Theme.Tokens.md

            Text {
                text: "FUEL CALCULATOR"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                font.weight: Font.Bold
                font.letterSpacing: 1.5
                color: Theme.Tokens.steel
            }

            // Race laps input
            Row {
                spacing: Theme.Tokens.lg
                Text {
                    text: "Race laps"
                    font.family: Theme.Typography.bodyFamily
                    font.pixelSize: Theme.Typography.captionSize
                    color: Theme.Tokens.steel
                    width: 100
                    anchors.verticalCenter: parent.verticalCenter
                }
                Rectangle {
                    width: 80; height: 32; radius: Theme.Tokens.radiusSm
                    color: Theme.Tokens.elevated
                    border.width: 1; border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.25)
                    TextInput {
                        anchors { fill: parent; margins: 8 }
                        color: Theme.Tokens.chalk
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: Theme.Typography.bodySize
                        text: strategyVM ? strategyVM.totalLaps.toString() : "0"
                        validator: IntValidator { bottom: 0; top: 999 }
                        onEditingFinished: if (strategyVM) strategyVM.setTotalLaps(parseInt(text) || 0)
                    }
                }
            }

            // Computed fuel needed
            Row {
                spacing: Theme.Tokens.lg
                Text { text: "Fuel needed"; font.family: Theme.Typography.bodyFamily; font.pixelSize: Theme.Typography.captionSize; color: Theme.Tokens.steel; width: 100 }
                Text {
                    text: {
                        var laps = strategyVM ? strategyVM.totalLaps : 0
                        var profiles = strategyVM ? strategyVM.compoundProfiles : []
                        if (profiles.length > 0 && laps > 0)
                            return (profiles[0].fuel_per_lap * laps).toFixed(1) + " L"
                        return "—"
                    }
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: 18; font.weight: Font.Bold
                    color: Theme.Tokens.pitOrange
                }
            }

            // Fuel capacity
            Row {
                spacing: Theme.Tokens.lg
                Text { text: "Tank"; font.family: Theme.Typography.bodyFamily; font.pixelSize: Theme.Typography.captionSize; color: Theme.Tokens.steel; width: 100 }
                Text {
                    text: (strategyVM && strategyVM.fuelCapacity > 0) ? strategyVM.fuelCapacity.toFixed(1) + " L" : "awaiting sim"
                    font.family: Theme.Typography.monoFamily; font.pixelSize: Theme.Typography.bodySize
                    color: (strategyVM && strategyVM.fuelCapacity > 0) ? Theme.Tokens.chalk : Theme.Tokens.steel
                }
            }
        }
    }

    // Quick pit presets
    Rectangle {
        width: parent.width
        implicitHeight: presetCol.implicitHeight + Theme.Tokens.xl * 2
        radius: Theme.Tokens.radiusLg
        color: Theme.Tokens.surface
        border.width: 1
        border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

        Column {
            id: presetCol
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.Tokens.xl }
            spacing: Theme.Tokens.md

            Text {
                text: "PIT PRESETS"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                font.weight: Font.Bold
                font.letterSpacing: 1.5
                color: Theme.Tokens.steel
            }

            Row {
                spacing: Theme.Tokens.sm
                Repeater {
                    model: ["Fill to End", "Splash & Go", "Full Service"]
                    delegate: Rectangle {
                        required property string modelData
                        width: presetLabel.implicitWidth + Theme.Tokens.lg * 2
                        height: 36; radius: Theme.Tokens.radiusMd
                        color: presetArea.containsMouse
                               ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.18)
                               : Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.08)
                        border.width: 1
                        border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.20)
                        Text {
                            id: presetLabel; anchors.centerIn: parent
                            text: modelData
                            font.family: Theme.Typography.bodyFamily
                            font.pixelSize: Theme.Typography.captionSize
                            font.weight: Font.DemiBold
                            color: Theme.Tokens.pitOrange
                        }
                        MouseArea { id: presetArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor }
                    }
                }
            }
        }
    }
}
```

- [ ] **Step 5: Add Sprint LIVE tab content**

A simplified live race view:

```qml
Column {
    visible: root.activeTabId === "live"
    width: parent.width
    spacing: Theme.Tokens.xl

    // Fuel countdown card
    Rectangle {
        width: parent.width
        implicitHeight: liveCol.implicitHeight + Theme.Tokens.xl * 2
        radius: Theme.Tokens.radiusLg
        color: Theme.Tokens.surface
        border.width: 1
        border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

        Column {
            id: liveCol
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.Tokens.xl }
            spacing: Theme.Tokens.md

            Text {
                text: "RACE STATUS"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                font.weight: Font.Bold; font.letterSpacing: 1.5
                color: Theme.Tokens.steel
            }

            // Fuel remaining
            Text {
                text: {
                    var cap = typeof overlayVM !== "undefined" && overlayVM ? overlayVM.fuelLevel : 0
                    return cap > 0 ? cap.toFixed(1) + " L remaining" : "Waiting for data..."
                }
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 22; font.weight: Font.Bold
                color: Theme.Tokens.chalk
            }

            // Laps remaining estimate
            Text {
                text: {
                    var laps = typeof overlayVM !== "undefined" && overlayVM ? overlayVM.fuelLapsLeft : 0
                    if (laps > 0) return "~" + laps.toFixed(1) + " laps of fuel"
                    return ""
                }
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.bodySize
                color: Theme.Tokens.steel
            }

            // Alerts from strategy plan
            Repeater {
                model: strategyVM ? strategyVM.alerts : []
                delegate: Rectangle {
                    required property var modelData
                    width: parent.width
                    height: alertText.implicitHeight + Theme.Tokens.md * 2
                    radius: Theme.Tokens.radiusSm
                    color: modelData.severity === "critical"
                           ? Theme.Tokens.subtle(Theme.Tokens.safetyRed, 0.12)
                           : Theme.Tokens.subtle(Theme.Tokens.marshalYellow, 0.08)
                    Text {
                        id: alertText
                        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: Theme.Tokens.md }
                        text: modelData.message
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: Theme.Typography.captionSize
                        font.weight: Font.Bold
                        color: modelData.severity === "critical"
                               ? Theme.Tokens.safetyRed
                               : Theme.Tokens.marshalYellow
                        wrapMode: Text.Wrap
                    }
                }
            }
        }
    }
}
```

- [ ] **Step 6: Add tests for StrategyViewModel mode-aware tabs**

In `tests/test_strategy_vm.py`:

```python
def test_vm_tabs_for_sprint_mode(tmp_path):
    store = StintStore(tmp_path / "stints.json")
    vm = StrategyViewModel(store=store)
    vm.set_mode("sprint")
    tabs = vm.tabsForMode
    assert len(tabs) == 2
    assert tabs[0]["id"] == "setup"
    assert tabs[1]["id"] == "live"


def test_vm_tabs_for_endurance_mode(tmp_path):
    store = StintStore(tmp_path / "stints.json")
    vm = StrategyViewModel(store=store)
    vm.set_mode("endurance")
    tabs = vm.tabsForMode
    assert len(tabs) == 3
    assert tabs[0]["id"] == "practice"
```

- [ ] **Step 7: Run tests**

Run: `.venv/Scripts/python -m pytest tests/test_strategy_vm.py tests/test_mode_vm.py tests/test_mode_detector.py -v`

- [ ] **Step 8: Commit**

```bash
git add src/lap_coach_logger/qml/Pages/StrategyPage.qml src/lap_coach_logger/viewmodels/strategy_vm.py src/lap_coach_logger/qml_bootstrap.py tests/test_strategy_vm.py
git commit -m "feat: mode-aware strategy tabs with Sprint setup+live view"
```

---

## Task 5: Mode-Aware Overlay Defaults

**Files:**
- Modify: `src/lap_coach_logger/viewmodels/overlay_vm.py`

- [ ] **Step 1: Add mode-aware overlay defaults**

Add a method that returns which overlays should be enabled for each mode:

```python
_MODE_OVERLAY_DEFAULTS: dict[str, set[str]] = {
    "sprint": {"relative", "radar", "fuel", "standings", "track_map"},
    "endurance": {"relative", "radar", "fuel", "standings", "track_map", "race_strategy", "tire_life", "session_timer"},
    "coaching": {"delta_time", "inputs", "coaching", "sector_bars"},
    "data": {"relative", "radar", "fuel", "track_map"},
}
```

Add a method:
```python
def apply_mode_defaults(self, mode: str) -> None:
    defaults = _MODE_OVERLAY_DEFAULTS.get(mode, set())
    for widget_id in self._widget_settings:
        self._widget_settings[widget_id]["enabled"] = widget_id in defaults
    self.settingsChanged.emit()
```

Wire this: when mode changes, call `overlay_vm.apply_mode_defaults(mode)`.

- [ ] **Step 2: Wire mode changes to overlay defaults in qml_bootstrap.py**

```python
mode_vm.modeChanged.connect(lambda: overlay_vm.apply_mode_defaults(mode_vm.activeMode))
```

- [ ] **Step 3: Commit**

```bash
git add src/lap_coach_logger/viewmodels/overlay_vm.py src/lap_coach_logger/qml_bootstrap.py
git commit -m "feat: mode-aware overlay defaults (minimal HUD for sprint, coaching overlays for practice)"
```

---

## Task 6: Final Integration Test

**Files:** All

- [ ] **Step 1: Run full test suite**

Run: `.venv/Scripts/python -m pytest tests/ -q --tb=short --ignore=tests/test_desktop_workspaces.py --ignore=tests/test_ghost_widget.py --ignore=tests/test_overlay_browser_frontend.py --ignore=tests/test_overlay_window_manager.py`
Expected: ALL PASS

- [ ] **Step 2: Launch app and verify**

Run: `start "" .venv/Scripts/pythonw.exe -m lap_coach_logger`

Verify:
1. Mode badge in nav bar shows "SPRINT" by default
2. Strategy page shows Setup + Live tabs in sprint mode
3. Setup tab has fuel calculator + pit presets
4. Can switch mode via nav badge or Strategy page

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: mode system complete — Sprint/Endurance/Coaching/Data with auto-detection"
```
