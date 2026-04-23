# Overlay Telemetry Bindings

## Purpose

Overlays should not query global telemetry state directly.

Instead:

- each overlay is assigned a telemetry contract
- the contract declares the required and optional signals
- a binding service resolves those signals from the shared runtime snapshot
- the service returns values plus field-by-field health

## Core Types

Implemented in [telemetry_bindings.py](/C:/Users/Admin/Documents/Telemetry/datalogger/src/lap_coach_logger/overlays/telemetry_bindings.py):

- `OverlayTelemetryRequirement`
- `OverlayTelemetryContract`
- `OverlayTelemetryContractRegistry`
- `OverlayTelemetryBindingService`
- `OverlayTelemetryFieldHealth`
- `OverlayTelemetryHealth`
- `OverlayTelemetryBindingResult`
- `OverlayTelemetryPreviewProvider`

## Resolution Model

Contracts resolve by overlay identity aliases.

Typical candidates are:

- explicit contract id
- overlay id
- renderer key
- settings schema base name
- `_overlay` suffix removed

This lets the backend map:

- `session_delta` -> `delta_widget`
- `standings` -> `relative_table`
- `track_map_overlay` -> `track_map`

## Health Rules

Per-field status:

- `ok`
- `missing`
- `stale`
- `invalid`
- `defaulted`
- `preview`

Overall health:

- `healthy`
- `degraded`
- `missing`
- `stale`
- `invalid`
- `preview`

Invalid values are not passed through blindly. If no explicit fallback exists, the bound value becomes `None`.

## Preview

Preview mode uses a mock snapshot generator, not ad-hoc widget-local fake data.

That keeps preview behavior:

- deterministic
- contract-driven
- testable
- reusable across browser previews and floating windows

## Example Contracts

Included examples:

- `core_driving_hud`
- `delta_widget`
- `relative_table`
- `track_map`

These are exposed through [telemetry_bindings.py](/C:/Users/Admin/Documents/Telemetry/datalogger/src/lap_coach_logger/overlays/telemetry_bindings.py) and `build_example_overlay_telemetry_binding_service()`.
