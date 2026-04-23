"""Tests for the desktop canonical resolver + LUT loader."""

from __future__ import annotations

from lap_coach_logger.normalization.lut_loader import load_bundled_lut
from lap_coach_logger.normalization.resolver import CanonicalResolver


class TestLUTLoader:
    def test_bundled_lut_loads_without_error(self) -> None:
        lut = load_bundled_lut()
        assert len(lut.car_map) >= 20
        assert len(lut.track_map) >= 20
        assert len(lut.version) > 0

    def test_iracing_ferrari_296_resolved(self) -> None:
        lut = load_bundled_lut()
        key = ("iracing", "Ferrari 296 GT3")
        assert key in lut.car_map
        assert lut.car_map[key].car_class == "GT3"

    def test_acc_alias_maps_to_same_car(self) -> None:
        lut = load_bundled_lut()
        ir = lut.car_map.get(("iracing", "Ferrari 296 GT3"))
        acc = lut.car_map.get(("acc", "ferrari_296_gt3"))
        # Both should exist and share the same canonical_id
        assert ir is not None
        assert acc is not None
        assert ir.canonical_id == acc.canonical_id

    def test_monza_resolved_across_sims(self) -> None:
        lut = load_bundled_lut()
        ir = lut.track_map.get(("iracing", "Autodromo Nazionale Monza", ""))
        acc = lut.track_map.get(("acc", "monza", ""))
        assert ir is not None
        assert acc is not None
        assert ir.canonical_id == acc.canonical_id


class TestResolver:
    def test_resolve_known_car(self) -> None:
        r = CanonicalResolver()
        car = r.resolve_car("iracing", "Ferrari 296 GT3")
        assert car is not None
        assert car.canonical_name == "Ferrari 296 GT3"
        assert car.car_class == "GT3"

    def test_resolve_unknown_car_returns_none(self) -> None:
        r = CanonicalResolver()
        assert r.resolve_car("iracing", "Made Up Car 9000") is None

    def test_resolve_known_track(self) -> None:
        r = CanonicalResolver()
        track = r.resolve_track("iracing", "Autodromo Nazionale Monza", None)
        assert track is not None
        assert track.canonical_name == "Monza"

    def test_resolve_unknown_track_returns_none(self) -> None:
        r = CanonicalResolver()
        assert r.resolve_track("iracing", "Fantasy Circuit", None) is None

    def test_lut_version_is_stable(self) -> None:
        r1 = CanonicalResolver()
        r2 = CanonicalResolver()
        assert r1.lut_version == r2.lut_version
        assert len(r1.lut_version) > 0

    def test_session_type_normalised(self) -> None:
        r = CanonicalResolver()
        assert r.resolve_session_type("Race") == "race"
        assert r.resolve_session_type("  Practice ") == "practice"

    def test_silverstone_layout_disambiguation(self) -> None:
        r = CanonicalResolver()
        gp = r.resolve_track("assetto_corsa", "silverstone", "gp")
        national = r.resolve_track("assetto_corsa", "silverstone", "national")
        assert gp is not None and national is not None
        assert gp.canonical_layout == "GP"
        assert national.canonical_layout == "National"
        # Same track, different layouts — same canonical_id
        assert gp.canonical_id == national.canonical_id
