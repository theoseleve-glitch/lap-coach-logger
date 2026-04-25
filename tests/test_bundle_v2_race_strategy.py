"""T144: race-strategy plan ships in the v2 bundle (Q102).

Per Q102 the post-session bundle must contain the pre-race
strategy plan + actual pit events + execution delta. T144
ships the *plan* slice; T145 will capture actuals; T146
computes the plan-vs-actual summary.

This file pins:

- :func:`serialize_race_strategy` produces the canonical dict
  shape (flat fields + pit_stops list).
- :func:`write_bundle_v2` accepts ``race_strategy`` and writes
  it into the manifest under a top-level ``race_strategy``
  key.
- Omitting ``race_strategy`` leaves the key absent (or
  explicitly null) so the bundle is backwards-compatible
  with earlier sessions that didn't capture strategy.
- The serialised plan round-trips through JSON — the bundle
  is JSON, so a non-JSON-friendly dataclass would silently
  break.
"""
from __future__ import annotations

import json
from pathlib import Path

from lap_coach_logger.core.race_strategy import PitStop, RaceStrategy


def _make_laps() -> list[dict]:
    return [
        {"lap_number": 1, "lap_time_s": 92.0, "valid": True, "fuel_used_l": 2.1, "sector_times_s": [30, 30, 32]},
        {"lap_number": 2, "lap_time_s": 91.5, "valid": True, "fuel_used_l": 2.0, "sector_times_s": [29.5, 30, 32]},
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


def _sample_strategy() -> RaceStrategy:
    """Realistic 50-lap plan with two pit stops."""
    return RaceStrategy(
        total_laps=50,
        fuel_capacity=65.0,
        fuel_per_lap=3.0,
        tire_life_laps=30,
        pit_stops=[
            PitStop(lap=21, fuel_to_add=46.5, tire_compound="medium", estimated_time_s=25.0),
            PitStop(lap=36, fuel_to_add=43.5, tire_compound="medium", estimated_time_s=25.0),
        ],
        total_race_time_s=4575.0,
        fuel_at_finish=2.0,
    )


# ---------------------------------------------------------------------------
# serialize_race_strategy: shape contract
# ---------------------------------------------------------------------------


def test_serialize_strategy_emits_top_level_fields() -> None:
    """Top-level plan fields (race scope + per-stint totals) end
    up in the dict so the webapp review can render them
    without joining additional pieces."""
    from lap_coach_logger.writers.strategy_serializer import (
        serialize_race_strategy,
    )

    payload = serialize_race_strategy(_sample_strategy())

    assert payload["total_laps"] == 50
    assert payload["fuel_capacity"] == 65.0
    assert payload["fuel_per_lap"] == 3.0
    assert payload["tire_life_laps"] == 30
    assert payload["total_race_time_s"] == 4575.0
    assert payload["fuel_at_finish"] == 2.0


def test_serialize_strategy_emits_pit_stops_as_list_of_dicts() -> None:
    """Pit stops nest inside the plan as plain dicts so the
    bundle stays JSON-friendly and the webapp can iterate
    without dataclass machinery."""
    from lap_coach_logger.writers.strategy_serializer import (
        serialize_race_strategy,
    )

    payload = serialize_race_strategy(_sample_strategy())

    assert payload["pit_stops"] == [
        {
            "lap": 21,
            "fuel_to_add": 46.5,
            "tire_compound": "medium",
            "estimated_time_s": 25.0,
        },
        {
            "lap": 36,
            "fuel_to_add": 43.5,
            "tire_compound": "medium",
            "estimated_time_s": 25.0,
        },
    ]


def test_serialize_strategy_handles_empty_pit_stops() -> None:
    """A no-stop plan (short race / generous fuel) still
    serialises cleanly — the bundle must not fail on a valid
    zero-stop plan."""
    from lap_coach_logger.writers.strategy_serializer import (
        serialize_race_strategy,
    )

    no_stop = RaceStrategy(
        total_laps=10, fuel_capacity=65.0, fuel_per_lap=3.0,
        tire_life_laps=30, pit_stops=[],
        total_race_time_s=900.0, fuel_at_finish=35.0,
    )

    payload = serialize_race_strategy(no_stop)

    assert payload["pit_stops"] == []


def test_serialize_strategy_round_trips_through_json() -> None:
    """The bundle is JSON — a payload that isn't json.dumps-able
    would silently break finalisation. Pin the round-trip so a
    future field change (e.g., adding a non-serialisable type)
    fails this test, not production write."""
    from lap_coach_logger.writers.strategy_serializer import (
        serialize_race_strategy,
    )

    payload = serialize_race_strategy(_sample_strategy())

    # Must round-trip — json.dumps + json.loads = same dict
    assert json.loads(json.dumps(payload)) == payload


# ---------------------------------------------------------------------------
# write_bundle_v2 integration
# ---------------------------------------------------------------------------


def test_bundle_v2_includes_race_strategy_when_provided(tmp_path: Path) -> None:
    """End-to-end: pass a strategy to the bundle writer and the
    written session.json carries the serialised plan under the
    canonical key."""
    from lap_coach_logger.writers.bundle_v2 import write_bundle_v2

    session_dir = _setup_v1_bundle(tmp_path)
    manifest = write_bundle_v2(
        session_dir,
        session_id="strat-1",
        sim_name="iRacing",
        raw_car="Ferrari 296 GT3",
        raw_track="Autodromo Nazionale Monza",
        raw_track_layout=None,
        session_type_raw="Race",
        mode="sprint",
        driver_name="",
        start_time="2026-04-25T12:00:00Z",
        end_time="2026-04-25T13:15:00Z",
        sample_count=10_000,
        duration_s=4500.0,
        laps=_make_laps(),
        events=[],
        race_strategy=_sample_strategy(),
    )

    assert "race_strategy" in manifest
    assert manifest["race_strategy"]["total_laps"] == 50
    assert len(manifest["race_strategy"]["pit_stops"]) == 2

    # Same shape lands on disk
    on_disk = json.loads((session_dir / "session.json").read_text())
    assert on_disk["race_strategy"]["total_laps"] == 50


def test_bundle_v2_omits_race_strategy_key_when_none(tmp_path: Path) -> None:
    """Backward compat: sessions without a strategy plan must
    not gain a noisy ``"race_strategy": null`` field — the key
    is simply absent. Webapp readers can ``payload.get(...)``
    cleanly."""
    from lap_coach_logger.writers.bundle_v2 import write_bundle_v2

    session_dir = _setup_v1_bundle(tmp_path)
    manifest = write_bundle_v2(
        session_dir,
        session_id="no-strat",
        sim_name="iRacing",
        raw_car="Ferrari 296 GT3",
        raw_track="Autodromo Nazionale Monza",
        raw_track_layout=None,
        session_type_raw="Race",
        mode="sprint",
        driver_name="",
        start_time="2026-04-25T12:00:00Z",
        end_time="2026-04-25T13:15:00Z",
        sample_count=10_000,
        duration_s=4500.0,
        laps=_make_laps(),
        events=[],
        # race_strategy defaults to None
    )

    assert "race_strategy" not in manifest


def test_bundle_v2_race_strategy_round_trips_through_disk(tmp_path: Path) -> None:
    """End-to-end seal: serialise, write, read, deserialise —
    the strategy on disk equals what was passed in. Catches
    encoding / dict-mutation regressions in the writer."""
    from lap_coach_logger.writers.bundle_v2 import write_bundle_v2

    session_dir = _setup_v1_bundle(tmp_path)
    write_bundle_v2(
        session_dir,
        session_id="rt",
        sim_name="iRacing",
        raw_car="Ferrari 296 GT3",
        raw_track="Autodromo Nazionale Monza",
        raw_track_layout=None,
        session_type_raw="Race",
        mode="sprint",
        driver_name="",
        start_time="2026-04-25T12:00:00Z",
        end_time="2026-04-25T13:15:00Z",
        sample_count=10_000,
        duration_s=4500.0,
        laps=_make_laps(),
        events=[],
        race_strategy=_sample_strategy(),
    )
    on_disk = json.loads((session_dir / "session.json").read_text())

    expected_pit_stops = [
        {
            "lap": 21, "fuel_to_add": 46.5,
            "tire_compound": "medium", "estimated_time_s": 25.0,
        },
        {
            "lap": 36, "fuel_to_add": 43.5,
            "tire_compound": "medium", "estimated_time_s": 25.0,
        },
    ]
    assert on_disk["race_strategy"]["pit_stops"] == expected_pit_stops
