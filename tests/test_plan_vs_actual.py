"""T146: plan-vs-actual summary in the bundle.

Per Q102 the post-session bundle ships pre-race plan + actual
pit events + execution delta. T144 wired the plan; T145 the
actuals; T146 ships the *delta* — pairs each planned stop with
the actual that executed it and reports the lap / fuel
divergence so the webapp review (and a future desktop summary,
T147) can render "you planned X, actual was Y".

Pairing strategy: index-based zip. Both sequences are
chronological (plan in lap order; actuals in record order),
so the i-th planned stop pairs with the i-th actual stop.
This keeps the summary deterministic and free of fuzzy
match-window logic — adequate for an MVP and consistent with
how a driver thinks about their plan ("first stop, second
stop").

Fields per pair:

- ``planned_lap`` / ``actual_lap``
- ``lap_delta`` (actual - planned), or ``None`` when one side
  is missing
- ``planned_fuel_l`` / ``actual_fuel_l`` (actuals may surface
  ``None`` if the sim adapter didn't capture fuel)
- ``fuel_delta_l`` (actual - planned), ``None`` if either
  fuel value is unknown
- ``matched``: True iff both planned and actual exist for
  this index

Top-level summary also exposes the count of planned vs actual
stops so the consumer doesn't need to introspect the list.

Bundle integration: when both ``race_strategy`` and
``actual_pit_events`` are passed to the bundle writer, the
manifest gains:

- ``actual_pit_events`` — the ordered log of actuals
- ``plan_vs_actual`` — the computed summary

When only one of them is provided, the bundle writer emits
that side and skips ``plan_vs_actual`` (no useful comparison
without both).
"""
from __future__ import annotations

import json
from pathlib import Path

from lap_coach_logger.core.actual_pit_events import (
    ActualPitEvent,
    ActualPitEventLog,
)
from lap_coach_logger.core.plan_vs_actual import compute_plan_vs_actual
from lap_coach_logger.core.race_strategy import PitStop, RaceStrategy


def _make_laps() -> list[dict]:
    return [
        {"lap_number": 1, "lap_time_s": 92.0, "valid": True, "fuel_used_l": 2.1, "sector_times_s": [30, 30, 32]},
    ]


def _setup_v1_bundle(tmp_path: Path) -> Path:
    session_dir = tmp_path / "2026-04-25_12-00-00__iracing__Monza__race"
    session_dir.mkdir(parents=True)
    (session_dir / "telemetry.parquet").write_bytes(b"\x00" * 512)
    (session_dir / "laps.json").write_text(json.dumps(_make_laps()))
    (session_dir / "events.json").write_text(json.dumps([]))
    (session_dir / "channels.json").write_text(
        json.dumps({"schema_version": 2, "channels": []})
    )
    return session_dir


def _two_stop_plan() -> RaceStrategy:
    return RaceStrategy(
        total_laps=50, fuel_capacity=65.0, fuel_per_lap=3.0, tire_life_laps=30,
        pit_stops=[
            PitStop(lap=21, fuel_to_add=46.5, tire_compound="medium", estimated_time_s=25.0),
            PitStop(lap=36, fuel_to_add=43.5, tire_compound="medium", estimated_time_s=25.0),
        ],
        total_race_time_s=4575.0, fuel_at_finish=2.0,
    )


# ---------------------------------------------------------------------------
# Empty / degenerate inputs
# ---------------------------------------------------------------------------


def test_no_plan_no_actuals_yields_empty_stops_and_zero_counts() -> None:
    """A session with neither plan nor actuals (e.g., free
    practice, wrong-mode capture) must produce a valid empty
    summary — caller can still serialise without special-
    casing."""
    plan = RaceStrategy(
        total_laps=10, fuel_capacity=65.0, fuel_per_lap=3.0,
        tire_life_laps=30, pit_stops=[],
    )
    actuals = ActualPitEventLog()

    summary = compute_plan_vs_actual(plan, actuals)

    assert summary == {"planned_stops": 0, "actual_stops": 0, "stops": []}


# ---------------------------------------------------------------------------
# Single matched pair
# ---------------------------------------------------------------------------


def test_single_pair_at_same_lap_yields_zero_lap_delta() -> None:
    """The happy path — driver pitted exactly when the plan
    said to. lap_delta == 0 and matched is True."""
    plan = RaceStrategy(
        total_laps=50, fuel_capacity=65.0, fuel_per_lap=3.0, tire_life_laps=30,
        pit_stops=[
            PitStop(lap=21, fuel_to_add=46.5, tire_compound="medium", estimated_time_s=25.0),
        ],
    )
    actuals = ActualPitEventLog()
    actuals.record(ActualPitEvent(
        lap=21, timestamp_utc="t1", source="sim_detected",
        fuel_added_l=46.5,
    ))

    summary = compute_plan_vs_actual(plan, actuals)

    assert summary["stops"][0]["matched"] is True
    assert summary["stops"][0]["lap_delta"] == 0
    assert summary["stops"][0]["fuel_delta_l"] == 0


