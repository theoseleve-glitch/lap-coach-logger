# Overlay Settings Schema Backend

This document describes the declarative overlay settings schema system in `src/lap_coach_logger/overlays/`.

## Purpose

The settings system is backend/domain infrastructure for overlay configuration.

It allows overlays to expose settings without embedding visible controls inside overlay widgets.
The UI can later generate forms automatically from schema metadata.

## Modules

- `settings_models.py`
  Typed schema, field, section, validation-rule, visibility-condition, resolution, and migration models.
- `settings_service.py`
  Schema registry, validation, default resolution, override merge, visibility evaluation, and migrations.
- `settings_examples.py`
  Example schemas for:
  - Core Driving HUD
  - Delta Widget
  - Relative Table
  - Track Map

## Field types

Supported field kinds:

- `boolean`
- `integer`
- `float`
- `enum`
- `color_token`
- `range`
- `spacing_token`
- `anchor_preset`

## Section groups

Supported standard sections:

- `performance_and_size`
- `appearance`
- `visibility`
- `behavior`
- `advanced`

## Per-field metadata

Each field can declare:

- label
- description
- default value
- min/max
- step
- category section
- premium-only flag
- advanced flag
- visibility conditions
- validation rules
- enum options
- token namespace

This is enough for a future Qt form renderer to choose controls and group them by section.

## Validation and merge flow

1. Load schema from the schema registry.
2. If a stored version is older than the current schema version, run schema migrations.
3. Merge defaults with user overrides.
4. Normalize and validate field values.
5. Apply cross-field validation rules.
6. Evaluate field visibility conditions.
7. Return a resolution object containing:
   - normalized values
   - visible field keys
   - validation/migration issues
   - schema version

## Migration strategy

Each schema has its own version.

Migrations are registered per `schema_id` and version pair. They are explicit transform functions, not hidden inside field validation.

Current example:

- `delta_widget` migrates from v1 to v2
  - `inactive_alpha` -> `inactive_opacity`
  - `show_reference_badge` -> `show_reference_chip`

This keeps schema evolution safe and testable.

## Intended Qt usage later

The Qt browser/editor can:

- request a schema by id
- render sections in order
- pick widget types from `kind`
- show premium badges from `premium_only`
- hide advanced fields by default
- dynamically hide/show dependent fields from `visibility_conditions`
- bind user edits back through `merge_overrides`

The overlay widgets themselves should not own form logic.

