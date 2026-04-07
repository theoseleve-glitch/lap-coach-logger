import QtQuick
import QtQuick.Layouts
import "../Theme" as Theme
import "widgets" as Widgets

Item {
    id: root

    // Main overlay layout — arranges widgets in a vertical stack
    // Each widget is self-contained and reads from overlayVM

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        // ── Delta/Time Widget (primary) ──
        Widgets.DeltaTimeWidget {
            Layout.fillWidth: true
            delta: overlayVM ? overlayVM.lastDelta ? parseFloat(overlayVM.lastDelta) : 0 : 0
            lapTime: overlayVM ? overlayVM.elapsed || "0:00.000" : "0:00.000"
            bestTime: overlayVM ? overlayVM.bestTime || "—" : "—"
            lapNumber: overlayVM ? overlayVM.lapNumber : 0
            totalLaps: 0
            lapProgress: 0
            sectors: overlayVM ? overlayVM.sectorStates || [] : []
        }

        // ── Inputs Widget ──
        Widgets.InputsWidget {
            Layout.fillWidth: true
            throttle: overlayVM ? overlayVM.throttlePct : 0
            brake: overlayVM ? overlayVM.brakePct : 0
            steering: 0
            gForceX: 0
            gForceY: 0
            lockup: false
            wheelspin: false
            smoothness: 0.85
        }
    }
}
