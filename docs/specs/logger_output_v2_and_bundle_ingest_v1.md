# Logger Output v2 + Connected Bundle Ingest v1

> **Status:** Approved for implementation. Derived from `docs/superpowers/specs/2026-04-15-connected-v1-master-spec.md` with locked decisions D1-D10.
> **Date:** 2026-04-15
> **Scope:** Desktop bundle writer (this repo) + backend ingest endpoint + canonical resolver integration. Webapp consumes via OpenAPI types — webapp changes specified in §9 but owned externally.
> **Hard constraint:** the finalized bundle is the canonical analysis-ready artifact. Native sim files (`.ibt`, `.ldx`, etc.) are provenance only; backend never parses them.

---

## 1. Executive summary

Today the desktop produces a rich session bundle on disk (`session.json`, `telemetry.parquet`, `laps.json`, `events.json`, `channels.json`, `quality_report.json`, sim-specific raw sidecars). The current sync stack ignores most of it and ships only minimal in-memory envelopes — drift between what the desktop knows and what the backend stores is structural.

This spec promotes the bundle to first-class status:

1. **Bundle schema v2** — adds `analysis.json`, embeds canonical IDs, declares a deterministic file inventory with per-file hashes, freezes a `bundle_hash` over the canonical set.
2. **Desktop-side canonical resolution** — the desktop ships with a snapshot of the registry LUT, resolves raw sim strings to `canonical_car_id` / `canonical_track_id` / `car_class` at finalize time, and writes them into `session.json`. Resolved bundles are usable offline and identical regardless of backend state.
3. **`POST /v1/bundles`** — single multipart endpoint accepts the whole bundle atomically. Backend validates, stores files in MinIO under `bundles/<user>/<session>/`, persists row data to Postgres, and **re-validates** the desktop's canonical IDs against its own registry. Drift is recorded, never silently overwritten.
4. **Idempotency** by `bundle_hash` (used as `Idempotency-Key`). Replay on the same user is a no-op; replay across users is rejected.
5. **Backfill** runs on every LUT addition — historical sessions get retroactive resolution without re-uploading.

The bundle is **canonical at the desktop**. Backend is the **governance layer**, not the first resolver.

---

## 2. Bundle schema v2

### 2.1 Authoritative file inventory

A v2 bundle is a directory at `<output_dir>/<YYYY-MM-DD>_<HH-MM-SS>__<sim_id>__<canonical_track_name>__<session_type>/` containing exactly the following files. Anything else is ignored at upload.

| File | Required | Format | Owner | Notes |
|---|---|---|---|---|
| `session.json` | **yes** | JSON | desktop | manifest, see §3 |
| `analysis.json` | **yes** | JSON | desktop | finalize-time computed analysis, see §4 |
| `telemetry.parquet` | **yes** | Parquet | desktop | canonical channels, see §5 |
| `laps.json` | **yes** | JSON | desktop | array of LapRecord, one per recorded lap (may be empty) |
| `events.json` | **yes** | JSON | desktop | array of SessionEvent (lifecycle markers) |
| `channels.json` | **yes** | JSON | desktop | column metadata for `telemetry.parquet` |
| `telemetry_<sim>_raw.parquet` | optional | Parquet | desktop | sim-native columns, present iff `iracing_raw_capture=true` or equivalent |
| `channels_<sim>_raw.json` | optional | JSON | desktop | metadata for raw columns; required iff raw parquet present |
| `session_info_<sim>.json` | optional | JSON | desktop | sim-native session-state snapshot (iRacing YAML, ACC/AC/LMU shm dump) |
| `raw_<sim>.<ext>.gz` | optional | bytes | desktop | full native artifact (`.ibt`, etc.), gzipped, per §6 retention policy |

**No CSV fallback in v2.** `telemetry.parquet` is required. Sessions where the desktop fails to write parquet (corrupt input, missing pyarrow) cannot be uploaded — they remain on disk only and surface in the desktop UI as "non-uploadable".

### 2.2 Required vs optional file rules

- A bundle missing any **required** file is invalid; backend returns `400 invalid_bundle` and stores nothing.
- Any **optional** file present must validate against its schema (raw parquet must have channels.json sibling, etc.). A malformed optional file invalidates the whole bundle — partial acceptance is not supported (per D7).
- The presence of optional files must be reflected in `session.json.bundle_files[]` (see §3.6). Backend cross-checks the multipart parts against the inventory; mismatch → `400 inventory_mismatch`.

### 2.3 Conflict resolution rules

When fields appear in multiple files (e.g. `session_id` in both `session.json` and `laps.json`):

1. **`session.json` wins.** Period. Other files must agree; mismatch → `400 inconsistent_bundle`.
2. **`channels.json` is authoritative for telemetry column metadata.** If a channel name appears in `telemetry.parquet` but not in `channels.json` → `400 missing_channel_metadata`.
3. **`bundle_hash` is computed by the desktop** over the canonical-file set in canonical order (see §9.5). The backend recomputes; mismatch → `400 bundle_hash_mismatch`.
4. **Native artifacts (raw_<sim>.*) never override canonical files.** They are read-only provenance.

---

## 3. session.json v2 — exact schema

### 3.1 Top-level structure

```json
{
  "schema_version": 2,
  "logger_version": "0.5.2",
  "bundle_hash": "sha256:9f8a3c...",
  "session_id": "01HZ8J3R7E6PMVTQXX2001",

  "raw_source": { /* §3.2 */ },
  "canonical_resolution": { /* §3.3 */ },
  "session": { /* §3.4 */ },
  "analysis_readiness": { /* §3.5 */ },
  "bundle_files": [ /* §3.6 */ ]
}
```

### 3.2 `raw_source` — provenance block

Records exactly what the sim API reported, before any normalization. Never modified post-finalize.

```json
"raw_source": {
  "sim_id": "iracing",
  "sim_display_name": "iRacing",
  "game_build": "2024.10.05",
  "raw_car": "ferrari296gt3",
  "raw_track": "Monza",
  "raw_track_layout": null,
  "session_type_raw": "Race",
  "driver_name_raw": "Daisy",
  "captured_at": "2026-04-15T12:00:00Z",
  "native_artifact": {
    "kind": "ibt",
    "filename": "raw_iracing.ibt.gz",
    "size_bytes": 24675824,
    "sha256": "sha256:7e2f1a..."
  }
}
```

`native_artifact` is `null` when no native sidecar is shipped (most ACC/AC/LMU sessions; iRacing sessions where bundle would exceed 200 MB).

`sim_id` must be one of `iracing`, `acc`, `assetto_corsa`, `lmu`. Anything else → backend rejects with `400 unknown_sim_id` per D8.

### 3.3 `canonical_resolution` — desktop-resolved canonical IDs

