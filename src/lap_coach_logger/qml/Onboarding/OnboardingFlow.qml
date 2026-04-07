import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../Theme" as Theme
import "../Components" as Components

Item {
    id: root

    anchors.fill: parent
    visible: onboardingVM && !onboardingVM.completed
             && settingsVM && settingsVM.isFirstRun

    property int currentStep: 0

    // Dim overlay
    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(Theme.Tokens.void_.r,
                       Theme.Tokens.void_.g,
                       Theme.Tokens.void_.b, 0.95)

        MouseArea {
            anchors.fill: parent
            // Block clicks to content behind
        }
    }

    // Centered card
    Rectangle {
        id: card
        anchors.centerIn: parent
        width: Math.min(480, parent.width - 64)
        height: cardContent.implicitHeight + 64
        radius: Theme.Tokens.radiusXl
        color: Theme.Tokens.surface
        border.width: 1
        border.color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.10)

        Item {
            id: cardContent
            anchors {
                fill: parent
                margins: 32
            }
            implicitHeight: stepLoader.item ? stepLoader.item.implicitHeight : 300

            // Step content with crossfade
            Loader {
                id: stepLoader
                anchors.fill: parent
                sourceComponent: {
                    switch (root.currentStep) {
                    case 0: return welcomeStep
                    case 1: return simsStep
                    case 2: return readyStep
                    default: return welcomeStep
                    }
                }

                // Crossfade animation
                opacity: 1.0
                Behavior on opacity {
                    NumberAnimation { duration: 200; easing.type: Easing.InOutQuad }
                }
            }
        }
    }

    function goNext() {
        stepLoader.opacity = 0.0
        stepTimer.start()
    }

    Timer {
        id: stepTimer
        interval: 200
        repeat: false
        onTriggered: {
            root.currentStep++
            stepLoader.opacity = 1.0
        }
    }

    // ── Step 0: Welcome ──────────────────────────────
    Component {
        id: welcomeStep

        ColumnLayout {
            spacing: Theme.Tokens.lg

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "\uD83C\uDFC1"
                font.pixelSize: 32
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "Welcome to Lap Coach"
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: Theme.Typography.titleSize
                font.weight: Theme.Typography.titleWeight
                color: Theme.Tokens.chalk
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                Layout.fillWidth: true
                text: "Local-first telemetry capture. No cloud.\nNo account. Your data stays yours."
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: Theme.Typography.bodySize
                color: Theme.Tokens.steel
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                lineHeight: 1.4
            }

            Item { Layout.preferredHeight: Theme.Tokens.sm }

            Rectangle {
                Layout.fillWidth: true
                height: 44
                radius: Theme.Tokens.radiusMd
                color: welcomeBtnArea.containsPress
                       ? Qt.darker(Theme.Tokens.pitOrange, 1.2)
                       : welcomeBtnArea.containsMouse
                         ? Qt.lighter(Theme.Tokens.pitOrange, 1.1)
                         : Theme.Tokens.pitOrange

                Behavior on color {
                    ColorAnimation { duration: Theme.Motion.hoverDuration }
                }

                Text {
                    anchors.centerIn: parent
                    text: "Continue"
                    font.family: Theme.Typography.bodyFamily
                    font.pixelSize: Theme.Typography.bodySize
                    font.weight: Font.DemiBold
                    color: Theme.Tokens.chalk
                }

                MouseArea {
                    id: welcomeBtnArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.goNext()
                }
            }
        }
    }

    // ── Step 1: Simulators ───────────────────────────
    Component {
        id: simsStep

        ColumnLayout {
            spacing: Theme.Tokens.lg

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "Which sims do you drive?"
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: Theme.Typography.titleSize
                font.weight: Theme.Typography.titleWeight
                color: Theme.Tokens.chalk
            }

            Repeater {
                model: [
                    { label: "iRacing", key: "iracing" },
                    { label: "ACC", key: "acc" },
                    { label: "Assetto Corsa", key: "assetto_corsa" },
                    { label: "Le Mans Ultimate", key: "lmu" }
                ]

                delegate: Rectangle {
                    required property var modelData
                    required property int index

                    Layout.fillWidth: true
                    height: 44
                    radius: Theme.Tokens.radiusMd
                    color: Theme.Tokens.subtle(Theme.Tokens.chalk)
                    border.width: 1
                    border.color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.12)

                    RowLayout {
                        anchors {
                            fill: parent
                            leftMargin: 14
                            rightMargin: 14
                        }

                        Text {
                            text: modelData.label
                            font.family: Theme.Typography.bodyFamily
                            font.pixelSize: 13
                            color: Theme.Tokens.chalk
                            Layout.fillWidth: true
                        }

                        Components.ToggleSwitch {
                            checked: onboardingVM
                                     ? onboardingVM.sims.indexOf(modelData.key) !== -1
                                     : false
                            onToggled: function(val) {
                                if (onboardingVM)
                                    onboardingVM.toggleSim(modelData.key)
                            }
                        }
                    }
                }
            }

            Item { Layout.preferredHeight: Theme.Tokens.xs }

            Rectangle {
                Layout.fillWidth: true
                height: 44
                radius: Theme.Tokens.radiusMd
                color: simsBtnArea.containsPress
                       ? Qt.darker(Theme.Tokens.pitOrange, 1.2)
                       : simsBtnArea.containsMouse
                         ? Qt.lighter(Theme.Tokens.pitOrange, 1.1)
                         : Theme.Tokens.pitOrange

                Behavior on color {
                    ColorAnimation { duration: Theme.Motion.hoverDuration }
                }

                Text {
                    anchors.centerIn: parent
                    text: "Continue"
                    font.family: Theme.Typography.bodyFamily
                    font.pixelSize: Theme.Typography.bodySize
                    font.weight: Font.DemiBold
                    color: Theme.Tokens.chalk
                }

                MouseArea {
                    id: simsBtnArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.goNext()
                }
            }
        }
    }

    // ── Step 2: Ready ────────────────────────────────
    Component {
        id: readyStep

        ColumnLayout {
            spacing: Theme.Tokens.lg

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "\u2728"
                font.pixelSize: 32
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "You're all set"
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: Theme.Typography.titleSize
                font.weight: Theme.Typography.titleWeight
                color: Theme.Tokens.chalk
            }

            Text {
                Layout.alignment: Qt.AlignHCenter
                Layout.fillWidth: true
                text: "Start any sim and Lap Coach will begin\nrecording automatically."
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: Theme.Typography.bodySize
                color: Theme.Tokens.steel
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                lineHeight: 1.4
            }

            Item { Layout.preferredHeight: Theme.Tokens.sm }

            Rectangle {
                Layout.fillWidth: true
                height: 44
                radius: Theme.Tokens.radiusMd
                color: readyBtnArea.containsPress
                       ? Qt.darker(Theme.Tokens.pitOrange, 1.2)
                       : readyBtnArea.containsMouse
                         ? Qt.lighter(Theme.Tokens.pitOrange, 1.1)
                         : Theme.Tokens.pitOrange

                Behavior on color {
                    ColorAnimation { duration: Theme.Motion.hoverDuration }
                }

                Text {
                    anchors.centerIn: parent
                    text: "Get Started"
                    font.family: Theme.Typography.bodyFamily
                    font.pixelSize: Theme.Typography.bodySize
                    font.weight: Font.DemiBold
                    color: Theme.Tokens.chalk
                }

                MouseArea {
                    id: readyBtnArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (onboardingVM)
                            onboardingVM.finish()
                    }
                }
            }
        }
    }
}
