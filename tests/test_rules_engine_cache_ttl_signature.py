"""T078: ``RuleBundleCache`` enforces TTL and signature.

T077 shipped the round-trip cache. T078 adds two protections:

- **TTL** (default 7 days) — stale cache returns ``None`` so the
  caller re-fetches. Per ADR-010 ("Desktop live coaching: works
  offline, IF rules fetched within last 7 days") this matches the
  offline guarantee window.

- **Signature verification** — the server signs each bundle;
  cache load rejects tampered payloads. The verifier is injectable
  so tests use stdlib HMAC; production wiring later substitutes
  the real public-key verifier (probably via ``cryptography``
  library, T090's job).

Failing TTL or signature returns ``None`` from ``load()`` — same
shape as missing/corrupt — so callers cold-start by re-fetching.
A typed ``RuleBundleCacheError`` is raised only when the *caller*
asked for sig-verification and the cache **was** fresh & parseable
but signature doesn't match: that's a tampering signal worth
escalating, not just "fall back to network".
"""
from __future__ import annotations

import hmac
import json
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Callable

import pytest

from lap_coach_logger.coaching.rules_engine import (
    RuleBundleCache,
    RuleBundleCacheError,
)


_SECRET = b"unit-test-secret-DO-NOT-USE-IN-PRODUCTION"


def _hmac_sign(payload: str) -> str:
    """Stdlib HMAC-SHA256 for tests. Production uses real keys
    via the verifier callback."""
    return hmac.new(_SECRET, payload.encode("utf-8"), sha256).hexdigest()


def _hmac_verifier() -> Callable[[str, str], bool]:
    def verify(payload: str, signature: str) -> bool:
        return hmac.compare_digest(_hmac_sign(payload), signature)

    return verify


def _minimal_payload() -> str:
    return json.dumps(
        {
            "schema_version": "1.0",
            "bundle_id": "rules-2026-q1-v1",
            "compiled_at": "2026-04-25T00:00:00Z",
            "rules": [],
        }
    )


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------


def test_save_persists_signature_alongside_payload(tmp_path: Path) -> None:
    """Sig-verify-on-load needs the signature in the envelope —
    pulling it back out of the payload bytes themselves would
    require parsing JSON we may not trust yet."""
    cache_path = tmp_path / "rules_cache.json"
    cache = RuleBundleCache(path=cache_path)
    payload = _minimal_payload()

    cache.save(payload, signature=_hmac_sign(payload))

    envelope = json.loads(cache_path.read_text(encoding="utf-8"))
    assert envelope["signature"] == _hmac_sign(payload)


def test_load_with_matching_signature_returns_bundle(tmp_path: Path) -> None:
    cache = RuleBundleCache(path=tmp_path / "rules.json")
    payload = _minimal_payload()
    cache.save(payload, signature=_hmac_sign(payload))

    loaded = cache.load(verifier=_hmac_verifier())

    assert loaded is not None
    assert loaded.bundle.bundle_id == "rules-2026-q1-v1"


def test_load_with_no_verifier_skips_signature_check(tmp_path: Path) -> None:
    """``verifier=None`` means "trust the cache" — the existing
    T077 behaviour. Required for a graceful migration: previously
    cached bundles still load."""
    cache = RuleBundleCache(path=tmp_path / "rules.json")
    cache.save(_minimal_payload(), signature="bogus")

    loaded = cache.load()  # no verifier passed

    assert loaded is not None


def test_load_with_mismatched_signature_raises_cache_error(
    tmp_path: Path,
) -> None:
    """Tampered payload — escalate as :class:`RuleBundleCacheError`
    so the caller can clear the cache + alert the user.

    Distinct from "missing/corrupt → None" because tamper-detection
    is a security signal, not a routine cache miss."""
    cache = RuleBundleCache(path=tmp_path / "rules.json")
    cache.save(_minimal_payload(), signature="ffff" * 16)  # wrong sig

    with pytest.raises(RuleBundleCacheError):
        cache.load(verifier=_hmac_verifier())


def test_load_treats_missing_signature_as_invalid_when_verifier_set(
    tmp_path: Path,
) -> None:
    """Old cache entries (saved by T077, without a signature)
    must NOT silently bypass verification. Either the user has
    asked for sig-verify (pass verifier) and gets the error, or
    they haven't (no verifier) and skip the check entirely."""
    cache_path = tmp_path / "rules.json"
    cache_path.write_text(
        json.dumps(
            {
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "payload": _minimal_payload(),
                # no signature field
            }
        ),
        encoding="utf-8",
    )

    cache = RuleBundleCache(path=cache_path)

    with pytest.raises(RuleBundleCacheError):
        cache.load(verifier=_hmac_verifier())


