# Overlay Platform Backend

_Last reviewed: 2026-04-26_

This document defines the backend architecture for LAP COACH overlay management.

## 1. Architecture Proposal

The overlay system is treated as a separate application subsystem with four clean layers:

1. Catalog layer
   Built-in or plugin-provided overlay definitions live in a registry. Definitions contain metadata, entitlement requirements, layout hints, and settings schema. They are immutable.
2. Persistence layer
   User state is stored in an atomic JSON document under app config. The persisted document contains layout presets, overlay instances, favorites, and active preset. It does not persist live window handles or preview sessions.
3. Runtime layer
   Runtime state tracks which persisted overlay instances are mounted for the active preset and which preview sessions are active. This layer is intentionally UI-agnostic.
4. Orchestration layer
   One service owns catalog queries, settings validation, entitlement checks, mutations, persistence, runtime sync, and event emission. The Qt shell should talk to this service instead of wiring together many small objects directly.

Design intent:

- overlay metadata is separated from user settings and runtime state
- schema validation is generic and registry-driven
- overlay-specific behavior stays in definition modules and renderer implementations, not in shared infrastructure
- the runtime controller is usable from Qt, but does not depend on Qt widgets or signals
- one callback-style event bus prevents signal fan-out and keeps backend changes observable

## 2. Module / Package Structure

The new backend package lives in `src/lap_coach_logger/overlays/`.

- `models.py`
  Core domain models for definitions, settings schema, presets, slots, instances, persistence documents, catalog entries, and runtime state.
- `builtins.py`
  Built-in overlay definitions shipped with the app. This is where overlay-specific metadata belongs.
- `registry.py`
  Definition registry, catalog search/filter, category grouping, and generic settings validation/coercion.
- `entitlements.py`
  Premium gating contracts and a simple local entitlement resolver.
- `migrations.py`
  Schema version migration logic for persisted overlay state.
- `store.py`
  Atomic JSON persistence with migration backup handling.
- `runtime.py`
  Preview/live runtime state controller with no Qt dependency.
- `service.py`
  Main orchestration service and the event bus.
- `browser.py`
  Read-model state for the overlay browser / picker UI: filter
  state, category items, overlay detail view, and the
  `OverlayBrowserPageService` that projects the catalog +
  user state into the QML-friendly shape.
- `runtime_instances.py`
  Per-instance lifecycle controller that mounts and unmounts
  overlay renderer instances, plus the bus that routes user
  actions back to the orchestration service.
- `settings_models.py`
  Declarative schema models for per-overlay settings —
  fields, sections, validation rules, visibility conditions,
  resolution + migration result types.
- `settings_service.py`
  Schema registry, validator, and migration runner for
  per-overlay settings. Sits between `settings_models` and
  `service.py` so settings remain editable independently of
  overlay placement / runtime state.
- `telemetry_bindings.py`
  Declares the telemetry channels each overlay needs, scores
  availability against the live snapshot, and serves preview
  fixtures when the live signal is missing — the contract
  between overlay definitions and the live telemetry pipeline.
- `__init__.py`
  Public exports and the default service factory.

## 3. Core Domain Models

### Metadata / Catalog

- `OverlayDefinition`
  Immutable overlay metadata:
  - `overlay_id`
  - `renderer_key`
  - `display_name`
  - `description`
  - `category`
  - `tags`
  - `search_keywords`
  - `preview_asset`
  - `settings_schema`
  - `capabilities`
  - `layout`
  - `entitlement`

- `OverlaySettingField`
  Generic schema for per-overlay settings:
  - `kind`: `bool`, `int`, `float`, `string`, `enum`, `color`
  - `section`: typically `performance`, `size`, `appearance`, `visibility`, `behavior`
  - default, description, min/max, step, enum options

- `OverlayCapabilities`
  Generic runtime/UI capabilities:
  - multiple instances
  - resizable
  - draggable
  - pinnable
  - scalable
  - preview support

- `OverlayLayoutHints`
  Default geometry and slot hints:
  - default/min width and height
  - default anchor
  - supported slots

- `OverlayEntitlement`
  Premium or free overlay requirement plus feature flag key.

### Persisted User State

- `OverlayStateDocument`
  Root persisted state:
  - schema version
  - active preset id
  - favorite overlay ids
  - presets
  - instances
  - timestamps

- `OverlayPreset`
  A named layout preset that can be bound later to sim/car/driver contexts.

- `OverlayLayoutSlot`
  Optional slot definitions per preset, including allowed categories / overlay ids and current assignment.

- `OverlayInstance`
  User-owned overlay instance:
  - stable `instance_id`
  - `overlay_id`
  - `preset_id`
  - `slot_id`
  - `placement`
  - `settings`
  - `enabled`
  - timestamps

- `OverlayPlacement`
  Persisted geometry and non-schema runtime-ish placement values:
  - x/y
  - width/height
  - scale
  - opacity
  - z-index
  - monitor id
  - pinned / locked

### Runtime State

- `OverlayRuntimeState`
  Ephemeral runtime state for mounted live overlays.

- `OverlayPreviewSession`
  Ephemeral preview session for overlay browser previews.

- `OverlayEvent`
  Single backend event shape used by the event bus.

## 4. Persistence Format

The persistence file is `overlay_state.json` under the existing config directory.

Example shape:

