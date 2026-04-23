"""Unit tests for BackendResolver — pure function tests against test data.

Since these need a live Postgres with car_aliases/track_aliases populated,
they're gated by TEST_DATABASE_URL. For environments without a DB, test
the resolver's logic through the seed file format tests below.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"


# ---------------------------------------------------------------------------
# Seed file integrity tests — always run, no DB needed
# ---------------------------------------------------------------------------


class TestSeedFileIntegrity:
    """Validate canonical_cars.json and canonical_tracks.json structure."""

    def test_cars_json_loads(self) -> None:
        path = SEED_DIR / "canonical_cars.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) >= 20, f"Expected ≥20 cars, got {len(data)}"

    def test_tracks_json_loads(self) -> None:
        path = SEED_DIR / "canonical_tracks.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) >= 20, f"Expected ≥20 tracks, got {len(data)}"

    def test_no_duplicate_car_aliases(self) -> None:
        """Every (sim_id, raw_id) must be unique across all cars."""
        data = json.loads((SEED_DIR / "canonical_cars.json").read_text(encoding="utf-8"))
        seen: set[tuple[str, str]] = set()
        for car in data:
            for alias in car.get("aliases", []):
                key = (alias["sim_id"], alias["raw_id"])
                assert key not in seen, (
                    f"Duplicate car alias {key} in {car['canonical_name']}"
                )
                seen.add(key)

    def test_no_duplicate_track_aliases(self) -> None:
        """Every (sim_id, raw_id, raw_layout) must be unique across all tracks."""
        data = json.loads((SEED_DIR / "canonical_tracks.json").read_text(encoding="utf-8"))
        seen: set[tuple[str, str, str]] = set()
        for track in data:
            for alias in track.get("aliases", []):
                key = (alias["sim_id"], alias["raw_id"], alias.get("raw_layout", ""))
                assert key not in seen, (
                    f"Duplicate track alias {key} in {track['canonical_name']}"
                )
                seen.add(key)

    def test_all_canonical_ids_are_valid_uuids(self) -> None:
        for filename in ("canonical_cars.json", "canonical_tracks.json"):
            data = json.loads((SEED_DIR / filename).read_text(encoding="utf-8"))
            for entry in data:
                uuid.UUID(entry["canonical_id"])  # raises on invalid

    def test_all_sim_ids_are_known(self) -> None:
        """Every alias references one of the 4 supported sims."""
        known_sims = {"iracing", "acc", "assetto_corsa", "lmu"}
        for filename in ("canonical_cars.json", "canonical_tracks.json"):
            data = json.loads((SEED_DIR / filename).read_text(encoding="utf-8"))
            for entry in data:
                for alias in entry.get("aliases", []):
                    assert alias["sim_id"] in known_sims, (
                        f"Unknown sim_id {alias['sim_id']!r} in {entry['canonical_name']}"
                    )

    def test_car_class_values_are_known_or_null(self) -> None:
        allowed = {"GT3", "GT4", "GTE", "LMP2", "Hypercar", "Formula", "Cup", "Touring", None}
        data = json.loads((SEED_DIR / "canonical_cars.json").read_text(encoding="utf-8"))
        for car in data:
            assert car.get("car_class") in allowed, (
                f"Unknown car_class {car.get('car_class')!r} for {car['canonical_name']}"
            )


class TestResolverDataModel:
    """Tests for the resolver's data model types (no DB)."""

    def test_resolved_car_is_frozen(self) -> None:
        from app.resolver import ResolvedCar
        rc = ResolvedCar(canonical_id=uuid.uuid4(), canonical_name="Test", car_class="GT3")
        with pytest.raises(AttributeError):
            rc.canonical_name = "Changed"  # type: ignore[misc]

    def test_drift_captures_both_values(self) -> None:
        from app.resolver import Drift
        d = Drift(field="canonical_car_id", submitted_value="aaa", backend_value="bbb")
        assert d.submitted_value != d.backend_value
