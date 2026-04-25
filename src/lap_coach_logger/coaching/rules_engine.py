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

import enum
import json
import queue
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Protocol
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


class RuleConditionError(RuntimeError):
    """Raised when a rule's ``condition`` dict is malformed or
    references an unsupported operator — almost always a server
    bug or an out-of-date client. Failing loudly (rather than
    silently no-firing) makes those bugs visible in logs/Sentry
    instead of becoming silent gaps in coaching coverage."""


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
class CoachingInsight:
    """One rule firing — the unit T091's overlay VM consumes.

    ``payload`` is the rule's verbatim ``insight`` dict (opaque
    to the engine, owned by the renderer). Frozen + plain-types
    by design so the live processor (T083) can hand-off across
    threads via ``Queue`` without locking.
    """

    rule_id: str
    payload: dict[str, Any]


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


class BundleSource(enum.Enum):
    """Where the bundle came from on this load — drives the UI's
    "rules out of date" banner."""

    FRESH_SERVER = "fresh_server"
    FRESH_CACHE = "fresh_cache"
    STALE_CACHE = "stale_cache"
    NO_BUNDLE = "no_bundle"

    @property
    def should_show_stale_banner(self) -> bool:
        """``True`` only when coaching is running on an out-of-TTL
        cache. NO_BUNDLE has its own empty-state UX (not a banner)."""
        return self is BundleSource.STALE_CACHE


@dataclass(frozen=True)
class BundleResolution:
    """Result of :func:`load_bundle_with_fallback`. ``bundle`` is
    ``None`` only when ``source is BundleSource.NO_BUNDLE``."""

    bundle: RuleBundle | None
    source: BundleSource


class _BundleClient(Protocol):
    """Structural shape of :class:`RuleBundleHttpClient` — just
    enough for the orchestrator to typecheck without coupling to
    the concrete client."""

    def fetch(self, *, auth_token: str) -> tuple[RuleBundle, str]: ...


def is_bundle_newer_than_cache(
    server_bundle: RuleBundle, *, cache: "RuleBundleCache"
) -> bool:
    """``True`` if the server's bundle should replace what's in
    cache, ``False`` if the cached version is current or newer.

    "Newer" is decided by ``compiled_at`` (ISO 8601 string from
    the server's compilation step). String comparison works
    because ISO 8601 sorts lexicographically when zones are
    consistent — and the server stamps everything in UTC.

    A missing/corrupt cache counts as "older than anything", so
    cold-start always upgrades. A server roll-back (server is
    older than cache) returns ``False`` so the upgrade path
    doesn't downgrade the user.
    """
    cached = cache.load()
    if cached is None:
        return True
    return server_bundle.compiled_at > cached.bundle.compiled_at


def load_bundle_with_fallback(
    *,
    client: _BundleClient,
    cache: "RuleBundleCache",
    auth_token: str,
    max_age: timedelta,
    now: Callable[[], datetime] | None = None,
) -> BundleResolution:
    """Resolve a bundle, falling back to cache when the server is
    unreachable.

    Resolution order (first hit wins):
    1. ``FRESH_SERVER`` — fetch succeeds; cache is updated.
    2. ``FRESH_CACHE``  — fetch fails, cache within ``max_age``.
    3. ``STALE_CACHE``  — fetch fails, cache outside ``max_age``.
       Returned anyway so coaching keeps working (per ADR-010
       graceful-degradation intent), with the source flag set so
       the UI can banner.
    4. ``NO_BUNDLE``    — fetch fails, no cache at all.

    Tries the server EVEN WITH a fresh cache because the server
    may ship rule updates between TTL ticks; the cache should
    never lock the user out of newer rules.
    """
    try:
        bundle, raw_payload = client.fetch(auth_token=auth_token)
    except RuleBundleFetchError:
        bundle = None
        raw_payload = None
    if bundle is not None and raw_payload is not None:
        cache.save(raw_payload)
        return BundleResolution(bundle=bundle, source=BundleSource.FRESH_SERVER)

    fresh = cache.load(max_age=max_age, now=now)
    if fresh is not None:
        return BundleResolution(
            bundle=fresh.bundle, source=BundleSource.FRESH_CACHE
        )

    stale = cache.load()  # no max_age → don't filter on TTL
    if stale is not None:
        return BundleResolution(
            bundle=stale.bundle, source=BundleSource.STALE_CACHE
        )

    return BundleResolution(bundle=None, source=BundleSource.NO_BUNDLE)


_COMPARISONS: dict[str, Callable[[float, float], bool]] = {
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "eq": lambda a, b: a == b,
}


