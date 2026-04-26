"""T191: First-launch downloads a coaching rules bundle and
caches it on disk for offline use.

Three primitives:

1. ``download_rules_bundle(url, target_path, *, http_get_bytes)``
   — atomic ``.partial`` + rename pattern, same shape as
   T186's ``download_update``.

2. ``validate_rules_bundle(payload_bytes)`` — checks the
   downloaded bytes parse as JSON with the required top-level
   shape (``{"version": str, "rules": list}``). Returns a
   :class:`RulesBundleStatus` capturing parsed payload + error.

3. ``load_cached_rules_bundle(cache_path)`` — read + validate
   in one shot. Returns the parsed dict on success or ``None``
   for any failure (cache absent, malformed JSON, wrong shape).

The actual rule-evaluation engine validates individual rules
at evaluation time. T191's job is just *transport* — getting
a structurally-valid bundle from a URL onto disk and loading
it back without crashing on corrupt data.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pytest


def _bytes_iter(payload: bytes, chunk: int = 64) -> Iterable[bytes]:
    """Helper: yield payload as fixed-size chunks."""
    for i in range(0, len(payload), chunk):
        yield payload[i : i + chunk]


# -- module exports ---------------------------------------------------


def test_module_exports_public_api() -> None:
    """All three primitives + the result type must be exposed."""
    from lap_coach_logger import rules_bundle

    assert hasattr(rules_bundle, "download_rules_bundle")
    assert hasattr(rules_bundle, "validate_rules_bundle")
    assert hasattr(rules_bundle, "load_cached_rules_bundle")
    assert hasattr(rules_bundle, "RulesBundleStatus")


def test_status_is_immutable() -> None:
    """``RulesBundleStatus`` should be a frozen dataclass."""
    from dataclasses import is_dataclass, FrozenInstanceError
    from lap_coach_logger.rules_bundle import RulesBundleStatus

    assert is_dataclass(RulesBundleStatus)
    s = RulesBundleStatus(payload=None, error="x")
    with pytest.raises(FrozenInstanceError):
        s.error = "y"  # type: ignore[misc]


# -- download_rules_bundle --------------------------------------------


def test_download_rules_bundle_writes_bytes_to_target(
    tmp_path: Path,
) -> None:
    """Downloaded bytes must end up at the target path."""
    from lap_coach_logger.rules_bundle import download_rules_bundle

    payload = json.dumps({
        "version": "1.0.0",
        "rules": [{"id": "rule-1"}],
    }).encode("utf-8")

    def fake_get(url: str, timeout_s: float):
        return _bytes_iter(payload)

    target = tmp_path / "rules.json"
    result = download_rules_bundle(
        "https://example.invalid/rules.json",
        target,
        http_get_bytes=fake_get,
    )
    assert result == target
    assert target.read_bytes() == payload


def test_download_rules_bundle_uses_partial_rename(
    tmp_path: Path,
) -> None:
    """Atomic via ``.partial`` rename — interrupted downloads
    don't leave half-baked content at the cache path."""
    from lap_coach_logger.rules_bundle import download_rules_bundle

    target = tmp_path / "rules.json"
    partial = target.with_suffix(target.suffix + ".partial")

    def boom(url: str, timeout_s: float):
        yield b"{\"partial"
        raise ConnectionError("network died")

    with pytest.raises(ConnectionError):
        download_rules_bundle(
            "https://example.invalid/rules.json",
            target,
            http_get_bytes=boom,
        )

    assert not partial.exists(), (
        ".partial must be cleaned up on failure"
    )
    assert not target.exists(), (
        "target must not exist after failed download"
    )


def test_download_rules_bundle_creates_parent_dir(
    tmp_path: Path,
) -> None:
    """The cache dir might not exist on first launch — the
    downloader must create it (the user's app-data dir is
    auto-managed)."""
    from lap_coach_logger.rules_bundle import download_rules_bundle

    target = tmp_path / "nested" / "subdir" / "rules.json"
    assert not target.parent.exists()

    payload = b'{"version":"1.0.0","rules":[]}'

    def fake_get(url: str, timeout_s: float):
        return _bytes_iter(payload)

    download_rules_bundle(
        "https://example.invalid/rules.json",
        target,
        http_get_bytes=fake_get,
    )
    assert target.is_file()


# -- validate_rules_bundle --------------------------------------------


