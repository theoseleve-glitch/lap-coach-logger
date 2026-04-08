import QtQuick

// Generates realistic animated demo telemetry for overlay previews.
// Simulates a full race lap cycle: straight → braking → corner → exit.

QtObject {
    id: root

    // Timing
    property real delta: -0.127
    property string lapTime: "1:42.873"
    property string bestTime: "1:42.746"
    property string lastTime: "1:43.201"
    property int lapNumber: 7
    property int totalLaps: 12
    property real lapProgress: 62.0

    // Inputs
    property real throttle: 0.87
    property real brake: 0.0
    property real steering: 0.15
    property real gForceX: 0.3
    property real gForceY: 0.5
    property bool lockup: false
    property bool wheelspin: false
    property real smoothness: 0.82
    property real clutch: 0.0

    // Fuel
    property real fuelLevel: 28.4
    property real fuelPerLap: 2.53
    property real fuelLapsLeft: 11.2
    property string fuelState: "SAFE"

    // Vehicle
    property real speedKph: 247.3
    property int gear: 5
    property int rpm: 7200
    property int maxRpm: 8500

    // Session
    property string sessionType: "Race"
    property string flag: "green"
    property string elapsed: "18:42"
    property string timeRemaining: "41:18"

    // Coaching
    property string coachHeadline: "BRAKE EARLIER"
    property string coachSub: "8m early into T3 — losing 0.12s"
    property string coachCategory: "BRAKING"
    property string coachSeverity: "caution"
    property int coachConfidence: 94
    property string coachSector: "T3"

    // Sectors
    property var sectors: [
        {id: 1, delta: -0.082, status: "gain"},
        {id: 2, delta: 0.041, status: "loss"},
        {id: 3, delta: 0, status: "active"}
    ]

    // Lap times for graph/log
    property var lapTimes: [
        {lap: 1, time_s: 105.2}, {lap: 2, time_s: 103.8},
        {lap: 3, time_s: 104.1}, {lap: 4, time_s: 102.7},
        {lap: 5, time_s: 103.1}, {lap: 6, time_s: 102.9}
    ]
    property var laps: [
        {lap: 6, time: "1:42.9", delta: "+0.2", status: "clean"},
        {lap: 5, time: "1:43.1", delta: "+0.4", status: "clean"},
        {lap: 4, time: "1:42.7", delta: "BEST", status: "clean"},
        {lap: 3, time: "1:44.1", delta: "+1.4", status: "track_limits"},
        {lap: 2, time: "1:43.8", delta: "+1.1", status: "clean"},
        {lap: 1, time: "1:45.2", delta: "+2.5", status: "clean"}
    ]

    // Weather
    property real trackTemp: 38.2
    property real airTemp: 24.5

    // Car position for maps
    property real carPosition: 0.62

    // Internal timer state
    property real _t: 0

    // NOTE: Timer as property var won't auto-parent in QtObject.
    // The parent page must call root.tick() on its own Timer.
    // Alternatively, use Component.onCompleted to start updates.

    function tick() {
            root._t += 0.08
            var phase = root._t % 12

            // Lap progress
            root.lapProgress = (root.lapProgress + 0.3) % 100
            root.carPosition = root.lapProgress / 100

            // Delta oscillates
            root.delta = -0.127 + Math.sin(root._t * 0.5) * 0.15

            // Driving phases
            if (phase < 3) {
                root.throttle = Math.min(1, 0.85 + Math.sin(root._t * 2) * 0.15)
                root.brake = 0
                root.steering = Math.sin(root._t * 0.5) * 0.05
                root.gForceY = 0.3 + root.throttle * 0.4
                root.gForceX = root.steering * 0.2
                root.lockup = false
                root.wheelspin = root.throttle > 0.95
                root.speedKph = 220 + Math.sin(root._t) * 30
                root.gear = 5
                root.rpm = 6500 + Math.sin(root._t * 3) * 1200
            } else if (phase < 5) {
                root.throttle = 0
                root.brake = Math.min(1, 0.7 + Math.sin(root._t * 3) * 0.25)
                root.steering = Math.sin(root._t * 1.2) * 0.15
                root.gForceY = -(0.5 + root.brake * 0.5)
                root.gForceX = root.steering * 0.3
                root.lockup = root.brake > 0.9
                root.wheelspin = false
                root.speedKph = Math.max(80, 180 - (phase - 3) * 40)
                root.gear = 3
                root.rpm = 5000 + Math.sin(root._t * 4) * 800
            } else if (phase < 8) {
                var cp = (phase - 5) / 3
                root.throttle = cp * 0.6
                root.brake = Math.max(0, (1 - cp * 2) * 0.3)
                root.steering = Math.sin(cp * Math.PI) * 0.7
                root.gForceX = root.steering * 0.8
                root.gForceY = root.throttle * 0.3 - root.brake * 0.3
                root.lockup = false
                root.wheelspin = root.throttle > 0.5 && cp > 0.6
                root.speedKph = 140 + cp * 40
                root.gear = 3 + Math.floor(cp * 2)
                root.rpm = 4500 + cp * 2500
            } else {
                var ep = (phase - 8) / 4
                root.throttle = 0.5 + ep * 0.5
                root.brake = 0
                root.steering = (1 - ep) * 0.3
                root.gForceX = root.steering * 0.4
                root.gForceY = root.throttle * 0.5
                root.lockup = false
                root.wheelspin = root.throttle > 0.9
                root.speedKph = 180 + ep * 60
                root.gear = 4 + Math.floor(ep)
                root.rpm = 5500 + ep * 2000
            }

            // Lap time from progress
            var el = 102 * (root.lapProgress / 100)
            var m = Math.floor(el / 60)
            var s = el % 60
            root.lapTime = m + ":" + ("0" + s.toFixed(3)).slice(-6)

            // Fuel
            root.fuelLevel = Math.max(5, 28.4 - (root._t % 300) * 0.08)
            root.fuelLapsLeft = root.fuelLevel / root.fuelPerLap
            root.fuelState = root.fuelLapsLeft < 1.5 ? "BOX" : root.fuelLapsLeft < 5 ? "SAVE" : root.fuelLapsLeft < 8 ? "TIGHT" : "SAFE"

            // Sectors cycle
            if (root.lapProgress < 33)
                root.sectors = [{id:1,delta:0,status:"active"},{id:2,delta:0,status:"pending"},{id:3,delta:0,status:"pending"}]
            else if (root.lapProgress < 66)
                root.sectors = [{id:1,delta:-0.082,status:"gain"},{id:2,delta:0,status:"active"},{id:3,delta:0,status:"pending"}]
            else
                root.sectors = [{id:1,delta:-0.082,status:"gain"},{id:2,delta:0.041,status:"loss"},{id:3,delta:0,status:"active"}]
    }
}
