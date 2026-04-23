# Overlay Qt Integration

## Architecture

Keep the overlay platform split into three layers:

1. Domain/backend

- catalog and definitions
- settings schemas
- layout presets
- runtime instance lifecycle
- persistence

2. Qt adapter layer

- renderer factory registry
- floating host window chrome
- runtime-event bridge into Qt signals
- window manager
- optional persistence write-back hook

3. App shell

- main window pages
- overlay browser/settings page
- tray behavior
- telemetry snapshot producer

The Qt adapter layer should depend on the backend. The backend must not depend on `QWidget`.

## Main Types

Implemented in [overlay_window_manager.py](/C:/Users/Admin/Documents/Telemetry/datalogger/src/lap_coach_logger/ui/desktop/overlay_window_manager.py):

- `OverlayWindowManager`
- `OverlayWidgetFactoryRegistry`
- `OverlayWidgetController`
- `OverlayWindowHost`
- `OverlayLayoutStateCommitter`
- `OverlayWindowDescriptor`
- `OverlayWindowManagerEvent`

## Event Flow

1. Backend runtime creates or restores an `OverlayRuntimeInstance`
2. `OverlayInstanceLifecycleService` publishes an `OverlayInstanceEvent`
3. `OverlayWindowManager` receives it through a Qt relay signal
4. The manager mounts or updates an `OverlayWindowHost`
5. The host applies geometry, visibility, flags, and renderer state
6. User drag/resize/pin/lock/hide actions emit host signals
7. The manager updates the backend runtime service
8. Optional persistence hooks write the resulting state back into layout persistence

This avoids direct widget mutation from backend code and avoids backend services reaching into Qt objects.

## Threading Rules

- All `QWidget` creation, mutation, and destruction stay on the GUI thread.
- Backend runtime events may originate elsewhere, but they must cross into Qt through signals.
- High-rate telemetry data should be coalesced. Do not push every sample directly into every window.
- `OverlayWindowManager` uses a timer-driven flush model via `push_live_payload(...)` plus `flush_live_payloads()`.
- Heavy telemetry processing stays outside the Qt window manager.

## Preview vs Live

- Live overlays are mounted from persisted/runtime instances.
- Preview overlays are explicit preview-mode runtime instances.
- The same renderer contract is used for both.
- Preview should be a mode flag, not a second windowing codepath.

## Recommended Main-Window Wiring

Minimal wiring:

```python
runtime = OverlayInstanceLifecycleService(registry=registry, settings_service=settings_service)
layout_service = OverlayLayoutPresetService(
    registry=registry,
    store=store,
    runtime=runtime,
)
manager = OverlayWindowManager(
    runtime=runtime,
    state_committer=OverlayLayoutStateCommitter(layout_service),
)

desktop_service.snapshot_changed.connect(manager.push_live_payload)
```

The browser page should talk to layout/browser services. It should not own `QWidget` overlay windows directly.

## Testing Strategy

Test the Qt adapter with small fake renderers and a real `QApplication`:

- runtime event creates a window binding
- runtime hide/show updates the host
- runtime destroy unmounts the window safely
- user placement commits update runtime state
- persistence hook receives geometry and visibility commits
- preview windows are distinct and removable
- live payload fan-out reaches renderer controllers

Focused examples are in [test_overlay_window_manager.py](/C:/Users/Admin/Documents/Telemetry/datalogger/tests/test_overlay_window_manager.py).
