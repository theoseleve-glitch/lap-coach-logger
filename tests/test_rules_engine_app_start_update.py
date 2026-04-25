"""T090: At app start, the rules engine fetches a newer
bundle from the server when one is available.

Two related questions T090 pins:

1. **When server is reachable**, does the orchestrator pick the
   server's bundle even if a fresh cache exists? (Yes — server
   is the source of truth; cache is opportunistic.)

2. **How is "newer" detected** when callers want to optimise
   the boot path (e.g., skip fetch if server's ``compiled_at``
   matches cache's)? T090 ships :func:`is_bundle_newer_than_cache`
   so an upstream "background-update" path can take that
   decision without a full ``load_bundle_with_fallback`` cycle.

Both questions are part of "if server has newer bundle, fetch":
the orchestrator covers the *behaviour*, the helper covers the
*decision*. Either one alone leaves a gap.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lap_coach_logger.coaching.rules_engine import (
    BundleSource,
    RuleBundleCache,
    is_bundle_newer_than_cache,
    load_bundle,
    load_bundle_with_fallback,
)


def _payload(*, bundle_id: str, compiled_at: str) -> str:
    return json.dumps(
        {
            "schema_version": "1.0",
            "bundle_id": bundle_id,
            "compiled_at": compiled_at,
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
    def __init__(self, payload: str) -> None:
        self._payload = payload

    def fetch(self, *, auth_token: str):
        return load_bundle(self._payload), self._payload


def _seed_cache(
    tmp_path: Path,
    *,
    bundle_id: str,
    compiled_at: str,
    cached_at: datetime,
) -> RuleBundleCache:
    cache_path = tmp_path / "rules.json"
    cache_path.write_text(
        json.dumps(
            {
                "cached_at": cached_at.isoformat(),
                "payload": _payload(
                    bundle_id=bundle_id, compiled_at=compiled_at
                ),
                "signature": "",
            }
        ),
        encoding="utf-8",
    )
    return RuleBundleCache(path=cache_path)


# ---------------------------------------------------------------------------
# Orchestrator: server-newer wins even with fresh cache
# ---------------------------------------------------------------------------


def test_app_start_uses_server_bundle_when_newer_than_cache(
    tmp_path: Path,
) -> None:
    """Cache has yesterday's bundle, server has today's. App
    start fetches today's — the cache is opportunistic, not
    authoritative."""
    fixed_now = datetime(2026, 4, 25, tzinfo=timezone.utc)
    server = _FakeClient(
        _payload(bundle_id="rules-v2", compiled_at="2026-04-25T00:00:00Z")
    )
    cache = _seed_cache(
        tmp_path,
        bundle_id="rules-v1",
        compiled_at="2026-04-24T00:00:00Z",
        cached_at=fixed_now - timedelta(hours=1),
    )

    result = load_bundle_with_fallback(
        client=server,
        cache=cache,
        auth_token="t",
        max_age=timedelta(days=7),
        now=lambda: fixed_now,
    )

    assert result.bundle.bundle_id == "rules-v2"
    assert result.source is BundleSource.FRESH_SERVER


def test_app_start_writes_newer_bundle_to_cache(tmp_path: Path) -> None:
    """The follow-on app start (or session start) without
    network must find the new bundle in cache, not the old one.
    Pinning the cache-write step here closes the upgrade loop."""
    fixed_now = datetime(2026, 4, 25, tzinfo=timezone.utc)
    server = _FakeClient(
        _payload(bundle_id="rules-v2", compiled_at="2026-04-25T00:00:00Z")
    )
    cache = _seed_cache(
        tmp_path,
        bundle_id="rules-v1",
        compiled_at="2026-04-24T00:00:00Z",
        cached_at=fixed_now - timedelta(hours=1),
    )

    load_bundle_with_fallback(
        client=server,
        cache=cache,
        auth_token="t",
        max_age=timedelta(days=7),
        now=lambda: fixed_now,
    )

    cached_after = cache.load()
    assert cached_after is not None
    assert cached_after.bundle.bundle_id == "rules-v2"


# ---------------------------------------------------------------------------
# is_bundle_newer_than_cache: explicit decision helper
# ---------------------------------------------------------------------------


def test_helper_says_yes_when_server_compiled_at_is_later(
    tmp_path: Path,
) -> None:
    """``compiled_at`` is the canonical "newer" signal — the
    server stamps it during compilation and the value increases
    monotonically per bundle release."""
    cache = _seed_cache(
        tmp_path,
        bundle_id="rules-v1",
        compiled_at="2026-04-20T00:00:00Z",
        cached_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
    )
    server_bundle = load_bundle(
        _payload(bundle_id="rules-v2", compiled_at="2026-04-25T00:00:00Z")
    )

    assert is_bundle_newer_than_cache(server_bundle, cache=cache) is True


def test_helper_says_no_when_server_compiled_at_matches_cache(
    tmp_path: Path,
) -> None:
    """Same ``compiled_at`` ⇒ no update — the orchestrator can
    skip the cache-write step without harm. Saves disk I/O on
    every app start when nothing has changed."""
    cache = _seed_cache(
        tmp_path,
        bundle_id="rules-v1",
        compiled_at="2026-04-25T00:00:00Z",
        cached_at=datetime(2026, 4, 25, tzinfo=timezone.utc),
    )
    server_bundle = load_bundle(
        _payload(bundle_id="rules-v1", compiled_at="2026-04-25T00:00:00Z")
    )

    assert is_bundle_newer_than_cache(server_bundle, cache=cache) is False


def test_helper_says_no_when_server_is_older_than_cache(
    tmp_path: Path,
) -> None:
    """Server rolled back (rare but possible after a bad ship)
    — don't downgrade the user's cache. Surface as "no update";
    callers can choose whether to force-pull anyway."""
    cache = _seed_cache(
        tmp_path,
        bundle_id="rules-v2",
        compiled_at="2026-04-25T00:00:00Z",
        cached_at=datetime(2026, 4, 25, tzinfo=timezone.utc),
    )
    server_bundle = load_bundle(
        _payload(bundle_id="rules-v1", compiled_at="2026-04-20T00:00:00Z")
    )

    assert is_bundle_newer_than_cache(server_bundle, cache=cache) is False


def test_helper_says_yes_when_cache_is_empty(tmp_path: Path) -> None:
    """Cold-start: any server bundle counts as "newer than
    nothing". Without this branch the helper would return False
    and the boot path would think the server's bundle was
    redundant."""
    cache = RuleBundleCache(path=tmp_path / "missing.json")
    server_bundle = load_bundle(
        _payload(bundle_id="rules-v1", compiled_at="2026-04-25T00:00:00Z")
    )

    assert is_bundle_newer_than_cache(server_bundle, cache=cache) is True
