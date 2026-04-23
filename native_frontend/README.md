# LAP COACH Native Frontend

This directory contains the in-progress native frontend rewrite for LAP COACH.

## Stack

- C++
- Qt 6
- QML
- JSON bridge to the existing Python business logic

## Status

The native frontend is implemented as a standalone desktop shell with:

- reusable QML design-system components
- pane-based workstation screens
- a C++ application controller
- a process-backed gateway for the Python backend bridge
- a mock gateway fallback for design and UI iteration

The repository environment used by Codex did not include a Qt 6 C++ SDK, so this
source tree is build-ready but was not compiled here.

## Build

### Windows

1. Install Qt 6.5+ with `Core`, `Gui`, `Qml`, `Quick`, and `QuickControls2`.
2. Open a Visual Studio developer shell.
3. Set `Qt6_DIR` to your Qt 6 CMake package location.
4. Run:

```bat
build_native_frontend.bat
```

### Backend bridge

By default the native shell launches:

```text
python -m lap_coach_logger.native_bridge
```

Override that with:

- `LAP_COACH_NATIVE_BACKEND_PROGRAM`
- `LAP_COACH_NATIVE_BACKEND_ARGS`

### Mock mode

Set:

```text
LAP_COACH_NATIVE_USE_MOCK=1
```

to run the native UI without the backend bridge.
