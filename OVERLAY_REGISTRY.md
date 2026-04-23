# Overlay Registry Backend

This note documents the LAP COACH overlay registry backend implemented in `src/lap_coach_logger/overlays/`.

## Scope

The registry is intentionally separate from runtime window instances and Qt widgets.

It owns:

- overlay metadata definitions
- declarative and Python-based registration
- category grouping
- favorites and hidden/internal visibility rules
- search and filter queries
- future localization hooks

It does not own:

- floating window creation
- renderer widget lifecycle
- telemetry rendering logic
- per-layout runtime mounting

## OverlayDefinition shape

`OverlayDefinition` now carries the catalog fields needed by a browser panel:

- `overlay_id`
- `display_name`
- `short_description`
- `category`
- `tags`
- `default_size`
- `default_anchor`
- `premium_tier`
- `availability_status`
- `preview_asset_ref`
- `settings_schema_ref`
- `supported_simulators`
- `default_enabled`
- `sort_order`

Additional forward-looking fields:

- `hidden`
- `internal`
- `display_name_i18n_key`
- `short_description_i18n_key`
- inline `settings_schema`

The localization keys make it possible to switch the browser UI to a translation service later without changing the registry contract.

## Supported categories

The built-in sample catalog includes the requested groups:

- `awareness`
- `timing`
- `telemetry`
- `strategy`
- `race context`
- `diagnostics`
- `coaching`

## Query / filter support

`OverlayCatalogFilter` supports:

- free-text query
- categories
- tags
- premium tiers
- availability statuses
- simulator compatibility
- favorites only
- entitled only
- include locked premium entries
- include hidden/internal entries

The registry search checks:

- overlay id
- display name
- short description
- category
- tags
- search keywords
- supported simulators
- settings schema reference
- availability status

## Declarative loading

The registry supports:

- Python registration with `register()` / `register_many()`
- declarative loading with `register_from_file(path)`

Supported file formats:

- `.json`
- `.yaml` / `.yml` when `PyYAML` is installed

Expected file shape:

```json
{
  "overlays": [
    {
      "overlay_id": "garage_awareness",
      "renderer_key": "garage_awareness",
      "display_name": "Garage Awareness",
      "short_description": "Simple sample loaded from JSON.",
      "category": "awareness",
      "tags": ["sample", "awareness"],
      "settings_schema_ref": "garage_awareness.v1",
      "supported_simulators": ["ACC", "Assetto Corsa"],
      "default_enabled": false,
      "availability_status": "beta",
      "preview_asset": "assets/overlays/garage_awareness.png",
      "default_size": [300, 120],
      "default_anchor": "bottom_left"
    }
  ]
}
```

## Recommendation: JSON / YAML vs Python registration

Recommended split:

- Python registration for built-in overlays and any overlay that needs rich inline schema, capability flags, or computed defaults.
- JSON for partner packs, experiments, remote-managed catalogs, or content that should be easily diffed and generated.
- YAML only if non-engineers will edit the catalog frequently and the extra parser dependency is acceptable.

Practical recommendation for LAP COACH:

1. Keep core first-party overlays in Python.
2. Support JSON import for partner / premium / experimental catalog packs.
3. Avoid making YAML the primary path unless you have a strong authoring requirement for it.

Why:

- Python is safer for strongly typed built-ins and avoids config drift between code and schema.
- JSON is easier to validate, ship, and generate from tools.
- YAML is friendlier to hand-edit, but it is less strict and introduces another failure surface.

## Example built-in catalog

The current built-in sample set includes more than ten overlays:

- `radar_awareness`
- `spotter_awareness`
- `session_delta`
- `sector_table`
- `track_map`
- `pedal_trace`
- `fuel_strategy`
- `pit_window`
- `standings`
- `race_control`
- `input_diagnostics`
- `live_coach`
- `engineer_debug_panel` (hidden/internal)

## Testing

The registry tests cover:

- definition shape and built-in category coverage
- settings validation and clamping
- favorites and premium metadata
- hidden/internal filtering
- declarative file registration
- legacy state migration
- service/runtime flows that consume the registry