def evaluate_condition(
    condition: dict[str, Any], *, features: dict[str, Any]
) -> bool:
    """Evaluate a rule's ``condition`` dict against a session
    feature snapshot.

    Supported operator types:

    - ``feature_threshold``: ``{feature, comparison, value}``.
      Comparisons: lt / lte / gt / gte / eq.
      Missing or non-numeric feature → ``False`` (not raise) — a
      rule depending on a metric that hasn't been computed for
      this lap yet should sit dormant, not crash the engine.

    - ``and`` / ``or``: ``{conditions: [...]}``. Children are
      themselves conditions, evaluated recursively. Empty children
      list collapses to vacuous-true (``and``) / vacuous-false
      (``or``) per Python's ``all([]) / any([])`` convention.

    Unknown operator types and malformed conditions raise
    :class:`RuleConditionError` — those are server-side bugs that
    should surface during dev rather than silently no-firing.
    """
    if not isinstance(condition, dict):
        raise RuleConditionError(
            f"condition must be a dict, got {type(condition).__name__}"
        )
    op_type = condition.get("type")

    if op_type == "feature_threshold":
        return _evaluate_feature_threshold(condition, features=features)
    if op_type == "and":
        children = _require_children(condition)
        return all(
            evaluate_condition(child, features=features) for child in children
        )
    if op_type == "or":
        children = _require_children(condition)
        return any(
            evaluate_condition(child, features=features) for child in children
        )

    raise RuleConditionError(f"unsupported condition type: {op_type!r}")


def _evaluate_feature_threshold(
    condition: dict[str, Any], *, features: dict[str, Any]
) -> bool:
    feature = condition.get("feature")
    comparison = condition.get("comparison")
    threshold = condition.get("value")
    if not isinstance(feature, str) or comparison is None or threshold is None:
        raise RuleConditionError(
            "feature_threshold requires feature, comparison, value"
        )
    op = _COMPARISONS.get(comparison)
    if op is None:
        raise RuleConditionError(f"unsupported comparison: {comparison!r}")

    feature_value = features.get(feature)
    if not isinstance(feature_value, (int, float)) or isinstance(
        feature_value, bool
    ):
        return False  # missing or non-numeric → dormant
    return op(float(feature_value), float(threshold))


def _require_children(condition: dict[str, Any]) -> list[dict[str, Any]]:
    children = condition.get("conditions")
    if not isinstance(children, list):
        raise RuleConditionError(
            f"{condition.get('type')} requires 'conditions' list"
        )
    return children


class CorroborationGate:
    """False-positive gating for noisy detectors.

    A rule with ``min_corroborating_laps > 1`` is suppressed
    until it has fired on N consecutive laps. After that, every
    subsequent firing lap re-emits — the user is still making
    the mistake, the gate has done its job suppressing first-fire
    noise. T092 (overlay VM cooldown) is the layer that says
    "stop telling me every lap forever".

    Reset semantics: a non-firing lap resets the rule's consecutive
    count to zero. Consecutive (not sliding-window) is the user-
    interpretable shape: "I've been doing this every lap since
    lap 5" is clearer than "I did this 3 of the last 5 laps".

    Default ``min_corroborating_laps = 1`` (T076) makes the gate
    a no-op for most rules — a noisy detector ships with N > 1
    explicitly to opt into corroboration.
    """

    def __init__(self, bundle: RuleBundle) -> None:
        self._min_laps_by_rule = {
            rule.id: rule.min_corroborating_laps for rule in bundle.rules
        }
        self._consec_fires: dict[str, int] = {
            rule.id: 0 for rule in bundle.rules
        }

    def process(
        self, insights: list[CoachingInsight]
    ) -> list[CoachingInsight]:
        """Update consecutive-fire counts for every known rule
        based on which ones fired this lap, then return the
        subset that has corroborated enough times to emit.

        Insights for rules unknown to the gate (e.g., bundle
        hot-reloaded between gate construction and this call)
        pass through with default min=1 rather than crashing —
        keeps the system operational across rule churn.
        """
        fired_ids = {i.rule_id for i in insights}

        for rule_id in self._min_laps_by_rule:
            if rule_id in fired_ids:
                self._consec_fires[rule_id] += 1
            else:
                self._consec_fires[rule_id] = 0

        return [
            insight
            for insight in insights
            if self._consec_fires.get(insight.rule_id, 1)
            >= self._min_laps_by_rule.get(insight.rule_id, 1)
        ]


