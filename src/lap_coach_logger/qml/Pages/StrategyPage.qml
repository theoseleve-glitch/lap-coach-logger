import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "../Theme" as Theme

Item {
    id: root

    // Compound color helper
    function compoundColor(compound) {
        switch (compound.toLowerCase()) {
        case "soft":    return "#dc2626"
        case "medium":  return "#eab308"
        case "hard":    return "#e5e5e5"
        case "wet":     return "#3b82f6"
        case "inter":   return "#22c55e"
        default:        return Theme.Tokens.steel
        }
    }

    function confidenceBadgeColor(confidence) {
        switch (confidence) {
        case "high":   return Theme.Tokens.acidGreen
        case "medium": return Theme.Tokens.marshalYellow
        default:       return Theme.Tokens.steel
        }
    }

    function formatTime(seconds) {
        if (seconds <= 0) return "--:--"
        var m = Math.floor(seconds / 60)
        var s = (seconds % 60).toFixed(1)
        return m + ":" + (s < 10 ? "0" : "") + s
    }

    ScrollView {
        anchors.fill: parent
        clip: true
        contentWidth: availableWidth

        Rectangle {
            width: parent.width
            height: Math.max(contentCol.implicitHeight + Theme.Tokens.xxl * 2, root.height)
            gradient: Gradient {
                GradientStop { position: 0.0; color: Theme.Tokens.void_ }
                GradientStop { position: 0.5; color: Theme.Tokens.surface }
                GradientStop { position: 1.0; color: "#030405" }
            }

            Column {
                id: contentCol
                anchors {
                    left: parent.left
                    right: parent.right
                    top: parent.top
                    margins: Theme.Tokens.xxl
                }
                spacing: Theme.Tokens.xl

                // ================================================================
                // 1. HEADER
                // ================================================================
                RowLayout {
                    width: parent.width
                    spacing: Theme.Tokens.lg

                    Column {
                        Layout.fillWidth: true
                        spacing: Theme.Tokens.xs

                        Text {
                            text: "Race Strategy"
                            font.family: Theme.Typography.displayFamily
                            font.pixelSize: 26
                            font.weight: Font.Bold
                            font.letterSpacing: -0.3
                            color: Theme.Tokens.chalk
                        }

                        Text {
                            text: {
                                var t = typeof strategyVM !== "undefined" && strategyVM ? strategyVM.trackName : ""
                                var c = typeof strategyVM !== "undefined" && strategyVM ? strategyVM.carName : ""
                                if (t && c) return t + " \u00b7 " + c
                                if (t) return t
                                return "No track/car selected"
                            }
                            font.family: Theme.Typography.bodyFamily
                            font.pixelSize: Theme.Typography.bodySize
                            color: Theme.Tokens.steel
                        }
                    }

                    // Header buttons
                    Row {
                        Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                        spacing: Theme.Tokens.sm

                        // Import Stint
                        Rectangle {
                            width: importLabel.implicitWidth + Theme.Tokens.xl * 2
                            height: 36
                            radius: Theme.Tokens.radiusMd
                            color: importArea.containsMouse
                                   ? Theme.Tokens.subtle(Theme.Tokens.chalk)
                                   : "transparent"
                            border.width: 1
                            border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                            Text {
                                id: importLabel
                                anchors.centerIn: parent
                                text: "Import Stint"
                                font.family: Theme.Typography.bodyFamily
                                font.pixelSize: Theme.Typography.captionSize
                                font.weight: Font.DemiBold
                                color: Theme.Tokens.steel
                            }

                            MouseArea {
                                id: importArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                // Placeholder -- will be wired in Task 8
                            }
                        }

                        // Record Stint
                        Rectangle {
                            width: recordLabel.implicitWidth + Theme.Tokens.xl * 2
                            height: 36
                            radius: Theme.Tokens.radiusMd
                            color: {
                                var recording = typeof strategyVM !== "undefined" && strategyVM && strategyVM.isRecording
                                if (recording) return Theme.Tokens.subtle(Theme.Tokens.safetyRed, 0.15)
                                return recordArea.containsMouse
                                       ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.18)
                                       : Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.10)
                            }
                            border.width: 1
                            border.color: {
                                var recording = typeof strategyVM !== "undefined" && strategyVM && strategyVM.isRecording
                                return recording
                                       ? Theme.Tokens.subtle(Theme.Tokens.safetyRed, 0.30)
                                       : Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.20)
                            }

                            Text {
                                id: recordLabel
                                anchors.centerIn: parent
                                text: {
                                    var recording = typeof strategyVM !== "undefined" && strategyVM && strategyVM.isRecording
                                    return recording ? "Stop Recording" : "Record Stint"
                                }
                                font.family: Theme.Typography.bodyFamily
                                font.pixelSize: Theme.Typography.captionSize
                                font.weight: Font.DemiBold
                                color: {
                                    var recording = typeof strategyVM !== "undefined" && strategyVM && strategyVM.isRecording
                                    return recording ? Theme.Tokens.safetyRed : Theme.Tokens.pitOrange
                                }
                            }

                            MouseArea {
                                id: recordArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (!strategyVM) return
                                    if (strategyVM.isRecording) {
                                        strategyVM.stopRecording()
                                    } else {
                                        strategyVM.startRecording("medium")
                                    }
                                }
                            }
                        }

                        // Auto-Optimize
                        Rectangle {
                            width: optimizeLabel.implicitWidth + Theme.Tokens.xl * 2
                            height: 36
                            radius: Theme.Tokens.radiusMd
                            color: optimizeArea.containsMouse
                                   ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.18)
                                   : Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.10)
                            border.width: 1
                            border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.20)

                            Text {
                                id: optimizeLabel
                                anchors.centerIn: parent
                                text: "Auto-Optimize"
                                font.family: Theme.Typography.bodyFamily
                                font.pixelSize: Theme.Typography.captionSize
                                font.weight: Font.DemiBold
                                color: Theme.Tokens.pitOrange
                            }

                            MouseArea {
                                id: optimizeArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (strategyVM) strategyVM.autoOptimize()
                                }
                            }
                        }
                    }
                }

                // ================================================================
                // Race Mode Toggle (LAP RACE / TIMED RACE)
                // ================================================================
                Row {
                    spacing: Theme.Tokens.sm
                    Layout.alignment: Qt.AlignLeft

                    Rectangle {
                        width: lapBtnText.implicitWidth + Theme.Tokens.xl * 2
                        height: 32
                        radius: Theme.Tokens.radiusSm
                        color: (typeof strategyVM !== "undefined" && strategyVM && strategyVM.raceMode === "laps")
                               ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.20)
                               : "transparent"
                        border.width: 1
                        border.color: (typeof strategyVM !== "undefined" && strategyVM && strategyVM.raceMode === "laps")
                                      ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.40)
                                      : Theme.Tokens.subtle(Theme.Tokens.chalk, 0.10)
                        Text {
                            id: lapBtnText
                            anchors.centerIn: parent
                            text: "LAP RACE"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.microSize
                            font.weight: Font.Bold
                            font.letterSpacing: 1.2
                            color: (typeof strategyVM !== "undefined" && strategyVM && strategyVM.raceMode === "laps")
                                   ? Theme.Tokens.pitOrange
                                   : Theme.Tokens.steel
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (strategyVM) strategyVM.setRaceMode("laps")
                        }
                    }

                    Rectangle {
                        width: timedBtnText.implicitWidth + Theme.Tokens.xl * 2
                        height: 32
                        radius: Theme.Tokens.radiusSm
                        color: (typeof strategyVM !== "undefined" && strategyVM && strategyVM.raceMode === "timed")
                               ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.20)
                               : "transparent"
                        border.width: 1
                        border.color: (typeof strategyVM !== "undefined" && strategyVM && strategyVM.raceMode === "timed")
                                      ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.40)
                                      : Theme.Tokens.subtle(Theme.Tokens.chalk, 0.10)
                        Text {
                            id: timedBtnText
                            anchors.centerIn: parent
                            text: "TIMED RACE"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.microSize
                            font.weight: Font.Bold
                            font.letterSpacing: 1.2
                            color: (typeof strategyVM !== "undefined" && strategyVM && strategyVM.raceMode === "timed")
                                   ? Theme.Tokens.pitOrange
                                   : Theme.Tokens.steel
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (strategyVM) strategyVM.setRaceMode("timed")
                        }
                    }
                }

                // ================================================================
                // Race Parameters
                // Only Total Laps is user-editable — fuel capacity and pit
                // time are auto-detected from telemetry when available.
                // ================================================================
                Rectangle {
                    width: parent.width
                    implicitHeight: paramsRow.implicitHeight + Theme.Tokens.xl * 2
                    radius: Theme.Tokens.radiusLg
                    color: Theme.Tokens.surface
                    border.width: 1
                    border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                    property real vmFuelCap: typeof strategyVM !== "undefined" && strategyVM ? strategyVM.fuelCapacity : 0
                    property real vmPitTime: typeof strategyVM !== "undefined" && strategyVM ? strategyVM.pitTime : 25
                    property bool hasFuelCap: vmFuelCap > 0
                    property bool hasPitTime: vmPitTime !== 25.0

                    RowLayout {
                        id: paramsRow
                        anchors {
                            left: parent.left; right: parent.right; top: parent.top
                            margins: Theme.Tokens.xl
                        }
                        spacing: Theme.Tokens.xl

                        // Total Laps — user-editable (laps mode)
                        Column {
                            visible: !(typeof strategyVM !== "undefined" && strategyVM && strategyVM.raceMode === "timed")
                            spacing: Theme.Tokens.xs
                            Text {
                                text: "RACE LAPS"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Theme.Typography.microWeight
                                font.letterSpacing: Theme.Typography.microSpacing
                                color: Theme.Tokens.pitOrange
                            }
                            Rectangle {
                                width: 100; height: 32
                                radius: Theme.Tokens.radiusSm
                                color: Theme.Tokens.elevated
                                border.width: 1
                                border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.25)
                                TextInput {
                                    anchors { fill: parent; margins: 8 }
                                    color: Theme.Tokens.chalk
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.bodySize
                                    text: typeof strategyVM !== "undefined" && strategyVM ? strategyVM.totalLaps.toString() : "0"
                                    validator: IntValidator { bottom: 0; top: 999 }
                                    onEditingFinished: {
                                        if (strategyVM) strategyVM.setTotalLaps(parseInt(text) || 0)
                                    }
                                }
                            }
                        }

                        // Race Duration — user-editable (timed mode)
                        Column {
                            visible: (typeof strategyVM !== "undefined" && strategyVM && strategyVM.raceMode === "timed")
                            spacing: Theme.Tokens.xs
                            Text {
                                text: "RACE DURATION (HRS)"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Theme.Typography.microWeight
                                font.letterSpacing: Theme.Typography.microSpacing
                                color: Theme.Tokens.pitOrange
                            }
                            Rectangle {
                                width: 100; height: 32
                                radius: Theme.Tokens.radiusSm
                                color: Theme.Tokens.elevated
                                border.width: 1
                                border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.25)
                                TextInput {
                                    anchors { fill: parent; margins: 8 }
                                    color: Theme.Tokens.chalk
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.bodySize
                                    text: typeof strategyVM !== "undefined" && strategyVM ? strategyVM.raceDurationHours.toFixed(2) : "0.00"
                                    validator: DoubleValidator { bottom: 0; top: 24; decimals: 2 }
                                    onEditingFinished: {
                                        if (strategyVM) strategyVM.setRaceDurationHours(parseFloat(text) || 0)
                                    }
                                }
                            }
                        }

                        // Fuel Capacity — read-only, auto-detected from sim
                        Column {
                            spacing: Theme.Tokens.xs
                            Row {
                                spacing: 6
                                Text {
                                    text: "FUEL CAPACITY"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.microSize
                                    font.weight: Theme.Typography.microWeight
                                    font.letterSpacing: Theme.Typography.microSpacing
                                    color: Theme.Tokens.steel
                                }
                                Rectangle {
                                    visible: parent.parent.parent.parent.hasFuelCap
                                    width: autoFuelLabel.implicitWidth + 8
                                    height: 14; radius: 3
                                    color: Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.12)
                                    Text {
                                        id: autoFuelLabel
                                        anchors.centerIn: parent
                                        text: "AUTO"
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: 8; font.weight: Font.Bold
                                        color: Theme.Tokens.acidGreen
                                    }
                                }
                            }
                            Rectangle {
                                width: 100; height: 32
                                radius: Theme.Tokens.radiusSm
                                color: Theme.Tokens.elevated
                                border.width: 1
                                border.color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.06)
                                Text {
                                    anchors { fill: parent; margins: 8 }
                                    verticalAlignment: Text.AlignVCenter
                                    text: {
                                        var cap = typeof strategyVM !== "undefined" && strategyVM ? strategyVM.fuelCapacity : 0
                                        return cap > 0 ? cap.toFixed(1) + " L" : "awaiting sim"
                                    }
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.bodySize
                                    color: {
                                        var cap = typeof strategyVM !== "undefined" && strategyVM ? strategyVM.fuelCapacity : 0
                                        return cap > 0 ? Theme.Tokens.chalk : Theme.Tokens.subtle(Theme.Tokens.steel, 0.5)
                                    }
                                }
                            }
                        }

                        // Pit Time — read-only, measured from actual pit stops
                        Column {
                            spacing: Theme.Tokens.xs
                            Row {
                                spacing: 6
                                Text {
                                    text: "PIT TIME"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.microSize
                                    font.weight: Theme.Typography.microWeight
                                    font.letterSpacing: Theme.Typography.microSpacing
                                    color: Theme.Tokens.steel
                                }
                                Rectangle {
                                    visible: parent.parent.parent.parent.hasPitTime
                                    width: measuredLabel.implicitWidth + 8
                                    height: 14; radius: 3
                                    color: Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.12)
                                    Text {
                                        id: measuredLabel
                                        anchors.centerIn: parent
                                        text: "MEASURED"
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: 8; font.weight: Font.Bold
                                        color: Theme.Tokens.acidGreen
                                    }
                                }
                            }
                            Rectangle {
                                width: 100; height: 32
                                radius: Theme.Tokens.radiusSm
                                color: Theme.Tokens.elevated
                                border.width: 1
                                border.color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.06)
                                Text {
                                    anchors { fill: parent; margins: 8 }
                                    verticalAlignment: Text.AlignVCenter
                                    text: {
                                        var pt = typeof strategyVM !== "undefined" && strategyVM ? strategyVM.pitTime : 25
                                        return pt.toFixed(1) + " s"
                                    }
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.bodySize
                                    color: Theme.Tokens.chalk
                                }
                            }
                        }

                        Item { Layout.fillWidth: true }
                    }
                }

                // ================================================================
                // 2. COMPOUND PROFILES CARD
                // ================================================================
                Rectangle {
                    width: parent.width
                    implicitHeight: profilesCol.implicitHeight + Theme.Tokens.xl * 2
                    radius: Theme.Tokens.radiusLg
                    color: Theme.Tokens.surface
                    border.width: 1
                    border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                    Column {
                        id: profilesCol
                        anchors {
                            left: parent.left; right: parent.right; top: parent.top
                            margins: Theme.Tokens.xl
                        }
                        spacing: Theme.Tokens.md

                        Text {
                            text: "COMPOUND PROFILES"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.microSize
                            font.weight: Theme.Typography.microWeight
                            font.letterSpacing: Theme.Typography.microSpacing
                            color: Theme.Tokens.steel
                        }

                        // Empty state
                        Text {
                            visible: !strategyVM || strategyVM.compoundProfiles.length === 0
                            text: "No compound data yet. Record or import stints to build profiles."
                            font.family: Theme.Typography.bodyFamily
                            font.pixelSize: Theme.Typography.captionSize
                            color: Qt.rgba(Theme.Tokens.steel.r, Theme.Tokens.steel.g,
                                           Theme.Tokens.steel.b, 0.6)
                        }

                        // Profile rows
                        Repeater {
                            model: typeof strategyVM !== "undefined" && strategyVM ? strategyVM.compoundProfiles : []

                            Rectangle {
                                required property var modelData
                                width: profilesCol.width
                                height: 40
                                radius: Theme.Tokens.radiusSm
                                color: profileRowArea.containsMouse
                                       ? Theme.Tokens.subtle(Theme.Tokens.chalk)
                                       : "transparent"

                                MouseArea {
                                    id: profileRowArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                }

                                RowLayout {
                                    anchors { fill: parent; leftMargin: Theme.Tokens.sm; rightMargin: Theme.Tokens.sm }
                                    spacing: Theme.Tokens.md

                                    // Compound dot
                                    Rectangle {
                                        width: 10; height: 10; radius: 5
                                        color: root.compoundColor(modelData.compound)
                                    }

                                    // Compound name
                                    Text {
                                        text: modelData.compound.charAt(0).toUpperCase() + modelData.compound.slice(1)
                                        font.family: Theme.Typography.bodyFamily
                                        font.pixelSize: Theme.Typography.bodySize
                                        font.weight: Font.DemiBold
                                        color: Theme.Tokens.chalk
                                        Layout.preferredWidth: 80
                                    }

                                    // Fuel/lap
                                    Column {
                                        spacing: 1
                                        Text {
                                            text: "FUEL/LAP"
                                            font.family: Theme.Typography.monoFamily
                                            font.pixelSize: 9
                                            font.weight: Font.Bold
                                            color: Theme.Tokens.steel
                                        }
                                        Text {
                                            text: modelData.fuel_per_lap.toFixed(2) + " L"
                                            font.family: Theme.Typography.monoFamily
                                            font.pixelSize: Theme.Typography.captionSize
                                            color: Theme.Tokens.chalk
                                        }
                                    }

                                    // Wear/lap
                                    Column {
                                        spacing: 1
                                        Text {
                                            text: "WEAR/LAP"
                                            font.family: Theme.Typography.monoFamily
                                            font.pixelSize: 9
                                            font.weight: Font.Bold
                                            color: Theme.Tokens.steel
                                        }
                                        Text {
                                            text: modelData.wear_per_lap.toFixed(2) + "%"
                                            font.family: Theme.Typography.monoFamily
                                            font.pixelSize: Theme.Typography.captionSize
                                            color: Theme.Tokens.chalk
                                        }
                                    }

                                    // Estimated life
                                    Column {
                                        spacing: 1
                                        Text {
                                            text: "EST. LIFE"
                                            font.family: Theme.Typography.monoFamily
                                            font.pixelSize: 9
                                            font.weight: Font.Bold
                                            color: Theme.Tokens.steel
                                        }
                                        Text {
                                            text: modelData.estimated_life + " laps"
                                            font.family: Theme.Typography.monoFamily
                                            font.pixelSize: Theme.Typography.captionSize
                                            color: Theme.Tokens.chalk
                                        }
                                    }

                                    // Total laps logged
                                    Column {
                                        spacing: 1
                                        Text {
                                            text: "LOGGED"
                                            font.family: Theme.Typography.monoFamily
                                            font.pixelSize: 9
                                            font.weight: Font.Bold
                                            color: Theme.Tokens.steel
                                        }
                                        Text {
                                            text: modelData.total_laps_logged + " laps"
                                            font.family: Theme.Typography.monoFamily
                                            font.pixelSize: Theme.Typography.captionSize
                                            color: Theme.Tokens.chalk
                                        }
                                    }

                                    // Model availability badges
                                    Row {
                                        spacing: 6
                                        visible: typeof strategyVM !== "undefined"
                                                 && strategyVM
                                                 && strategyVM.modelAvailability
                                                 && modelData.compound in strategyVM.modelAvailability
                                        property var avail: (typeof strategyVM !== "undefined"
                                                             && strategyVM
                                                             && strategyVM.modelAvailability)
                                                             ? (strategyVM.modelAvailability[modelData.compound] || ({}))
                                                             : ({})

                                        Rectangle {
                                            visible: parent.avail.thermal === true
                                            width: thermalLbl.implicitWidth + 6; height: 12; radius: 2
                                            color: Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.15)
                                            Text {
                                                id: thermalLbl
                                                anchors.centerIn: parent
                                                text: "THERMAL"
                                                font.family: Theme.Typography.monoFamily
                                                font.pixelSize: 7; font.weight: Font.Bold
                                                color: Theme.Tokens.acidGreen
                                            }
                                        }

                                        Rectangle {
                                            visible: parent.avail.warmup === true
                                            width: warmupLbl.implicitWidth + 6; height: 12; radius: 2
                                            color: Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.15)
                                            Text {
                                                id: warmupLbl
                                                anchors.centerIn: parent
                                                text: "WARMUP"
                                                font.family: Theme.Typography.monoFamily
                                                font.pixelSize: 7; font.weight: Font.Bold
                                                color: Theme.Tokens.acidGreen
                                            }
                                        }

                                        Rectangle {
                                            visible: parent.avail.degradation === true
                                            width: degLbl.implicitWidth + 6; height: 12; radius: 2
                                            color: Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.15)
                                            Text {
                                                id: degLbl
                                                anchors.centerIn: parent
                                                text: "DEG"
                                                font.family: Theme.Typography.monoFamily
                                                font.pixelSize: 7; font.weight: Font.Bold
                                                color: Theme.Tokens.acidGreen
                                            }
                                        }
                                    }

                                    Item { Layout.fillWidth: true }

                                    // Confidence badge
                                    Rectangle {
                                        width: confLabel.implicitWidth + Theme.Tokens.md * 2
                                        height: 22
                                        radius: Theme.Tokens.radiusSm
                                        color: Theme.Tokens.subtle(root.confidenceBadgeColor(modelData.confidence), 0.15)

                                        Text {
                                            id: confLabel
                                            anchors.centerIn: parent
                                            text: modelData.confidence.toUpperCase()
                                            font.family: Theme.Typography.monoFamily
                                            font.pixelSize: 9
                                            font.weight: Font.Bold
                                            font.letterSpacing: 1
                                            color: root.confidenceBadgeColor(modelData.confidence)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // ================================================================
                // 3. RACE PLAN CARD
                // ================================================================
                Rectangle {
                    width: parent.width
                    implicitHeight: planCol.implicitHeight + Theme.Tokens.xl * 2
                    radius: Theme.Tokens.radiusLg
                    color: Theme.Tokens.surface
                    border.width: 1
                    border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                    Column {
                        id: planCol
                        anchors {
                            left: parent.left; right: parent.right; top: parent.top
                            margins: Theme.Tokens.xl
                        }
                        spacing: Theme.Tokens.md

                        Text {
                            text: "RACE PLAN"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.microSize
                            font.weight: Theme.Typography.microWeight
                            font.letterSpacing: Theme.Typography.microSpacing
                            color: Theme.Tokens.steel
                        }

                        // Summary row
                        Row {
                            visible: typeof strategyVM !== "undefined" && strategyVM && strategyVM.racePlan.length > 0
                            spacing: Theme.Tokens.xl

                            Column {
                                spacing: 1
                                Text {
                                    text: "PIT STOPS"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: 9; font.weight: Font.Bold
                                    color: Theme.Tokens.steel
                                }
                                Text {
                                    text: strategyVM ? strategyVM.planNumStops.toString() : "0"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.bodySize
                                    font.weight: Font.Bold
                                    color: Theme.Tokens.chalk
                                }
                            }

                            Column {
                                spacing: 1
                                Text {
                                    text: "TOTAL TIME"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: 9; font.weight: Font.Bold
                                    color: Theme.Tokens.steel
                                }
                                Text {
                                    text: strategyVM ? root.formatTime(strategyVM.planTotalTime) : "--:--"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.bodySize
                                    font.weight: Font.Bold
                                    color: Theme.Tokens.chalk
                                }
                            }

                            Column {
                                spacing: 1
                                Text {
                                    text: "FUEL AT FINISH"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: 9; font.weight: Font.Bold
                                    color: Theme.Tokens.steel
                                }
                                Text {
                                    text: strategyVM ? strategyVM.planFuelAtFinish.toFixed(1) + " L" : "-- L"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.bodySize
                                    font.weight: Font.Bold
                                    color: {
                                        var fuel = strategyVM ? strategyVM.planFuelAtFinish : 0
                                        return fuel < 2 ? Theme.Tokens.safetyRed
                                             : fuel < 5 ? Theme.Tokens.marshalYellow
                                             : Theme.Tokens.acidGreen
                                    }
                                }
                            }
                        }

                        // Timeline bar
                        Rectangle {
                            id: timelineBar
                            visible: typeof strategyVM !== "undefined" && strategyVM && strategyVM.racePlan.length > 0
                            width: planCol.width
                            height: 32
                            radius: Theme.Tokens.radiusSm
                            color: Theme.Tokens.elevated
                            clip: true

                            Row {
                                anchors.fill: parent

                                Repeater {
                                    model: typeof strategyVM !== "undefined" && strategyVM ? strategyVM.racePlan : []

                                    Rectangle {
                                        required property var modelData
                                        required property int index
                                        property int stintLaps: modelData.end_lap - modelData.start_lap + 1
                                        property int totalLaps: typeof strategyVM !== "undefined" && strategyVM ? strategyVM.totalLaps : 1

                                        width: totalLaps > 0
                                               ? (stintLaps / totalLaps) * timelineBar.width
                                               : 0
                                        height: parent.height
                                        color: Theme.Tokens.subtle(root.compoundColor(modelData.compound), 0.35)
                                        border.width: 1
                                        border.color: Theme.Tokens.subtle(root.compoundColor(modelData.compound), 0.5)

                                        Text {
                                            anchors.centerIn: parent
                                            text: modelData.compound.charAt(0).toUpperCase() + " L" + modelData.start_lap + "-" + modelData.end_lap
                                            font.family: Theme.Typography.monoFamily
                                            font.pixelSize: 10
                                            font.weight: Font.Bold
                                            color: Theme.Tokens.chalk
                                            visible: parent.width > 50
                                        }
                                    }
                                }
                            }
                        }

                        // Stint details
                        Repeater {
                            model: typeof strategyVM !== "undefined" && strategyVM ? strategyVM.racePlan : []

                            Rectangle {
                                required property var modelData
                                required property int index
                                width: planCol.width
                                height: 36
                                radius: Theme.Tokens.radiusSm
                                color: stintDetailArea.containsMouse
                                       ? Theme.Tokens.subtle(Theme.Tokens.chalk)
                                       : "transparent"

                                MouseArea {
                                    id: stintDetailArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                }

                                RowLayout {
                                    anchors { fill: parent; leftMargin: Theme.Tokens.sm; rightMargin: Theme.Tokens.sm }
                                    spacing: Theme.Tokens.md

                                    Rectangle {
                                        width: 10; height: 10; radius: 5
                                        color: root.compoundColor(modelData.compound)
                                    }

                                    Text {
                                        text: "Stint " + (index + 1) + ": " + modelData.compound
                                        font.family: Theme.Typography.bodyFamily
                                        font.pixelSize: Theme.Typography.captionSize
                                        font.weight: Font.DemiBold
                                        color: Theme.Tokens.chalk
                                        Layout.preferredWidth: 120
                                    }

                                    Text {
                                        text: "Laps " + modelData.start_lap + "-" + modelData.end_lap
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: Theme.Typography.captionSize
                                        color: Theme.Tokens.steel
                                    }

                                    Text {
                                        visible: index > 0
                                        text: "Pit: +" + modelData.fuel_to_add.toFixed(1) + " L"
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: Theme.Typography.captionSize
                                        color: Theme.Tokens.pitOrange
                                    }

                                    Text {
                                        text: root.formatTime(modelData.estimated_time_s)
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: Theme.Typography.captionSize
                                        color: Theme.Tokens.steel
                                    }

                                    Text {
                                        text: "Fuel: " + modelData.fuel_at_start.toFixed(1) + " L"
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: Theme.Typography.captionSize
                                        color: Theme.Tokens.steel
                                    }

                                    Item { Layout.fillWidth: true }
                                }
                            }
                        }

                        // Empty state
                        Text {
                            visible: !strategyVM || strategyVM.racePlan.length === 0
                            text: "Set race parameters and click Auto-Optimize to generate a race plan."
                            font.family: Theme.Typography.bodyFamily
                            font.pixelSize: Theme.Typography.captionSize
                            color: Qt.rgba(Theme.Tokens.steel.r, Theme.Tokens.steel.g,
                                           Theme.Tokens.steel.b, 0.6)
                        }

                        // Alerts
                        Repeater {
                            model: typeof strategyVM !== "undefined" && strategyVM ? strategyVM.alerts : []

                            Rectangle {
                                required property var modelData
                                width: planCol.width
                                implicitHeight: alertCol.implicitHeight + Theme.Tokens.md * 2
                                radius: Theme.Tokens.radiusSm
                                color: {
                                    if (modelData.severity === "critical") return Theme.Tokens.subtle(Theme.Tokens.safetyRed, 0.10)
                                    if (modelData.severity === "warning") return Theme.Tokens.subtle(Theme.Tokens.marshalYellow, 0.10)
                                    return Theme.Tokens.subtle(Theme.Tokens.steel, 0.08)
                                }

                                Column {
                                    id: alertCol
                                    anchors {
                                        left: parent.left; right: parent.right; top: parent.top
                                        margins: Theme.Tokens.md
                                    }
                                    spacing: 2

                                    Text {
                                        text: modelData.message
                                        font.family: Theme.Typography.bodyFamily
                                        font.pixelSize: Theme.Typography.captionSize
                                        font.weight: Font.DemiBold
                                        color: {
                                            if (modelData.severity === "critical") return Theme.Tokens.safetyRed
                                            if (modelData.severity === "warning") return Theme.Tokens.marshalYellow
                                            return Theme.Tokens.steel
                                        }
                                        width: parent.width
                                        wrapMode: Text.WordWrap
                                    }

                                    Text {
                                        visible: modelData.suggested_action !== ""
                                        text: modelData.suggested_action
                                        font.family: Theme.Typography.bodyFamily
                                        font.pixelSize: Theme.Typography.captionSize
                                        color: Theme.Tokens.steel
                                        width: parent.width
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                        }
                    }
                }

                // ================================================================
                // 4. WEATHER CARD (conditional)
                // ================================================================
                Rectangle {
                    visible: typeof strategyVM !== "undefined" && strategyVM && strategyVM.hasWeatherData
                    width: parent.width
                    implicitHeight: weatherCol.implicitHeight + Theme.Tokens.xl * 2
                    radius: Theme.Tokens.radiusLg
                    color: Theme.Tokens.surface
                    border.width: 1
                    border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                    Column {
                        id: weatherCol
                        anchors {
                            left: parent.left; right: parent.right; top: parent.top
                            margins: Theme.Tokens.xl
                        }
                        spacing: Theme.Tokens.md

                        Text {
                            text: "WEATHER CONDITIONS"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.microSize
                            font.weight: Theme.Typography.microWeight
                            font.letterSpacing: Theme.Typography.microSpacing
                            color: Theme.Tokens.steel
                        }

                        Repeater {
                            model: typeof strategyVM !== "undefined" && strategyVM ? strategyVM.weatherTimeline : []

                            Rectangle {
                                required property var modelData
                                width: weatherCol.width
                                height: 36
                                radius: Theme.Tokens.radiusSm
                                color: "transparent"

                                RowLayout {
                                    anchors { fill: parent; leftMargin: Theme.Tokens.sm; rightMargin: Theme.Tokens.sm }
                                    spacing: Theme.Tokens.md

                                    Text {
                                        text: "Laps " + modelData.start_lap + "-" + modelData.end_lap
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: Theme.Typography.captionSize
                                        color: Theme.Tokens.chalk
                                        Layout.preferredWidth: 90
                                    }

                                    Text {
                                        text: modelData.track_state
                                        font.family: Theme.Typography.bodyFamily
                                        font.pixelSize: Theme.Typography.captionSize
                                        font.weight: Font.DemiBold
                                        color: Theme.Tokens.chalk
                                    }

                                    Text {
                                        text: modelData.track_temp_c.toFixed(0) + "\u00b0C"
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: Theme.Typography.captionSize
                                        color: Theme.Tokens.steel
                                    }

                                    Text {
                                        text: modelData.precipitation
                                        font.family: Theme.Typography.bodyFamily
                                        font.pixelSize: Theme.Typography.captionSize
                                        color: Theme.Tokens.steel
                                    }

                                    Rectangle {
                                        visible: modelData.recommended_compound !== ""
                                        width: recCompLabel.implicitWidth + Theme.Tokens.sm * 2
                                        height: 20
                                        radius: Theme.Tokens.radiusSm
                                        color: Theme.Tokens.subtle(root.compoundColor(modelData.recommended_compound), 0.15)

                                        Text {
                                            id: recCompLabel
                                            anchors.centerIn: parent
                                            text: modelData.recommended_compound
                                            font.family: Theme.Typography.monoFamily
                                            font.pixelSize: 9
                                            font.weight: Font.Bold
                                            color: root.compoundColor(modelData.recommended_compound)
                                        }
                                    }

                                    Item { Layout.fillWidth: true }
                                }
                            }
                        }
                    }
                }

                // ================================================================
                // 5. LOGGED STINTS CARD
                // ================================================================
                Rectangle {
                    width: parent.width
                    implicitHeight: stintsCol.implicitHeight + Theme.Tokens.xl * 2
                    radius: Theme.Tokens.radiusLg
                    color: Theme.Tokens.surface
                    border.width: 1
                    border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                    Column {
                        id: stintsCol
                        anchors {
                            left: parent.left; right: parent.right; top: parent.top
                            margins: Theme.Tokens.xl
                        }
                        spacing: Theme.Tokens.md

                        Text {
                            text: "LOGGED STINTS"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.microSize
                            font.weight: Theme.Typography.microWeight
                            font.letterSpacing: Theme.Typography.microSpacing
                            color: Theme.Tokens.steel
                        }

                        // Header row
                        RowLayout {
                            width: stintsCol.width
                            spacing: Theme.Tokens.sm

                            Text { text: "Source"; Layout.preferredWidth: 120; font.family: Theme.Typography.monoFamily; font.pixelSize: 9; font.weight: Font.Bold; color: Theme.Tokens.steel }
                            Text { text: "Compound"; Layout.preferredWidth: 80; font.family: Theme.Typography.monoFamily; font.pixelSize: 9; font.weight: Font.Bold; color: Theme.Tokens.steel }
                            Text { text: "Laps"; Layout.preferredWidth: 50; font.family: Theme.Typography.monoFamily; font.pixelSize: 9; font.weight: Font.Bold; color: Theme.Tokens.steel }
                            Text { text: "Fuel/Lap"; Layout.preferredWidth: 70; font.family: Theme.Typography.monoFamily; font.pixelSize: 9; font.weight: Font.Bold; color: Theme.Tokens.steel }
                            Text { text: "Wear/Lap"; Layout.preferredWidth: 70; font.family: Theme.Typography.monoFamily; font.pixelSize: 9; font.weight: Font.Bold; color: Theme.Tokens.steel }
                            Text { text: "Grip End"; Layout.preferredWidth: 60; font.family: Theme.Typography.monoFamily; font.pixelSize: 9; font.weight: Font.Bold; color: Theme.Tokens.steel }
                            Text { text: "Temp"; Layout.preferredWidth: 50; font.family: Theme.Typography.monoFamily; font.pixelSize: 9; font.weight: Font.Bold; color: Theme.Tokens.steel }
                            Text { text: "Status"; Layout.preferredWidth: 60; font.family: Theme.Typography.monoFamily; font.pixelSize: 9; font.weight: Font.Bold; color: Theme.Tokens.steel }
                            Item { Layout.fillWidth: true }
                        }

                        // Stint rows
                        Repeater {
                            model: typeof strategyVM !== "undefined" && strategyVM ? strategyVM.stintLog : []

                            Rectangle {
                                required property var modelData
                                width: stintsCol.width
                                height: 34
                                radius: Theme.Tokens.radiusSm
                                color: stintRowArea.containsMouse
                                       ? Theme.Tokens.subtle(Theme.Tokens.chalk)
                                       : "transparent"
                                opacity: modelData.excluded ? 0.5 : 1.0

                                MouseArea {
                                    id: stintRowArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (!strategyVM) return
                                        if (modelData.excluded) {
                                            strategyVM.includeLoggedStint(modelData.id)
                                        } else {
                                            strategyVM.excludeLoggedStint(modelData.id)
                                        }
                                    }
                                }

                                RowLayout {
                                    anchors { fill: parent; leftMargin: Theme.Tokens.sm; rightMargin: Theme.Tokens.sm }
                                    spacing: Theme.Tokens.sm

                                    Text {
                                        text: modelData.source_label || "Manual"
                                        Layout.preferredWidth: 120
                                        font.family: Theme.Typography.bodyFamily
                                        font.pixelSize: Theme.Typography.captionSize
                                        color: Theme.Tokens.chalk
                                        elide: Text.ElideRight
                                    }

                                    Row {
                                        Layout.preferredWidth: 80
                                        spacing: 4
                                        Rectangle {
                                            width: 8; height: 8; radius: 4
                                            anchors.verticalCenter: parent.verticalCenter
                                            color: root.compoundColor(modelData.compound)
                                        }
                                        Text {
                                            text: modelData.compound
                                            font.family: Theme.Typography.bodyFamily
                                            font.pixelSize: Theme.Typography.captionSize
                                            color: Theme.Tokens.chalk
                                        }
                                    }

                                    Text {
                                        text: modelData.lap_count.toString()
                                        Layout.preferredWidth: 50
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: Theme.Typography.captionSize
                                        color: Theme.Tokens.chalk
                                    }

                                    Text {
                                        text: modelData.fuel_per_lap.toFixed(2)
                                        Layout.preferredWidth: 70
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: Theme.Typography.captionSize
                                        color: Theme.Tokens.chalk
                                    }

                                    Text {
                                        text: modelData.wear_per_lap.toFixed(2) + "%"
                                        Layout.preferredWidth: 70
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: Theme.Typography.captionSize
                                        color: Theme.Tokens.chalk
                                    }

                                    Text {
                                        text: modelData.grip_at_end.toFixed(0) + "%"
                                        Layout.preferredWidth: 60
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: Theme.Typography.captionSize
                                        color: Theme.Tokens.chalk
                                    }

                                    Text {
                                        text: modelData.track_temp_c.toFixed(0) + "\u00b0C"
                                        Layout.preferredWidth: 50
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: Theme.Typography.captionSize
                                        color: Theme.Tokens.steel
                                    }

                                    // Excluded badge
                                    Rectangle {
                                        Layout.preferredWidth: 60
                                        width: exclLabel.implicitWidth + Theme.Tokens.sm * 2
                                        height: 20
                                        radius: Theme.Tokens.radiusSm
                                        color: modelData.excluded
                                               ? Theme.Tokens.subtle(Theme.Tokens.safetyRed, 0.12)
                                               : Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.12)

                                        Text {
                                            id: exclLabel
                                            anchors.centerIn: parent
                                            text: modelData.excluded ? "EXCL" : "ACTIVE"
                                            font.family: Theme.Typography.monoFamily
                                            font.pixelSize: 9
                                            font.weight: Font.Bold
                                            color: modelData.excluded ? Theme.Tokens.safetyRed : Theme.Tokens.acidGreen
                                        }
                                    }

                                    Item { Layout.fillWidth: true }
                                }
                            }
                        }

                        // Empty state
                        Text {
                            visible: !strategyVM || strategyVM.stintLog.length === 0
                            text: "No stints logged for this track/car combination."
                            font.family: Theme.Typography.bodyFamily
                            font.pixelSize: Theme.Typography.captionSize
                            color: Qt.rgba(Theme.Tokens.steel.r, Theme.Tokens.steel.g,
                                           Theme.Tokens.steel.b, 0.6)
                        }
                    }
                }
            }
        }
    }
}
