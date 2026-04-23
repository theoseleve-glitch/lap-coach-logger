"""Declarative overlay settings schema models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

OverlaySettingsFieldKind = Literal[
    "boolean",
    "integer",
    "float",
    "enum",
    "color_token",
    "range",
    "spacing_token",
    "anchor_preset",
]
OverlaySettingsSectionKey = Literal[
    "performance_and_size",
    "appearance",
    "visibility",
    "behavior",
    "advanced",
]
OverlaySettingsNumericMode = Literal["int", "float"]
OverlaySettingsVisibilityOperator = Literal[
    "equals",
    "not_equals",
    "in",
    "not_in",
    "truthy",
    "falsy",
    "gte",
    "lte",
]
OverlaySettingsValidationRuleKind = Literal[
    "less_than_or_equal_field",
    "greater_than_or_equal_field",
    "required_if",
    "one_of",
    "multiple_of",
]

STANDARD_SPACING_TOKENS: tuple[str, ...] = (
    "tight",
    "compact",
    "normal",
    "comfortable",
    "spacious",
)

STANDARD_ANCHOR_PRESETS: tuple[str, ...] = (
    "top_left",
    "top_center",
    "top_right",
    "center_left",
    "center",
    "center_right",
    "bottom_left",
    "bottom_center",
    "bottom_right",
)


def _string_tuple(values: object) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(str(value) for value in values if str(value).strip())


def _dict_copy(data: object) -> dict[str, object]:
    if not isinstance(data, dict):
        return {}
    return {str(key): value for key, value in data.items()}


@dataclass(slots=True, frozen=True)
class OverlaySettingsOption:
    value: str
    label: str
    description: str = ""
    premium_only: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "value": self.value,
            "label": self.label,
            "description": self.description,
            "premium_only": self.premium_only,
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlaySettingsOption:
        payload = _dict_copy(data)
        return cls(
            value=str(payload.get("value") or ""),
            label=str(payload.get("label") or payload.get("value") or ""),
            description=str(payload.get("description") or ""),
            premium_only=bool(payload.get("premium_only")),
        )


@dataclass(slots=True, frozen=True)
class OverlaySettingsVisibilityCondition:
    field_key: str
    operator: OverlaySettingsVisibilityOperator
    value: object = None

    def to_dict(self) -> dict[str, object]:
        return {
            "field_key": self.field_key,
            "operator": self.operator,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlaySettingsVisibilityCondition:
        payload = _dict_copy(data)
        return cls(
            field_key=str(payload.get("field_key") or ""),
            operator=str(payload.get("operator") or "equals"),
            value=payload.get("value"),
        )


@dataclass(slots=True, frozen=True)
class OverlaySettingsValidationRule:
    kind: OverlaySettingsValidationRuleKind
    message: str = ""
    other_field_key: str = ""
    value: object = None

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "message": self.message,
            "other_field_key": self.other_field_key,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlaySettingsValidationRule:
        payload = _dict_copy(data)
        return cls(
            kind=str(payload.get("kind") or "one_of"),
            message=str(payload.get("message") or ""),
            other_field_key=str(payload.get("other_field_key") or ""),
            value=payload.get("value"),
        )


@dataclass(slots=True, frozen=True)
class OverlaySettingsField:
    field_key: str
    label: str
    kind: OverlaySettingsFieldKind
    section: OverlaySettingsSectionKey
    default_value: object
    description: str = ""
    min_value: int | float | None = None
    max_value: int | float | None = None
    step: int | float | None = None
    category_section: str = ""
    premium_only: bool = False
    advanced: bool = False
    visibility_conditions: tuple[OverlaySettingsVisibilityCondition, ...] = ()
    validation_rules: tuple[OverlaySettingsValidationRule, ...] = ()
    options: tuple[OverlaySettingsOption, ...] = ()
    unit: str = ""
    token_namespace: str = ""
    numeric_mode: OverlaySettingsNumericMode = "float"

    def to_dict(self) -> dict[str, object]:
        return {
            "field_key": self.field_key,
            "label": self.label,
            "kind": self.kind,
            "section": self.section,
            "default_value": self.default_value,
            "description": self.description,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "step": self.step,
            "category_section": self.category_section or self.section,
            "premium_only": self.premium_only,
            "advanced": self.advanced,
            "visibility_conditions": [condition.to_dict() for condition in self.visibility_conditions],
            "validation_rules": [rule.to_dict() for rule in self.validation_rules],
            "options": [option.to_dict() for option in self.options],
            "unit": self.unit,
            "token_namespace": self.token_namespace,
            "numeric_mode": self.numeric_mode,
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlaySettingsField:
        payload = _dict_copy(data)
        return cls(
            field_key=str(payload.get("field_key") or ""),
            label=str(payload.get("label") or payload.get("field_key") or ""),
            kind=str(payload.get("kind") or "float"),
            section=str(payload.get("section") or "behavior"),
            default_value=payload.get("default_value"),
            description=str(payload.get("description") or ""),
            min_value=payload.get("min_value") if isinstance(payload.get("min_value"), (int, float)) else None,
            max_value=payload.get("max_value") if isinstance(payload.get("max_value"), (int, float)) else None,
            step=payload.get("step") if isinstance(payload.get("step"), (int, float)) else None,
            category_section=str(payload.get("category_section") or payload.get("section") or "behavior"),
            premium_only=bool(payload.get("premium_only")),
            advanced=bool(payload.get("advanced")),
            visibility_conditions=tuple(
                OverlaySettingsVisibilityCondition.from_dict(item)
                for item in payload.get("visibility_conditions", [])
            ),
            validation_rules=tuple(
                OverlaySettingsValidationRule.from_dict(item)
                for item in payload.get("validation_rules", [])
            ),
            options=tuple(OverlaySettingsOption.from_dict(item) for item in payload.get("options", [])),
            unit=str(payload.get("unit") or ""),
            token_namespace=str(payload.get("token_namespace") or ""),
            numeric_mode=str(payload.get("numeric_mode") or "float"),
        )


@dataclass(slots=True, frozen=True)
class OverlaySettingsSection:
    key: OverlaySettingsSectionKey
    label: str
    description: str = ""
    sort_order: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "sort_order": self.sort_order,
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlaySettingsSection:
        payload = _dict_copy(data)
        return cls(
            key=str(payload.get("key") or "behavior"),
            label=str(payload.get("label") or payload.get("key") or ""),
            description=str(payload.get("description") or ""),
            sort_order=int(payload.get("sort_order") or 0),
        )


STANDARD_SECTIONS: tuple[OverlaySettingsSection, ...] = (
    OverlaySettingsSection("performance_and_size", "Performance and Size", sort_order=10),
    OverlaySettingsSection("appearance", "Appearance", sort_order=20),
    OverlaySettingsSection("visibility", "Visibility", sort_order=30),
    OverlaySettingsSection("behavior", "Behavior", sort_order=40),
    OverlaySettingsSection("advanced", "Advanced", sort_order=50),
)


@dataclass(slots=True, frozen=True)
class OverlaySettingsSchema:
    schema_id: str
    overlay_key: str
    version: int
    title: str
    description: str = ""
    sections: tuple[OverlaySettingsSection, ...] = STANDARD_SECTIONS
    fields: tuple[OverlaySettingsField, ...] = ()

    def field_map(self) -> dict[str, OverlaySettingsField]:
        return {field.field_key: field for field in self.fields}

    def default_values(self) -> dict[str, object]:
        return {field.field_key: field.default_value for field in self.fields}

    def field(self, field_key: str) -> OverlaySettingsField | None:
        for field in self.fields:
            if field.field_key == field_key:
                return field
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "overlay_key": self.overlay_key,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "sections": [section.to_dict() for section in self.sections],
            "fields": [field.to_dict() for field in self.fields],
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlaySettingsSchema:
        payload = _dict_copy(data)
        return cls(
            schema_id=str(payload.get("schema_id") or ""),
            overlay_key=str(payload.get("overlay_key") or payload.get("schema_id") or ""),
            version=int(payload.get("version") or 1),
            title=str(payload.get("title") or payload.get("schema_id") or ""),
            description=str(payload.get("description") or ""),
            sections=tuple(
                OverlaySettingsSection.from_dict(item)
                for item in payload.get("sections", list(section.to_dict() for section in STANDARD_SECTIONS))
            ),
            fields=tuple(OverlaySettingsField.from_dict(item) for item in payload.get("fields", [])),
        )


@dataclass(slots=True, frozen=True)
class OverlaySettingsValidationIssue:
    field_key: str
    code: str
    message: str
    severity: Literal["error", "warning"] = "error"


@dataclass(slots=True, frozen=True)
class OverlaySettingsResolution:
    schema_id: str
    schema_version: int
    values: dict[str, object]
    visible_field_keys: tuple[str, ...]
    issues: tuple[OverlaySettingsValidationIssue, ...] = ()
    migrated_from_version: int | None = None


@dataclass(slots=True, frozen=True)
class OverlaySettingsMigration:
    schema_id: str
    from_version: int
    to_version: int
    transform: object
    description: str = ""

