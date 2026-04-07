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
        "history": historyComponent
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
            bottom: parent.bottom
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
        overlayManager.overlayVisible = !overlayManager.overlayVisible
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
        id: historyComponent
        Pages.HistoryPage {
            onReviewRequested: function(folder) {
                root.openReview(folder)
            }
        }
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