```json
"canonical_resolution": {
  "lut_version": "2026-04-15",
  "resolved_at": "2026-04-15T12:35:12Z",
  "resolver_version": "1.0.0",
  "canonical_car_id": "01HZ8J3R7E6PMVTQXX0001",
  "canonical_car_name": "Ferrari 296 GT3",
  "car_class": "GT3",
  "canonical_track_id": "01HZ8J3R7E6PMVTQXX1001",
  "canonical_track_name": "Monza",
  "canonical_track_layout": "GP",
  "session_type_canonical": "race",
  "unresolved": []
}
```

`lut_version` identifies which version of the registry LUT the desktop used. Backend uses this to decide whether to flag drift (see §7.2).

When the desktop cannot resolve a field, it uses these conventions:

- `canonical_car_id: null`, `canonical_car_name: null`, `car_class: null` → also append `"car"` to `unresolved`
- Same for track / layout
- `session_type_canonical: "race"` is the default if the raw value doesn't map; the unresolved list does **not** include session_type because the enum mapping has full coverage by design

`unresolved` is one of `["car"]`, `["track"]`, `["layout"]`, or any combination including `[]`.

### 3.4 `session` — capture-time metadata

```json
"session": {
  "session_uid": "uuid",
  "mode": "sprint",
  "driver_name": "Daisy",
  "start_time": "2026-04-15T12:00:00Z",
  "end_time": "2026-04-15T12:35:00Z",
  "duration_s": 2100.0,
  "sample_count": 21000,
  "lap_count": 14
}
```

`mode` ∈ `{sprint, endurance, coaching, data}` — the desktop's hero-workflow mode (existing concept).

`session_uid` is the desktop's internal UUID; `session_id` at the top level is the same value, lifted for ergonomics. They must match — backend validates.

### 3.5 `analysis_readiness` — fast gate for backend / webapp

```json
"analysis_readiness": {
  "ready_for_analysis": true,
  "blockers": [],
  "quality_score": 0.92,
  "completeness": 1.0,
  "min_valid_laps_met": true
}
```

`blockers` is empty iff `ready_for_analysis: true`. Possible blocker codes:

- `telemetry_corrupted` — parquet failed to read after write
- `no_complete_laps` — zero rows in `laps.json` with `valid: true`
- `sample_rate_too_low` — measured rate < 5 Hz over > 50% of session
- `gaps_excessive` — total telemetry gaps > 10 seconds
- `session_too_short` — `duration_s < 60`

Webapp uses `ready_for_analysis` to decide whether to render the analysis tab. Backend uses it for prioritization of optional re-analysis jobs.

### 3.6 `bundle_files` — file inventory + hashes

```json
"bundle_files": [
  { "name": "session.json",       "sha256": "self",                         "size_bytes": 1842, "required": true  },
  { "name": "analysis.json",      "sha256": "sha256:a1b2c3...",             "size_bytes": 4216, "required": true  },
  { "name": "telemetry.parquet",  "sha256": "sha256:9d8e7f...",             "size_bytes": 6291456, "required": true },
  { "name": "laps.json",          "sha256": "sha256:1234ab...",             "size_bytes": 783,  "required": true  },
  { "name": "events.json",        "sha256": "sha256:fedcba...",             "size_bytes": 412,  "required": true  },
  { "name": "channels.json",      "sha256": "sha256:0a0b0c...",             "size_bytes": 1024, "required": true  },
  { "name": "telemetry_iracing_raw.parquet", "sha256": "sha256:3344ee...",  "size_bytes": 4194304, "required": false },
  { "name": "channels_iracing_raw.json",     "sha256": "sha256:5566ff...",  "size_bytes": 6800,    "required": false },
  { "name": "session_info_iracing.json",     "sha256": "sha256:7788aa...",  "size_bytes": 9412,    "required": false },
  { "name": "raw_iracing.ibt.gz",            "sha256": "sha256:99aabb...",  "size_bytes": 24675824, "required": false }
]
```

Self-hash for `session.json` is the literal string `"self"` because session.json contains its own hash field. Backend computes its hash with the `bundle_files[0].sha256` field set to `"self"` for comparison.

### 3.7 Full session.json v2 example

```json
{
  "schema_version": 2,
  "logger_version": "0.5.2",
  "bundle_hash": "sha256:9f8a3c5e7b1d4a2e6f8c0b3d5a7e9f1c3b5d7e9f1a3c5e7b9d1f3a5c7e9b1d3f",
  "session_id": "01HZ8J3R7E6PMVTQXX2001",

  "raw_source": {
    "sim_id": "iracing",
    "sim_display_name": "iRacing",
    "game_build": "2024.10.05",
    "raw_car": "ferrari296gt3",
    "raw_track": "Monza",
    "raw_track_layout": null,
    "session_type_raw": "Race",
    "driver_name_raw": "Daisy",
    "captured_at": "2026-04-15T12:00:00Z",
    "native_artifact": {
      "kind": "ibt",
      "filename": "raw_iracing.ibt.gz",
      "size_bytes": 24675824,
      "sha256": "sha256:7e2f1a4c8b3d6f9a2e5b8d1c4a7f0e3b6d9a2c5f8b1e4d7a0c3f6b9e2d5a8c1f"
    }
  },

  "canonical_resolution": {
    "lut_version": "2026-04-15",
    "resolved_at": "2026-04-15T12:35:12Z",
    "resolver_version": "1.0.0",
    "canonical_car_id": "01HZ8J3R7E6PMVTQXX0001",
    "canonical_car_name": "Ferrari 296 GT3",
    "car_class": "GT3",
    "canonical_track_id": "01HZ8J3R7E6PMVTQXX1001",
    "canonical_track_name": "Monza",
    "canonical_track_layout": "GP",
    "session_type_canonical": "race",
    "unresolved": []
  },

  "session": {
    "session_uid": "01HZ8J3R7E6PMVTQXX2001",
    "mode": "sprint",
    "driver_name": "Daisy",
    "start_time": "2026-04-15T12:00:00Z",
    "end_time": "2026-04-15T12:35:00Z",
    "duration_s": 2100.0,
    "sample_count": 21000,
    "lap_count": 14
  },

  "analysis_readiness": {
    "ready_for_analysis": true,
    "blockers": [],
    "quality_score": 0.92,
    "completeness": 1.0,
    "min_valid_laps_met": true
  },

  "bundle_files": [
    { "name": "session.json",                  "sha256": "self",                                                              "size_bytes": 1842,    "required": true  },
    { "name": "analysis.json",                 "sha256": "sha256:a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2", "size_bytes": 4216,    "required": true  },
    { "name": "telemetry.parquet",             "sha256": "sha256:9d8e7f6c5b4a3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e", "size_bytes": 6291456, "required": true  },
    { "name": "laps.json",                     "sha256": "sha256:1234abcd5678ef901234abcd5678ef901234abcd5678ef901234abcd5678ef90", "size_bytes": 783,     "required": true  },
    { "name": "events.json",                   "sha256": "sha256:fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210", "size_bytes": 412,     "required": true  },
    { "name": "channels.json",                 "sha256": "sha256:0a0b0c0d0e0f0a0b0c0d0e0f0a0b0c0d0e0f0a0b0c0d0e0f0a0b0c0d0e0f0a0b", "size_bytes": 1024,    "required": true  },
    { "name": "telemetry_iracing_raw.parquet", "sha256": "sha256:3344ee5566ff77883344ee5566ff77883344ee5566ff77883344ee5566ff7788", "size_bytes": 4194304, "required": false },
    { "name": "channels_iracing_raw.json",     "sha256": "sha256:5566ff7788aabb995566ff7788aabb995566ff7788aabb995566ff7788aabb99", "size_bytes": 6800,    "required": false },
    { "name": "session_info_iracing.json",     "sha256": "sha256:7788aabb99ccdd ee7788aabb99ccddee7788aabb99ccddee7788aabb99ccddee", "size_bytes": 9412,    "required": false },
    { "name": "raw_iracing.ibt.gz",            "sha256": "sha256:99aabbccddeeff0099aabbccddeeff0099aabbccddeeff0099aabbccddeeff00", "size_bytes": 24675824, "required": false }
  ]
}
```

