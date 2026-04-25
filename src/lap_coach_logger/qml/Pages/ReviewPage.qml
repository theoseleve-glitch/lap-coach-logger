import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "../Theme" as Theme
import "../Components" as Components

Item {
    id: root

    property var reviewData: ({})

    signal backRequested()

    // Map section id to StackLayout index
    readonly property var sectionIndexMap: ({
        "overview": 0,
        "laps": 1,
        "telemetry": 2,
        "setup": 3,
        "engineering": 4
    })

    // T069: confirm dialog for the destructive Delete action.
    // Uses the standard QtQuick.Dialogs MessageDialog so the look
    // matches OS conventions (native modal on Windows). On accept,
    // delegates to serviceVM.deleteSession() which removes the
    // bundle on disk + the sync queue entry, then we navigate back
    // to History so the UI doesn't show stale data.
    Dialog {
        id: deleteConfirmDialog
        title: "Delete session?"
        modal: true
        anchors.centerIn: parent
        standardButtons: Dialog.Yes | Dialog.Cancel

        Text {
            text: "This will permanently delete the session bundle on disk.\n\nThis cannot be undone."
            font.family: Theme.Typography.bodyFamily
            font.pixelSize: Theme.Typography.bodySize
            color: Theme.Tokens.chalk
            wrapMode: Text.Wrap
        }

        onAccepted: {
            if (reviewVM.path) {
                serviceVM.deleteSession(reviewVM.path)
                root.backRequested()
            }
        }
    }

    Column {
        anchors.fill: parent
        spacing: 0

        // === 1. Custom nav bar ===
        Rectangle {
            width: parent.width
            height: 52
            color: Theme.Tokens.subtle(Theme.Tokens.surface, 0.85)

            // Bottom border
            Rectangle {
                anchors {
                    left: parent.left
                    right: parent.right
                    bottom: parent.bottom
                }
                height: 1
                color: Theme.Tokens.subtle(Theme.Tokens.chalk)
            }

            RowLayout {
                anchors {
                    fill: parent
                    leftMargin: Theme.Tokens.xl
                    rightMargin: Theme.Tokens.xl
                }
                spacing: Theme.Tokens.md

                // Back button
                Rectangle {
                    width: backLabel.implicitWidth + Theme.Tokens.xl * 2
                    height: 30
                    radius: Theme.Tokens.radiusMd
                    color: backArea.containsMouse
                           ? Theme.Tokens.subtle(Theme.Tokens.chalk)
                           : "transparent"

                    Text {
                        id: backLabel
                        anchors.centerIn: parent
                        text: "\u2039 History"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.bodySize
                        font.weight: Font.DemiBold
                        color: Theme.Tokens.chalk
                    }

                    MouseArea {
                        id: backArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.backRequested()
                    }
                }

                Item { Layout.fillWidth: true }

                // Action buttons
                // T070: "Export CSV" replaced with "View in webapp"
                // (export + deep-analysis flows live in lap-webapp per Q95).
                Repeater {
                    model: [
                        { label: "Open Folder",     style: "subtle", danger: false },
                        { label: "View in webapp",  style: "subtle", danger: false },
                        { label: "Reprocess",       style: "subtle", danger: false },
                        { label: "Delete",          style: "danger", danger: true }
                    ]

                    Rectangle {
                        required property var modelData
                        width: btnLabel.implicitWidth + Theme.Tokens.lg * 2
                        height: 30
                        radius: Theme.Tokens.radiusMd
                        color: btnArea.containsMouse
                               ? (modelData.danger
                                  ? Theme.Tokens.subtle(Theme.Tokens.safetyRed, 0.15)
                                  : Theme.Tokens.subtle(Theme.Tokens.chalk))
                               : "transparent"
                        border.width: modelData.danger ? 1 : 0
                        border.color: Theme.Tokens.subtle(Theme.Tokens.safetyRed, 0.25)

                        Text {
                            id: btnLabel
                            anchors.centerIn: parent
                            text: modelData.label
                            font.family: Theme.Typography.bodyFamily
                            font.pixelSize: Theme.Typography.captionSize
                            font.weight: Font.DemiBold
                            color: modelData.danger ? Theme.Tokens.safetyRed : Theme.Tokens.steel
                        }

                        MouseArea {
                            id: btnArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (modelData.label === "Open Folder")
                                    serviceVM.openOutputFolder()
                                else if (modelData.label === "Delete")
                                    deleteConfirmDialog.open()
                                else if (modelData.label === "View in webapp")
                                    serviceVM.viewSessionInWebapp(
                                        (reviewVM.data && reviewVM.data.session_id) || "")
                                // T067: wire "Reprocess" → backend /sessions/:id/reprocess
                            }
                        }
                    }
                }
            }
        }

        // === 2. Session header ===
        Item {
            width: parent.width
            height: headerRow.implicitHeight + Theme.Tokens.xl * 2

            RowLayout {
                id: headerRow
                anchors {
                    left: parent.left
                    right: parent.right
                    verticalCenter: parent.verticalCenter
                    leftMargin: Theme.Tokens.xl
                    rightMargin: Theme.Tokens.xl
                }
                spacing: Theme.Tokens.lg

                // Sim badge
                Rectangle {
                    width: 40
                    height: 40
                    radius: Theme.Tokens.radiusMd
                    color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.12)
                    border.width: 1
                    border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.20)

                    Text {
                        anchors.centerIn: parent
                        text: {
                            var s = reviewVM.data.sim || ""
                            if (s === "iRacing") return "iR"
                            if (s === "ACC" || s === "Assetto Corsa") return "AC"
                            if (s === "Le Mans Ultimate") return "LM"
                            return s.substring(0, 2).toUpperCase()
                        }
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: Theme.Typography.microSize
                        font.weight: Font.Bold
                        color: Theme.Tokens.pitOrange
                    }
                }

                // Quality grade badge
                Rectangle {
                    visible: (reviewVM.data.quality_grade || "") !== ""
                    implicitWidth: gradeLabel.implicitWidth + 20
                    implicitHeight: gradeLabel.implicitHeight + 8
                    radius: Theme.Tokens.radiusSm
                    color: Theme.Tokens.subtle(gradeColorForReview, 0.12)
                    border.width: 1
                    border.color: Theme.Tokens.subtle(gradeColorForReview, 0.25)

                    readonly property color gradeColorForReview: {
                        var g = reviewVM.data.quality_grade || ""
                        if (g === "A+" || g === "A") return Theme.Tokens.acidGreen
                        if (g === "B+") return Theme.Tokens.marshalYellow
                        return Theme.Tokens.steel
                    }

                    Text {
                        id: gradeLabel
                        anchors.centerIn: parent
                        text: reviewVM.data.quality_grade || ""
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: Theme.Typography.microSize
                        font.weight: Font.Bold
                        color: parent.gradeColorForReview
                    }
                }

                // Track name + metadata
                Column {
                    Layout.fillWidth: true
                    spacing: Theme.Tokens.xs

                    Text {
                        text: reviewVM.data.track || ""
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: 28
                        font.weight: Font.Bold
                        color: Theme.Tokens.chalk
                    }

                    Text {
                        text: (reviewVM.data.car || "") + " \u00b7 "
                              + (reviewVM.data.laps || 0) + " laps \u00b7 "
                              + (reviewVM.data.sim || "")
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: 13
                        color: Theme.Tokens.steel
                    }
                }

                // Best lap (right)
                Column {
                    Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                    spacing: Theme.Tokens.xs

                    Text {
                        text: "BEST LAP"
                        anchors.right: parent.right
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: Theme.Typography.microSize
                        font.weight: Theme.Typography.microWeight
                        font.letterSpacing: Theme.Typography.microSpacing
                        color: Theme.Tokens.pitOrange
                    }

                    Text {
                        text: reviewVM.data.best_lap_formatted || "\u2014"
                        anchors.right: parent.right
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 40
                        font.weight: Font.Bold
                        color: Theme.Tokens.chalk
                    }
                }
            }
        }

        // Separator
        Rectangle {
            width: parent.width
            height: 1
            color: Theme.Tokens.subtle(Theme.Tokens.chalk)
        }

        // === 3. SectionTabs ===
        Item {
            width: parent.width
            height: 48

            Components.SectionTabs {
                anchors {
                    left: parent.left
                    verticalCenter: parent.verticalCenter
                    leftMargin: Theme.Tokens.xl
                }
                model: [
                    { id: "overview",    label: "Overview" },
                    { id: "laps",        label: "Laps" },
                    { id: "telemetry",   label: "Telemetry" },
                    { id: "setup",       label: "Setup" },
                    { id: "engineering", label: "Engineering" }
                ]
                currentSection: reviewVM.section
                onSectionRequested: function(sectionId) {
                    reviewVM.setSection(sectionId)
                }
            }
        }

        // === 4. Section content ===
        StackLayout {
            width: parent.width
            height: parent.height - y
            currentIndex: root.sectionIndexMap[reviewVM.section] !== undefined
                          ? root.sectionIndexMap[reviewVM.section] : 0

            // --- Overview ---
            ScrollView {
                clip: true
                contentWidth: availableWidth

                Column {
                    anchors {
                        left: parent.left
                        right: parent.right
                        top: parent.top
                        margins: Theme.Tokens.xl
                    }
                    spacing: Theme.Tokens.lg

                    // T071: compact summary \u2014 header already shows
                    // laps + best + DQ; this row keeps only the
                    // Consistency dimension. Median Lap / Clean Laps /
                    // Data Size dropped (full breakdown lives in
                    // lap-webapp per Q95; T072 adds the CTA).
                    RowLayout {
                        width: parent.width
                        spacing: Theme.Tokens.md

                        Components.MetricCard {
                            Layout.fillWidth: true
                            label: "Consistency"
                            value: reviewVM.data.consistency || "\u2014"
                            subtitle: reviewVM.data.consistency_sigma || ""
                        }
                    }

                    // LapTimeChart \u2014 visual companion to the four
                    // T071 dimensions (shows lap-by-lap variance which
                    // is exactly what consistency summarises).
                    Components.LapTimeChart {
                        width: parent.width
                        height: 180
                        laps: reviewVM.data.lap_times || []
                    }
                }
            }

            // --- Laps ---
            ScrollView {
                clip: true
                contentWidth: availableWidth

                Column {
                    anchors {
                        left: parent.left
                        right: parent.right
                        top: parent.top
                        margins: Theme.Tokens.xl
                    }
                    spacing: 0

                    // Table header
                    RowLayout {
                        width: parent.width
                        height: 36
                        spacing: Theme.Tokens.sm

                        Text {
                            text: "LAP"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.microSize
                            font.weight: Theme.Typography.microWeight
                            font.letterSpacing: Theme.Typography.microSpacing
                            color: Theme.Tokens.steel
                            Layout.preferredWidth: 50
                        }

                        Text {
                            text: "TIME"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.microSize
                            font.weight: Theme.Typography.microWeight
                            font.letterSpacing: Theme.Typography.microSpacing
                            color: Theme.Tokens.steel
                            Layout.fillWidth: true
                        }

                        Text {
                            text: "SECTORS"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.microSize
                            font.weight: Theme.Typography.microWeight
                            font.letterSpacing: Theme.Typography.microSpacing
                            color: Theme.Tokens.steel
                            Layout.preferredWidth: 200
                        }

                        Text {
                            text: "DELTA"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.microSize
                            font.weight: Theme.Typography.microWeight
                            font.letterSpacing: Theme.Typography.microSpacing
                            color: Theme.Tokens.steel
                            Layout.preferredWidth: 100
                            horizontalAlignment: Text.AlignRight
                        }

                        Text {
                            text: "STATUS"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.microSize
                            font.weight: Theme.Typography.microWeight
                            font.letterSpacing: Theme.Typography.microSpacing
                            color: Theme.Tokens.steel
                            Layout.preferredWidth: 80
                            horizontalAlignment: Text.AlignRight
                        }
                    }

                    Rectangle {
                        width: parent.width
                        height: 1
                        color: Theme.Tokens.subtle(Theme.Tokens.chalk)
                    }

                    // Lap rows
                    Repeater {
                        model: reviewVM.data.lap_times || []

                        Rectangle {
                            required property var modelData
                            required property int index

                            readonly property bool isBest: modelData.is_best === true

                            width: parent.width
                            height: 40
                            color: isBest ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.08)
                                          : "transparent"
                            radius: isBest ? Theme.Tokens.radiusSm : 0

                            RowLayout {
                                anchors {
                                    fill: parent
                                    leftMargin: Theme.Tokens.xs
                                    rightMargin: Theme.Tokens.xs
                                }
                                spacing: Theme.Tokens.sm

                                Text {
                                    text: modelData.lap !== undefined
                                          ? modelData.lap.toString() : (index + 1).toString()
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.captionSize
                                    font.weight: isBest ? Font.Bold : Font.Normal
                                    color: isBest ? Theme.Tokens.pitOrange : Theme.Tokens.chalk
                                    Layout.preferredWidth: 50
                                }

                                Text {
                                    text: modelData.time || "\u2014"
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.captionSize
                                    font.weight: Font.DemiBold
                                    color: isBest ? Theme.Tokens.pitOrange : Theme.Tokens.chalk
                                    Layout.fillWidth: true
                                }

                                // Sector times
                                Text {
                                    text: {
                                        var sectors = modelData.sectors
                                        if (!sectors || sectors.length === 0) return "\u2014"
                                        return sectors.join("  ")
                                    }
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: 11
                                    color: Theme.Tokens.steel
                                    Layout.preferredWidth: 200
                                }

                                Text {
                                    text: modelData.delta || ""
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.captionSize
                                    color: {
                                        if (!modelData.delta) return Theme.Tokens.steel
                                        if (modelData.delta.indexOf("-") === 0)
                                            return Theme.Tokens.acidGreen
                                        return Theme.Tokens.safetyRed
                                    }
                                    Layout.preferredWidth: 100
                                    horizontalAlignment: Text.AlignRight
                                }

                                Text {
                                    text: modelData.status || ""
                                    font.family: Theme.Typography.monoFamily
                                    font.pixelSize: Theme.Typography.microSize
                                    font.weight: Font.Bold
                                    color: {
                                        if (modelData.status === "clean")
                                            return Theme.Tokens.acidGreen
                                        if (modelData.status === "track_limits")
                                            return Theme.Tokens.marshalYellow
                                        return Theme.Tokens.steel
                                    }
                                    Layout.preferredWidth: 80
                                    horizontalAlignment: Text.AlignRight
                                }
                            }
                        }
                    }
                }
            }

            // --- Telemetry (placeholder, removed by T073) ---
            Item {
                Column {
                    anchors.centerIn: parent
                    spacing: Theme.Tokens.md

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "Telemetry"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.headingSize
                        font.weight: Theme.Typography.headingWeight
                        color: Theme.Tokens.chalk
                    }

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "Coming from legacy migration"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.bodySize
                        color: Theme.Tokens.steel
                    }
                }
            }

            // --- Setup (placeholder, removed by T073) ---
            Item {
                Column {
                    anchors.centerIn: parent
                    spacing: Theme.Tokens.md

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "Setup"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.headingSize
                        font.weight: Theme.Typography.headingWeight
                        color: Theme.Tokens.chalk
                    }

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "Coming from legacy migration"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.bodySize
                        color: Theme.Tokens.steel
                    }
                }
            }

            // --- Engineering (placeholder, removed by T073) ---
            Item {
                Column {
                    anchors.centerIn: parent
                    spacing: Theme.Tokens.md

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "Engineering"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.headingSize
                        font.weight: Theme.Typography.headingWeight
                        color: Theme.Tokens.chalk
                    }

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "Coming from legacy migration"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.bodySize
                        color: Theme.Tokens.steel
                    }
                }
            }
        }
    }
}
