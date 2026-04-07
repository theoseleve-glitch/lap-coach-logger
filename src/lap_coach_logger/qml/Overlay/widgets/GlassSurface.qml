import QtQuick
import "../../Theme" as Theme

/*  GlassSurface — shared glass-material container for all overlay widgets.
    Dark semi-transparent rectangle with thin border, top refraction highlight,
    and a default-property content slot.                                       */
Item {
    id: root

    property real radius: 12
    property real borderAlpha: 0.06
    property real surfaceAlpha: 0.78

    // Asymmetric radius support (coaching widget apex corner)
    property real topLeftRadius: radius
    property real topRightRadius: radius
    property real bottomLeftRadius: radius
    property real bottomRightRadius: radius

    // Content slot
    default property alias contentData: contentContainer.data

    // Background pane
    Rectangle {
        id: bg
        anchors.fill: parent
        radius: root.radius
        color: Qt.rgba(0, 0, 0, root.surfaceAlpha)

        border.width: 1
        border.color: Qt.rgba(Theme.Tokens.chalk.r,
                              Theme.Tokens.chalk.g,
                              Theme.Tokens.chalk.b,
                              root.borderAlpha)
    }

    // Top refraction highlight — 1px gradient strip
    Rectangle {
        id: refractionHighlight
        anchors {
            top: parent.top
            left: parent.left
            right: parent.right
            topMargin: 1
            leftMargin: root.radius
            rightMargin: root.radius
        }
        height: 1
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.35; color: Qt.rgba(Theme.Tokens.chalk.r,
                                                           Theme.Tokens.chalk.g,
                                                           Theme.Tokens.chalk.b, 0.09) }
            GradientStop { position: 0.65; color: Qt.rgba(Theme.Tokens.chalk.r,
                                                           Theme.Tokens.chalk.g,
                                                           Theme.Tokens.chalk.b, 0.12) }
            GradientStop { position: 1.0; color: "transparent" }
        }
    }

    // Content container
    Item {
        id: contentContainer
        anchors.fill: parent
    }
}
