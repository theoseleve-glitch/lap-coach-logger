"""ACC shared-memory binary structures (ctypes).

ACC exposes three memory-mapped files on Windows:
  - ``Local\\acpmf_physics``   – physics telemetry updated every frame
  - ``Local\\acpmf_graphics``  – session/graphics info
  - ``Local\\acpmf_static``    – static car/track info (changes per session)

The struct layouts below mirror the ACC 1.9+ shared-memory specification.
Field names match the official ACC documentation.  All coordinates are
in the ACC native reference frame (Y-up, left-handed).

References:
  https://www.assettocorsa.net/forum/index.php?threads/acc-shared-memory-documentation.59965/
"""

from __future__ import annotations

import ctypes


# ── Enumerations (match ACC SDK values) ───────────────────────────────

class ACC_STATUS(ctypes.c_int):
    """Game status enum."""
    ACC_OFF = 0
    ACC_REPLAY = 1
    ACC_LIVE = 2
    ACC_PAUSE = 3


class ACC_SESSION_TYPE(ctypes.c_int):
    """Session type enum."""
    ACC_UNKNOWN = -1
    ACC_PRACTICE = 0
    ACC_QUALIFY = 1
    ACC_RACE = 2
    ACC_HOTLAP = 3
    ACC_TIME_ATTACK = 4
    ACC_DRIFT = 5
    ACC_DRAG = 6
    ACC_HOTSTINT = 7
    ACC_HOTSTINT_SUPERPOLE = 8


# Map integer values back to human-readable strings
SESSION_TYPE_MAP: dict[int, str] = {
    -1: "unknown",
    0: "practice",
    1: "qualifying",
    2: "race",
    3: "hotlap",
    4: "time_attack",
    5: "drift",
    6: "drag",
    7: "hotstint",
    8: "hotstint_superpole",
}


# ── Physics shared memory ─────────────────────────────────────────────

class SPageFilePhysics(ctypes.Structure):
    """``Local\\acpmf_physics`` – updated every physics tick."""
    _fields_ = [
        ("packetId", ctypes.c_int),
        ("gas", ctypes.c_float),
        ("brake", ctypes.c_float),
        ("fuel", ctypes.c_float),
        ("gear", ctypes.c_int),            # 0=R, 1=N, 2=1st, …
        ("rpms", ctypes.c_int),
        ("steerAngle", ctypes.c_float),
        ("speedKmh", ctypes.c_float),
        ("velocity", ctypes.c_float * 3),   # [x, y, z] m/s
        ("accG", ctypes.c_float * 3),       # [x, y, z] g-forces
        ("wheelSlip", ctypes.c_float * 4),
        ("wheelLoad", ctypes.c_float * 4),  # NOT USED in ACC
        ("wheelsPressure", ctypes.c_float * 4),
        ("wheelAngularSpeed", ctypes.c_float * 4),
        ("tyrewear", ctypes.c_float * 4),   # NOT USED in ACC
        ("tyreDirtyLevel", ctypes.c_float * 4),  # NOT USED
        ("tyreCoreTemperature", ctypes.c_float * 4),
        ("camberRAD", ctypes.c_float * 4),  # NOT USED
        ("suspensionTravel", ctypes.c_float * 4),
        ("drs", ctypes.c_float),            # NOT USED
        ("tc", ctypes.c_float),
        ("heading", ctypes.c_float),
        ("pitch", ctypes.c_float),
        ("roll", ctypes.c_float),
        ("cgHeight", ctypes.c_float),       # NOT USED
        ("carDamage", ctypes.c_float * 5),
        ("numberOfTyresOut", ctypes.c_int), # NOT USED
        ("pitLimiterOn", ctypes.c_int),
        ("abs", ctypes.c_float),
        ("kersCharge", ctypes.c_float),     # NOT USED
        ("kersInput", ctypes.c_float),      # NOT USED
        ("autoShifterOn", ctypes.c_int),
        ("rideHeight", ctypes.c_float * 2),
        ("turboBoost", ctypes.c_float),
        ("ballast", ctypes.c_float),        # NOT USED
        ("airDensity", ctypes.c_float),     # NOT USED
        ("airTemp", ctypes.c_float),
        ("roadTemp", ctypes.c_float),
        ("localAngularVel", ctypes.c_float * 3),
        ("finalFF", ctypes.c_float),
        ("performanceMeter", ctypes.c_float),  # NOT USED
        ("engineBrake", ctypes.c_int),      # NOT USED
        ("ersRecoveryLevel", ctypes.c_int), # NOT USED
        ("ersPowerLevel", ctypes.c_int),    # NOT USED
        ("ersHeatCharging", ctypes.c_int),  # NOT USED
        ("ersIsCharging", ctypes.c_int),    # NOT USED
        ("kersCurrentKJ", ctypes.c_float),  # NOT USED
        ("drsAvailable", ctypes.c_int),     # NOT USED
        ("drsEnabled", ctypes.c_int),       # NOT USED
        ("brakeTemp", ctypes.c_float * 4),
        ("clutch", ctypes.c_float),
        ("tyreTempI", ctypes.c_float * 4),  # NOT USED
        ("tyreTempM", ctypes.c_float * 4),  # NOT USED
        ("tyreTempO", ctypes.c_float * 4),  # NOT USED
        ("isAIControlled", ctypes.c_int),
        ("tyreContactPoint", ctypes.c_float * 4 * 3),
        ("tyreContactNormal", ctypes.c_float * 4 * 3),
        ("tyreContactHeading", ctypes.c_float * 4 * 3),
        ("brakeBias", ctypes.c_float),
        ("localVelocity", ctypes.c_float * 3),
        ("P2PActivation", ctypes.c_int),    # NOT USED
        ("P2PStatus", ctypes.c_int),        # NOT USED
        ("currentMaxRpm", ctypes.c_int),    # NOT USED
        ("mz", ctypes.c_float * 4),         # NOT USED
        ("fx", ctypes.c_float * 4),         # NOT USED
        ("fy", ctypes.c_float * 4),         # NOT USED
        ("slipRatio", ctypes.c_float * 4),
        ("slipAngle", ctypes.c_float * 4),
        ("tcinAction", ctypes.c_int),       # NOT USED
        ("absInAction", ctypes.c_int),      # NOT USED
        ("suspensionDamage", ctypes.c_float * 4),  # NOT USED
        ("tyreTemp", ctypes.c_float * 4),   # NOT USED
        ("waterTemp", ctypes.c_float),
        ("brakePressure", ctypes.c_float * 4),
        ("frontBrakeCompound", ctypes.c_int),
        ("rearBrakeCompound", ctypes.c_int),
        ("padLife", ctypes.c_float * 4),
        ("discLife", ctypes.c_float * 4),
        ("ignitionOn", ctypes.c_int),
        ("starterEngineOn", ctypes.c_int),
        ("isEngineRunning", ctypes.c_int),
        ("kerbVibration", ctypes.c_float),
        ("slipVibrations", ctypes.c_float),
        ("gVibrations", ctypes.c_float),
        ("absVibrations", ctypes.c_float),
    ]