---

## 4. analysis.json — finalize-time analysis snapshot

### 4.1 Purpose

`analysis.json` is everything the **desktop** can compute deterministically at finalize time, given only the bundle's other files. It is the contract surface for the webapp's "analysis" tab. Anything that requires cross-session data, ML, or the backend's authoritative state lives backend-side and is **not** in `analysis.json`.

### 4.2 Schema

```json
{
  "schema_version": 1,
  "computed_at": "2026-04-15T12:35:30Z",
  "computed_by": "logger",
  "logger_version": "0.5.2",

  "session_quality": {
    "overall_score": 0.92,
    "completeness": 1.0,
    "sample_rate_hz_measured": 9.97,
    "sample_rate_hz_target": 10.0,
    "telemetry_gaps_count": 0,
    "telemetry_gaps_total_s": 0.0,
    "channels_present_count": 28,
    "channels_missing_optional": ["tyre_pressure_lf", "tyre_pressure_rf"]
  },

  "lap_summary": {
    "total_laps": 14,
    "valid_laps": 12,
    "invalid_laps": 2,
    "incomplete_laps": 0,
    "fastest_valid_lap_s": 92.345,
    "fastest_valid_lap_number": 8,
    "median_valid_lap_s": 92.789,
    "lap_time_std_dev_s": 0.412,
    "lap_consistency_pct": 88.4
  },

  "stint_summary": {
    "stint_count": 1,
    "longest_stint_laps": 14,
    "fuel_consumed_l": 32.4,
    "avg_fuel_per_lap_l": 2.31,
    "fuel_per_lap_std_l": 0.18
  },

  "input_quality": {
    "throttle_smoothness_score": 0.78,
    "brake_modulation_score": 0.82,
    "steering_smoothness_score": 0.91,
    "shift_count": 412,
    "downshift_count": 198,
    "off_throttle_total_s": 312.4,
    "trail_brake_avg_overlap_pct": 18.2
  },

  "track_position": {
    "best_sector_times_s": [29.123, 30.456, 32.766],
    "best_theoretical_lap_s": 92.345,
    "lap_with_best_theoretical": 8
  },

  "recommendation": {
    "verdict": "ready_for_review",
    "blockers": [],
    "warnings": []
  }
}
```

### 4.3 Field origins

| Field block | Computed from |
|---|---|
| `session_quality.*` | `telemetry.parquet` row count + timestamp deltas + `channels.json` |
| `lap_summary.*` | `laps.json` |
| `stint_summary.*` | `events.json` (pit_stop events) + `laps.json` (fuel deltas) |
| `input_quality.*` | `telemetry.parquet` channels: throttle_pct, brake_pct, steering_deg, gear |
| `track_position.*` | `laps.json` per-sector times |
| `recommendation.*` | aggregation of the above against thresholds |

All thresholds and scoring functions live in the desktop's existing `core/session_quality.py` and `core/consistency_analyzer.py` — **no new physics**, this spec only formalizes the JSON shape.

### 4.4 What stays backend-only (NOT in analysis.json)

- Personal best comparisons across sessions
- Rivals / leaderboards / percentile ranking
- ML-derived suggestions (handled separately via coaching envelopes — independent contract)
- Cross-session trend curves
- Setup-related diagnostics that depend on a setup database
- Telemetry gap reconstruction

Backend may compute and store additional analysis in a separate `backend_analysis_json` column on `sessions` later (out of scope for this spec). The webapp distinguishes the two by their `computed_by` field.

### 4.5 `recommendation.verdict` values

- `ready_for_review` — bundle is healthy, all checks passed
- `partial_data` — usable but missing some quality, present `warnings`
- `not_recommended` — present `blockers`; webapp shows but flags

The same verdict appears on `session.json.analysis_readiness.ready_for_analysis` (boolean projection: `true` iff verdict is `ready_for_review` or `partial_data`).

---

## 5. telemetry.parquet v2

### 5.1 Minimum canonical channels (every sim, every session)

These columns must be present, in this order, with these names and dtypes. Missing rows for a channel use Parquet null, not 0.

| Column | dtype | Units | Source | Notes |
|---|---|---|---|---|
| `timestamp_utc` | `timestamp[ms, UTC]` | — | desktop clock | non-null, monotonic |
| `session_time_s` | `double` | seconds | desktop | seconds since session start_time |
| `lap_number` | `int32` | — | sim | 0 = out lap, 1+ = recorded |
| `lap_dist_pct` | `double` | 0..1 | sim | normalized lap progress |
| `lap_distance_m` | `double` | meters | sim | derived from track length × pct |
| `speed_kph` | `double` | km/h | sim | |
| `throttle_pct` | `double` | 0..1 | sim | |
| `brake_pct` | `double` | 0..1 | sim | |
| `clutch_pct` | `double` | 0..1 | sim | nullable; many sims don't expose |
| `steering_deg` | `double` | degrees | sim | signed, + = right |
| `gear` | `int32` | — | sim | -1 = R, 0 = N, 1..N |
| `rpm` | `double` | rpm | sim | |
| `fuel_level_l` | `double` | liters | sim | absolute, not delta |
| `tyre_temp_lf` | `double` | °C | sim | nullable |
| `tyre_temp_rf` | `double` | °C | sim | nullable |
| `tyre_temp_lr` | `double` | °C | sim | nullable |
| `tyre_temp_rr` | `double` | °C | sim | nullable |
| `track_temp_c` | `double` | °C | sim | nullable |
| `air_temp_c` | `double` | °C | sim | nullable |
| `pos_x_m` | `double` | meters | sim | track-local; nullable |
| `pos_y_m` | `double` | meters | sim | nullable |
| `pos_z_m` | `double` | meters | sim | nullable |
| `is_in_pits` | `boolean` | — | sim | |
| `is_on_track` | `boolean` | — | sim | |

Order is fixed so that older bundle readers can position-index without consulting `channels.json`.

### 5.2 iRacing-only enrichments (canonical channels remain — these are added)

