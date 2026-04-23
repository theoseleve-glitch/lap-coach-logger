from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import pyarrow.parquet as pq

from lap_coach_logger.core.schema import TelemetrySample
from lap_coach_logger.core.setup_tools import describe_setup_effect


_LEVER_PATTERNS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("brake_bias", "Brake bias", ("brakebias", "frontbias", "brake_bias")),
    ("rear_wing", "Rear wing", ("rearwing", "wing", "aero", "spoiler")),
    ("front_arb", "Front anti-roll bar", ("frontarb", "arbfront", "antirollbarfront")),
    ("rear_arb", "Rear anti-roll bar", ("reararb", "arbrear", "antirollbarrear")),
    ("front_spring", "Front spring", ("frontspring", "springfront", "wheelratefront")),
    ("rear_spring", "Rear spring", ("rearspring", "springrear", "wheelraterear")),
    ("ride_height", "Ride height", ("rideheight", "rodlength", "rod_length", "rake")),
    ("camber", "Camber", ("camber",)),
    ("toe", "Toe", ("toe",)),
    ("tyre_pressure", "Tyre pressure", ("pressure", "pressures")),
    ("diff", "Differential", ("diff", "preload")),
    ("tc", "Traction control", ("tc", "tractioncontrol")),
    ("abs", "ABS", ("abs",)),
    ("fuel", "Fuel load", ("fuel",)),
)


@dataclass(frozen=True, slots=True)
class _HeuristicRule:
    issue_tag: str
    lever_id: str
    direction: str
    weight: float
    rationale: str


_HEURISTIC_RULES: tuple[_HeuristicRule, ...] = (
    _HeuristicRule("front_limited", "front_arb", "decrease", 0.74, "Soften the front axle to free mid-corner rotation."),
    _HeuristicRule("front_limited", "rear_arb", "increase", 0.68, "Add rear roll support to help the car rotate."),
    _HeuristicRule("front_limited", "brake_bias", "decrease", 0.55, "Move brake bias rearward if the car is reluctant on entry."),
    _HeuristicRule("front_limited", "rear_wing", "decrease", 0.46, "Trim rear aero support if the push is strongest at higher speed."),
    _HeuristicRule("front_limited", "camber", "increase", 0.36, "More front camber can recover loaded mid-corner grip."),
    _HeuristicRule("rear_limited", "rear_wing", "increase", 0.76, "Add rear aero support to calm high-speed and exit instability."),
    _HeuristicRule("rear_limited", "rear_arb", "decrease", 0.67, "Softer rear roll stiffness generally improves rear compliance."),
    _HeuristicRule("rear_limited", "brake_bias", "increase", 0.57, "Move brake bias forward to stabilize braking entry."),
    _HeuristicRule("rear_limited", "diff", "increase", 0.42, "More diff locking can steady the rear, but watch rotation."),
    _HeuristicRule("rear_limited", "toe", "increase", 0.30, "More rear toe-in usually adds stability if the axle is nervous."),
    _HeuristicRule("traction_limited", "tc", "increase", 0.79, "Raise TC intervention if exit wheelspin is costing time."),
    _HeuristicRule("traction_limited", "rear_arb", "decrease", 0.58, "Soften rear roll stiffness to let the tyre stay loaded on exit."),
    _HeuristicRule("traction_limited", "rear_spring", "decrease", 0.52, "Reduce rear spring support if traction is breaking away."),
    _HeuristicRule("traction_limited", "rear_wing", "increase", 0.47, "A little more rear support can help exit stability."),
    _HeuristicRule("traction_limited", "diff", "review", 0.36, "Review diff preload/locking if the rear is spinning up on power."),
    _HeuristicRule("braking_instability", "brake_bias", "increase", 0.83, "More front brake bias is the cleanest first move for stability."),
    _HeuristicRule("braking_instability", "abs", "increase", 0.54, "More ABS support can reduce threshold lockups."),
    _HeuristicRule("braking_instability", "front_arb", "increase", 0.28, "A calmer front platform can help the braking phase."),
    _HeuristicRule("tyres_overheated", "tyre_pressure", "decrease", 0.74, "Reducing pressure helps calm the tyre window when it is running hot."),
    _HeuristicRule("tyres_overheated", "camber", "decrease", 0.51, "Excess camber can overwork the loaded shoulder."),
    _HeuristicRule("tyres_overheated", "tc", "increase", 0.24, "More intervention can reduce heat from excessive slip."),
    _HeuristicRule("tyres_cold", "tyre_pressure", "increase", 0.67, "More pressure can help a cold tyre support itself sooner."),
    _HeuristicRule("tyres_cold", "camber", "increase", 0.21, "A touch more camber can build load when the tyre is not waking up."),
    _HeuristicRule("high_drag_risk", "rear_wing", "decrease", 0.77, "Rear wing is the first lever to trim when drag looks expensive."),
    _HeuristicRule("high_drag_risk", "ride_height", "decrease", 0.23, "Review ride heights if the car looks aero-draggy without obvious balance gain."),
    _HeuristicRule("bottoming_risk", "ride_height", "increase", 0.88, "Raise the platform before chasing finer setup balance."),
    _HeuristicRule("bottoming_risk", "rear_wing", "decrease", 0.22, "If the floor is overloading, trim some downforce only after ride height is addressed."),
)