# ── Graphics shared memory ────────────────────────────────────────────

class SPageFileGraphic(ctypes.Structure):
    """``Local\\acpmf_graphics`` – session/graphics state."""
    _fields_ = [
        ("packetId", ctypes.c_int),
        ("status", ctypes.c_int),           # ACC_STATUS
        ("session", ctypes.c_int),          # ACC_SESSION_TYPE
        ("currentTime", ctypes.c_wchar * 15),
        ("lastTime", ctypes.c_wchar * 15),
        ("bestTime", ctypes.c_wchar * 15),
        ("split", ctypes.c_wchar * 15),
        ("completedLaps", ctypes.c_int),
        ("position", ctypes.c_int),
        ("iCurrentTime", ctypes.c_int),     # current lap time ms
        ("iLastTime", ctypes.c_int),
        ("iBestTime", ctypes.c_int),
        ("sessionTimeLeft", ctypes.c_float),
        ("distanceTraveled", ctypes.c_float),
        ("isInPit", ctypes.c_int),
        ("currentSectorIndex", ctypes.c_int),
        ("lastSectorTime", ctypes.c_int),
        ("numberOfLaps", ctypes.c_int),
        ("tyreCompound", ctypes.c_wchar * 33),
        ("replayTimeMultiplier", ctypes.c_float),  # NOT USED
        ("normalizedCarPosition", ctypes.c_float),
        ("activeCars", ctypes.c_int),
        ("carCoordinates", ctypes.c_float * 60 * 3),
        ("carID", ctypes.c_int * 60),
        ("playerCarID", ctypes.c_int),
        ("penaltyTime", ctypes.c_float),
        ("flag", ctypes.c_int),
        ("penalty", ctypes.c_int),
        ("idealLineOn", ctypes.c_int),
        ("isInPitLane", ctypes.c_int),
        ("surfaceGrip", ctypes.c_float),
        ("mandatoryPitDone", ctypes.c_int),
        ("windSpeed", ctypes.c_float),
        ("windDirection", ctypes.c_float),
        ("isSetupMenuVisible", ctypes.c_int),
        ("mainDisplayIndex", ctypes.c_int),
        ("secondaryDisplayIndex", ctypes.c_int),
        ("TC", ctypes.c_int),
        ("TCCut", ctypes.c_int),
        ("EngineMap", ctypes.c_int),
        ("ABS", ctypes.c_int),
        ("fuelXLap", ctypes.c_float),
        ("rainLights", ctypes.c_int),
        ("flashingLights", ctypes.c_int),
        ("lightsStage", ctypes.c_int),
        ("exhaustTemperature", ctypes.c_float),
        ("wiperLV", ctypes.c_int),
        ("driverStintTotalTimeLeft", ctypes.c_int),
        ("driverStintTimeLeft", ctypes.c_int),
        ("rainTyres", ctypes.c_int),
        ("sessionIndex", ctypes.c_int),
        ("usedFuel", ctypes.c_float),
        ("deltaLapTime", ctypes.c_wchar * 15),
        ("iDeltaLapTime", ctypes.c_int),
        ("estimatedLapTime", ctypes.c_wchar * 15),
        ("iEstimatedLapTime", ctypes.c_int),
        ("isDeltaPositive", ctypes.c_int),
        ("iSplit", ctypes.c_int),
        ("isValidLap", ctypes.c_int),
        ("fuelEstimatedLaps", ctypes.c_float),
        ("trackStatus", ctypes.c_wchar * 33),
        ("missingMandatoryPits", ctypes.c_int),
        ("Clock", ctypes.c_float),
        ("directionLightsLeft", ctypes.c_int),
        ("directionLightsRight", ctypes.c_int),
        ("GlobalYellow", ctypes.c_int),
        ("GlobalYellow1", ctypes.c_int),
        ("GlobalYellow2", ctypes.c_int),
        ("GlobalYellow3", ctypes.c_int),
        ("GlobalWhite", ctypes.c_int),
        ("GlobalGreen", ctypes.c_int),
        ("GlobalChequered", ctypes.c_int),
        ("GlobalRed", ctypes.c_int),
        ("mfdTyreSet", ctypes.c_int),
        ("mfdFuelToAdd", ctypes.c_float),
        ("mfdTyrePressureLF", ctypes.c_float),
        ("mfdTyrePressureRF", ctypes.c_float),
        ("mfdTyrePressureLR", ctypes.c_float),
        ("mfdTyrePressureRR", ctypes.c_float),
        ("trackGripStatus", ctypes.c_int),
        ("rainIntensity", ctypes.c_int),
        ("rainIntensityIn10min", ctypes.c_int),
        ("rainIntensityIn30min", ctypes.c_int),
        ("currentTyreSet", ctypes.c_int),
        ("strategyTyreSet", ctypes.c_int),
        ("gapAhead", ctypes.c_int),
        ("gapBehind", ctypes.c_int),
    ]


