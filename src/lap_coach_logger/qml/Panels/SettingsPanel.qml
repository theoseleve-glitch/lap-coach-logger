import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../Theme" as Theme
import "../Components" as Components

Flickable {
    id: root

    signal showDiagnostics()

    contentHeight: mainColumn.implicitHeight + 40
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    ColumnLayout {
        id: mainColumn
        anchors {
            left: parent.left
            right: parent.right
            top: parent.top
            leftMargin: 24
            rightMargin: 24
            topMargin: 20
        }
        spacing: Theme.Tokens.lg

        // ── GENERAL ──────────────────────────────────────
        Text {
            text: "GENERAL"
            font.family: Theme.Typography.bodyFamily
            font.pixelSize: Theme.Typography.microSize
            font.weight: Theme.Typography.microWeight
            font.letterSpacing: 2
            color: Theme.Tokens.pitOrange
            Layout.bottomMargin: -2
        }

        // Output directory
        ColumnLayout {
            spacing: 6
            Layout.fillWidth: true

            Text {
                text: "Output directory"
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: Theme.Typography.captionSize
                color: Theme.Tokens.steel
            }

            RowLayout {
                spacing: Theme.Tokens.sm
                Layout.fillWidth: true

                Rectangle {
                    Layout.fillWidth: true
                    height: 36
                    radius: Theme.Tokens.radiusSm
                    color: Theme.Tokens.raised

                    TextInput {
                        id: outputDirInput
                        anchors {
                            fill: parent
                            leftMargin: Theme.Tokens.md
                            rightMargin: Theme.Tokens.md
                        }
                        verticalAlignment: TextInput.AlignVCenter
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: Theme.Typography.captionSize
                        color: Theme.Tokens.chalk
                        text: settingsVM ? settingsVM.getString("output_directory") : ""
                        onTextEdited: {
                            if (settingsVM)
                                settingsVM.setValue("output_directory", text)
                        }
                    }
                }

                Rectangle {
                    width: 72
                    height: 36
                    radius: Theme.Tokens.radiusSm
                    color: browseArea.containsMouse
                           ? Theme.Tokens.subtle(Theme.Tokens.chalk, 0.10)
                           : Theme.Tokens.subtle(Theme.Tokens.chalk)
                    border.width: 1
                    border.color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.12)

                    Text {
                        anchors.centerIn: parent
                        text: "Browse"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: Theme.Typography.captionSize
                        color: Theme.Tokens.steel
                    }

                    MouseArea {
                        id: browseArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            // Placeholder — file dialog will be wired later
                        }
                    }
                }
            }
        }

        // Driver name
        ColumnLayout {
            spacing: 6
            Layout.fillWidth: true

            Text {
                text: "Driver name"
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: Theme.Typography.captionSize
                color: Theme.Tokens.steel
            }

            Rectangle {
                Layout.fillWidth: true
                height: 36
                radius: Theme.Tokens.radiusSm
                color: Theme.Tokens.raised

                TextInput {
                    id: driverNameInput
                    anchors {
                        fill: parent
                        leftMargin: Theme.Tokens.md
                        rightMargin: Theme.Tokens.md
                    }
                    verticalAlignment: TextInput.AlignVCenter
                    font.family: Theme.Typography.bodyFamily
                    font.pixelSize: Theme.Typography.captionSize
                    color: Theme.Tokens.chalk

                    property string placeholder: "Optional \u2014 written into session bundles"
                    Text {
                        visible: !driverNameInput.text && !driverNameInput.activeFocus
                        text: driverNameInput.placeholder
                        font: driverNameInput.font
                        color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.30)
                        anchors.verticalCenter: parent.verticalCenter
                    }

                    text: settingsVM ? settingsVM.getString("driver_name") : ""
                    onTextEdited: {
                        if (settingsVM)
                            settingsVM.setValue("driver_name", text)
                    }
                }
            }
        }

        // Start with Windows
        RowLayout {
            spacing: Theme.Tokens.md
            Layout.fillWidth: true

            Text {
                text: "Start with Windows"
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: 13
                color: Theme.Tokens.chalk
                Layout.fillWidth: true
            }

            Components.ToggleSwitch {
                id: startWithWinToggle
                checked: settingsVM ? settingsVM.getBool("start_with_windows") : false
                onToggled: function(val) {
                    if (settingsVM)
                        settingsVM.setValue("start_with_windows", val)
                }
            }
        }

        // ── RECORDING ────────────────────────────────────
        Text {
            text: "RECORDING"
            font.family: Theme.Typography.bodyFamily
            font.pixelSize: Theme.Typography.microSize
            font.weight: Theme.Typography.microWeight
            font.letterSpacing: 2
            color: Theme.Tokens.pitOrange
            Layout.topMargin: Theme.Tokens.sm
            Layout.bottomMargin: -2
        }

        RowLayout {
            spacing: Theme.Tokens.lg
            Layout.fillWidth: true

            // Sample rate
            ColumnLayout {
                spacing: 6
                Layout.fillWidth: true

                Text {
                    text: "Sample rate"
                    font.family: Theme.Typography.bodyFamily
                    font.pixelSize: Theme.Typography.captionSize
                    color: Theme.Tokens.steel
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 36
                    radius: Theme.Tokens.radiusSm
                    color: Theme.Tokens.raised

                    RowLayout {
                        anchors {
                            fill: parent
                            leftMargin: Theme.Tokens.md
                            rightMargin: Theme.Tokens.md
                        }

                        TextInput {
                            id: sampleRateInput
                            Layout.fillWidth: true
                            verticalAlignment: TextInput.AlignVCenter
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.captionSize
                            color: Theme.Tokens.chalk
                            text: settingsVM ? String(settingsVM.getFloat("sample_rate_hz")) : "10"
                            validator: DoubleValidator { bottom: 0.1; top: 120.0 }
                            onTextEdited: {
                                if (settingsVM)
                                    settingsVM.setValue("sample_rate_hz", parseFloat(text))
                            }
                        }

                        Text {
                            text: "Hz"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.captionSize
                            color: Theme.Tokens.steel
                        }
                    }
                }
            }

            // Detection poll
            ColumnLayout {
                spacing: 6
                Layout.fillWidth: true

                Text {
                    text: "Detection poll"
                    font.family: Theme.Typography.bodyFamily
                    font.pixelSize: Theme.Typography.captionSize
                    color: Theme.Tokens.steel
                }

                Rectangle {
                    Layout.fillWidth: true
                    height: 36
                    radius: Theme.Tokens.radiusSm
                    color: Theme.Tokens.raised

                    RowLayout {
                        anchors {
                            fill: parent
                            leftMargin: Theme.Tokens.md
                            rightMargin: Theme.Tokens.md
                        }

                        TextInput {
                            id: pollIntervalInput
                            Layout.fillWidth: true
                            verticalAlignment: TextInput.AlignVCenter
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.captionSize
                            color: Theme.Tokens.chalk
                            text: settingsVM ? String(settingsVM.getFloat("poll_interval_s")) : "3"
                            validator: DoubleValidator { bottom: 0.5; top: 60.0 }
                            onTextEdited: {
                                if (settingsVM)
                                    settingsVM.setValue("poll_interval_s", parseFloat(text))
                            }
                        }

                        Text {
                            text: "s"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.captionSize
                            color: Theme.Tokens.steel
                        }
                    }
                }
            }
        }

        // ── SIMULATORS ───────────────────────────────────
        Text {
            text: "SIMULATORS"
            font.family: Theme.Typography.bodyFamily
            font.pixelSize: Theme.Typography.microSize
            font.weight: Theme.Typography.microWeight
            font.letterSpacing: 2
            color: Theme.Tokens.pitOrange
            Layout.topMargin: Theme.Tokens.sm
            Layout.bottomMargin: -2
        }

        Repeater {
            model: [
                { label: "iRacing", key: "enable_iracing" },
                { label: "ACC", key: "enable_acc" },
                { label: "Assetto Corsa", key: "enable_assetto_corsa" },
                { label: "Le Mans Ultimate", key: "enable_lmu" }
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
                        checked: settingsVM ? settingsVM.getBool(modelData.key) : false
                        onToggled: function(val) {
                            if (settingsVM)
                                settingsVM.setValue(modelData.key, val)
                        }
                    }
                }
            }
        }

        // ── DIAGNOSTICS LINK ─────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.topMargin: Theme.Tokens.sm
            height: 56
            radius: Theme.Tokens.radiusMd
            color: diagArea.containsMouse
                   ? Theme.Tokens.subtle(Theme.Tokens.chalk, 0.10)
                   : Theme.Tokens.subtle(Theme.Tokens.chalk)
            border.width: 1
            border.color: Theme.Tokens.subtle(Theme.Tokens.chalk, 0.12)

            RowLayout {
                anchors {
                    fill: parent
                    leftMargin: 14
                    rightMargin: 14
                }

                ColumnLayout {
                    spacing: 2
                    Layout.fillWidth: true

                    Text {
                        text: "Diagnostics"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                        color: Theme.Tokens.chalk
                    }

                    Text {
                        text: "Logs, health, support bundle"
                        font.family: Theme.Typography.bodyFamily
                        font.pixelSize: 11
                        color: Theme.Tokens.steel
                    }
                }

                Text {
                    text: "\u203A"
                    font.pixelSize: 20
                    color: Theme.Tokens.steel
                }
            }

            MouseArea {
                id: diagArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.showDiagnostics()
            }
        }

        // ── SAVE BUTTON ─────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.topMargin: Theme.Tokens.lg
            Layout.bottomMargin: 20
            height: 44
            radius: Theme.Tokens.radiusMd
            color: saveArea.containsPress
                   ? Qt.darker(Theme.Tokens.pitOrange, 1.2)
                   : saveArea.containsMouse
                     ? Qt.lighter(Theme.Tokens.pitOrange, 1.1)
                     : Theme.Tokens.pitOrange

            Behavior on color {
                ColorAnimation { duration: Theme.Motion.hoverDuration }
            }

            Text {
                anchors.centerIn: parent
                text: "Save Settings"
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: Theme.Typography.bodySize
                font.weight: Font.DemiBold
                color: Theme.Tokens.chalk
            }

            MouseArea {
                id: saveArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    if (settingsVM)
                        settingsVM.save()
                }
            }
        }
    }
}
