"""Local setup coach data foundations and baseline heuristics.

This module turns native setup files plus saved session bundles into a
machine-friendly local dataset. It intentionally stops short of scoring
heavy ML predictions. The baseline here is a deterministic setup coach:
structured setup vectors, saved-lap feature rows, and a lightweight
heuristic engine that can score candidate levers before residual ML is
added.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from lap_coach_logger.core.setup_calculations import (
    _coerce_numeric_value,
    _display_recommendation_value,
    _match_lever,
    _round_or_none,
    _unique,
    as_optional_str as _as_optional_str,
    available_levers as _available_levers,
    build_bundle_dataset_rows as _build_bundle_dataset_rows,
    canonical_feature_key as _canonical_feature_key,
    derive_issue_tags as _derive_issue_tags,
    normalize_issue_tags as _normalize_issue_tags_impl,
    read_json as _read_json,
    score_heuristic_candidates as _score_heuristic_candidates,
    write_dataset_csv as _write_dataset_csv_impl,
)
from lap_coach_logger.core.setup_tools import (
    describe_setup_effect,
    file_fingerprint,
    read_setup_rows,
)

_ISSUE_ALIASES: dict[str, str] = {
    "entryundersteer": "front_limited",
    "understeer": "front_limited",
    "frontlimited": "front_limited",
    "highspeedundersteer": "front_limited",
    "rearlimited": "rear_limited",
    "oversteer": "rear_limited",
    "rearinstability": "rear_limited",
    "tractionlimited": "traction_limited",
    "wheelspin": "traction_limited",
    "brakinginstability": "braking_instability",
    "brakeinstability": "braking_instability",
    "lockups": "braking_instability",
    "brakelockups": "braking_instability",
    "tyresoverheated": "tyres_overheated",
    "tiresoverheated": "tyres_overheated",
    "tyrescold": "tyres_cold",
    "tirescold": "tyres_cold",
    "highdragrisk": "high_drag_risk",
    "draglimited": "high_drag_risk",
    "bottomingrisk": "bottoming_risk",
    "platformsensitive": "bottoming_risk",
}


@dataclass(slots=True)
class SetupVector:
    sim: str
    source_path: str
    source_name: str
    source_format: str
    source_fingerprint: str
    car: str | None = None
    track: str | None = None
    row_count: int = 0
    numeric_features: dict[str, float] = field(default_factory=dict)
    categorical_features: dict[str, str] = field(default_factory=dict)
    available_levers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SetupRecommendationCandidate:
    lever_id: str
    label: str
    feature_key: str
    current_value: float | str | None
    current_display: str | None
    direction: str
    confidence: float
    rationale: str
    likely_effect: str
    suggested_value: float | str | None = None
    suggested_display: str | None = None
    diff_hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SetupRecommendationSnapshot:
    status: str
    sim: str
    car: str | None = None
    track: str | None = None
    issue_tags: list[str] = field(default_factory=list)
    candidates: list[SetupRecommendationCandidate] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["candidates"] = [candidate.to_dict() for candidate in self.candidates]
        return payload


@dataclass(slots=True)
class SetupDatasetRow:
    session_id: str
    bundle_dir: str
    sim: str
    car: str | None
    track: str | None
    session_type: str | None
    lap_number: int
    lap_time_s: float | None
    classification: str
    clean_lap: bool
    valid_for_analysis: bool
    delta_to_best_lap_s: float | None
    delta_to_best_clean_lap_s: float | None
    delta_to_representative_lap_s: float | None
    sample_count: int
    distance_coverage_pct: float | None
    speed_min_kph: float | None
    speed_mean_kph: float | None
    speed_max_kph: float | None
    throttle_mean_pct: float | None
    brake_mean_pct: float | None
    brake_peak_pct: float | None
    coast_ratio: float | None
    pedal_overlap_ratio: float | None
    steering_abs_mean_deg: float | None
    steering_peak_deg: float | None
    rpm_mean: float | None
    rpm_max: float | None
    long_g_peak: float | None
    lat_g_peak: float | None
    fuel_used_l: float | None
    tyre_temp_mean_c: float | None
    track_temp_c: float | None
    air_temp_c: float | None
    setup_source_path: str
    setup_fingerprint: str
    setup_feature_count: int
    setup_numeric_features: dict[str, float] = field(default_factory=dict)
    setup_categorical_features: dict[str, str] = field(default_factory=dict)
    recommendation_seed: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SetupDatasetBuild:
    output_root: str
    session_count: int = 0
    sessions_with_setup: int = 0
    sessions_missing_setup: int = 0
    sessions_unreadable: int = 0
    lap_row_count: int = 0
    rows: list[SetupDatasetRow] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["rows"] = [row.to_dict() for row in self.rows]
        return payload


def extract_setup_vector(
    path: str | Path,
    *,
    sim: str | None = None,
    format_name: str | None = None,
    car: str | None = None,
    track: str | None = None,
) -> SetupVector | None:
    setup_path = Path(path).expanduser().resolve()
    if not setup_path.exists() or not setup_path.is_file():
        return None

    rows = read_setup_rows(setup_path, format_name or setup_path.suffix.lstrip("."))
    if not rows:
        return None

    numeric_features: dict[str, float] = {}
    categorical_features: dict[str, str] = {}
    for row in rows:
        key = _canonical_feature_key(row.get("key"))
        if not key:
            continue
        raw_value = row.get("value")
        numeric_value = _coerce_numeric_value(raw_value)
        if numeric_value is not None:
            numeric_features[key] = numeric_value
            continue
        display_value = str(row.get("display") or raw_value or "").strip()
        if display_value:
            categorical_features[key] = display_value

    available_levers = _available_levers(numeric_features, categorical_features)
    return SetupVector(
        sim=str(sim or "Unknown"),
        source_path=str(setup_path),
        source_name=setup_path.name,
        source_format=(format_name or setup_path.suffix.lstrip(".") or "bin").upper(),
        source_fingerprint=file_fingerprint(setup_path),
        car=car,
        track=track,
        row_count=len(rows),
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        available_levers=available_levers,
    )


def build_recommendation_snapshot(
    setup_vector: SetupVector | None,
    *,
    issue_tags: Iterable[str] = (),
) -> SetupRecommendationSnapshot:
    tags = _normalize_issue_tags(issue_tags)
    if setup_vector is None:
        return SetupRecommendationSnapshot(
            status="no_setup",
            sim="-",
            issue_tags=tags,
            notes=["No structured setup vector is available for this session."],
        )

    features = {**setup_vector.numeric_features, **setup_vector.categorical_features}
    if not tags:
        candidates: list[SetupRecommendationCandidate] = []
        seen: set[str] = set()
        for feature_key in sorted(features):
            lever_match = _match_lever(feature_key)
            if lever_match is None:
                continue
            lever_id, label = lever_match
            if lever_id in seen:
                continue
            seen.add(lever_id)
            candidates.append(
                SetupRecommendationCandidate(
                    lever_id=lever_id,
                    label=label,
                    feature_key=feature_key,
                    current_value=features.get(feature_key),
                    current_display=_display_recommendation_value(lever_id, features.get(feature_key)),
                    direction="review",
                    confidence=0.0,
                    rationale="Foundation only: this extracted lever is available for later heuristic or residual-model scoring.",
                    likely_effect=describe_setup_effect(feature_key),
                    suggested_value=features.get(feature_key),
                    suggested_display=_display_recommendation_value(lever_id, features.get(feature_key)),
                    diff_hint="No scored step yet.",
                )
            )

        notes = [
            "This payload is a stable recommendation schema seed. Direction and confidence remain unscored until issue evidence is available.",
        ]
        if not candidates:
            notes.append("The setup parsed successfully, but no first-order lever patterns were recognized yet.")

        return SetupRecommendationSnapshot(
            status="foundation_only",
            sim=setup_vector.sim,
            car=setup_vector.car,
            track=setup_vector.track,
            issue_tags=tags,
            candidates=candidates,
            notes=notes,
        )

    candidates = _score_heuristic_candidates(setup_vector, tags)
    notes = [
        "Recommendations are deterministic setup heuristics derived from saved-lap evidence and lever-effect priors.",
    ]
    if not candidates:
        notes.append("Issue evidence was found, but none of the parsed setup levers matched the current heuristic rule set.")
    return SetupRecommendationSnapshot(
        status="heuristic_scored",
        sim=setup_vector.sim,
        car=setup_vector.car,
        track=setup_vector.track,
        issue_tags=tags,
        candidates=candidates,
        notes=notes,
    )


def analyze_setup_bundle(
    bundle_dir: str | Path,
    *,
    issue_tags: Iterable[str] = (),
) -> SetupRecommendationSnapshot:
    bundle = Path(bundle_dir).expanduser().resolve()
    manifest = _read_json(bundle / "session.json")
    raw_source = manifest.get("raw_source") or {}
    sim = str(raw_source.get("sim_display_name") or raw_source.get("sim_id") or manifest.get("sim_name") or "Unknown")
    car = _as_optional_str(raw_source.get("raw_car") or manifest.get("car_name"))
    track = _as_optional_str(raw_source.get("raw_track") or manifest.get("track_name"))
    setup_path = discover_embedded_setup_file(bundle)
    if setup_path is None:
        return SetupRecommendationSnapshot(
            status="no_setup",
            sim=sim,
            car=car,
            track=track,
            notes=["No embedded setup file was found in this saved session bundle."],
        )

    setup_vector = extract_setup_vector(setup_path, sim=sim, car=car, track=track)
    if setup_vector is None:
        return SetupRecommendationSnapshot(
            status="no_setup",
            sim=sim,
            car=car,
            track=track,
            notes=["An embedded setup file exists, but it could not be parsed into a structured vector."],
        )

    bundle_rows = _build_bundle_dataset_rows(bundle, manifest=manifest, metadata={}, setup_vector=setup_vector)
    derived_tags = _derive_issue_tags(bundle_rows, setup_vector=setup_vector)
    merged_tags = [*derived_tags, *_normalize_issue_tags(issue_tags)]
    snapshot = build_recommendation_snapshot(setup_vector, issue_tags=merged_tags)
    if not bundle_rows:
        snapshot.notes.append("No valid lap rows were available, so only setup priors were used.")
    return snapshot


def print_setup_bundle_analysis_result(snapshot: SetupRecommendationSnapshot, bundle_dir: str | Path) -> None:
    print(f"Setup analysis: {bundle_dir}")
    print(f"Status: {snapshot.status}")
    if snapshot.issue_tags:
        print("Issue tags: " + ", ".join(snapshot.issue_tags))
    if not snapshot.candidates:
        for note in snapshot.notes:
            print(f"- {note}")
        return
    for candidate in snapshot.candidates[:6]:
        suggested = f" -> {candidate.suggested_display}" if candidate.suggested_display else ""
        print(
            f"- {candidate.label}: {candidate.direction} "
            f"(confidence {candidate.confidence:.2f}){suggested}"
        )
        print(f"  Why: {candidate.rationale}")
        if candidate.diff_hint:
            print(f"  Change: {candidate.diff_hint}")
        print(f"  Effect: {candidate.likely_effect}")


def build_setup_dataset(
    output_root: str | Path,
    *,
    include_non_analysis_laps: bool = False,
) -> SetupDatasetBuild:
    root = Path(output_root).expanduser().resolve()
    dataset = SetupDatasetBuild(output_root=str(root))
    if not root.exists():
        return dataset

    for bundle_dir in _candidate_bundle_dirs(root):
        dataset.session_count += 1
        manifest = _read_json(bundle_dir / "session.json")
        raw_source = manifest.get("raw_source") or {}
        session_block = manifest.get("session") or {}
        session_id = str(manifest.get("session_id") or session_block.get("session_uid") or bundle_dir.name)
        sim = str(raw_source.get("sim_display_name") or raw_source.get("sim_id") or manifest.get("sim_name") or "Unknown")
        car = _as_optional_str(raw_source.get("raw_car") or manifest.get("car_name"))
        track = _as_optional_str(raw_source.get("raw_track") or manifest.get("track_name"))
        session_type = _as_optional_str(raw_source.get("session_type_raw") or manifest.get("session_type"))

        setup_path = discover_embedded_setup_file(bundle_dir)
        if setup_path is None:
            dataset.sessions_missing_setup += 1
            continue

        setup_vector = extract_setup_vector(setup_path, sim=sim, car=car, track=track)
        if setup_vector is None:
            dataset.sessions_unreadable += 1
            continue

        dataset.sessions_with_setup += 1
        bundle_rows = _build_bundle_dataset_rows(bundle_dir, manifest=manifest, metadata={}, setup_vector=setup_vector)
        if not bundle_rows:
            continue

        if not include_non_analysis_laps:
            bundle_rows = [row for row in bundle_rows if row.valid_for_analysis]
        if not bundle_rows:
            continue

        issue_tags = _derive_issue_tags(bundle_rows, setup_vector=setup_vector)
        recommendation = build_recommendation_snapshot(setup_vector, issue_tags=issue_tags).to_dict()
        for row in bundle_rows:
            row.recommendation_seed = recommendation
            dataset.rows.append(row)

    dataset.lap_row_count = len(dataset.rows)
    return dataset


def export_setup_dataset(
    output_root: str | Path,
    export_path: str | Path,
    *,
    include_non_analysis_laps: bool = False,
) -> SetupDatasetBuild:
    dataset = build_setup_dataset(
        output_root,
        include_non_analysis_laps=include_non_analysis_laps,
    )
    target = Path(export_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.suffix.lower() == ".csv":
        _write_dataset_csv_impl(target, dataset.rows)
    else:
        target.write_text(json.dumps(dataset.to_dict(), indent=2), encoding="utf-8")
    return dataset


def print_setup_dataset_result(dataset: SetupDatasetBuild, export_path: str | Path) -> None:
    print(f"Setup dataset exported: {export_path}")
    print(
        "Sessions scanned: "
        f"{dataset.session_count} total, "
        f"{dataset.sessions_with_setup} with embedded setups, "
        f"{dataset.sessions_missing_setup} without setup, "
        f"{dataset.sessions_unreadable} unreadable"
    )
    print(f"Lap rows exported: {dataset.lap_row_count}")


def discover_embedded_setup_file(bundle_dir: str | Path) -> Path | None:
    directory = Path(bundle_dir)
    candidates = [path for path in directory.glob("setup__*") if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_ctime, path.stat().st_mtime, path.name))


def _candidate_bundle_dirs(output_root: Path) -> list[Path]:
    directories: list[Path] = []
    for path in output_root.iterdir():
        if not path.is_dir() or path.name.startswith("_tmp_"):
            continue
        if (path / "session.json").exists() or (path / "metadata.json").exists():
            directories.append(path)
    directories.sort(key=lambda path: path.name)
    return directories


def _normalize_issue_tags(issue_tags: Iterable[str]) -> list[str]:
    return _normalize_issue_tags_impl(issue_tags, _ISSUE_ALIASES)
