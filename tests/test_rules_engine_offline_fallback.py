"""T089: Offline fallback — when fetch fails AND cache is fresh,
use the cache silently. When fetch fails AND cache is stale, use
the cache anyway and surface a "rules out of date" banner signal.

Per ADR-010, desktop live coaching must work offline IF rules
were fetched within the last 7 days. T078 enforces that 7-day
TTL on a happy-path load. T089 covers the *unhappy* path: what
happens when the server is unreachable AND the cache is older
than 7 days?

Decision (per the task description): fall back to the stale
cache, but flag the load as ``BundleSource.STALE_CACHE`` so the
UI can show a "rules out of date" banner. Coaching keeps working
(graceful degradation) but the user knows it's not the latest
ruleset.

Resolution order (first hit wins):
1. ``FRESH_SERVER``  — network OK + server returns 2xx
2. ``FRESH_CACHE``   — network failed + cache within TTL
3. ``STALE_CACHE``   — network failed + cache *outside* TTL
4. ``NO_BUNDLE``     — network failed + no cache at all

The orchestrator stays out of T077/T078's way: it composes
their primitives, doesn't replace them. T077 callers can still
use the raw client/cache directly.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lap_coach_logger.coaching.rules_engine import (
    BundleSource,
    RuleBundleCache,
    RuleBundleFetchError,
    load_bundle_with_fallback,
)


def _payload(bundle_id: str = "rules-2026-q1-v1") -> str:
    return json.dumps(
        {
            "schema_version": "1.0",
            "bundle_id": bundle_id,
            "compiled_at": "2026-04-25T00:00:00Z",
            "rules": [
                {
                    "id": "br.late",
                    "category": "braking",
                    "condition": {"type": "feature_threshold"},
                    "insight": {"title": "Brake later"},
                }
            ],
        }
    )


class _FakeClient:
    """Stand-in for :class:`RuleBundleHttpClient` — ``fetch`` returns
    the configured bundle or raises :class:`RuleBundleFetchError`
    to simulate offline."""

    def __init__(
        self,
        *,
        payload: str | None = None,
        offline: bool = False,
    ) -> None:
        self._payload = payload
        self._offline = offline
        self.fetch_count = 0

    def fetch(self, *, auth_token: str):
        self.fetch_count += 1
        if self._offline:
            raise RuleBundleFetchError("network down (test)")
        from lap_coach_logger.coaching.rules_engine import load_bundle

        return load_bundle(self._payload), self._payload


def _seed_cache(
    tmp_path: Path,
    *,
    cached_at: datetime,
    payload: str | None = None,
) -> RuleBundleCache:
    """Plant a cache file directly so we can backdate ``cached_at``."""
    cache_path = tmp_path / "rules.json"
    cache_path.write_text(
        json.dumps(
            {
                "cached_at": cached_at.isoformat(),
                "payload": payload if payload is not None else _payload(),
                "signature": "",
            }
        ),
        encoding="utf-8",
    )
    return RuleBundleCache(path=cache_path)


# ---------------------------------------------------------------------------
# 1. FRESH_SERVER — happy path
# ---------------------------------------------------------------------------


def test_fresh_server_fetch_returns_fresh_source(tmp_path: Path) -> None:
    """Network OK + server responds. Source must be FRESH_SERVER
    so the UI doesn't show a banner."""
    client = _FakeClient(payload=_payload())
    cache = RuleBundleCache(path=tmp_path / "rules.json")

    result = load_bundle_with_fallback(
        client=client,
        cache=cache,
        auth_token="t",
        max_age=timedelta(days=7),
    )

    assert result.bundle.bundle_id == "rules-2026-q1-v1"
    assert result.source is BundleSource.FRESH_SERVER


def test_fresh_server_fetch_writes_cache(tmp_path: Path) -> None:
    """A successful fetch updates the cache so the next offline
    fall-back has a fresh bundle waiting."""
    client = _FakeClient(payload=_payload(bundle_id="server-says-this"))
    cache = RuleBundleCache(path=tmp_path / "rules.json")

    load_bundle_with_fallback(
        client=client,
        cache=cache,
        auth_token="t",
        max_age=timedelta(days=7),
    )

    cached = cache.load()
    assert cached is not None
    assert cached.bundle.bundle_id == "server-says-this"


# ---------------------------------------------------------------------------
# 2. FRESH_CACHE — fetch failed, cache within TTL
# ---------------------------------------------------------------------------


