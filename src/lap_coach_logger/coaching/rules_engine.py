"""T076: Rules engine client — compiled-bundle parser.

ADR-009 splits the coaching library across server (authors rules)
and client (executes rules during live session). This module is
the client's **parser**: hand it a JSON dict (or raw text) and
get back a typed :class:`RuleBundle`. Downstream tasks layer on
top:

- T077 — disk cache (fetch once, reuse for 7 days)
- T078 — signature verification of the cached bundle
- T079 — condition evaluation against a feature dict
- T080 — wiring to the live telemetry processor

The :attr:`Rule.condition` and :attr:`Rule.insight` payloads stay as
plain ``dict`` values at this layer — T079 owns the condition DSL,
T091 owns the insight presentation shape, and locking either of
them in T076 would force a Block-F rework when those land.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class RuleBundleParseError(ValueError):
    """Raised when a bundle payload can't be parsed into a typed
    :class:`RuleBundle` — invalid JSON, missing required fields,
    wrong types, etc. Wraps the underlying error so callers don't
    have to depend on the ``json`` module to pattern-match."""


class RuleBundleFetchError(RuntimeError):
    """Raised when the HTTP fetch for a bundle fails — network
    error, non-2xx status, or malformed JSON in a 2xx response.
    Distinct from :class:`RuleBundleParseError` so callers can
    decide between "fall back to cache" (fetch error) and "cache
    is now corrupted" (parse error)."""


class RuleBundleCacheError(RuntimeError):
    """Raised when a cache load fails *signature verification*
    on a payload that was otherwise fresh & parseable — i.e.,
    a tampering signal worth escalating, not just "fall back to
    network". Missing / corrupt / TTL-expired all collapse to
    ``None`` instead so callers cold-start by re-fetching."""


@dataclass(frozen=True)
class Rule:
    """One coaching rule from the bundle."""

    id: str
    category: str
    condition: dict[str, Any]
    insight: dict[str, Any]
    min_corroborating_laps: int = 1


@dataclass(frozen=True)
class RuleBundle:
    """Versioned, server-authored bundle of coaching rules."""

    schema_version: str
    bundle_id: str
    compiled_at: str
    rules: list[Rule] = field(default_factory=list)


_REQUIRED_BUNDLE_FIELDS = ("schema_version", "bundle_id", "compiled_at", "rules")
_REQUIRED_RULE_FIELDS = ("id", "category", "condition", "insight")


def load_bundle(data: str | dict[str, Any]) -> RuleBundle:
    """Parse a JSON bundle (text or already-decoded dict) into
    a :class:`RuleBundle`.

    Forward-compat by design: unknown top-level and per-rule
    fields are silently ignored so the server can add metadata
    (signatures, telemetry requirements, …) without forcing a
    coordinated client release.
    """
    payload = _decode(data)
    _require_fields(payload, _REQUIRED_BUNDLE_FIELDS, context="bundle")

    raw_rules = payload["rules"]
    if not isinstance(raw_rules, list):
        raise RuleBundleParseError(
            f"bundle 'rules' must be a list, got {type(raw_rules).__name__}"
        )

    rules = [_build_rule(entry, index=i) for i, entry in enumerate(raw_rules)]

    return RuleBundle(
        schema_version=str(payload["schema_version"]),
        bundle_id=str(payload["bundle_id"]),
        compiled_at=str(payload["compiled_at"]),
        rules=rules,
    )


