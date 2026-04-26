"""T192: First-launch downloads a track catalog and caches it
on disk for offline sector-split computation.

Three primitives, identical shape to T191's rules bundle but a
separate module since the consumers (sector-splits feature)
and content schema differ:

1. ``download_track_catalog(url, target_path, *,
   http_get_bytes)`` — atomic ``.partial`` + rename.
2. ``validate_track_catalog(payload_bytes)`` — parse + check
   top-level shape ``{"version": str, "tracks": list}``.
3. ``load_cached_track_catalog(cache_path)`` — read +
   validate; returns dict or None for any failure.

Per-track schema validation (sector boundaries, track length,
GPS coordinates) is the consumer's responsibility — T192 just
guarantees structural integrity at transport time.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pytest


def _bytes_iter(payload: bytes, chunk: int = 64) -> Iterable[bytes]:
    for i in range(0, len(payload), chunk):
        yield payload[i : i + chunk]


# -- module exports ---------------------------------------------------


def test_module_exports_public_api() -> None:
    from lap_coach_logger import track_catalog

    assert hasattr(track_catalog, "download_track_catalog")
    assert hasattr(track_catalog, "validate_track_catalog")
    assert hasattr(track_catalog, "load_cached_track_catalog")
    assert hasattr(track_catalog, "TrackCatalogStatus")


def test_status_is_immutable() -> None:
    """Frozen dataclass — no in-flight mutation."""
    from dataclasses import is_dataclass, FrozenInstanceError
    from lap_coach_logger.track_catalog import TrackCatalogStatus

    assert is_dataclass(TrackCatalogStatus)
    s = TrackCatalogStatus(payload=None, error="x")
    with pytest.raises(FrozenInstanceError):
        s.error = "y"  # type: ignore[misc]


# -- download_track_catalog -------------------------------------------


def test_download_writes_bytes_to_target(tmp_path: Path) -> None:
    from lap_coach_logger.track_catalog import download_track_catalog

    payload = json.dumps({
        "version": "1.0.0",
        "tracks": [{"id": "spa", "name": "Spa-Francorchamps"}],
    }).encode("utf-8")

    def fake_get(url: str, timeout_s: float):
        return _bytes_iter(payload)

    target = tmp_path / "tracks.json"
    download_track_catalog(
        "https://example.invalid/tracks.json",
        target,
        http_get_bytes=fake_get,
    )
    assert target.read_bytes() == payload


def test_download_uses_partial_rename(tmp_path: Path) -> None:
    """Atomic — interrupted downloads don't leave half-baked
    catalog at the cache path. Half-cached catalog would
    silently corrupt sector splits."""
    from lap_coach_logger.track_catalog import download_track_catalog

    target = tmp_path / "tracks.json"
    partial = target.with_suffix(target.suffix + ".partial")

    def boom(url: str, timeout_s: float):
        yield b"{\"version\":\"1"
        raise ConnectionError("network died")

    with pytest.raises(ConnectionError):
        download_track_catalog(
            "https://example.invalid/tracks.json",
            target,
            http_get_bytes=boom,
        )

    assert not partial.exists()
    assert not target.exists()


def test_download_creates_parent_dir(tmp_path: Path) -> None:
    """First-launch cache dir doesn't exist yet."""
    from lap_coach_logger.track_catalog import download_track_catalog

    target = tmp_path / "nested" / "cache" / "tracks.json"
    payload = b'{"version":"1.0.0","tracks":[]}'

    def fake_get(url: str, timeout_s: float):
        return _bytes_iter(payload)

    download_track_catalog(
        "https://example.invalid/tracks.json",
        target,
        http_get_bytes=fake_get,
    )
    assert target.is_file()


# -- validate_track_catalog -------------------------------------------


def test_validate_accepts_well_formed_catalog() -> None:
    from lap_coach_logger.track_catalog import validate_track_catalog

    raw = json.dumps({
        "version": "1.0.0",
        "tracks": [
            {
                "id": "spa",
                "name": "Spa-Francorchamps",
                "track_length_m": 7004,
                "sectors": [
                    {"index": 0, "split_m": 2300},
                    {"index": 1, "split_m": 4750},
                ],
            },
            {"id": "monza", "name": "Monza", "sectors": []},
        ],
    }).encode("utf-8")

    status = validate_track_catalog(raw)
    assert status.error is None
    assert status.payload is not None
    assert status.payload["version"] == "1.0.0"
    assert len(status.payload["tracks"]) == 2


