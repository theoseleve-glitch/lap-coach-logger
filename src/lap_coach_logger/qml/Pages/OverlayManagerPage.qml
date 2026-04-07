import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "../Theme" as Theme
import "../Components" as Components

Item {
    id: root

    // ── Data model for overlay widgets ──
    ListModel {
        id: overlayItemsModel

        ListElement {
            widgetId: "delta_timing"
            name: "Delta / Timing"
            category: "timing"
            description: "Real-time lap delta vs personal best, sector splits, and current lap time. The core timing widget for tracking your improvement lap-by-lap."
        }
        ListElement {
            widgetId: "inputs_grip"
            name: "Inputs / Grip"
            category: "inputs"
            description: "Live throttle, brake, and steering inputs with G-force visualisation. Detects lockups, wheelspin, and rates input smoothness in real time."
        }
        ListElement {
            widgetId: "fuel_strategy"
            name: "Fuel Strategy"
            category: "strategy"
            description: "Fuel level, consumption per lap, and remaining laps estimate. Provides BOX/SAVE/TIGHT/SAFE state indicators to guide pit strategy."
        }
        ListElement {
            widgetId: "coaching"
            name: "Coaching Alerts"
            category: "awareness"
            description: "Context-aware coaching cards with braking, throttle, and cornering advice. Shows severity, confidence, and sector-specific tips during your session."
        }
        ListElement {
            widgetId: "gforce_meter"
            name: "G-Force Meter"
            category: "inputs"
            description: "Dedicated lateral and longitudinal G-force display. Visualises the grip circle to help you find the limit under braking and cornering."
        }
        ListElement {
            widgetId: "lap_timing"
            name: "Lap Timing"
            category: "timing"
            description: "Compact lap time display showing last lap, best lap, and the gap between them. A minimal timing reference for quick glances."
        }
        ListElement {
            widgetId: "track_map"
            name: "Track Map"
            category: "awareness"
            description: "Top-down track outline with your live position marker. Highlights sector boundaries and flags trouble spots from your coaching feed."
        }
        ListElement {
            widgetId: "standings"
            name: "Standings"
            category: "awareness"
            description: "Horizontal standings showing nearby cars, gaps, and positions. Useful for online races and monitoring traffic during practice."
        }
        ListElement {
            widgetId: "weather"
            name: "Weather"
            category: "awareness"
            description: "Track and ambient temperature, grip level, and weather forecast. Helps anticipate changing conditions that affect tyre performance."
        }
        ListElement {
            widgetId: "laptime_graph"
            name: "Lap Time Graph"
            category: "timing"
            description: "Bar chart of recent lap times. Fastest lap highlighted in gold, current lap in white. Quickly spot trends and consistency across your stint."
        }
        ListElement {
            widgetId: "laptime_log"
            name: "Lap Time Log"
            category: "timing"
            description: "Scrollable list of completed laps with time, delta, and status. A compact table view of your full session history at a glance."
        }
        ListElement {
            widgetId: "laptime_spread"
            name: "Lap Time Spread"
            category: "timing"
            description: "Horizontal range bar showing the spread between your fastest and slowest laps. Includes average and current time markers for consistency tracking."
        }
        ListElement {
            widgetId: "session_timer"
            name: "Session Timer"
            category: "awareness"
            description: "Simple session elapsed time display with session type badge (Practice, Qualifying, Race) and optional remaining time countdown."
        }
        ListElement {
            widgetId: "delta_bar"
            name: "Delta Bar"
            category: "timing"
            description: "Horizontal bar showing delta vs best lap. Green extends left when faster, red extends right when slower. A quick visual reference for live pace."
        }
        ListElement {
            widgetId: "flags"
            name: "Flags"
            category: "awareness"
            description: "Current flag status displayed as a large coloured panel. Supports green, yellow, red, blue, white, and checkered flags for instant recognition."
        }
        ListElement {
            widgetId: "digiflag"
            name: "Digital Flag"
            category: "awareness"
            description: "Digital marshal post indicator with flag symbol, sector number, and optional message. Compact flag display with sector-specific context."
        }
        ListElement {
            widgetId: "radar"
            name: "Radar"
            category: "awareness"
            description: "Top-down proximity radar showing nearby cars as dots around your centre car icon. Range-configurable canvas display for spatial awareness."
        }
        ListElement {
            widgetId: "radar_bars"
            name: "Radar Bars"
            category: "awareness"
            description: "Horizontal proximity bars showing how close cars are on your left and right. Bars shift to red when a car enters the danger zone."
        }
        ListElement {
            widgetId: "blind_spot"
            name: "Blind Spot"
            category: "awareness"
            description: "Simple left/right blind spot indicators. Rectangles flash red when a car is alongside, giving instant awareness of cars in your mirrors."
        }
        ListElement {
            widgetId: "overtake_alert"
            name: "Overtake Alert"
            category: "awareness"
            description: "Animated OVERTAKE or DEFEND alert with direction arrow and car number. Flashes to grab attention during close racing situations."
        }
        ListElement {
            widgetId: "relatives"
            name: "Relatives"
            category: "awareness"
            description: "Cars sorted by track position relative to you. Shows gap, name, position, and class colour for quick situational awareness in traffic."
        }
        ListElement {
            widgetId: "standings_table"
            name: "Standings Table"
            category: "awareness"
            description: "Full race standings with position, driver name, gap to leader, last lap time, and class badge. Your row highlighted for quick reference."
        }
        ListElement {
            widgetId: "leaderboard"
            name: "Leaderboard"
            category: "awareness"
            description: "Simplified leaderboard with alternating row backgrounds, podium-highlighted position badges, and gap to leader for each driver."
        }
        ListElement {
            widgetId: "head_to_head"
            name: "Head to Head"
            category: "awareness"
            description: "Side-by-side comparison of two drivers. Shows sector times, lap times, and top speed with colour-coded faster/slower indicators."
        }
        ListElement {
            widgetId: "track_map_canvas"
            name: "Track Map (Canvas)"
            category: "awareness"
            description: "Canvas-based track outline with live car position dot and nearby car markers. Draws from normalised track points or falls back to a placeholder oval."
        }
        ListElement {
            widgetId: "mini_map"
            name: "Mini Map"
            category: "awareness"
            description: "Compact track outline with car position dot. A smaller, label-free version of the track map for minimal screen space usage."
        }
        ListElement {
            widgetId: "flat_map"
            name: "Flat Map"
            category: "awareness"
            description: "Horizontal flattened track strip with car position marker and sector boundary lines. A linear view of your progress around the circuit."
        }
        ListElement {
            widgetId: "fuel_calculator"
            name: "Fuel Calculator"
            category: "strategy"
            description: "Extended fuel info showing current level, consumption rate, laps remaining, fuel to add at pit stop, stint length and target laps."
        }
        ListElement {
            widgetId: "pitbox_helper"
            name: "Pitbox Helper"
            category: "strategy"
            description: "Pit stop planning assistant showing estimated pit entry lap, fuel to add, tyre change recommendation, estimated pit time, and pit window status."
        }
        ListElement {
            widgetId: "weather_monitor"
            name: "Weather Monitor"
            category: "awareness"
            description: "Track conditions display with air and track temperature, humidity, wind speed and direction, rain probability, and surface state (dry/damp/wet)."
        }
        ListElement {
            widgetId: "boost_box"
            name: "Boost Box"
            category: "inputs"
            description: "ERS/KERS boost level arc gauge showing available energy, deployment mode (deploy/harvest/off), and percentage remaining."
        }
        ListElement {
            widgetId: "gforce_meter_full"
            name: "G-Force Meter (Full)"
            category: "inputs"
            description: "Dedicated G-force circle visualisation with current G dot, historical trail, reference rings, and lateral/longitudinal axis labels."
        }
        ListElement {
            widgetId: "advanced_panel"
            name: "Advanced Panel"
            category: "inputs"
            description: "Multi-row configurable telemetry data panel. Grid of label+value pairs showing speed, RPM, gear, brake temp, tyre temp, fuel, position, and gap."
        }
        ListElement {
            widgetId: "data_blocks"
            name: "Data Blocks"
            category: "inputs"
            description: "Compact data blocks in a configurable grid layout. Each block displays a labeled value with optional colour coding for quick data scanning."
        }
        ListElement {
            widgetId: "race_schedule"
            name: "Race Schedule"
            category: "awareness"
            description: "Upcoming race sessions with time, series name, duration, and registration deadline. Highlights the next session for quick reference."
        }
        ListElement {
            widgetId: "world_map"
            name: "World Map"
            category: "awareness"
            description: "Simplified world map outline showing the current track location as a glowing dot. Displays track name and coordinates for geographic context."
        }
        ListElement {
            widgetId: "heart_rate"
            name: "Heart Rate"
            category: "inputs"
            description: "Heart rate display with BPM number, pulse sparkline animation, and zone indicator (rest/warm/cardio/max). Monitor driver biometrics in real time."
        }
        ListElement {
            widgetId: "input_telemetry"
            name: "Input Telemetry"
            category: "inputs"
            description: "Detailed input view with throttle, brake, and clutch vertical bars, steering angle arc, gear display, and RPM bar. Full pedal and wheel overview."
        }
        ListElement {
            widgetId: "chat"
            name: "Stream Chat"
            category: "streaming"
            description: "Live chat display for streaming. Dark scrolling text area with colour-coded usernames, timestamps, and auto-scroll to latest messages."
        }
        ListElement {
            widgetId: "chat_highlight"
            name: "Chat Highlight"
            category: "streaming"
            description: "Single highlighted chat message for stream display. Large text with username colour accent, fade in/out animation, and streaming indicator."
        }
    }

    property int selectedIndex: 0

    function categoryColor(cat) {
        switch (cat) {
            case "timing":    return Theme.Tokens.pitOrange
            case "inputs":    return Theme.Tokens.acidGreen
            case "strategy":  return Theme.Tokens.marshalYellow
            case "awareness": return Theme.Tokens.racingPurple
            case "streaming": return Theme.Tokens.racingPurple
            default:          return Theme.Tokens.steel
        }
    }

    function widgetEnabled(wid) {
        if (!overlayVM || !overlayVM.widgetSettings) return false
        var s = overlayVM.widgetSettings[wid]
        return s ? s.enabled : false
    }

    function selectedWidget() {
        if (selectedIndex < 0 || selectedIndex >= overlayItemsModel.count) return null
        return overlayItemsModel.get(selectedIndex)
    }

    function selectedSettings() {
        var w = selectedWidget()
        if (!w || !overlayVM || !overlayVM.widgetSettings) return null
        return overlayVM.widgetSettings[w.widgetId] || null
    }

    // Background
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: Theme.Tokens.void_ }
            GradientStop { position: 0.5; color: Theme.Tokens.surface }
            GradientStop { position: 1.0; color: "#030405" }
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ════════════════════════════════════════════
        // LEFT SIDEBAR (280px)
        // ════════════════════════════════════════════
        Rectangle {
            Layout.preferredWidth: 280
            Layout.fillHeight: true
            color: Theme.Tokens.surface

            // Right border
            Rectangle {
                anchors { top: parent.top; bottom: parent.bottom; right: parent.right }
                width: 1
                color: Theme.Tokens.subtle(Theme.Tokens.chalk)
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Theme.Tokens.lg
                spacing: Theme.Tokens.md

                // ── Header ──
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.Tokens.sm

                    Text {
                        text: "OVERLAYS"
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: Theme.Typography.microSize
                        font.weight: Theme.Typography.microWeight
                        font.letterSpacing: 2
                        color: Theme.Tokens.steel
                    }

                    // Count badge
                    Rectangle {
                        width: 22
                        height: 16
                        radius: 8
                        color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.15)

                        Text {
                            anchors.centerIn: parent
                            text: overlayItemsModel.count
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: 9
                            font.weight: Font.Bold
                            color: Theme.Tokens.pitOrange
                        }
                    }

                    Item { Layout.fillWidth: true }
                }

                // ── Search bar ──
                Components.SearchBar {
                    id: searchBar
                    Layout.fillWidth: true
                    placeholder: "Search overlays..."

                    onSearchTextChanged: function(searchText) {
                        filterModel(searchText)
                    }
                }

                // ── Scrollable overlay list ──
                ListView {
                    id: overlayList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 2
                    model: overlayItemsModel

                    delegate: Rectangle {
                        id: listItem
                        required property int index
                        required property string widgetId
                        required property string name
                        required property string category

                        width: overlayList.width
                        height: 44
                        radius: Theme.Tokens.radiusSm
                        color: {
                            if (root.selectedIndex === index)
                                return Theme.Tokens.subtle(Theme.Tokens.chalk, 0.06)
                            if (itemArea.containsMouse)
                                return Theme.Tokens.subtle(Theme.Tokens.chalk, 0.04)
                            return "transparent"
                        }

                        Behavior on color {
                            ColorAnimation { duration: Theme.Motion.hoverDuration }
                        }

                        // Selected indicator (left border accent)
                        Rectangle {
                            anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
                            width: 3
                            radius: 1.5
                            color: root.selectedIndex === index
                                   ? root.categoryColor(category)
                                   : "transparent"
                            visible: root.selectedIndex === index
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: Theme.Tokens.md
                            anchors.rightMargin: Theme.Tokens.sm
                            spacing: Theme.Tokens.sm

                            // Category color square
                            Rectangle {
                                width: 10
                                height: 10
                                radius: 2
                                color: root.categoryColor(category)
                                opacity: 0.8
                            }

                            // Widget name
                            Text {
                                Layout.fillWidth: true
                                text: name
                                font.family: Theme.Typography.bodyFamily
                                font.pixelSize: 13
                                color: root.selectedIndex === index
                                       ? Theme.Tokens.chalk
                                       : Theme.Tokens.steel
                                elide: Text.ElideRight
                            }

                            // Toggle switch
                            Components.ToggleSwitch {
                                checked: root.widgetEnabled(widgetId)
                                onToggled: function(val) {
                                    if (overlayVM) overlayVM.toggleWidget(widgetId)
                                }
                            }
                        }

                        MouseArea {
                            id: itemArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            // Avoid capturing clicks on the toggle
                            propagateComposedEvents: true
                            onClicked: function(mouse) {
                                root.selectedIndex = index
                                if (overlayVM) overlayVM.selectWidget(widgetId)
                            }
                        }
                    }
                }
            }
        }

        // ════════════════════════════════════════════
        // CENTER AREA (fill)
        // ════════════════════════════════════════════
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ScrollView {
                anchors.fill: parent
                clip: true
                contentWidth: availableWidth

                ColumnLayout {
                    id: centerCol
                    width: parent.width
                    spacing: Theme.Tokens.xl

                    Item { height: Theme.Tokens.xl }

                    // ── Widget title ──
                    ColumnLayout {
                        Layout.leftMargin: Theme.Tokens.xxxl
                        Layout.rightMargin: Theme.Tokens.xxxl
                        spacing: Theme.Tokens.sm

                        Text {
                            text: {
                                var w = root.selectedWidget()
                                return w ? w.name : ""
                            }
                            font.family: Theme.Typography.displayFamily
                            font.pixelSize: Theme.Typography.titleSize
                            font.weight: Theme.Typography.titleWeight
                            color: Theme.Tokens.chalk
                        }

                        Text {
                            Layout.fillWidth: true
                            text: {
                                var w = root.selectedWidget()
                                return w ? w.description : ""
                            }
                            font.family: Theme.Typography.bodyFamily
                            font.pixelSize: 13
                            color: Theme.Tokens.steel
                            wrapMode: Text.WordWrap
                        }
                    }

                    // ── Preview placeholder ──
                    Rectangle {
                        Layout.leftMargin: Theme.Tokens.xxxl
                        Layout.rightMargin: Theme.Tokens.xxxl
                        Layout.fillWidth: true
                        Layout.preferredHeight: 220
                        radius: Theme.Tokens.radiusMd
                        color: Theme.Tokens.void_
                        border.width: 2
                        border.color: {
                            var w = root.selectedWidget()
                            return w ? Theme.Tokens.subtle(root.categoryColor(w.category), 0.25)
                                     : Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08)
                        }

                        Text {
                            anchors.centerIn: parent
                            text: "PREVIEW"
                            font.family: Theme.Typography.monoFamily
                            font.pixelSize: Theme.Typography.microSize
                            font.weight: Theme.Typography.microWeight
                            font.letterSpacing: 3
                            color: Theme.Tokens.subtle(Theme.Tokens.steel, 0.40)
                        }
                    }

                    // ── Section header: WIDGET SETTINGS ──
                    Text {
                        Layout.leftMargin: Theme.Tokens.xxxl
                        Layout.topMargin: Theme.Tokens.md
                        text: "WIDGET SETTINGS"
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: Theme.Typography.microSize
                        font.weight: Theme.Typography.microWeight
                        font.letterSpacing: 2
                        color: Theme.Tokens.steel
                    }

                    // ── Settings panel ──
                    Rectangle {
                        Layout.leftMargin: Theme.Tokens.xxxl
                        Layout.rightMargin: Theme.Tokens.xxxl
                        Layout.fillWidth: true
                        implicitHeight: settingsCol.implicitHeight + Theme.Tokens.xl * 2
                        radius: Theme.Tokens.radiusMd
                        color: Theme.Tokens.elevated

                        ColumnLayout {
                            id: settingsCol
                            anchors {
                                left: parent.left
                                right: parent.right
                                top: parent.top
                                margins: Theme.Tokens.xl
                            }
                            spacing: Theme.Tokens.lg

                            // ── Width slider ──
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: Theme.Tokens.xs

                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        text: "Width"
                                        font.family: Theme.Typography.bodyFamily
                                        font.pixelSize: 13
                                        color: Theme.Tokens.chalk
                                    }
                                    Item { Layout.fillWidth: true }
                                    Text {
                                        text: {
                                            var s = root.selectedSettings()
                                            return s ? Math.round(widthSlider.value) + " px" : "--"
                                        }
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: 12
                                        color: Theme.Tokens.pitOrange
                                    }
                                }

                                Slider {
                                    id: widthSlider
                                    Layout.fillWidth: true
                                    from: 200; to: 800; stepSize: 10
                                    value: {
                                        var s = root.selectedSettings()
                                        return s ? s.width : 320
                                    }
                                    onMoved: {
                                        var w = root.selectedWidget()
                                        if (w && overlayVM) overlayVM.setWidgetSetting(w.widgetId, "width", Math.round(value))
                                    }

                                    background: Rectangle {
                                        x: widthSlider.leftPadding
                                        y: widthSlider.topPadding + widthSlider.availableHeight / 2 - height / 2
                                        width: widthSlider.availableWidth
                                        height: 4
                                        radius: 2
                                        color: Theme.Tokens.raised

                                        Rectangle {
                                            width: widthSlider.visualPosition * parent.width
                                            height: parent.height
                                            radius: 2
                                            color: Theme.Tokens.pitOrange
                                        }
                                    }

                                    handle: Rectangle {
                                        x: widthSlider.leftPadding + widthSlider.visualPosition * (widthSlider.availableWidth - width)
                                        y: widthSlider.topPadding + widthSlider.availableHeight / 2 - height / 2
                                        width: 16; height: 16; radius: 8
                                        color: widthSlider.pressed ? Theme.Tokens.chalk : Theme.Tokens.pitOrange
                                        border.width: 2
                                        border.color: Theme.Tokens.elevated
                                    }
                                }
                            }

                            // ── Height slider ──
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: Theme.Tokens.xs

                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        text: "Height"
                                        font.family: Theme.Typography.bodyFamily
                                        font.pixelSize: 13
                                        color: Theme.Tokens.chalk
                                    }
                                    Item { Layout.fillWidth: true }
                                    Text {
                                        text: {
                                            var s = root.selectedSettings()
                                            return s ? Math.round(heightSlider.value) + " px" : "--"
                                        }
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: 12
                                        color: Theme.Tokens.pitOrange
                                    }
                                }

                                Slider {
                                    id: heightSlider
                                    Layout.fillWidth: true
                                    from: 100; to: 500; stepSize: 10
                                    value: {
                                        var s = root.selectedSettings()
                                        return s ? s.height : 200
                                    }
                                    onMoved: {
                                        var w = root.selectedWidget()
                                        if (w && overlayVM) overlayVM.setWidgetSetting(w.widgetId, "height", Math.round(value))
                                    }

                                    background: Rectangle {
                                        x: heightSlider.leftPadding
                                        y: heightSlider.topPadding + heightSlider.availableHeight / 2 - height / 2
                                        width: heightSlider.availableWidth
                                        height: 4
                                        radius: 2
                                        color: Theme.Tokens.raised

                                        Rectangle {
                                            width: heightSlider.visualPosition * parent.width
                                            height: parent.height
                                            radius: 2
                                            color: Theme.Tokens.pitOrange
                                        }
                                    }

                                    handle: Rectangle {
                                        x: heightSlider.leftPadding + heightSlider.visualPosition * (heightSlider.availableWidth - width)
                                        y: heightSlider.topPadding + heightSlider.availableHeight / 2 - height / 2
                                        width: 16; height: 16; radius: 8
                                        color: heightSlider.pressed ? Theme.Tokens.chalk : Theme.Tokens.pitOrange
                                        border.width: 2
                                        border.color: Theme.Tokens.elevated
                                    }
                                }
                            }

                            // ── Font scale slider ──
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: Theme.Tokens.xs

                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        text: "Font Scale"
                                        font.family: Theme.Typography.bodyFamily
                                        font.pixelSize: 13
                                        color: Theme.Tokens.chalk
                                    }
                                    Item { Layout.fillWidth: true }
                                    Text {
                                        text: {
                                            var s = root.selectedSettings()
                                            return s ? fontScaleSlider.value.toFixed(1) + "x" : "--"
                                        }
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: 12
                                        color: Theme.Tokens.pitOrange
                                    }
                                }

                                Slider {
                                    id: fontScaleSlider
                                    Layout.fillWidth: true
                                    from: 0.7; to: 1.5; stepSize: 0.1
                                    value: {
                                        var s = root.selectedSettings()
                                        return s ? s.font_scale : 1.0
                                    }
                                    onMoved: {
                                        var w = root.selectedWidget()
                                        if (w && overlayVM) overlayVM.setWidgetSetting(w.widgetId, "font_scale", value)
                                    }

                                    background: Rectangle {
                                        x: fontScaleSlider.leftPadding
                                        y: fontScaleSlider.topPadding + fontScaleSlider.availableHeight / 2 - height / 2
                                        width: fontScaleSlider.availableWidth
                                        height: 4
                                        radius: 2
                                        color: Theme.Tokens.raised

                                        Rectangle {
                                            width: fontScaleSlider.visualPosition * parent.width
                                            height: parent.height
                                            radius: 2
                                            color: Theme.Tokens.pitOrange
                                        }
                                    }

                                    handle: Rectangle {
                                        x: fontScaleSlider.leftPadding + fontScaleSlider.visualPosition * (fontScaleSlider.availableWidth - width)
                                        y: fontScaleSlider.topPadding + fontScaleSlider.availableHeight / 2 - height / 2
                                        width: 16; height: 16; radius: 8
                                        color: fontScaleSlider.pressed ? Theme.Tokens.chalk : Theme.Tokens.pitOrange
                                        border.width: 2
                                        border.color: Theme.Tokens.elevated
                                    }
                                }
                            }

                            // ── Opacity slider ──
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: Theme.Tokens.xs

                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        text: "Opacity"
                                        font.family: Theme.Typography.bodyFamily
                                        font.pixelSize: 13
                                        color: Theme.Tokens.chalk
                                    }
                                    Item { Layout.fillWidth: true }
                                    Text {
                                        text: {
                                            var s = root.selectedSettings()
                                            return s ? Math.round(opacitySlider.value * 100) + "%" : "--"
                                        }
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: 12
                                        color: Theme.Tokens.pitOrange
                                    }
                                }

                                Slider {
                                    id: opacitySlider
                                    Layout.fillWidth: true
                                    from: 0.3; to: 1.0; stepSize: 0.01
                                    value: {
                                        var s = root.selectedSettings()
                                        return s ? s.opacity : 0.92
                                    }
                                    onMoved: {
                                        var w = root.selectedWidget()
                                        if (w && overlayVM) overlayVM.setWidgetSetting(w.widgetId, "opacity", value)
                                    }

                                    background: Rectangle {
                                        x: opacitySlider.leftPadding
                                        y: opacitySlider.topPadding + opacitySlider.availableHeight / 2 - height / 2
                                        width: opacitySlider.availableWidth
                                        height: 4
                                        radius: 2
                                        color: Theme.Tokens.raised

                                        Rectangle {
                                            width: opacitySlider.visualPosition * parent.width
                                            height: parent.height
                                            radius: 2
                                            color: Theme.Tokens.pitOrange
                                        }
                                    }

                                    handle: Rectangle {
                                        x: opacitySlider.leftPadding + opacitySlider.visualPosition * (opacitySlider.availableWidth - width)
                                        y: opacitySlider.topPadding + opacitySlider.availableHeight / 2 - height / 2
                                        width: 16; height: 16; radius: 8
                                        color: opacitySlider.pressed ? Theme.Tokens.chalk : Theme.Tokens.pitOrange
                                        border.width: 2
                                        border.color: Theme.Tokens.elevated
                                    }
                                }
                            }

                            // ── Refresh rate dropdown ──
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: Theme.Tokens.xs

                                Text {
                                    text: "Refresh Rate"
                                    font.family: Theme.Typography.bodyFamily
                                    font.pixelSize: 13
                                    color: Theme.Tokens.chalk
                                }

                                RowLayout {
                                    spacing: Theme.Tokens.sm

                                    Repeater {
                                        model: [30, 60]

                                        delegate: Rectangle {
                                            required property int modelData

                                            width: 64; height: 30
                                            radius: Theme.Tokens.radiusSm
                                            color: {
                                                var s = root.selectedSettings()
                                                var active = s && s.refresh_hz === modelData
                                                return active
                                                    ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.15)
                                                    : Theme.Tokens.raised
                                            }
                                            border.width: 1
                                            border.color: {
                                                var s = root.selectedSettings()
                                                var active = s && s.refresh_hz === modelData
                                                return active
                                                    ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.30)
                                                    : Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08)
                                            }

                                            Text {
                                                anchors.centerIn: parent
                                                text: modelData + " Hz"
                                                font.family: Theme.Typography.monoFamily
                                                font.pixelSize: 12
                                                font.weight: Font.DemiBold
                                                color: {
                                                    var s = root.selectedSettings()
                                                    var active = s && s.refresh_hz === modelData
                                                    return active ? Theme.Tokens.pitOrange : Theme.Tokens.steel
                                                }
                                            }

                                            MouseArea {
                                                anchors.fill: parent
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: {
                                                    var w = root.selectedWidget()
                                                    if (w && overlayVM) overlayVM.setWidgetSetting(w.widgetId, "refresh_hz", modelData)
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            // ── Border radius slider ──
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: Theme.Tokens.xs

                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        text: "Border Radius"
                                        font.family: Theme.Typography.bodyFamily
                                        font.pixelSize: 13
                                        color: Theme.Tokens.chalk
                                    }
                                    Item { Layout.fillWidth: true }
                                    Text {
                                        text: {
                                            var s = root.selectedSettings()
                                            return s ? Math.round(borderRadiusSlider.value) + " px" : "--"
                                        }
                                        font.family: Theme.Typography.monoFamily
                                        font.pixelSize: 12
                                        color: Theme.Tokens.pitOrange
                                    }
                                }

                                Slider {
                                    id: borderRadiusSlider
                                    Layout.fillWidth: true
                                    from: 0; to: 20; stepSize: 1
                                    value: {
                                        var s = root.selectedSettings()
                                        return s ? (s.border_radius !== undefined ? s.border_radius : 12) : 12
                                    }
                                    onMoved: {
                                        var w = root.selectedWidget()
                                        if (w && overlayVM) overlayVM.setWidgetSetting(w.widgetId, "border_radius", Math.round(value))
                                    }

                                    background: Rectangle {
                                        x: borderRadiusSlider.leftPadding
                                        y: borderRadiusSlider.topPadding + borderRadiusSlider.availableHeight / 2 - height / 2
                                        width: borderRadiusSlider.availableWidth
                                        height: 4
                                        radius: 2
                                        color: Theme.Tokens.raised

                                        Rectangle {
                                            width: borderRadiusSlider.visualPosition * parent.width
                                            height: parent.height
                                            radius: 2
                                            color: Theme.Tokens.pitOrange
                                        }
                                    }

                                    handle: Rectangle {
                                        x: borderRadiusSlider.leftPadding + borderRadiusSlider.visualPosition * (borderRadiusSlider.availableWidth - width)
                                        y: borderRadiusSlider.topPadding + borderRadiusSlider.availableHeight / 2 - height / 2
                                        width: 16; height: 16; radius: 8
                                        color: borderRadiusSlider.pressed ? Theme.Tokens.chalk : Theme.Tokens.pitOrange
                                        border.width: 2
                                        border.color: Theme.Tokens.elevated
                                    }
                                }
                            }

                            // ── Reset button ──
                            Item { height: Theme.Tokens.sm }

                            Rectangle {
                                Layout.alignment: Qt.AlignLeft
                                width: resetLabel.implicitWidth + Theme.Tokens.xl * 2
                                height: 32
                                radius: Theme.Tokens.radiusSm
                                color: resetArea.containsMouse
                                       ? Theme.Tokens.subtle(Theme.Tokens.safetyRed, 0.12)
                                       : Theme.Tokens.subtle(Theme.Tokens.chalk, 0.04)
                                border.width: 1
                                border.color: resetArea.containsMouse
                                              ? Theme.Tokens.subtle(Theme.Tokens.safetyRed, 0.25)
                                              : Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08)

                                Text {
                                    id: resetLabel
                                    anchors.centerIn: parent
                                    text: "Reset to Defaults"
                                    font.family: Theme.Typography.bodyFamily
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                    color: resetArea.containsMouse
                                           ? Theme.Tokens.safetyRed
                                           : Theme.Tokens.steel
                                }

                                MouseArea {
                                    id: resetArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        var w = root.selectedWidget()
                                        if (w && overlayVM) overlayVM.resetWidget(w.widgetId)
                                    }
                                }
                            }
                        }
                    }

                    // Bottom padding
                    Item { height: Theme.Tokens.xxxl }
                }
            }
        }
    }

    // ── Search filter helper (hides non-matching items) ──
    function filterModel(searchText) {
        // Simple approach: reset visibility on all items via the list
        // (QML ListModel doesn't support filtering natively, so we just
        // change selectedIndex when search narrows things down.)
        // For now, select first matching item.
        if (searchText.length === 0) return

        var lower = searchText.toLowerCase()
        for (var i = 0; i < overlayItemsModel.count; i++) {
            var item = overlayItemsModel.get(i)
            if (item.name.toLowerCase().indexOf(lower) !== -1) {
                root.selectedIndex = i
                overlayList.positionViewAtIndex(i, ListView.Center)
                return
            }
        }
    }
}