def test_offline_with_fresh_cache_returns_fresh_cache_source(
    tmp_path: Path,
) -> None:
    """Server unreachable, cache within 7-day TTL — silent
    fallback (no banner). Coaching is current; user has no signal
    they should have."""
    fixed_now = datetime(2026, 4, 25, tzinfo=timezone.utc)
    client = _FakeClient(offline=True)
    cache = _seed_cache(tmp_path, cached_at=fixed_now - timedelta(days=3))

    result = load_bundle_with_fallback(
        client=client,
        cache=cache,
        auth_token="t",
        max_age=timedelta(days=7),
        now=lambda: fixed_now,
    )

    assert result.bundle.bundle_id == "rules-2026-q1-v1"
    assert result.source is BundleSource.FRESH_CACHE


# ---------------------------------------------------------------------------
# 3. STALE_CACHE — fetch failed, cache outside TTL
# ---------------------------------------------------------------------------


def test_offline_with_stale_cache_returns_stale_source(
    tmp_path: Path,
) -> None:
    """Server unreachable, cache 10 days old (past 7-day TTL).
    Use the cache anyway (per ADR-010 graceful-degradation
    intent) but flag as STALE_CACHE so the UI banners.

    Coaching keeps working — better an out-of-date rule
    suggesting "brake later" than no coaching at all on a
    multi-day flight away from internet."""
    fixed_now = datetime(2026, 4, 25, tzinfo=timezone.utc)
    client = _FakeClient(offline=True)
    cache = _seed_cache(tmp_path, cached_at=fixed_now - timedelta(days=10))

    result = load_bundle_with_fallback(
        client=client,
        cache=cache,
        auth_token="t",
        max_age=timedelta(days=7),
        now=lambda: fixed_now,
    )

    assert result.bundle.bundle_id == "rules-2026-q1-v1"
    assert result.source is BundleSource.STALE_CACHE


# ---------------------------------------------------------------------------
# 4. NO_BUNDLE — fetch failed, no cache at all
# ---------------------------------------------------------------------------


def test_offline_with_no_cache_returns_no_bundle(tmp_path: Path) -> None:
    """Cold-start offline: no cache + no network. Coaching is
    impossible; UI must show a "connect to internet to enable
    coaching" empty state. ``bundle`` is None so the caller can't
    accidentally use it."""
    client = _FakeClient(offline=True)
    cache = RuleBundleCache(path=tmp_path / "missing.json")

    result = load_bundle_with_fallback(
        client=client,
        cache=cache,
        auth_token="t",
        max_age=timedelta(days=7),
    )

    assert result.bundle is None
    assert result.source is BundleSource.NO_BUNDLE


# ---------------------------------------------------------------------------
# Resolution order pin
# ---------------------------------------------------------------------------


def test_server_is_tried_before_cache_when_both_available(
    tmp_path: Path,
) -> None:
    """Even with a fresh cache available, the orchestrator MUST
    try the server first — the server may have shipped an updated
    rule and the user shouldn't be stuck on the cached version
    just because the cache is fresh."""
    fixed_now = datetime(2026, 4, 25, tzinfo=timezone.utc)
    client = _FakeClient(payload=_payload(bundle_id="server-newer"))
    cache = _seed_cache(
        tmp_path,
        cached_at=fixed_now - timedelta(days=1),
        payload=_payload(bundle_id="cache-older"),
    )

    result = load_bundle_with_fallback(
        client=client,
        cache=cache,
        auth_token="t",
        max_age=timedelta(days=7),
        now=lambda: fixed_now,
    )

    assert result.bundle.bundle_id == "server-newer"
    assert client.fetch_count == 1


def test_fresh_cache_preferred_over_stale_cache(tmp_path: Path) -> None:
    """If somehow the cache write date is fresh AND we're offline,
    we should use the *fresh* path even though the stale path
    would also accept it. Pinning this prevents an off-by-one
    where the fallback chain accidentally always lands on STALE."""
    fixed_now = datetime(2026, 4, 25, tzinfo=timezone.utc)
    client = _FakeClient(offline=True)
    cache = _seed_cache(tmp_path, cached_at=fixed_now - timedelta(hours=1))

    result = load_bundle_with_fallback(
        client=client,
        cache=cache,
        auth_token="t",
        max_age=timedelta(days=7),
        now=lambda: fixed_now,
    )

    assert result.source is BundleSource.FRESH_CACHE


# ---------------------------------------------------------------------------
# Banner-signal helper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expects_banner"),
    [
        (BundleSource.FRESH_SERVER, False),
        (BundleSource.FRESH_CACHE, False),
        (BundleSource.STALE_CACHE, True),
        (BundleSource.NO_BUNDLE, False),  # different UX (empty state, not banner)
    ],
)
def test_bundle_source_signals_banner_intent(
    source: BundleSource, expects_banner: bool
) -> None:
    """The UI doesn't need to know about the four-way enum — a
    boolean ``should_show_stale_banner`` is the actual decision
    point. Pinning this here means the QML side stays decoupled
    from the orchestrator's vocabulary."""
    assert source.should_show_stale_banner is expects_banner
