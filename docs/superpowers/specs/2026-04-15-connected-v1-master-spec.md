# Connected v1 — Master Spec

> **Status:** Draft. Master document — smaller specs (resolver, bundle upload, DB migration, desktop changes, webapp contract) will be derived from this.
> **Date:** 2026-04-15
> **Scope:** Cross-repo design doc spanning desktop (this repo), backend (FastAPI, sibling repo or `backend/` subdir), and webapp (external repo).

---

## 0. TL;DR

The desktop already produces a rich, well-structured session bundle on disk; the current sync stack ignores most of it and ships only minimal in-memory envelopes. Connected v1 closes that gap by:

1. Promoting the existing `session.json` manifest to be the canonical upload payload.
2. Adding a thin resolver that converts sim-native car/track strings into stable canonical IDs at the adapter boundary.
3. Extending the backend with `cars`, `tracks`, and `sims` registry tables plus four new `sessions` columns.
4. Adding a `POST /bundles` endpoint that accepts the full session directory.
5. Defining the OpenAPI contract as the single source of truth between repos.

Success: a session captured in iRacing and a session captured in ACC both surface in the webapp under the same canonical "Ferrari 296 GT3 / Monza" badge, with the GT3 class label populated.

---

## 1. Background

### 1.1 What exists today

**Desktop (this repo, Python 3.12 / PySide6)**

Captures sessions from iRacing, ACC, Assetto Corsa, Le Mans Ultimate. Per session writes a self-contained bundle to `<output_dir>/<YYYY-MM-DD>_<HH-MM-SS>__<sim>__<track>__<session_type>/`:

- `session.json` — single source of truth manifest (`writers/finalizer.py:267-321`)
- `metadata.json` — back-compat shim
- `telemetry.parquet` — columnar samples (~10 Hz)
- `laps.json`, `events.json`, `channels.json`, `quality_report.json`
- iRacing-only: `telemetry_iracing_raw.csv`, `iracing_catalogs.json`, `session_info_iracing.json`
- Other sims: `telemetry_<sim>_raw.csv`, `session_info_<sim>.json`

In parallel, an in-memory **envelope sync queue** (`sync/queue.py`) ships minimal `SessionPayload` / `LapPayload` / `CoachingPayload` / `EventPayload` objects to five typed endpoints (`/sessions-start`, `/sessions-end`, `/laps-batch`, `/coaching-batch`, `/events-batch`). This path is well-tested and idempotent but **carries far less context than the on-disk bundle**.

**Backend (FastAPI + Postgres, sibling repo or `backend/` here)**

Already exists with the five envelope endpoints, two read endpoints (`GET /sessions`, `GET /sessions/{id}`), webapp auth (`POST /auth/login`), seven business tables, and Argon2 + JWT cookie auth.

**Webapp (external repo, already built)**

Lives in a separate repo. Reads sessions via the backend's REST API. We do not modify webapp code from here — instead we publish a contract.

### 1.2 What's missing

| Gap | Severity | Notes |
|---|---|---|
| No canonical car/track IDs | **Blocking** for the cross-sim story | Each sim's raw strings (`porsche_911_gt3_r` vs `Porsche 911 GT3 R`) flow through to the DB unmodified |
| `car_class` not captured anywhere | Blocking for any class-based filtering / leaderboards | None of the 4 sims expose it via API |
| No bundle upload endpoint | Blocking for `analysis_json` | Current path can't carry the rich `quality_report.json` |
| `analysis_json` field doesn't exist | Blocking for richer review | Webapp can't show quality scores / per-lap classification |
| Multi-repo contract source | Coordination risk | OpenAPI exists at `/openapi.json` but no codegen pipeline |
| Track layout inconsistency | Polish | Only Assetto Corsa stores `trackConfiguration`; iRacing/ACC/LMU drop layout info |

### 1.3 Audit findings recap

- Most reliable adapter: **iRacing** > LMU > ACC ≈ AC.
- All sims provide raw car + track strings + session-type enum. None provide car class.
- `CompoundProfile` (`core/stint_store.py:102-136`) is the closest existing structure to a `vehicle_spec`, but it stores **behavioural** data (fuel/lap, wear curves) not **static** spec.
- The desktop is fully local-first: in-memory buffer → atomic temp-folder rename → bundle on disk. Crash mid-session loses the buffer.

