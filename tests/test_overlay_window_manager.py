from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout

from lap_coach_logger.overlays import (
    OverlayDefinition,
    OverlayInstanceLifecycleService,
    OverlayLayoutHints,
    OverlayRegistry,
)
from lap_coach_logger.ui.desktop.overlay_window_manager import (
    OverlayPlaceholderController,
    OverlayWidgetFactoryRegistry,
    OverlayWindowManager,
    OverlayWindowStateCommitter,
)


def test_overlay_window_manager_mounts_updates_and_unmounts_runtime_instances() -> None:
    app = _app()
    runtime = _runtime()
    manager = OverlayWindowManager(
        runtime=runtime,
        factories=_factories(),
        show_on_screen=False,
    )

    instance = runtime.create_instance("track_map_overlay", layout_id="layout-a", visible=True)
    app.processEvents()

    assert len(manager.descriptors()) == 1
    assert manager.descriptors()[0].instance_id == instance.instance_id
    assert manager.descriptors()[0].visible is True
    assert manager.window(instance.instance_id) is not None

    runtime.hide(instance.instance_id)
    app.processEvents()
    assert manager.descriptors()[0].visible is False

    runtime.destroy(instance.instance_id)
    app.processEvents()
    assert manager.descriptors() == ()

    manager.shutdown()


def test_overlay_window_manager_pushes_live_payloads_to_renderers() -> None:
    app = _app()
    runtime = _runtime()
    factories = _factories()
    manager = OverlayWindowManager(
        runtime=runtime,
        factories=factories,
        show_on_screen=False,
    )

    instance = runtime.create_instance("track_map_overlay", layout_id="layout-a", visible=True)
    app.processEvents()

    manager.push_live_payload({"status": "Recording", "sim": "ACC", "live": {"lap_number": 4, "speed_kph": 201.5}})
    manager.flush_live_payloads()
    controller = manager.controller(instance.instance_id)

    assert isinstance(controller, _RecordingController)
    assert controller.payloads[-1]["sim"] == "ACC"
    assert controller.payloads[-1]["live"]["lap_number"] == 4

    manager.shutdown()


def test_overlay_window_manager_routes_user_actions_back_to_runtime_and_persistence() -> None:
    app = _app()
    runtime = _runtime()
    committer = _RecordingCommitter()
    manager = OverlayWindowManager(
        runtime=runtime,
        factories=_factories(),
        state_committer=committer,
        show_on_screen=False,
    )

    instance = runtime.create_instance("track_map_overlay", layout_id="layout-a", visible=True)
    app.processEvents()
    host = manager.window(instance.instance_id)
    assert host is not None

    host.placement_committed.emit(instance.instance_id, 120, 150, 480, 260, "screen-2")
    app.processEvents()
    updated = runtime.instance(instance.instance_id)
    assert updated.placement.x == 120
    assert updated.placement.y == 150
    assert updated.placement.width == 480
    assert updated.placement.height == 260
    assert updated.screen_id == "screen-2"

    host.toggle_pin()
    host.toggle_lock()
    host.toggle_click_through()
    host.request_hide()
    app.processEvents()
    updated = runtime.instance(instance.instance_id)
    assert updated.state.pinned is True
    assert updated.state.locked is True
    assert updated.state.click_through is True
    assert updated.state.visible is False
    assert committer.placement_commits >= 3
    assert committer.visibility_commits == 1
    assert committer.settings_commits == 1

    manager.shutdown()


def test_overlay_window_manager_preview_instances_are_explicit() -> None:
    app = _app()
    runtime = _runtime()
    manager = OverlayWindowManager(
        runtime=runtime,
        factories=_factories(),
        show_on_screen=False,
    )

    preview = manager.open_preview_overlay("track_map_overlay", settings={"scale": 1.2})
    app.processEvents()

    descriptor = manager.descriptors()[0]
    assert descriptor.preview_mode is True
    assert descriptor.layout_id == "preview:track_map_overlay"
    assert runtime.instance(preview.instance_id).state.preview_mode is True

    manager.close_preview_overlay(preview.instance_id)
    app.processEvents()
    assert manager.descriptors() == ()

    manager.shutdown()


def _app() -> QApplication:
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


def _runtime() -> OverlayInstanceLifecycleService:
    registry = OverlayRegistry(
        (
            OverlayDefinition(
                overlay_id="track_map_overlay",
                renderer_key="track_map_overlay",
                display_name="Track Map",
                short_description="Track map overlay.",
                category="telemetry",
                settings_schema_ref="track_map.v1",
                layout=OverlayLayoutHints(default_width=320, default_height=220),
                default_enabled=False,
            ),
        )
    )
    return OverlayInstanceLifecycleService(registry=registry)


def _factories() -> OverlayWidgetFactoryRegistry:
    return OverlayWidgetFactoryRegistry(
        fallback_factory=lambda instance: _RecordingController(instance.definition.display_name)
    )


class _RecordingController(OverlayPlaceholderController):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.payloads: list[dict[str, object]] = []
        self._extra = QLabel(title)
        layout = self.layout()
        assert isinstance(layout, QVBoxLayout)
        layout.addWidget(self._extra)

    def apply_live_payload(self, payload: dict[str, object]) -> None:
        self.payloads.append(dict(payload))
        super().apply_live_payload(payload)


@dataclass(slots=True)
class _RecordingCommitter(OverlayWindowStateCommitter):
    placement_commits: int = 0
    visibility_commits: int = 0
    settings_commits: int = 0
    last_instance_ids: list[str] = field(default_factory=list)

    def persist_placement(self, instance) -> None:  # noqa: ANN001
        self.placement_commits += 1
        self.last_instance_ids.append(instance.instance_id)

    def persist_visibility(self, instance) -> None:  # noqa: ANN001
        self.visibility_commits += 1
        self.last_instance_ids.append(instance.instance_id)

    def persist_settings(self, instance) -> None:  # noqa: ANN001
        self.settings_commits += 1
        self.last_instance_ids.append(instance.instance_id)