class InsightCooldownFilter:
    """Per-rule cooldown — drops insights for rules shown within
    the cooldown window.

    Distinct from :class:`CorroborationGate`: that one suppresses
    *first-fire spam* (rule must fire on N consecutive laps before
    its first emission). This one suppresses *steady-state spam*
    (after the first emission, drop subsequent fires of the same
    rule until the cooldown expires).

    Default 30 s — long enough that the same coaching tip stops
    being useful (driver heard it; either fixing it or actively
    ignoring it for now), short enough that the tip can re-surface
    if the mistake persists across multiple corner sequences.

    ``cooldown_seconds=0`` disables the filter — the right default
    for tests that don't care about cooldown semantics.
    """

    def __init__(
        self,
        *,
        cooldown_seconds: float = 30.0,
        now: Callable[[], float] | None = None,
    ) -> None:
        if cooldown_seconds < 0:
            raise ValueError(
                f"cooldown_seconds must be >= 0, got {cooldown_seconds}"
            )
        self._cooldown_seconds = cooldown_seconds
        self._now = now if now is not None else time.monotonic
        self._last_shown_at: dict[str, float] = {}

    def filter(
        self, insights: list[CoachingInsight]
    ) -> list[CoachingInsight]:
        """Return insights NOT in cooldown, preserving input
        order. Updates the cooldown timer for those that pass."""
        if self._cooldown_seconds <= 0:
            return list(insights)
        current_time = self._now()
        passed: list[CoachingInsight] = []
        for insight in insights:
            last = self._last_shown_at.get(insight.rule_id)
            if last is None or current_time - last >= self._cooldown_seconds:
                passed.append(insight)
                self._last_shown_at[insight.rule_id] = current_time
        return passed


class InsightQueue:
    """Thread-safe handoff between the rules engine (sample
    thread, T083) and the overlay VM (Qt main thread, T091).

    Wraps :class:`queue.Queue` to expose just the two operations
    the boundary uses (publish list, drain to list). The Queue
    itself is thread-safe by construction in CPython, so all this
    layer adds is the engine-shaped API and an unbounded
    buffer — sample-thread publishes never raise ``queue.Full``,
    UI-thread drains never raise ``queue.Empty``.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[CoachingInsight] = queue.Queue()

    def publish(self, insights: list[CoachingInsight]) -> None:
        """Publish a list of insights produced by one
        :func:`evaluate_bundle` call. Empty list is a no-op
        (every lap calls this regardless of whether any rule
        fired, so the no-fire path stays branchless on the
        producer side)."""
        for insight in insights:
            self._queue.put_nowait(insight)

    def drain(self) -> list[CoachingInsight]:
        """Pull every pending insight off the queue and return
        them in the order they were published. Empty queue
        returns ``[]`` so the consumer's polling loop doesn't
        have to special-case "nothing yet"."""
        drained: list[CoachingInsight] = []
        while True:
            try:
                drained.append(self._queue.get_nowait())
            except queue.Empty:
                return drained


def evaluate_bundle(
    bundle: RuleBundle, *, features: dict[str, Any]
) -> list[CoachingInsight]:
    """Evaluate every rule in the bundle against ``features`` and
    return a list of :class:`CoachingInsight` for the rules that
    fired.

    Order preserves bundle order so T091's priority queue sees a
    deterministic stream. T088 will gate emission on N corroborating
    laps; T080 fires once per evaluation regardless.

    Per the live-processor invariant (T083), this runs at lap-end
    on the sample thread — keep it allocation-light. The output
    list is the only allocation per call.
    """
    return [
        CoachingInsight(rule_id=rule.id, payload=rule.insight)
        for rule in bundle.rules
        if evaluate_condition(rule.condition, features=features)
    ]


def write_live_insights(
    folder: Path, *, insights: list[CoachingInsight]
) -> None:
    """Serialise live-generated coaching insights to
    ``coaching_insights.json`` in the bundle ``folder``.

    Each entry is tagged ``source: "client"`` so the server can
    distinguish them from its own post-session insights (per
    ADR-009 — server is authoritative; client coaching is
    best-effort latency cover).

    Empty insights list still writes the file (with ``[]``) —
    the server's audit path needs to distinguish "client
    coaching off" (file absent) from "client coaching ran
    clean" (file empty).
    """
    payload = [
        {
            "rule_id": insight.rule_id,
            "payload": insight.payload,
            "source": "client",
        }
        for insight in insights
    ]
    (folder / "coaching_insights.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


__all__ = [
    "BundleResolution",
    "BundleSource",
    "CachedBundle",
    "CoachingInsight",
    "CorroborationGate",
    "InsightCooldownFilter",
    "InsightQueue",
    "Rule",
    "RuleBundle",
    "RuleBundleCache",
    "RuleBundleCacheError",
    "RuleBundleFetchError",
    "RuleBundleHttpClient",
    "RuleBundleParseError",
    "RuleConditionError",
    "evaluate_bundle",
    "evaluate_condition",
    "is_bundle_newer_than_cache",
    "load_bundle",
    "load_bundle_with_fallback",
    "write_live_insights",
]