---

## 2. Goals and non-goals

### Goals

1. **Stable canonical identifiers** for sims, cars, tracks (and layouts where available). One ID per real-world entity, regardless of which sim captured it.
2. **Full bundle upload** so the webapp can show everything `session.json` already contains.
3. **`analysis_json`** field on sessions, populated from `quality_report.json` at upload time.
4. **`car_class`** captured at upload time (resolver-supplied).
5. **OpenAPI as single contract** between backend and webapp; webapp regenerates types via codegen.
6. **Backwards compatible**: existing envelope path keeps working unchanged for the next 1+ release.

### Non-goals (for v1)

- Curated `vehicle_spec` static data (mass, power, fuel capacity).
- Curated `track_spec` static data (length, sectors, surface, elevation).
- Cross-sim leaderboards / direct lap-time comparison.
- Auto-discovery of new cars/tracks (resolver is LUT-driven; unknowns logged, not auto-added).
- Real-time streaming upload (still local-first → finalize → upload).
- Mobile / web ingest paths (desktop is the only writer in v1).

---

## 3. Architecture

### 3.1 System layout

```
┌──────────────────────┐         ┌──────────────────────┐         ┌──────────────────────┐
│  Desktop (this repo) │ ──────> │  Backend (FastAPI)   │ <────── │  Webapp (separate)   │
│  PySide6 / Python    │  HTTPS  │  Python / Postgres   │  HTTPS  │  Next.js (existing)  │
│                      │         │                      │         │                      │
│  - capture           │  device │  - 5 envelope routes │  cookie │  - SSR fetch         │
│  - resolver (NEW)    │  token  │  - bundle upload NEW │  auth   │  - server components │
│  - sync queue        │ ──────> │  - read routes       │ <────── │  - typed via OpenAPI │
│  - bundle writer     │ multi-  │  - cars/tracks NEW   │         │                      │
│                      │ part    │  - analysis_json NEW │         │                      │
└──────────────────────┘         └──────────────────────┘         └──────────────────────┘
                                            │
                                            ▼
                                  ┌────────────────────┐
                                  │  Postgres          │
                                  │  - sessions (+5    │
                                  │     new cols)      │
                                  │  - laps            │
                                  │  - coaching        │
                                  │  - events          │
                                  │  - sync_envelopes  │
                                  │  - sync_failures   │
                                  │  - devices         │
                                  │  - users           │
                                  │  - cars (NEW)      │
                                  │  - tracks (NEW)    │
                                  │  - sims (NEW)      │
                                  └────────────────────┘
```

### 3.2 Cross-repo coordination

- **Backend serves `/openapi.json`** (auto-generated by FastAPI) — no extra work.
- **Webapp regenerates types** with `openapi-typescript` against either a running backend or a checked-in `openapi.json` snapshot. CI fails if the committed snapshot differs from a fresh one.
- **API versioning**: introduce `/v1` prefix in this work. All new and existing routes move under `/v1`. Future breaking changes go under `/v2` while `/v1` lives ≥ 1 webapp release longer.
- **Issue tracking**: cross-repo links use the convention `lap-coach/backend#42 ⇄ lap-coach/webapp#17 ⇄ lap-coach/desktop#9`.
- **Release order**: backend ships first (additive), then webapp, then desktop. Never the reverse.
- **Local dev for webapp team**: `docker-compose up` in the backend repo brings up Postgres + API. Webapp's own `docker-compose.yml` references the backend image so a webapp dev needs `docker-compose up` in one place.

### 3.3 Auth model (unchanged)

- Desktop → backend: `Authorization: Bearer <device_token>` + `Idempotency-Key: <UUID>`.
- Webapp → backend: `lc_session` HttpOnly Secure SameSite=Lax JWT cookie.
- No RLS in Postgres; app-layer filter by `user_id` in every query.

---

## 4. Data model changes

### 4.1 New table: `sims`

Static table seeded once. Pure reference.

