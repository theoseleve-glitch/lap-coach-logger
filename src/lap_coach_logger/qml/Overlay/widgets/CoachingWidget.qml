import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  CoachingWidget — live coaching advice overlay (290 px wide).
    Asymmetric-radius glass panel (4px apex corner top-left, 14px elsewhere)
    with severity accent, category / sector meta, headline + subtext,
    severity-colored confidence bar, "Coach" brand mark, and dismiss
    animation (scale down + fade).                                           */
GlassSurface {
    id: root

    // -- font scale (driven by OverlayWidget parent) --
    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 290
    implicitHeight: col.implicitHeight + 24

    // Asymmetric radius: 4 px "apex corner" top-left, 14 px elsewhere
    radius: 14
    topLeftRadius: 4

    // ── public API ──────────────────────────────────────────────────
    property string headline: ""
    property string sub: ""
    property string category: ""
    property string severity: "positive"   // positive | caution | critical
    property int    confidence: 0          // 0-100
    property string sector: ""

    signal dismissed()

    // ── severity colors ─────────────────────────────────────────────
    readonly property color severityColor: {
        switch (root.severity) {
        case "caution":  return Theme.Tokens.marshalYellow
        case "critical": return Theme.Tokens.safetyRed
        default:         return Theme.Tokens.acidGreen
        }
    }

    readonly property bool isCritical: root.severity === "critical"

    // ── Dismiss animation (scale down + fade) ──────────────────────
    opacity: 1.0
    scale: 1.0
    transformOrigin: Item.Center
    visible: opacity > 0

    function dismiss() {
        dismissAnim.start()
    }

    ParallelAnimation {
        id: dismissAnim

        NumberAnimation {
            target: root
            property: "opacity"
            to: 0.0
            duration: 200
            easing.type: Easing.InCubic
        }
        NumberAnimation {
            target: root
            property: "scale"
            to: 0.92
            duration: 200
            easing.type: Easing.InCubic
        }

        onFinished: {
            root.dismissed()
            root.opacity = 1.0
            root.scale = 1.0
        }
    }

    // ── Appear animation ───────────────────────────────────────────
    Component.onCompleted: appearAnim.start()

    ParallelAnimation {
        id: appearAnim

        NumberAnimation {
            target: root
            property: "opacity"
            from: 0.0; to: 1.0
            duration: 250
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: root
            property: "scale"
            from: 0.95; to: 1.0
            duration: 250
            easing.type: Easing.OutCubic
        }
    }

    // ── Critical top rule (1.5px red) ──────────────────────────────
    Rectangle {
        visible: root.isCritical
        anchors {
            top: parent.top
            left: parent.left
            right: parent.right
            leftMargin: 4      // matches apex corner radius
            rightMargin: 14
        }
        height: 1.5
        color: Theme.Tokens.safetyRed
        z: 2

        opacity: root.isCritical ? 1.0 : 0.0
        Behavior on opacity { NumberAnimation { duration: 200 } }
    }

    ColumnLayout {
        id: col
        anchors {
            fill: parent
            topMargin: 12
            bottomMargin: 10
            leftMargin: 14
            rightMargin: 14
        }
        spacing: 0

        // ── Top meta: CATEGORY / SECTOR + dismiss ──────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 4

            Text {
                text: {
                    var parts = []
                    if (root.category && root.category.length > 0)
                        parts.push(root.category.toUpperCase())
                    if (root.sector && root.sector.length > 0)
                        parts.push(root.sector.toUpperCase())
                    return parts.join(" \u00B7 ")
                }
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Math.round(9 * root.fontScale)
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: root.severityColor
                elide: Text.ElideRight
                Layout.fillWidth: true

                Behavior on color { ColorAnimation { duration: 200 } }
            }

            // Dismiss button
            Rectangle {
                id: dismissBtn
                width: 16; height: 16; radius: 4
                color: "transparent"

                Text {
                    anchors.centerIn: parent
                    text: "\u00D7"
                    font.pixelSize: Math.round(12 * root.fontScale)
                    font.weight: Font.Bold
                    color: dismissArea.containsMouse
                          ? Theme.Tokens.chalk : Theme.Tokens.steel
                    Behavior on color { ColorAnimation { duration: 120 } }
                }

                MouseArea {
                    id: dismissArea
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    hoverEnabled: true
                    onEntered: dismissBtn.color = Theme.Tokens.subtle(Theme.Tokens.chalk, 0.06)
                    onExited:  dismissBtn.color = "transparent"
                    onClicked: root.dismiss()
                }
            }
        }

        // ── Headline ───────────────────────────────────────────────
        Text {
            text: root.headline || ""
            font.family: Theme.Typography.bodyFamily
            font.pixelSize: Math.round(19 * root.fontScale)
            font.weight: Font.DemiBold
            color: Theme.Tokens.chalk
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            Layout.topMargin: 6
        }

        // ── Sub line ───────────────────────────────────────────────
        Text {
            visible: (root.sub ? root.sub.length : 0) > 0
            text: root.sub || ""
            font.family: Theme.Typography.bodyFamily
            font.pixelSize: Math.round(12 * root.fontScale)
            color: Theme.Tokens.steel
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            Layout.topMargin: 2
        }

        // ── Confidence bar + percentage + "Coach" ──────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 10
            spacing: 8

            // Thin confidence bar (colored by severity)
            Item {
                Layout.preferredWidth: 36
                Layout.preferredHeight: 3
                Layout.alignment: Qt.AlignVCenter

                Rectangle {
                    anchors.fill: parent
                    radius: 1.5
                    color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.06)
                }

                Rectangle {
                    anchors {
                        left: parent.left
                        top: parent.top
                        bottom: parent.bottom
                    }
                    width: parent.width * Math.max(0, Math.min(1, root.confidence / 100))
                    radius: 1.5
                    color: root.severityColor

                    Behavior on width { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
                    Behavior on color { ColorAnimation { duration: 200 } }
                }
            }

            Text {
                text: root.confidence + "%"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Math.round(9 * root.fontScale)
                font.weight: Font.Bold
                color: Theme.Tokens.steel
                Layout.alignment: Qt.AlignVCenter
            }

            Item { Layout.fillWidth: true }

            // "Coach" brand mark
            Text {
                text: "Coach"
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: Math.round(10 * root.fontScale)
                font.weight: Font.DemiBold
                font.italic: true
                color: Qt.rgba(Theme.Tokens.racingPurple.r,
                               Theme.Tokens.racingPurple.g,
                               Theme.Tokens.racingPurple.b, 0.5)
                Layout.alignment: Qt.AlignVCenter
            }
        }
    }
}
