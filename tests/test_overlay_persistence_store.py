from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from lap_coach_logger.overlays import (
    OVERLAY_PERSISTENCE_SCHEMA_VERSION,
    OVERLAY_STATE_SCHEMA_VERSION,
    OverlayBrowserPreferences,
    OverlayInstance,
    OverlayLastUsedSettings,
    OverlayPlacement,
    OverlayPreset,
    OverlayStateDocument,
    OverlayStateStore,
)
from lap_coach_logger.overlays.models import utc_now_iso


def _sample_document() -> OverlayStateDocument:
    return OverlayStateDocument(
        schema_version=OVERLAY_STATE_SCHEMA_VERSION,
        active_preset_id="layout-race",
        layout_shortcuts={"A": "layout-race", "B": "", "C": ""},
        favorite_overlay_ids=["track_map"],
        browser_preferences=OverlayBrowserPreferences(
            selected_category="telemetry",
            selected_overlay_id="track_map",
            selected_layout_id="layout-race",
            search_query="track",
            favorites_only=True,
        ),
        last_used_settings=[
            OverlayLastUsedSettings(
                overlay_id="track_map",
                settings_schema_ref="track_map.v2",
                settings_schema_version=2,
                values={"scale": 1.15, "opacity": 0.9},
            )
        ],
        presets=[
            OverlayPreset(
                preset_id="layout-race",
                name="Race Focus",
                instance_ids=["track-map-1"],
            )
        ],
        instances=[
            OverlayInstance(
                instance_id="track-map-1",
                overlay_id="track_map",
                preset_id="layout-race",
                name="Track Map",
                placement=OverlayPlacement(
                    x=40,
                    y=60,
                    width=320,
                    height=320,
                    pinned=True,
                    locked=True,
                ),
                settings={"scale": 1.15, "opacity": 0.9},
            )
        ],
    )


def test_sqlite_overlay_state_store_round_trips_document_and_reports_versions(tmp_path: Path) -> None:
    path = tmp_path / "overlay_state.db"
    store = OverlayStateStore(path=path)
    store.save(_sample_document())

    document, report = store.load_with_report()

    assert path.exists()
    assert report.backend == "sqlite"
    assert report.schema_version == OVERLAY_STATE_SCHEMA_VERSION
    assert report.storage_schema_version == OVERLAY_PERSISTENCE_SCHEMA_VERSION
    assert report.warnings == ()
    assert document.active_preset_id == "layout-race"
    assert document.browser_preferences.selected_overlay_id == "track_map"
    assert document.last_used_settings[0].settings_schema_ref == "track_map.v2"
    assert document.instances[0].placement.pinned is True
    assert document.instances[0].placement.locked is True
    with sqlite3.connect(path) as connection:
        assert int(connection.execute("PRAGMA user_version").fetchone()[0]) == OVERLAY_PERSISTENCE_SCHEMA_VERSION


def test_sqlite_overlay_state_store_quarantines_corrupted_rows_and_recovers_partially(tmp_path: Path) -> None:
    path = tmp_path / "overlay_state.db"
    store = OverlayStateStore(path=path)
    store.save(_sample_document())

    orphan_payload = json.dumps(
        {
            "instance_id": "orphan-instance",
            "overlay_id": "track_map",
            "preset_id": "layout-missing",
            "name": "Orphan Track Map",
            "placement": {"x": 0, "y": 0, "width": 250, "height": 250},
            "settings": {"scale": 1.0},
        }
    )
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO layouts (layout_id, payload_json, updated_at_utc) VALUES (?, ?, ?)",
            ("layout-corrupt", "{not-json", utc_now_iso()),
        )
        connection.execute(
            "INSERT INTO last_used_settings (overlay_id, payload_json, updated_at_utc) VALUES (?, ?, ?)",
            ("session_delta", "{still-not-json", utc_now_iso()),
        )
        connection.execute(
            "INSERT INTO overlay_instances (instance_id, layout_id, payload_json, updated_at_utc) VALUES (?, ?, ?, ?)",
            ("orphan-instance", "layout-missing", orphan_payload, utc_now_iso()),
        )
        connection.commit()

    document, report = store.load_with_report()

    assert document.presets[0].layout_id == "layout-race"
    assert {record.overlay_id for record in document.last_used_settings} == {"track_map"}
    assert {instance.instance_id for instance in document.instances} == {"track-map-1"}
    assert report.migrated is True
    assert any(warning.entity_kind == "layout" and warning.entity_id == "layout-corrupt" for warning in report.warnings)
    assert any(warning.entity_kind == "last_used_settings" and warning.entity_id == "session_delta" for warning in report.warnings)
    assert any(warning.entity_kind == "overlay_instance" and warning.entity_id == "orphan-instance" for warning in report.warnings)
    with sqlite3.connect(path) as connection:
        quarantined = {
            (str(row[0]), str(row[1]))
            for row in connection.execute(
                "SELECT entity_kind, entity_id FROM quarantine_records ORDER BY quarantine_id"
            )
        }
    assert ("layout", "layout-corrupt") in quarantined
    assert ("last_used_settings", "session_delta") in quarantined


def test_json_overlay_state_store_recovers_from_corrupt_document_with_backup(tmp_path: Path) -> None:
    path = tmp_path / "overlay_state.json"
    path.write_text("{ this is not valid json", encoding="utf-8")

    document, report = OverlayStateStore(path=path).load_with_report()

    assert document.schema_version == OVERLAY_STATE_SCHEMA_VERSION
    assert report.backend == "json"
    assert report.recovered_defaults is True
    assert report.warnings
    assert path.with_suffix(".json.corrupt").exists()
