# Overlay Backend Integration — 8-Phase Plan

**Goal:** Wire all overlay widgets to production-grade backend data using existing live processing modules.

**Architecture:** LiveTelemetryProcessor composes all existing trackers into a single pipeline. OverlayViewModel calls processor each update cycle, exposes results as flat QML properties.

**Phases:** 8 phases, ordered by dependency. See spec for full details.

- Phase 1: Snapshot + Lap Progress (foundation)
- Phase 2: Live Lap Delta
- Phase 3: Sector Time Tracking
- Phase 4: Lockup/Wheelspin Detection
- Phase 5: Input Smoothness
- Phase 6: Coaching Alerts Pipeline
- Phase 7: Enhanced Fuel Strategy
- Phase 8: Corner Analysis Data
