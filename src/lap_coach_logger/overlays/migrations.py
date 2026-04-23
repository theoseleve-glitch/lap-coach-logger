"""Schema migration helpers for overlay state persistence."""

from __future__ import annotations

from copy import deepcopy

from lap_coach_logger.overlays.models import OverlayStateDocument, utc_now_iso

OVERLAY_STATE_SCHEMA_VERSION = 4


class OverlayStateMigrator:
    """Migrates raw overlay state documents to the current schema."""

    def migrate(self, raw_data: dict[str, object] | None) -> tuple[dict[str, object], bool]:
        payload = deepcopy(raw_data or {})
        original_version = int(payload.get("schema_version") or 0)
        changed = original_version != OVERLAY_STATE_SCHEMA_VERSION

        if original_version < 1:
            payload = self._migrate_v0_to_v1(payload)
        if int(payload.get("schema_version") or 0) < 2:
            payload = self._migrate_v1_to_v2(payload)
        if int(payload.get("schema_version") or 0) < 3:
            payload = self._migrate_v2_to_v3(payload)
        if int(payload.get("schema_version") or 0) < 4:
            payload = self._migrate_v3_to_v4(payload)

        payload["schema_version"] = OVERLAY_STATE_SCHEMA_VERSION
        payload.setdefault("created_at_utc", utc_now_iso())
        payload["updated_at_utc"] = utc_now_iso()
        return payload, changed

    def default_document(self) -> OverlayStateDocument:
        raw, _ = self.migrate({})
        return OverlayStateDocument.from_dict(raw)

    @staticmethod
    def _migrate_v0_to_v1(payload: dict[str, object]) -> dict[str, object]:
        migrated = {
            "schema_version": 1,
            "active_preset_id": str(payload.get("active_layout_id") or payload.get("active_preset_id") or ""),
            "favorite_overlay_ids": list(payload.get("favorites") or payload.get("favorite_overlay_ids") or []),
            "presets": list(payload.get("layouts") or payload.get("presets") or []),
            "instances": list(payload.get("instances") or []),
            "created_at_utc": str(payload.get("created_at_utc") or utc_now_iso()),
            "updated_at_utc": str(payload.get("updated_at_utc") or utc_now_iso()),
        }
        return migrated

    @staticmethod
    def _migrate_v1_to_v2(payload: dict[str, object]) -> dict[str, object]:
        presets: list[dict[str, object]] = []
        for raw_preset in payload.get("presets", []):
            preset = dict(raw_preset) if isinstance(raw_preset, dict) else {}
            preset.setdefault("scope", {"sim": "", "car": "", "driver": ""})
            preset.setdefault("slots", [])
            preset.setdefault("instance_ids", [])
            preset.setdefault("created_at_utc", utc_now_iso())
            preset.setdefault("updated_at_utc", utc_now_iso())
            presets.append(preset)

        instances: list[dict[str, object]] = []
        for raw_instance in payload.get("instances", []):
            instance = dict(raw_instance) if isinstance(raw_instance, dict) else {}
            instance.setdefault("slot_id", "")
            placement = dict(instance.get("placement") or {})
            placement.setdefault("opacity", 1.0)
            placement.setdefault("monitor_id", "primary")
            placement.setdefault("pinned", False)
            placement.setdefault("locked", False)
            instance["placement"] = placement
            instance.setdefault("created_at_utc", utc_now_iso())
            instance.setdefault("updated_at_utc", utc_now_iso())
            instances.append(instance)

        return {
            "schema_version": 2,
            "active_preset_id": str(payload.get("active_preset_id") or ""),
            "favorite_overlay_ids": list(payload.get("favorite_overlay_ids") or []),
            "presets": presets,
            "instances": instances,
            "created_at_utc": str(payload.get("created_at_utc") or utc_now_iso()),
            "updated_at_utc": str(payload.get("updated_at_utc") or utc_now_iso()),
        }

    @staticmethod
    def _migrate_v2_to_v3(payload: dict[str, object]) -> dict[str, object]:
        presets: list[dict[str, object]] = []
        for raw_preset in payload.get("presets", []):
            preset = dict(raw_preset) if isinstance(raw_preset, dict) else {}
            scope = dict(preset.get("scope") or {})
            simulator_filter = list(preset.get("simulator_filter") or [])
            if not simulator_filter and scope.get("sim"):
                simulator_filter = [str(scope.get("sim") or "")]
            car_filter = list(preset.get("car_filter") or [])
            if not car_filter and scope.get("car"):
                car_filter = [str(scope.get("car") or "")]

            preset.setdefault("favorite", False)
            preset["simulator_filter"] = simulator_filter
            preset["car_filter"] = car_filter
            preset.setdefault("session_type_filter", [])
            preset.setdefault("tags", [])
            preset.setdefault("active", False)
            preset.setdefault("auto_apply_rules", [])
            preset.setdefault("version", 1)
            preset.setdefault("created_at", preset.get("created_at_utc") or utc_now_iso())
            preset.setdefault("last_modified", preset.get("updated_at_utc") or preset.get("created_at_utc") or utc_now_iso())
            presets.append(preset)

        layout_shortcuts = payload.get("layout_shortcuts")
        shortcut_map = dict(layout_shortcuts) if isinstance(layout_shortcuts, dict) else {}
        shortcut_map.setdefault("A", "")
        shortcut_map.setdefault("B", "")
        shortcut_map.setdefault("C", "")

        return {
            "schema_version": 3,
            "active_preset_id": str(payload.get("active_preset_id") or ""),
            "layout_shortcuts": shortcut_map,
            "favorite_overlay_ids": list(payload.get("favorite_overlay_ids") or []),
            "presets": presets,
            "instances": list(payload.get("instances") or []),
            "created_at_utc": str(payload.get("created_at_utc") or utc_now_iso()),
            "updated_at_utc": str(payload.get("updated_at_utc") or utc_now_iso()),
        }

    @staticmethod
    def _migrate_v3_to_v4(payload: dict[str, object]) -> dict[str, object]:
        browser_preferences = dict(payload.get("browser_preferences") or {})
        browser_preferences.setdefault("selected_category", "")
        browser_preferences.setdefault("selected_overlay_id", "")
        browser_preferences.setdefault("selected_layout_id", str(payload.get("active_preset_id") or ""))
        browser_preferences.setdefault("search_query", "")
        browser_preferences.setdefault("tag_filters", [])
        browser_preferences.setdefault("simulator_filters", [])
        browser_preferences.setdefault("availability_filters", [])
        browser_preferences.setdefault("status_filters", [])
        browser_preferences.setdefault("entitlement_filter", "all")
        browser_preferences.setdefault("favorites_only", False)
        browser_preferences.setdefault("include_hidden", False)
        browser_preferences.setdefault("updated_at_utc", utc_now_iso())

        return {
            "schema_version": 4,
            "active_preset_id": str(payload.get("active_preset_id") or ""),
            "layout_shortcuts": dict(payload.get("layout_shortcuts") or {"A": "", "B": "", "C": ""}),
            "favorite_overlay_ids": list(payload.get("favorite_overlay_ids") or []),
            "browser_preferences": browser_preferences,
            "last_used_settings": list(payload.get("last_used_settings") or []),
            "presets": list(payload.get("presets") or []),
            "instances": list(payload.get("instances") or []),
            "created_at_utc": str(payload.get("created_at_utc") or utc_now_iso()),
            "updated_at_utc": str(payload.get("updated_at_utc") or utc_now_iso()),
        }
