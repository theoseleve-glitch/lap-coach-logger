# Coaching Rules — Client-Side Execution

_Last reviewed: 2026-04-26_

This document explains how the desktop client receives, caches,
and executes the coaching rule bundle that drives live, in-car
prompts and post-session insights.

The architectural decision behind the design lives in
**ADR-009** (Live coaching latency policy) and
**ADR-010** (Offline-first contract).

## 1. Why client-side execution

Live coaching prompts have to fire within ~200 ms of the
triggering event (entering Sector 2, locking a brake, etc.).
A network round-trip to the server cannot meet that budget on
a typical residential connection — even a 50 ms RTT plus
serialization overhead eats most of the budget, and a flaky
connection breaks coaching entirely.

ADR-009 splits the responsibility:

- **Server authors the rules.** The coaching library (~80–150
  rules) is curated, versioned, and compiled to a portable
  bundle on the server. Server decides _which_ rules ship.
- **Client executes the rules.** The desktop fetches the
  bundle once per session (or reuses a cached copy up to 7
  days old per ADR-010), and evaluates conditions locally
  against the live telemetry feature stream. Client decides
  _when_ each rule fires.

This preserves "server owns the brain" while meeting the
latency requirement.

## 2. Bundle format

The wire format is JSON with four required top-level keys
(see ``_REQUIRED_BUNDLE_FIELDS`` in
``src/lap_coach_logger/coaching/rules_engine.py``):

| Field | Type | Meaning |
|-------|------|---------|
| `schema_version` | int | Bundle schema version (1 today). Bumped when the rule shape itself changes. |
| `bundle_id` | string | Stable identifier for the published bundle. The client logs this with every coaching event so server-side analytics can join "rule fired" telemetry against "rule body". |
| `compiled_at` | ISO-8601 UTC string | When the server compiled this bundle. Used by the client's freshness logic to decide whether to re-fetch. |
| `rules` | list | One entry per rule. |

Each rule entry has four required fields:

| Field | Type | Meaning |
|-------|------|---------|
| `id` | string | Stable rule id; appears in coaching telemetry. |
| `category` | string | Insight category (braking / cornering / strategy / …). Drives presentation and severity tier. |
| `condition` | dict | Condition DSL evaluated against the live feature dict. See `evaluate_condition`. |
| `insight` | dict | Insight payload (text template, severity, audio cue id, …). Owned by the presentation layer. |

The runtime types are `RuleBundle` and `Rule`, both
`@dataclass(frozen=True)` so a mis-typed bundle fails fast at
parse time rather than mid-session.

## 3. Module layout

The rules-engine code lives in
``src/lap_coach_logger/coaching/`` and is organised as:

- `rules_engine.py` — bundle parser, fetcher, cache, condition
  evaluator. Exports `RuleBundle`, `Rule`, `BundleSource`,
  `RuleBundleHttpClient`, `RuleBundleCache`,
  `load_bundle_with_fallback`, `evaluate_condition`.
- `presentation.py` — turns a fired rule's `insight` payload
  into the user-visible coaching card / audio cue.
- `corner_insights.py` — corner-by-corner derived insights
  (braking, apex speed, throttle release) computed locally
  from the per-lap trace.
- `post_session_summary.py` — assembles the post-session
  recap card from the lap-by-lap insights.
- `plan_engine.py` / `plan_evaluator.py` — next-session plan
  generation and evaluation against the actual run.
- `readiness.py` — the green/yellow/red readiness label that
  gates whether live coaching engages at all.
- `surface_policy.py` — decides which insights surface to the
  user vs. log silently (severity gating).
- `policy_config.py` / `output.py` / `strategy_review.py` —
  supporting infrastructure for the above.

## 4. Lifecycle

1. **Session start** — `load_bundle_with_fallback` is called
   with the configured `BundleSource` (network, cache, or
   embedded fallback).
   1. Try the network if the bundle on cache is older than the
      freshness window (or absent). On HTTP success, write the
      bundle to the cache.
   2. On network failure (or offline mode), reuse the cached
      bundle if it's within the ADR-010 freshness window
      (currently 7 days).
   3. If the cache is stale or missing, fall back to the
      embedded baseline bundle that ships with the binary —
      the user always gets _some_ coaching, even on first
      launch with no internet.
2. **Live session** — for each tick of the live feature
   stream, the engine evaluates every rule's `condition`
   against the feature dict. Conditions that match produce a
   `CoachingInsight`, which the presentation layer queues for
   display.
3. **Session end** — the post-session summary collects the
   final set of insights and the strategy review evaluates
   the run against the active plan.

## 5. Failure handling

- **Bad bundle JSON** — `RuleBundleParseError` on parse;
  caller falls through to the cached / embedded path.
- **Bad rule body** — caught at `_build_rule` time; the
  rule is logged + skipped, not the whole bundle dropped.
- **Bad condition at runtime** — `RuleConditionError` is
  caught, logged, and the rule is skipped for the rest of
  the session. One rotten rule never blocks the others.
- **HTTP fetch failure** — `RuleBundleFetchError`; the
  fallback chain takes over.
- **Cache file corrupt** — `RuleBundleCacheError`; the cache
  is treated as missing.

## 6. Drift prevention

`tests/test_coaching_rules_doc.py` pins:

- The doc references ADR-009.
- The doc names `RuleBundle`, `Rule`, `BundleSource`.
- The doc lists the four required bundle fields.
- The doc carries a "Last reviewed" date.

Renaming a class or adding a required bundle field without
updating this doc fails CI.
