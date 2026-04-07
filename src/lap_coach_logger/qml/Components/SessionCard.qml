import QtQuick
import QtQuick.Layouts
import "../Theme" as Theme

Rectangle {
    id: root

    property string simName: ""
    property string track: ""
    property string metadata: ""
    property string bestLap: ""
    property string grade: ""
    property color gradeColor: Theme.Tokens.steel

    signal clicked()
    signal contextMenuRequested(real x, real y)

    // Derived sim badge properties
    readonly property string simAbbr: {
        switch (simName) {
        case "iRacing":          return "iR"
        case "ACC":              return "AC"
        case "Assetto Corsa":    return "AC"
        case "Le Mans Ultimate": return "LM"
        default:                 return simName.substring(0, 2).toUpperCase()
        }
    }
    readonly property color simColor: {
        switch (simName) {
        case "iRacing":          return Theme.Tokens.pitOrange
        case "ACC":              return Theme.Tokens.racingPurple
        case "Assetto Corsa":    return Theme.Tokens.racingPurple
        case "Le Mans Ultimate": return Theme.Tokens.acidGreen
        default:                 return Theme.Tokens.steel
        }
    }

    implicitWidth: cardRow.implicitWidth + 40
    implicitHeight: cardRow.implicitHeight + 36
    radius: Theme.Tokens.radiusLg
    color: Theme.Tokens.surface
    border.width: 1
    border.color: hoverArea.containsMouse
                  ? Theme.Tokens.medium(Theme.Tokens.chalk)
                  : Theme.Tokens.subtle(Theme.Tokens.chalk)

    scale: hoverArea.containsMouse ? 1.005 : 1.0

    Behavior on border.color {
        ColorAnimation { duration: Theme.Motion.focusDuration }
    }
    Behavior on scale {
        NumberAnimation { duration: Theme.Motion.focusDuration }
    }

    MouseArea {
        id: hoverArea
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton

        onClicked: function(mouse) {
            if (mouse.button === Qt.RightButton)
                root.contextMenuRequested(mouse.x, mouse.y)
            else
                root.clicked()
        }
    }

    RowLayout {
        id: cardRow
        anchors {
            fill: parent
            topMargin: 18
            bottomMargin: 18
            leftMargin: 20
            rightMargin: 20
        }
        spacing: 20

        // Sim badge
        Rectangle {
            width: 40
            height: 40
            radius: Theme.Tokens.radiusMd
            color: Qt.rgba(root.simColor.r, root.simColor.g, root.simColor.b, 0.10)
            border.width: 1
            border.color: Qt.rgba(root.simColor.r, root.simColor.g, root.simColor.b, 0.20)

            Text {
                anchors.centerIn: parent
                text: root.simAbbr
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                font.weight: Font.Bold
                color: root.simColor
            }
        }

        // Track + metadata
        Column {
            Layout.fillWidth: true
            spacing: Theme.Tokens.xs

            Text {
                text: root.track
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: 15
                font.weight: Font.DemiBold
                color: Theme.Tokens.chalk
                elide: Text.ElideRight
                width: parent.width
            }

            Text {
                text: root.metadata
                font.family: Theme.Typography.bodyFamily
                font.pixelSize: Theme.Typography.captionSize
                color: Theme.Tokens.steel
                elide: Text.ElideRight
                width: parent.width
            }
        }

        // Best lap
        Column {
            Layout.minimumWidth: 120
            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
            spacing: 2

            Text {
                anchors.right: parent.right
                text: root.bestLap
                font.family: Theme.Typography.monoFamily
                font.pixelSize: 18
                font.weight: Font.Bold
                color: Theme.Tokens.chalk
            }

            Text {
                anchors.right: parent.right
                text: "best lap"
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                color: Theme.Tokens.steel
            }
        }

        // Grade badge
        Rectangle {
            visible: root.grade !== ""
            implicitWidth: gradeText.implicitWidth + 20
            implicitHeight: gradeText.implicitHeight + 8
            radius: Theme.Tokens.radiusSm
            color: Qt.rgba(root.gradeColor.r, root.gradeColor.g, root.gradeColor.b, 0.10)
            border.width: 1
            border.color: Qt.rgba(root.gradeColor.r, root.gradeColor.g, root.gradeColor.b, 0.20)

            Text {
                id: gradeText
                anchors.centerIn: parent
                text: root.grade
                font.family: Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.microSize
                font.weight: Font.Bold
                color: root.gradeColor
            }
        }

        // Chevron
        Text {
            text: "\u203A"
            font.pixelSize: 16
            color: "#646464"
            Layout.alignment: Qt.AlignVCenter
        }
    }
}