When `raw_source.sim_id == "iracing"` and `raw_iracing` capture was enabled, additional canonical (i.e. exposed in `telemetry.parquet`, not the raw sidecar) columns may be present:

| Column | dtype | Units | Notes |
|---|---|---|---|
| `pedal_force_brake_n` | `double` | newtons | from IRSDK pedal-force vars when available |
| `gear_indicator_pct` | `double` | 0..1 | shift-indicator light pct |
| `dc_drs_active` | `boolean` | — | DRS state |
| `dc_p2p_remaining` | `int32` | count | push-to-pass, when applicable |

These are **promoted** from `telemetry_iracing_raw.parquet` when present. They are still iRacing-only; ACC/AC/LMU bundles never have them.

### 5.3 Channel provenance strategy

`channels.json` carries one entry per column in `telemetry.parquet`:

```json
{
  "schema_version": 2,
  "telemetry_schema_version": "2.0.0",
  "channels": [
    {
      "name": "speed_kph",
      "dtype": "double",
      "units": "km/h",
      "origin": "canonical",
      "source": "sim_native",
      "missing_allowed": false,
      "description": "Vehicle speed over ground"
    },
    {
      "name": "pedal_force_brake_n",
      "dtype": "double",
      "units": "N",
      "origin": "iracing_only",
      "source": "irsdk:BrakeForce",
      "missing_allowed": true,
      "description": "Brake pedal force; promoted from IRSDK raw"
    }
  ]
}
```

`origin` ∈ `{canonical, iracing_only, lmu_only, acc_only, ac_only}`. Webapp filters channels by origin to know which charts to render per sim.

### 5.4 Compression and encoding

- Snappy compression (smaller install footprint than zstd; pyarrow default)
- Row-group size: 10000 rows (≈1000 seconds at 10 Hz)
- Column statistics enabled
- No dictionary encoding for `timestamp_utc` (high cardinality)

These are PyArrow defaults except row-group size — explicit so multi-MB files chunk predictably.

---

## 6. Native artifact retention policy

### 6.1 What counts as a native artifact

| Sim | Native file | Typical size |
|---|---|---|
| iRacing | `.ibt` | 5-100 MB per session |
| LMU | shm dump or motec export | n/a — no widely-used persistent format |
| ACC | shm dump | n/a — no native export |
| Assetto Corsa | shm dump or motec export | n/a — no native export |

In practice **only iRacing has a persistent native artifact** (`.ibt`) worth preserving as provenance. The other three sims have no native file the desktop can capture.

### 6.2 When to include `.ibt` in the bundle

**Default: include**, gzipped to `raw_iracing.ibt.gz`, **iff total bundle size remains under 200 MB** (D4 cap).

Decision tree at finalize time:

```
if sim_id != "iracing":            skip native artifact (none exists)
elif user_disabled_raw_capture:    skip
elif estimated_total > 200 MB:     hash + reference only (see §6.3)
elif estimated_total <= 200 MB:    include compressed
```

### 6.3 Hash + reference (when native exceeds size budget)

When the .ibt would push the bundle over 200 MB:

- The .ibt is **not** included as a multipart part.
- `session.json.raw_source.native_artifact` still records `kind`, `filename`, `size_bytes`, `sha256`.
- Add a sibling field `local_path_hint` so the desktop can find it again later for re-upload:

```json
"native_artifact": {
  "kind": "ibt",
  "filename": "raw_iracing.ibt",
  "size_bytes": 187654321,
  "sha256": "sha256:...",
  "in_bundle": false,
  "local_path_hint": "C:\\Users\\Daisy\\Documents\\iRacing\\telemetry\\..."
}
```

Backend stores the metadata only. Webapp shows "native artifact available locally — request upload" UI affordance (out of scope for this spec; deferred).

### 6.4 MinIO storage of native artifacts

When included, `raw_iracing.ibt.gz` is stored at:

```
bundles/<user_uuid>/<session_id>/raw_iracing.ibt.gz
```

Same TTL and signed-URL policy as canonical files (D6 — 1-hour signed URLs only).

Backend never decompresses or parses the .ibt. It's stored verbatim for forensics and any future analysis tool the user wants to run client-side.

### 6.5 Sync implications

- `bundle_hash` (§9.5) is computed over the **canonical file set only** — not the native artifact. So the same session uploaded once with .ibt and once without has the same `bundle_hash`. This is intentional: the canonical analysis is the contract; native is supplementary.
- The native artifact's `sha256` is recorded in `session.json` so backend can detect if a re-upload changes the .ibt content (theoretically impossible — sims don't rewrite captured files — but caught for completeness).

---

## 7. Canonical resolver integration

### 7.1 Desktop finalize-time resolution flow

```
session ends
  ↓
finalizer collects raw_source fields
  ↓
load LUT: src/lap_coach_logger/normalization/lut/canonical_cars.json
                                            /canonical_tracks.json
  ↓
[optional, best-effort] GET /v1/registry/snapshot?since=<bundled_lut_version>
   if newer LUT available, merge into in-memory copy for this session only
   if backend unreachable, fall back to bundled LUT silently
  ↓
resolve(sim_id, raw_car) → canonical_car_id, canonical_car_name, car_class
resolve(sim_id, raw_track, raw_layout) → canonical_track_id, canonical_track_name, canonical_layout
  ↓
on miss: append to canonical_resolution.unresolved[]
         leave canonical_*_id = null
         leave car_class = null
  ↓
write session.json with canonical_resolution block
write rest of bundle
write bundle_hash (computed over canonical file set in canonical order)
  ↓
atomic rename _tmp_<sess> → final
```

The desktop runs offline-clean. Bundles produced offline are valid against the LUT version the desktop shipped with.

### 7.2 Backend validation flow (NOT first-resolution)

When `POST /v1/bundles` arrives:

```
parse session.json
  ↓
extract submitted: canonical_car_id, canonical_track_id, car_class
extract raw: sim_id, raw_car, raw_track, raw_track_layout
  ↓
look up backend's authoritative resolution for the same raw fields
   → backend_canonical_car_id, backend_canonical_track_id, backend_car_class
  ↓
case A: submitted matches backend → store as-is, drift = false
case B: submitted differs from backend → store SUBMITTED ids on the session,
                                          set sessions.canonical_drift_flags = ["car"|"track"|"class"|...],
                                          insert one row per drift into canonical_drifts table for curator review
case C: submitted is null AND backend can resolve → store as-is (NULL),
                                                    insert into unresolved_canonicals for curator,
                                                    do NOT auto-fill from backend
case D: both null → store as-is (NULL), insert into unresolved_canonicals
  ↓
proceed with bundle storage + row inserts
```

**Backend never overwrites the desktop's resolution.** The bundle is canonical; the backend is governance. Drift is surfaced, never silently fixed. This preserves the property that two bundle copies in two locations describe the session identically.

### 7.3 `canonical_drifts` table

