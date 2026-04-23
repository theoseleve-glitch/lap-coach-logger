# Overlay Browser Frontend Architecture

## Figma Analysis

The browser UI in the Figma Make file resolves into four stable regions:

- left column: brand, category navigation, overlay catalog list, active/premium footer
- center stage: selected overlay preview with premium-locked and inactive placeholder states
- right column: selected overlay metadata, actions, schema-driven settings sections
- bottom rail: layout selector, quick layout switches, layout actions, activation CTA

The visual language is consistent across the browser and the LAP COACH brand guide:

- background surfaces: `#000000` asphalt, `#141414` concrete
- foreground text: `#F0EDE5` chalk, `#949494` steel
- accent / premium: `#C9A84C`
- success / error / warning / info: `#22C55E`, `#FF2A2A`, `#FACC15`, `#8B5CF6`
- typography roles:
  - display: `Space Grotesk`
  - body: `Inter`
  - mono / telemetry / metadata: `Space Mono`
- spacing rhythm: `4 / 6 / 8 / 12 / 16 / 20 / 24 / 32`
- glass surface behavior:
  - dark fill alpha around `0.55`
  - strong surface alpha around `0.82`
  - thin bright border around `1.5px`
  - heavy shadow blur around `32px`
  - design blur token `40px` carried as metadata for future compositor blur

## Frontend Package

Qt-specific code lives in:

- `src/lap_coach_logger/ui/desktop/overlay_browser/design_system.py`
- `src/lap_coach_logger/ui/desktop/overlay_browser/controller.py`
- `src/lap_coach_logger/ui/desktop/overlay_browser/settings_renderer.py`
- `src/lap_coach_logger/ui/desktop/overlay_browser/widgets.py`
- `src/lap_coach_logger/ui/desktop/overlay_browser/page.py`
- `src/lap_coach_logger/ui/desktop/overlay_browser/integration.py`

That split keeps the system modular:

- `design_system.py`: tokens only
- `controller.py`: Qt-friendly coordination around the overlay backend services
- `settings_renderer.py`: generic settings-schema to form renderer
- `widgets.py`: reusable browser components
- `page.py`: page assembly only
- `integration.py`: one coherent example composition from shared backend services

## Component Set

The reusable Qt component layer maps directly to the requested system:

- `GlassPanel`
- `SearchFilterBar`
- `OverlaySidebar`
- `_OverlayCatalogItemWidget` as the reusable overlay list row
- `PreviewCanvas`
- `OverlaySettingsPanel`
- `AccordionSection`
- `OverlaySettingsFormRenderer`
- `BottomActionBar`

The settings renderer is schema-driven and does not embed overlay-specific control logic into widgets.

## Backend Mapping

The page uses the backend exactly along the intended seams:

- catalog and selection: `OverlayBrowserPageService`
- overlay metadata: `OverlayRegistry`
- settings sections: `OverlayBrowserPageService` + `OverlaySettingsSchemaService`
- layout operations: `OverlayLayoutPresetService`
- preview telemetry summaries: `OverlayTelemetryBindingService`

The Qt page does not query global telemetry or mutate overlay persistence directly. All mutations go through the controller into backend services.

## Preview Strategy

The center preview stage is backend-driven:

- selected overlay detail comes from `OverlayBrowserPageService`
- premium lock / preview-only / inactive states come from entitlement and preview DTOs
- telemetry preview stats come from `OverlayTelemetryBindingService.preview_binding_for_definition()`

This keeps preview logic explicit and testable even before full renderer embedding is added.

## Recommended Next Step

The next integration step is to replace the current placeholder preview stage with a renderer-backed preview host that reuses the overlay factory/window-manager renderer contract for in-shell previews as well as floating windows.