```sql
CREATE TABLE sims (
    sim_id      TEXT PRIMARY KEY,    -- "iracing", "acc", "assetto_corsa", "lmu"
    display_name TEXT NOT NULL,      -- "iRacing", "Assetto Corsa Competizione", ...
    is_supported BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Seed: 4 rows (iRacing, ACC, Assetto Corsa, Le Mans Ultimate).

### 4.2 New table: `cars`

Canonical car registry. Each row represents one real-world car (e.g. one row for "Ferrari 296 GT3"). Multiple sim-aliases point to the same canonical row.

```sql
CREATE TABLE cars (
    canonical_id    UUID PRIMARY KEY,           -- stable across sims
    canonical_name  TEXT NOT NULL,              -- "Ferrari 296 GT3"
    car_class       TEXT,                       -- "GT3", "GTE", "Hypercar", "Formula", "Touring", NULL if unknown
    manufacturer    TEXT,                       -- optional, "Ferrari"
    model           TEXT,                       -- optional, "296 GT3"
    year            INTEGER,                    -- optional, 2023
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE car_aliases (
    sim_id          TEXT NOT NULL REFERENCES sims(sim_id),
    raw_id          TEXT NOT NULL,              -- as it comes from the sim API
    canonical_id    UUID NOT NULL REFERENCES cars(canonical_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (sim_id, raw_id)
);

CREATE INDEX car_aliases_canonical_idx ON car_aliases(canonical_id);
```

### 4.3 New table: `tracks`

Same pattern as cars — one canonical row per real-world track, multiple sim-aliases.

```sql
CREATE TABLE tracks (
    canonical_id    UUID PRIMARY KEY,
    canonical_name  TEXT NOT NULL,              -- "Monza"
    country         TEXT,                       -- optional, "Italy"
    length_m        DOUBLE PRECISION,           -- optional, will rarely be present in v1
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE track_aliases (
    sim_id          TEXT NOT NULL REFERENCES sims(sim_id),
    raw_id          TEXT NOT NULL,
    raw_layout      TEXT,                       -- optional, e.g. "GP" / "Junior" — NULL when no layout reported
    canonical_id    UUID NOT NULL REFERENCES tracks(canonical_id),
    canonical_layout TEXT,                      -- normalized layout name, "GP" / "Junior" / "Oval"
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (sim_id, raw_id, raw_layout)
);

CREATE INDEX track_aliases_canonical_idx ON track_aliases(canonical_id);
```

Note `(sim_id, raw_id, raw_layout)` is the alias PK — the same `raw_id` can map to two canonical rows when only the layout differs (Bathurst Mt Panorama is one track but used as multiple layouts in some sims).

### 4.4 `sessions` table changes

Add five columns:

```sql
ALTER TABLE sessions
    ADD COLUMN canonical_car_id   UUID REFERENCES cars(canonical_id),
    ADD COLUMN canonical_track_id UUID REFERENCES tracks(canonical_id),
    ADD COLUMN car_class          TEXT,                   -- denormalized from cars.car_class at upload time for fast filter
    ADD COLUMN track_layout       TEXT,                   -- denormalized canonical layout
    ADD COLUMN analysis_json      JSONB;                  -- contents of quality_report.json
```

`canonical_car_id` and `canonical_track_id` are NULLABLE because a session may have no resolver hit. Read endpoints return both raw + canonical fields.

`car_class` and `track_layout` are denormalized for query speed and to survive resolver-table edits. The resolver writes them at upload time; later changes to `cars.car_class` do not retroactively rewrite session rows.

### 4.5 No changes to other tables

`laps`, `coaching_outputs`, `session_events`, `sync_envelopes`, `sync_failures`, `devices`, `users` are unchanged.

---

## 5. Upload-to-analysis contract

### 5.1 Two upload paths, kept distinct

**Path A — envelope queue (existing, unchanged):**
Used for in-progress streaming. The desktop emits `SessionPayload` on session start, then optionally `LapPayload` and `CoachingPayload` while the session is live. Wire format unchanged. **No change to existing endpoints in this work.**

**Path B — bundle upload (NEW):**
Used at session finalize. The desktop ships the **whole bundle directory** (the contents of `<session_dir>/`) in a single multipart request after finalize succeeds locally.

Why two paths instead of one: (a) backwards compat — existing desktop builds keep working, (b) Path A enables future streaming/coaching features without re-uploading the whole bundle, (c) Path B is the right granularity for "completed session" because it's atomic per session.

### 5.2 Bundle upload endpoint

```
POST /v1/bundles
Headers:
  Authorization: Bearer <device_token>
  Idempotency-Key: <UUID — bundle_hash from session.json>
  Content-Type: multipart/form-data
Body (multipart parts):
  manifest:        application/json   (session.json contents)
  laps:            application/json   (laps.json contents)
  events:          application/json   (events.json contents)
  channels:        application/json   (channels.json contents)
  quality:         application/json   (quality_report.json contents)
  telemetry:       application/octet-stream  (telemetry.parquet bytes)
  raw_session:     application/json   (session_info_<sim>.json — optional)
  raw_telemetry:   application/octet-stream  (telemetry_<sim>_raw.csv|parquet bytes — optional)
  raw_channels:    application/json   (channels_<sim>_raw.json — optional)
```

Response:

```json
{ "ok": true, "bundle_id": "<uuid>", "session_id": "<text>", "already_seen": false }
```

Failure shape unchanged from existing typed errors (`{ok:false, code, message, field?}`).

### 5.3 Backend processing on receipt

1. Parse `manifest` → extract `session_id`, `sim`, `car`, `track`, `track_layout`, `start_time`, `end_time`, `sample_count`, `driver_name`, `bundle_hash`.
2. **Resolve canonical IDs**:
   - `canonical_car_id` ← lookup `(sim, car) → canonical_id` in `car_aliases`
   - `canonical_track_id` ← lookup `(sim, track, track_layout) → canonical_id` in `track_aliases`
   - `car_class` ← from `cars.car_class` (joined)
   - On miss: log to `sync_failures` with `error_code = "unresolved_car"` or `"unresolved_track"`, but **accept the upload** with `canonical_*_id = NULL`. The webapp shows raw strings as fallback. Resolver entries can be added later via admin tooling, then a one-shot backfill rerun re-resolves.
3. Upsert into `sessions` (`ON CONFLICT (session_id) DO UPDATE` — bundle is the authoritative source).
4. Bulk-insert `laps`, `coaching_outputs`, `session_events` from the JSON parts. Per-row `envelope_id` derived deterministically from `bundle_hash + entity_type + entity_index`.
5. Store telemetry blobs to object storage (S3-compatible, MinIO for self-hosted) at `bundles/<user_id>/<session_id>/telemetry.parquet`. Backend stores only the **path**, not the bytes, in `sessions.telemetry_path` — which doesn't exist yet either, so:

```sql
ALTER TABLE sessions
    ADD COLUMN telemetry_path TEXT,                        -- "bundles/<user>/<session>/telemetry.parquet"
    ADD COLUMN raw_telemetry_path TEXT,                    -- optional
    ADD COLUMN bundle_hash TEXT;                           -- SHA256 from manifest, used as Idempotency-Key
```

6. Write `analysis_json = quality JSON content`.
7. Insert `sync_envelopes` audit row with `payload_type = "bundle"`, `envelope_id = bundle_hash` (UUID-shaped).
8. Return `{ok: true, bundle_id, session_id, already_seen: false}`.

Replay (same `bundle_hash`): step 4-7 are no-ops via `ON CONFLICT DO NOTHING`; return `already_seen: true`.

### 5.4 Object storage

For self-hosted RC1: **MinIO** in docker-compose alongside Postgres. Bucket `lap-coach-bundles`. Path convention `bundles/<user_uuid>/<session_id>/telemetry.parquet`. Webapp generates time-limited pre-signed URLs to fetch telemetry for download (not for inline rendering — too large).

For Supabase / managed deploys: native object storage with the same path convention.

Add to backend env:

```
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
S3_BUCKET=lap-coach-bundles
```

### 5.5 Why `analysis_json` belongs on `sessions`, not a separate table

`quality_report.json` is small (≤ a few KB), one-per-session, and only ever read in the context of its session. JSONB on `sessions` keeps the read query simple. If it grows past ~50KB or gets queried independently (e.g. "all sessions with quality > 0.8") we promote it to a real table with extracted columns — but not in v1.

---

## 6. Resolver design

### 6.1 What the resolver does

Given `(sim_id, raw_car, raw_track, raw_track_layout)`, return `(canonical_car_id, canonical_track_id, canonical_layout, car_class)` or `(None, None, None, None)` on miss.

Lives **on the backend, not the desktop**. Reasons:
- Single source of truth that all sources (desktop, future mobile, manual upload) share.
- Updates without shipping a desktop release.
- Backfill of older sessions when LUTs grow.

The desktop **passes raw strings** unchanged in the manifest. It has no resolver knowledge.

### 6.2 LUT format

Two seed JSON files at `backend/seed/`:

```jsonc
// canonical_cars.json
[
  {
    "canonical_id": "01HZ8J3R7E6PMVTQXX0001",
    "canonical_name": "Ferrari 296 GT3",
    "car_class": "GT3",
    "manufacturer": "Ferrari",
    "model": "296 GT3",
    "year": 2023,
    "aliases": [
      { "sim_id": "iracing",        "raw_id": "ferrari296gt3" },
      { "sim_id": "acc",            "raw_id": "ferrari_296_gt3" },
      { "sim_id": "assetto_corsa",  "raw_id": "ferrari_296_gt3" },
      { "sim_id": "lmu",            "raw_id": "Ferrari 296 GT3" }
    ]
  }
]
```

```jsonc
// canonical_tracks.json
[
  {
    "canonical_id": "01HZ8J3R7E6PMVTQXX1001",
    "canonical_name": "Monza",
    "country": "Italy",
    "aliases": [
      { "sim_id": "iracing",       "raw_id": "Monza", "raw_layout": null,  "canonical_layout": "GP" },
      { "sim_id": "acc",           "raw_id": "monza", "raw_layout": null,  "canonical_layout": "GP" },
      { "sim_id": "assetto_corsa", "raw_id": "monza", "raw_layout": "gp",  "canonical_layout": "GP" },
      { "sim_id": "assetto_corsa", "raw_id": "monza", "raw_layout": "junior", "canonical_layout": "Junior" },
      { "sim_id": "lmu",           "raw_id": "Monza", "raw_layout": null,  "canonical_layout": "GP" }
    ]
  }
]
```

UUIDs are version 7 (time-ordered, monotonic) so chronologically newer registry entries sort later — useful for "what cars were added since last release" queries.

### 6.3 Seed import

A script `backend/scripts/import_canonicals.py` reads the JSON files and upserts into `cars`, `car_aliases`, `tracks`, `track_aliases`. Idempotent — same input always produces the same DB state. Runs after `alembic upgrade head` in the deploy script.

### 6.4 Resolver code (backend)

```python
# backend/app/resolver.py (NEW)
async def resolve_car(db, sim_id: str, raw_car: str) -> ResolvedCar | None: ...
async def resolve_track(db, sim_id: str, raw_track: str, raw_layout: str | None) -> ResolvedTrack | None: ...
```

Pure function over the DB. Cached in-process for 5 minutes (LRU on `(sim_id, raw_id)`) since the registry is read-heavy and rarely written.

### 6.5 Unresolved fallback

When resolver returns None:
- Insert the session with `canonical_*_id = NULL`.
- Log to `sync_failures` with `error_code = "unresolved_car"` (or `track`), `error_message` containing the raw string.
- Backend ships an admin-only endpoint `GET /v1/admin/unresolved` listing all unresolved car/track strings with counts, so curators can add them in batch.

The session is **never rejected** for an unresolved car/track. Webapp displays raw strings as fallback.

### 6.6 Backfill

`backend/scripts/backfill_resolver.py` re-runs the resolver over all `sessions` rows where `canonical_car_id IS NULL` or `canonical_track_id IS NULL`. Run after each LUT addition.

---

## 7. Desktop changes

Minimal — desktop is the source of raw strings only.

### 7.1 New: bundle uploader

`src/lap_coach_logger/sync/bundle_uploader.py` — sibling to existing `sync/client.py`.

```python
class BundleUploader:
    def upload(self, bundle_dir: Path, device_token: str, base_url: str) -> UploadResult:
        """Multipart POST of session.json + laps.json + ... + telemetry.parquet to /v1/bundles."""
```

Triggered by `SyncQueueManager` after session finalize succeeds locally. Same retry policy as `HttpTransport`. Failures persist in a new `bundle_failures.json` (analogous to `sync_failures.json`).

### 7.2 Manifest enrichment (`session.json`)

Add fields to `SessionManifest` (`writers/finalizer.py`):

- `sim_id` — normalized, e.g. `"iracing"` (from a small map at finalize time, since the adapter knows this)
- `bundle_hash` — already exists
- (No canonical IDs — backend resolves)

### 7.3 No removal of envelope path

`SessionPayload`/`LapPayload`/etc. envelope shipping continues to work for in-progress sessions where streaming matters (live coaching). Bundle upload is added alongside.

### 7.4 Config

Add to `AppConfig.sync`:

```
bundle_upload_enabled: bool = True       # opt out for bandwidth-constrained users
bundle_upload_after_finalize: bool = True
bundle_max_size_mb: int = 200            # safety cap; refuse to upload larger
```

### 7.5 What the desktop does NOT do

- No resolver lookup
- No canonical ID generation
- No re-uploading old sessions on schema changes (backend backfill handles that)
- No partial-bundle uploads (atomicity = whole bundle or nothing)

---

## 8. Backend changes summary

| Concern | Change |
|---|---|
| Migrations | New: `0002_canonical_registry.py` (sims, cars, car_aliases, tracks, track_aliases). New: `0003_sessions_extensions.py` (canonical_car_id, canonical_track_id, car_class, track_layout, analysis_json, telemetry_path, raw_telemetry_path, bundle_hash). |
| Routes | New router `routers/bundles.py` with `POST /v1/bundles`. New `routers/admin.py` with `GET /v1/admin/unresolved`. Move all existing routes under `/v1` prefix. |
| Resolver | New module `app/resolver.py`. |
| Object storage | New module `app/storage.py` wrapping S3/MinIO. New env vars in `config.py`. |
| Read endpoints | `GET /v1/sessions/{id}` returns canonical fields + raw fields side by side, plus a pre-signed `telemetry_url`. |
| Seed | New `seed/canonical_cars.json` + `canonical_tracks.json`. New `scripts/import_canonicals.py`. |
| Backfill | New `scripts/backfill_resolver.py`. |
| OpenAPI | Auto-served, no extra work. Tag `cars`, `tracks`, `bundles`, `admin`. |

---

## 9. Webapp expectations (contract for the external repo)

The webapp does not change in this repo. The contract it consumes:

### 9.1 Auth (unchanged)

`POST /v1/auth/login`, `/v1/auth/logout`, `GET /v1/auth/me` — same shapes as today.

### 9.2 New / updated read endpoints

`GET /v1/sessions?limit=100` returns `SessionSummary[]`:

```ts
interface SessionSummary {
    session_id: string;
    sim_id: string;             // canonical sim ID, e.g. "iracing"
    sim_display_name: string;   // "iRacing"
    raw_car: string;            // sim-native, fallback for unresolved
    canonical_car_id: string | null;
    canonical_car_name: string | null;
    car_class: string | null;   // "GT3" | "GTE" | "Hypercar" | "Formula" | "Touring" | null
    raw_track: string;
    canonical_track_id: string | null;
    canonical_track_name: string | null;
    track_layout: string | null; // canonical, e.g. "GP", "Junior"
    mode: "sprint" | "endurance" | "coaching" | "data";
    driver_name: string;
    start_time: string;
    end_time: string | null;
    sample_count: number;
    lap_count: number;
}
```

`GET /v1/sessions/{id}` returns `SessionDetail`:

```ts
interface SessionDetail extends SessionSummary {
    source: string;
    schema_version: number;
    device_token: string;       // last-8 only displayed
    envelope_count: number;
    bundle_hash: string | null;
    telemetry_url: string | null;   // pre-signed, expires in 1 hour
    analysis: AnalysisJson | null;  // contents of quality_report.json
    laps: LapOut[];
    coaching: CoachingOut[];
    events: EventOut[];
}
```

`AnalysisJson` is shaped like the existing `quality_report.json`; webapp can render whatever fields it cares about.

### 9.3 Display rules

- If `canonical_car_name` is present, show it as the primary label. Show `raw_car` only as a faded subtitle for debugging.
- If `canonical_car_name` is null, show `raw_car` as the primary label with a `[?]` badge.
- `car_class` becomes a colored badge ("GT3" purple, "Hypercar" red, etc.) — only if non-null.
- `track_layout`, when non-null, appears as " · Layout" suffix to the canonical name.
- `telemetry_url` is rendered as a "Download .parquet" button; not visualised inline.
- `analysis.recommendation` (`ready_for_review` / etc.) becomes a status pill.

### 9.4 Type generation

Webapp adds `npm run regen-types`:

```
openapi-typescript http://localhost:8000/openapi.json -o lib/api-types.ts
```

CI fails if the committed file differs from a fresh regeneration against the latest backend tag.

### 9.5 What the webapp does NOT do

- Does not resolve canonical IDs itself.
- Does not call the admin endpoints (those are backend-only / curator tooling).
- Does not write — read-only against `GET /v1/...` endpoints.

---

## 10. Implementation phasing

### Phase 1 — Backend foundation (1-2 sessions of work)

- Migrations: `0002_canonical_registry`, `0003_sessions_extensions`
- Resolver module + tests
- Seed files for **iRacing only** (most-used adapter)
- Import + backfill scripts
- `/v1` route prefix migration
- Update `GET /v1/sessions` and `GET /v1/sessions/{id}` to expose canonical fields

### Phase 2 — Bundle upload (1-2 sessions)

- `POST /v1/bundles` endpoint
- Object storage (MinIO in docker-compose, S3-compatible in prod)
- `analysis_json` extraction from `quality_report.json`
- `routers/bundles.py` + tests

### Phase 3 — Desktop integration (1 session)

- `BundleUploader` module + `SyncQueueManager` wiring
- `AppConfig.sync.bundle_upload_*` flags
- `SessionManifest.sim_id` field
- E2E test: capture iRacing → bundle uploaded → visible in webapp via mocked client

### Phase 4 — Cross-sim coverage (1 session)

- Seed entries for ACC, Assetto Corsa, LMU
- Backfill run
- Admin endpoint `GET /v1/admin/unresolved` for curators

### Phase 5 — Webapp contract publish (handed off to external repo)

- Publish `openapi.json` snapshot to a tag
- Webapp regenerates types, updates display, releases

Each phase is independently shippable. Phase 1 can ship without Phase 2, etc. Phase 5 is owned by the webapp team.

---

## 11. Open decisions

These need a call before the smaller specs are written:

| # | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | Object storage for self-hosted | MinIO sidecar / direct filesystem volume / S3 only | MinIO — same API as S3, swap host header in prod |
| D2 | What about sessions captured before resolver existed? | Backfill all / leave NULL / one-time prompt to user | Backfill on each LUT update (idempotent) |
| D3 | Where does the LUT live? | Backend repo `seed/` / separate `protocol/` repo / Postgres-only with admin UI | Backend repo `seed/` for v1; admin UI deferred |
| D4 | Bundle upload size cap | 50 MB / 200 MB / 1 GB | 200 MB; refuse client-side, return 413 server-side |
| D5 | Should the desktop pre-resolve before upload (faster webapp) or always defer to backend? | Pre-resolve / defer | Defer — backend is the single source of truth |
| D6 | Telemetry parquet — public download or always pre-signed URL? | Public / signed | Signed; 1 hour TTL |
| D7 | Bundle upload retries — at what granularity? | Whole bundle / per-part / smart resume | Whole bundle. No partial state on the backend until commit. |
| D8 | When a session arrives with `sim_id` not in `sims` table | Reject 400 / accept with NULL canonicals / auto-insert sim row | Reject 400 — `sims` is small and curated; an unknown sim is a desktop bug |
| D9 | Multi-tenant car/track aliases — can two users have different canonical names for the same raw id? | No (global registry) / yes (per-user) | No. One canonical registry shared across users. |
| D10 | What happens when the same `bundle_hash` arrives from a different `device_token` (same user)? | Accept (replay-safe) / reject (suspicious) | Accept — replay is fine. Different-user replay is rejected by `user_id` mismatch on the existing row. |

---

## 12. Success criteria

Connected v1 ships when:

1. A user captures a session in **iRacing** with car "Ferrari 296 GT3" and track "Monza" → the webapp's `/sessions` page shows a row with badge "Ferrari 296 GT3 · GT3 · Monza GP".
2. The same user captures a session in **ACC** with raw car "ferrari_296_gt3" and track "monza" → the webapp shows the **same** badges.
3. `quality_report.json.recommendation` from the desktop appears as a status pill on the webapp session detail page.
4. A new car released by iRacing post-launch is added to `seed/canonical_cars.json`, the import script runs, the backfill script runs, and historical sessions from that car retroactively show their canonical name without re-uploading.
5. The webapp regenerates types via `openapi-typescript` and the build passes.
6. Bundle upload is idempotent: re-running the desktop's "upload" against a session already in the backend returns `{already_seen: true}` with no data duplication.

---

## 13. Smaller specs to derive from this document

| Sub-spec | Section coverage | Owner |
|---|---|---|
| Resolver design | §6 | backend |
| Bundle upload contract | §5 | backend + desktop |
| Canonical registry seed | §6.2, §6.3 | backend (curator role) |
| DB migration 0002 + 0003 | §4 | backend |
| Desktop bundle uploader | §7 | desktop |
| Webapp contract publish | §9 | backend (publisher) + webapp (consumer) |
| Object storage layer | §5.4, D1 | backend |
| Cross-repo CI / type-regen | §3.2, §9.4 | webapp |
| Backfill + admin tooling | §6.5, §6.6 | backend |
| Phasing + release plan | §10 | release engineer |

---

## 14. Out of scope / explicitly deferred

- Curated `vehicle_spec` data (mass, power, fuel capacity)
- Curated `track_spec` data (length, sectors, surface, elevation)
- Cross-sim leaderboards
- Weather-state normalization (fields don't exist in 3 of 4 sims)
- Driver/account ID normalization (only LMU exposes one, and the adapter doesn't even read it today)
- Real-time bundle streaming (still local-first → finalize → upload)
- Auto-suggestion of canonical IDs (resolver is LUT-only; ML matching is GA territory)
- Mobile / web ingest paths
- Public read-only API for third parties
- Bulk "submit my historical bundles" tool (manual one-shot if needed)

---

## 15. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Curating the LUT becomes the bottleneck | Medium | Admin endpoint `GET /v1/admin/unresolved` surfaces gaps in real time; curator can batch-add |
| Bundle uploads saturate user bandwidth | Low | Local-first model means uploads happen post-session, can be paused/throttled in `AppConfig.sync` |
| Object storage becomes expensive at scale | Medium | Telemetry parquet ~1-5 MB per session; 1000 sessions/user/year ≈ 5 GB, ~$0.10/mo S3 — acceptable |
| Backend resolver becomes a hot path | Low | LRU cache + small registry size make this O(1) in practice |
| Webapp ships before backend supports new fields | High | API versioning (`/v1`) + OpenAPI codegen + CI lint catches it |
| Two contributors write conflicting LUT entries | Medium | LUT files are JSON; PR review + a CI test that asserts no duplicate `(sim_id, raw_id)` keys |

---

## 16. Appendix: glossary

- **Canonical ID** — UUID identifying one real-world entity (car, track) regardless of which sim observed it.
- **Raw ID** — the string the sim's API returns (e.g. `porsche_911_gt3_r`).
- **Alias** — a row mapping `(sim_id, raw_id) → canonical_id`.
- **Bundle** — the on-disk session directory containing manifest + telemetry + sidecars.
- **Envelope** — an in-memory typed payload (SessionPayload, LapPayload, …) shipped via the existing sync queue.
- **Resolver** — the backend function that turns raw strings into canonical IDs.
- **LUT** — Look-Up Table; the seed JSON files mapping aliases.
- **Manifest** — `session.json`, the desktop's per-session metadata file.