```sql
CREATE TABLE canonical_drifts (
    id              BIGSERIAL PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    field           TEXT NOT NULL,                  -- "canonical_car_id" | "canonical_track_id" | "car_class" | "canonical_track_layout"
    submitted_value TEXT,                           -- what desktop sent
    backend_value   TEXT,                           -- what backend resolved
    sim_id          TEXT NOT NULL,
    raw_value       TEXT NOT NULL,                  -- the raw_car or raw_track that disagreed
    desktop_lut_version TEXT,                       -- from session.json.canonical_resolution.lut_version
    backend_lut_version TEXT,                       -- backend's current LUT version
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Curator-facing endpoint `GET /v1/admin/drifts` lists all rows. After the curator decides which side is correct:

- If desktop wins (LUT was added on desktop first), backend's LUT gets updated; backfill re-resolves accordingly.
- If backend wins, the **session's stored canonical_id is updated** via a backfill job (sessions are mutable for this specific concern), the desktop LUT update ships in the next release.

Sessions touched by curator-driven backfills get a `last_canonicalized_at` timestamp on the session row.

### 7.4 Unresolved mapping representation

```sql
CREATE TABLE unresolved_canonicals (
    id              BIGSERIAL PRIMARY KEY,
    sim_id          TEXT NOT NULL,
    raw_car         TEXT,
    raw_track       TEXT,
    raw_track_layout TEXT,
    occurrence_count INTEGER NOT NULL DEFAULT 1,    -- aggregated across sessions
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (sim_id, raw_car, raw_track, raw_track_layout)
);
```

Per upload with `unresolved` non-empty: backend upserts into this table, incrementing `occurrence_count`. Curator dashboard sorts by `occurrence_count DESC` so the most impactful gaps surface first.

### 7.5 LUT distribution

- **Source of truth:** `backend/seed/canonical_cars.json` and `canonical_tracks.json` in the backend repo.
- **Desktop snapshot:** at desktop release time, a build step copies the seed files into `src/lap_coach_logger/normalization/lut/` and writes a `lut_version` file derived from the file SHA + ISO date.
- **Backend snapshot endpoint:** `GET /v1/registry/snapshot?since=<lut_version>` returns the current LUT (or `304 Not Modified` if no change). Desktop calls this best-effort at finalize time; failure is silent.
- **Versioning scheme:** `lut_version` is `YYYY-MM-DD.<short-sha>` derived from the seed file's hash. Monotonic via date prefix. Curator-driven LUT changes increment the version.

### 7.6 Resolver code surface

**Desktop (this repo):**

```python
# src/lap_coach_logger/normalization/resolver.py
class CanonicalResolver:
    def __init__(self, lut_dir: Path) -> None: ...
    def resolve_car(self, sim_id: str, raw_car: str) -> ResolvedCar | None: ...
    def resolve_track(self, sim_id: str, raw_track: str, raw_layout: str | None) -> ResolvedTrack | None: ...
    @property
    def lut_version(self) -> str: ...
```

**Backend (sibling repo or `backend/`):**

```python
# backend/app/resolver.py
class BackendResolver:
    """Used only for VALIDATION of submitted canonical IDs and for backfill — not first resolution."""
    async def resolve_car(self, db, sim_id: str, raw_car: str) -> ResolvedCar | None: ...
    async def resolve_track(self, db, sim_id: str, raw_track: str, raw_layout: str | None) -> ResolvedTrack | None: ...
    async def detect_drift(self, db, sim_id: str, raw_car: str, raw_track: str,
                           raw_layout: str | None, submitted_canonical_car_id: UUID | None,
                           submitted_canonical_track_id: UUID | None,
                           submitted_car_class: str | None) -> list[Drift]: ...
```

---

## 8. Multi-sim compatibility

### 8.1 Tier definitions

| Tier | Sims | What's required | What may be missing |
|---|---|---|---|
| **Tier 1: First-class** | iRacing | All canonical channels + iRacing enrichments + native .ibt + session_info | n/a |
| **Tier 2: Full** | LMU | All canonical channels + session_info | native artifact (no usable export); `pedal_force_brake_n` etc. |
| **Tier 3: Limited** | ACC, AC | All canonical channels | track_layout (ACC; AC has it), driver_name, native artifact, sim-specific enrichments |

A bundle's tier is **not** explicitly recorded — it's derivable from `raw_source.sim_id`. Tier governs:

- **Webapp UI**: which charts are shown
- **Quality threshold**: tier-3 sessions default to a more permissive `min_valid_laps` threshold
- **`session_info_<sim>.json` requirement**: optional for all tiers, but webapp displays its absence as a quality warning for tier-1

### 8.2 Per-sim canonical mapping coverage targets

Initial seed (Phase 1):
- iRacing: top 50 cars (by community usage), 30 tracks. All cars have `car_class`.
- LMU, ACC, AC: top 20 cars, 15 tracks each. `car_class` populated where available from sim metadata or curator entry.

Coverage rule: **a car/track that appears in a real upload but isn't in the LUT enters `unresolved_canonicals`**. Curator backfills as the table grows.

### 8.3 Behavior when sim_id is unsupported

Per D8: backend returns `400 unknown_sim_id`. The desktop should **never** generate a bundle with an unknown sim_id — sim adapters are the only source and they hardcode the four supported values. If the backend sees an unknown sim_id, it's a desktop bug or tampering.

---

## 9. Backend ingest contract

### 9.1 Endpoint

```
POST /v1/bundles
```

Headers (all required unless noted):

| Header | Value | Notes |
|---|---|---|
| `Authorization` | `Bearer <device_token>` | per existing auth (§9.3 of master spec) |
| `Idempotency-Key` | `<bundle_hash>` from session.json (UUID-cast) | dedup key |
| `Content-Length` | bytes | required for 200 MB pre-flight; absence → 411 Length Required |
| `Content-Type` | `multipart/form-data; boundary=...` | standard |

Body: `multipart/form-data` with one part per file in `bundle_files`. Part name == file name. Required parts must be present. Optional parts present in `bundle_files` must be present in the multipart body — mismatch → `400 inventory_mismatch`.

### 9.2 200 MB enforcement

**Client-side pre-flight:**

```
total = sum(f.size_bytes for f in bundle_files)
if total > 200 * 1024 * 1024:
    drop optional native_artifact
    if total still > 200 MB:
        refuse upload, surface UI error, do NOT call POST
