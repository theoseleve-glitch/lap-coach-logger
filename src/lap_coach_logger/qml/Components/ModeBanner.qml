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

    anchors.horizontalCenter: parent.horizontalCenter
    width: Math.min(parent.width - 48, 520)
    height: bannerCol.implicitHeight + 32
    radius: Theme.Tokens.radiusLg
    color: Theme.Tokens.elevated
    border.width: 1
    border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.25)
    z: 100
    visible: y > -height

    // Slide animation
    y: bannerVisible ? 16 : -height - 8
    Behavior on y {
        NumberAnimation {
            duration: 300
            easing.type: Easing.OutCubic
        }
    }

    // Subtle shadow
    Rectangle {
        anchors.fill: parent
        anchors.margins: -1
        radius: parent.radius + 1
        color: "transparent"
        border.width: 1
        border.color: Qt.rgba(0, 0, 0, 0.4)
        z: -1
    }

    ColumnLayout {
        id: bannerCol
        anchors {
            left: parent.left
            right: parent.right
            top: parent.top
            margins: 16
        }
        spacing: 12

        // "Session Detected" label
        Text {
            text: "SESSION DETECTED"
            font.family: Theme.Typography.monoFamily
            font.pixelSize: 10
            font.weight: Font.Bold
            font.letterSpacing: 1.5
            color: Theme.Tokens.pitOrange
        }

        // Session description
        Text {
            text: root.detectedSession || "Connecting..."
            font.family: Theme.Typography.bodyFamily
            font.pixelSize: 14
            font.weight: Font.DemiBold
            color: Theme.Tokens.chalk
            Layout.fillWidth: true
            elide: Text.ElideRight
        }

        // Mode buttons row
        RowLayout {
            spacing: 6
            Layout.fillWidth: true

            Repeater {
                model: ["sprint", "endurance", "coaching", "data"]

                delegate: Rectangle {
                    id: modeBtn
                    required property string modelData
                    readonly property bool isActive: root.activeMode === modelData

                    Layout.fillWidth: true
                    height: 30
                    radius: Theme.Tokens.radiusSm
                    color: isActive ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.15)
                                    : Theme.Tokens.subtle(Theme.Tokens.chalk, 0.04)
                    border.width: isActive ? 1 : 0
                    border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.40)

                    scale: modeBtnArea.pressed ? Theme.Motion.pressScale
                         : modeBtnArea.containsMouse ? Theme.Motion.hoverScale
                         : 1.0

                    Behavior on scale {
                        NumberAnimation {
                            duration: modeBtnArea.pressed ? Theme.Motion.pressDuration
                                                         : Theme.Motion.hoverDuration
                            easing.type: Easing.OutBack
                        }
                    }

                    Text {
                        anchors.centerIn: parent
                        text: modeBtn.modelData.toUpperCase()
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: 10
                        font.weight: Font.Bold
                        font.letterSpacing: 0.8
                        color: modeBtn.isActive ? Theme.Tokens.pitOrange : Theme.Tokens.steel
                    }

                    MouseArea {
                        id: modeBtnArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.modeSelected(modeBtn.modelData)
                    }
                }
            }
        }

        // Continue button
        Rectangle {
            Layout.fillWidth: true
            height: 34
            radius: Theme.Tokens.radiusSm
            color: continueBtnArea.containsMouse
                   ? Qt.darker(Theme.Tokens.pitOrange, 1.1)
                   : Theme.Tokens.pitOrange

            scale: continueBtnArea.pressed ? Theme.Motion.pressScale : 1.0

            Behavior on scale {
                NumberAnimation {
                    duration: Theme.Motion.pressDuration
                    easing.type: Easing.OutBack
                }
            }

            Text {
                anchors.centerIn: parent
                text: "CONTINUE"
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: 12
                font.weight: Font.Bold
                font.letterSpacing: 1
                color: Theme.Tokens.void_
            }

            MouseArea {
                id: continueBtnArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.dismissed()
            }
        }
    }
}
