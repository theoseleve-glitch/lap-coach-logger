import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  RelativesWidget — relative position list (280 x 240).
    Cars sorted by track position relative to player. Shows
    gap, name/number, and position change indicators.           */
Rectangle {
    id: root
    width: 280
    height: 240
    color: "transparent"

    // ── public API ──────────────────────────────────────────────────
    // [{position, name, gap, isPlayer, classColor}]
    property var relatives: []

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: 10
            bottomMargin: 10
            leftMargin: 12
            rightMargin: 12
        }
        spacing: 4

        // ── Header ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Text {
                text: "RELATIVE"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            Item { Layout.fillWidth: true }

            Text {
                text: {
                    var list = root.relatives || []
                    return list.length + " cars"
                }
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 9
                color: Theme.Tokens.steel
                opacity: 0.7
            }
        }

        // ── Column headers ─────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 0

            Text {
                Layout.preferredWidth: 28
                text: "POS"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 8
                font.weight: Font.Bold
                font.letterSpacing: 0.8
                color: Theme.Tokens.steel
                opacity: 0.5
            }

            Text {
                Layout.fillWidth: true
                text: "DRIVER"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 8
                font.weight: Font.Bold
                font.letterSpacing: 0.8
                color: Theme.Tokens.steel
                opacity: 0.5
            }

            Text {
                Layout.preferredWidth: 60
                text: "GAP"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 8
                font.weight: Font.Bold
                font.letterSpacing: 0.8
                color: Theme.Tokens.steel
                opacity: 0.5
                horizontalAlignment: Text.AlignRight
            }
        }

        // Separator
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Qt.rgba(Theme.Tokens.chalk.r,
                           Theme.Tokens.chalk.g,
                           Theme.Tokens.chalk.b, 0.06)
        }

        // ── List ───────────────────────────────────────────────────
        ListView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 1
            model: root.relatives || []

            delegate: Rectangle {
                required property var modelData
                required property int index

                width: ListView.view ? ListView.view.width : 0
                height: 22
                radius: 3
                color: modelData.isPlayer
                       ? Qt.rgba(Theme.Tokens.acidGreen.r,
                                 Theme.Tokens.acidGreen.g,
                                 Theme.Tokens.acidGreen.b, 0.08)
                       : "transparent"

                RowLayout {
                    anchors {
                        fill: parent
                        leftMargin: 4
                        rightMargin: 4
                    }
                    spacing: 0

                    // Position
                    Text {
                        Layout.preferredWidth: 28
                        text: modelData.position !== undefined
                              ? modelData.position.toString() : ""
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: modelData.isPlayer
                               ? Theme.Tokens.acidGreen
                               : Theme.Tokens.chalk
                    }

                    // Class color bar
                    Rectangle {
                        Layout.preferredWidth: 3
                        Layout.preferredHeight: 14
                        radius: 1.5
                        color: modelData.classColor || Theme.Tokens.steel
                        opacity: 0.8
                    }

                    Item { width: 6 }

                    // Name
                    Text {
                        Layout.fillWidth: true
                        text: modelData.name || ""
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 11
                        color: modelData.isPlayer
                               ? Theme.Tokens.acidGreen
                               : Theme.Tokens.chalk
                        elide: Text.ElideRight
                    }

                    // Gap
                    Text {
                        Layout.preferredWidth: 60
                        text: modelData.gap || ""
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                        color: modelData.isPlayer
                               ? Theme.Tokens.acidGreen
                               : Theme.Tokens.pitOrange
                        horizontalAlignment: Text.AlignRight
                    }
                }
            }
        }
    }
}