```

**Server-side enforcement (defence in depth):**

1. If `Content-Length > 200*1024*1024` → return `413 Payload Too Large` immediately, do not buffer the body.
2. If `Content-Length` missing → return `411 Length Required`.
3. While reading multipart, enforce a hard cap of `200*1024*1024 + 1 MB slack`. Exceeding mid-stream → close connection, return `413`.
4. Also enforce per-part caps: `telemetry.parquet ≤ 100 MB`, `raw_iracing.ibt.gz ≤ 150 MB`, others ≤ 1 MB. Per-part cap exceeded → `413` with `field` = part name.

### 9.3 Validation sequence (executes in this order; first failure stops)

```
1. auth: Authorization header → device → user             [401 auth_failed]
2. idempotency: Idempotency-Key present + UUID-shaped     [400 missing_envelope_id]
3. content_length: present + ≤ 200 MB                     [411 length_required | 413 bundle_too_large]
4. content_type: multipart/form-data                      [415 unsupported_media_type]
5. parse multipart                                        [400 malformed_multipart]
6. extract session.json part                              [400 missing_required_file: "session.json"]
7. parse session.json                                     [400 invalid_schema: parse error]
8. validate session.json against v2 schema                [400 invalid_schema: field=...]
9. session.json.schema_version == 2                       [400 unsupported_schema_version]
10. session.json.raw_source.sim_id ∈ known sims           [400 unknown_sim_id]
11. session.json.bundle_hash matches Idempotency-Key      [400 bundle_hash_mismatch]
12. multipart parts == bundle_files inventory             [400 inventory_mismatch]
13. each part's sha256 matches inventory entry            [400 file_hash_mismatch: file=...]
14. recompute bundle_hash from canonical files in canonical order, == submitted [400 bundle_hash_mismatch]
15. dedup check: sync_envelopes.envelope_id == bundle_hash AND user_id == current
       → if exists: return 200 already_seen=true (skip remaining steps)
16. dedup check: sync_envelopes.envelope_id == bundle_hash AND user_id != current
       → return 409 bundle_owned_by_other_user
