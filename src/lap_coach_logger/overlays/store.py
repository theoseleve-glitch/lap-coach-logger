"""Persistent store for overlay layouts, browser state, and user customization."""

from __future__ import annotations

import json
import logging
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path

from lap_coach_logger.overlays.migrations import OVERLAY_STATE_SCHEMA_VERSION, OverlayStateMigrator
from lap_coach_logger.overlays.models import (
    OverlayBrowserPreferences,
    OverlayInstance,
    OverlayLastUsedSettings,
    OverlayPreset,
    OverlayStateDocument,
    utc_now_iso,
)
from lap_coach_logger.utils.paths import config_dir

log = logging.getLogger(__name__)

OVERLAY_PERSISTENCE_SCHEMA_VERSION = 1


@dataclass(slots=True, frozen=True)
class OverlayStoreWarning:
    entity_kind: str
    entity_id: str
    message: str
    recovered_with_defaults: bool = True


@dataclass(slots=True, frozen=True)
class OverlayStoreLoadReport:
    backend: str
    schema_version: int
    storage_schema_version: int = 0
    warnings: tuple[OverlayStoreWarning, ...] = ()
    recovered_defaults: bool = False
    migrated: bool = False


class OverlayPersistenceMigrationRunner:
    """SQLite schema migration runner for local overlay persistence."""

    def migrate(self, connection: sqlite3.Connection) -> bool:
        current_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        changed = current_version != OVERLAY_PERSISTENCE_SCHEMA_VERSION
        if current_version < 1:
            self._migrate_v0_to_v1(connection)
            connection.execute(f"PRAGMA user_version = {OVERLAY_PERSISTENCE_SCHEMA_VERSION}")
        return changed

    @staticmethod
    def _migrate_v0_to_v1(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS document_state (
                singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS favorites (
                overlay_id TEXT PRIMARY KEY NOT NULL,
                updated_at_utc TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS browser_preferences (
                singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS layouts (
                layout_id TEXT PRIMARY KEY NOT NULL,
                payload_json TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS overlay_instances (
                instance_id TEXT PRIMARY KEY NOT NULL,
                layout_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_overlay_instances_layout_id
                ON overlay_instances(layout_id);

            CREATE TABLE IF NOT EXISTS last_used_settings (
                overlay_id TEXT PRIMARY KEY NOT NULL,
                payload_json TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS quarantine_records (
                quarantine_id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_kind TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                raw_payload TEXT NOT NULL,
                error TEXT NOT NULL,
                quarantined_at_utc TEXT NOT NULL
            );
            """
        )


class _OverlayStateBackend:
    def load_with_report(self) -> tuple[OverlayStateDocument, OverlayStoreLoadReport]:
        raise NotImplementedError

    def save(self, document: OverlayStateDocument) -> None:
        raise NotImplementedError


class JsonOverlayStateStoreBackend(_OverlayStateBackend):
    """Readable JSON backend retained for explicit legacy/debug use."""

    def __init__(self, path: Path, *, migrator: OverlayStateMigrator) -> None:
        self.path = path
        self._migrator = migrator

    def load_with_report(self) -> tuple[OverlayStateDocument, OverlayStoreLoadReport]:
        if not self.path.exists():
            return (
                self._migrator.default_document(),
                OverlayStoreLoadReport(
                    backend="json",
                    schema_version=OVERLAY_STATE_SCHEMA_VERSION,
                    recovered_defaults=True,
                ),
            )

        raw_text = ""
        try:
            raw_text = self.path.read_text(encoding="utf-8")
            raw_data = json.loads(raw_text)
            migrated, changed = self._migrator.migrate(raw_data)
            document = OverlayStateDocument.from_dict(migrated)
            document, normalization_warnings, normalized = _normalize_document_graph(document)
            if changed or normalized:
                self._write_backup(raw_text)
                self.save(document)
            return (
                document,
                OverlayStoreLoadReport(
                    backend="json",
                    schema_version=document.schema_version,
                    warnings=normalization_warnings,
                    migrated=changed or normalized,
                ),
            )
        except Exception as exc:
            log.exception("Failed to load overlay state from %s; rebuilding defaults", self.path)
            if raw_text:
                self._write_failure_backup(raw_text)
            warning = OverlayStoreWarning(
                entity_kind="document",
                entity_id=str(self.path),
                message=f"JSON overlay state could not be parsed: {exc}",
            )
            return (
                self._migrator.default_document(),
                OverlayStoreLoadReport(
                    backend="json",
                    schema_version=OVERLAY_STATE_SCHEMA_VERSION,
                    warnings=(warning,),
                    recovered_defaults=True,
                ),
            )

    def save(self, document: OverlayStateDocument) -> None:
        payload = document.to_dict()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=self.path.parent, prefix="overlay_", suffix=".tmp")
        try:
            with open(tmp_fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            Path(tmp_path).replace(self.path)
        except Exception:
            log.exception("Failed to save overlay state to %s", self.path)
            Path(tmp_path).unlink(missing_ok=True)
            raise

    def _write_backup(self, raw_text: str) -> None:
        backup_path = self.path.with_suffix(self.path.suffix + ".bak")
        try:
            backup_path.write_text(raw_text, encoding="utf-8")
        except Exception:
            log.warning("Could not write overlay migration backup to %s", backup_path, exc_info=True)

    def _write_failure_backup(self, raw_text: str) -> None:
        backup_path = self.path.with_suffix(self.path.suffix + ".corrupt")
        try:
            backup_path.write_text(raw_text, encoding="utf-8")
        except Exception:
            log.warning("Could not write overlay corruption backup to %s", backup_path, exc_info=True)


class SQLiteOverlayStateStoreBackend(_OverlayStateBackend):
    """Primary local persistence backend with row-level recovery and validation."""

    def __init__(
        self,
        path: Path,
        *,
        migrator: OverlayStateMigrator,
        migration_runner: OverlayPersistenceMigrationRunner | None = None,
    ) -> None:
        self.path = path
        self._migrator = migrator
        self._migration_runner = migration_runner or OverlayPersistenceMigrationRunner()

    def load_with_report(self) -> tuple[OverlayStateDocument, OverlayStoreLoadReport]:
        warnings: list[OverlayStoreWarning] = []
        migrated = False
        document: OverlayStateDocument | None = None
        persist_after_load = False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                migrated = self._migration_runner.migrate(connection)
                raw_document = self._load_raw_document(connection, warnings)
                payload, changed = self._migrator.migrate(raw_document)
                document = OverlayStateDocument.from_dict(payload)
                document, normalization_warnings, normalized = _normalize_document_graph(document)
                warnings.extend(normalization_warnings)
                persist_after_load = changed or normalized
            if document is None:
                raise RuntimeError("Overlay state document was not loaded")
            if persist_after_load:
                self.save(document)
            return (
                document,
                OverlayStoreLoadReport(
                    backend="sqlite",
                    schema_version=document.schema_version,
                    storage_schema_version=OVERLAY_PERSISTENCE_SCHEMA_VERSION,
                    warnings=tuple(warnings),
                    migrated=migrated or persist_after_load,
                ),
            )
        except Exception as exc:
            log.exception("Failed to load overlay SQLite state from %s; rebuilding defaults", self.path)
            warning = OverlayStoreWarning(
                entity_kind="document",
                entity_id=str(self.path),
                message=f"SQLite overlay state could not be loaded: {exc}",
            )
            return (
                self._migrator.default_document(),
                OverlayStoreLoadReport(
                    backend="sqlite",
                    schema_version=OVERLAY_STATE_SCHEMA_VERSION,
                    storage_schema_version=OVERLAY_PERSISTENCE_SCHEMA_VERSION,
                    warnings=tuple((*warnings, warning)),
                    recovered_defaults=True,
                    migrated=migrated,
                ),
            )

    def save(self, document: OverlayStateDocument) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            self._migration_runner.migrate(connection)
            payload = document.to_dict()
            meta_payload = {
                "schema_version": payload.get("schema_version"),
                "active_preset_id": payload.get("active_preset_id"),
                "layout_shortcuts": payload.get("layout_shortcuts"),
                "created_at_utc": payload.get("created_at_utc"),
                "updated_at_utc": payload.get("updated_at_utc"),
            }
            connection.execute(
                """
                INSERT INTO document_state (singleton_id, payload_json)
                VALUES (1, ?)
                ON CONFLICT(singleton_id) DO UPDATE SET payload_json = excluded.payload_json
                """,
                (json.dumps(meta_payload),),
            )

            connection.execute("DELETE FROM favorites")
            connection.executemany(
                "INSERT INTO favorites (overlay_id, updated_at_utc) VALUES (?, ?)",
                [(overlay_id, utc_now_iso()) for overlay_id in document.favorite_overlay_ids],
            )

            connection.execute(
                """
                INSERT INTO browser_preferences (singleton_id, payload_json)
                VALUES (1, ?)
                ON CONFLICT(singleton_id) DO UPDATE SET payload_json = excluded.payload_json
                """,
                (json.dumps(document.browser_preferences.to_dict()),),
            )

            connection.execute("DELETE FROM layouts")
            connection.executemany(
                "INSERT INTO layouts (layout_id, payload_json, updated_at_utc) VALUES (?, ?, ?)",
                [
                    (layout.layout_id, json.dumps(layout.to_dict()), layout.updated_at_utc)
                    for layout in document.presets
                ],
            )

            connection.execute("DELETE FROM overlay_instances")
            connection.executemany(
                "INSERT INTO overlay_instances (instance_id, layout_id, payload_json, updated_at_utc) VALUES (?, ?, ?, ?)",
                [
                    (instance.instance_id, instance.preset_id, json.dumps(instance.to_dict()), instance.updated_at_utc)
                    for instance in document.instances
                ],
            )

            connection.execute("DELETE FROM last_used_settings")
            connection.executemany(
                "INSERT INTO last_used_settings (overlay_id, payload_json, updated_at_utc) VALUES (?, ?, ?)",
                [
                    (record.overlay_id, json.dumps(record.to_dict()), record.updated_at_utc)
                    for record in document.last_used_settings
                ],
            )

            connection.commit()

    def _load_raw_document(
        self,
        connection: sqlite3.Connection,
        warnings: list[OverlayStoreWarning],
    ) -> dict[str, object]:
        default_document = self._migrator.default_document().to_dict()
        meta_payload = self._read_singleton_payload(
            connection,
            table="document_state",
            entity_kind="document_state",
            warnings=warnings,
        ) or {}

        browser_preferences = self._read_singleton_payload(
            connection,
            table="browser_preferences",
            entity_kind="browser_preferences",
            warnings=warnings,
        ) or OverlayBrowserPreferences().to_dict()

        favorites = [
            str(row["overlay_id"])
            for row in connection.execute("SELECT overlay_id FROM favorites ORDER BY overlay_id")
            if str(row["overlay_id"]).strip()
        ]

        presets = self._load_entity_rows(
            connection,
            table="layouts",
            id_column="layout_id",
            entity_kind="layout",
            constructor=OverlayPreset.from_dict,
            id_getter=lambda item: item.layout_id,
            warnings=warnings,
        )
        instances = self._load_entity_rows(
            connection,
            table="overlay_instances",
            id_column="instance_id",
            entity_kind="overlay_instance",
            constructor=OverlayInstance.from_dict,
            id_getter=lambda item: item.instance_id,
            warnings=warnings,
        )
        last_used_settings = self._load_entity_rows(
            connection,
            table="last_used_settings",
            id_column="overlay_id",
            entity_kind="last_used_settings",
            constructor=OverlayLastUsedSettings.from_dict,
            id_getter=lambda item: item.overlay_id,
            warnings=warnings,
        )

        return {
            "schema_version": meta_payload.get("schema_version", default_document["schema_version"]),
            "active_preset_id": meta_payload.get("active_preset_id", default_document["active_preset_id"]),
            "layout_shortcuts": meta_payload.get("layout_shortcuts", default_document["layout_shortcuts"]),
            "favorite_overlay_ids": favorites,
            "browser_preferences": browser_preferences,
            "last_used_settings": [item.to_dict() for item in last_used_settings],
            "presets": [item.to_dict() for item in presets],
            "instances": [item.to_dict() for item in instances],
            "created_at_utc": meta_payload.get("created_at_utc", default_document["created_at_utc"]),
            "updated_at_utc": meta_payload.get("updated_at_utc", default_document["updated_at_utc"]),
        }

    def _read_singleton_payload(
        self,
        connection: sqlite3.Connection,
        *,
        table: str,
        entity_kind: str,
        warnings: list[OverlayStoreWarning],
    ) -> dict[str, object] | None:
        row = connection.execute(f"SELECT payload_json FROM {table} WHERE singleton_id = 1").fetchone()
        if row is None:
            return None
        raw_payload = str(row["payload_json"] or "")
        try:
            payload = json.loads(raw_payload)
            if not isinstance(payload, dict):
                raise ValueError("Expected object payload")
            return payload
        except Exception as exc:
            warnings.append(
                OverlayStoreWarning(
                    entity_kind=entity_kind,
                    entity_id="singleton",
                    message=f"Recovered defaults because stored payload was invalid: {exc}",
                )
            )
            self._quarantine_payload(
                connection,
                table=table,
                id_column="singleton_id",
                entity_kind=entity_kind,
                entity_id="singleton",
                raw_payload=raw_payload,
                error=str(exc),
            )
            return None

    def _load_entity_rows(
        self,
        connection: sqlite3.Connection,
        *,
        table: str,
        id_column: str,
        entity_kind: str,
        constructor,
        id_getter,
        warnings: list[OverlayStoreWarning],
    ) -> list[object]:
        records: list[object] = []
        rows = connection.execute(f"SELECT {id_column}, payload_json FROM {table} ORDER BY updated_at_utc, {id_column}")
        for row in rows:
            entity_id = str(row[id_column] or "")
            raw_payload = str(row["payload_json"] or "")
            try:
                payload = json.loads(raw_payload)
                item = constructor(payload)
                if not str(id_getter(item) or "").strip():
                    raise ValueError("Entity is missing its primary identifier")
                records.append(item)
            except Exception as exc:
                warnings.append(
                    OverlayStoreWarning(
                        entity_kind=entity_kind,
                        entity_id=entity_id,
                        message=f"Skipped corrupted {entity_kind} record '{entity_id}': {exc}",
                    )
                )
                self._quarantine_payload(
                    connection,
                    table=table,
                    id_column=id_column,
                    entity_kind=entity_kind,
                    entity_id=entity_id,
                    raw_payload=raw_payload,
                    error=str(exc),
                )
        return records

    @staticmethod
    def _quarantine_payload(
        connection: sqlite3.Connection,
        *,
        table: str,
        id_column: str,
        entity_kind: str,
        entity_id: str,
        raw_payload: str,
        error: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO quarantine_records (entity_kind, entity_id, raw_payload, error, quarantined_at_utc)
            VALUES (?, ?, ?, ?, ?)
            """,
            (entity_kind, entity_id, raw_payload, error, utc_now_iso()),
        )
        if id_column == "singleton_id":
            connection.execute(f"DELETE FROM {table} WHERE singleton_id = 1")
        else:
            connection.execute(f"DELETE FROM {table} WHERE {id_column} = ?", (entity_id,))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection


class OverlayStateStore:
    """Hybrid persistence entrypoint: SQLite by default, JSON for explicit legacy/debug paths."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        migrator: OverlayStateMigrator | None = None,
        migration_runner: OverlayPersistenceMigrationRunner | None = None,
    ) -> None:
        self.path = path or (config_dir() / "overlay_state.db")
        self._migrator = migrator or OverlayStateMigrator()
        self._migration_runner = migration_runner or OverlayPersistenceMigrationRunner()
        self.last_report = OverlayStoreLoadReport(
            backend="sqlite" if self.path.suffix.lower() != ".json" else "json",
            schema_version=OVERLAY_STATE_SCHEMA_VERSION,
            storage_schema_version=OVERLAY_PERSISTENCE_SCHEMA_VERSION if self.path.suffix.lower() != ".json" else 0,
        )
        self._backend: _OverlayStateBackend = self._build_backend()

    def load(self) -> OverlayStateDocument:
        document, report = self.load_with_report()
        self.last_report = report
        return document

    def load_with_report(self) -> tuple[OverlayStateDocument, OverlayStoreLoadReport]:
        document, report = self._backend.load_with_report()
        self.last_report = report
        return document, report

    def save(self, document: OverlayStateDocument) -> None:
        self._backend.save(document)

    def _build_backend(self) -> _OverlayStateBackend:
        if self.path.suffix.lower() == ".json":
            return JsonOverlayStateStoreBackend(self.path, migrator=self._migrator)
        return SQLiteOverlayStateStoreBackend(
            self.path,
            migrator=self._migrator,
            migration_runner=self._migration_runner,
        )


def _normalize_document_graph(
    document: OverlayStateDocument,
) -> tuple[OverlayStateDocument, tuple[OverlayStoreWarning, ...], bool]:
    warnings: list[OverlayStoreWarning] = []
    changed = False

    normalized_presets: list[OverlayPreset] = []
    seen_layout_ids: set[str] = set()
    for preset in document.presets:
        layout_id = str(preset.layout_id or "").strip()
        if not layout_id:
            warnings.append(
                OverlayStoreWarning(
                    entity_kind="layout",
                    entity_id="",
                    message="Dropped layout with missing layout_id during normalization.",
                    recovered_with_defaults=False,
                )
            )
            changed = True
            continue
        if layout_id in seen_layout_ids:
            warnings.append(
                OverlayStoreWarning(
                    entity_kind="layout",
                    entity_id=layout_id,
                    message=f"Dropped duplicate layout '{layout_id}' during normalization.",
                    recovered_with_defaults=False,
                )
            )
            changed = True
            continue
        seen_layout_ids.add(layout_id)
        normalized_presets.append(preset)
    document.presets = normalized_presets

    normalized_instances: list[OverlayInstance] = []
    seen_instance_ids: set[str] = set()
    for instance in document.instances:
        instance_id = str(instance.instance_id or "").strip()
        if not instance_id:
            warnings.append(
                OverlayStoreWarning(
                    entity_kind="overlay_instance",
                    entity_id="",
                    message="Dropped overlay instance with missing instance_id during normalization.",
                    recovered_with_defaults=False,
                )
            )
            changed = True
            continue
        if instance_id in seen_instance_ids:
            warnings.append(
                OverlayStoreWarning(
                    entity_kind="overlay_instance",
                    entity_id=instance_id,
                    message=f"Dropped duplicate overlay instance '{instance_id}' during normalization.",
                    recovered_with_defaults=False,
                )
            )
            changed = True
            continue
        if not str(instance.overlay_id or "").strip():
            warnings.append(
                OverlayStoreWarning(
                    entity_kind="overlay_instance",
                    entity_id=instance_id,
                    message=f"Dropped overlay instance '{instance_id}' because overlay_id is missing.",
                    recovered_with_defaults=False,
                )
            )
            changed = True
            continue
        if not str(instance.preset_id or "").strip() or instance.preset_id not in seen_layout_ids:
            warnings.append(
                OverlayStoreWarning(
                    entity_kind="overlay_instance",
                    entity_id=instance_id,
                    message=f"Dropped overlay instance '{instance_id}' because it references an unknown layout '{instance.preset_id}'.",
                    recovered_with_defaults=False,
                )
            )
            changed = True
            continue
        seen_instance_ids.add(instance_id)
        normalized_instances.append(instance)
    document.instances = normalized_instances

    instance_ids_by_layout: dict[str, list[str]] = {}
    for instance in document.instances:
        instance_ids_by_layout.setdefault(instance.preset_id, []).append(instance.instance_id)

    for preset in document.presets:
        valid_instance_ids = instance_ids_by_layout.get(preset.layout_id, [])
        if preset.instance_ids != valid_instance_ids:
            preset.instance_ids = list(valid_instance_ids)
            changed = True
        for slot in preset.slots:
            if slot.instance_id and slot.instance_id not in seen_instance_ids:
                warnings.append(
                    OverlayStoreWarning(
                        entity_kind="layout_slot",
                        entity_id=slot.slot_id,
                        message=f"Cleared slot '{slot.slot_id}' because it referenced missing instance '{slot.instance_id}'.",
                        recovered_with_defaults=False,
                    )
                )
                slot.instance_id = ""
                changed = True

    if document.active_preset_id and document.active_preset_id not in seen_layout_ids:
        warnings.append(
            OverlayStoreWarning(
                entity_kind="document",
                entity_id="active_preset_id",
                message=f"Reset active layout because '{document.active_preset_id}' no longer exists.",
            )
        )
        document.active_preset_id = document.presets[0].layout_id if document.presets else ""
        changed = True

    normalized_shortcuts = dict(document.layout_shortcuts)
    for shortcut, layout_id in list(normalized_shortcuts.items()):
        if layout_id and layout_id not in seen_layout_ids:
            warnings.append(
                OverlayStoreWarning(
                    entity_kind="layout_shortcut",
                    entity_id=shortcut,
                    message=f"Cleared layout shortcut '{shortcut}' because '{layout_id}' no longer exists.",
                )
            )
            normalized_shortcuts[shortcut] = ""
            changed = True
    document.layout_shortcuts = normalized_shortcuts

    browser = document.browser_preferences
    if browser.selected_layout_id and browser.selected_layout_id not in seen_layout_ids:
        browser.selected_layout_id = document.active_preset_id or (document.presets[0].layout_id if document.presets else "")
        warnings.append(
            OverlayStoreWarning(
                entity_kind="browser_preferences",
                entity_id="selected_layout_id",
                message="Reset browser selected layout because the stored layout no longer exists.",
            )
        )
        changed = True

    normalized_favorites: list[str] = []
    seen_favorites: set[str] = set()
    for overlay_id in document.favorite_overlay_ids:
        normalized_id = str(overlay_id or "").strip()
        if not normalized_id or normalized_id in seen_favorites:
            changed = True
            continue
        seen_favorites.add(normalized_id)
        normalized_favorites.append(normalized_id)
    document.favorite_overlay_ids = normalized_favorites

    normalized_last_used: list[OverlayLastUsedSettings] = []
    seen_last_used: set[str] = set()
    for record in sorted(document.last_used_settings, key=lambda item: item.updated_at_utc, reverse=True):
        overlay_id = str(record.overlay_id or "").strip()
        if not overlay_id:
            warnings.append(
                OverlayStoreWarning(
                    entity_kind="last_used_settings",
                    entity_id="",
                    message="Dropped last-used settings record with missing overlay_id during normalization.",
                    recovered_with_defaults=False,
                )
            )
            changed = True
            continue
        if overlay_id in seen_last_used:
            changed = True
            continue
        seen_last_used.add(overlay_id)
        normalized_last_used.append(record)
    document.last_used_settings = list(reversed(normalized_last_used))

    return document, tuple(warnings), changed