def _decode(data: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        try:
            decoded = json.loads(data)
        except json.JSONDecodeError as exc:
            raise RuleBundleParseError(f"invalid JSON: {exc}") from exc
        if not isinstance(decoded, dict):
            raise RuleBundleParseError(
                f"bundle root must be an object, got {type(decoded).__name__}"
            )
        return decoded
    raise RuleBundleParseError(
        f"bundle must be a dict or JSON string, got {type(data).__name__}"
    )


def _require_fields(
    payload: dict[str, Any], fields: tuple[str, ...], *, context: str
) -> None:
    missing = [f for f in fields if f not in payload]
    if missing:
        raise RuleBundleParseError(
            f"{context} missing required field(s): {', '.join(missing)}"
        )


def _build_rule(entry: Any, *, index: int) -> Rule:
    if not isinstance(entry, dict):
        raise RuleBundleParseError(
            f"rules[{index}] must be an object, got {type(entry).__name__}"
        )
    _require_fields(entry, _REQUIRED_RULE_FIELDS, context=f"rules[{index}]")

    condition = entry["condition"]
    insight = entry["insight"]
    if not isinstance(condition, dict):
        raise RuleBundleParseError(
            f"rules[{index}].condition must be an object, "
            f"got {type(condition).__name__}"
        )
    if not isinstance(insight, dict):
        raise RuleBundleParseError(
            f"rules[{index}].insight must be an object, "
            f"got {type(insight).__name__}"
        )

    return Rule(
        id=str(entry["id"]),
        category=str(entry["category"]),
        condition=condition,
        insight=insight,
        min_corroborating_laps=int(entry.get("min_corroborating_laps", 1)),
    )


@dataclass(frozen=True)
class CachedBundle:
    """A bundle loaded back from the on-disk cache, paired with
    the verbatim raw payload so T078 can sig-verify it without
    re-fetching from the server."""

    bundle: RuleBundle
    raw_payload: str
    cached_at: str  # ISO 8601 UTC


_RULES_BUNDLE_PATH = "/api/v1/coaching/rules-bundle"


class RuleBundleHttpClient:
    """HTTP client for the compiled rules-bundle endpoint.

    Mirrors :class:`IngestClient`'s shape: ``base_url`` is the
    server origin, transport is injectable for hermetic tests, and
    auth is a Bearer token passed at call-time so the same client
    instance survives token rotation.
    """

    def __init__(
        self,
        *,
        base_url: str,
        path: str = _RULES_BUNDLE_PATH,
        opener: Callable[[Request], Any] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._path = path
        self._opener = opener if opener is not None else urlopen

    def fetch(self, *, auth_token: str) -> tuple[RuleBundle, str]:
        """Fetch the latest compiled bundle.

        Returns ``(parsed_bundle, raw_payload)``; the raw payload
        is what T078 sig-verifies against and what
        :class:`RuleBundleCache` persists.
        """
        request = Request(
            f"{self._base_url}{self._path}",
            headers={"Authorization": f"Bearer {auth_token}"},
            method="GET",
        )
        try:
            with self._opener(request) as response:
                raw_bytes = response.read()
        except HTTPError as exc:
            raise RuleBundleFetchError(
                f"server returned HTTP {exc.code}"
            ) from exc
        except URLError as exc:
            raise RuleBundleFetchError(f"network error: {exc.reason}") from exc

        try:
            raw_payload = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RuleBundleFetchError("response was not valid UTF-8") from exc

        try:
            bundle = load_bundle(raw_payload)
        except RuleBundleParseError as exc:
            raise RuleBundleFetchError(
                f"server returned malformed bundle: {exc}"
            ) from exc

        return bundle, raw_payload


class RuleBundleCache:
    """Disk cache for the compiled rules bundle.

    Persists the **raw** server payload verbatim so T078 can
    signature-verify against it byte-for-byte. Re-parses on load.

    Missing / corrupt / TTL-expired loads collapse to ``None`` so
    callers cold-start (typically: re-fetch from the server)
    without user intervention. Signature mismatch on an otherwise
    valid+fresh cache raises :class:`RuleBundleCacheError` because
    that's a tampering signal worth escalating, not a routine miss.
    """

    def __init__(self, *, path: Path) -> None:
        self._path = Path(path)

    def save(self, raw_payload: str, *, signature: str = "") -> None:
        """Persist ``raw_payload`` (and ``signature``, if provided)
        to disk with a ``cached_at`` timestamp. Creates parent
        directories as needed."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        envelope = {
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "payload": raw_payload,
            "signature": signature,
        }
        self._path.write_text(json.dumps(envelope), encoding="utf-8")

    def load(
        self,
        *,
        max_age: timedelta | None = None,
        now: Callable[[], datetime] | None = None,
        verifier: Callable[[str, str], bool] | None = None,
    ) -> CachedBundle | None:
        """Return the cached bundle, or ``None`` if the cache
        can't satisfy the request (missing, corrupt, old shape,
        payload no longer parseable, TTL expired).

        :param max_age: TTL window. ``None`` skips the age check
            (T077 callers that haven't migrated).
        :param now: Clock injection point for tests; defaults to
            ``datetime.now(timezone.utc)``.
        :param verifier: ``(payload, signature) -> bool`` callback
            for signature verification. ``None`` skips the check.
            A mismatched signature raises
            :class:`RuleBundleCacheError`.
        """
        if not self._path.exists():
            return None
        try:
            envelope = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(envelope, dict):
            return None
        raw_payload = envelope.get("payload")
        cached_at = envelope.get("cached_at")
        if not isinstance(raw_payload, str) or not isinstance(cached_at, str):
            return None

        if max_age is not None:
            current_time = (now or _utc_now)()
            try:
                cached_dt = datetime.fromisoformat(cached_at)
            except ValueError:
                return None
            if current_time - cached_dt > max_age:
                return None

        if verifier is not None:
            signature = envelope.get("signature")
            if not isinstance(signature, str) or not signature:
                raise RuleBundleCacheError(
                    "cache entry has no signature but verification was requested"
                )
            if not verifier(raw_payload, signature):
                raise RuleBundleCacheError(
                    "cache signature did not verify — possible tampering"
                )

        try:
            bundle = load_bundle(raw_payload)
        except RuleBundleParseError:
            return None
        return CachedBundle(
            bundle=bundle, raw_payload=raw_payload, cached_at=cached_at
        )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "CachedBundle",
    "Rule",
    "RuleBundle",
    "RuleBundleCache",
    "RuleBundleCacheError",
    "RuleBundleFetchError",
    "RuleBundleHttpClient",
    "RuleBundleParseError",
    "load_bundle",
]