17. resolver validation: backend_resolve(raw_*) vs submitted canonical_* → record drifts
18. begin transaction
19.   upsert sessions row
20.   bulk insert laps from laps.json
21.   bulk insert coaching_outputs (if analysis.json contains any — for v1 it doesn't)
22.   bulk insert session_events from events.json
23.   write each file to MinIO at bundles/<user_uuid>/<session_id>/<filename>
24.   insert sync_envelopes audit row (envelope_id = bundle_hash, payload_type = "bundle")
25.   insert canonical_drifts rows (if any)
26.   insert unresolved_canonicals upserts (if any)
27. commit
28. return 200 {ok: true, bundle_id: <bundle_hash>, session_id, already_seen: false, drifts: [...]}
```

### 9.4 Error responses (full table)

| Code | HTTP | Body shape |
|---|---|---|
| `auth_failed` | 401 | `{ok:false, code:"auth_failed", message:"invalid or missing device token"}` |
| `missing_envelope_id` | 400 | `{ok:false, code:"missing_envelope_id", message:"Idempotency-Key must be a UUID matching session.json.bundle_hash"}` |
| `length_required` | 411 | `{ok:false, code:"length_required", message:"Content-Length required"}` |
| `bundle_too_large` | 413 | `{ok:false, code:"bundle_too_large", message:"bundle exceeds 200 MB cap (got: <bytes>)", field?: "<part_name>"}` |
| `unsupported_media_type` | 415 | `{ok:false, code:"unsupported_media_type", message:"Content-Type must be multipart/form-data"}` |
| `malformed_multipart` | 400 | `{ok:false, code:"malformed_multipart", message:"<parser error>"}` |
| `missing_required_file` | 400 | `{ok:false, code:"missing_required_file", message:"required file missing", field:"<filename>"}` |
| `invalid_schema` | 400 | `{ok:false, code:"invalid_schema", message:"<pydantic error>", field:"<dotted path>"}` |
| `unsupported_schema_version` | 400 | `{ok:false, code:"unsupported_schema_version", message:"only schema_version 2 supported, got <n>"}` |
| `unknown_sim_id` | 400 | `{ok:false, code:"unknown_sim_id", message:"sim_id <x> is not supported", field:"raw_source.sim_id"}` |
| `bundle_hash_mismatch` | 400 | `{ok:false, code:"bundle_hash_mismatch", message:"Idempotency-Key does not match bundle_hash"}` or computed-hash mismatch |
| `inventory_mismatch` | 400 | `{ok:false, code:"inventory_mismatch", message:"multipart parts do not match bundle_files inventory", field:"<missing/extra part>"}` |
| `file_hash_mismatch` | 400 | `{ok:false, code:"file_hash_mismatch", message:"file content does not match declared sha256", field:"<filename>"}` |
| `bundle_owned_by_other_user` | 409 | `{ok:false, code:"bundle_owned_by_other_user", message:"bundle_hash already accepted under a different user account"}` |
| `inconsistent_bundle` | 400 | `{ok:false, code:"inconsistent_bundle", message:"<which fields disagree>", field:"<dotted path>"}` |
| `server_error` | 500 | `{ok:false, code:"server_error", message:"transient error, retry"}` |

### 9.5 `bundle_hash` semantics

**Definition:** SHA-256 over the concatenation of (per file, sorted by `name` ASCII):
- `name` (UTF-8 bytes)
- `\x00` separator
- `sha256` (raw 32 bytes, not hex)
- `\x00` separator

…iterating over `bundle_files` where `required == true` only. **Optional files (raw native, sim sidecars) are EXCLUDED** so the same session uploaded with and without .ibt has the same `bundle_hash`.

`session.json`'s own sha256 is computed with the `bundle_files[0].sha256` field set to the literal string `"self"`. After computation, the field is replaced with the actual hex sha256 of the `session.json` bytes; **this is a non-circular convention**, the receiving side flips it back to `"self"` to verify.

Result: a 64-char hex string, prefixed `sha256:`. Cast to UUID by taking the first 32 hex chars and formatting as `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` for use as `Idempotency-Key` and as `sync_envelopes.envelope_id`.

### 9.6 Replay semantics

Per D10: same `bundle_hash` from a different `device_token` on the **same user** → accept as replay (return `already_seen: true`). Different user → 409.

Implementation: query `sync_envelopes` by `envelope_id`. If exists and `user_id == current_user.id` → already_seen. If exists and different user → 409. If not exists → proceed.

Subsequent uploads with the same `bundle_hash` from the same user but with a different `bundle_files` inventory (e.g. first upload had no .ibt, second includes .ibt) are still treated as `already_seen: true` — **the canonical content is the same**. The optional native artifact from the second upload is **discarded** to keep MinIO storage idempotent. (Future enhancement: accept native upgrades; out of scope for v1.)

### 9.7 Object storage layout in MinIO

```
bundles/<user_uuid>/<session_id>/
├── session.json
├── analysis.json
├── telemetry.parquet
├── laps.json
├── events.json
├── channels.json
├── telemetry_iracing_raw.parquet      (iff present in bundle)
├── channels_iracing_raw.json          (iff present)
├── session_info_iracing.json          (iff present)
└── raw_iracing.ibt.gz                 (iff present)
```

Bucket: `lap-coach-bundles` (single bucket; per-user prefix gives logical isolation).

Bucket policy: private. All access via backend-issued pre-signed URLs (D6 — 1-hour TTL).

Lifecycle: no automatic expiry in v1. Storage cost is dominated by parquet (5-10 MB/session). 1000 sessions ≈ 10 GB ≈ <$1/month at S3 prices.

### 9.8 Signed download rules

```
GET /v1/sessions/{session_id}/files/{filename}
```

- Auth: requires `lc_session` cookie (webapp user) OR `Authorization: Bearer <device_token>` (desktop re-fetch).
- Authorization: row's `user_id` must match authenticated user.
- `filename` must be one of the file names in the session's `bundle_files`. Requesting any other name → `404`.
- Response: `302 Found` with `Location: <minio-presigned-url>`. URL valid for **1 hour**.
- Pre-signed URLs are not cacheable; webapp fetches a fresh URL per download.

`telemetry.parquet` and `raw_iracing.ibt.gz` are the only two files webapp typically signs URLs for. JSON files are small; backend serves their content inline via separate read endpoints.

### 9.9 Required files in a valid v2 bundle (canonical list)

```
session.json           (required, JSON)
analysis.json          (required, JSON)
telemetry.parquet      (required, Parquet)
laps.json              (required, JSON)
events.json            (required, JSON)
channels.json          (required, JSON)
```

Optional, only validated if listed in `bundle_files`:

```
telemetry_<sim>_raw.parquet
channels_<sim>_raw.json
session_info_<sim>.json
raw_<sim>.<native_ext>.gz
```

`<sim>` must equal `raw_source.sim_id`. Sidecars for a different sim (e.g. `telemetry_acc_raw.parquet` in a bundle with `sim_id == "iracing"`) → `400 inconsistent_bundle`.

---

## 10. Migration plan

### 10.1 Phasing

| Phase | What ships | Who |
|---|---|---|
| **0** | This spec, frozen | architect |
| **1** | Backend: migrations 0002 (registry tables) + 0003 (sessions extensions) + 0004 (canonical_drifts, unresolved_canonicals). Seed iRacing top-50 cars + 30 tracks. `GET /v1/registry/snapshot`. | backend |
| **2** | Backend: `POST /v1/bundles` endpoint, MinIO sidecar, signed download endpoint, validation + drift detection | backend |
| **3** | Desktop: `normalization/lut/`, `CanonicalResolver`, `writers/bundle_v2.py`, dual-write (v1 + v2 simultaneously), `BundleUploader` | desktop |
| **4** | Backend: backfill script for historical sessions | backend |
| **5** | Webapp: regen types from updated OpenAPI, render canonical fields + analysis_json | webapp (external) |
| **6** | Desktop: drop v1 bundle write path, ship v2 only | desktop |

Phases 1-2 are backend-only, can ship before any desktop change. Phase 3 starts when the backend endpoint is live in staging. Phases 4-5 run in parallel.

### 10.2 Idempotent backfill on LUT updates

```
backend/scripts/backfill_resolver.py
```

Runs after every LUT update (manual trigger; later wrapped in CI on `seed/*.json` change):

```
1. Load updated LUT into cars/car_aliases/tracks/track_aliases (idempotent upsert via import_canonicals.py)
2. Find all sessions where:
     (canonical_car_id IS NULL AND raw_source allows resolution)
     OR (canonical_drift_flags contains 'car' AND backend_resolve agrees with desktop now)
3. For each, re-resolve and update sessions row
     - clear canonical_drift_flags entry if drift resolved
     - decrement / delete unresolved_canonicals row
4. Log summary: <n> sessions resolved, <n> drifts cleared
```

Idempotent: running twice produces the same DB state. Cheap: bounded by `unresolved_canonicals` and `canonical_drifts` table size, both small.

### 10.3 What does not migrate

- Existing v1 bundles already on disk are **not** auto-converted to v2. The desktop UI shows them as "legacy — re-record to upload" if the user tries to upload them after Phase 6.
- v1 envelope sync queue items already in `.sync_queue.json` continue to drain via the existing path (Phase 6 is a desktop-only deprecation; the envelope endpoints stay live indefinitely).

---

## 11. Implementation plan

### 11.1 Backend modules + files

```
backend/
├── alembic/versions/
│   ├── 0002_canonical_registry.py       (sims, cars, car_aliases, tracks, track_aliases)
│   ├── 0003_sessions_extensions.py      (canonical_*, car_class, analysis_json, telemetry_path, raw_telemetry_path, bundle_hash, canonical_drift_flags, last_canonicalized_at)
│   └── 0004_drift_tracking.py           (canonical_drifts, unresolved_canonicals)
├── app/
│   ├── resolver.py                      (NEW — backend validator)
│   ├── storage.py                       (NEW — MinIO wrapper)
│   ├── bundle_validator.py              (NEW — session.json v2 schema, file inventory checks, hash recomputation)
│   ├── routers/
│   │   ├── bundles.py                   (NEW — POST /v1/bundles, GET /v1/sessions/{id}/files/{name})
│   │   ├── registry.py                  (NEW — GET /v1/registry/snapshot)
│   │   ├── admin.py                     (NEW — GET /v1/admin/drifts, /unresolved)
│   │   ├── ingest.py                    (existing — moved to /v1 prefix)
│   │   ├── auth_routes.py               (existing — moved to /v1)
│   │   └── read.py                      (existing — moved to /v1, extended with canonical fields + telemetry_url)
│   └── schemas.py                       (extended with BundleManifestV2, AnalysisJson, etc.)
├── seed/
│   ├── canonical_cars.json              (NEW — iRacing top-50 + tier-2/3 minimums)
│   ├── canonical_tracks.json            (NEW)
│   └── README.md                        (curator instructions)
├── scripts/
│   ├── import_canonicals.py             (NEW — upsert seed → DB)
│   └── backfill_resolver.py             (NEW — re-resolve unresolved + drift sessions)
├── docker-compose.yml                   (extended with minio sidecar)
└── tests/
    ├── test_resolver.py                 (NEW)
    ├── test_bundle_validator.py         (NEW)
    ├── test_bundles_endpoint.py         (NEW — covers all error cases from §9.4)
    └── test_backfill.py                 (NEW)
```

### 11.2 Desktop modules + files

```
src/lap_coach_logger/
├── normalization/
│   ├── lut/
│   │   ├── canonical_cars.json          (NEW — copied from backend/seed at build time)
│   │   ├── canonical_tracks.json        (NEW)
│   │   └── lut_version.txt              (NEW — auto-generated at build, e.g. "2026-04-15.a1b2c3d")
│   ├── resolver.py                      (NEW — CanonicalResolver class)
│   └── lut_loader.py                    (NEW — loads LUT from package data, offers in-memory merge with backend snapshot)
├── writers/
│   ├── bundle_v2.py                     (NEW — writes session.json v2, analysis.json, computes bundle_hash)
│   ├── analysis_writer.py               (NEW — populates analysis.json from existing session_quality + lap data)
│   ├── finalizer.py                     (modified — orchestrates v1+v2 dual-write during phases 3-5, then v2-only)
│   └── channels.py                      (modified — adds origin field per §5.3)
├── sync/
│   ├── bundle_uploader.py               (NEW — multipart POST /v1/bundles, pre-flight 200 MB check, drop native if needed)
│   ├── bundle_failures.py               (NEW — persistent store for bundles that failed upload)
│   ├── client.py                        (existing — unchanged for v1 envelope path)
│   └── http_transport.py                (existing — reused by bundle_uploader)
├── config/models.py                     (modified — AppConfig.sync.bundle_upload_enabled, bundle_max_size_mb, bundle_upload_after_finalize)
└── core/session_quality.py              (existing — extended to emit AnalysisJson struct, no new physics)

scripts/
├── sync_lut_from_backend.py             (NEW — build-time copy backend/seed → src/.../normalization/lut/)
└── build_rc1.bat                        (existing — extended to invoke sync_lut_from_backend.py)
```

### 11.3 Tests to add

**Backend:**

1. `test_resolver.py::test_resolve_known_car` — happy path
2. `test_resolver.py::test_resolve_unknown_returns_none`
3. `test_resolver.py::test_layout_disambiguation` — Bathurst variants
4. `test_bundle_validator.py::test_v2_schema_accepts_minimal_valid_bundle`
5. `test_bundle_validator.py::test_rejects_missing_required_file`
6. `test_bundle_validator.py::test_rejects_hash_mismatch`
7. `test_bundle_validator.py::test_rejects_inconsistent_session_id`
8. `test_bundles_endpoint.py::test_happy_path_iracing_with_native`
9. `test_bundles_endpoint.py::test_happy_path_acc_no_native`
10. `test_bundles_endpoint.py::test_replay_returns_already_seen`
11. `test_bundles_endpoint.py::test_oversize_returns_413_pre_body`
12. `test_bundles_endpoint.py::test_unknown_sim_id_returns_400`
13. `test_bundles_endpoint.py::test_invalid_schema_returns_400_with_field`
14. `test_bundles_endpoint.py::test_inventory_mismatch_returns_400`
15. `test_bundles_endpoint.py::test_file_hash_mismatch_returns_400`
16. `test_bundles_endpoint.py::test_bundle_hash_mismatch_returns_400`
17. `test_bundles_endpoint.py::test_replay_different_user_returns_409`
18. `test_bundles_endpoint.py::test_drift_recorded_when_canonical_disagrees`
19. `test_bundles_endpoint.py::test_unresolved_recorded_when_desktop_left_null`
20. `test_bundles_endpoint.py::test_signed_download_url_works`
21. `test_bundles_endpoint.py::test_signed_download_url_denies_other_user`
22. `test_backfill.py::test_resolves_previously_unresolved_after_lut_update`
23. `test_backfill.py::test_clears_drift_when_backend_now_agrees`
24. `test_backfill.py::test_idempotent_second_run_no_changes`

**Desktop:**

1. `test_resolver.py::test_resolve_iracing_ferrari_296`
2. `test_resolver.py::test_resolve_acc_same_car_same_canonical_id`
3. `test_resolver.py::test_unknown_returns_none_and_logs`
4. `test_bundle_v2_writer.py::test_writes_all_required_files`
5. `test_bundle_v2_writer.py::test_bundle_hash_deterministic_excluding_optionals`
6. `test_bundle_v2_writer.py::test_session_json_validates_against_schema`
7. `test_analysis_writer.py::test_populates_lap_summary_from_laps_json`
8. `test_analysis_writer.py::test_blockers_when_no_valid_laps`
9. `test_bundle_uploader.py::test_drops_native_when_over_200mb`
10. `test_bundle_uploader.py::test_refuses_pre_flight_when_canonical_files_alone_over_200mb`
11. `test_bundle_uploader.py::test_persists_failure_to_bundle_failures_on_5xx`
12. `test_bundle_uploader.py::test_replay_response_marks_as_synced_locally`

### 11.4 Rollout order

```
Day 1-2:  Backend phase 1 (migrations + seed + registry endpoint)
Day 3-4:  Backend phase 2 (POST /v1/bundles + MinIO + validation + drift detection)
Day 5:    Backend code-review + integration test sweep
Day 6-8:  Desktop phase 3 (resolver + bundle_v2 writer + uploader, dual-write)
Day 9:    Desktop code-review + e2e test (fake backend)
Day 10:   Backend phase 4 (backfill script, cron-able)
Day 11:   Webapp phase 5 (external — types regen, UI extension)
Day 12:   Staging end-to-end test: capture iRacing → bundle uploaded → visible in webapp with canonical Ferrari 296 GT3 / Monza badges
Day 13:   Desktop phase 6 (drop v1 dual-write, v2-only)
Day 14:   Production cutover
```

Each phase has a hard checkpoint: backend phases ship behind feature flags (`/v1/bundles` returns 404 until enabled). Desktop phase 3 dual-writes — old v1 path keeps working until phase 6.

---

## 12. Constraints recap (anti-bloat)

- No new physics. `analysis.json` derives from existing `core/session_quality.py` and `core/consistency_analyzer.py` outputs only.
- No per-user canonical aliasing (D9). Global registry, period.
- No partial bundle uploads (D7). Whole bundle re-upload only.
- No backend overwrite of desktop's canonical resolution. Drift surfaced, not silently fixed (D5).
- No CSV fallback for telemetry. Parquet required.
- No automatic `.ibt` parsing on the backend. Native artifacts are stored verbatim and never decoded server-side.
- No cross-sim leaderboards / rivals / ML in `analysis.json` (those are separate features, separate contracts).
- No new auth model. Bearer device token + JWT cookie session, unchanged.

---

## 13. Open follow-ups (NOT in this spec; tracked for next sub-spec)

- Curator UI for `unresolved_canonicals` and `canonical_drifts` review (manual SQL is acceptable for v1).
- Backend-side enrichment / re-analysis (`backend_analysis_json`) — separate spec when needed.
- Bundle re-upload UI to add native `.ibt` to a previously-uploaded bundle (currently discarded — see §9.6).
- Streaming bundle delta sync for very long endurance sessions.
- Multi-driver session support (current model assumes one driver per session row).

---

## 14. Glossary

- **Bundle** — the directory of files described in §2; the canonical analysis-ready artifact.
- **Bundle hash** — SHA-256 over canonical-only files in canonical order; identifies one logical session.
- **Canonical ID** — UUID identifying one real-world car or track regardless of which sim observed it.
- **Drift** — submitted canonical ID differs from backend-resolved canonical ID for the same raw inputs.
- **LUT** — look-up table; the JSON files mapping `(sim_id, raw_id) → canonical_id`.
- **Native artifact** — the sim's own file format (.ibt for iRacing); provenance only.
- **Provenance** — supporting evidence preserved alongside the canonical record. Read-only at the backend.
- **Resolver** — code that maps raw → canonical. Lives on both desktop (first resolution) and backend (validation + backfill).
- **Tier** — multi-sim support level: 1 = iRacing first-class, 2 = LMU full, 3 = ACC/AC limited.
