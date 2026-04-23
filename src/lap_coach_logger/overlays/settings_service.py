"""Validation, default resolution, override merge, and migration for overlay settings schemas."""

from __future__ import annotations

from collections.abc import Callable

from lap_coach_logger.overlays.settings_models import (
    OverlaySettingsField,
    OverlaySettingsFieldKind,
    OverlaySettingsMigration,
    OverlaySettingsResolution,
    OverlaySettingsSchema,
    OverlaySettingsValidationIssue,
    STANDARD_ANCHOR_PRESETS,
    STANDARD_SPACING_TOKENS,
)


class OverlaySettingsSchemaRegistry:
    """Registry for declarative overlay settings schemas."""

    def __init__(self, schemas: list[OverlaySettingsSchema] | tuple[OverlaySettingsSchema, ...] | None = None) -> None:
        self._schemas: dict[str, OverlaySettingsSchema] = {}
        if schemas:
            self.register_many(schemas)

    def register(self, schema: OverlaySettingsSchema) -> None:
        if not schema.schema_id.strip():
            raise ValueError("schema_id must not be empty")
        if schema.schema_id in self._schemas:
            raise ValueError(f"Overlay settings schema '{schema.schema_id}' is already registered")
        self._schemas[schema.schema_id] = schema

    def register_many(self, schemas: list[OverlaySettingsSchema] | tuple[OverlaySettingsSchema, ...]) -> None:
        for schema in schemas:
            self.register(schema)

    def get(self, schema_id: str) -> OverlaySettingsSchema:
        try:
            return self._schemas[schema_id]
        except KeyError as exc:
            raise KeyError(f"Unknown overlay settings schema '{schema_id}'") from exc

    def list_schemas(self) -> tuple[OverlaySettingsSchema, ...]:
        return tuple(sorted(self._schemas.values(), key=lambda item: (item.overlay_key.lower(), item.title.lower())))


class OverlaySettingsSchemaMigrator:
    """Per-schema migration chain for persisted override payloads."""

    def __init__(self) -> None:
        self._migrations: dict[tuple[str, int], OverlaySettingsMigration] = {}

    def register(
        self,
        schema_id: str,
        from_version: int,
        to_version: int,
        transform: Callable[[dict[str, object]], dict[str, object]],
        *,
        description: str = "",
    ) -> None:
        if to_version <= from_version:
            raise ValueError("to_version must be greater than from_version")
        key = (schema_id, from_version)
        if key in self._migrations:
            raise ValueError(f"Migration already registered for '{schema_id}' from v{from_version}")
        self._migrations[key] = OverlaySettingsMigration(
            schema_id=schema_id,
            from_version=from_version,
            to_version=to_version,
            transform=transform,
            description=description,
        )

    def migrate(
        self,
        schema_id: str,
        values: dict[str, object] | None,
        *,
        from_version: int,
        to_version: int,
    ) -> tuple[dict[str, object], tuple[OverlaySettingsValidationIssue, ...]]:
        current_version = from_version
        payload = dict(values or {})
        issues: list[OverlaySettingsValidationIssue] = []

        if current_version > to_version:
            issues.append(
                OverlaySettingsValidationIssue(
                    field_key="",
                    code="schema_version_newer_than_runtime",
                    message=f"Stored settings version {current_version} is newer than supported version {to_version}.",
                )
            )
            return payload, tuple(issues)

        while current_version < to_version:
            migration = self._migrations.get((schema_id, current_version))
            if migration is None:
                issues.append(
                    OverlaySettingsValidationIssue(
                        field_key="",
                        code="missing_migration",
                        message=f"Missing migration for '{schema_id}' from version {current_version} to {to_version}.",
                    )
                )
                break
            payload = dict(migration.transform(dict(payload)))
            current_version = migration.to_version
            issues.append(
                OverlaySettingsValidationIssue(
                    field_key="",
                    code="migration_applied",
                    message=migration.description or f"Migrated '{schema_id}' to version {current_version}.",
                    severity="warning",
                )
            )

        return payload, tuple(issues)


