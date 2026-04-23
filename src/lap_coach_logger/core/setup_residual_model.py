"""Lightweight local residual model for setup-coach refinement.

The deterministic heuristic engine remains the primary recommendation
source. This module trains and serves a tiny, dependency-free residual
model that looks at nearby historical lap/setup examples and refines the
confidence of those heuristic candidates.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from lap_coach_logger.core.setup_coach import (
    SetupDatasetRow,
    SetupRecommendationCandidate,
    SetupRecommendationSnapshot,
    _match_lever,
    build_setup_dataset,
)

MODEL_VERSION = "1"
DEFAULT_CONTEXT_FIELDS = (
    "speed_min_kph",
    "speed_mean_kph",
    "speed_max_kph",
    "throttle_mean_pct",
    "brake_mean_pct",
    "brake_peak_pct",
    "coast_ratio",
    "pedal_overlap_ratio",
    "steering_abs_mean_deg",
    "rpm_mean",
    "long_g_peak",
    "lat_g_peak",
    "fuel_used_l",
    "tyre_temp_mean_c",
    "track_temp_c",
    "air_temp_c",
)


@dataclass(slots=True)
class ResidualExample:
    sim: str
    car: str | None
    track: str | None
    session_id: str
    lap_number: int
    target_delta_s: float
    context: dict[str, float] = field(default_factory=dict)
    setup_features: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ResidualModelArtifact:
    version: str
    created_at_utc: str
    output_root: str
    context_fields: list[str]
    example_count: int
    stats: dict[str, dict[str, float]]
    examples: list[ResidualExample] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["examples"] = [example.to_dict() for example in self.examples]
        return payload


@dataclass(slots=True)
class ResidualCandidateAdjustment:
    lever_id: str
    direction: str
    confidence_delta: float
    expected_delta_s: float | None
    support_count: int
    note: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def train_residual_model(
    output_root: str | Path,
    export_path: str | Path,
    *,
    context_fields: Iterable[str] = DEFAULT_CONTEXT_FIELDS,
) -> ResidualModelArtifact:
    fields = [str(field) for field in context_fields]
    dataset = build_setup_dataset(output_root)
    examples = build_residual_examples(dataset.rows, context_fields=fields)
    stats = _compute_stats(examples, fields)
    artifact = ResidualModelArtifact(
        version=MODEL_VERSION,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        output_root=str(Path(output_root).expanduser().resolve()),
        context_fields=fields,
        example_count=len(examples),
        stats=stats,
        examples=examples,
    )
    target = Path(export_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(artifact.to_dict(), indent=2), encoding="utf-8")
    return artifact


def build_residual_examples(
    rows: Iterable[SetupDatasetRow],
    *,
    context_fields: Iterable[str] = DEFAULT_CONTEXT_FIELDS,
) -> list[ResidualExample]:
    fields = [str(field) for field in context_fields]
    examples: list[ResidualExample] = []
    for row in rows:
        target = row.delta_to_best_clean_lap_s
        if target is None:
            target = row.delta_to_best_lap_s
        if target is None or target < 0.0:
            continue
        context = {
            field: float(value)
            for field in fields
            if (value := getattr(row, field, None)) is not None
        }
        if not context:
            continue
        examples.append(
            ResidualExample(
                sim=row.sim,
                car=row.car,
                track=row.track,
                session_id=row.session_id,
                lap_number=row.lap_number,
                target_delta_s=float(target),
                context=context,
                setup_features=dict(row.setup_numeric_features),
            )
        )
    return examples


def load_residual_model(path: str | Path) -> ResidualModelArtifact:
    payload = json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))
    examples = [ResidualExample(**dict(item)) for item in payload.get("examples") or []]
    return ResidualModelArtifact(
        version=str(payload.get("version") or MODEL_VERSION),
        created_at_utc=str(payload.get("created_at_utc") or ""),
        output_root=str(payload.get("output_root") or ""),
        context_fields=[str(field) for field in payload.get("context_fields") or []],
        example_count=int(payload.get("example_count") or len(examples)),
        stats={str(key): dict(value) for key, value in dict(payload.get("stats") or {}).items()},
        examples=examples,
    )


def refine_recommendation_snapshot(
    snapshot: SetupRecommendationSnapshot,
    rows: Iterable[SetupDatasetRow],
    model: ResidualModelArtifact,
) -> tuple[SetupRecommendationSnapshot, list[ResidualCandidateAdjustment]]:
    candidates = list(snapshot.candidates)
    if not candidates:
        return snapshot, []

    reference_row = _select_reference_row(rows)
    if reference_row is None:
        return snapshot, []

    adjusted_candidates: list[SetupRecommendationCandidate] = []
    adjustments: list[ResidualCandidateAdjustment] = []
    for candidate in candidates:
        adjustment = score_candidate_with_model(
            model,
            row=reference_row,
            lever_id=candidate.lever_id,
            direction=candidate.direction,
        )
        if adjustment is None:
            adjusted_candidates.append(candidate)
            continue

        new_confidence = max(0.0, min(0.99, candidate.confidence + adjustment.confidence_delta))
        rationale = f"{candidate.rationale} {adjustment.note}".strip()
        adjusted_candidates.append(
            SetupRecommendationCandidate(
                lever_id=candidate.lever_id,
                label=candidate.label,
                feature_key=candidate.feature_key,
                current_value=candidate.current_value,
                current_display=candidate.current_display,
                direction=candidate.direction,
                confidence=round(new_confidence, 2),
                rationale=rationale,
                likely_effect=candidate.likely_effect,
                suggested_value=candidate.suggested_value,
                suggested_display=candidate.suggested_display,
                diff_hint=candidate.diff_hint,
            )
        )
        adjustments.append(adjustment)

    adjusted_candidates.sort(key=lambda item: (-item.confidence, item.label))
    notes = list(snapshot.notes)
    if adjustments:
        notes.append("Residual model refinement is active for this bundle.")
    refined = SetupRecommendationSnapshot(
        status=snapshot.status if adjustments else snapshot.status,
        sim=snapshot.sim,
        car=snapshot.car,
        track=snapshot.track,
        issue_tags=list(snapshot.issue_tags),
        candidates=adjusted_candidates,
        notes=notes,
    )
    return refined, adjustments


def refine_bundle_snapshot(
    snapshot: SetupRecommendationSnapshot,
    bundle_dir: str | Path,
    model: ResidualModelArtifact,
) -> tuple[SetupRecommendationSnapshot, list[ResidualCandidateAdjustment]]:
    bundle = Path(bundle_dir).expanduser().resolve()
    dataset = build_setup_dataset(bundle.parent, include_non_analysis_laps=True)
    rows = [row for row in dataset.rows if Path(row.bundle_dir).resolve() == bundle]
    return refine_recommendation_snapshot(snapshot, rows, model)


def score_candidate_with_model(
    model: ResidualModelArtifact,
    *,
    row: SetupDatasetRow,
    lever_id: str,
    direction: str,
    k: int = 12,
) -> ResidualCandidateAdjustment | None:
    lever_feature_key, current_value = _resolve_lever_value(row, lever_id)
    if lever_feature_key is None or current_value is None:
        return None

    pool = _matching_examples(model.examples, row)
    if len(pool) < 4:
        return None

    ranked = sorted(pool, key=lambda example: _distance(row, example, model))
    baseline_neighbors = ranked[: max(k, 4)]
    baseline_delta = _weighted_mean(
        [(example.target_delta_s, _weight(_distance(row, example, model))) for example in baseline_neighbors]
    )
    directed_neighbors = [
        example
        for example in ranked[: max(k * 3, 24)]
        if _direction_matches(example.setup_features.get(lever_feature_key), current_value, direction)
    ]
    if len(directed_neighbors) < 2:
        return None
    directed_neighbors = directed_neighbors[:k]
    directed_delta = _weighted_mean(
        [(example.target_delta_s, _weight(_distance(row, example, model))) for example in directed_neighbors]
    )
    improvement = baseline_delta - directed_delta
    if improvement <= 0.01:
        confidence_delta = max(-0.08, round(improvement * 0.18, 2))
    else:
        confidence_delta = min(0.20, round(improvement * 0.35, 2))
    if abs(confidence_delta) < 0.01:
        return None

    direction_word = {
        "increase": "higher",
        "decrease": "lower",
        "review": "different",
    }.get(direction, direction)
    note = (
        f"Residual model saw {len(directed_neighbors)} nearby examples where {lever_id.replace('_', ' ')} "
        f"was {direction_word}, shifting expected lap delta by {improvement:+.2f}s."
    )
    return ResidualCandidateAdjustment(
        lever_id=lever_id,
        direction=direction,
        confidence_delta=confidence_delta,
        expected_delta_s=round(improvement, 3),
        support_count=len(directed_neighbors),
        note=note,
    )


def print_residual_model_result(artifact: ResidualModelArtifact, export_path: str | Path) -> None:
    print(f"Residual model exported: {export_path}")
    print(f"Examples: {artifact.example_count}")
    print("Context fields: " + ", ".join(artifact.context_fields))


def _compute_stats(
    examples: Iterable[ResidualExample],
    context_fields: Iterable[str],
) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    example_list = list(examples)
    for field in context_fields:
        values = [example.context[field] for example in example_list if field in example.context]
        if not values:
            continue
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        stats[str(field)] = {"mean": mean, "std": max(variance**0.5, 1e-6)}
    return stats


def _select_reference_row(rows: Iterable[SetupDatasetRow]) -> SetupDatasetRow | None:
    candidates = [row for row in rows if row.valid_for_analysis and row.lap_time_s is not None]
    if not candidates:
        candidates = [row for row in rows if row.lap_time_s is not None]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda row: float(row.delta_to_best_clean_lap_s or row.delta_to_best_lap_s or 0.0),
    )


def _resolve_lever_value(row: SetupDatasetRow, lever_id: str) -> tuple[str | None, float | None]:
    for key, value in sorted(row.setup_numeric_features.items()):
        match = _match_lever(key)
        if match is not None and match[0] == lever_id:
            return key, value
    return None, None


def _matching_examples(
    examples: Iterable[ResidualExample],
    row: SetupDatasetRow,
) -> list[ResidualExample]:
    same_sim_car_track = [
        example
        for example in examples
        if example.sim == row.sim and example.car == row.car and example.track == row.track
    ]
    if len(same_sim_car_track) >= 4:
        return same_sim_car_track
    same_sim_car = [
        example
        for example in examples
        if example.sim == row.sim and example.car == row.car
    ]
    if len(same_sim_car) >= 4:
        return same_sim_car
    same_sim = [example for example in examples if example.sim == row.sim]
    return same_sim if len(same_sim) >= 4 else list(examples)


def _distance(row: SetupDatasetRow, example: ResidualExample, model: ResidualModelArtifact) -> float:
    total = 0.0
    count = 0
    for field in model.context_fields:
        row_value = getattr(row, field, None)
        example_value = example.context.get(field)
        if row_value is None or example_value is None:
            continue
        stats = model.stats.get(field) or {"mean": 0.0, "std": 1.0}
        scale = max(float(stats.get("std") or 1.0), 1e-6)
        diff = (float(row_value) - float(example_value)) / scale
        total += diff * diff
        count += 1
    if row.sim != example.sim:
        total += 4.0
        count += 1
    if row.car and example.car and row.car != example.car:
        total += 1.5
        count += 1
    if row.track and example.track and row.track != example.track:
        total += 1.0
        count += 1
    if count == 0:
        return 999.0
    return math.sqrt(total / count)


def _weight(distance: float) -> float:
    return 1.0 / (1.0 + distance)


def _weighted_mean(pairs: Iterable[tuple[float, float]]) -> float:
    total_weight = 0.0
    total_value = 0.0
    for value, weight in pairs:
        total_value += float(value) * float(weight)
        total_weight += float(weight)
    return total_value / total_weight if total_weight > 0 else 0.0


def _direction_matches(example_value: float | None, current_value: float, direction: str) -> bool:
    if example_value is None:
        return False
    if direction == "increase":
        return float(example_value) > current_value
    if direction == "decrease":
        return float(example_value) < current_value
    return abs(float(example_value) - current_value) >= 0.5
