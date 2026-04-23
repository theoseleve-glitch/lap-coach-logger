# Overlay Persistence

## Recommendation

Use a hybrid model:

- SQLite for the primary local store
- JSON for explicit export/import bundles and legacy/debug paths

Why:

- SQLite gives row-level recovery, atomic updates, and safe schema evolution.
- JSON is still useful for layout bundle portability and manual inspection.
- A pure JSON primary store is simple, but one malformed overlay record can poison the whole document.

## Final Design

Primary local state lives in `overlay_state.db`.

Persisted concerns:

- favorite overlay ids
- browser preferences
- layout presets
- overlay instances and placement
- per-overlay last-used settings
- layout activation state
- layout shortcuts

The primary implementation is in [store.py](/C:/Users/Admin/Documents/Telemetry/datalogger/src/lap_coach_logger/overlays/store.py).

## Storage Model

SQLite tables:

- `document_state`
- `favorites`
- `browser_preferences`
- `layouts`
- `overlay_instances`
- `last_used_settings`
- `quarantine_records`

This keeps shared document metadata small while storing recoverable entities independently.

## Versioning

Two versions are tracked:

- document schema version: overlay state payload shape
- storage schema version: SQLite table schema via `PRAGMA user_version`

The document migrator is in [migrations.py](/C:/Users/Admin/Documents/Telemetry/datalogger/src/lap_coach_logger/overlays/migrations.py).
The SQLite migration runner is in [store.py](/C:/Users/Admin/Documents/Telemetry/datalogger/src/lap_coach_logger/overlays/store.py).

## Recovery Rules

Reads are strongly validated.

- invalid singleton payloads fall back to defaults for that section
- corrupted row payloads are quarantined and removed from the live document
- graph inconsistencies are normalized after deserialize
- dangling overlay instances are dropped
- invalid layout shortcuts are cleared
- invalid browser-selected layout ids are reset
- duplicate favorites and duplicate last-used records are normalized

The load path always returns an `OverlayStoreLoadReport` with warnings instead of failing silently.

## Export / Import

- primary local state stays in SQLite
- layout sharing should continue using JSON layout bundles
- future sync can serialize the same domain models without exposing SQLite internals

## Debugging

For explicit JSON-backed stores:

- migration rewrites create `.bak` backups
- unreadable files create `.corrupt` backups before defaults are used

For SQLite-backed stores:

- quarantined raw payloads are preserved in `quarantine_records`

## Why Not JSON-Only

JSON-only is acceptable for tiny configs, but it is a bad default here because LAP COACH now persists many independent overlay entities. Partial corruption recovery is materially better with SQLite.
