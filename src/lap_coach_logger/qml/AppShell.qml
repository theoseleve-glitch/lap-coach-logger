import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Theme" as Theme
import "Components" as Components
import "Pages" as Pages
import "Panels" as Panels
import "Onboarding" as Onboarding
import "Overlay" as Overlay

Item {
    id: root

    // Page component map for tab switching
    readonly property var pageComponents: ({
        "dashboard": dashboardComponent,
        "live": liveComponent,
        "strategy": strategyComponent,
        "history": historyComponent,
        "overlays": overlaysComponent
    })

    property string currentPage: "dashboard"

    // === 1. NavBar ===
    Components.NavBar {
        id: navBar
        anchors {
            top: parent.top
            left: parent.left
            right: parent.right
        }
        currentPage: root.currentPage
        status: serviceVM.status
        statusDetail: serviceVM.statusDetail
        isMonitoring: serviceVM.isMonitoring
        elapsedFormatted: serviceVM.elapsedFormatted

        onPageRequested: function(pageId) {
            if (root.currentPage === pageId) return
            root.currentPage = pageId
            var component = root.pageComponents[pageId]
            if (component) {
                pageStack.replace(pageStack.currentItem, component, StackView.Transition)
            }
        }

        onSettingsRequested: {
            settingsSlideOver.isOpen = true
        }

        onPauseRequested: {
            serviceVM.pauseMonitoring()
        }

        onOverlayToggleRequested: {
            root.toggleOverlay()
        }

        onResumeRequested: {
            serviceVM.resumeMonitoring()
        }
    }

    // === 2. StackView ===
    StackView {
        id: pageStack
        anchors {
            top: navBar.bottom
            left: parent.left
            right: parent.right
            bottom: statusBar.top
        }
        initialItem: dashboardComponent

        // --- Replace transitions (tab switching) ---
        replaceEnter: Transition {
            ParallelAnimation {
                NumberAnimation {
                    property: "opacity"
                    from: 0; to: 1
                    duration: Theme.Motion.pageInDuration
                    easing.type: Easing.OutCubic
                }
                NumberAnimation {
                    property: "x"
                    from: Theme.Motion.pageSlideOffset; to: 0
                    duration: Theme.Motion.pageInDuration
                    easing.type: Easing.OutCubic
                }
            }
        }

        replaceExit: Transition {
            ParallelAnimation {
                NumberAnimation {
                    property: "opacity"
                    from: 1; to: 0
                    duration: Theme.Motion.pageOutDuration
                    easing.type: Easing.OutCubic
                }
                NumberAnimation {
                    property: "x"
                    from: 0; to: -Theme.Motion.pageSlideOffset
                    duration: Theme.Motion.pageOutDuration
                    easing.type: Easing.OutCubic
                }
            }
        }

        // --- Push transitions (History -> Review) ---
        pushEnter: Transition {
            ParallelAnimation {
                NumberAnimation {
                    property: "x"
                    from: pageStack.width; to: 0
                    duration: Theme.Motion.pushDuration
                    easing.type: Easing.OutQuint
                }
                NumberAnimation {
                    property: "opacity"
                    from: 0; to: 1
                    duration: Theme.Motion.pushDuration
                }
            }
        }

        pushExit: Transition {
            ParallelAnimation {
                NumberAnimation {
                    property: "x"
                    from: 0; to: -pageStack.width * 0.3
                    duration: Theme.Motion.pushDuration
                }
                NumberAnimation {
                    property: "opacity"
                    from: 1; to: 0.5
                    duration: Theme.Motion.pushDuration
                }
            }
        }

        // --- Pop transitions (Review -> History) ---
        popEnter: Transition {
            ParallelAnimation {
                NumberAnimation {
                    property: "x"
                    from: -pageStack.width * 0.3; to: 0
                    duration: Theme.Motion.pushDuration
                    easing.type: Easing.OutQuint
                }
                NumberAnimation {
                    property: "opacity"
                    from: 0.5; to: 1
                    duration: Theme.Motion.pushDuration
                }
            }
        }

        popExit: Transition {
            ParallelAnimation {
                NumberAnimation {
                    property: "x"
                    from: 0; to: pageStack.width
                    duration: Theme.Motion.pushDuration
                    easing.type: Easing.InQuad
                }
                NumberAnimation {
                    property: "opacity"
                    from: 1; to: 0
                    duration: Theme.Motion.pushDuration
                }
            }
        }
    }

    // === 2a. Mode selection banner ===
    Components.ModeBanner {
        id: modeBanner
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: navBar.bottom
        detectedSession: {
            var track = typeof strategyVM !== "undefined" && strategyVM ? strategyVM.trackName : ""
            var car = typeof strategyVM !== "undefined" && strategyVM ? strategyVM.carName : ""
            var st = typeof modeVM !== "undefined" && modeVM ? modeVM.sessionType : ""
            if (track && car) return st + " \u00b7 " + track + " \u00b7 " + car
            return st || "Connecting..."
        }
        activeMode: typeof modeVM !== "undefined" && modeVM ? modeVM.activeMode : "sprint"
        bannerVisible: typeof modeVM !== "undefined" && modeVM ? modeVM.bannerVisible : false

        onModeSelected: function(mode) {
            if (typeof modeVM !== "undefined" && modeVM) modeVM.setMode(mode)
        }
        onDismissed: {
            if (typeof modeVM !== "undefined" && modeVM) modeVM.dismissBanner()
        }
    }

    // === 2a2. Demo Mode badge — always visible when demo is active ===
    Components.DemoBadge {
        id: demoBadge
        active: typeof demoVM !== "undefined" && demoVM ? demoVM.isActive : false
        currentLap: typeof demoVM !== "undefined" && demoVM ? demoVM.currentLap : 0
        totalLaps: typeof demoVM !== "undefined" && demoVM ? demoVM.totalLaps : 0
        phase: typeof demoVM !== "undefined" && demoVM ? demoVM.phase : ""
        momentTitle: typeof demoVM !== "undefined" && demoVM ? demoVM.lastMomentTitle : ""
    }

    // === 2a3. Demo controls — compact transport panel while demo is active ===
    Components.DemoControls {
        anchors {
            bottom: statusBar.top
            horizontalCenter: parent.horizontalCenter
            bottomMargin: 16
        }
        active: typeof demoVM !== "undefined" && demoVM ? demoVM.isActive : false
        playing: typeof demoVM !== "undefined" && demoVM ? demoVM.isPlaying : false

        onPlayRequested: if (typeof demoVM !== "undefined" && demoVM) demoVM.play()
        onPauseRequested: if (typeof demoVM !== "undefined" && demoVM) demoVM.pause()
        onStepRequested: if (typeof demoVM !== "undefined" && demoVM) demoVM.stepLap()
        onResetRequested: if (typeof demoVM !== "undefined" && demoVM) demoVM.reset()
    }

    // === 2b. Status bar ===
    Rectangle {
        id: statusBar
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 28
        color: Theme.Tokens.surface
        z: 5

        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 1
            color: Qt.rgba(Theme.Tokens.chalk.r, Theme.Tokens.chalk.g, Theme.Tokens.chalk.b, 0.06)
        }

        RowLayout {
            anchors { fill: parent; leftMargin: 16; rightMargin: 16 }
            spacing: 16

            // Connection status
            Row {
                spacing: 6
                Rectangle {
                    width: 6; height: 6; radius: 3
                    anchors.verticalCenter: parent.verticalCenter
                    color: serviceVM && serviceVM.sim ? Theme.Tokens.acidGreen : Theme.Tokens.steel
                }
                Text {
                    text: serviceVM && serviceVM.sim ? serviceVM.sim + " Connected" : "No Simulator"
                    font { family: Theme.Typography.monoFamily; pixelSize: 10; weight: Font.Bold }
                    color: Theme.Tokens.steel
                }
            }

            Item { Layout.fillWidth: true }

            // Session info
            Text {
                text: serviceVM && serviceVM.statusDetail ? serviceVM.statusDetail : "\u2014"
                font { family: Theme.Typography.monoFamily; pixelSize: 10 }
                color: Qt.rgba(Theme.Tokens.steel.r, Theme.Tokens.steel.g, Theme.Tokens.steel.b, 0.6)
            }

            Item { Layout.fillWidth: true }

            // Overlay info
            Text {
                text: {
                    if (!overlayVM) return ""
                    var ids = overlayVM.getEnabledWidgetIds()
                    var count = ids ? ids.length : 0
                    var lockText = overlayVM.overlayLocked ? " \u00b7 \ud83d\udd12" : ""
                    var hideMode = overlayVM.autoHideEnabled ? " \u00b7 AUTO" : " \u00b7 MANUAL"
                    return count + " overlay" + (count !== 1 ? "s" : "") + hideMode + lockText
                }
                font { family: Theme.Typography.monoFamily; pixelSize: 10 }
                color: Theme.Tokens.steel
            }
        }
    }

    // === 3. SlideOver for Settings ===
    Components.SlideOver {
        id: settingsSlideOver

        onCloseRequested: {
            settingsSlideOver.isOpen = false
            // Reset to settings view when closing
            settingsStack.currentIndex = 0
        }

        // Panel stack: 0=Settings, 1=Diagnostics, 2=About
        Item {
            anchors.fill: parent

            property int currentIndex: 0

            // Alias for children to reference
            id: settingsStack

            Panels.SettingsPanel {
                anchors.fill: parent
                visible: settingsStack.currentIndex === 0
                opacity: visible ? 1.0 : 0.0
                Behavior on opacity {
                    NumberAnimation { duration: 200; easing.type: Easing.InOutQuad }
                }
                onShowDiagnostics: settingsStack.currentIndex = 1
            }

            Panels.DiagnosticsPanel {
                anchors.fill: parent
                visible: settingsStack.currentIndex === 1
                opacity: visible ? 1.0 : 0.0
                Behavior on opacity {
                    NumberAnimation { duration: 200; easing.type: Easing.InOutQuad }
                }
                onBackRequested: settingsStack.currentIndex = 0
                onShowAbout: settingsStack.currentIndex = 2
            }

            Panels.AboutPanel {
                anchors.fill: parent
                visible: settingsStack.currentIndex === 2
                opacity: visible ? 1.0 : 0.0
                Behavior on opacity {
                    NumberAnimation { duration: 200; easing.type: Easing.InOutQuad }
                }
                onBackRequested: settingsStack.currentIndex = 1
            }
        }
    }

    // === 4. ConfirmDialog for destructive actions ===
    Components.ConfirmDialog {
        id: confirmDialog

        onConfirmed: {
            confirmDialog.isOpen = false
            // Callback will be set by the requesting action
            if (confirmDialog._onConfirm)
                confirmDialog._onConfirm()
        }

        onCancelled: {
            confirmDialog.isOpen = false
        }

        property var _onConfirm: null

        function show(title, message, onConfirm) {
            confirmDialog.title = title
            confirmDialog.message = message
            confirmDialog._onConfirm = onConfirm
            confirmDialog.isOpen = true
        }
    }

    // === 5. Onboarding overlay (shown on first launch) ===
    Onboarding.OnboardingFlow {
        id: onboarding
    }

    // === 6. Modular overlay system (RaceLab-style independent widget windows) ===
    Overlay.OverlayWindow {
        id: overlayManager
    }

    function toggleOverlay() {
        if (!overlayVM) return
        var enabled = overlayVM.getEnabledWidgetIds()
        if (enabled && enabled.length > 0) {
            overlayVM.disableAllWidgets()
            toast.show("All overlays hidden")
        } else {
            overlayVM.toggleWidget("delta_timing")
            overlayVM.toggleWidget("inputs_grip")
            overlayVM.toggleWidget("fuel_strategy")
            toast.show("Default overlays enabled")
        }
    }

    // === Tray integration ===
    Connections {
        target: typeof trayVM !== "undefined" && trayVM !== null ? trayVM : null
        function onOverlayToggleRequested() { root.toggleOverlay() }
    }

    // === Keyboard shortcuts ===

    // Ctrl+O — toggle all overlay widgets on/off
    Shortcut {
        sequence: "Ctrl+O"
        onActivated: root.toggleOverlay()
    }

    // Ctrl+L — lock/unlock overlay positions
    Shortcut {
        sequence: "Ctrl+L"
        onActivated: {
            if (overlayVM) { overlayVM.toggleOverlayLock(); toast.show(overlayVM.overlayLocked ? "Overlays locked" : "Overlays unlocked") }
        }
    }

    // Ctrl+G — toggle snap-to-edge for overlay dragging
    Shortcut {
        sequence: "Ctrl+G"
        onActivated: {
            if (overlayVM) { overlayVM.toggleSnap(); toast.show(overlayVM.snapEnabled ? "Snap enabled" : "Snap disabled") }
        }
    }

    Shortcut {
        sequence: "Ctrl+H"
        onActivated: {
            if (overlayVM) { overlayVM.toggleAutoHide(); toast.show(overlayVM.autoHideEnabled ? "Auto-hide on" : "Auto-hide off") }
        }
    }

    // Ctrl+1/2/3/4/5 — switch tabs
    Shortcut { sequence: "Ctrl+1"; onActivated: navBar.pageRequested("dashboard") }
    Shortcut { sequence: "Ctrl+2"; onActivated: navBar.pageRequested("live") }
    Shortcut { sequence: "Ctrl+3"; onActivated: navBar.pageRequested("strategy") }
    Shortcut { sequence: "Ctrl+4"; onActivated: navBar.pageRequested("history") }
    Shortcut { sequence: "Ctrl+5"; onActivated: navBar.pageRequested("overlays") }

    // Ctrl+Up — increase all overlay opacity by 5%
    Shortcut {
        sequence: "Ctrl+Up"
        onActivated: {
            if (overlayVM) overlayVM.adjustAllOpacity(0.05)
        }
    }

    // Ctrl+Down — decrease all overlay opacity by 5%
    Shortcut {
        sequence: "Ctrl+Down"
        onActivated: {
            if (overlayVM) overlayVM.adjustAllOpacity(-0.05)
        }
    }

    // Escape — close settings, help, or other overlays
    Shortcut {
        sequence: "Escape"
        onActivated: {
            if (shortcutHelp.visible) { shortcutHelp.visible = false; return }
            if (settingsSlideOver.isOpen) settingsSlideOver.isOpen = false
        }
    }

    // F1 — keyboard shortcut help
    Shortcut {
        sequence: "F1"
        onActivated: shortcutHelp.visible = !shortcutHelp.visible
    }

    // Ctrl+A — auto-arrange overlays in a grid
    Shortcut {
        sequence: "Ctrl+A"
        onActivated: { if (overlayVM) { overlayVM.autoArrangeOverlays(); toast.show("Overlays arranged") } }
    }

    // Alt+1 through Alt+9 — quick-toggle individual overlay widgets
    Repeater {
        model: 9
        Shortcut {
            required property int index
            sequence: "Alt+" + (index + 1)
            onActivated: if (overlayVM) overlayVM.toggleWidgetByIndex(index + 1)
        }
    }

    // Shortcut help overlay
    Components.ShortcutHelpOverlay {
        id: shortcutHelp
    }

    // Toast notification
    Components.ToastNotification {
        id: toast
    }

    // Wire toast signals
    Connections {
        target: serviceVM
        function onToastRequested(message) { toast.show(message) }
    }
    Connections {
        target: overlayVM
        function onWidgetSettingsChanged() {
            // Don't toast on every settings change — only on explicit actions
        }
    }

    // === Page components ===
    Component {
        id: dashboardComponent
        Pages.DashboardPage {}
    }

    Component {
        id: liveComponent
        Pages.LivePage {}
    }

    Component {
        id: strategyComponent
        Pages.StrategyPage {}
    }

    Component {
        id: historyComponent
        Pages.HistoryPage {
            onReviewRequested: function(folder) {
                root.openReview(folder)
            }
        }
    }

    Component {
        id: overlaysComponent
        Pages.OverlayManagerPage {}
    }

    Component {
        id: reviewComponent
        Pages.ReviewPage {
            onBackRequested: {
                pageStack.pop()
                // Restore the NavBar page indicator to history
                root.currentPage = "history"
            }
        }
    }

    // === Review navigation flow ===
    function openReview(folder) {
        // Load review data via the ViewModel
        reviewVM.setSection("overview")
        // Push ReviewPage onto the stack
        pageStack.push(reviewComponent)
    }
}