def test_pair_at_different_lap_computes_lap_delta() -> None:
    """Driver came in two laps later than planned. lap_delta
    is +2 (actual - planned). Sign convention: positive =
    later than planned, negative = earlier."""
    plan = RaceStrategy(
        total_laps=50, fuel_capacity=65.0, fuel_per_lap=3.0, tire_life_laps=30,
        pit_stops=[
            PitStop(lap=21, fuel_to_add=46.5, tire_compound="medium", estimated_time_s=25.0),
        ],
    )
    actuals = ActualPitEventLog()
    actuals.record(ActualPitEvent(
        lap=23, timestamp_utc="t1", source="sim_detected",
        fuel_added_l=46.5,
    ))

    summary = compute_plan_vs_actual(plan, actuals)

    assert summary["stops"][0]["planned_lap"] == 21
    assert summary["stops"][0]["actual_lap"] == 23
    assert summary["stops"][0]["lap_delta"] == 2


def test_pair_with_different_fuel_computes_fuel_delta() -> None:
    """Driver added 50 L instead of the planned 46.5 L —
    fuel_delta is +3.5. Same sign convention as laps."""
    plan = RaceStrategy(
        total_laps=50, fuel_capacity=65.0, fuel_per_lap=3.0, tire_life_laps=30,
        pit_stops=[
            PitStop(lap=21, fuel_to_add=46.5, tire_compound="medium", estimated_time_s=25.0),
        ],
    )
    actuals = ActualPitEventLog()
    actuals.record(ActualPitEvent(
        lap=21, timestamp_utc="t1", source="sim_detected",
        fuel_added_l=50.0,
    ))

    summary = compute_plan_vs_actual(plan, actuals)

    assert summary["stops"][0]["planned_fuel_l"] == 46.5
    assert summary["stops"][0]["actual_fuel_l"] == 50.0
    assert summary["stops"][0]["fuel_delta_l"] == 3.5


def test_pair_with_unknown_actual_fuel_yields_null_fuel_delta() -> None:
    """Sim adapters that don't surface fuel-added leave
    actuals.fuel_added_l == None. The summary must not invent
    a delta — None propagates so the consumer can render
    'unknown' rather than '0'."""
    plan = RaceStrategy(
        total_laps=50, fuel_capacity=65.0, fuel_per_lap=3.0, tire_life_laps=30,
        pit_stops=[
            PitStop(lap=21, fuel_to_add=46.5, tire_compound="medium", estimated_time_s=25.0),
        ],
    )
    actuals = ActualPitEventLog()
    actuals.record(ActualPitEvent(
        lap=21, timestamp_utc="t1", source="sim_detected",
        # fuel_added_l intentionally omitted
    ))

    summary = compute_plan_vs_actual(plan, actuals)

    assert summary["stops"][0]["actual_fuel_l"] is None
    assert summary["stops"][0]["fuel_delta_l"] is None


# ---------------------------------------------------------------------------
# Asymmetry: plan-only or actual-only entries
# ---------------------------------------------------------------------------


def test_planned_stop_with_no_actual_is_unmatched() -> None:
    """Driver retired before reaching their planned second
    stop. The unmatched plan entry surfaces with actual_lap =
    None and matched = False — webapp can render 'planned but
    didn't happen'."""
    plan = _two_stop_plan()
    actuals = ActualPitEventLog()
    actuals.record(ActualPitEvent(
        lap=21, timestamp_utc="t1", source="sim_detected",
    ))

    summary = compute_plan_vs_actual(plan, actuals)

    second = summary["stops"][1]
    assert second["planned_lap"] == 36
    assert second["actual_lap"] is None
    assert second["matched"] is False
    assert second["lap_delta"] is None


def test_actual_stop_with_no_plan_is_unmatched() -> None:
    """Driver pitted unscheduled (puncture, mistake). The
    extra actual surfaces with planned_lap = None and matched
    = False — same rationale as the inverse case."""
    plan = RaceStrategy(
        total_laps=50, fuel_capacity=65.0, fuel_per_lap=3.0, tire_life_laps=30,
        pit_stops=[
            PitStop(lap=21, fuel_to_add=46.5, tire_compound="medium", estimated_time_s=25.0),
        ],
    )
    actuals = ActualPitEventLog()
    actuals.record(ActualPitEvent(lap=21, timestamp_utc="t1", source="sim_detected"))
    actuals.record(ActualPitEvent(lap=33, timestamp_utc="t2", source="user_annotated"))

    summary = compute_plan_vs_actual(plan, actuals)

    extra = summary["stops"][1]
    assert extra["planned_lap"] is None
    assert extra["actual_lap"] == 33
    assert extra["matched"] is False
    assert extra["lap_delta"] is None


# ---------------------------------------------------------------------------
# Counts at top level
# ---------------------------------------------------------------------------


