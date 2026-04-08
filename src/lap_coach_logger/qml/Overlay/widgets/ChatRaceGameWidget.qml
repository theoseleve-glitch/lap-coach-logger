import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  ChatRaceGameWidget -- interactive race prediction game for streams (280x200).
    Shows prediction question, viewer entries, and results with points.
    Category: streaming -- uses racingPurple accent.                          */
Rectangle {
    id: root

    // -- font scale (driven by OverlayWidget parent) --
    property real fontScale: parent && parent.fontScale !== undefined ? parent.fontScale : 1.0
    width: 280
    height: 200
    color: "transparent"

    // -- public API ----------------------------------------------------------
    // [{user: string, pick: string, result: string, points: int}]
    property var    predictions: []
    property string question: "Who wins?"
    property bool   isActive: true

    // -- internal ------------------------------------------------------------
    readonly property var  _safePredictions: Array.isArray(predictions)
                                            ? predictions : []
    readonly property int  _count: _safePredictions.length
    readonly property string _safeQuestion: (question || "").length > 0
                                            ? question : "---"

    ColumnLayout {
        anchors {
            fill: parent
            topMargin: Theme.Tokens.sm
            bottomMargin: Theme.Tokens.sm
            leftMargin: Theme.Tokens.md - 2
            rightMargin: Theme.Tokens.md - 2
        }
        spacing: 0

        // -- Header ----------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.Tokens.xs + 2

            Text {
                text: "RACE GAME"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Math.round(9 * root.fontScale)
                font.weight: Font.Bold
                font.letterSpacing: 1.2
                color: Theme.Tokens.steel
            }

            // Active badge (pulsing when live)
            Rectangle {
                implicitWidth: activeLbl.implicitWidth + Theme.Tokens.sm
                implicitHeight: 14
                radius: 3
                color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.15)
                border.width: 1
                border.color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.30)

                SequentialAnimation on opacity {
                    running: root.isActive
                    loops: Animation.Infinite
                    NumberAnimation { from: 1.0; to: 0.5; duration: 900 }
                    NumberAnimation { from: 0.5; to: 1.0; duration: 900 }
                }

                Text {
                    id: activeLbl
                    anchors.centerIn: parent
                    text: root.isActive ? "LIVE" : "ENDED"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Math.round(7 * root.fontScale)
                    font.weight: Font.Bold
                    color: Theme.Tokens.racingPurple
                }
            }

            Item { Layout.fillWidth: true }

            Text {
                text: root._count + " picks"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Math.round(8 * root.fontScale)
                color: Theme.Tokens.steel
                opacity: 0.6
            }
        }

        // -- Separator -------------------------------------------------------
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.Tokens.xs + 2
            Rectangle {
                anchors.centerIn: parent
                width: parent.width; height: 1
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.5;
                                   color: Theme.Tokens.subtle(Theme.Tokens.racingPurple, 0.12) }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }

        // -- Question --------------------------------------------------------
        Text {
            Layout.fillWidth: true
            text: root._safeQuestion
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Theme.Typography.captionSize
            font.weight: Font.Bold
            color: Theme.Tokens.chalk
            elide: Text.ElideRight
            opacity: root.isActive ? _questionPulse : 1.0

            property real _questionPulse: 1.0
            SequentialAnimation on _questionPulse {
                running: root.isActive
                loops: Animation.Infinite
                NumberAnimation { from: 1.0; to: 0.7; duration: 1200 }
                NumberAnimation { from: 0.7; to: 1.0; duration: 1200 }
            }
        }

        // -- Empty state -----------------------------------------------------
        Text {
            visible: root._count === 0
            Layout.fillWidth: true
            Layout.fillHeight: true
            text: "No predictions yet"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Theme.Typography.microSize
            color: Theme.Tokens.steel
            opacity: 0.5
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        // -- Predictions list ------------------------------------------------
        ListView {
            id: predList
            visible: root._count > 0
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 2
            model: root._count

            delegate: PredictionRow {
                required property int index
                width: predList.width
                entry: root._safePredictions[index] || ({})
            }
        }
    }

    // -- PredictionRow component (inline) ------------------------------------
    component PredictionRow: RowLayout {
        property var entry: ({})
        spacing: Theme.Tokens.xs

        readonly property string _user:   (entry && entry.user)   || "???"
        readonly property string _pick:   (entry && entry.pick)   || ""
        readonly property string _result: (entry && entry.result) || ""
        readonly property int    _points: (entry && entry.points !== undefined)
                                          ? entry.points : 0

        Text {
            text: _user
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Math.round(9 * root.fontScale)
            font.weight: Font.Bold
            color: Theme.Tokens.racingPurple
            Layout.preferredWidth: 70
            elide: Text.ElideRight
        }

        Text {
            text: _pick
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Math.round(9 * root.fontScale)
            color: Theme.Tokens.chalk
            Layout.fillWidth: true
            elide: Text.ElideRight
        }

        Text {
            text: _result === "correct" ? "+" + _points
                : _result === "wrong"   ? "0"
                : "..."
            font.family: Theme.Typography.monoFamily
            font.pixelSize: Math.round(9 * root.fontScale)
            font.weight: Font.Bold
            color: _result === "correct" ? Theme.Tokens.acidGreen
                 : _result === "wrong"   ? Theme.Tokens.safetyRed
                 : Theme.Tokens.steel
            Layout.preferredWidth: 28
            horizontalAlignment: Text.AlignRight
        }
    }
}