class OverlaySettingsSchemaService:
    """Backend service for default resolution, validation, merge, and visibility checks."""

    def __init__(
        self,
        *,
        registry: OverlaySettingsSchemaRegistry,
        migrator: OverlaySettingsSchemaMigrator | None = None,
    ) -> None:
        self._registry = registry
        self._migrator = migrator or OverlaySettingsSchemaMigrator()

    def schema(self, schema_id: str) -> OverlaySettingsSchema:
        return self._registry.get(schema_id)

    def default_values(self, schema_id: str) -> dict[str, object]:
        return dict(self.schema(schema_id).default_values())

    def validate(
        self,
        schema_id: str,
        values: dict[str, object] | None,
    ) -> tuple[dict[str, object], tuple[OverlaySettingsValidationIssue, ...]]:
        schema = self.schema(schema_id)
        incoming = dict(values or {})
        normalized: dict[str, object] = {}
        issues: list[OverlaySettingsValidationIssue] = []

        for field in schema.fields:
            raw_value = incoming.pop(field.field_key, field.default_value)
            normalized[field.field_key], field_issues = self._normalize_field(field, raw_value)
            issues.extend(field_issues)

        for key in sorted(incoming):
            issues.append(
                OverlaySettingsValidationIssue(
                    field_key=key,
                    code="unknown_field",
                    message=f"Unknown setting '{key}' ignored.",
                    severity="warning",
                )
            )

        for field in schema.fields:
            issues.extend(self._apply_rules(field, normalized))

        return normalized, tuple(issues)

    def visible_fields(
        self,
        schema_id: str,
        values: dict[str, object] | None,
    ) -> tuple[OverlaySettingsField, ...]:
        schema = self.schema(schema_id)
        normalized, _issues = self.validate(schema_id, values)
        visible = [
            field
            for field in schema.fields
            if self._field_visible(field, normalized)
        ]
        return tuple(visible)

    def merge_overrides(
        self,
        schema_id: str,
        overrides: dict[str, object] | None,
        *,
        source_version: int | None = None,
    ) -> OverlaySettingsResolution:
        schema = self.schema(schema_id)
        migrated_from_version: int | None = None
        migration_issues: tuple[OverlaySettingsValidationIssue, ...] = ()
        incoming = dict(overrides or {})

        if source_version is not None and source_version != schema.version:
            migrated_from_version = source_version
            incoming, migration_issues = self._migrator.migrate(
                schema_id,
                incoming,
                from_version=source_version,
                to_version=schema.version,
            )

        merged = schema.default_values()
        merged.update(incoming)
        normalized, issues = self.validate(schema_id, merged)
        visible_keys = tuple(field.field_key for field in self.visible_fields(schema_id, normalized))
        return OverlaySettingsResolution(
            schema_id=schema.schema_id,
            schema_version=schema.version,
            values=normalized,
            visible_field_keys=visible_keys,
            issues=tuple((*migration_issues, *issues)),
            migrated_from_version=migrated_from_version,
        )

    def _normalize_field(
        self,
        field: OverlaySettingsField,
        raw_value: object,
    ) -> tuple[object, list[OverlaySettingsValidationIssue]]:
        if field.kind == "boolean":
            return self._normalize_boolean(field, raw_value)
        if field.kind == "integer":
            return self._normalize_integer(field, raw_value)
        if field.kind == "float":
            return self._normalize_float(field, raw_value)
        if field.kind == "enum":
            return self._normalize_enum(field, raw_value)
        if field.kind == "color_token":
            return self._normalize_color_token(field, raw_value)
        if field.kind == "range":
            return self._normalize_range(field, raw_value)
        if field.kind == "spacing_token":
            return self._normalize_spacing_token(field, raw_value)
        if field.kind == "anchor_preset":
            return self._normalize_anchor_preset(field, raw_value)
        return raw_value, []

    def _normalize_boolean(
        self,
        field: OverlaySettingsField,
        raw_value: object,
    ) -> tuple[bool, list[OverlaySettingsValidationIssue]]:
        if isinstance(raw_value, bool):
            return raw_value, []
        if isinstance(raw_value, str):
            lowered = raw_value.strip().lower()
            if lowered in {"1", "true", "yes", "on"}:
                return True, []
            if lowered in {"0", "false", "no", "off"}:
                return False, []
        return bool(field.default_value), [self._issue(field.field_key, "invalid_boolean", "Expected boolean; default restored.")]

    def _normalize_integer(
        self,
        field: OverlaySettingsField,
        raw_value: object,
    ) -> tuple[int, list[OverlaySettingsValidationIssue]]:
        try:
            value = int(raw_value)
        except Exception:
            return int(field.default_value), [self._issue(field.field_key, "invalid_integer", "Expected integer; default restored.")]
        return self._apply_numeric_limits(field, value)

    def _normalize_float(
        self,
        field: OverlaySettingsField,
        raw_value: object,
    ) -> tuple[float, list[OverlaySettingsValidationIssue]]:
        try:
            value = float(raw_value)
        except Exception:
            return float(field.default_value), [self._issue(field.field_key, "invalid_float", "Expected float; default restored.")]
        normalized, issues = self._apply_numeric_limits(field, value)
        return float(normalized), issues

    def _normalize_enum(
        self,
        field: OverlaySettingsField,
        raw_value: object,
    ) -> tuple[str, list[OverlaySettingsValidationIssue]]:
        value = str(raw_value)
        allowed = {option.value for option in field.options}
        if allowed and value not in allowed:
            return str(field.default_value), [self._issue(field.field_key, "invalid_enum", f"Value '{value}' is not allowed; default restored.")]
        return value, []

    def _normalize_color_token(
        self,
        field: OverlaySettingsField,
        raw_value: object,
    ) -> tuple[str, list[OverlaySettingsValidationIssue]]:
        value = str(raw_value).strip()
        allowed = {option.value for option in field.options}
        if allowed and value not in allowed:
            return str(field.default_value), [self._issue(field.field_key, "invalid_color_token", f"Color token '{value}' is not allowed; default restored.")]
        if not allowed and not value:
            return str(field.default_value), [self._issue(field.field_key, "invalid_color_token", "Color token must not be empty; default restored.")]
        return value, []

    def _normalize_range(
        self,
        field: OverlaySettingsField,
        raw_value: object,
    ) -> tuple[int | float, list[OverlaySettingsValidationIssue]]:
        if field.numeric_mode == "int":
            return self._normalize_integer(field, raw_value)
        return self._normalize_float(field, raw_value)

    def _normalize_spacing_token(
        self,
        field: OverlaySettingsField,
        raw_value: object,
    ) -> tuple[str, list[OverlaySettingsValidationIssue]]:
        value = str(raw_value).strip()
        allowed = {option.value for option in field.options} or set(STANDARD_SPACING_TOKENS)
        if value not in allowed:
            return str(field.default_value), [self._issue(field.field_key, "invalid_spacing_token", f"Spacing token '{value}' is not allowed; default restored.")]
        return value, []

    def _normalize_anchor_preset(
        self,
        field: OverlaySettingsField,
        raw_value: object,
    ) -> tuple[str, list[OverlaySettingsValidationIssue]]:
        value = str(raw_value).strip()
        allowed = {option.value for option in field.options} or set(STANDARD_ANCHOR_PRESETS)
        if value not in allowed:
            return str(field.default_value), [self._issue(field.field_key, "invalid_anchor_preset", f"Anchor preset '{value}' is not allowed; default restored.")]
        return value, []

    def _apply_numeric_limits(
        self,
        field: OverlaySettingsField,
        value: int | float,
    ) -> tuple[int | float, list[OverlaySettingsValidationIssue]]:
        issues: list[OverlaySettingsValidationIssue] = []
        normalized = value

        if field.min_value is not None and normalized < field.min_value:
            normalized = type(normalized)(field.min_value)
            issues.append(self._issue(field.field_key, "clamped_min", f"Clamped to minimum {field.min_value}.", severity="warning"))
        if field.max_value is not None and normalized > field.max_value:
            normalized = type(normalized)(field.max_value)
            issues.append(self._issue(field.field_key, "clamped_max", f"Clamped to maximum {field.max_value}.", severity="warning"))
        if field.step is not None and field.step > 0:
            base = field.min_value or 0
            relative = (float(normalized) - float(base)) / float(field.step)
            snapped = round(relative) * float(field.step) + float(base)
            if abs(float(normalized) - snapped) > 1e-9:
                normalized = int(round(snapped)) if isinstance(normalized, int) else snapped
                issues.append(self._issue(field.field_key, "snapped_step", f"Adjusted to step {field.step}.", severity="warning"))

        if field.numeric_mode == "int" or field.kind == "integer":
            return int(round(float(normalized))), issues
        return float(normalized), issues

    def _apply_rules(
        self,
        field: OverlaySettingsField,
        values: dict[str, object],
    ) -> list[OverlaySettingsValidationIssue]:
        issues: list[OverlaySettingsValidationIssue] = []
        value = values.get(field.field_key)
        for rule in field.validation_rules:
            if rule.kind == "less_than_or_equal_field":
                other = values.get(rule.other_field_key)
                if isinstance(value, (int, float)) and isinstance(other, (int, float)) and float(value) > float(other):
                    values[field.field_key] = other
                    issues.append(
                        self._issue(
                            field.field_key,
                            "rule_less_than_or_equal_field",
                            rule.message or f"Adjusted to not exceed '{rule.other_field_key}'.",
                            severity="warning",
                        )
                    )
                    value = other
            elif rule.kind == "greater_than_or_equal_field":
                other = values.get(rule.other_field_key)
                if isinstance(value, (int, float)) and isinstance(other, (int, float)) and float(value) < float(other):
                    values[field.field_key] = other
                    issues.append(
                        self._issue(
                            field.field_key,
                            "rule_greater_than_or_equal_field",
                            rule.message or f"Adjusted to be at least '{rule.other_field_key}'.",
                            severity="warning",
                        )
                    )
                    value = other
            elif rule.kind == "required_if":
                other = values.get(rule.other_field_key)
                if other == rule.value and self._is_empty(value):
                    issues.append(
                        self._issue(
                            field.field_key,
                            "rule_required_if",
                            rule.message or f"Required when '{rule.other_field_key}' is '{rule.value}'.",
                        )
                    )
            elif rule.kind == "one_of":
                allowed = {str(item) for item in (rule.value or [])} if isinstance(rule.value, (list, tuple, set)) else {str(rule.value)}
                if str(value) not in allowed:
                    issues.append(
                        self._issue(
                            field.field_key,
                            "rule_one_of",
                            rule.message or f"Value must be one of {sorted(allowed)}.",
                        )
                    )
            elif rule.kind == "multiple_of":
                if isinstance(value, (int, float)) and isinstance(rule.value, (int, float)) and float(rule.value) > 0:
                    quotient = float(value) / float(rule.value)
                    rounded = round(quotient)
                    if abs(quotient - rounded) > 1e-9:
                        snapped = rounded * float(rule.value)
                        values[field.field_key] = int(snapped) if isinstance(value, int) else snapped
                        issues.append(
                            self._issue(
                                field.field_key,
                                "rule_multiple_of",
                                rule.message or f"Adjusted to a multiple of {rule.value}.",
                                severity="warning",
                            )
                        )
        return issues

    def _field_visible(
        self,
        field: OverlaySettingsField,
        values: dict[str, object],
    ) -> bool:
        for condition in field.visibility_conditions:
            actual = values.get(condition.field_key)
            operator = condition.operator
            expected = condition.value
            if operator == "equals" and actual != expected:
                return False
            if operator == "not_equals" and actual == expected:
                return False
            if operator == "in" and actual not in set(expected or []):
                return False
            if operator == "not_in" and actual in set(expected or []):
                return False
            if operator == "truthy" and not bool(actual):
                return False
            if operator == "falsy" and bool(actual):
                return False
            if operator == "gte":
                if not isinstance(actual, (int, float)) or not isinstance(expected, (int, float)) or float(actual) < float(expected):
                    return False
            if operator == "lte":
                if not isinstance(actual, (int, float)) or not isinstance(expected, (int, float)) or float(actual) > float(expected):
                    return False
        return True

    @staticmethod
    def _issue(
        field_key: str,
        code: str,
        message: str,
        *,
        severity: str = "error",
    ) -> OverlaySettingsValidationIssue:
        return OverlaySettingsValidationIssue(
            field_key=field_key,
            code=code,
            message=message,
            severity="warning" if severity == "warning" else "error",
        )

    @staticmethod
    def _is_empty(value: object) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        return False

