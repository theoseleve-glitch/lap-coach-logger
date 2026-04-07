import QtQuick
import "../Theme" as Theme
import "widgets" as Widgets

// RaceLab-style modular overlay manager.
// Each widget is its own independent, draggable, frameless window.
// Toggle shows/hides all widgets. Each can be repositioned freely.

Item {
    id: root

    property bool overlayVisible: false

    onOverlayVisibleChanged: {
        deltaWindow.visible = overlayVisible
        inputsWindow.visible = overlayVisible
        fuelWindow.visible = overlayVisible
    }

    // ── Delta / Time Widget ──
    OverlayWidget {
        id: deltaWindow
        width: 320
        height: 200
        x: 100
        y: 80

        Widgets.DeltaTimeWidget {
            anchors.fill: parent
            anchors.margins: 4
            delta: overlayVM ? overlayVM.liveDelta : 0
            lapTime: overlayVM ? overlayVM.currentLapTime || "0:00.000" : "0:00.000"
            bestTime: overlayVM ? overlayVM.bestTime || "\u2014" : "\u2014"
            lapNumber: overlayVM ? overlayVM.lapNumber : 0
            totalLaps: 0
            lapProgress: overlayVM ? overlayVM.lapProgress : 0
            sectors: overlayVM ? overlayVM.sectorStates || [] : []
        }
    }

    // ── Inputs / Grip Widget ──
    OverlayWidget {
        id: inputsWindow
        width: 240
        height: 260
        x: 440
        y: 80

        Widgets.InputsWidget {
            anchors.fill: parent
            anchors.margins: 4
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

    // ── Fuel Strategy Widget ──
    OverlayWidget {
        id: fuelWindow
        width: 180
        height: 240
        x: 700
        y: 80

        Widgets.FuelWidget {
            anchors.fill: parent
            anchors.margins: 4
            remaining: overlayVM ? overlayVM.fuelLevel : 0
            lapsLeft: overlayVM ? overlayVM.fuelLapsLeft : 0
            fuelPerLap: overlayVM ? overlayVM.fuelPerLap : 0
            state: overlayVM ? overlayVM.fuelState || "SAFE" : "SAFE"
            pitWindow: ""
            totalLaps: 0
            currentLap: overlayVM ? overlayVM.lapNumber : 0
        }
    }
}
