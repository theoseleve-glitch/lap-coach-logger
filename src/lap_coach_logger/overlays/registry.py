"""Overlay catalog registry, search, and generic settings validation."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from lap_coach_logger.overlays.entitlements import (
    OverlayEntitlementContext,
    OverlayEntitlementResolver,
    StaticOverlayEntitlementResolver,
)
from lap_coach_logger.overlays.models import (
    OverlayCatalogEntry,
    OverlayCatalogFilter,
    OverlayDefinition,
    OverlaySettingField,
)

_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")


class OverlayRegistry:
    """Source of truth for built-in and plugin-provided overlay definitions."""

    def __init__(self, definitions: list[OverlayDefinition] | tuple[OverlayDefinition, ...] | None = None) -> None:
        self._definitions: dict[str, OverlayDefinition] = {}
        if definitions:
            self.register_many(definitions)

    def register(self, definition: OverlayDefinition) -> None:
        if not definition.overlay_id.strip():
            raise ValueError("overlay_id must not be empty")
        if definition.overlay_id in self._definitions:
            raise ValueError(f"Overlay '{definition.overlay_id}' is already registered")
        self._definitions[definition.overlay_id] = definition

    def register_many(self, definitions: list[OverlayDefinition] | tuple[OverlayDefinition, ...]) -> None:
        for definition in definitions:
            self.register(definition)

    def register_from_file(self, path: str | Path) -> tuple[OverlayDefinition, ...]:
        definitions = self.load_definitions_from_file(path)
        self.register_many(definitions)
        return definitions

    @staticmethod
    def load_definitions_from_file(path: str | Path) -> tuple[OverlayDefinition, ...]:
        source = Path(path)
        payload = OverlayRegistry._load_declarative_payload(source)
        if isinstance(payload, dict):
            items = payload.get("overlays", [])
        else:
            items = payload
        if not isinstance(items, list):
            raise ValueError(f"Overlay definition file must contain a list or an 'overlays' list: {source}")
        return tuple(OverlayDefinition.from_dict(item) for item in items)

    def get(self, overlay_id: str) -> OverlayDefinition:
        try:
            return self._definitions[overlay_id]
        except KeyError as exc:
            raise KeyError(f"Unknown overlay '{overlay_id}'") from exc

    def list_definitions(self) -> tuple[OverlayDefinition, ...]:
        return tuple(sorted(self._definitions.values(), key=lambda item: (item.category.lower(), item.sort_order, item.display_name.lower())))

    def categories(self) -> dict[str, tuple[OverlayDefinition, ...]]:
        grouped: dict[str, list[OverlayDefinition]] = defaultdict(list)
        for definition in self.list_definitions():
            grouped[definition.category].append(definition)
        return {category: tuple(items) for category, items in grouped.items()}

    def catalog_entries(
        self,
        *,
        filter_spec: OverlayCatalogFilter | None = None,
        favorites: set[str] | None = None,
        entitlement_resolver: OverlayEntitlementResolver | None = None,
        entitlement_context: OverlayEntitlementContext | None = None,
    ) -> tuple[OverlayCatalogEntry, ...]:
        spec = filter_spec or OverlayCatalogFilter()
        favorite_ids = favorites or set()
        resolver = entitlement_resolver or StaticOverlayEntitlementResolver()
        query_tokens = tuple(token for token in spec.query.lower().split() if token)
        category_filter = {item.lower() for item in spec.categories}
        tag_filter = {item.lower() for item in spec.tags}
        tier_filter = {item.lower() for item in spec.premium_tiers}
        status_filter = {item.lower() for item in spec.availability_statuses}
        simulator_filter = {item.lower() for item in spec.simulators}

        entries: list[OverlayCatalogEntry] = []
        for definition in self.list_definitions():
            if category_filter and definition.category.lower() not in category_filter:
                continue
            if tier_filter and definition.premium_tier.lower() not in tier_filter:
                continue
            if status_filter and definition.availability_status.lower() not in status_filter:
                continue
            if definition.hidden and not spec.include_hidden:
                continue
            tag_values = {tag.lower() for tag in definition.tags}
            if tag_filter and not tag_filter.issubset(tag_values):
                continue
            simulator_values = {sim.lower() for sim in definition.supported_simulators}
            if simulator_filter and simulator_values.isdisjoint(simulator_filter):
                continue
            search_text = self._search_text(definition)
            if query_tokens and any(token not in search_text for token in query_tokens):
                continue

            entitlement = resolver.evaluate(definition, context=entitlement_context)
            if not entitlement.visible_in_catalog:
                continue
            if spec.favorites_only and definition.overlay_id not in favorite_ids:
                continue
            if spec.entitled_only and not entitlement.can_activate:
                continue
            if not spec.include_locked and not entitlement.can_activate:
                continue

            sections = tuple(dict.fromkeys(field.section for field in definition.settings_schema))
            entries.append(
                OverlayCatalogEntry(
                    overlay_id=definition.overlay_id,
                    display_name=definition.display_name,
                    short_description=definition.short_description,
                    category=definition.category,
                    tags=definition.tags,
                    settings_schema_ref=definition.settings_schema_ref,
                    preview_asset=definition.preview_asset,
                    favorite=definition.overlay_id in favorite_ids,
                    premium_tier=definition.premium_tier,
                    availability_status=definition.availability_status,
                    hidden=definition.hidden,
                    entitled=entitlement.entitled,
                    entitlement_reason=entitlement.reason,
                    preview_supported=definition.capabilities.preview_supported,
                    supported_simulators=definition.supported_simulators,
                    default_enabled=definition.default_enabled,
                    settings_sections=sections,
                    access_state=entitlement.access_state,
                    can_activate=entitlement.can_activate,
                    can_preview=entitlement.can_preview,
                    can_view_settings=entitlement.can_view_settings,
                    upsell_message=entitlement.upsell_message,
                    access_badge=entitlement.access_badge,
                )
            )
        return tuple(entries)

    def default_settings(self, overlay_id: str) -> dict[str, object]:
        return dict(self.get(overlay_id).default_settings())

    def validate_settings(
        self,
        overlay_id: str,
        values: dict[str, object] | None,
        *,
        include_defaults: bool = True,
    ) -> tuple[dict[str, object], list[str]]:
        definition = self.get(overlay_id)
        incoming = dict(values or {})
        issues: list[str] = []
        normalized = definition.default_settings() if include_defaults else {}

        for field in definition.settings_schema:
            raw_value = incoming.pop(field.key, field.default if include_defaults else None)
            if raw_value is None and not include_defaults:
                continue
            normalized[field.key], field_issues = self._coerce_field(field, raw_value)
            issues.extend(field_issues)

        for key in sorted(incoming):
            issues.append(f"Unknown setting key ignored: {key}")
        return normalized, issues

    @staticmethod
    def _search_text(definition: OverlayDefinition) -> str:
        return " ".join(
            [
                definition.overlay_id,
                definition.display_name,
                definition.short_description,
                definition.category,
                *definition.tags,
                *definition.search_keywords,
                *definition.supported_simulators,
                definition.settings_schema_ref,
                definition.availability_status,
            ]
        ).lower()

    @staticmethod
    def _load_declarative_payload(path: Path) -> object:
        raw_text = path.read_text(encoding="utf-8")
        suffix = path.suffix.lower()
        if suffix == ".json":
            return json.loads(raw_text)
        if suffix in {".yaml", ".yml"}:
            try:
                import yaml  # type: ignore
            except Exception as exc:  # pragma: no cover - optional dependency path
                raise RuntimeError("YAML overlay files require PyYAML to be installed") from exc
            return yaml.safe_load(raw_text)
        raise ValueError(f"Unsupported overlay definition file type: {path.suffix}")

    def _coerce_field(self, field: OverlaySettingField, raw_value: object) -> tuple[object, list[str]]:
        issues: list[str] = []

        if field.kind == "bool":
            value, issue = self._coerce_bool(raw_value, field.default)
            if issue:
                issues.append(f"{field.key}: {issue}")
            return value, issues

        if field.kind == "int":
            value, issue = self._coerce_int(raw_value, field.default)
            if issue:
                issues.append(f"{field.key}: {issue}")
            value, clamp_issues = self._apply_numeric_limits(field, value)
            issues.extend(f"{field.key}: {issue}" for issue in clamp_issues)
            return value, issues

        if field.kind == "float":
            value, issue = self._coerce_float(raw_value, field.default)
            if issue:
                issues.append(f"{field.key}: {issue}")
            value, clamp_issues = self._apply_numeric_limits(field, value)
            issues.extend(f"{field.key}: {issue}" for issue in clamp_issues)
            return value, issues

        if field.kind == "enum":
            allowed = {option.value for option in field.options}
            value = str(raw_value)
            if allowed and value not in allowed:
                issues.append(f"{field.key}: value '{value}' is invalid; default restored")
                return field.default, issues
            return value, issues

        if field.kind == "color":
            value = str(raw_value)
            if not _COLOR_RE.match(value):
                issues.append(f"{field.key}: color must be #RRGGBB or #RRGGBBAA; default restored")
                return field.default, issues
            return value, issues

        return str(raw_value), issues

    @staticmethod
    def _coerce_bool(raw_value: object, default: object) -> tuple[bool, str]:
        if isinstance(raw_value, bool):
            return raw_value, ""
        if isinstance(raw_value, str):
            lowered = raw_value.strip().lower()
            if lowered in {"1", "true", "yes", "on"}:
                return True, ""
            if lowered in {"0", "false", "no", "off"}:
                return False, ""
        return bool(default), "expected boolean; default restored"

    @staticmethod
    def _coerce_int(raw_value: object, default: object) -> tuple[int, str]:
        if isinstance(raw_value, bool):
            return int(default or 0), "expected int; default restored"
        try:
            return int(raw_value), ""
        except Exception:
            return int(default or 0), "expected int; default restored"

    @staticmethod
    def _coerce_float(raw_value: object, default: object) -> tuple[float, str]:
        if isinstance(raw_value, bool):
            return float(default or 0.0), "expected float; default restored"
        try:
            return float(raw_value), ""
        except Exception:
            return float(default or 0.0), "expected float; default restored"

    @staticmethod
    def _apply_numeric_limits(field: OverlaySettingField, value: int | float) -> tuple[int | float, list[str]]:
        issues: list[str] = []
        if field.min_value is not None and value < field.min_value:
            value = type(value)(field.min_value)
            issues.append(f"clamped to minimum {field.min_value}")
        if field.max_value is not None and value > field.max_value:
            value = type(value)(field.max_value)
            issues.append(f"clamped to maximum {field.max_value}")
        return value, issues