def test_top_level_counts_reflect_input_sizes() -> None:
    """planned_stops / actual_stops totals are the simplest
    summary — let consumers render '2 planned, 3 actual'
    without iterating the stops list."""
    plan = _two_stop_plan()
    actuals = ActualPitEventLog()
    for lap in (21, 33, 40):
        actuals.record(ActualPitEvent(lap=lap, timestamp_utc=f"t{lap}", source="sim_detected"))

    summary = compute_plan_vs_actual(plan, actuals)

    assert summary["planned_stops"] == 2
    assert summary["actual_stops"] == 3
    assert len(summary["stops"]) == 3


# ---------------------------------------------------------------------------
# JSON round-trip
# ---------------------------------------------------------------------------


def test_summary_round_trips_through_json() -> None:
    """Bundle is JSON. Pinning the round-trip catches any
    non-JSON-friendly values (NaN, Infinity, dataclass
    instances) sneaking in."""
    plan = _two_stop_plan()
    actuals = ActualPitEventLog()
    actuals.record(ActualPitEvent(
        lap=22, timestamp_utc="t1", source="sim_detected", fuel_added_l=47.0,
    ))

    summary = compute_plan_vs_actual(plan, actuals)

    assert json.loads(json.dumps(summary)) == summary


# ---------------------------------------------------------------------------
# Bundle integration: actuals + summary land in the manifest
# ---------------------------------------------------------------------------


def test_bundle_v2_includes_actual_pit_events_when_provided(tmp_path: Path) -> None:
    """T145's log carries no value if it doesn't reach the
    bundle. write_bundle_v2 ships the serialised log under
    `actual_pit_events` when the kwarg is provided."""
    from lap_coach_logger.writers.bundle_v2 import write_bundle_v2

    session_dir = _setup_v1_bundle(tmp_path)
    actuals = ActualPitEventLog()
    actuals.record(ActualPitEvent(
        lap=22, timestamp_utc="t1", source="sim_detected", fuel_added_l=47.0,
    ))

    manifest = write_bundle_v2(
        session_dir,
        session_id="actuals-1",
        sim_name="iRacing",
        raw_car="Ferrari 296 GT3",
        raw_track="Autodromo Nazionale Monza",
        raw_track_layout=None, session_type_raw="Race", mode="sprint",
        driver_name="", start_time="2026-04-25T12:00:00Z",
        end_time="2026-04-25T13:15:00Z", sample_count=10000,
        duration_s=4500.0, laps=_make_laps(), events=[],
        actual_pit_events=actuals,
    )

    assert manifest["actual_pit_events"] == [
        {
            "lap": 22, "timestamp_utc": "t1", "source": "sim_detected",
            "fuel_added_l": 47.0, "tire_compound": None, "duration_s": None,
        },
    ]


def test_bundle_v2_includes_plan_vs_actual_when_both_provided(tmp_path: Path) -> None:
    """When both race_strategy + actual_pit_events are
    available the bundle gains a precomputed summary so the
    webapp doesn't have to recompute from raw inputs every
    page load."""
    from lap_coach_logger.writers.bundle_v2 import write_bundle_v2

    session_dir = _setup_v1_bundle(tmp_path)
    actuals = ActualPitEventLog()
    actuals.record(ActualPitEvent(
        lap=22, timestamp_utc="t1", source="sim_detected", fuel_added_l=47.0,
    ))

    manifest = write_bundle_v2(
        session_dir,
        session_id="full-1",
        sim_name="iRacing",
        raw_car="Ferrari 296 GT3",
        raw_track="Autodromo Nazionale Monza",
        raw_track_layout=None, session_type_raw="Race", mode="sprint",
        driver_name="", start_time="2026-04-25T12:00:00Z",
        end_time="2026-04-25T13:15:00Z", sample_count=10000,
        duration_s=4500.0, laps=_make_laps(), events=[],
        race_strategy=_two_stop_plan(),
        actual_pit_events=actuals,
    )

    assert "plan_vs_actual" in manifest
    summary = manifest["plan_vs_actual"]
    assert summary["planned_stops"] == 2
    assert summary["actual_stops"] == 1
    # First pair is matched (planned 21 vs actual 22)
    assert summary["stops"][0]["lap_delta"] == 1


def test_bundle_v2_omits_plan_vs_actual_when_actuals_missing(tmp_path: Path) -> None:
    """No useful comparison without actuals — the summary key
    must be absent. Backwards compatible with sessions that
    only carry the plan (T144's standalone behaviour)."""
    from lap_coach_logger.writers.bundle_v2 import write_bundle_v2

    session_dir = _setup_v1_bundle(tmp_path)
    manifest = write_bundle_v2(
        session_dir,
        session_id="plan-only",
        sim_name="iRacing",
        raw_car="Ferrari 296 GT3",
        raw_track="Autodromo Nazionale Monza",
        raw_track_layout=None, session_type_raw="Race", mode="sprint",
        driver_name="", start_time="2026-04-25T12:00:00Z",
        end_time="2026-04-25T13:15:00Z", sample_count=10000,
        duration_s=4500.0, laps=_make_laps(), events=[],
        race_strategy=_two_stop_plan(),
        # actual_pit_events intentionally omitted
    )

    assert "race_strategy" in manifest
    assert "plan_vs_actual" not in manifest
    assert "actual_pit_events" not in manifest