_LEVER_STEP_RULES: dict[str, dict[str, float | str]] = {
    "brake_bias": {"step": 0.3, "digits": 1, "unit": "%"},
    "rear_wing": {"step": 1.0, "digits": 0},
    "front_arb": {"step": 1.0, "digits": 0},
    "rear_arb": {"step": 1.0, "digits": 0},
    "front_spring": {"step": 1.0, "digits": 0},
    "rear_spring": {"step": 1.0, "digits": 0},
    "ride_height": {"step": 1.0, "digits": 0, "unit": " mm"},
    "camber": {"step": 0.2, "digits": 1, "mode": "camber"},
    "toe": {"step": 0.02, "digits": 2},
    "tyre_pressure": {"step": 0.2, "digits": 1, "unit": " psi"},
    "diff": {"step": 5.0, "digits": 0},
    "tc": {"step": 1.0, "digits": 0},
    "abs": {"step": 1.0, "digits": 0},
    "fuel": {"step": 2.0, "digits": 0, "unit": " L"},
}


def _coerce_numeric_value(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in {"on", "true", "yes"}:
        return 1.0
    if lowered in {"off", "false", "no"}:
        return 0.0
    text = text.replace("%", "").replace(",", "")
    try:
        return float(text)
    except Exception:
        return None


def _series(samples: Iterable[TelemetrySample], attr: str) -> list[float]:
    values: list[float] = []
    for sample in samples:
        value = getattr(sample, attr, None)
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            values.append(float(value))
    return values


def _mean(values: Iterable[float]) -> float | None:
    values_list = [float(value) for value in values]
    if not values_list:
        return None
    return sum(values_list) / len(values_list)


def _round_or_none(value: float | None, digits: int = 3) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _unique(values: Iterable[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _match_lever(feature_key: str) -> tuple[str, str] | None:
    compact = feature_key.replace(".", "").replace("_", "")
    for lever_id, label, patterns in _LEVER_PATTERNS:
        if any(pattern in compact for pattern in patterns):
            return lever_id, label
    return None


def _label_for_lever(lever_id: str, feature_key: str) -> str:
    match = _match_lever(feature_key)
    if match is not None:
        return match[1]
    return lever_id.replace("_", " ").title()


def _collect_lever_features(setup_vector: Any) -> dict[str, tuple[str, float | str | None]]:
    lever_features: dict[str, tuple[str, float | str | None]] = {}
    features = {**setup_vector.numeric_features, **setup_vector.categorical_features}
    for feature_key in sorted(features):
        match = _match_lever(feature_key)
        if match is None:
            continue
        lever_id, _ = match
        current = lever_features.get(lever_id)
        if current is None or len(feature_key) < len(current[0]):
            lever_features[lever_id] = (feature_key, features[feature_key])
    return lever_features


def _numeric_value_for_lever(setup_vector: Any, lever_id: str) -> float | None:
    for feature_key, value in setup_vector.numeric_features.items():
        match = _match_lever(feature_key)
        if match is not None and match[0] == lever_id:
            return value
    return None


def _suggest_value(
    *,
    lever_id: str,
    current_value: float | str | None,
    direction: str,
) -> float | str | None:
    if direction == "review":
        return current_value
    numeric = _coerce_numeric_value(current_value)
    if numeric is None:
        return current_value
    rule = _LEVER_STEP_RULES.get(lever_id)
    if rule is None:
        return numeric
    step = float(rule.get("step") or 0.0)
    if step <= 0.0:
        return numeric
    mode = str(rule.get("mode") or "")
    if mode == "camber":
        # More negative camber is usually the useful "increase" direction.
        numeric = numeric - step if direction == "increase" else numeric + step
    else:
        numeric = numeric + step if direction == "increase" else numeric - step
    digits = int(rule.get("digits") or 0)
    return round(numeric, digits)


def _display_recommendation_value(lever_id: str, value: float | str | None) -> str:
    if value is None:
        return "-"
    numeric = _coerce_numeric_value(value)
    if numeric is None:
        return str(value)
    rule = _LEVER_STEP_RULES.get(lever_id) or {}
    digits = int(rule.get("digits") or 0)
    unit = str(rule.get("unit") or "")
    return f"{round(numeric, digits):.{digits}f}{unit}"


def _suggested_display(
    *,
    lever_id: str,
    current_value: float | str | None,
    direction: str,
) -> str:
    suggested = _suggest_value(lever_id=lever_id, current_value=current_value, direction=direction)
    return _display_recommendation_value(lever_id, suggested)


def _diff_hint(
    *,
    lever_id: str,
    current_value: float | str | None,
    direction: str,
) -> str:
    current_numeric = _coerce_numeric_value(current_value)
    suggested_numeric = _coerce_numeric_value(_suggest_value(lever_id=lever_id, current_value=current_value, direction=direction))
    if current_numeric is None or suggested_numeric is None or direction == "review":
        return "Review this lever against the symptom before changing it."
    delta = suggested_numeric - current_numeric
    rule = _LEVER_STEP_RULES.get(lever_id) or {}
    digits = int(rule.get("digits") or 0)
    unit = str(rule.get("unit") or "")
    if digits <= 0:
        delta_text = f"{delta:+.0f}{unit}"
    else:
        delta_text = f"{delta:+.{digits}f}{unit}"
    return f"{delta_text} from current."


def _prior_boost(
    *,
    lever_id: str,
    direction: str,
    current_value: float | str | None,
    issue_tag: str,
) -> float:
    numeric = _coerce_numeric_value(current_value)
    if numeric is None:
        return 0.0
    if lever_id == "rear_wing":
        if direction == "increase" and numeric <= 6.0:
            return 0.12
        if direction == "decrease" and numeric >= 9.0:
            return 0.12
    if lever_id == "brake_bias":
        if direction == "increase" and numeric <= 53.5:
            return 0.10
        if direction == "decrease" and numeric >= 56.0:
            return 0.10
    if lever_id in {"tc", "abs"} and direction == "increase" and numeric <= 4.0:
        return 0.08
    if lever_id == "ride_height" and direction == "increase" and numeric <= 45.0:
        return 0.12
    if lever_id == "tyre_pressure":
        if direction == "decrease" and issue_tag == "tyres_overheated":
            return 0.08
        if direction == "increase" and issue_tag == "tyres_cold":
            return 0.08
    return 0.0


def build_lap_metrics(samples: list[TelemetrySample]) -> dict[str, float | None]:
    speeds = _series(samples, "speed_kph")
    throttles = _series(samples, "throttle_pct")
    brakes = _series(samples, "brake_pct")
    steerings = _series(samples, "steering_deg")
    rpms = _series(samples, "rpm")
    long_g = _series(samples, "long_accel_g")
    lat_g = _series(samples, "lat_accel_g")
    fuels = _series(samples, "fuel_level")
    track_temps = _series(samples, "track_temp_c")
    air_temps = _series(samples, "air_temp_c")
    tyre_temps = []
    for field in ("tyre_temp_lf", "tyre_temp_rf", "tyre_temp_lr", "tyre_temp_rr"):
        tyre_temps.extend(_series(samples, field))
    lap_dist = _series(samples, "lap_dist_pct")

    coast_samples = sum(
        1
        for sample in samples
        if (sample.throttle_pct or 0.0) <= 0.05 and (sample.brake_pct or 0.0) <= 0.05
    )
    overlap_samples = sum(
        1
        for sample in samples
        if (sample.throttle_pct or 0.0) >= 0.05 and (sample.brake_pct or 0.0) >= 0.05
    )
    total_samples = len(samples) or 0

    return {
        "distance_coverage_pct": _round_or_none((max(lap_dist) - min(lap_dist)) if len(lap_dist) >= 2 else None, 4),
        "speed_min_kph": _round_or_none(min(speeds) if speeds else None),
        "speed_mean_kph": _round_or_none(_mean(speeds)),
        "speed_max_kph": _round_or_none(max(speeds) if speeds else None),
        "throttle_mean_pct": _round_or_none(_mean(throttles), 4),
        "brake_mean_pct": _round_or_none(_mean(brakes), 4),
        "brake_peak_pct": _round_or_none(max(brakes) if brakes else None, 4),
        "coast_ratio": _round_or_none((coast_samples / total_samples) if total_samples else None, 4),
        "pedal_overlap_ratio": _round_or_none((overlap_samples / total_samples) if total_samples else None, 4),
        "steering_abs_mean_deg": _round_or_none(_mean(abs(value) for value in steerings)),
        "steering_peak_deg": _round_or_none(max((abs(value) for value in steerings), default=None)),
        "rpm_mean": _round_or_none(_mean(rpms)),
        "rpm_max": _round_or_none(max(rpms) if rpms else None),
        "long_g_peak": _round_or_none(max((abs(value) for value in long_g), default=None), 4),
        "lat_g_peak": _round_or_none(max((abs(value) for value in lat_g), default=None), 4),
        "fuel_used_l": _round_or_none((fuels[0] - fuels[-1]) if len(fuels) >= 2 else None, 4),
        "tyre_temp_mean_c": _round_or_none(_mean(tyre_temps), 4),
        "track_temp_c": _round_or_none(_mean(track_temps), 4),
        "air_temp_c": _round_or_none(_mean(air_temps), 4),
    }


def derive_issue_tags(
    rows: list[Any],
    *,
    setup_vector: Any,
) -> list[str]:
    valid_rows = [
        row
        for row in rows
        if row.lap_time_s is not None and (row.valid_for_analysis or row.clean_lap)
    ]
    analysis_rows = valid_rows or [row for row in rows if row.lap_time_s is not None]
    if not analysis_rows:
        return []

    best_row = min(analysis_rows, key=lambda row: float(row.lap_time_s or 0.0))
    comparison_rows = [row for row in analysis_rows if row.lap_number != best_row.lap_number] or [best_row]
    tags: list[str] = []

    avg_tyre_temp = _mean(row.tyre_temp_mean_c for row in comparison_rows if row.tyre_temp_mean_c is not None)
    if avg_tyre_temp is not None:
        if avg_tyre_temp >= 98.0:
            tags.append("tyres_overheated")
        elif avg_tyre_temp <= 70.0:
            tags.append("tyres_cold")

    avg_brake_peak = _mean(row.brake_peak_pct for row in comparison_rows if row.brake_peak_pct is not None)
    avg_overlap = _mean(row.pedal_overlap_ratio for row in comparison_rows if row.pedal_overlap_ratio is not None)
    if (
        (avg_brake_peak is not None and avg_brake_peak >= 0.94)
        or (avg_overlap is not None and avg_overlap >= 0.09)
        or (
            avg_brake_peak is not None
            and best_row.brake_peak_pct is not None
            and avg_brake_peak - best_row.brake_peak_pct >= 0.08
        )
    ):
        tags.append("braking_instability")

    avg_steering = _mean(row.steering_abs_mean_deg for row in comparison_rows if row.steering_abs_mean_deg is not None)
    avg_speed_min = _mean(row.speed_min_kph for row in comparison_rows if row.speed_min_kph is not None)
    avg_lat_g = _mean(row.lat_g_peak for row in comparison_rows if row.lat_g_peak is not None)
    if (
        avg_steering is not None
        and avg_speed_min is not None
        and best_row.steering_abs_mean_deg is not None
        and best_row.speed_min_kph is not None
        and avg_steering >= best_row.steering_abs_mean_deg + 2.5
        and avg_speed_min <= best_row.speed_min_kph - 4.0
    ) or (
        avg_steering is not None
        and avg_lat_g is not None
        and avg_steering >= 22.0
        and avg_lat_g <= 0.90
    ):
        tags.append("front_limited")

    avg_throttle = _mean(row.throttle_mean_pct for row in comparison_rows if row.throttle_mean_pct is not None)
    avg_long_g = _mean(row.long_g_peak for row in comparison_rows if row.long_g_peak is not None)
    if (
        avg_throttle is not None
        and avg_long_g is not None
        and best_row.long_g_peak is not None
        and avg_throttle >= max(0.34, (best_row.throttle_mean_pct or 0.0) - 0.03)
        and avg_long_g <= best_row.long_g_peak - 0.08
    ):
        tags.append("traction_limited")
        tags.append("rear_limited")

    rear_wing_value = _numeric_value_for_lever(setup_vector, "rear_wing")
    if (
        rear_wing_value is not None
        and rear_wing_value >= 10.0
        and best_row.speed_max_kph is not None
        and best_row.speed_mean_kph is not None
        and best_row.speed_max_kph <= best_row.speed_mean_kph * 1.20
    ):
        tags.append("high_drag_risk")

    ride_height_value = _numeric_value_for_lever(setup_vector, "ride_height")
    if (
        ride_height_value is not None
        and ride_height_value <= 45.0
        and avg_brake_peak is not None
        and avg_brake_peak >= 0.90
        and avg_speed_min is not None
        and avg_speed_min <= 110.0
    ):
        tags.append("bottoming_risk")

    return _unique(tags)


def score_heuristic_candidates(
    setup_vector: Any,
    tags: list[str],
) -> list[Any]:
    from lap_coach_logger.core.setup_coach import SetupRecommendationCandidate

    lever_features = _collect_lever_features(setup_vector)
    if not lever_features:
        return []

    contributions: dict[tuple[str, str], dict[str, Any]] = {}
    for tag in tags:
        for rule in _HEURISTIC_RULES:
            if rule.issue_tag != tag:
                continue
            if rule.lever_id not in lever_features:
                continue
            feature_key, current_value = lever_features[rule.lever_id]
            boost = _prior_boost(
                lever_id=rule.lever_id,
                direction=rule.direction,
                current_value=current_value,
                issue_tag=tag,
            )
            bucket = contributions.setdefault(
                (rule.lever_id, rule.direction),
                {
                    "label": _label_for_lever(rule.lever_id, feature_key),
                    "feature_key": feature_key,
                    "current_value": current_value,
                    "score": 0.0,
                    "reasons": [],
                },
            )
            bucket["score"] = float(bucket["score"]) + rule.weight + boost
            bucket["reasons"].append(f"{tag.replace('_', ' ')}: {rule.rationale}")

    winners: dict[str, tuple[str, dict[str, Any]]] = {}
    for (lever_id, direction), payload in contributions.items():
        current = winners.get(lever_id)
        if current is None or float(payload["score"]) > float(current[1]["score"]):
            winners[lever_id] = (direction, payload)

    ranked: list[SetupRecommendationCandidate] = []
    for lever_id, (direction, payload) in winners.items():
        confidence = min(0.95, round(float(payload["score"]), 2))
        feature_key = str(payload["feature_key"])
        ranked.append(
            SetupRecommendationCandidate(
                lever_id=lever_id,
                label=str(payload["label"]),
                feature_key=feature_key,
                current_value=payload["current_value"],
                current_display=_display_recommendation_value(lever_id, payload["current_value"]),
                direction=direction,
                confidence=confidence,
                rationale=" ".join(_unique(payload["reasons"])[:2]),
                likely_effect=describe_setup_effect(feature_key),
                suggested_value=_suggest_value(
                    lever_id=lever_id,
                    current_value=payload["current_value"],
                    direction=direction,
                ),
                suggested_display=_suggested_display(
                    lever_id=lever_id,
                    current_value=payload["current_value"],
                    direction=direction,
                ),
                diff_hint=_diff_hint(
                    lever_id=lever_id,
                    current_value=payload["current_value"],
                    direction=direction,
                ),
            )
        )

    ranked.sort(key=lambda candidate: (-candidate.confidence, candidate.label))
    return ranked[:6]


_STRING_FIELDS = {
    "timestamp_utc",
    "sim",
    "session_uid",
    "track_name",
    "car_name",
    "session_type",
}
_INT_FIELDS = {"lap_number", "gear"}
_BOOL_FIELDS = {"is_on_track", "is_in_pits"}
_FLOAT_FIELDS = set(TelemetrySample.field_names()) - _STRING_FIELDS - _INT_FIELDS - _BOOL_FIELDS


def _coerce_telemetry_value(field: str, value: Any) -> Any:
    if value is None or value == "":
        return None
    if field in _STRING_FIELDS:
        return str(value)
    if field in _INT_FIELDS:
        try:
            return int(float(value))
        except Exception:
            return None
    if field in _BOOL_FIELDS:
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"true", "1", "yes"}:
            return True
        if text in {"false", "0", "no"}:
            return False
        return None
    if field in _FLOAT_FIELDS:
        try:
            return float(value)
        except Exception:
            return None
    return value


def _coerce_sample_row(row: Mapping[str, Any]) -> TelemetrySample:
    payload: dict[str, Any] = {}
    for field in TelemetrySample.field_names():
        payload[field] = _coerce_telemetry_value(field, row.get(field))
    return TelemetrySample(**payload)


def load_csv_samples(path: Path) -> list[TelemetrySample]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [_coerce_sample_row(row) for row in reader]


def load_parquet_samples(path: Path) -> list[TelemetrySample]:
    table = pq.read_table(path)
    return [_coerce_sample_row(row) for row in table.to_pylist()]


def load_saved_samples(folder: Path, manifest: Mapping[str, Any]) -> list[TelemetrySample]:
    telemetry_name = manifest.get("telemetry_file")
    candidates: list[Path] = []
    if telemetry_name:
        candidates.append(folder / str(telemetry_name))
    candidates.extend([folder / "telemetry.csv", folder / "telemetry.parquet"])

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen or not candidate.exists():
            continue
        seen.add(candidate)
        if candidate.suffix.lower() == ".csv":
            return load_csv_samples(candidate)
        if candidate.suffix.lower() == ".parquet":
            return load_parquet_samples(candidate)
    return []


def write_dataset_csv(path: Path, rows: list[Any]) -> None:
    flattened = [flatten_dataset_row(row) for row in rows]
    columns = set()
    for row in flattened:
        columns.update(row.keys())
    ordered_columns = sorted(columns)

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ordered_columns)
        writer.writeheader()
        for row in flattened:
            writer.writerow(row)


def flatten_dataset_row(row: Any) -> dict[str, Any]:
    payload = row.to_dict()
    numeric_features = dict(payload.pop("setup_numeric_features", {}) or {})
    categorical_features = dict(payload.pop("setup_categorical_features", {}) or {})
    recommendation_seed = dict(payload.pop("recommendation_seed", {}) or {})

    flattened = dict(payload)
    for key, value in sorted(numeric_features.items()):
        flattened[f"setup_num__{key}"] = value
    for key, value in sorted(categorical_features.items()):
        flattened[f"setup_cat__{key}"] = value
    flattened["recommendation_status"] = recommendation_seed.get("status")
    flattened["recommendation_candidate_count"] = len(recommendation_seed.get("candidates") or [])
    flattened["recommendation_issue_tags"] = "|".join(recommendation_seed.get("issue_tags") or [])
    return flattened


def group_samples_by_lap(samples: list[TelemetrySample]) -> dict[int, list[TelemetrySample]]:
    grouped: dict[int, list[TelemetrySample]] = {}
    for sample in samples:
        if sample.lap_number is None:
            continue
        grouped.setdefault(int(sample.lap_number), []).append(sample)
    return grouped


def canonical_feature_key(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = text.replace("[", ".").replace("]", "")
    text = re.sub(r"[^a-z0-9._]+", "_", text)
    text = re.sub(r"_+", "_", text)
    text = re.sub(r"\.+", ".", text)
    return text.strip("._")


def available_levers(
    numeric_features: Mapping[str, float],
    categorical_features: Mapping[str, str],
) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for key in sorted({*numeric_features.keys(), *categorical_features.keys()}):
        lever_match = _match_lever(key)
        if lever_match is None:
            continue
        lever_id, _ = lever_match
        if lever_id in seen:
            continue
        seen.add(lever_id)
        found.append(lever_id)
    return found


def normalize_issue_tags(issue_tags: Iterable[str], issue_aliases: dict[str, str]) -> list[str]:
    normalized: list[str] = []
    for tag in issue_tags:
        raw = str(tag).strip().lower()
        if not raw:
            continue
        compact = re.sub(r"[^a-z0-9]+", "", raw)
        normalized.append(issue_aliases.get(compact, raw.replace(" ", "_").replace("-", "_")))
    return _unique(normalized)


def read_json(path: Path) -> dict[str, Any]:
    payload = read_json_like(path)
    return payload if isinstance(payload, dict) else {}


def read_json_like(path: Path) -> Any:
    if not path.exists():
        return {} if path.suffix.lower() == ".json" else None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {} if path.suffix.lower() == ".json" else None


def best_lap_time(laps: list[dict[str, Any]], *, clean_only: bool) -> float | None:
    candidates = []
    for lap in laps:
        if clean_only and not bool(lap.get("clean_lap")):
            continue
        lap_time = finite_or_none(lap.get("lap_time_s"))
        if lap_time is not None:
            candidates.append(lap_time)
    return min(candidates) if candidates else None


def representative_lap_time(laps: list[dict[str, Any]]) -> float | None:
    candidates = [
        finite_or_none(lap.get("lap_time_s"))
        for lap in laps
        if bool(lap.get("valid_for_analysis"))
    ]
    candidates = [candidate for candidate in candidates if candidate is not None]
    if not candidates:
        return None
    candidates.sort()
    return candidates[len(candidates) // 2]


def finite_or_none(value: object) -> float | None:
    try:
        number = float(value)
    except Exception:
        return None
    return number if math.isfinite(number) else None


def first_finite(*values: object) -> float | None:
    for value in values:
        number = finite_or_none(value)
        if number is not None:
            return number
    return None


def delta(lhs: float | None, rhs: float | None) -> float | None:
    if lhs is None or rhs is None:
        return None
    return _round_or_none(lhs - rhs, 4)


def as_optional_str(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def build_bundle_dataset_rows(
    bundle_dir: Path,
    *,
    manifest: Mapping[str, Any],
    metadata: Mapping[str, Any],
    setup_vector: Any,
) -> list[Any]:
    from lap_coach_logger.core.setup_coach import SetupDatasetRow

    raw_source = manifest.get("raw_source") or {}
    session_block = manifest.get("session") or {}
    session_id = str(manifest.get("session_id") or session_block.get("session_uid") or metadata.get("session_uid") or bundle_dir.name)
    sim = str(raw_source.get("sim_display_name") or raw_source.get("sim_id") or manifest.get("sim_name") or metadata.get("sim") or setup_vector.sim or "Unknown")
    car = as_optional_str(raw_source.get("raw_car") or manifest.get("car_name") or metadata.get("car_name") or setup_vector.car)
    track = as_optional_str(raw_source.get("raw_track") or manifest.get("track_name") or metadata.get("track_name") or setup_vector.track)
    session_type = as_optional_str(raw_source.get("session_type_raw") or manifest.get("session_type") or metadata.get("session_type"))

    samples = load_saved_samples(bundle_dir, manifest)
    if not samples:
        return []
    lap_records = load_or_classify_laps(bundle_dir, samples)
    if not lap_records:
        return []

    lap_samples = group_samples_by_lap(samples)
    best_time = first_finite(manifest.get("best_lap_time_s"), best_lap_time(lap_records, clean_only=False))
    best_clean_time = first_finite(
        manifest.get("best_clean_lap_time_s"),
        best_lap_time(lap_records, clean_only=True),
    )
    rep_time = first_finite(
        manifest.get("representative_lap_time_s"),
        representative_lap_time(lap_records),
    )

    rows: list[SetupDatasetRow] = []
    for lap in lap_records:
        lap_number = int(lap.get("lap_number") or 0)
        lap_time_s = finite_or_none(lap.get("lap_time_s"))
        samples_for_lap = lap_samples.get(lap_number, [])
        metrics = build_lap_metrics(samples_for_lap)
        rows.append(
            SetupDatasetRow(
                session_id=session_id,
                bundle_dir=str(bundle_dir),
                sim=sim,
                car=car,
                track=track,
                session_type=session_type,
                lap_number=lap_number,
                lap_time_s=lap_time_s,
                classification=str(lap.get("classification") or "unknown"),
                clean_lap=bool(lap.get("clean_lap")),
                valid_for_analysis=bool(lap.get("valid_for_analysis")),
                delta_to_best_lap_s=delta(lap_time_s, best_time),
                delta_to_best_clean_lap_s=delta(lap_time_s, best_clean_time),
                delta_to_representative_lap_s=delta(lap_time_s, rep_time),
                sample_count=int(lap.get("sample_count") or len(samples_for_lap)),
                distance_coverage_pct=metrics["distance_coverage_pct"],
                speed_min_kph=metrics["speed_min_kph"],
                speed_mean_kph=metrics["speed_mean_kph"],
                speed_max_kph=metrics["speed_max_kph"],
                throttle_mean_pct=metrics["throttle_mean_pct"],
                brake_mean_pct=metrics["brake_mean_pct"],
                brake_peak_pct=metrics["brake_peak_pct"],
                coast_ratio=metrics["coast_ratio"],
                pedal_overlap_ratio=metrics["pedal_overlap_ratio"],
                steering_abs_mean_deg=metrics["steering_abs_mean_deg"],
                steering_peak_deg=metrics["steering_peak_deg"],
                rpm_mean=metrics["rpm_mean"],
                rpm_max=metrics["rpm_max"],
                long_g_peak=metrics["long_g_peak"],
                lat_g_peak=metrics["lat_g_peak"],
                fuel_used_l=metrics["fuel_used_l"],
                tyre_temp_mean_c=metrics["tyre_temp_mean_c"],
                track_temp_c=first_finite(metrics["track_temp_c"], manifest.get("track_temp_c")),
                air_temp_c=first_finite(metrics["air_temp_c"], manifest.get("air_temp_c")),
                setup_source_path=setup_vector.source_path,
                setup_fingerprint=setup_vector.source_fingerprint,
                setup_feature_count=len(setup_vector.numeric_features),
                setup_numeric_features=dict(setup_vector.numeric_features),
                setup_categorical_features=dict(setup_vector.categorical_features),
                recommendation_seed={},
            )
        )
    return rows


def load_or_classify_laps(bundle_dir: Path, samples: list[TelemetrySample]) -> list[dict[str, Any]]:
    from lap_coach_logger.core.lap_analysis import LapAnalysisConfig, classify_laps

    laps_path = bundle_dir / "laps.json"
    laps = read_json_like(laps_path)
    if isinstance(laps, list) and laps:
        return [dict(item) for item in laps if isinstance(item, Mapping)]

    classified, _ = classify_laps(samples, config=LapAnalysisConfig())
    return [lap.to_dict() for lap in classified]
