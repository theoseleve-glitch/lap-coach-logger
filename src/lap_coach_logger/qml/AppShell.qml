import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Theme" as Theme
import "Components" as Components
import "Pages" as Pages

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
            pageStack.replace(null, root.pageComponents[pageId])
        }

        onSettingsRequested: {
            settingsSlideOver.isOpen = true
        }

        onPauseRequested: {
            serviceVM.pauseMonitoring()
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
        }

        // Placeholder content for Task 12
        Text {
            anchors {
                top: parent.top
                left: parent.left
                topMargin: Theme.Tokens.lg
            }
            text: "Settings panel will be added in Task 12."
            font.family: Theme.Typography.bodyFamily
            font.pixelSize: Theme.Typography.bodySize
            color: Theme.Tokens.steel
            wrapMode: Text.WordWrap
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
