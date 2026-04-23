"""Live stint capture from telemetry snapshots.

Tracks fuel consumption and tyre wear lap-by-lap during a driving stint,
then finalises a StintRecord for the stint store.
"""

from __future__ import annotations

from datetime import datetime, timezone

from lap_coach_logger.core.stint_store import StintRecord, StintStore
from lap_coach_logger.core.strategy_models import PitMeasurement


class StintRecorder:
    """State-machine that accumulates telemetry snapshots into a StintRecord.

    States: IDLE -> RECORDING -> IDLE
    """

    def __init__(self, store: StintStore, track: str, car: str) -> None:
        self._store = store
        self._track = track
        self._car = car
        self._recording = False
        self._compound = ""
        self._source_session_id = ""
        self._source_label = ""
        self._prev_lap: int | None = None
        self._prev_fuel: float | None = None
        self._prev_session_time: float | None = None
        self._fuel_deltas: list[float] = []
        self._lap_times: list[float] = []
        self._lap_tyre_temps: list[list[float]] = []
        self._current_lap_temps: list[float] = []
        self._track_temps: list[float] = []
        self._air_temps: list[float] = []
        # Pit stop timing
        self._in_pits = False
        self._pit_entry_time: float | None = None
        self._pit_times: list[float] = []
        self._fuel_at_pit_entry: float | None = None
        self._pit_measurements: list[PitMeasurement] = []
        # Fuel capacity (auto-detected from first sample)
        self._fuel_capacity: float | None = None

    # ---- public API --------------------------------------------------------

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def measured_pit_time_s(self) -> float | None:
        """Average pit lane time loss from observed pit stops, or None."""
        if not self._pit_times:
            return None
        return sum(self._pit_times) / len(self._pit_times)

    @property
    def detected_fuel_capacity(self) -> float | None:
        """Fuel tank capacity auto-detected from telemetry, or None."""
        return self._fuel_capacity

    def start(
        self,
        compound: str,
        source_session_id: str = "",
        source_label: str = "",
    ) -> None:
        """Begin recording a new stint."""
        self._recording = True
        self._compound = compound
        self._source_session_id = source_session_id
        self._source_label = source_label
        self._prev_lap = None
        self._prev_fuel = None
        self._prev_session_time = None
        self._fuel_deltas = []
        self._lap_times = []
        self._lap_tyre_temps = []
        self._current_lap_temps = []
        self._track_temps = []
        self._air_temps = []
        self._in_pits = False
        self._pit_entry_time = None
        self._pit_times = []
        self._fuel_at_pit_entry = None
        self._pit_measurements = []
        self._fuel_capacity = None

    def push_snapshot(self, snap: dict) -> None:  # noqa: C901
        """Process one telemetry snapshot.

        Expected keys: lap_number, fuel_level, tyre_temp_lf, tyre_temp_rf,
        tyre_temp_lr, tyre_temp_rr, track_temp_c, air_temp_c, speed_kph,
        session_time_s.
        """
        if not self._recording:
            return

        if not isinstance(snap, dict):
            return

        raw_lap = snap.get("lap_number")
        raw_fuel = snap.get("fuel_level")
        raw_time = snap.get("session_time_s")
        if raw_lap is None or raw_fuel is None or raw_time is None:
            return

        lap = int(raw_lap)
        fuel = float(raw_fuel)
        session_time = float(raw_time)

        # Auto-detect fuel capacity from first available value
        fuel_cap = snap.get("fuel_capacity")
        if fuel_cap is not None and self._fuel_capacity is None:
            try:
                cap = float(fuel_cap)
                if cap > 0:
                    self._fuel_capacity = cap
            except (ValueError, TypeError):
                pass

        # Pit stop timing: track is_in_pits transitions
        is_in_pits = bool(snap.get("is_in_pits", False))
        if is_in_pits and not self._in_pits:
            self._pit_entry_time = session_time
            self._fuel_at_pit_entry = fuel
        elif not is_in_pits and self._in_pits and self._pit_entry_time is not None:
            pit_duration = session_time - self._pit_entry_time
            if 5.0 < pit_duration < 300.0:
                self._pit_times.append(pit_duration)
                if self._fuel_at_pit_entry is not None:
                    fuel_at_exit = fuel
                    fuel_added = max(
                        0.0, fuel_at_exit - self._fuel_at_pit_entry,
                    )
                    measurement = PitMeasurement(
                        total_time_s=pit_duration,
                        fuel_added=fuel_added,
                        tires_changed=False,
                        fuel_at_entry=self._fuel_at_pit_entry,
                        fuel_at_exit=fuel_at_exit,
                        compound_before=self._compound,
                        compound_after=self._compound,
                        recorded_at=datetime.now(timezone.utc).isoformat(),
                    )
                    self._pit_measurements.append(measurement)
                    self._store.log_pit_measurement(self._track, measurement)
            self._pit_entry_time = None
            self._fuel_at_pit_entry = None
        self._in_pits = is_in_pits
        tl = snap.get("tyre_temp_lf")
        tr = snap.get("tyre_temp_rf")
        bl = snap.get("tyre_temp_lr")
        br = snap.get("tyre_temp_rr")
        if tl is None or tr is None or bl is None or br is None:
            return
        avg_temp = (float(tl) + float(tr) + float(bl) + float(br)) / 4.0

        track_t = snap.get("track_temp_c")
        air_t = snap.get("air_temp_c")
        if track_t is not None:
            self._track_temps.append(float(track_t))
        if air_t is not None:
            self._air_temps.append(float(air_t))

        if self._prev_lap is None:
            # First snapshot -- seed state
            self._prev_lap = lap
            self._prev_fuel = fuel
            self._prev_session_time = session_time
            self._current_lap_temps.append(avg_temp)
            return

        if lap != self._prev_lap:
            # Lap changed -- finalise the completed lap
            assert self._prev_fuel is not None
            assert self._prev_session_time is not None

            fuel_delta = self._prev_fuel - fuel
            lap_time = session_time - self._prev_session_time

            self._fuel_deltas.append(fuel_delta)
            self._lap_times.append(lap_time)

            if self._current_lap_temps:
                self._lap_tyre_temps.append(self._current_lap_temps)
            self._current_lap_temps = [avg_temp]

            self._prev_lap = lap
            self._prev_fuel = fuel
            self._prev_session_time = session_time
        else:
            # Same lap -- accumulate tyre temps
            self._current_lap_temps.append(avg_temp)

    def stop(self) -> StintRecord | None:
        """Finalise recording and persist the stint.

        Returns the StintRecord, or None if no complete laps were recorded.
        """
        self._recording = False

        if not self._fuel_deltas:
            return None

        lap_count = len(self._fuel_deltas)
        fuel_per_lap = sum(self._fuel_deltas) / lap_count
        avg_lap_time = sum(self._lap_times) / lap_count
        avg_track_temp = (
            sum(self._track_temps) / len(self._track_temps)
            if self._track_temps
            else 0.0
        )
        avg_air_temp = (
            sum(self._air_temps) / len(self._air_temps)
            if self._air_temps
            else 0.0
        )
        wear_per_lap = self._estimate_wear()
        grip_at_end = max(0.0, 100.0 - wear_per_lap * lap_count)

        # Compute per-lap average temps from _lap_tyre_temps (list of lists)
        lap_avg_temps = [
            sum(temps) / len(temps) if temps else 0.0
            for temps in self._lap_tyre_temps
        ]

        record = StintRecord(
            compound=self._compound,
            fuel_per_lap=fuel_per_lap,
            fuel_per_lap_series=list(self._fuel_deltas),
            wear_per_lap=wear_per_lap,
            grip_at_end=grip_at_end,
            lap_count=lap_count,
            avg_lap_time_s=avg_lap_time,
            track_temp_c=avg_track_temp,
            air_temp_c=avg_air_temp,
            source_session_id=self._source_session_id,
            source_label=self._source_label,
            lap_times_s=list(self._lap_times),
            lap_avg_temps_c=lap_avg_temps,
        )
        self._store.log_stint(self._track, self._car, record)
        return record

    # ---- internals ---------------------------------------------------------

    def _estimate_wear(self) -> float:
        """Estimate tyre wear per lap from averaged tyre temps.

        Base wear = 2.0 %/lap.
        Cold penalty:  if avg < 75 C  -> add (75 - avg) * 0.3
        Hot penalty:   if avg > 100 C -> add (avg - 100) * 0.5
        The result is averaged across all recorded laps.
        """
        if not self._lap_tyre_temps:
            return 2.0

        lap_wears: list[float] = []
        for temps in self._lap_tyre_temps:
            avg = sum(temps) / len(temps)
            wear = 2.0
            if avg < 75.0:
                wear += (75.0 - avg) * 0.3
            elif avg > 100.0:
                wear += (avg - 100.0) * 0.5
            lap_wears.append(wear)

        return sum(lap_wears) / len(lap_wears)
