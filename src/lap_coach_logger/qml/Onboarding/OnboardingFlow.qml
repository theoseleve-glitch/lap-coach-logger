import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../Theme" as Theme
import "../Components" as Components

Item {
    id: root
    anchors.fill: parent
    visible: !dismissed
    z: 1000

    property int currentStep: 0
    property bool dismissed: false

    // Dim overlay
    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(Theme.Tokens.void_.r,
                       Theme.Tokens.void_.g,
                       Theme.Tokens.void_.b, 0.95)
        MouseArea { anchors.fill: parent; enabled: root.visible }
    }

    // Centered card — z:1 so it receives clicks above the dim overlay
    Rectangle {
        z: 1
        anchors.centerIn: parent
        width: Math.min(480, parent.width - 64)
        implicitHeight: col.implicitHeight + 64
        radius: Theme.Tokens.radiusXl
        color: Theme.Tokens.surface
        border.width: 1
        border.color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.10)

        Column {
            id: col
            anchors {
                fill: parent
                margins: 32
            }
            spacing: Theme.Tokens.lg

            // ── Step 0: Welcome ──
            Column {
                visible: root.currentStep === 0
                width: parent.width
                spacing: Theme.Tokens.lg

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "\uD83C\uDFC1"
                    font.pixelSize: 32
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Welcome to Lap Coach"
                    font.family: Theme.Typography.bodyFamily
                    font.pixelSize: Theme.Typography.titleSize
                    font.weight: Font.Bold
                    color: Theme.Tokens.chalk
                }
                Text {
                    width: parent.width
                    text: "Local-first telemetry capture. No cloud.\nNo account. Your data stays yours."
                    font.family: Theme.Typography.bodyFamily
                    font.pixelSize: Theme.Typography.bodySize
                    color: Theme.Tokens.steel
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    lineHeight: 1.4
                }
                Item { width: 1; height: Theme.Tokens.sm }
                Rectangle {
                    width: parent.width
                    height: 44
                    radius: Theme.Tokens.radiusMd
                    color: ma0.pressed ? Qt.darker(Theme.Tokens.pitOrange, 1.2)
                         : ma0.containsMouse ? Qt.lighter(Theme.Tokens.pitOrange, 1.1)
                         : Theme.Tokens.pitOrange
                    Text {
                        anchors.centerIn: parent
                        text: "Continue"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.bodySize
                        font.weight: Font.DemiBold
                        color: Theme.Tokens.chalk
                    }
                    MouseArea {
                        id: ma0
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { root.currentStep = 1 }
                    }
                }
            }

            // ── Step 1: Simulators ──
            Column {
                visible: root.currentStep === 1
                width: parent.width
                spacing: Theme.Tokens.lg

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Which sims do you drive?"
                    font.family: Theme.Typography.bodyFamily
                    font.pixelSize: Theme.Typography.titleSize
                    font.weight: Font.Bold
                    color: Theme.Tokens.chalk
                }
                Column {
                    width: parent.width
                    spacing: Theme.Tokens.sm

                    Repeater {
                        model: ["iRacing", "ACC", "Assetto Corsa", "Le Mans Ultimate"]
                        delegate: Rectangle {
                            required property string modelData
                            width: parent.width
                            height: 44
                            radius: Theme.Tokens.radiusMd
                            color: Theme.Tokens.subtle(Theme.Tokens.chalk)
                            border.width: 1
                            border.color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.12)
                            Row {
                                anchors.fill: parent
                                anchors.leftMargin: 14
                                anchors.rightMargin: 14
                                spacing: Theme.Tokens.sm
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData
                                    font.family: Theme.Typography.bodyFamily
                                    font.pixelSize: 13
                                    color: Theme.Tokens.chalk
                                    width: parent.width - toggleSw.width - parent.spacing
                                }
                                Components.ToggleSwitch {
                                    id: toggleSw
                                    anchors.verticalCenter: parent.verticalCenter
                                    checked: modelData === "iRacing" || modelData === "ACC"
                                    onToggled: function(val) {
                                        if (onboardingVM)
                                            onboardingVM.toggleSim(modelData)
                                    }
                                }
                            }
                        }
                    }
                }
                Item { width: 1; height: Theme.Tokens.xs }
                Rectangle {
                    width: parent.width
                    height: 44
                    radius: Theme.Tokens.radiusMd
                    color: ma1.pressed ? Qt.darker(Theme.Tokens.pitOrange, 1.2)
                         : ma1.containsMouse ? Qt.lighter(Theme.Tokens.pitOrange, 1.1)
                         : Theme.Tokens.pitOrange
                    Text {
                        anchors.centerIn: parent
                        text: "Continue"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.bodySize
                        font.weight: Font.DemiBold
                        color: Theme.Tokens.chalk
                    }
                    MouseArea {
                        id: ma1
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: { root.currentStep = 2 }
                    }
                }
            }

            // ── Step 2: Ready ──
            Column {
                visible: root.currentStep === 2
                width: parent.width
                spacing: Theme.Tokens.lg

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "\u2728"
                    font.pixelSize: 32
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "You're all set"
                    font.family: Theme.Typography.bodyFamily
                    font.pixelSize: Theme.Typography.titleSize
                    font.weight: Font.Bold
                    color: Theme.Tokens.chalk
                }
                Text {
                    width: parent.width
                    text: "Start any sim and Lap Coach will begin\nrecording automatically."
                    font.family: Theme.Typography.bodyFamily
                    font.pixelSize: Theme.Typography.bodySize
                    color: Theme.Tokens.steel
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    lineHeight: 1.4
                }
                Item { width: 1; height: Theme.Tokens.sm }
                Rectangle {
                    width: parent.width
                    height: 44
                    radius: Theme.Tokens.radiusMd
                    color: ma2.pressed ? Qt.darker(Theme.Tokens.pitOrange, 1.2)
                         : ma2.containsMouse ? Qt.lighter(Theme.Tokens.pitOrange, 1.1)
                         : Theme.Tokens.pitOrange
                    Text {
                        anchors.centerIn: parent
                        text: "Get Started"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.bodySize
                        font.weight: Font.DemiBold
                        color: Theme.Tokens.chalk
                    }
                    MouseArea {
                        id: ma2
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (onboardingVM) onboardingVM.finish()
                            root.dismissed = true
                        }
                    }
                }
            }
        }
    }
}
