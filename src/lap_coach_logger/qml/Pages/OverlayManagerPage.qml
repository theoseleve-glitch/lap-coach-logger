import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "../Theme" as Theme
import "../Components" as Components
import "../Overlay/widgets" as Widgets

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
        ListElement {
            widgetId: "chat_race_game"
            name: "Race Prediction Game"
            category: "streaming"
            description: "Interactive race prediction game for stream viewers. Shows prediction question, viewer entries with picks, and results with point scores."
        }
        ListElement {
            widgetId: "chat_race_standing"
            name: "Prediction Standings"
            category: "streaming"
            description: "Streaming leaderboard showing viewer race prediction standings. Displays rank, player name, total points, and current win streak per round."
        }
        ListElement {
            widgetId: "custom_text"
            name: "Custom Text Banner"
            category: "streaming"
            description: "Customisable text banner for streams. Supports static or scrolling text with configurable font size and colour. Ideal for sponsor messages."
        }
        ListElement {
            widgetId: "custom_url"
            name: "Custom URL Content"
            category: "streaming"
            description: "Placeholder for loading custom URL content as a browser widget. Shows URL, label, and a custom content area for embedded web resources."
        }
        ListElement {
            widgetId: "garage_cover"
            name: "Garage Cover"
            category: "streaming"
            description: "Be right back and intermission screen with branding. Shows a customisable garage message, subtitle, logo placeholder, and breathing animation."
        }
        ListElement {
            widgetId: "mic_visualizer"
            name: "Mic Visualiser"
            category: "streaming"
            description: "Audio level visualiser with 16 vertical bars that react to microphone input. Configurable bar colour with active indicator for stream audio."
        }
        ListElement {
            widgetId: "promo_code_alert"
            name: "Promo Code Alert"
            category: "streaming"
            description: "Animated promo code display for sponsors. Shows sponsor name, large promo code with copy indicator, description, and pulsing border glow."
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
        if (!overlayVM) return false
        return overlayVM.isWidgetEnabled(wid)
    }

    function selectedWidget() {
        if (selectedIndex < 0 || selectedIndex >= overlayItemsModel.count) return null
        return overlayItemsModel.get(selectedIndex)
    }

    function selectedSettings() {
        var w = selectedWidget()
        if (!w || !overlayVM) return null
        return overlayVM.getWidgetSettingsMap(w.widgetId)
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

                // ── Presets ──
                Text {
                    text: "PRESETS"
                    font.family: Theme.Typography.monoFamily
                    font.pixelSize: Theme.Typography.microSize
                    font.weight: Theme.Typography.microWeight
                    font.letterSpacing: 2
                    color: Theme.Tokens.steel
                }

                Flow {
                    Layout.fillWidth: true
                    spacing: 4

                    Repeater {
                        model: overlayVM ? overlayVM.getPresetList() : []

                        delegate: Rectangle {
                            width: presetLabel.implicitWidth + 16
                            height: 26
                            radius: 6
                            color: presetArea.containsMouse
                                   ? Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.18)
                                   : Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.10)
                            border.width: 1
                            border.color: Theme.Tokens.subtle(Theme.Tokens.pitOrange, 0.20)

                            Behavior on color {
                                ColorAnimation { duration: Theme.Motion.hoverDuration }
                            }

                            Text {
                                id: presetLabel
                                anchors.centerIn: parent
                                text: modelData.name
                                font.family: Theme.Typography.monoFamily
                                font.pixelSize: 10
                                font.weight: Font.DemiBold
                                color: Theme.Tokens.pitOrange
                            }

                            MouseArea {
                                id: presetArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (overlayVM) overlayVM.loadPreset(modelData.id)
                                }
                            }
                        }
                    }
                }

                // ── Accent colour selector ──
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Text {
                        text: "ACCENT"
                        font.family: Theme.Typography.monoFamily
                        font.pixelSize: Theme.Typography.microSize
                        font.weight: Theme.Typography.microWeight
                        font.letterSpacing: 2
                        color: Theme.Tokens.steel
                    }

                    Repeater {
                        model: overlayVM ? overlayVM.getAccentOptions() : []

                        delegate: Rectangle {
                            width: 20; height: 20; radius: 10
                            color: modelData.hex
                            border.width: overlayVM && overlayVM.overlayAccent === modelData.id ? 2 : 0
                            border.color: Theme.Tokens.chalk

                            Behavior on border.width {
                                NumberAnimation { duration: Theme.Motion.hoverDuration }
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (overlayVM) overlayVM.setOverlayAccent(modelData.id)
                                }
                            }
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
                            z: -1  // behind toggle so it doesn't steal clicks
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

                    // ── Live widget preview ──
                    Rectangle {
                        Layout.leftMargin: Theme.Tokens.xxxl
                        Layout.rightMargin: Theme.Tokens.xxxl
                        Layout.fillWidth: true
                        Layout.preferredHeight: 220
                        radius: Theme.Tokens.radiusLg
                        color: Qt.rgba(0, 0, 0, 0.4)
                        clip: true
                        border.width: 1
                        border.color: {
                            var w = root.selectedWidget()
                            return w ? Theme.Tokens.subtle(root.categoryColor(w.category), 0.25)
                                     : Theme.Tokens.subtle(Theme.Tokens.chalk, 0.08)
                        }

                        // Scale down the widget to fit the preview
                        Item {
                            anchors.centerIn: parent
                            width: previewLoader.item ? previewLoader.item.implicitWidth || 300 : 300
                            height: previewLoader.item ? previewLoader.item.implicitHeight || 200 : 200
                            scale: Math.min(1.0, Math.min(
                                (parent.width - 40) / Math.max(1, width),
                                (parent.height - 20) / Math.max(1, height)
                            ))

                            Loader {
                                id: previewLoader
                                anchors.fill: parent
                                sourceComponent: root._previewComponent()
                            }
                        }

                        // Fallback label when no preview available
                        Text {
                            anchors.centerIn: parent
                            visible: !previewLoader.item
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

    // ================================================================
    //  Preview component resolver
    // ================================================================

    property var _previewMap: ({
        "delta_timing":       pvDeltaTiming,
        "inputs_grip":        pvInputsGrip,
        "fuel_strategy":      pvFuelStrategy,
        "coaching":           pvCoaching,
        "gforce_meter":       pvGforceMeter,
        "lap_timing":         pvLapTiming,
        "track_map":          pvTrackMap,
        "standings":          pvStandings,
        "weather":            pvWeather,
        "laptime_graph":      pvLaptimeGraph,
        "laptime_log":        pvLaptimeLog,
        "laptime_spread":     pvLaptimeSpread,
        "session_timer":      pvSessionTimer,
        "delta_bar":          pvDeltaBar,
        "flags":              pvFlags,
        "digiflag":           pvDigiflag,
        "radar":              pvRadar,
        "radar_bars":         pvRadarBars,
        "blind_spot":         pvBlindSpot,
        "overtake_alert":     pvOvertakeAlert,
        "relatives":          pvRelatives,
        "standings_table":    pvStandingsTable,
        "leaderboard":        pvLeaderboard,
        "head_to_head":       pvHeadToHead,
        "track_map_canvas":   pvTrackMapCanvas,
        "mini_map":           pvMiniMap,
        "flat_map":           pvFlatMap,
        "fuel_calculator":    pvFuelCalculator,
        "pitbox_helper":      pvPitboxHelper,
        "weather_monitor":    pvWeatherMonitor,
        "boost_box":          pvBoostBox,
        "gforce_meter_full":  pvGforceMeterFull,
        "advanced_panel":     pvAdvancedPanel,
        "data_blocks":        pvDataBlocks,
        "race_schedule":      pvRaceSchedule,
        "world_map":          pvWorldMap,
        "heart_rate":         pvHeartRate,
        "input_telemetry":    pvInputTelemetry,
        "chat":               pvChat,
        "chat_highlight":     pvChatHighlight,
        "chat_race_game":     pvChatRaceGame,
        "chat_race_standing": pvChatRaceStanding,
        "custom_text":        pvCustomText,
        "custom_url":         pvCustomUrl,
        "garage_cover":       pvGarageCover,
        "mic_visualizer":     pvMicVisualizer,
        "promo_code_alert":   pvPromoCodeAlert
    })

    function _previewComponent() {
        var w = selectedWidget()
        if (!w) return null
        return _previewMap[w.widgetId] || null
    }

    // ================================================================
    //  Preview Component blocks (no OverlayWidget wrapper)
    // ================================================================

    Component {
        id: pvDeltaTiming
        Widgets.DeltaTimeWidget {
            implicitWidth: 320; implicitHeight: 200
            delta: overlayVM ? overlayVM.liveDelta : 0
            lapTime: overlayVM ? overlayVM.currentLapTime || "0:00.000" : "0:00.000"
            bestTime: overlayVM ? overlayVM.bestTime || "\u2014" : "\u2014"
            lapNumber: overlayVM ? overlayVM.lapNumber : 0
            totalLaps: 0
            lapProgress: overlayVM ? overlayVM.lapProgress : 0
            sectors: overlayVM ? overlayVM.sectorStates || [] : []
        }
    }

    Component {
        id: pvInputsGrip
        Widgets.InputsWidget {
            implicitWidth: 240; implicitHeight: 260
            throttle: overlayVM ? overlayVM.throttlePct : 0
            brake: overlayVM ? overlayVM.brakePct : 0
            steering: overlayVM ? overlayVM.steeringDeg / 450.0 : 0
            gForceX: overlayVM ? overlayVM.latAccelG : 0
            gForceY: overlayVM ? overlayVM.longAccelG : 0
            lockup: overlayVM ? overlayVM.lockupActive : false
            wheelspin: overlayVM ? overlayVM.wheelspinActive : false
            smoothness: overlayVM ? overlayVM.inputSmoothness : 0.75
        }
    }

    Component {
        id: pvFuelStrategy
        Widgets.FuelWidget {
            implicitWidth: 180; implicitHeight: 240
            remaining: overlayVM ? overlayVM.fuelLevel : 0
            lapsLeft: overlayVM ? overlayVM.fuelLapsLeft : 0
            fuelPerLap: overlayVM ? overlayVM.fuelPerLap : 0
            state: overlayVM ? overlayVM.fuelState || "SAFE" : "SAFE"
            pitWindow: ""
            totalLaps: 0
            currentLap: overlayVM ? overlayVM.lapNumber : 0
        }
    }

    Component {
        id: pvCoaching
        Widgets.CoachingWidget {
            implicitWidth: 290; implicitHeight: 200
            headline: overlayVM ? overlayVM.coachingHeadline : ""
            sub: overlayVM ? overlayVM.coachingSub : ""
            category: overlayVM ? overlayVM.coachingCategory : ""
            severity: overlayVM ? overlayVM.coachingSeverity : "positive"
            confidence: overlayVM ? overlayVM.coachingConfidence : 0
            sector: overlayVM ? overlayVM.coachingSector : ""
        }
    }

    Component {
        id: pvGforceMeter
        Widgets.GForceMeterWidget {
            implicitWidth: 200; implicitHeight: 200
            latG: overlayVM ? overlayVM.latAccelG : 0
            longG: overlayVM ? overlayVM.longAccelG : 0
        }
    }

    Component {
        id: pvLapTiming
        Widgets.LapTimingWidget {
            implicitWidth: 280; implicitHeight: 120
            currentTime: overlayVM ? overlayVM.currentLapTime : ""
            lastTime: overlayVM ? overlayVM.lastTime : ""
            bestTime: overlayVM ? overlayVM.bestTime : ""
            deltaVsBest: overlayVM ? overlayVM.lastDelta : ""
        }
    }

    Component {
        id: pvTrackMap
        Widgets.TrackMapWidget {
            implicitWidth: 240; implicitHeight: 240
            carPosition: overlayVM ? overlayVM.lapDistPct : 0
        }
    }

    Component {
        id: pvStandings
        Widgets.StandingsWidget {
            implicitWidth: 300; implicitHeight: 300
        }
    }

    Component {
        id: pvWeather
        Widgets.WeatherMonitorWidget {
            implicitWidth: 200; implicitHeight: 160
        }
    }

    Component {
        id: pvLaptimeGraph
        Widgets.LaptimeGraphWidget {
            implicitWidth: 320; implicitHeight: 180
        }
    }

    Component {
        id: pvLaptimeLog
        Widgets.LaptimeLogWidget {
            implicitWidth: 280; implicitHeight: 200
        }
    }

    Component {
        id: pvLaptimeSpread
        Widgets.LaptimeSpreadWidget {
            implicitWidth: 300; implicitHeight: 160
        }
    }

    Component {
        id: pvSessionTimer
        Widgets.SessionTimerWidget {
            implicitWidth: 200; implicitHeight: 80
            elapsed: overlayVM ? overlayVM.elapsed || "0:00:00" : "0:00:00"
        }
    }

    Component {
        id: pvDeltaBar
        Widgets.DeltaBarWidget {
            implicitWidth: 300; implicitHeight: 60
            delta: overlayVM ? overlayVM.liveDelta : 0
        }
    }

    Component {
        id: pvFlags
        Widgets.FlagsWidget {
            implicitWidth: 160; implicitHeight: 100
        }
    }

    Component {
        id: pvDigiflag
        Widgets.DigiflagWidget {
            implicitWidth: 120; implicitHeight: 120
        }
    }

    Component {
        id: pvRadar
        Widgets.RadarWidget {
            implicitWidth: 200; implicitHeight: 200
        }
    }

    Component {
        id: pvRadarBars
        Widgets.RadarBarsWidget {
            implicitWidth: 200; implicitHeight: 120
        }
    }

    Component {
        id: pvBlindSpot
        Widgets.BlindSpotWidget {
            implicitWidth: 160; implicitHeight: 80
        }
    }

    Component {
        id: pvOvertakeAlert
        Widgets.OvertakeAlertWidget {
            implicitWidth: 240; implicitHeight: 60
        }
    }

    Component {
        id: pvRelatives
        Widgets.RelativesWidget {
            implicitWidth: 280; implicitHeight: 240
        }
    }

    Component {
        id: pvStandingsTable
        Widgets.StandingsWidget {
            implicitWidth: 280; implicitHeight: 300
        }
    }

    Component {
        id: pvLeaderboard
        Widgets.LeaderboardWidget {
            implicitWidth: 260; implicitHeight: 280
        }
    }

    Component {
        id: pvHeadToHead
        Widgets.HeadToHeadWidget {
            implicitWidth: 300; implicitHeight: 160
        }
    }

    Component {
        id: pvTrackMapCanvas
        Widgets.TrackMapWidget {
            implicitWidth: 240; implicitHeight: 240
            carPosition: overlayVM ? overlayVM.lapDistPct : 0
        }
    }

    Component {
        id: pvMiniMap
        Widgets.MiniMapWidget {
            implicitWidth: 180; implicitHeight: 180
            carPosition: overlayVM ? overlayVM.lapDistPct : 0
        }
    }

    Component {
        id: pvFlatMap
        Widgets.FlatMapWidget {
            implicitWidth: 300; implicitHeight: 100
            carPosition: overlayVM ? overlayVM.lapDistPct : 0
        }
    }

    Component {
        id: pvFuelCalculator
        Widgets.FuelCalculatorWidget {
            implicitWidth: 220; implicitHeight: 200
            fuelLevel: overlayVM ? overlayVM.fuelLevel : 0
            fuelPerLap: overlayVM ? overlayVM.fuelPerLap : 0
            lapsLeft: overlayVM ? overlayVM.fuelLapsLeft : 0
        }
    }

    Component {
        id: pvPitboxHelper
        Widgets.PitboxHelperWidget {
            implicitWidth: 240; implicitHeight: 160
        }
    }

    Component {
        id: pvWeatherMonitor
        Widgets.WeatherMonitorWidget {
            implicitWidth: 200; implicitHeight: 160
        }
    }

    Component {
        id: pvBoostBox
        Widgets.BoostBoxWidget {
            implicitWidth: 160; implicitHeight: 100
        }
    }

    Component {
        id: pvGforceMeterFull
        Widgets.GForceMeterWidget {
            implicitWidth: 200; implicitHeight: 200
            latG: overlayVM ? overlayVM.latAccelG : 0
            longG: overlayVM ? overlayVM.longAccelG : 0
        }
    }

    Component {
        id: pvAdvancedPanel
        Widgets.AdvancedPanelWidget {
            implicitWidth: 360; implicitHeight: 280
        }
    }

    Component {
        id: pvDataBlocks
        Widgets.DataBlocksWidget {
            implicitWidth: 320; implicitHeight: 200
        }
    }

    Component {
        id: pvRaceSchedule
        Widgets.RaceScheduleWidget {
            implicitWidth: 300; implicitHeight: 240
        }
    }

    Component {
        id: pvWorldMap
        Widgets.WorldMapWidget {
            implicitWidth: 280; implicitHeight: 160
            trackName: overlayVM ? overlayVM.track : ""
        }
    }

    Component {
        id: pvHeartRate
        Widgets.HeartRateWidget {
            implicitWidth: 180; implicitHeight: 100
        }
    }

    Component {
        id: pvInputTelemetry
        Widgets.InputTelemetryWidget {
            implicitWidth: 280; implicitHeight: 180
            throttle: overlayVM ? overlayVM.throttlePct : 0
            brake: overlayVM ? overlayVM.brakePct : 0
            steering: overlayVM ? overlayVM.steeringDeg / 450.0 : 0
            gear: overlayVM ? overlayVM.gear : 0
            rpm: overlayVM ? overlayVM.rpm : 0
        }
    }

    Component {
        id: pvChat
        Widgets.ChatWidget {
            implicitWidth: 280; implicitHeight: 200
        }
    }

    Component {
        id: pvChatHighlight
        Widgets.ChatHighlightWidget {
            implicitWidth: 320; implicitHeight: 80
        }
    }

    Component {
        id: pvChatRaceGame
        Widgets.ChatRaceGameWidget {
            implicitWidth: 280; implicitHeight: 200
        }
    }

    Component {
        id: pvChatRaceStanding
        Widgets.ChatRaceStandingWidget {
            implicitWidth: 260; implicitHeight: 240
        }
    }

    Component {
        id: pvCustomText
        Widgets.CustomTextWidget {
            implicitWidth: 280; implicitHeight: 60
        }
    }

    Component {
        id: pvCustomUrl
        Widgets.CustomUrlWidget {
            implicitWidth: 300; implicitHeight: 200
        }
    }

    Component {
        id: pvGarageCover
        Widgets.GarageCoverWidget {
            implicitWidth: 320; implicitHeight: 180
        }
    }

    Component {
        id: pvMicVisualizer
        Widgets.MicVisualizerWidget {
            implicitWidth: 200; implicitHeight: 60
        }
    }

    Component {
        id: pvPromoCodeAlert
        Widgets.PromoCodeAlertWidget {
            implicitWidth: 300; implicitHeight: 100
        }
    }
}