```json
{
  "schema_version": 2,
  "active_preset_id": "preset-default",
  "favorite_overlay_ids": ["track_map", "session_delta"],
  "presets": [
    {
      "preset_id": "preset-default",
      "name": "Default Layout",
      "description": "Starter preset for built-in overlays.",
      "scope": {
        "sim": "",
        "car": "",
        "driver": ""
      },
      "slots": [
        {
          "slot_id": "top_left",
          "name": "Top Left",
          "instance_id": "overlay-abcd1234",
          "allowed_categories": ["Driving"],
          "allowed_overlay_ids": [],
          "locked": false
        }
      ],
      "instance_ids": ["overlay-abcd1234"],
      "created_at_utc": "2026-04-01T15:00:00+00:00",
      "updated_at_utc": "2026-04-01T15:00:00+00:00"
    }
  ],
  "instances": [
    {
      "instance_id": "overlay-abcd1234",
      "overlay_id": "session_delta",
      "preset_id": "preset-default",
      "name": "Session Delta",
      "enabled": true,
      "slot_id": "top_left",
      "placement": {
        "x": 48,
        "y": 72,
        "width": 420,
        "height": 180,
        "scale": 1.0,
        "opacity": 0.95,
        "z_index": 0,
        "monitor_id": "primary",
        "pinned": true,
        "locked": false
      },
      "settings": {
        "show_gain_loss_markers": true,
        "delta_precision_ms": "0.01",
        "scale": 1.0,
        "opacity": 0.95
      },
      "created_at_utc": "2026-04-01T15:00:00+00:00",
      "updated_at_utc": "2026-04-01T15:00:00+00:00"
    }
  ],
  "created_at_utc": "2026-04-01T15:00:00+00:00",
  "updated_at_utc": "2026-04-01T15:05:00+00:00"
}
```

Rules:

- definitions are not persisted here
- preview sessions are not persisted
- runtime state is not persisted
- file writes are atomic
- migrations create a `.bak` copy before rewriting older formats

## 5. Service Layer Design

`OverlayManagerService` is the single backend entrypoint.

Responsibilities:

- load and normalize persisted state
- ensure a default preset exists
- expose searchable/grouped catalog snapshots
- validate and normalize instance settings against the registry schema
- apply entitlement checks before creation
- create / update / remove overlay instances
- manage favorite overlays
- create and activate presets
- assign overlays to slots
- start and stop preview sessions
- sync runtime state after every mutation
- persist state after every mutation
- publish a single event stream for the UI layer

Qt integration pattern:

- create one Qt adapter or use the existing desktop service as the adapter
- subscribe once to `OverlayEventBus`
- map backend snapshots into Qt models or widgets
- do not let individual overlay widgets own persistence logic

## 6. Runtime Lifecycle

1. App boot
   - load `overlay_state.json`
   - migrate if required
   - ensure default preset exists
   - sync runtime controller with the active preset
2. Overlay browser query
   - UI requests `catalog(filter_spec=...)`
   - service returns grouped/searchable entries with entitlement state and favorites
3. Preview
   - UI requests `start_preview(overlay_id)`
   - runtime creates an ephemeral preview session
   - no persisted state is mutated
4. Add overlay to layout
   - UI requests `add_overlay_instance(...)`
   - service checks entitlement
   - service validates settings with defaults
   - service persists instance + preset linkage
   - runtime marks it mounted if the preset is active
5. Layout activation
   - UI requests `activate_preset(preset_id)`
   - runtime mounts enabled overlays from the preset and marks others inactive
6. User customization
   - UI sends setting / placement / visibility mutations
   - service validates and persists
   - runtime updates visible state

## 7. Schema / Versioning Strategy

The overlay persistence document has an explicit schema version.

Current strategy:

- `schema_version = 2`
- missing version is treated as `0`
- v0 to v1:
  - migrate `favorites` to `favorite_overlay_ids`
  - migrate `layouts` / `active_layout_id`
- v1 to v2:
  - add preset scope
  - add slot ids
  - add placement `monitor_id`, `opacity`, `pinned`, `locked`
  - normalize timestamps

Guidelines for future evolution:

- only the store writes files
- always migrate raw dicts before model construction
- keep migrations additive and deterministic
- back up the pre-migration file before write-back
- never bake migration logic into UI or renderer code

## 8. Example Implementation Skeleton

The current codebase includes:

- generic registry and validation engine
- persistent overlay document and migrations
- entitlement resolver
- runtime controller for live and preview overlays
- high-level manager service
- built-in sample overlay definitions:
  - `session_delta`
  - `track_map`
  - `fuel_strategy`
  - `input_diagnostics`

Sample factory:

```python
from lap_coach_logger.overlays import build_default_overlay_manager

overlay_service = build_default_overlay_manager()
catalog = overlay_service.catalog()
preview = overlay_service.start_preview("track_map")
```

## 9. Test Plan

Backend tests should cover:

1. Registry / schema validation
   - default settings expansion
   - type coercion
   - numeric clamping
   - unknown key handling
   - search/filter/category behavior
2. Persistence
   - load missing file
   - atomic save
   - round-trip equality
   - migration backup creation
3. Migration
   - version-less legacy document migration
   - previous schema version migration
4. Entitlements
   - premium overlay locked by default
   - unlocked through premium flag
   - unlocked through feature flag
5. Service orchestration
   - create preset
   - create overlay instance
   - update settings and placement
   - assign slots safely
   - remove instance
   - favorite toggling
6. Runtime lifecycle
   - active preset mount states
   - preview session start / stop
   - preview sessions remain ephemeral across reloads

This is intentionally backend-first. UI screens can now be built on top of a stable overlay platform instead of embedding overlay persistence and business rules inside Qt widgets.

