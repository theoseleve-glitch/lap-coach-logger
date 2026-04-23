# Native Frontend Architecture

## Audit Summary

- Current frontend stack is Python + PySide6 widgets.
- `DesktopService` is the central UI-facing backend seam:
  - `snapshot_changed(dict)`
  - `history_changed(list)`
  - `review_changed(dict)`
  - `log_event(dict)`
- Overlay management already has a usable DTO/service seam:
  - `OverlayBrowserPageService`
  - `OverlayBrowserPageController`
  - `OverlayBrowserPageState`
- Main structural weakness: business logic and view composition still live in the same Python runtime and most screens are widget-composed instead of model-driven native desktop views.

## Target Native Stack

- `native_frontend/`
  - C++ application shell
  - QML workstation screens
  - reusable component library
  - design tokens via QML singleton
  - process-backed backend gateway
- `src/lap_coach_logger/native_bridge/`
  - Python bridge
  - preserves existing backend/business logic
  - emits line-delimited JSON events to the native shell

## Data Flow

1. Native C++ shell starts.
2. `ProcessBackendGateway` launches `python -m lap_coach_logger.native_bridge`.
3. Python bridge boots current backend services and the overlay browser controller.
4. Python bridge emits:
   - `shell/state`
   - `screen/dashboard`
   - `screen/live`
   - `screen/logs`
   - `screen/history`
   - `screen/review`
   - `screen/overlay`
5. `ApplicationController` updates typed Qt models and QML-facing state maps.
6. QML screens bind to those models and maps.

## Migration Path

- Phase 1: native shell, components, tokens, screen layouts, mock gateway
- Phase 2: Python bridge to current business logic
- Phase 3: parity on overlay, logs, history, dashboard, live, review
- Phase 4: replace Python widget shell packaging with native packaging once Qt 6 toolchain is present
