import QtQuick
import QtQuick.Layouts
import "../../Theme" as Theme

/*  HeadToHeadWidget -- driver comparison panel (300 x 160).
    Side-by-side layout with center divider and "VS" badge.
    Each driver: name, lap time, 3 sector times, speed.
    Green/red highlighting for faster/slower values.
    Comparison rows extracted into inline component.              */
Rectangle {
    id: root
    width: 300
    height: 160
    color: "transparent"

    // -- public API ------------------------------------------------------
    // {name, time, sectors: [s1, s2, s3], speed}
    property var driver1: null
    property var driver2: null

    // -- null-safe driver accessors --------------------------------------
    readonly property var _d1: root.driver1 || _emptyDriver
    readonly property var _d2: root.driver2 || _emptyDriver

    readonly property var _emptyDriver: ({
        name: "", time: "", sectors: [], speed: 0
    })

    // -- comparison helper -----------------------------------------------
    function _fasterColor(v1, v2) {
        if (v1 === v2 || v1 === "" || v2 === "" ||
            v1 === undefined || v2 === undefined)
            return Theme.Tokens.chalk
        return v1 < v2 ? Theme.Tokens.acidGreen : Theme.Tokens.safetyRed
    }

    function _safeSector(driver, idx) {
        var sectors = driver ? driver.sectors : null
        if (!sectors || !Array.isArray(sectors) || idx >= sectors.length)
            return ""
        return sectors[idx]
    }

    function _safeSpeed(driver) {
        if (!driver || driver.speed === undefined || driver.speed === null)
            return 0
        return Number(driver.speed) || 0
    }

    function _safeTime(driver) {
        if (!driver || !driver.time) return ""
        return driver.time
    }

    function _safeName(driver, fallback) {
        if (!driver || !driver.name) return fallback
        return driver.name
    }

    // -- inline component: comparison row --------------------------------
    component ComparisonRow: RowLayout {
        id: _cmpRow

        required property string leftValue
        required property string rightValue
        required property string label
        property bool isSpeed: false

        Layout.fillWidth: true
        spacing: 0

        Text {
            Layout.fillWidth: true
            text: _cmpRow.leftValue || (_cmpRow.isSpeed ? "-- kph" : "--:--.---")
            font.family:    Theme.Typography.monoFamily
            font.pixelSize: _cmpRow.isSpeed ? Theme.Typography.microSize : 11
            font.weight:    _cmpRow.label === "LAP" ? Font.Bold : Font.Normal
            color: {
                if (_cmpRow.isSpeed) {
                    var l = parseFloat(_cmpRow.leftValue) || 0
                    var r = parseFloat(_cmpRow.rightValue) || 0
                    return l >= r ? Theme.Tokens.acidGreen : Theme.Tokens.safetyRed
                }
                return root._fasterColor(_cmpRow.leftValue, _cmpRow.rightValue)
            }
            Behavior on color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
        }

        Text {
            text: _cmpRow.label
            font.family:       Theme.Typography.monoFamily
            font.pixelSize:    8
            font.weight:       Font.Bold
            font.letterSpacing: _cmpRow.label.length <= 3 ? 1.0 : 0.8
            color: Theme.Tokens.steel
            opacity: 0.5
        }

        Text {
            Layout.fillWidth: true
            text: _cmpRow.rightValue || (_cmpRow.isSpeed ? "-- kph" : "--:--.---")
            font.family:    Theme.Typography.monoFamily
            font.pixelSize: _cmpRow.isSpeed ? Theme.Typography.microSize : 11
            font.weight:    _cmpRow.label === "LAP" ? Font.Bold : Font.Normal
            horizontalAlignment: Text.AlignRight
            color: {
                if (_cmpRow.isSpeed) {
                    var l2 = parseFloat(_cmpRow.leftValue) || 0
                    var r2 = parseFloat(_cmpRow.rightValue) || 0
                    return r2 >= l2 ? Theme.Tokens.acidGreen : Theme.Tokens.safetyRed
                }
                return root._fasterColor(_cmpRow.rightValue, _cmpRow.leftValue)
            }
            Behavior on color { ColorAnimation { duration: Theme.Motion.statusColorDuration } }
        }
    }

    // -- main layout -----------------------------------------------------
    ColumnLayout {
        anchors {
            fill: parent
            topMargin:    Theme.Tokens.sm
            bottomMargin: Theme.Tokens.sm
            leftMargin:   Theme.Tokens.md
            rightMargin:  Theme.Tokens.md
        }
        spacing: Theme.Tokens.sm

        // -- Title -------------------------------------------------------
        Text {
            text: "HEAD TO HEAD"
            font.family:       Theme.Typography.monoFamily
            font.pixelSize:    Theme.Typography.microSize
            font.weight:       Font.Bold
            font.letterSpacing: Theme.Typography.microSpacing
            color: Theme.Tokens.steel
        }

        // -- Driver names row with VS badge ------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 0

            Text {
                Layout.fillWidth: true
                text: root._safeName(root._d1, "Driver 1")
                font.family:    Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.captionSize
                font.weight:    Font.Bold
                color: Theme.Tokens.acidGreen
                elide: Text.ElideRight
            }

            // VS badge
            Rectangle {
                Layout.preferredWidth:  28
                Layout.preferredHeight: 16
                radius: 3
                color: Theme.Tokens.subtle(Theme.Tokens.steel, 0.12)

                Text {
                    anchors.centerIn: parent
                    text: "VS"
                    font.family:       Theme.Typography.monoFamily
                    font.pixelSize:    8
                    font.weight:       Font.Bold
                    font.letterSpacing: 1
                    color: Theme.Tokens.steel
                }
            }

            Text {
                Layout.fillWidth: true
                text: root._safeName(root._d2, "Driver 2")
                font.family:    Theme.Typography.monoFamily
                font.pixelSize: Theme.Typography.captionSize
                font.weight:    Font.Bold
                color: Theme.Tokens.pitOrange
                horizontalAlignment: Text.AlignRight
                elide: Text.ElideRight
            }
        }

        // -- Center divider ----------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.Tokens.subtle(Theme.Tokens.chalk)
        }

        // -- Lap time comparison -----------------------------------------
        ComparisonRow {
            leftValue:  root._safeTime(root._d1)
            rightValue: root._safeTime(root._d2)
            label: "LAP"
        }

        // -- Sector comparisons (S1, S2, S3) -----------------------------
        Repeater {
            model: 3

            ComparisonRow {
                required property int index

                leftValue: {
                    var v = root._safeSector(root._d1, index)
                    return v !== "" ? v.toString() : ""
                }
                rightValue: {
                    var v2 = root._safeSector(root._d2, index)
                    return v2 !== "" ? v2.toString() : ""
                }
                label: "S" + (index + 1)
            }
        }

        // -- Speed comparison --------------------------------------------
        ComparisonRow {
            readonly property real _spd1: root._safeSpeed(root._d1)
            readonly property real _spd2: root._safeSpeed(root._d2)

            leftValue:  _spd1 > 0 ? _spd1.toFixed(0) + " kph" : ""
            rightValue: _spd2 > 0 ? _spd2.toFixed(0) + " kph" : ""
            label:   "SPD"
            isSpeed: true
        }
    }
}
