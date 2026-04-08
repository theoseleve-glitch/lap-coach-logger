import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  RaceScheduleWidget — upcoming race sessions display (300 x 240).
    Shows time, series name, duration for each event.
    Highlights the next upcoming session with acidGreen "NEXT" badge.
    Past events are dimmed; empty state shown when no events.

    Inline component: EventRow                                       */
Rectangle {
    id: root

    // -- font scale (driven by OverlayWidget parent) --
    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 300
    height: 240
    color: "transparent"

    // ── Public API ──────────────────────────────────────────────────
    property var events: []   // [{name, time, duration, registrationEnd, isNext, isPast}]

    // ── Null-safe accessor ──────────────────────────────────────────
    function safeEvent(idx) {
        if (!Array.isArray(root.events) || idx < 0 || idx >= root.events.length)
            return { name: "", time: "", duration: "", registrationEnd: "", isNext: false, isPast: false }
        return root.events[idx] || { name: "", time: "", duration: "", registrationEnd: "", isNext: false, isPast: false }
    }

    // ── Time formatting helper ──────────────────────────────────────
    function fmtTime(t) {
        if (!t || typeof t !== "string") return "--:--"
        return t
    }

    // ── Inline component: EventRow ──────────────────────────────────
    component EventRow: Rectangle {
        id: row

        property var   evt: ({})
        property bool  isNext: evt.isNext || false
        property bool  isPast: evt.isPast || false

        Layout.fillWidth: true
        Layout.preferredHeight: 50
        radius: Theme.Tokens.radiusSm
        opacity: isPast ? 0.4 : 1.0

        color: isNext ? Theme.Tokens.subtle(Theme.Tokens.acidGreen)
                      : Theme.Tokens.subtle(Theme.Tokens.chalk, 0.03)
        border.width: isNext ? 1 : 0
        border.color: Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.20)

        Behavior on opacity { NumberAnimation { duration: Theme.Motion.statusColorDuration } }
        Behavior on color   { ColorAnimation  { duration: Theme.Motion.statusColorDuration } }

        RowLayout {
            anchors {
                fill: parent
                leftMargin: Theme.Tokens.sm + 2
                rightMargin: Theme.Tokens.sm + 2
            }
            spacing: Theme.Tokens.sm

            // Time column
            ColumnLayout {
                spacing: 0
                Layout.preferredWidth: 44

                Text {
                    text: root.fmtTime(row.evt.time)
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Math.round(13 * root.fontScale)
                    font.weight: Font.Bold
                    color: row.isNext ? Theme.Tokens.acidGreen : Theme.Tokens.chalk
                    Behavior on color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
                }
                Text {
                    text: row.evt.duration || ""
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Theme.Typography.microSize - 2
                    color: Theme.Tokens.steel
                }
            }

            // Separator dot
            Rectangle {
                width: 3; height: 3; radius: 1.5
                color: row.isNext ? Theme.Tokens.acidGreen : Theme.Tokens.steel
                Layout.alignment: Qt.AlignVCenter
                opacity: 0.5
            }

            // Name + registration end
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0

                Text {
                    text: row.evt.name || ""
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Math.round(11 * root.fontScale)
                    font.weight: Font.DemiBold
                    color: Theme.Tokens.chalk
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
                Text {
                    visible: (row.evt.registrationEnd || "").length > 0
                    text: "REG " + (row.evt.registrationEnd || "")
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Math.round(7 * root.fontScale)
                    font.letterSpacing: 0.6
                    color: Theme.Tokens.steel
                }
            }

            // NEXT badge
            Rectangle {
                visible: row.isNext
                implicitWidth: nextLbl.implicitWidth + Theme.Tokens.sm
                implicitHeight: 14
                radius: 3
                color: Theme.Tokens.subtle(Theme.Tokens.acidGreen, 0.15)
                Layout.alignment: Qt.AlignVCenter

                Text {
                    id: nextLbl
                    anchors.centerIn: parent
                    text: "NEXT"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Math.round(7 * root.fontScale)
                    font.weight: Font.Bold
                    color: Theme.Tokens.acidGreen
                }
            }
        }
    }

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: Theme.Tokens.sm + 2
            bottomMargin: Theme.Tokens.sm + 2
            leftMargin: Theme.Tokens.md
            rightMargin: Theme.Tokens.md
        }
        spacing: 0

        // ── Header ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.Tokens.sm - 2

            Text {
                text: "SCHEDULE"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize - 1
                font.weight: Theme.Typography.microWeight
                font.letterSpacing: Theme.Typography.microSpacing - 0.3
                color: Theme.Tokens.steel
            }

            Rectangle {
                implicitWidth: evtCount.implicitWidth + Theme.Tokens.sm
                implicitHeight: 14
                radius: 3
                color: Theme.Tokens.subtle(Theme.Tokens.marshalYellow, 0.12)

                Text {
                    id: evtCount
                    anchors.centerIn: parent
                    text: Array.isArray(root.events) ? root.events.length : 0
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Math.round(7 * root.fontScale)
                    font.weight: Font.Bold
                    color: Theme.Tokens.marshalYellow
                }
            }

            Item { Layout.fillWidth: true }
        }

        // ── Separator ──────────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.Tokens.sm
            Rectangle {
                anchors.centerIn: parent
                width: parent.width; height: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.5; color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }

        // ── Event rows / Empty state ───────────────────────────────
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.Tokens.xs

            // Empty state
            Text {
                visible: !Array.isArray(root.events) || root.events.length === 0
                text: "No scheduled events"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.captionSize
                color: Theme.Tokens.steel
                opacity: 0.5
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: Theme.Tokens.xxl
            }

            Repeater {
                model: Array.isArray(root.events) ? root.events.length : 0

                delegate: EventRow {
                    required property int index
                    evt: root.safeEvent(index)
                }
            }
        }
    }
}
