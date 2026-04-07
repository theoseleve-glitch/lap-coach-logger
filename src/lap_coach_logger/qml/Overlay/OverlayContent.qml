import QtQuick
import QtQuick.Layouts
import "../Theme" as Theme
import "widgets" as Widgets

Item {
    id: root

    // Overlay layout — arranges premium widgets vertically
    // Each widget is self-contained and binds to overlayVM

    RowLayout {
        anchors.fill: parent
        spacing: 8

        // Left column: Delta + Inputs stacked
        ColumnLayout {
            Layout.fillHeight: true
            Layout.preferredWidth: 310
            spacing: 8

            // Delta/Time Widget (primary timing overlay)
            Widgets.DeltaTimeWidget {
                Layout.fillWidth: true
                delta: overlayVM ? overlayVM.liveDelta : 0
                lapTime: overlayVM ? overlayVM.currentLapTime || "0:00.000" : "0:00.000"
                bestTime: overlayVM ? overlayVM.bestTime || "\u2014" : "\u2014"
                lapNumber: overlayVM ? overlayVM.lapNumber : 0
                totalLaps: 0
                lapProgress: overlayVM ? overlayVM.lapProgress : 0
                sectors: overlayVM ? overlayVM.sectorStates || [] : []
            }

            // Inputs/Grip Widget
            Widgets.InputsWidget {
                Layout.fillWidth: true
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

        // Center column: Coaching (only when visible)
        ColumnLayout {
            Layout.fillHeight: true
            Layout.preferredWidth: 290
            spacing: 8
            visible: overlayVM ? overlayVM.coachingVisible : false

            Widgets.CoachingWidget {
                Layout.fillWidth: true
                headline: overlayVM ? overlayVM.coachingHeadline : ""
                sub: overlayVM ? overlayVM.coachingSub : ""
                category: overlayVM ? overlayVM.coachingCategory : ""
                severity: overlayVM ? overlayVM.coachingSeverity : "positive"
                confidence: overlayVM ? overlayVM.coachingConfidence : 0
                sector: overlayVM ? overlayVM.coachingSector : ""
            }

            Item { Layout.fillHeight: true }
        }

        // Right column: Fuel widget
        ColumnLayout {
            Layout.fillHeight: true
            Layout.preferredWidth: 164
            spacing: 8

            Widgets.FuelWidget {
                Layout.fillWidth: true
                remaining: overlayVM ? overlayVM.fuelLevel : 0
                lapsLeft: overlayVM ? overlayVM.fuelLapsLeft : 0
                fuelPerLap: overlayVM ? overlayVM.fuelPerLap : 0
                state: overlayVM ? overlayVM.fuelState || "SAFE" : "SAFE"
                pitWindow: ""
                totalLaps: 0
                currentLap: overlayVM ? overlayVM.lapNumber : 0
            }

            Item { Layout.fillHeight: true }
        }
    }
}