# ── Static shared memory ──────────────────────────────────────────────

class SPageFileStatic(ctypes.Structure):
    """``Local\\acpmf_static`` – written once per session load."""
    _fields_ = [
        ("smVersion", ctypes.c_wchar * 15),
        ("acVersion", ctypes.c_wchar * 15),
        ("numberOfSessions", ctypes.c_int),
        ("numCars", ctypes.c_int),
        ("carModel", ctypes.c_wchar * 33),
        ("track", ctypes.c_wchar * 33),
        ("playerName", ctypes.c_wchar * 33),
        ("playerSurname", ctypes.c_wchar * 33),
        ("playerNick", ctypes.c_wchar * 33),
        ("sectorCount", ctypes.c_int),
        ("maxTorque", ctypes.c_float),      # NOT USED
        ("maxPower", ctypes.c_float),       # NOT USED
        ("maxRpm", ctypes.c_int),
        ("maxFuel", ctypes.c_float),
        ("suspensionMaxTravel", ctypes.c_float * 4),  # NOT USED
        ("tyreRadius", ctypes.c_float * 4), # NOT USED
        ("maxTurboBoost", ctypes.c_float),  # NOT USED
        ("deprecated1", ctypes.c_float),
        ("deprecated2", ctypes.c_float),
        ("penaltiesEnabled", ctypes.c_int),
        ("aidFuelRate", ctypes.c_float),
        ("aidTireRate", ctypes.c_float),
        ("aidMechanicalDamage", ctypes.c_float),
        ("aidAllowTyreBlankets", ctypes.c_int),  # NOT USED
        ("aidStability", ctypes.c_float),
        ("aidAutoClutch", ctypes.c_int),
        ("aidAutoBlip", ctypes.c_int),      # NOT USED
        ("hasDRS", ctypes.c_int),           # NOT USED
        ("hasERS", ctypes.c_int),           # NOT USED
        ("hasKERS", ctypes.c_int),          # NOT USED
        ("kersMaxJ", ctypes.c_float),       # NOT USED
        ("engineBrakeSettingsCount", ctypes.c_int),  # NOT USED
        ("ersPowerControllerCount", ctypes.c_int),  # NOT USED
        ("trackSPlineLength", ctypes.c_float),
        ("trackConfiguration", ctypes.c_wchar * 33),  # NOT USED
        ("ersMaxJ", ctypes.c_float),        # NOT USED
        ("isTimedRace", ctypes.c_int),      # NOT USED
        ("hasExtraLap", ctypes.c_int),      # NOT USED
        ("carSkin", ctypes.c_wchar * 33),   # NOT USED
        ("reversedGridPositions", ctypes.c_int),  # NOT USED
        ("PitWindowStart", ctypes.c_int),
        ("PitWindowEnd", ctypes.c_int),
        ("isOnline", ctypes.c_int),
        ("dryTyresName", ctypes.c_wchar * 33),
        ("wetTyresName", ctypes.c_wchar * 33),
    ]