# ---------------------------------------------------------------------------
# TTL enforcement
# ---------------------------------------------------------------------------


def _save_at(
    tmp_path: Path,
    cached_at: datetime,
    *,
    payload: str | None = None,
    signature: str = "",
) -> RuleBundleCache:
    """Bypass ``cache.save`` to backdate ``cached_at``."""
    cache_path = tmp_path / "rules.json"
    cache_path.write_text(
        json.dumps(
            {
                "cached_at": cached_at.isoformat(),
                "payload": payload if payload is not None else _minimal_payload(),
                "signature": signature,
            }
        ),
        encoding="utf-8",
    )
    return RuleBundleCache(path=cache_path)


def test_load_returns_bundle_when_within_ttl(tmp_path: Path) -> None:
    """Six days old, 7-day TTL — fresh enough."""
    fixed_now = datetime(2026, 4, 25, tzinfo=timezone.utc)
    cache = _save_at(tmp_path, fixed_now - timedelta(days=6))

    loaded = cache.load(max_age=timedelta(days=7), now=lambda: fixed_now)

    assert loaded is not None


def test_load_returns_none_when_past_ttl(tmp_path: Path) -> None:
    """Eight days old, 7-day TTL — stale, cold-start."""
    fixed_now = datetime(2026, 4, 25, tzinfo=timezone.utc)
    cache = _save_at(tmp_path, fixed_now - timedelta(days=8))

    loaded = cache.load(max_age=timedelta(days=7), now=lambda: fixed_now)

    assert loaded is None


def test_load_with_no_ttl_arg_skips_age_check(tmp_path: Path) -> None:
    """``max_age=None`` — caller opts out of the TTL check.
    Mirrors T077's behaviour for callers that haven't migrated."""
    cache = _save_at(
        tmp_path,
        datetime(2020, 1, 1, tzinfo=timezone.utc),  # ancient
    )

    loaded = cache.load()  # no max_age

    assert loaded is not None


def test_load_returns_none_when_cached_at_is_unparseable(tmp_path: Path) -> None:
    """A garbled timestamp under TTL enforcement collapses to
    cold-start (same as missing/corrupt). Don't crash on a
    bad ISO string — the cache file is opaque user data."""
    cache_path = tmp_path / "rules.json"
    cache_path.write_text(
        json.dumps(
            {
                "cached_at": "not-a-valid-iso-string",
                "payload": _minimal_payload(),
                "signature": "",
            }
        ),
        encoding="utf-8",
    )
    cache = RuleBundleCache(path=cache_path)

    loaded = cache.load(
        max_age=timedelta(days=7),
        now=lambda: datetime(2026, 4, 25, tzinfo=timezone.utc),
    )

    assert loaded is None


# ---------------------------------------------------------------------------
# TTL + signature interaction
# ---------------------------------------------------------------------------


def test_stale_cache_returns_none_even_when_signature_valid(
    tmp_path: Path,
) -> None:
    """TTL is checked **before** signature so an expired-but-valid
    cache short-circuits to None without spending CPU on
    HMAC. Signature verification is only meaningful on a fresh
    cache."""
    fixed_now = datetime(2026, 4, 25, tzinfo=timezone.utc)
    payload = _minimal_payload()
    cache = _save_at(
        tmp_path,
        fixed_now - timedelta(days=10),  # stale
        payload=payload,
        signature=_hmac_sign(payload),
    )

    loaded = cache.load(
        max_age=timedelta(days=7),
        now=lambda: fixed_now,
        verifier=_hmac_verifier(),
    )

    assert loaded is None  # not RuleBundleCacheError — TTL wins


def test_fresh_cache_with_bad_signature_still_raises_error(
    tmp_path: Path,
) -> None:
    """Within TTL but signature mismatched — still a tampering
    signal that warrants escalation."""
    fixed_now = datetime(2026, 4, 25, tzinfo=timezone.utc)
    cache = _save_at(
        tmp_path,
        fixed_now - timedelta(days=1),
        signature="ffff" * 16,
    )

    with pytest.raises(RuleBundleCacheError):
        cache.load(
            max_age=timedelta(days=7),
            now=lambda: fixed_now,
            verifier=_hmac_verifier(),
        )