def test_validate_accepts_well_formed_bundle() -> None:
    """A bundle with ``version`` (str) + ``rules`` (list) is
    valid; the parsed payload is returned in the result."""
    from lap_coach_logger.rules_bundle import validate_rules_bundle

    raw = json.dumps({
        "version": "1.0.0",
        "rules": [
            {"id": "early-throttle", "weight": 0.5},
            {"id": "late-brake"},
        ],
    }).encode("utf-8")

    status = validate_rules_bundle(raw)
    assert status.error is None
    assert status.payload is not None
    assert status.payload["version"] == "1.0.0"
    assert len(status.payload["rules"]) == 2


def test_validate_rejects_malformed_json() -> None:
    """Garbage bytes → error captured, payload is None."""
    from lap_coach_logger.rules_bundle import validate_rules_bundle

    status = validate_rules_bundle(b"not json at all }}}")
    assert status.payload is None
    assert status.error is not None


def test_validate_rejects_missing_version_field() -> None:
    """A bundle missing the version field is invalid — version
    is what `is_bundle_stale` (future task) compares against."""
    from lap_coach_logger.rules_bundle import validate_rules_bundle

    raw = json.dumps({"rules": []}).encode("utf-8")
    status = validate_rules_bundle(raw)
    assert status.payload is None
    assert status.error is not None
    assert "version" in status.error.lower()


def test_validate_rejects_missing_rules_field() -> None:
    """A bundle missing the rules field has nothing to coach
    with — invalid."""
    from lap_coach_logger.rules_bundle import validate_rules_bundle

    raw = json.dumps({"version": "1.0.0"}).encode("utf-8")
    status = validate_rules_bundle(raw)
    assert status.payload is None
    assert status.error is not None
    assert "rules" in status.error.lower()


def test_validate_rejects_rules_not_a_list() -> None:
    """``rules`` must be a list — a dict with rule names as
    keys is a different schema we don't support."""
    from lap_coach_logger.rules_bundle import validate_rules_bundle

    raw = json.dumps({
        "version": "1.0.0",
        "rules": {"by-id": {}},
    }).encode("utf-8")
    status = validate_rules_bundle(raw)
    assert status.payload is None
    assert status.error is not None


def test_validate_rejects_top_level_array() -> None:
    """A top-level array is not the bundle shape — must be an
    object with version + rules fields."""
    from lap_coach_logger.rules_bundle import validate_rules_bundle

    raw = json.dumps([{"id": "x"}]).encode("utf-8")
    status = validate_rules_bundle(raw)
    assert status.payload is None
    assert status.error is not None


def test_validate_accepts_empty_rules_list() -> None:
    """An empty rules list is unusual but valid — represents
    a deployment with all rules disabled, not a corrupt
    bundle."""
    from lap_coach_logger.rules_bundle import validate_rules_bundle

    raw = json.dumps({
        "version": "1.0.0",
        "rules": [],
    }).encode("utf-8")
    status = validate_rules_bundle(raw)
    assert status.error is None
    assert status.payload == {"version": "1.0.0", "rules": []}


# -- load_cached_rules_bundle -----------------------------------------


def test_load_cached_returns_parsed_dict(tmp_path: Path) -> None:
    """End-to-end: write a valid bundle to the cache, then
    load it — must return the parsed dict."""
    from lap_coach_logger.rules_bundle import load_cached_rules_bundle

    cache = tmp_path / "rules.json"
    cache.write_text(json.dumps({
        "version": "1.0.0",
        "rules": [{"id": "r1"}],
    }), encoding="utf-8")

    loaded = load_cached_rules_bundle(cache)
    assert loaded is not None
    assert loaded["version"] == "1.0.0"
    assert loaded["rules"] == [{"id": "r1"}]


def test_load_cached_returns_none_when_absent(tmp_path: Path) -> None:
    """No cache yet (first launch before download completes)
    → None. Callers fall back to bundled defaults."""
    from lap_coach_logger.rules_bundle import load_cached_rules_bundle

    assert load_cached_rules_bundle(tmp_path / "missing.json") is None


def test_load_cached_returns_none_when_malformed(tmp_path: Path) -> None:
    """Corrupt cache (truncated download, manual edit, AV
    interference) → None, never raise. App must be able to
    cold-start despite a corrupt cache."""
    from lap_coach_logger.rules_bundle import load_cached_rules_bundle

    cache = tmp_path / "rules.json"
    cache.write_text("not valid json")
    assert load_cached_rules_bundle(cache) is None


def test_load_cached_returns_none_when_wrong_shape(tmp_path: Path) -> None:
    """Cache parses as JSON but doesn't match the bundle
    schema (e.g., a previous version's format) → None."""
    from lap_coach_logger.rules_bundle import load_cached_rules_bundle

    cache = tmp_path / "rules.json"
    cache.write_text(json.dumps({"only": "wrong-fields"}), encoding="utf-8")
    assert load_cached_rules_bundle(cache) is None
