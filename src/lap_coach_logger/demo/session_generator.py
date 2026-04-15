"""Deterministic synthetic session generator for Demo Mode.

Produces a stream of telemetry snapshots that tell a specific story:
first 5 laps inconsistent (especially in Sector 2), last 5 laps tight
(the coaching narrative). Same seed -> same output every time.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator

# Deterministic story: pre-scripted lap times per lap per sector.
# Each inner list is [sector_1, sector_2, sector_3] in seconds.
# Notice S2 has high variance early (laps 1-5), tightens late (6-10).
_STORY_LAP_SECTORS_S: list[list[float]] = [
    [28.50, 35.20, 27.30],  # Lap 1 - out lap, cold tires
    [28.30, 33.80, 27.10],  # Lap 2 - still inconsistent
    [28.25, 36.40, 27.00],  # Lap 3 - missed T5 braking point, big S2 loss
    [28.20, 33.20, 26.90],  # Lap 4
    [28.15, 34.90, 26.85],  # Lap 5 - plan generated here
    [28.10, 32.80, 26.80],  # Lap 6 - starting to execute plan
    [28.05, 32.50, 26.75],  # Lap 7 - S2 tightening
    [28.05, 32.30, 26.70],  # Lap 8
    [28.00, 32.20, 26.70],  # Lap 9 - consistent
    [28.00, 32.15, 26.65],  # Lap 10 - race-ready
]

# Fuel per lap (deterministic slight variance)
_FUEL_PER_LAP_L = 2.6
_FUEL_VARIANCE = [0.02, -0.03, 0.05, -0.01, 0.00, -0.02, 0.00, 0.01, -0.01, 0.00]

# Initial tank size and starting fuel
_FUEL_CAPACITY = 110.0
_INITIAL_FUEL = 60.0

# Tire temps story: warm up over first 3 laps, plateau, slight overheat late
_TYRE_TEMPS_BY_LAP: list[float] = [
    65.0, 72.0, 80.0, 85.0, 88.0,  # warming up
    90.0, 92.0, 94.0, 96.0, 98.0,  # plateau -> slight heat
]

# Pit stop occurs after lap 5 (between lap 5 end and lap 6 start)
_PIT_STOP_AFTER_LAP = 5

_TRACK_NAME = "Monza"
_CAR_NAME = "Ferrari 296 GT3"
_SESSION_TYPE = "practice"
_SIM = "iRacing"
_TOTAL_LAPS = 10
_SAMPLES_PER_LAP = 20  # 10 Hz x ~2s/sample - compressed for demo speed


@dataclass
class DemoLapRecord:
    """One completed lap in the demo story."""
    lap_number: int
    sector_times_s: list[float]
    lap_time_s: float
    fuel_used_l: float
    avg_tyre_temp_c: float
    is_in_pits: bool = False


@dataclass
class DemoEvent:
    """An event fired during the demo."""
    lap_number: int
    event_type: str   # "pit_stop" | "alert" | "plan_generated" | "readiness_changed"
    message: str
    timestamp_s: float


@dataclass
class DemoSession:
    """Complete pre-computed demo session data."""
    laps: list[DemoLapRecord]
    events: list[DemoEvent]
    total_laps: int = _TOTAL_LAPS
    track_name: str = _TRACK_NAME
    car_name: str = _CAR_NAME
    session_type: str = _SESSION_TYPE
    sim: str = _SIM
    fuel_capacity_l: float = _FUEL_CAPACITY
    samples_per_lap: int = _SAMPLES_PER_LAP


def generate_session() -> DemoSession:
    """Build the deterministic demo session."""
    laps: list[DemoLapRecord] = []
    events: list[DemoEvent] = []
    running_time = 0.0

    for i, sectors in enumerate(_STORY_LAP_SECTORS_S):
        lap_number = i + 1
        lap_time = sum(sectors)
        fuel_used = _FUEL_PER_LAP_L + _FUEL_VARIANCE[i]
        temp = _TYRE_TEMPS_BY_LAP[i]

        laps.append(DemoLapRecord(
            lap_number=lap_number,
            sector_times_s=list(sectors),
            lap_time_s=lap_time,
            fuel_used_l=fuel_used,
            avg_tyre_temp_c=temp,
            is_in_pits=False,
        ))
        running_time += lap_time

        # Scripted events
        if lap_number == 3:
            events.append(DemoEvent(
                lap_number=3, event_type="alert",
                message="Large S2 loss - inconsistent braking in T5",
                timestamp_s=running_time,
            ))
        if lap_number == 5:
            events.append(DemoEvent(
                lap_number=5, event_type="plan_generated",
                message="Focus on Sector 2 - stabilize braking point in T5",
                timestamp_s=running_time,
            ))
            events.append(DemoEvent(
                lap_number=5, event_type="pit_stop",
                message="Pit stop: fuel + tire change",
                timestamp_s=running_time + 25.0,
            ))
            running_time += 25.0
        if lap_number == 8:
            events.append(DemoEvent(
                lap_number=8, event_type="readiness_changed",
                message="Readiness: ALMOST",
                timestamp_s=running_time,
            ))
        if lap_number == 10:
            events.append(DemoEvent(
                lap_number=10, event_type="readiness_changed",
                message="Readiness: READY",
                timestamp_s=running_time,
            ))

    return DemoSession(laps=laps, events=events)


def iter_snapshots(session: DemoSession) -> Iterator[dict[str, Any]]:
    """Yield telemetry snapshots for the entire demo session.

    Each snapshot looks like a real coordinator snapshot dict -
    the same shape that `StrategyViewModel.update_live` expects.
    Field `_demo` is set to True on every snapshot so UI can
    display the SYNTHETIC chip.
    """
    session_time = 0.0
    cumulative_fuel = _INITIAL_FUEL

    for lap in session.laps:
        lap_duration = lap.lap_time_s
        sample_dt = lap_duration / session.samples_per_lap
        sector_bounds = [
            lap.sector_times_s[0],
            lap.sector_times_s[0] + lap.sector_times_s[1],
        ]
        lap_fuel_at_start = cumulative_fuel
        fuel_drain_per_sample = lap.fuel_used_l / session.samples_per_lap

        for sample_i in range(session.samples_per_lap):
            elapsed_in_lap = sample_i * sample_dt
            session_time_s = session_time + elapsed_in_lap
            fuel = lap_fuel_at_start - fuel_drain_per_sample * sample_i

            # Fake a speed profile: accelerate -> brake before T5 -> apex
            lap_pct = elapsed_in_lap / lap_duration
            if lap_pct < 0.33:
                speed = 220.0 + 30 * math.sin(lap_pct * math.pi * 3)
            elif lap_pct < 0.66:
                speed = 180.0 - 40 * math.sin((lap_pct - 0.33) * math.pi * 3)
            else:
                speed = 200.0 + 20 * math.sin((lap_pct - 0.66) * math.pi * 3)

            snap = {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "sim": _SIM,
                "track_name": _TRACK_NAME,
                "car_name": _CAR_NAME,
                "session_type": _SESSION_TYPE,
                "session_time_s": session_time_s,
                "lap_number": lap.lap_number,
                "lap_dist_pct": lap_pct,
                "lap_distance_m": lap_pct * 5793.0,  # Monza length
                "speed_kph": round(speed, 1),
                "throttle_pct": 0.85 if elapsed_in_lap < sector_bounds[0] else 0.4,
                "brake_pct": 0.0 if elapsed_in_lap < sector_bounds[0] else 0.6,
                "gear": 4,
                "rpm": 7500.0,
                "tyre_temp_lf": lap.avg_tyre_temp_c,
                "tyre_temp_rf": lap.avg_tyre_temp_c,
                "tyre_temp_lr": lap.avg_tyre_temp_c - 2.0,
                "tyre_temp_rr": lap.avg_tyre_temp_c - 2.0,
                "track_temp_c": 30.0,
                "air_temp_c": 22.0,
                "fuel_level": round(max(0.0, fuel), 2),
                "fuel_capacity": _FUEL_CAPACITY,
                "is_in_pits": False,
                "is_on_track": True,
                "position": 5,
                "num_cars": 20,
                "_demo": True,
            }
            yield snap

        # Advance session time by lap duration
        session_time += lap_duration
        cumulative_fuel -= lap.fuel_used_l

        # Simulate pit stop after lap 5: refuel, reset tyre temps
        if lap.lap_number == _PIT_STOP_AFTER_LAP:
            cumulative_fuel = _FUEL_CAPACITY * 0.7
            session_time += 25.0  # pit time
