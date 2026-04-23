# Overlay Runtime Instance Lifecycle

This document describes the runtime overlay instance backend implemented in `src/lap_coach_logger/overlays/runtime_instances.py`.

## Purpose

The runtime layer represents each live overlay on screen separately from:

- the overlay catalog definition
- persisted layout and user preference records

This keeps the runtime Qt-friendly while avoiding Qt dependence in the backend.

## Runtime models

The lifecycle backend exposes:

- `OverlayInstanceState`
  Runtime booleans and lifecycle flags:
  - visible
  - pinned
  - locked
  - click-through
  - active
  - preview mode
  - entitlement blocked
  - lifecycle status
  - error

- `OverlayRuntimeMetrics`
  Runtime counters and timestamps:
  - created / updated / shown / hidden / destroyed timestamps
  - move count
  - resize count
  - settings update count
  - show / hide counts
  - transition count

- `OverlayRuntimeInstance`
  Live runtime object:
  - instance id
  - overlay id
  - layout id
  - screen id
  - placement
  - state
  - metrics
  - layout overrides
  - instance overrides
  - effective settings

## Separation of concerns

- `OverlayDefinition`
  Immutable catalog metadata
- persisted `OverlayInstance`
  Durable layout preference record used by the overlay store
- `OverlayRuntimeInstance`
  Ephemeral live object used while overlays are mounted on screen

The runtime service can restore from or export to the persisted `OverlayInstance` model, but the live state is separate.

## Lifecycle service

`OverlayInstanceLifecycleService` owns:

- create instance
- show / hide
- move / resize
- update settings
- lock / unlock
- pin / unpin
- click-through updates
- enter / exit preview mode
- destroy
- serialize state
- restore state
- export to persisted overlay record
- restore from persisted overlay record

## State transition rules

- create:
  - entitlement-blocked instances start in `blocked`
  - preview instances start in `preview`
  - otherwise they start in `visible` or `hidden`
- show:
  - blocked instances cannot be shown
  - destroyed instances cannot transition
- hide:
  - sets visible false and active false
- move / resize:
  - locked instances reject mutation
- preview:
  - entering preview forces visible and active
  - exiting preview returns to `visible`, `hidden`, or `blocked`
- destroy:
  - marks the instance destroyed and removes it from the live set
  - destroyed snapshots remain serializable / inspectable

## Effective settings

Effective settings are recomputed from:

1. schema defaults
2. layout overrides
3. instance overrides

When a settings schema service is available, merge and validation go through that service.
Otherwise the lifecycle service falls back to the overlay definition defaults.

## Persistence hooks

The lifecycle service supports two persistence paths:

- `serialize_state()`
  Full runtime snapshot for crash recovery or debugging
- `to_persisted_instance()`
  Durable record containing only placement and instance overrides

This allows the runtime to be restored without making runtime metrics part of the user preference store.

## Event model

`OverlayInstanceEventBus` publishes backend events such as:

- `created`
- `shown`
- `hidden`
- `moved`
- `resized`
- `settings_updated`
- `locked`
- `unlocked`
- `pinned`
- `unpinned`
- `click_through_updated`
- `preview_entered`
- `preview_exited`
- `destroyed`
- `restored`

The Qt layer can subscribe once and map these events into window operations.

## Intended usage

The Qt adapter should:

1. query the overlay registry for a definition
2. create or restore runtime instances through the lifecycle service
3. subscribe to runtime events
4. map each runtime instance to a concrete window/widget
5. serialize or export persisted records when needed

This keeps window logic out of the domain layer while still giving Qt a stable, explicit backend contract.

