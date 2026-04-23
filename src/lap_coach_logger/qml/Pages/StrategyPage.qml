import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "../Theme" as Theme

Item {
    id: root

    property string activeTabId: strategyVM ? strategyVM.activeTab : "practice"

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
                // HEADER (always visible)
                // ================================================================
                Column {
                    width: parent.width
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

                // ================================================================
                // TAB BAR
                // ================================================================
                Row {
                    width: parent.width
                    spacing: 0

                    Repeater {
                        model: strategyVM ? strategyVM.tabsForMode : []

                        Rectangle {
                            required property var modelData
                            required property int index
                            width: tabLabel.implicitWidth + Theme.Tokens.xl * 2
                            height: 40
                            color: "transparent"

                            Text {
                                id: tabLabel
                                anchors.centerIn: parent
                                text: modelData.label
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.captionSize
                                font.weight: Font.Bold
                                font.letterSpacing: 1.2
                                color: root.activeTabId === modelData.id
                                       ? Theme.Tokens.pitOrange
                                       : Theme.Tokens.steel
                            }

                            // Orange underline for active tab
                            Rectangle {
                                anchors.bottom: parent.bottom
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: parent.width - Theme.Tokens.sm * 2
                                height: 2
                                radius: 1
                                color: Theme.Tokens.pitOrange
                                visible: root.activeTabId === modelData.id
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.activeTabId = modelData.id
                            }
                        }
                    }

                    // Divider line under tabs
                    Item { width: 1; height: 1 }
                }

                // Tab divider line
                Rectangle {
                    width: parent.width
                    height: 1
                    color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.10)
                }

                // ================================================================
                // PRACTICE TAB
                // ================================================================
                Column {
                    id: practiceTab
                    visible: root.activeTabId === "practice"
                    width: parent.width
                    spacing: Theme.Tokens.xl

                    // ---- Readiness Dashboard card ----
                    Rectangle {
                        width: parent.width
                        implicitHeight: readinessCol.implicitHeight + Theme.Tokens.xl * 2
                        radius: Theme.Tokens.radiusLg
                        color: Theme.Tokens.surface
                        border.width: 1
                        border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                        Column {
                            id: readinessCol
                            anchors {
                                left: parent.left; right: parent.right; top: parent.top
                                margins: Theme.Tokens.xl
                            }
                            spacing: Theme.Tokens.md

                            Text {
                                text: "COMPOUND READINESS"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Theme.Typography.microWeight
                                font.letterSpacing: Theme.Typography.microSpacing
                                color: Theme.Tokens.steel
                            }

                            // Empty state
                            Text {
                                visible: !strategyVM || Object.keys(strategyVM.readiness).length === 0
                                text: "No compounds logged yet"
                                font.family: Theme.Typography.bodyFamily
                                font.pixelSize: Theme.Typography.captionSize
                                color: Qt.rgba(Theme.Tokens.steel.r, Theme.Tokens.steel.g,
                                               Theme.Tokens.steel.b, 0.6)
                            }

                            // Readiness rows
                            Repeater {
                                model: typeof strategyVM !== "undefined" && strategyVM
                                       ? Object.keys(strategyVM.readiness) : []

                                Column {
                                    required property string modelData
                                    property var info: strategyVM ? strategyVM.readiness[modelData] : ({})
                                    width: readinessCol.width
                                    spacing: Theme.Tokens.xs

                                    RowLayout {
                                        width: parent.width
                                        spacing: Theme.Tokens.md

                                        // Compound dot
                                        Rectangle {
                                            width: 10; height: 10; radius: 5
                                            color: root.compoundColor(modelData)
                                        }

                                        // Compound name
                                        Text {
                                            text: modelData.charAt(0).toUpperCase() + modelData.slice(1)
                                            font.family: Theme.Typography.bodyFamily
                                            font.pixelSize: Theme.Typography.bodySize
                                            font.weight: Font.DemiBold
                                            color: Theme.Tokens.chalk
                                            Layout.preferredWidth: 80
                                        }

                                        // Progress bar
                                        Rectangle {
                                            Layout.fillWidth: true
                                            height: 8
                                            radius: 4
                                            color: Theme.Tokens.elevated

                                            Rectangle {
                                                width: parent.width * Math.min((info.readiness_pct || 0) / 100.0, 1.0)
                                                height: parent.height
                                                radius: parent.radius
                                                color: (info.readiness_pct || 0) >= 80
                                                       ? Theme.Tokens.acidGreen
                                                       : (info.readiness_pct || 0) >= 50
                                                         ? Theme.Tokens.pitOrange
                                                         : Theme.Tokens.steel
                                            }
                                        }

                                        // Readiness percent
                                        Text {
                                            text: (info.readiness_pct || 0) + "% ready"
                                            font.family: Theme.Typography.monoFamily
                                            font.pixelSize: Theme.Typography.captionSize
                                            color: Theme.Tokens.chalk
                                            Layout.preferredWidth: 80
                                        }

                                        // Model badges
                                        Row {
                                            spacing: 4

                                            Rectangle {
                                                visible: info.thermal === true
                                                width: thermalBadge.implicitWidth + 6
                                                height: 14; radius: 3
                                                color: Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.15)
                                                Text {
                                                    id: thermalBadge
                                                    anchors.centerIn: parent
                                                    text: "THERMAL"
                                                    font.family: Theme.Typography.monoFamily
                                                    font.pixelSize: 7; font.weight: Font.Bold
                                                    color: Theme.Tokens.acidGreen
                                                }
                                            }

                                            Rectangle {
                                                visible: info.warmup === true
                                                width: warmupBadge.implicitWidth + 6
                                                height: 14; radius: 3
                                                color: Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.15)
                                                Text {
                                                    id: warmupBadge
                                                    anchors.centerIn: parent
                                                    text: "WARMUP"
                                                    font.family: Theme.Typography.monoFamily
                                                    font.pixelSize: 7; font.weight: Font.Bold
                                                    color: Theme.Tokens.acidGreen
                                                }
                                            }

                                            Rectangle {
                                                visible: info.degradation === true
                                                width: degBadge.implicitWidth + 6
                                                height: 14; radius: 3
                                                color: Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.15)
                                                Text {
                                                    id: degBadge
                                                    anchors.centerIn: parent
                                                    text: "DEG"
                                                    font.family: Theme.Typography.monoFamily
                                                    font.pixelSize: 7; font.weight: Font.Bold
                                                    color: Theme.Tokens.acidGreen
                                                }
                                            }
                                        }
                                    }

                                    // Laps needed hint
                                    Text {
                                        visible: (info.laps_needed_for_high || 0) > 0
                                        text: "Need: " + (info.laps_needed_for_high || 0) + " more laps"
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: Theme.Typography.microSize
                                        color: Theme.Tokens.steel
                                        leftPadding: 22
                                    }
                                }
                            }
                        }
                    }

                    // ---- Nudges card ----
                    Rectangle {
                        width: parent.width
                        implicitHeight: nudgesCol.implicitHeight + Theme.Tokens.xl * 2
                        radius: Theme.Tokens.radiusLg
                        color: Theme.Tokens.surface
                        border.width: 1
                        border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                        Column {
                            id: nudgesCol
                            anchors {
                                left: parent.left; right: parent.right; top: parent.top
                                margins: Theme.Tokens.xl
                            }
                            spacing: Theme.Tokens.md

                            Text {
                                text: "SUGGESTED NEXT STEPS"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Theme.Typography.microWeight
                                font.letterSpacing: Theme.Typography.microSpacing
                                color: Theme.Tokens.steel
                            }

                            // Empty state
                            Text {
                                visible: !strategyVM || strategyVM.nudges.length === 0
                                text: "Drive some laps to get started"
                                font.family: Theme.Typography.bodyFamily
                                font.pixelSize: Theme.Typography.captionSize
                                color: Qt.rgba(Theme.Tokens.steel.r, Theme.Tokens.steel.g,
                                               Theme.Tokens.steel.b, 0.6)
                            }

                            Repeater {
                                model: typeof strategyVM !== "undefined" && strategyVM
                                       ? strategyVM.nudges : []

                                Text {
                                    required property string modelData
                                    text: "\u2192 " + modelData
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.captionSize
                                    color: Theme.Tokens.steel
                                    width: nudgesCol.width
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }
                    }

                    // ---- "Build Strategy" button ----
                    Rectangle {
                        visible: {
                            if (!strategyVM) return false
                            var r = strategyVM.readiness
                            var keys = Object.keys(r)
                            for (var i = 0; i < keys.length; i++) {
                                if ((r[keys[i]].readiness_pct || 0) >= 50) return true
                            }
                            return false
                        }
                        width: buildBtnLabel.implicitWidth + Theme.Tokens.xl * 2
                        height: 40
                        radius: Theme.Tokens.radiusMd
                        color: buildBtnArea.containsMouse
                               ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.22)
                               : Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.12)
                        border.width: 1
                        border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.30)

                        Text {
                            id: buildBtnLabel
                            anchors.centerIn: parent
                            text: "Build Strategy \u2192"
                            font.family: Theme.Typography.bodyFamily
                            font.pixelSize: Theme.Typography.bodySize
                            font.weight: Font.DemiBold
                            color: Theme.Tokens.pitOrange
                        }

                        MouseArea {
                            id: buildBtnArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.activeTabId = "build"
                        }
                    }
                }

                // ================================================================
                // BUILD TAB
                // ================================================================
                Column {
                    id: buildTab
                    visible: root.activeTabId === "build"
                    width: parent.width
                    spacing: Theme.Tokens.xl

                    // ---- Race Mode Toggle (LAP RACE / TIMED RACE) ----
                    Row {
                        spacing: Theme.Tokens.sm

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

                    // ---- Race Parameters card ----
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

                            // Total Laps (laps mode)
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

                            // Race Duration (timed mode)
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

                            // Fuel Capacity (read-only, auto-detected)
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

                            // Pit Time (read-only, measured)
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

                    // ---- Compound Profiles card ----
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

                    // ---- "Process Strategy" button ----
                    Rectangle {
                        width: processLabel.implicitWidth + Theme.Tokens.xl * 2
                        height: 40
                        radius: Theme.Tokens.radiusMd
                        color: processArea.containsMouse
                               ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.22)
                               : Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.12)
                        border.width: 1
                        border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.30)

                        Text {
                            id: processLabel
                            anchors.centerIn: parent
                            text: "Process Strategy"
                            font.family: Theme.Typography.bodyFamily
                            font.pixelSize: Theme.Typography.bodySize
                            font.weight: Font.DemiBold
                            color: Theme.Tokens.pitOrange
                        }

                        MouseArea {
                            id: processArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (strategyVM) strategyVM.autoOptimize()
                                root.activeTabId = "raceplan"
                            }
                        }
                    }
                }

                // ================================================================
                // RACE PLAN TAB
                // ================================================================
                Column {
                    id: raceplanTab
                    visible: root.activeTabId === "raceplan"
                    width: parent.width
                    spacing: Theme.Tokens.xl

                    // ---- Race Statistics card (NEW) ----
                    Rectangle {
                        width: parent.width
                        implicitHeight: statsCol.implicitHeight + Theme.Tokens.xl * 2
                        radius: Theme.Tokens.radiusLg
                        color: Theme.Tokens.surface
                        border.width: 1
                        border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                        Column {
                            id: statsCol
                            anchors {
                                left: parent.left; right: parent.right; top: parent.top
                                margins: Theme.Tokens.xl
                            }
                            spacing: Theme.Tokens.md

                            Text {
                                text: "RACE STATISTICS"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Theme.Typography.microWeight
                                font.letterSpacing: Theme.Typography.microSpacing
                                color: Theme.Tokens.steel
                            }

                            // Empty state
                            Text {
                                visible: !strategyVM || Object.keys(strategyVM.raceStatistics).length === 0
                                text: "Process a strategy first"
                                font.family: Theme.Typography.bodyFamily
                                font.pixelSize: Theme.Typography.captionSize
                                color: Qt.rgba(Theme.Tokens.steel.r, Theme.Tokens.steel.g,
                                               Theme.Tokens.steel.b, 0.6)
                            }

                            // Statistics rows
                            Column {
                                visible: strategyVM && Object.keys(strategyVM.raceStatistics).length > 0
                                width: statsCol.width
                                spacing: Theme.Tokens.xs

                                property var stats: strategyVM ? strategyVM.raceStatistics : ({})

                                Repeater {
                                    model: [
                                        { key: "estimated_laps",       label: "Estimated laps",       fmt: "int" },
                                        { key: "estimated_race_time",  label: "Estimated race time",  fmt: "time" },
                                        { key: "pit_stops",            label: "Pit stops",            fmt: "int" },
                                        { key: "qualifying_target",    label: "Qualifying target",    fmt: "time" },
                                        { key: "race_pace_target",     label: "Race pace target",     fmt: "time" },
                                        { key: "best_case",            label: "Best case",            fmt: "time" },
                                        { key: "expected",             label: "Expected",             fmt: "time" },
                                        { key: "worst_case",           label: "Worst case",           fmt: "time" },
                                        { key: "fuel_margin",          label: "Fuel margin",          fmt: "fuel" },
                                        { key: "grip_at_finish",       label: "Grip at finish",       fmt: "pct" }
                                    ]

                                    RowLayout {
                                        required property var modelData
                                        width: statsCol.width
                                        height: 28
                                        spacing: Theme.Tokens.md

                                        Text {
                                            text: modelData.label
                                            font.family: Theme.Typography.bodyFamily
                                            font.pixelSize: Theme.Typography.captionSize
                                            color: Theme.Tokens.steel
                                            Layout.preferredWidth: 160
                                        }

                                        Text {
                                            property var stats: strategyVM ? strategyVM.raceStatistics : ({})
                                            property var val: stats[modelData.key]
                                            text: {
                                                if (val === undefined || val === null) return "--"
                                                if (modelData.fmt === "time") return root.formatTime(val)
                                                if (modelData.fmt === "fuel") return val.toFixed(1) + " L"
                                                if (modelData.fmt === "pct") return val.toFixed(0) + "%"
                                                return val.toString()
                                            }
                                            font.family: Theme.Typography.monoFamily
                                            font.pixelSize: Theme.Typography.bodySize
                                            font.weight: Font.DemiBold
                                            color: Theme.Tokens.chalk
                                        }

                                        Item { Layout.fillWidth: true }
                                    }
                                }
                            }
                        }
                    }

                    // ---- Race Plan card (timeline + stint details + alerts) ----
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
                                text: "Set race parameters and click Process Strategy to generate a race plan."
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

                    // ---- Weather card (conditional) ----
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

                    // ---- Logged Stints card ----
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

                // ================================================================
                // SPRINT SETUP TAB
                // ================================================================
                Column {
                    visible: root.activeTabId === "setup"
                    width: parent.width
                    spacing: Theme.Tokens.xl

                    // ---- Fuel Calculator card ----
                    Rectangle {
                        width: parent.width
                        implicitHeight: fuelCalcCol.implicitHeight + Theme.Tokens.xl * 2
                        radius: Theme.Tokens.radiusLg
                        color: Theme.Tokens.surface
                        border.width: 1
                        border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                        Column {
                            id: fuelCalcCol
                            anchors {
                                left: parent.left; right: parent.right; top: parent.top
                                margins: Theme.Tokens.xl
                            }
                            spacing: Theme.Tokens.md

                            Text {
                                text: "FUEL CALCULATOR"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Theme.Typography.microWeight
                                font.letterSpacing: Theme.Typography.microSpacing
                                color: Theme.Tokens.steel
                            }

                            // Race laps input
                            RowLayout {
                                width: parent.width
                                spacing: Theme.Tokens.md

                                Text {
                                    text: "Race laps"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.captionSize
                                    color: Theme.Tokens.chalk
                                    Layout.preferredWidth: 120
                                }

                                Rectangle {
                                    Layout.preferredWidth: 80
                                    height: 32
                                    radius: Theme.Tokens.radiusSm
                                    color: Theme.Tokens.elevated
                                    border.width: 1
                                    border.color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.15)

                                    TextInput {
                                        id: sprintLapsInput
                                        anchors.fill: parent
                                        anchors.margins: Theme.Tokens.xs
                                        text: strategyVM ? strategyVM.totalLaps.toString() : "0"
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: Theme.Typography.bodySize
                                        color: Theme.Tokens.chalk
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                        validator: IntValidator { bottom: 0; top: 999 }
                                        onEditingFinished: {
                                            if (strategyVM) strategyVM.setTotalLaps(parseInt(text) || 0)
                                        }
                                    }
                                }
                            }

                            // Computed fuel needed
                            RowLayout {
                                width: parent.width
                                spacing: Theme.Tokens.md

                                Text {
                                    text: "Fuel needed"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.captionSize
                                    color: Theme.Tokens.chalk
                                    Layout.preferredWidth: 120
                                }

                                Text {
                                    property var profiles: strategyVM ? strategyVM.compoundProfiles : []
                                    property real fuelPerLap: profiles.length > 0 ? (profiles[0].fuel_per_lap || 0) : 0
                                    property int laps: strategyVM ? strategyVM.totalLaps : 0
                                    text: fuelPerLap > 0 ? (laps * fuelPerLap).toFixed(1) + " L" : "--"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.bodySize
                                    font.weight: Font.Bold
                                    color: Theme.Tokens.pitOrange
                                }
                            }

                            // Fuel capacity (read-only)
                            RowLayout {
                                width: parent.width
                                spacing: Theme.Tokens.md

                                Text {
                                    text: "Fuel capacity"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.captionSize
                                    color: Theme.Tokens.chalk
                                    Layout.preferredWidth: 120
                                }

                                Text {
                                    text: strategyVM ? strategyVM.fuelCapacity.toFixed(1) + " L" : "--"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.bodySize
                                    color: Theme.Tokens.steel
                                }
                            }
                        }
                    }

                    // ---- Pit Presets card ----
                    Rectangle {
                        width: parent.width
                        implicitHeight: pitPresetsCol.implicitHeight + Theme.Tokens.xl * 2
                        radius: Theme.Tokens.radiusLg
                        color: Theme.Tokens.surface
                        border.width: 1
                        border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                        Column {
                            id: pitPresetsCol
                            anchors {
                                left: parent.left; right: parent.right; top: parent.top
                                margins: Theme.Tokens.xl
                            }
                            spacing: Theme.Tokens.md

                            Text {
                                text: "PIT PRESETS"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Theme.Typography.microWeight
                                font.letterSpacing: Theme.Typography.microSpacing
                                color: Theme.Tokens.steel
                            }

                            Row {
                                spacing: Theme.Tokens.md

                                Repeater {
                                    model: [
                                        { label: "Fill to End" },
                                        { label: "Splash & Go" },
                                        { label: "Full Service" }
                                    ]

                                    Rectangle {
                                        required property var modelData
                                        width: presetLabel.implicitWidth + Theme.Tokens.xl * 2
                                        height: 36
                                        radius: Theme.Tokens.radiusMd
                                        color: presetArea.containsMouse
                                               ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.22)
                                               : Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.12)
                                        border.width: 1
                                        border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.30)

                                        Text {
                                            id: presetLabel
                                            anchors.centerIn: parent
                                            text: modelData.label
                                            font.family: Theme.Typography.monoFamily
                                            font.pixelSize: Theme.Typography.captionSize
                                            font.weight: Font.DemiBold
                                            color: Theme.Tokens.pitOrange
                                        }

                                        MouseArea {
                                            id: presetArea
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: { /* placeholder */ }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // ================================================================
                // SPRINT LIVE TAB
                // ================================================================
                Column {
                    visible: root.activeTabId === "live"
                    width: parent.width
                    spacing: Theme.Tokens.xl

                    // ---- Race Status card ----
                    Rectangle {
                        width: parent.width
                        implicitHeight: raceStatusCol.implicitHeight + Theme.Tokens.xl * 2
                        radius: Theme.Tokens.radiusLg
                        color: Theme.Tokens.surface
                        border.width: 1
                        border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                        Column {
                            id: raceStatusCol
                            anchors {
                                left: parent.left; right: parent.right; top: parent.top
                                margins: Theme.Tokens.xl
                            }
                            spacing: Theme.Tokens.md

                            Text {
                                text: "RACE STATUS"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Theme.Typography.microWeight
                                font.letterSpacing: Theme.Typography.microSpacing
                                color: Theme.Tokens.steel
                            }

                            // Fuel remaining (large)
                            Column {
                                width: parent.width
                                spacing: Theme.Tokens.xs

                                Text {
                                    text: "Fuel remaining"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.captionSize
                                    color: Theme.Tokens.steel
                                }

                                Text {
                                    text: typeof overlayVM !== "undefined" && overlayVM
                                          ? overlayVM.fuelLevel.toFixed(1) + " L"
                                          : "--"
                                    font.family: Theme.Typography.displayFamily
                                    font.pixelSize: 36
                                    font.weight: Font.Bold
                                    color: Theme.Tokens.chalk
                                }
                            }

                            // Laps remaining estimate
                            RowLayout {
                                width: parent.width
                                spacing: Theme.Tokens.md

                                Text {
                                    text: "Laps remaining"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.captionSize
                                    color: Theme.Tokens.chalk
                                    Layout.preferredWidth: 120
                                }

                                Text {
                                    text: typeof overlayVM !== "undefined" && overlayVM
                                          ? overlayVM.fuelLapsLeft.toFixed(1)
                                          : "--"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.bodySize
                                    font.weight: Font.Bold
                                    color: Theme.Tokens.pitOrange
                                }
                            }

                            // Alerts
                            Column {
                                width: parent.width
                                spacing: Theme.Tokens.xs
                                visible: strategyVM && strategyVM.alerts.length > 0

                                Text {
                                    text: "ALERTS"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.microSize
                                    font.weight: Theme.Typography.microWeight
                                    font.letterSpacing: Theme.Typography.microSpacing
                                    color: Theme.Tokens.safetyRed
                                    topPadding: Theme.Tokens.md
                                }

                                Repeater {
                                    model: strategyVM ? strategyVM.alerts : []

                                    Text {
                                        required property var modelData
                                        text: modelData.message
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: Theme.Typography.captionSize
                                        color: modelData.severity === "critical"
                                               ? Theme.Tokens.safetyRed
                                               : Theme.Tokens.marshalYellow
                                        width: raceStatusCol.width
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                        }
                    }
                }

                // ================================================================
                // COACHING PLACEHOLDERS
                // ================================================================
                Column {
                    visible: root.activeTabId === "consistency"
                    width: parent.width
                    spacing: Theme.Tokens.xl

                    // Consistency Score card
                    Rectangle {
                        id: consistencyCard
                        width: parent.width
                        implicitHeight: consistencyCol.implicitHeight + Theme.Tokens.xl * 2
                        radius: Theme.Tokens.radiusLg
                        color: Theme.Tokens.surface
                        border.width: 1
                        border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                        property var report: strategyVM ? strategyVM.consistencyReport : ({})
                        property bool hasData: report && report.lap_count !== undefined && report.lap_count > 0

                        Column {
                            id: consistencyCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.Tokens.xl }
                            spacing: Theme.Tokens.md

                            Text {
                                text: "CONSISTENCY SCORE"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Font.Bold; font.letterSpacing: 1.5
                                color: Theme.Tokens.steel
                            }

                            // Score + progress bar
                            Row {
                                visible: consistencyCard.hasData
                                spacing: Theme.Tokens.lg
                                width: parent.width

                                Text {
                                    text: consistencyCard.report.consistency_pct !== undefined
                                          ? Math.round(consistencyCard.report.consistency_pct) + "%"
                                          : "--"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: 36; font.weight: Font.Bold
                                    color: Theme.Tokens.chalk
                                }

                                Column {
                                    spacing: 4
                                    anchors.verticalCenter: parent.verticalCenter

                                    // Progress bar
                                    Rectangle {
                                        width: 200; height: 8; radius: 4
                                        color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08)
                                        Rectangle {
                                            width: parent.width * (consistencyCard.report.consistency_pct || 0) / 100
                                            height: parent.height; radius: 4
                                            color: Theme.Tokens.acidGreen
                                        }
                                    }

                                    Text {
                                        text: {
                                            var r = consistencyCard.report
                                            if (!r || !r.trend) return ""
                                            var arrow = r.trend === "improving" ? "\u2191" : r.trend === "degrading" ? "\u2193" : "\u2192"
                                            return arrow + " " + r.trend.charAt(0).toUpperCase() + r.trend.slice(1)
                                        }
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: Theme.Typography.captionSize
                                        color: {
                                            var r = consistencyCard.report
                                            if (!r) return Theme.Tokens.steel
                                            if (r.trend === "improving") return Theme.Tokens.acidGreen
                                            if (r.trend === "degrading") return Theme.Tokens.safetyRed
                                            return Theme.Tokens.steel
                                        }
                                    }
                                }
                            }

                            // Lap stats row
                            Row {
                                visible: consistencyCard.hasData
                                spacing: Theme.Tokens.xxl

                                Column {
                                    spacing: 2
                                    Text { text: "BEST"; font.family: Theme.Typography.monoFamily; font.pixelSize: Theme.Typography.microSize; color: Theme.Tokens.steel }
                                    Text {
                                        text: root.formatTime(consistencyCard.report.best_lap_time_s || 0)
                                        font.family: Theme.Typography.monoFamily; font.pixelSize: 16; font.weight: Font.Bold
                                        color: Theme.Tokens.acidGreen
                                    }
                                }
                                Column {
                                    spacing: 2
                                    Text { text: "MEDIAN"; font.family: Theme.Typography.monoFamily; font.pixelSize: Theme.Typography.microSize; color: Theme.Tokens.steel }
                                    Text {
                                        text: root.formatTime(consistencyCard.report.median_lap_time_s || 0)
                                        font.family: Theme.Typography.monoFamily; font.pixelSize: 16; font.weight: Font.Bold
                                        color: Theme.Tokens.chalk
                                    }
                                }
                                Column {
                                    spacing: 2
                                    Text { text: "STD DEV"; font.family: Theme.Typography.monoFamily; font.pixelSize: Theme.Typography.microSize; color: Theme.Tokens.steel }
                                    Text {
                                        text: "\u00b1" + (consistencyCard.report.overall_std_dev_s || 0).toFixed(3) + "s"
                                        font.family: Theme.Typography.monoFamily; font.pixelSize: 16; font.weight: Font.Bold
                                        color: Theme.Tokens.pitOrange
                                    }
                                }
                                Column {
                                    spacing: 2
                                    Text { text: "LAPS"; font.family: Theme.Typography.monoFamily; font.pixelSize: Theme.Typography.microSize; color: Theme.Tokens.steel }
                                    Text {
                                        text: (consistencyCard.report.lap_count || 0).toString()
                                        font.family: Theme.Typography.monoFamily; font.pixelSize: 16; font.weight: Font.Bold
                                        color: Theme.Tokens.chalk
                                    }
                                }
                            }

                            // No data state
                            Text {
                                visible: !consistencyCard.hasData
                                text: "Drive at least 3 laps to see consistency analysis"
                                font.family: Theme.Typography.bodyFamily
                                font.pixelSize: Theme.Typography.bodySize
                                color: Theme.Tokens.steel
                            }
                        }
                    }

                    // Focus recommendation card
                    Rectangle {
                        visible: strategyVM && strategyVM.consistencyReport && strategyVM.consistencyReport.focus_recommendation
                        width: parent.width
                        implicitHeight: focusCol.implicitHeight + Theme.Tokens.xl * 2
                        radius: Theme.Tokens.radiusLg
                        color: Theme.Tokens.surface
                        border.width: 1
                        border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.15)

                        Column {
                            id: focusCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.Tokens.xl }
                            spacing: Theme.Tokens.sm

                            Text {
                                text: "FOCUS FOR NEXT 5 LAPS"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Font.Bold; font.letterSpacing: 1.5
                                color: Theme.Tokens.pitOrange
                            }

                            Text {
                                text: strategyVM && strategyVM.consistencyReport ? (strategyVM.consistencyReport.focus_recommendation || "") : ""
                                font.family: Theme.Typography.bodyFamily
                                font.pixelSize: Theme.Typography.bodySize
                                color: Theme.Tokens.chalk
                                wrapMode: Text.Wrap
                                width: parent.width
                            }
                        }
                    }

                    // Active Coaching Plan card — bound to the unified
                    // CoachingMessage contract so wording matches the overlay.
                    // `activePlan` is kept only for structural metadata
                    // (laps_remaining) — no user-facing strings come from it.
                    Rectangle {
                        id: planCard
                        property var message: strategyVM ? strategyVM.coachingMessage : ({})
                        property var meta: strategyVM ? strategyVM.activePlan : ({})
                        property bool hasPlan: message && !message.is_empty
                        property var supporting: (message && message.supporting) ? message.supporting : ({})
                        visible: hasPlan

                        width: parent.width
                        implicitHeight: planCardCol.implicitHeight + Theme.Tokens.xl * 2
                        radius: Theme.Tokens.radiusLg
                        color: Theme.Tokens.surface
                        border.width: 1
                        border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.25)

                        Column {
                            id: planCardCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.Tokens.xl }
                            spacing: Theme.Tokens.md

                            Row {
                                spacing: Theme.Tokens.sm

                                Text {
                                    text: "COACHING PLAN"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.microSize
                                    font.weight: Font.Bold; font.letterSpacing: 1.5
                                    color: Theme.Tokens.pitOrange
                                }

                                Rectangle {
                                    visible: planCard.meta && planCard.meta.laps_remaining !== undefined
                                    width: lapsLbl.implicitWidth + 10; height: 16; radius: 3
                                    color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.12)
                                    Text {
                                        id: lapsLbl
                                        anchors.centerIn: parent
                                        text: ((planCard.meta && planCard.meta.laps_remaining) || 0) + " LAPS LEFT"
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: 9; font.weight: Font.Bold
                                        color: Theme.Tokens.pitOrange
                                    }
                                }
                            }

                            Text {
                                text: "Focus: " + (planCard.message.focus_id || "")
                                font.family: Theme.Typography.bodyFamily
                                font.pixelSize: 16; font.weight: Font.DemiBold
                                color: Theme.Tokens.chalk
                            }

                            Text {
                                text: planCard.message.headline || ""
                                font.family: Theme.Typography.bodyFamily
                                font.pixelSize: Theme.Typography.bodySize
                                color: Theme.Tokens.chalk
                                wrapMode: Text.Wrap; width: parent.width
                            }

                            Text {
                                visible: planCard.message.subline && planCard.message.subline.length > 0
                                text: planCard.message.subline || ""
                                font.family: Theme.Typography.bodyFamily
                                font.pixelSize: Theme.Typography.bodySize
                                color: Theme.Tokens.acidGreen
                                wrapMode: Text.Wrap; width: parent.width
                            }

                            Text {
                                visible: planCard.supporting.measurable_target && planCard.supporting.measurable_target.length > 0
                                text: "Target: " + (planCard.supporting.measurable_target || "")
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.captionSize
                                color: Theme.Tokens.acidGreen
                                wrapMode: Text.Wrap; width: parent.width
                            }

                            Text {
                                visible: planCard.supporting.ignore_list && planCard.supporting.ignore_list.length > 0
                                text: "Ignore: " + (planCard.supporting.ignore_list ? planCard.supporting.ignore_list.join(", ") : "")
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.captionSize
                                color: Theme.Tokens.steel
                                wrapMode: Text.Wrap; width: parent.width
                            }
                        }
                    }
                }

                // ================================================================
                // PACE TAB
                // ================================================================
                Column {
                    visible: root.activeTabId === "pace"
                    width: parent.width
                    spacing: Theme.Tokens.xl

                    Rectangle {
                        id: paceCard
                        property var pace: strategyVM ? strategyVM.paceBreakdown : ({})
                        property bool hasPace: pace && pace.lap_count !== undefined && pace.lap_count > 0

                        width: parent.width
                        implicitHeight: paceCardCol.implicitHeight + Theme.Tokens.xl * 2
                        radius: Theme.Tokens.radiusLg
                        color: Theme.Tokens.surface
                        border.width: 1
                        border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                        Column {
                            id: paceCardCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.Tokens.xl }
                            spacing: Theme.Tokens.md

                            Text {
                                text: "PACE BREAKDOWN"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Font.Bold; font.letterSpacing: 1.5
                                color: Theme.Tokens.steel
                            }

                            Row {
                                visible: paceCard.hasPace
                                spacing: Theme.Tokens.xxl

                                Column {
                                    spacing: 2
                                    Text {
                                        text: "BEST LAP"
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: Theme.Typography.microSize
                                        color: Theme.Tokens.steel
                                    }
                                    Text {
                                        text: root.formatTime(paceCard.pace.best_lap_s || 0)
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: 20; font.weight: Font.Bold
                                        color: Theme.Tokens.chalk
                                    }
                                }
                                Column {
                                    spacing: 2
                                    Text {
                                        text: "THEORETICAL BEST"
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: Theme.Typography.microSize
                                        color: Theme.Tokens.steel
                                    }
                                    Text {
                                        text: root.formatTime(paceCard.pace.theoretical_best_s || 0)
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: 20; font.weight: Font.Bold
                                        color: Theme.Tokens.acidGreen
                                    }
                                }
                                Column {
                                    spacing: 2
                                    Text {
                                        text: "GAIN AVAILABLE"
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: Theme.Typography.microSize
                                        color: Theme.Tokens.steel
                                    }
                                    Text {
                                        text: "-" + (paceCard.pace.gain_available_s || 0).toFixed(3) + "s"
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: 20; font.weight: Font.Bold
                                        color: Theme.Tokens.pitOrange
                                    }
                                }
                            }

                            Text {
                                visible: !paceCard.hasPace
                                text: "Drive at least 3 laps to see pace breakdown"
                                font.family: Theme.Typography.bodyFamily
                                font.pixelSize: Theme.Typography.bodySize
                                color: Theme.Tokens.steel
                            }
                        }
                    }
                }

                // ================================================================
                // READINESS TAB
                // ================================================================
                Column {
                    visible: root.activeTabId === "readiness"
                    width: parent.width
                    spacing: Theme.Tokens.xl

                    Rectangle {
                        id: readyCard
                        property var ready: strategyVM ? strategyVM.readinessState : ({})
                        property bool hasReady: ready && ready.state !== undefined && ready.lap_count > 0

                        width: parent.width
                        implicitHeight: readyCardCol.implicitHeight + Theme.Tokens.xl * 2
                        radius: Theme.Tokens.radiusLg
                        color: Theme.Tokens.surface
                        border.width: 1
                        border.color: {
                            if (!readyCard.hasReady || !readyCard.ready) return Theme.Tokens.subtle(Theme.Tokens.chalk)
                            if (readyCard.ready.state === "ready") return Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.4)
                            if (readyCard.ready.state === "almost") return Theme.Tokens.subtle(Theme.Tokens.marshalYellow, 0.4)
                            return Theme.Tokens.subtle(Theme.Tokens.safetyRed, 0.25)
                        }

                        Column {
                            id: readyCardCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.Tokens.xl }
                            spacing: Theme.Tokens.md

                            Text {
                                text: "RACE READINESS"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Font.Bold; font.letterSpacing: 1.5
                                color: Theme.Tokens.steel
                            }

                            // Big state label
                            Text {
                                visible: readyCard.hasReady
                                text: (readyCard.ready.state || "").toUpperCase().replace("_", " ")
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: 36; font.weight: Font.Bold
                                color: {
                                    if (!readyCard.ready) return Theme.Tokens.chalk
                                    if (readyCard.ready.state === "ready") return Theme.Tokens.acidGreen
                                    if (readyCard.ready.state === "almost") return Theme.Tokens.marshalYellow
                                    return Theme.Tokens.safetyRed
                                }
                            }

                            // Check indicators
                            Column {
                                visible: readyCard.hasReady
                                spacing: 6

                                Row {
                                    spacing: 8
                                    Text {
                                        text: readyCard.ready.consistency_ok ? "\u2713" : "\u2717"
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: 14; font.weight: Font.Bold
                                        color: readyCard.ready.consistency_ok ? Theme.Tokens.acidGreen : Theme.Tokens.safetyRed
                                    }
                                    Text {
                                        text: "Consistency"
                                        font.family: Theme.Typography.bodyFamily
                                        font.pixelSize: Theme.Typography.bodySize
                                        color: Theme.Tokens.chalk
                                    }
                                }
                                Row {
                                    spacing: 8
                                    Text {
                                        text: readyCard.ready.variance_stable ? "\u2713" : "\u2717"
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: 14; font.weight: Font.Bold
                                        color: readyCard.ready.variance_stable ? Theme.Tokens.acidGreen : Theme.Tokens.safetyRed
                                    }
                                    Text {
                                        text: "Sector variance stable"
                                        font.family: Theme.Typography.bodyFamily
                                        font.pixelSize: Theme.Typography.bodySize
                                        color: Theme.Tokens.chalk
                                    }
                                }
                                Row {
                                    spacing: 8
                                    Text {
                                        text: readyCard.ready.trend_ok ? "\u2713" : "\u2717"
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: 14; font.weight: Font.Bold
                                        color: readyCard.ready.trend_ok ? Theme.Tokens.acidGreen : Theme.Tokens.safetyRed
                                    }
                                    Text {
                                        text: "Trend not degrading"
                                        font.family: Theme.Typography.bodyFamily
                                        font.pixelSize: Theme.Typography.bodySize
                                        color: Theme.Tokens.chalk
                                    }
                                }
                                Row {
                                    spacing: 8
                                    Text {
                                        text: readyCard.ready.no_outlier_corners ? "\u2713" : "\u2717"
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: 14; font.weight: Font.Bold
                                        color: readyCard.ready.no_outlier_corners ? Theme.Tokens.acidGreen : Theme.Tokens.safetyRed
                                    }
                                    Text {
                                        text: "No outlier corners"
                                        font.family: Theme.Typography.bodyFamily
                                        font.pixelSize: Theme.Typography.bodySize
                                        color: Theme.Tokens.chalk
                                    }
                                }
                            }

                            Text {
                                text: (readyCard.ready && readyCard.ready.reason) || ""
                                font.family: Theme.Typography.bodyFamily
                                font.pixelSize: Theme.Typography.captionSize
                                color: Theme.Tokens.steel
                                wrapMode: Text.Wrap; width: parent.width
                            }

                            Text {
                                visible: !readyCard.hasReady
                                text: "Drive more laps to assess race readiness"
                                font.family: Theme.Typography.bodyFamily
                                font.pixelSize: Theme.Typography.bodySize
                                color: Theme.Tokens.steel
                            }
                        }
                    }
                }

                // ================================================================
                // DATA MODE — TELEMETRY TAB
                // ================================================================
                Column {
                    visible: root.activeTabId === "telemetry"
                    width: parent.width
                    spacing: Theme.Tokens.xl

                    // Overall quality card
                    Rectangle {
                        id: qualityCard
                        property var inspection: strategyVM ? strategyVM.dataInspection : ({})
                        property bool hasData: strategyVM ? strategyVM.hasDataInspection : false

                        width: parent.width
                        implicitHeight: qualityCol.implicitHeight + Theme.Tokens.xl * 2
                        radius: Theme.Tokens.radiusLg
                        color: Theme.Tokens.surface
                        border.width: 1
                        border.color: {
                            if (!qualityCard.hasData) return Theme.Tokens.subtle(Theme.Tokens.chalk)
                            var q = qualityCard.inspection.overall_quality
                            if (q === "good") return Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.3)
                            if (q === "degraded") return Theme.Tokens.subtle(Theme.Tokens.marshalYellow, 0.3)
                            return Theme.Tokens.subtle(Theme.Tokens.safetyRed, 0.25)
                        }

                        Column {
                            id: qualityCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.Tokens.xl }
                            spacing: Theme.Tokens.md

                            Text {
                                text: "DATA QUALITY"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Font.Bold; font.letterSpacing: 1.5
                                color: Theme.Tokens.steel
                            }

                            Row {
                                visible: qualityCard.hasData
                                spacing: Theme.Tokens.xxl

                                Column {
                                    spacing: 2
                                    Text { text: "OVERALL"; font.family: Theme.Typography.monoFamily; font.pixelSize: Theme.Typography.microSize; color: Theme.Tokens.steel }
                                    Text {
                                        text: (qualityCard.inspection.overall_quality || "").toUpperCase()
                                        font.family: Theme.Typography.monoFamily; font.pixelSize: 20; font.weight: Font.Bold
                                        color: {
                                            var q = qualityCard.inspection.overall_quality
                                            if (q === "good") return Theme.Tokens.acidGreen
                                            if (q === "degraded") return Theme.Tokens.marshalYellow
                                            return Theme.Tokens.safetyRed
                                        }
                                    }
                                }
                                Column {
                                    spacing: 2
                                    Text { text: "SAMPLES"; font.family: Theme.Typography.monoFamily; font.pixelSize: Theme.Typography.microSize; color: Theme.Tokens.steel }
                                    Text {
                                        text: (qualityCard.inspection.total_samples || 0).toString()
                                        font.family: Theme.Typography.monoFamily; font.pixelSize: 20; font.weight: Font.Bold
                                        color: Theme.Tokens.chalk
                                    }
                                }
                                Column {
                                    spacing: 2
                                    Text { text: "SAMPLE RATE"; font.family: Theme.Typography.monoFamily; font.pixelSize: Theme.Typography.microSize; color: Theme.Tokens.steel }
                                    Text {
                                        text: (qualityCard.inspection.sample_rate_hz || 0).toFixed(1) + " Hz"
                                        font.family: Theme.Typography.monoFamily; font.pixelSize: 20; font.weight: Font.Bold
                                        color: Theme.Tokens.chalk
                                    }
                                }
                            }

                            Row {
                                visible: qualityCard.hasData
                                spacing: Theme.Tokens.lg

                                Rectangle {
                                    width: availLbl.implicitWidth + 12; height: 20; radius: 3
                                    color: Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.12)
                                    Text {
                                        id: availLbl
                                        anchors.centerIn: parent
                                        text: (qualityCard.inspection.available_count || 0) + " AVAILABLE"
                                        font.family: Theme.Typography.monoFamily; font.pixelSize: 9; font.weight: Font.Bold
                                        color: Theme.Tokens.acidGreen
                                    }
                                }
                                Rectangle {
                                    width: estLbl.implicitWidth + 12; height: 20; radius: 3
                                    color: Theme.Tokens.subtle(Theme.Tokens.marshalYellow, 0.12)
                                    Text {
                                        id: estLbl
                                        anchors.centerIn: parent
                                        text: (qualityCard.inspection.estimated_count || 0) + " ESTIMATED"
                                        font.family: Theme.Typography.monoFamily; font.pixelSize: 9; font.weight: Font.Bold
                                        color: Theme.Tokens.marshalYellow
                                    }
                                }
                                Rectangle {
                                    width: unavLbl.implicitWidth + 12; height: 20; radius: 3
                                    color: Theme.Tokens.subtle(Theme.Tokens.safetyRed, 0.12)
                                    Text {
                                        id: unavLbl
                                        anchors.centerIn: parent
                                        text: (qualityCard.inspection.unavailable_count || 0) + " UNAVAILABLE"
                                        font.family: Theme.Typography.monoFamily; font.pixelSize: 9; font.weight: Font.Bold
                                        color: Theme.Tokens.safetyRed
                                    }
                                }
                            }

                            Text {
                                visible: !qualityCard.hasData
                                text: "No telemetry data yet \u2014 connect to a sim and drive"
                                font.family: Theme.Typography.bodyFamily
                                font.pixelSize: Theme.Typography.bodySize
                                color: Theme.Tokens.steel
                            }
                        }
                    }

                    // Warnings card (only if there are warnings)
                    Rectangle {
                        id: warningsCard
                        property var warnings: strategyVM && strategyVM.dataInspection ? (strategyVM.dataInspection.warnings || []) : []
                        visible: warningsCard.warnings.length > 0

                        width: parent.width
                        implicitHeight: warnCol.implicitHeight + Theme.Tokens.xl * 2
                        radius: Theme.Tokens.radiusLg
                        color: Theme.Tokens.surface
                        border.width: 1
                        border.color: Theme.Tokens.subtle(Theme.Tokens.marshalYellow, 0.2)

                        Column {
                            id: warnCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.Tokens.xl }
                            spacing: Theme.Tokens.sm

                            Text {
                                text: "WARNINGS"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Font.Bold; font.letterSpacing: 1.5
                                color: Theme.Tokens.marshalYellow
                            }

                            Repeater {
                                model: warningsCard.warnings
                                delegate: Text {
                                    required property string modelData
                                    text: "\u26a0 " + modelData
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.captionSize
                                    color: Theme.Tokens.steel
                                    wrapMode: Text.Wrap
                                    width: warnCol.width
                                }
                            }
                        }
                    }

                    // Channel inventory card
                    Rectangle {
                        id: channelCard
                        property var channels: strategyVM && strategyVM.dataInspection ? (strategyVM.dataInspection.channels || []) : []
                        visible: channelCard.channels.length > 0

                        width: parent.width
                        implicitHeight: channelCol.implicitHeight + Theme.Tokens.xl * 2
                        radius: Theme.Tokens.radiusLg
                        color: Theme.Tokens.surface
                        border.width: 1
                        border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                        Column {
                            id: channelCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.Tokens.xl }
                            spacing: Theme.Tokens.sm

                            Text {
                                text: "CHANNEL INVENTORY"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Font.Bold; font.letterSpacing: 1.5
                                color: Theme.Tokens.steel
                            }

                            // Header row
                            Row {
                                width: channelCol.width
                                spacing: 12
                                Text { text: "CHANNEL"; width: 180; font.family: Theme.Typography.monoFamily; font.pixelSize: 9; color: Theme.Tokens.steel }
                                Text { text: "STATE"; width: 100; font.family: Theme.Typography.monoFamily; font.pixelSize: 9; color: Theme.Tokens.steel }
                                Text { text: "LAST"; width: 120; font.family: Theme.Typography.monoFamily; font.pixelSize: 9; color: Theme.Tokens.steel }
                                Text { text: "NULL %"; width: 60; font.family: Theme.Typography.monoFamily; font.pixelSize: 9; color: Theme.Tokens.steel }
                            }

                            Repeater {
                                model: channelCard.channels
                                delegate: Row {
                                    required property var modelData
                                    width: channelCol.width
                                    spacing: 12

                                    Text {
                                        text: modelData.name
                                        width: 180
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: 11
                                        color: Theme.Tokens.chalk
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        text: (modelData.state || "").toUpperCase()
                                        width: 100
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: 11; font.weight: Font.Bold
                                        color: {
                                            if (modelData.state === "available") return Theme.Tokens.acidGreen
                                            if (modelData.state === "estimated") return Theme.Tokens.marshalYellow
                                            return Theme.Tokens.safetyRed
                                        }
                                    }
                                    Text {
                                        text: modelData.last_value !== null && modelData.last_value !== undefined
                                              ? (typeof modelData.last_value === "number" ? modelData.last_value.toFixed(2) : modelData.last_value.toString())
                                              : "\u2014"
                                        width: 120
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: 11
                                        color: Theme.Tokens.steel
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        text: ((modelData.null_ratio || 0) * 100).toFixed(0) + "%"
                                        width: 60
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: 11
                                        color: Theme.Tokens.steel
                                    }
                                }
                            }
                        }
                    }
                }

                // ================================================================
                // DATA MODE — EXPORT TAB
                // ================================================================
                Column {
                    visible: root.activeTabId === "export"
                    width: parent.width
                    spacing: Theme.Tokens.xl

                    // Sync status card
                    Rectangle {
                        id: syncCard
                        property var sync: strategyVM ? strategyVM.syncStatus : ({})

                        width: parent.width
                        implicitHeight: syncCol.implicitHeight + Theme.Tokens.xl * 2
                        radius: Theme.Tokens.radiusLg
                        color: Theme.Tokens.surface
                        border.width: 1
                        border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                        Column {
                            id: syncCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.Tokens.xl }
                            spacing: Theme.Tokens.md

                            Text {
                                text: "WEBAPP SYNC"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Font.Bold; font.letterSpacing: 1.5
                                color: Theme.Tokens.steel
                            }

                            Row {
                                spacing: Theme.Tokens.xxl

                                Column {
                                    spacing: 2
                                    Text { text: "STATUS"; font.family: Theme.Typography.monoFamily; font.pixelSize: Theme.Typography.microSize; color: Theme.Tokens.steel }
                                    Text {
                                        text: (syncCard.sync && syncCard.sync.enabled) ? "ENABLED" : "OFF"
                                        font.family: Theme.Typography.monoFamily; font.pixelSize: 16; font.weight: Font.Bold
                                        color: (syncCard.sync && syncCard.sync.enabled) ? Theme.Tokens.acidGreen : Theme.Tokens.steel
                                    }
                                }
                                Column {
                                    spacing: 2
                                    Text { text: "QUEUE DEPTH"; font.family: Theme.Typography.monoFamily; font.pixelSize: Theme.Typography.microSize; color: Theme.Tokens.steel }
                                    Text {
                                        text: (syncCard.sync ? (syncCard.sync.queue_depth || 0) : 0).toString()
                                        font.family: Theme.Typography.monoFamily; font.pixelSize: 16; font.weight: Font.Bold
                                        color: Theme.Tokens.chalk
                                    }
                                }
                                Column {
                                    spacing: 2
                                    Text { text: "SESSION ID"; font.family: Theme.Typography.monoFamily; font.pixelSize: Theme.Typography.microSize; color: Theme.Tokens.steel }
                                    Text {
                                        text: {
                                            var sid = syncCard.sync ? (syncCard.sync.session_id || "") : ""
                                            return sid ? sid.substring(0, 8) + "..." : "\u2014"
                                        }
                                        font.family: Theme.Typography.monoFamily; font.pixelSize: 14
                                        color: Theme.Tokens.steel
                                    }
                                }
                            }
                        }
                    }

                    // Export card
                    Rectangle {
                        id: exportCard
                        width: parent.width
                        implicitHeight: exportCol.implicitHeight + Theme.Tokens.xl * 2
                        radius: Theme.Tokens.radiusLg
                        color: Theme.Tokens.surface
                        border.width: 1
                        border.color: Theme.Tokens.subtle(Theme.Tokens.chalk)

                        Column {
                            id: exportCol
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.Tokens.xl }
                            spacing: Theme.Tokens.md

                            Text {
                                text: "EXPORT SESSION"
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.microSize
                                font.weight: Font.Bold; font.letterSpacing: 1.5
                                color: Theme.Tokens.steel
                            }

                            Text {
                                text: "Export channel inventory, lap times, and sync status to a JSON file in your output directory."
                                font.family: Theme.Typography.bodyFamily
                                font.pixelSize: Theme.Typography.captionSize
                                color: Theme.Tokens.steel
                                wrapMode: Text.Wrap
                                width: exportCol.width
                            }

                            Rectangle {
                                id: exportBtn
                                property string lastPath: ""
                                width: exportBtnText.implicitWidth + Theme.Tokens.xl * 2
                                height: 36
                                radius: Theme.Tokens.radiusMd
                                color: exportArea.containsMouse
                                       ? Qt.lighter(Theme.Tokens.pitOrange, 1.1)
                                       : Theme.Tokens.pitOrange

                                Text {
                                    id: exportBtnText
                                    anchors.centerIn: parent
                                    text: "Export JSON"
                                    font.family: Theme.Typography.bodyFamily
                                    font.pixelSize: Theme.Typography.captionSize
                                    font.weight: Font.DemiBold
                                    color: Theme.Tokens.void_
                                }

                                MouseArea {
                                    id: exportArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (strategyVM) {
                                            exportBtn.lastPath = strategyVM.exportSessionJson()
                                        }
                                    }
                                }
                            }

                            Text {
                                visible: exportBtn.lastPath !== ""
                                text: "Saved to: " + exportBtn.lastPath
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: Theme.Typography.captionSize
                                color: Theme.Tokens.acidGreen
                                wrapMode: Text.WrapAnywhere
                                width: exportCol.width
                            }
                        }
                    }
                }
            }
        }
    }
}
