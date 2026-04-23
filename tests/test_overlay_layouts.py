from __future__ import annotations

from pathlib import Path

from lap_coach_logger.overlays import (
    OverlayInstance,
    OverlayInstanceLifecycleService,
    OverlayLayoutContext,
    OverlayLayoutPresetService,
    OverlayPlacement,
    OverlayRegistry,
    OverlayStateStore,
    builtin_overlay_definitions,
    example_overlay_layout_templates,
)


def _build_layout_service(tmp_path: Path) -> tuple[OverlayLayoutPresetService, OverlayInstanceLifecycleService]:
    registry = OverlayRegistry(builtin_overlay_definitions())
    runtime = OverlayInstanceLifecycleService(registry=registry)
    service = OverlayLayoutPresetService(
        registry=registry,
        store=OverlayStateStore(path=tmp_path / "overlay_state.json"),
        runtime=runtime,
        default_layouts=example_overlay_layout_templates(),
    )
    return service, runtime


def test_layout_service_seeds_examples_and_supports_shortcut_activation(tmp_path: Path) -> None:
    service, runtime = _build_layout_service(tmp_path)

    layouts = {layout.layout_id: layout for layout in service.layouts()}
    assert {"layout-qualifying-focus", "layout-race-focus", "layout-telemetry-lab"}.issubset(layouts)
    assert service.document().active_preset_id == "layout-race-focus"

    shortcuts = service.bind_layout_shortcut("A", "layout-qualifying-focus")
    assert shortcuts["A"] == "layout-qualifying-focus"

    activated = service.activate_layout_shortcut("A")
    assert activated.layout_id == "layout-qualifying-focus"
    assert service.document().active_preset_id == "layout-qualifying-focus"
    assert {instance.layout_id for instance in runtime.list_instances()} == {"layout-qualifying-focus"}

    service.activate_layout("layout-race-focus")
    fuel_runtime = next(item for item in runtime.list_instances() if item.overlay_id == "fuel_strategy")
    assert fuel_runtime.state.entitlement_blocked is True


def test_layout_export_import_and_diff_are_stable(tmp_path: Path) -> None:
    service, _runtime = _build_layout_service(tmp_path)
    export_path = tmp_path / "telemetry_lab.layout.json"

    bundle = service.export_layout("layout-telemetry-lab", export_path)
    assert bundle.layouts[0].layout_id == "layout-telemetry-lab"
    assert export_path.exists()

    imported = service.import_layout(export_path)
    assert len(imported) == 1
    assert imported[0].layout_id != "layout-telemetry-lab"
    assert imported[0].display_name.startswith("Telemetry Lab")

    diff = service.diff_layouts("layout-telemetry-lab", imported[0].layout_id)
    assert {change.field for change in diff.metadata_changes} == {"display_name"}
    assert diff.instance_changes == ()


def test_layout_auto_apply_and_reset_to_default(tmp_path: Path) -> None:
    service, _runtime = _build_layout_service(tmp_path)

    qualifying_match = service.match_auto_apply(
        OverlayLayoutContext(simulator="ACC", car="Ferrari 296 GT3", session_type="qualifying")
    )
    assert qualifying_match is not None
    assert qualifying_match.layout_id == "layout-qualifying-focus"

    activated = service.auto_apply_for_context(
        OverlayLayoutContext(simulator="ACC", car="Ferrari 296 GT3", session_type="race"),
        apply_to_runtime=False,
    )
    assert activated is not None
    assert activated.layout_id == "layout-race-focus"

    version_before = next(layout.version for layout in service.layouts() if layout.layout_id == "layout-race-focus")
    renamed = service.rename_layout("layout-race-focus", "Race Focus Custom")
    assert renamed.display_name == "Race Focus Custom"
    assert renamed.version == version_before + 1

    reset = service.reset_layout_to_default("layout-race-focus")
    assert reset.display_name == "Race Focus"
    assert any(instance.overlay_id == "fuel_strategy" for instance in service.layout_instances("layout-race-focus"))

    telemetry_lab_debug = next(
        instance for instance in service.layout_instances("layout-telemetry-lab") if instance.overlay_id == "engineer_debug_panel"
    )
    assert telemetry_lab_debug.enabled is False


def test_layout_create_clone_and_delete_keep_instances_isolated(tmp_path: Path) -> None:
    service, _runtime = _build_layout_service(tmp_path)

    created = service.create_layout(
        display_name="Custom Sprint",
        simulator_filter=("ACC",),
        session_type_filter=("race",),
        overlay_instances=[
            OverlayInstance(
                instance_id="custom-sprint-delta",
                overlay_id="session_delta",
                preset_id="ignored-by-service",
                name="Session Delta",
                placement=OverlayPlacement(x=10, y=10, width=420, height=180),
                settings={"scale": 1.15},
            )
        ],
    )
    cloned = service.clone_layout(created.layout_id, display_name="Custom Sprint B")
    service.bind_layout_shortcut("C", created.layout_id)
    service.delete_layout(created.layout_id)

    assert cloned.display_name == "Custom Sprint B"
    assert created.layout_id not in {layout.layout_id for layout in service.layouts()}
    assert service.shortcut_bindings()["C"] == ""
    assert all(instance.preset_id != created.layout_id for instance in service.document().instances)
