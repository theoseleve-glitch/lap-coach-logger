import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  CoachingWidget — live coaching advice overlay (290 px wide).
    Asymmetric-radius glass panel with severity accent, category / sector
    meta, headline + subtext, confidence bar, and a compact history list.  */
GlassSurface {
    id: root
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
        switch (severity) {
        case "caution":  return Theme.Tokens.marshalYellow
        case "critical": return Theme.Tokens.safetyRed
        default:         return Theme.Tokens.acidGreen
        }
    }

    // ── Critical top rule ──────────────────────────────────────────
    Rectangle {
        visible: root.severity === "critical"
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
                    if (root.category) parts.push(root.category.toUpperCase())
                    if (root.sector) parts.push(root.sector.toUpperCase())
                    return parts.join(" \u00B7 ")
                }
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: root.severityColor
                elide: Text.ElideRight
                Layout.fillWidth: true

                Behavior on color { ColorAnimation { duration: 200 } }
            }

            // Dismiss button
            Rectangle {
                width: 16; height: 16; radius: 4
                color: Qt.rgba(Theme.Tokens.chalk.r,
                               Theme.Tokens.chalk.g,
                               Theme.Tokens.chalk.b, 0.0)

                Text {
                    anchors.centerIn: parent
                    text: "\u00D7"   // multiplication sign (x)
                    font.pixelSize: 12
                    font.weight: Font.Bold
                    color: Theme.Tokens.steel
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    hoverEnabled: true
                    onEntered: parent.color = Qt.rgba(Theme.Tokens.chalk.r,
                                                      Theme.Tokens.chalk.g,
                                                      Theme.Tokens.chalk.b, 0.06)
                    onExited:  parent.color = "transparent"
                    onClicked: root.dismissed()
                }
            }
        }

        // ── Headline ───────────────────────────────────────────────
        Text {
            text: root.headline
            font.family: Theme.Typography.bodyFamily
            font.pixelSize: 19
            font.weight: Font.DemiBold
            color: Theme.Tokens.chalk
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            Layout.topMargin: 6
        }

        // ── Sub line ───────────────────────────────────────────────
        Text {
            visible: root.sub.length > 0
            text: root.sub
            font.family: Theme.Typography.bodyFamily
            font.pixelSize: 12
            color: Theme.Tokens.steel
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            Layout.topMargin: 2
        }

        // ── Confidence bar + "Coach" ───────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 10
            spacing: 8

            // Thin confidence bar
            Item {
                Layout.preferredWidth: 36
                Layout.preferredHeight: 3
                Layout.alignment: Qt.AlignVCenter

                Rectangle {
                    anchors.fill: parent
                    radius: 1.5
                    color: Qt.rgba(Theme.Tokens.chalk.r,
                                   Theme.Tokens.chalk.g,
                                   Theme.Tokens.chalk.b, 0.06)
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

                    Behavior on width { NumberAnimation { duration: 200 } }
                    Behavior on color { ColorAnimation { duration: 200 } }
                }
            }

            Text {
                text: root.confidence + "%"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                color: Theme.Tokens.steel
                Layout.alignment: Qt.AlignVCenter
            }

            Item { Layout.fillWidth: true }

            // "Coach" brand mark
            Text {
                text: "Coach"
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: 10
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
