# Webapp Contract v2 — Handoff Document

> **For:** webapp team (external repo)
> **From:** backend + desktop (this repo)
> **Date:** 2026-04-16
> **Backend version:** openapi.json snapshot committed at `backend/openapi.json`
> **Types file:** `backend/contract/webapp-types.ts` — copy or generate via `openapi-typescript`

---

## What changed

The backend API (`/v1/...`) now exposes **canonical car/track fields** and **analysis data** on session endpoints. Previously, only raw sim strings were available.

### New fields on `GET /v1/sessions` (SessionSummary)

| Field | Type | When present | Example |
|---|---|---|---|
| `canonical_car_id` | `string \| null` (UUID) | When desktop resolver found a match | `"b0000001-0001-7000-8000-000000000001"` |
| `canonical_car_name` | `string \| null` | Same | `"Ferrari 296 GT3"` |
| `car_class` | `CarClass \| null` | Same | `"GT3"` |
| `canonical_track_id` | `string \| null` (UUID) | When desktop resolver found a match | `"a0000001-0001-7000-8000-000000000001"` |
| `canonical_track_name` | `string \| null` | Same | `"Monza"` |
| `track_layout` | `string \| null` | Same | `"GP"` |

### New fields on `GET /v1/sessions/{id}` (SessionDetail)

All of the above, plus:

| Field | Type | When present | Example |
|---|---|---|---|
| `bundle_hash` | `string \| null` | When session was uploaded via bundle | `"sha256:9f8a..."` |
| `analysis_json` | `AnalysisJson \| null` | When bundle included analysis.json | See §3 below |

### New endpoints

| Endpoint | Purpose | Auth |
|---|---|---|
| `GET /v1/sessions/{id}/files/{filename}` | Signed download redirect (telemetry.parquet, etc.) | session cookie |
| `GET /v1/registry/snapshot?since=<ver>` | Full canonical LUT (cars + tracks) | none (public) |
| `GET /v1/admin/drifts` | Canonical drift log (curator) | none (v1) |
| `GET /v1/admin/unresolved` | Unresolved raw strings (curator) | none (v1) |

---

## Display rules

### Car name

```tsx
{session.canonical_car_name
    ? <span>{session.canonical_car_name}</span>
    : <span className="muted">{session.car} <Badge variant="unknown">[?]</Badge></span>
}
```

- If `canonical_car_name` is non-null: show it as the **primary label**.
- If null: show `car` (the raw sim string) with a `[?]` badge indicating unresolved.
- `car` (raw) can optionally appear as a faded subtitle for debugging.

### Car class badge

```tsx
{session.car_class && <Badge variant={classVariant(session.car_class)}>{session.car_class}</Badge>}
```

| `car_class` | Color | Hex suggestion |
|---|---|---|
| `GT3` | Purple | `#8B5CF6` |
| `GT4` | Blue | `#3B82F6` |
| `GTE` | Amber | `#D97706` |
| `Hypercar` | Red | `#DC2626` |
| `LMP2` | Teal | `#0D9488` |
| `Formula` | Yellow | `#EAB308` |
| `Cup` | Orange | `#EA580C` |
| `Touring` | Green | `#16A34A` |
| `null` | — | Don't render |

### Track name + layout

```tsx
<span>
    {session.canonical_track_name ?? session.track}
    {session.track_layout && <span className="muted"> · {session.track_layout}</span>}
</span>
```

### Analysis (session detail page)

`analysis_json` is the desktop-computed analysis snapshot. Render it as a "Session Analysis" card on the detail page.

**Recommended sections:**

1. **Quality** — `analysis_json.session_quality.overall_score` as a progress bar (0..1)
2. **Lap summary** — fastest, median, consistency from `lap_summary`
3. **Fuel** — total consumed, avg per lap from `stint_summary`
4. **Best theoretical** — `track_position.best_theoretical_lap_s` + sector breakdown
5. **Verdict** — `recommendation.verdict` as a status pill:
   - `ready_for_review` → green pill "Ready"
   - `partial_data` → yellow pill "Partial"
   - `not_recommended` → red pill "Issues"

If `analysis_json` is null (older sessions, or session synced via envelope path without bundle): show "No analysis available — re-upload from desktop to generate."

### Telemetry download

```tsx
{session.bundle_hash && (
    <a href={`/v1/sessions/${session.session_id}/files/telemetry.parquet`}>
        Download telemetry (.parquet)
    </a>
)}
```

The endpoint returns a `302` redirect to a MinIO pre-signed URL (1-hour TTL). If `bundle_hash` is null, the telemetry file wasn't uploaded — don't show the button.

---

## Type generation

### Option A: Copy types (quickest)

```bash
cp ../desktop/backend/contract/webapp-types.ts lib/api-types.ts
```

### Option B: Generate from OpenAPI (recommended for CI)

```bash
# Against a running backend:
npx openapi-typescript http://localhost:8000/openapi.json -o lib/api-types.ts

# Against the committed snapshot:
npx openapi-typescript ../desktop/backend/openapi.json -o lib/api-types.ts
```

### CI guard

Add a step that fails if committed types drift from the latest backend:

```yaml
- name: Check API types
  run: |
    npx openapi-typescript $BACKEND_URL/openapi.json -o /tmp/fresh-types.ts
    diff lib/api-types.ts /tmp/fresh-types.ts || (echo "Types drifted — regenerate" && exit 1)
```

---

## Migration checklist for the webapp team

- [ ] Copy or generate updated types from `backend/contract/webapp-types.ts`
- [ ] Update `/sessions` page to render `canonical_car_name` + `car_class` badge + `canonical_track_name` + `track_layout`
- [ ] Add fallback to `car` / `track` (raw) when canonical is null
- [ ] Update `/sessions/[id]` page to render `analysis_json` card (quality, laps, fuel, verdict)
- [ ] Add "Download telemetry" button gated on `bundle_hash` presence
- [ ] Verify signed download redirect works (302 → MinIO URL)
- [ ] Run type-check against the new types — should surface any missed fields
- [ ] Update API base URL in `.env` to point at the `/v1` prefix (all routes moved)
- [ ] Update any hardcoded fetch paths from `/sessions` → `/v1/sessions`, `/auth/login` → `/v1/auth/login`, etc.

---

## Breaking changes

1. **All routes moved under `/v1` prefix.** Old paths (`/sessions`, `/auth/login`) return 404. Update all fetch calls.
2. **`SessionSummary` and `SessionDetail` have new nullable fields.** TypeScript types are additive (optional), so existing code won't break at compile time, but the webapp should render the new fields to deliver value.
3. **No removed fields.** Everything from the previous API version is still present.

---

## Known limitations (from the backend)

- `car_class` is denormalized at upload time and not retroactively updated if the registry changes. Historical sessions keep their original class.
- `analysis_json` is only present for sessions uploaded via the bundle path (`POST /v1/bundles`). Sessions synced via the envelope path (`POST /v1/sessions-start` etc.) have `analysis_json = null`.
- Signed download URLs expire after 1 hour. The webapp should not cache them.
- Admin endpoints (`/v1/admin/drifts`, `/v1/admin/unresolved`) are not auth-gated in v1. Add role checks before exposing in a multi-tenant webapp.