def test_validate_rejects_malformed_json() -> None:
    from lap_coach_logger.track_catalog import validate_track_catalog

    status = validate_track_catalog(b"not json")
    assert status.payload is None
    assert status.error is not None


def test_validate_rejects_missing_version() -> None:
    from lap_coach_logger.track_catalog import validate_track_catalog

    raw = json.dumps({"tracks": []}).encode("utf-8")
    status = validate_track_catalog(raw)
    assert status.payload is None
    assert status.error is not None
    assert "version" in status.error.lower()


def test_validate_rejects_missing_tracks() -> None:
    from lap_coach_logger.track_catalog import validate_track_catalog

    raw = json.dumps({"version": "1.0.0"}).encode("utf-8")
    status = validate_track_catalog(raw)
    assert status.payload is None
    assert status.error is not None
    assert "tracks" in status.error.lower()


def test_validate_rejects_tracks_not_a_list() -> None:
    """``tracks`` must be a list — a dict keyed by track id is
    a different schema we don't accept."""
    from lap_coach_logger.track_catalog import validate_track_catalog

    raw = json.dumps({
        "version": "1.0.0",
        "tracks": {"spa": {"name": "Spa"}},
    }).encode("utf-8")
    status = validate_track_catalog(raw)
    assert status.payload is None
    assert status.error is not None


def test_validate_rejects_top_level_array() -> None:
    """Top level must be a JSON object, not an array."""
    from lap_coach_logger.track_catalog import validate_track_catalog

    raw = json.dumps([{"id": "spa"}]).encode("utf-8")
    status = validate_track_catalog(raw)
    assert status.payload is None
    assert status.error is not None


def test_validate_rejects_empty_version_string() -> None:
    """Empty version is unparseable for staleness checks."""
    from lap_coach_logger.track_catalog import validate_track_catalog

    raw = json.dumps({"version": "", "tracks": []}).encode("utf-8")
    status = validate_track_catalog(raw)
    assert status.payload is None
    assert status.error is not None


def test_validate_accepts_empty_tracks_list() -> None:
    """Empty ``tracks`` is valid — represents an empty catalog
    (e.g., before tracks have been published) — not a corrupt
    bundle."""
    from lap_coach_logger.track_catalog import validate_track_catalog

    raw = json.dumps({"version": "1.0.0", "tracks": []}).encode("utf-8")
    status = validate_track_catalog(raw)
    assert status.error is None
    assert status.payload == {"version": "1.0.0", "tracks": []}


# -- load_cached_track_catalog ----------------------------------------


def test_load_cached_returns_parsed_dict(tmp_path: Path) -> None:
    from lap_coach_logger.track_catalog import load_cached_track_catalog

    cache = tmp_path / "tracks.json"
    cache.write_text(json.dumps({
        "version": "1.0.0",
        "tracks": [{"id": "spa"}],
    }), encoding="utf-8")

    loaded = load_cached_track_catalog(cache)
    assert loaded is not None
    assert loaded["version"] == "1.0.0"
    assert loaded["tracks"] == [{"id": "spa"}]


def test_load_cached_returns_none_when_absent(tmp_path: Path) -> None:
    """No cache yet → None. Caller falls back to bundled
    defaults shipped with the app."""
    from lap_coach_logger.track_catalog import load_cached_track_catalog

    assert load_cached_track_catalog(tmp_path / "missing.json") is None


def test_load_cached_returns_none_when_malformed(tmp_path: Path) -> None:
    from lap_coach_logger.track_catalog import load_cached_track_catalog

    cache = tmp_path / "tracks.json"
    cache.write_text("not json")
    assert load_cached_track_catalog(cache) is None


def test_load_cached_returns_none_when_wrong_shape(
    tmp_path: Path,
) -> None:
    from lap_coach_logger.track_catalog import load_cached_track_catalog

    cache = tmp_path / "tracks.json"
    cache.write_text(json.dumps({"only": "wrong"}), encoding="utf-8")
    assert load_cached_track_catalog(cache) is None
