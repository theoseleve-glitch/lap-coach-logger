"""Explicit telemetry binding contracts for overlays."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from lap_coach_logger.overlays.models import OverlayDefinition, utc_now_iso

OverlayTelemetryValueKind = Literal[
    "any",
    "number",
    "integer",
    "string",
    "boolean",
    "mapping",
    "sequence",
]
OverlayTelemetryFieldStatus = Literal["ok", "missing", "stale", "invalid", "defaulted", "preview"]
OverlayTelemetryHealthStatus = Literal["healthy", "degraded", "missing", "stale", "invalid", "preview"]

_SCHEMA_VERSION_RE = re.compile(r"\.v(?P<version>\d+)$", re.IGNORECASE)


@dataclass(slots=True, frozen=True)
class OverlayTelemetryRequirement:
    field_key: str
    label: str
    source_paths: tuple[str, ...]
    value_kind: OverlayTelemetryValueKind = "any"
    required: bool = False
    description: str = ""
    default_value: object = None
    stale_after_s: float | None = None
    preview_value: object = None

    def to_dict(self) -> dict[str, object]:
        return {
            "field_key": self.field_key,
            "label": self.label,
            "source_paths": list(self.source_paths),
            "value_kind": self.value_kind,
            "required": self.required,
            "description": self.description,
            "default_value": copy.deepcopy(self.default_value),
            "stale_after_s": self.stale_after_s,
            "preview_value": copy.deepcopy(self.preview_value),
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlayTelemetryRequirement:
        payload = _dict_copy(data)
        return cls(
            field_key=str(payload.get("field_key") or ""),
            label=str(payload.get("label") or payload.get("field_key") or ""),
            source_paths=_string_tuple(payload.get("source_paths")),
            value_kind=_normalize_value_kind(payload.get("value_kind")),
            required=bool(payload.get("required")),
            description=str(payload.get("description") or ""),
            default_value=copy.deepcopy(payload.get("default_value")),
            stale_after_s=_maybe_float(payload.get("stale_after_s")),
            preview_value=copy.deepcopy(payload.get("preview_value")),
        )


@dataclass(slots=True, frozen=True)
class OverlayTelemetryContract:
    contract_id: str
    title: str
    description: str = ""
    overlay_keys: tuple[str, ...] = ()
    requirements: tuple[OverlayTelemetryRequirement, ...] = ()

    def matches_overlay_key(self, overlay_key: str) -> bool:
        normalized = _normalize_overlay_key(overlay_key)
        if not normalized:
            return False
        if normalized == _normalize_overlay_key(self.contract_id):
            return True
        return normalized in {_normalize_overlay_key(item) for item in self.overlay_keys}

    def to_dict(self) -> dict[str, object]:
        return {
            "contract_id": self.contract_id,
            "title": self.title,
            "description": self.description,
            "overlay_keys": list(self.overlay_keys),
            "requirements": [item.to_dict() for item in self.requirements],
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlayTelemetryContract:
        payload = _dict_copy(data)
        return cls(
            contract_id=str(payload.get("contract_id") or ""),
            title=str(payload.get("title") or payload.get("contract_id") or ""),
            description=str(payload.get("description") or ""),
            overlay_keys=_string_tuple(payload.get("overlay_keys")),
            requirements=tuple(
                OverlayTelemetryRequirement.from_dict(item)
                for item in payload.get("requirements", [])
            ),
        )


@dataclass(slots=True, frozen=True)
class OverlayTelemetryFieldHealth:
    field_key: str
    status: OverlayTelemetryFieldStatus
    required: bool
    source_path: str = ""
    message: str = ""
    staleness_s: float | None = None


@dataclass(slots=True, frozen=True)
class OverlayTelemetryHealth:
    status: OverlayTelemetryHealthStatus
    summary: str
    resolved_field_count: int
    total_field_count: int
    missing_field_keys: tuple[str, ...] = ()
    stale_field_keys: tuple[str, ...] = ()
    invalid_field_keys: tuple[str, ...] = ()
    defaulted_field_keys: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class OverlayTelemetryBindingResult:
    contract_id: str
    overlay_key: str
    values: dict[str, object]
    field_health: tuple[OverlayTelemetryFieldHealth, ...]
    health: OverlayTelemetryHealth
    preview_mode: bool = False
    generated_at_utc: str = field(default_factory=utc_now_iso)
    live_timestamp_utc: str = ""
    data_staleness_s: float | None = None

    def field_health_map(self) -> dict[str, OverlayTelemetryFieldHealth]:
        return {item.field_key: item for item in self.field_health}


class OverlayTelemetryContractRegistry:
    """Registry for explicit overlay telemetry contracts."""

    def __init__(
        self,
        contracts: tuple[OverlayTelemetryContract, ...] | list[OverlayTelemetryContract] = (),
    ) -> None:
        self._contracts: dict[str, OverlayTelemetryContract] = {}
        self._overlay_lookup: dict[str, str] = {}
        for contract in tuple(contracts):
            self.register(contract)

    def register(self, contract: OverlayTelemetryContract) -> OverlayTelemetryContract:
        if not contract.contract_id.strip():
            raise ValueError("Telemetry contract must define contract_id")
        self._contracts[contract.contract_id] = contract
        for overlay_key in (contract.contract_id, *contract.overlay_keys):
            normalized = _normalize_overlay_key(overlay_key)
            if normalized:
                self._overlay_lookup[normalized] = contract.contract_id
        return contract

    def contract(self, contract_id: str) -> OverlayTelemetryContract:
        try:
            return self._contracts[contract_id]
        except KeyError as exc:
            raise KeyError(f"Unknown overlay telemetry contract '{contract_id}'") from exc

    def resolve_for_overlay_key(self, overlay_key: str) -> OverlayTelemetryContract:
        normalized = _normalize_overlay_key(overlay_key)
        contract_id = self._overlay_lookup.get(normalized)
        if not contract_id:
            raise KeyError(f"No overlay telemetry contract registered for '{overlay_key}'")
        return self.contract(contract_id)

    def list_contracts(self) -> tuple[OverlayTelemetryContract, ...]:
        return tuple(self._contracts.values())


class OverlayTelemetryPreviewProvider:
    """Generates deterministic fake telemetry snapshots for preview mode."""

    def __init__(self, registry: OverlayTelemetryContractRegistry) -> None:
        self._registry = registry

    def snapshot_for_contract(self, contract_id: str) -> dict[str, object]:
        contract = self._registry.contract(contract_id)
        snapshot: dict[str, object] = {
            "status": "Preview",
            "sim": "Preview Simulator",
            "data_staleness_s": 0.0,
            "stream_status": "ok",
            "live": {
                "timestamp_utc": utc_now_iso(),
                "sim_name": "Preview Simulator",
                "track_name": "Preview Raceway",
                "session_uid": f"preview:{contract.contract_id}",
            },
        }
        for requirement in contract.requirements:
            value = copy.deepcopy(_preview_value_for_requirement(requirement))
            if not requirement.source_paths:
                continue
            _assign_path(snapshot, requirement.source_paths[0], value)
        return snapshot


class OverlayTelemetryBindingService:
    """Resolves overlay contracts against a shared telemetry snapshot."""

    def __init__(
        self,
        *,
        registry: OverlayTelemetryContractRegistry,
        preview_provider: OverlayTelemetryPreviewProvider | None = None,
    ) -> None:
        self._registry = registry
        self._preview_provider = preview_provider or OverlayTelemetryPreviewProvider(registry)

    def contract(self, contract_id: str) -> OverlayTelemetryContract:
        return self._registry.contract(contract_id)

    def bind(self, contract_id: str, telemetry_snapshot: dict[str, object]) -> OverlayTelemetryBindingResult:
        contract = self._registry.contract(contract_id)
        return self._bind_contract(
            contract,
            telemetry_snapshot=telemetry_snapshot,
            overlay_key=contract.contract_id,
            preview_mode=False,
        )

    def preview_binding(self, contract_id: str) -> OverlayTelemetryBindingResult:
        contract = self._registry.contract(contract_id)
        return self._bind_contract(
            contract,
            telemetry_snapshot=self._preview_provider.snapshot_for_contract(contract_id),
            overlay_key=contract.contract_id,
            preview_mode=True,
        )

    def bind_for_overlay_key(
        self,
        overlay_key: str,
        telemetry_snapshot: dict[str, object],
    ) -> OverlayTelemetryBindingResult:
        contract = self._registry.resolve_for_overlay_key(overlay_key)
        return self._bind_contract(
            contract,
            telemetry_snapshot=telemetry_snapshot,
            overlay_key=overlay_key,
            preview_mode=False,
        )

    def preview_binding_for_overlay_key(self, overlay_key: str) -> OverlayTelemetryBindingResult:
        contract = self._registry.resolve_for_overlay_key(overlay_key)
        return self._bind_contract(
            contract,
            telemetry_snapshot=self._preview_provider.snapshot_for_contract(contract.contract_id),
            overlay_key=overlay_key,
            preview_mode=True,
        )

    def bind_for_definition(
        self,
        definition: OverlayDefinition,
        telemetry_snapshot: dict[str, object],
    ) -> OverlayTelemetryBindingResult:
        contract = self._resolve_for_definition(definition)
        return self._bind_contract(
            contract,
            telemetry_snapshot=telemetry_snapshot,
            overlay_key=definition.overlay_id,
            preview_mode=False,
        )

    def preview_binding_for_definition(self, definition: OverlayDefinition) -> OverlayTelemetryBindingResult:
        contract = self._resolve_for_definition(definition)
        return self._bind_contract(
            contract,
            telemetry_snapshot=self._preview_provider.snapshot_for_contract(contract.contract_id),
            overlay_key=definition.overlay_id,
            preview_mode=True,
        )

    def bind_for_instance(
        self,
        instance: object,
        telemetry_snapshot: dict[str, object],
    ) -> OverlayTelemetryBindingResult:
        overlay_key = str(getattr(instance, "overlay_id", "") or "")
        if hasattr(instance, "definition"):
            definition = getattr(instance, "definition")
            if isinstance(definition, OverlayDefinition):
                return self.bind_for_definition(definition, telemetry_snapshot)
        return self.bind_for_overlay_key(overlay_key, telemetry_snapshot)

    def preview_binding_for_instance(self, instance: object) -> OverlayTelemetryBindingResult:
        overlay_key = str(getattr(instance, "overlay_id", "") or "")
        if hasattr(instance, "definition"):
            definition = getattr(instance, "definition")
            if isinstance(definition, OverlayDefinition):
                return self.preview_binding_for_definition(definition)
        return self.preview_binding_for_overlay_key(overlay_key)

    def _resolve_for_definition(self, definition: OverlayDefinition) -> OverlayTelemetryContract:
        for candidate in _contract_candidates_for_definition(definition):
            try:
                return self._registry.resolve_for_overlay_key(candidate)
            except KeyError:
                continue
        raise KeyError(
            f"No telemetry contract registered for overlay '{definition.overlay_id}'"
        )

    def _bind_contract(
        self,
        contract: OverlayTelemetryContract,
        *,
        telemetry_snapshot: dict[str, object],
        overlay_key: str,
        preview_mode: bool,
    ) -> OverlayTelemetryBindingResult:
        live_timestamp_utc = _extract_live_timestamp_utc(telemetry_snapshot)
        data_staleness_s = _extract_data_staleness_seconds(
            telemetry_snapshot,
            live_timestamp_utc=live_timestamp_utc,
        )

        values: dict[str, object] = {}
        field_health: list[OverlayTelemetryFieldHealth] = []
        missing_required: list[str] = []
        stale_fields: list[str] = []
        invalid_fields: list[str] = []
        defaulted_fields: list[str] = []
        resolved_field_count = 0

        for requirement in contract.requirements:
            value, health = _resolve_requirement(
                requirement,
                telemetry_snapshot=telemetry_snapshot,
                preview_mode=preview_mode,
                data_staleness_s=data_staleness_s,
            )
            values[requirement.field_key] = value
            field_health.append(health)
            if health.status in {"ok", "stale", "defaulted", "preview"}:
                resolved_field_count += 1
            if health.required and health.status == "missing":
                missing_required.append(health.field_key)
            if health.status == "stale":
                stale_fields.append(health.field_key)
            if health.status == "invalid":
                invalid_fields.append(health.field_key)
            if health.status == "defaulted":
                defaulted_fields.append(health.field_key)

        health = _build_health(
            preview_mode=preview_mode,
            total_fields=len(contract.requirements),
            resolved_field_count=resolved_field_count,
            missing_required=tuple(missing_required),
            stale_fields=tuple(stale_fields),
            invalid_fields=tuple(invalid_fields),
            defaulted_fields=tuple(defaulted_fields),
        )
        return OverlayTelemetryBindingResult(
            contract_id=contract.contract_id,
            overlay_key=overlay_key,
            values=values,
            field_health=tuple(field_health),
            health=health,
            preview_mode=preview_mode,
            live_timestamp_utc=live_timestamp_utc,
            data_staleness_s=data_staleness_s,
        )


def example_overlay_telemetry_contracts() -> tuple[OverlayTelemetryContract, ...]:
    return (
        OverlayTelemetryContract(
            contract_id="core_driving_hud",
            title="Core Driving HUD",
            description="Primary driving HUD bindings for on-track state and vehicle vitals.",
            overlay_keys=("core_driving_hud_overlay",),
            requirements=(
                OverlayTelemetryRequirement("speed_kph", "Speed", ("live.speed_kph",), "number", True, preview_value=214.0, stale_after_s=2.5),
                OverlayTelemetryRequirement("gear", "Gear", ("live.gear",), "integer", True, preview_value=5, stale_after_s=2.5),
                OverlayTelemetryRequirement("rpm", "RPM", ("live.rpm",), "number", True, preview_value=7125.0, stale_after_s=2.5),
                OverlayTelemetryRequirement("lap_time_s", "Lap Time", ("live.lap_time_s",), "number", False, preview_value=82.416),
                OverlayTelemetryRequirement("live_delta_s", "Live Delta", ("live.live_delta_s",), "number", False, preview_value=-0.124),
                OverlayTelemetryRequirement("sector_1_time_s", "Sector 1", ("live.sector_1_time_s",), "number", False, preview_value=26.104),
                OverlayTelemetryRequirement("sector_2_time_s", "Sector 2", ("live.sector_2_time_s",), "number", False, preview_value=28.781),
                OverlayTelemetryRequirement("sector_3_time_s", "Sector 3", ("live.sector_3_time_s",), "number", False, preview_value=27.531),
                OverlayTelemetryRequirement("fuel_level", "Fuel Level", ("live.fuel_level",), "number", False, preview_value=48.6),
                OverlayTelemetryRequirement("flag_state", "Flag State", ("live.flag_state", "live.flags", "status"), "string", False, preview_value="Green"),
                OverlayTelemetryRequirement("tyre_temp_fl", "FL Tyre Temp", ("live.tyre_temp_fl",), "number", False, preview_value=78.0),
                OverlayTelemetryRequirement("tyre_temp_fr", "FR Tyre Temp", ("live.tyre_temp_fr",), "number", False, preview_value=80.0),
                OverlayTelemetryRequirement("tyre_temp_rl", "RL Tyre Temp", ("live.tyre_temp_rl",), "number", False, preview_value=81.0),
                OverlayTelemetryRequirement("tyre_temp_rr", "RR Tyre Temp", ("live.tyre_temp_rr",), "number", False, preview_value=82.0),
                OverlayTelemetryRequirement("brake_temp_fl", "FL Brake Temp", ("live.brake_temp_fl",), "number", False, preview_value=515.0),
                OverlayTelemetryRequirement("brake_temp_fr", "FR Brake Temp", ("live.brake_temp_fr",), "number", False, preview_value=526.0),
                OverlayTelemetryRequirement("brake_temp_rl", "RL Brake Temp", ("live.brake_temp_rl",), "number", False, preview_value=442.0),
                OverlayTelemetryRequirement("brake_temp_rr", "RR Brake Temp", ("live.brake_temp_rr",), "number", False, preview_value=449.0),
            ),
        ),
        OverlayTelemetryContract(
            contract_id="delta_widget",
            title="Delta Widget",
            description="Lap delta and sector comparison bindings.",
            overlay_keys=("delta_widget_overlay", "session_delta"),
            requirements=(
                OverlayTelemetryRequirement("live_delta_s", "Live Delta", ("live.live_delta_s",), "number", True, preview_value=-0.086, stale_after_s=2.0),
                OverlayTelemetryRequirement("lap_number", "Lap Number", ("live.lap_number",), "integer", False, preview_value=7),
                OverlayTelemetryRequirement("last_lap_time_s", "Last Lap", ("live.last_lap_time_s",), "number", False, preview_value=81.944),
                OverlayTelemetryRequirement("best_lap_time_s", "Best Lap", ("live.best_lap_time_s",), "number", False, preview_value=81.601),
                OverlayTelemetryRequirement("sector_1_time_s", "Sector 1", ("live.sector_1_time_s",), "number", False, preview_value=25.983),
                OverlayTelemetryRequirement("sector_2_time_s", "Sector 2", ("live.sector_2_time_s",), "number", False, preview_value=28.401),
                OverlayTelemetryRequirement("sector_3_time_s", "Sector 3", ("live.sector_3_time_s",), "number", False, preview_value=27.217),
            ),
        ),
        OverlayTelemetryContract(
            contract_id="relative_table",
            title="Relative Table",
            description="Standings and nearby-car relative bindings.",
            overlay_keys=("relative_table_overlay", "standings"),
            requirements=(
                OverlayTelemetryRequirement(
                    "relative_rows",
                    "Relative Rows",
                    ("live.relative_rows", "live.standings_rows", "live.relative_table_rows"),
                    "sequence",
                    True,
                    preview_value=(
                        {"position": 6, "driver": "Player", "gap_s": 0.0, "class_position": 2},
                        {"position": 5, "driver": "Car Ahead", "gap_s": -0.412, "class_position": 2},
                        {"position": 7, "driver": "Car Behind", "gap_s": 0.663, "class_position": 3},
                    ),
                    stale_after_s=3.0,
                ),
                OverlayTelemetryRequirement("player_position", "Overall Position", ("live.player_position", "live.position_overall"), "integer", False, preview_value=6),
                OverlayTelemetryRequirement("class_position", "Class Position", ("live.class_position", "live.position_class"), "integer", False, preview_value=2),
                OverlayTelemetryRequirement("flag_state", "Flag State", ("live.flag_state", "status"), "string", False, preview_value="Green"),
            ),
        ),
        OverlayTelemetryContract(
            contract_id="track_map",
            title="Track Map",
            description="Map position and lap-progress bindings.",
            overlay_keys=("track_map_overlay", "track_map"),
            requirements=(
                OverlayTelemetryRequirement("world_pos_x", "World X", ("live.world_pos_x",), "number", True, preview_value=112.4, stale_after_s=2.0),
                OverlayTelemetryRequirement("world_pos_y", "World Y", ("live.world_pos_z", "live.world_pos_y"), "number", True, preview_value=-84.9, stale_after_s=2.0),
                OverlayTelemetryRequirement("lap_dist_pct", "Lap Distance", ("live.lap_dist_pct",), "number", False, preview_value=0.438),
                OverlayTelemetryRequirement("current_sector_index", "Current Sector", ("live.current_sector_index",), "integer", False, preview_value=2),
                OverlayTelemetryRequirement("speed_kph", "Speed", ("live.speed_kph",), "number", False, preview_value=191.0),
                OverlayTelemetryRequirement("track_name", "Track", ("live.track_name", "sim"), "string", False, preview_value="Preview Raceway"),
            ),
        ),
    )


def build_example_overlay_telemetry_binding_service() -> OverlayTelemetryBindingService:
    registry = OverlayTelemetryContractRegistry(example_overlay_telemetry_contracts())
    return OverlayTelemetryBindingService(registry=registry)


def _build_health(
    *,
    preview_mode: bool,
    total_fields: int,
    resolved_field_count: int,
    missing_required: tuple[str, ...],
    stale_fields: tuple[str, ...],
    invalid_fields: tuple[str, ...],
    defaulted_fields: tuple[str, ...],
) -> OverlayTelemetryHealth:
    if preview_mode:
        status: OverlayTelemetryHealthStatus = "preview"
        summary = "Preview telemetry is active."
    elif invalid_fields:
        status = "invalid"
        summary = f"{len(invalid_fields)} field(s) are invalid."
    elif missing_required:
        status = "missing"
        summary = f"{len(missing_required)} required field(s) are missing."
    elif stale_fields:
        status = "stale"
        summary = f"{len(stale_fields)} field(s) are stale."
    elif defaulted_fields:
        status = "degraded"
        summary = f"{len(defaulted_fields)} field(s) are using fallback values."
    else:
        status = "healthy"
        summary = "Overlay telemetry is healthy."
    return OverlayTelemetryHealth(
        status=status,
        summary=summary,
        resolved_field_count=resolved_field_count,
        total_field_count=total_fields,
        missing_field_keys=missing_required,
        stale_field_keys=stale_fields,
        invalid_field_keys=invalid_fields,
        defaulted_field_keys=defaulted_fields,
    )


def _resolve_requirement(
    requirement: OverlayTelemetryRequirement,
    *,
    telemetry_snapshot: dict[str, object],
    preview_mode: bool,
    data_staleness_s: float | None,
) -> tuple[object, OverlayTelemetryFieldHealth]:
    value = None
    source_path = ""
    found = False
    for candidate in requirement.source_paths:
        candidate_found, candidate_value = _resolve_path(telemetry_snapshot, candidate)
        if candidate_found and candidate_value is not None:
            source_path = candidate
            value = candidate_value
            found = True
            break

    status: OverlayTelemetryFieldStatus = "ok"
    message = ""
    if preview_mode:
        value = _preview_value_for_requirement(requirement) if not found else value
        status = "preview"
        message = "Preview data"
    elif not found:
        if requirement.default_value is not None:
            value = copy.deepcopy(requirement.default_value)
            status = "defaulted"
            message = "Signal missing, using fallback value."
        else:
            status = "missing"
            message = "Signal missing."
    else:
        if not _matches_value_kind(value, requirement.value_kind):
            if requirement.default_value is not None:
                value = copy.deepcopy(requirement.default_value)
                status = "invalid"
                message = "Signal type was invalid, fallback applied."
            else:
                value = None
                status = "invalid"
                message = "Signal type was invalid."
        elif (
            requirement.stale_after_s is not None
            and isinstance(data_staleness_s, float)
            and data_staleness_s > requirement.stale_after_s
        ):
            status = "stale"
            message = f"Signal is stale by {data_staleness_s:.2f}s."

    return value, OverlayTelemetryFieldHealth(
        field_key=requirement.field_key,
        status=status,
        required=requirement.required,
        source_path=source_path,
        message=message,
        staleness_s=data_staleness_s if status == "stale" else None,
    )


def _contract_candidates_for_definition(definition: OverlayDefinition) -> tuple[str, ...]:
    candidates: list[str] = []
    schema_base = _strip_version_suffix(definition.settings_schema_ref)
    for candidate in (
        schema_base,
        definition.overlay_id,
        definition.renderer_key,
        _strip_overlay_suffix(definition.overlay_id),
        _strip_overlay_suffix(definition.renderer_key),
    ):
        normalized = str(candidate or "").strip()
        if normalized and normalized not in candidates:
            candidates.append(normalized)
    return tuple(candidates)


def _extract_live_timestamp_utc(snapshot: dict[str, object]) -> str:
    found, value = _resolve_path(snapshot, "live.timestamp_utc")
    if found and isinstance(value, str):
        return value
    return ""


def _extract_data_staleness_seconds(
    snapshot: dict[str, object],
    *,
    live_timestamp_utc: str,
) -> float | None:
    found, value = _resolve_path(snapshot, "data_staleness_s")
    if found and isinstance(value, (int, float)):
        return max(0.0, float(value))
    if live_timestamp_utc:
        try:
            live_ts = datetime.fromisoformat(live_timestamp_utc)
            return max(0.0, (datetime.now(timezone.utc) - live_ts).total_seconds())
        except Exception:
            return None
    return None


def _resolve_path(payload: dict[str, object], path: str) -> tuple[bool, object]:
    current: object = payload
    for segment in str(path).split("."):
        if not isinstance(current, dict) or segment not in current:
            return False, None
        current = current[segment]
    return True, current


def _assign_path(payload: dict[str, object], path: str, value: object) -> None:
    current = payload
    parts = str(path).split(".")
    for segment in parts[:-1]:
        child = current.get(segment)
        if not isinstance(child, dict):
            child = {}
            current[segment] = child
        current = child
    current[parts[-1]] = value


def _matches_value_kind(value: object, kind: OverlayTelemetryValueKind) -> bool:
    if kind == "any":
        return True
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "string":
        return isinstance(value, str)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "mapping":
        return isinstance(value, dict)
    if kind == "sequence":
        return isinstance(value, (list, tuple))
    return False


def _preview_value_for_requirement(requirement: OverlayTelemetryRequirement) -> object:
    if requirement.preview_value is not None:
        return copy.deepcopy(requirement.preview_value)
    if requirement.default_value is not None:
        return copy.deepcopy(requirement.default_value)
    if requirement.value_kind == "number":
        return 0.0
    if requirement.value_kind == "integer":
        return 0
    if requirement.value_kind == "string":
        return ""
    if requirement.value_kind == "boolean":
        return False
    if requirement.value_kind == "mapping":
        return {}
    if requirement.value_kind == "sequence":
        return []
    return None


def _normalize_overlay_key(value: object) -> str:
    return str(value or "").strip().lower()


def _strip_overlay_suffix(value: object) -> str:
    text = str(value or "").strip()
    return text[:-8] if text.lower().endswith("_overlay") else text


def _strip_version_suffix(value: object) -> str:
    text = str(value or "").strip()
    match = _SCHEMA_VERSION_RE.search(text)
    if match is None:
        return text
    return text[: match.start()]


def _normalize_value_kind(value: object) -> OverlayTelemetryValueKind:
    candidate = str(value or "any").strip().lower()
    if candidate in {"number", "integer", "string", "boolean", "mapping", "sequence"}:
        return candidate
    return "any"


def _maybe_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _string_tuple(values: object) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(str(item) for item in values if str(item).strip())


def _dict_copy(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}
