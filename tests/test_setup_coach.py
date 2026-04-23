from __future__ import annotations

import csv
import json
from pathlib import Path

from lap_coach_logger.core.setup_coach import (
    analyze_setup_bundle,
    build_recommendation_snapshot,
    build_setup_dataset,
    export_setup_dataset,
    extract_setup_vector,
)
from lap_coach_logger.core.setup_tools import save_setup_to_bundle
from tests.helpers import finalize_session


def test_extract_setup_vector_normalizes_numeric_and_categorical_features(tmp_path: Path) -> None:
    setup_path = tmp_path / "aggressive.json"
    setup_path.write_text(json.dumps(_acc_setup(brake_bias=54, rear_wing=10)), encoding="utf-8")

    vector = extract_setup_vector(
        setup_path,
        sim="ACC",
        car="ferrari_488_gt3",
        track="Spa",
    )

    assert vector is not None
    assert vector.sim == "ACC"
    assert vector.car == "ferrari_488_gt3"
    assert vector.track == "Spa"
    assert vector.numeric_features["advancedsetup.mechanicalbalance.brakebias"] == 54.0
    assert vector.numeric_features["advancedsetup.aerobalance.rearwing"] == 10.0
    assert vector.categorical_features["carname"] == "ferrari_488_gt3"
    assert "brake_bias" in vector.available_levers
    assert vector.source_fingerprint


def test_build_recommendation_snapshot_seeds_candidates_from_setup_vector(tmp_path: Path) -> None:
    setup_path = tmp_path / "aggressive.json"
    setup_path.write_text(json.dumps(_acc_setup(brake_bias=54, rear_wing=10)), encoding="utf-8")
    vector = extract_setup_vector(setup_path, sim="ACC")

    snapshot = build_recommendation_snapshot(vector, issue_tags=["entry understeer", "brake instability"])

    assert snapshot.status == "heuristic_scored"
    assert snapshot.issue_tags == ["front_limited", "braking_instability"]
    lever_ids = {candidate.lever_id for candidate in snapshot.candidates}
    assert "brake_bias" in lever_ids
    assert "rear_wing" in lever_ids
    assert any(candidate.confidence > 0.0 for candidate in snapshot.candidates)
    brake_bias = next(candidate for candidate in snapshot.candidates if candidate.lever_id == "brake_bias")
    assert brake_bias.current_display
    assert brake_bias.suggested_display
    assert brake_bias.diff_hint
    assert snapshot.notes


def test_build_setup_dataset_uses_embedded_setup_files_and_exports_csv(tmp_path: Path) -> None:
    output_root = tmp_path / "sessions"
    output_root.mkdir()
    bundle_dir = finalize_session(
        output_root,
        sim="ACC",
        track="Spa",
        car="ferrari_488_gt3",
        session_uid="setup-dataset",
    )

    setup_path = tmp_path / "aggressive.json"
    setup_path.write_text(json.dumps(_acc_setup(brake_bias=54, rear_wing=10)), encoding="utf-8")
    save_setup_to_bundle(setup_path, bundle_dir)

    dataset = build_setup_dataset(output_root)

    assert dataset.session_count == 1
    assert dataset.sessions_with_setup == 1
    assert dataset.sessions_missing_setup == 0
    assert dataset.lap_row_count >= 1

    row = dataset.rows[0]
    assert row.sim == "ACC"
    assert row.track == "Spa"
    assert row.setup_feature_count >= 2
    assert row.setup_numeric_features["advancedsetup.mechanicalbalance.brakebias"] == 54.0
    assert row.recommendation_seed["status"] in {"foundation_only", "heuristic_scored"}
    if row.recommendation_seed["candidates"]:
        assert row.recommendation_seed["candidates"][0].get("suggested_display") or row.recommendation_seed["candidates"][0].get("diff_hint")
    assert row.speed_mean_kph is not None
    assert row.delta_to_best_lap_s is not None

    export_path = tmp_path / "setup_dataset.csv"
    export_setup_dataset(output_root, export_path)

    assert export_path.exists()
    with export_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    assert rows
    assert "setup_num__advancedsetup.mechanicalbalance.brakebias" in reader.fieldnames
    assert rows[0]["recommendation_status"] in {"foundation_only", "heuristic_scored"}


def test_analyze_setup_bundle_scores_brake_and_balance_recommendations(tmp_path: Path) -> None:
    output_root = tmp_path / "sessions"
    output_root.mkdir()
    bundle_dir = finalize_session(
        output_root,
        sim="ACC",
        track="Spa",
        car="ferrari_488_gt3",
        session_uid="bundle-analysis",
    )

    setup_path = tmp_path / "aggressive.json"
    setup_path.write_text(json.dumps(_acc_setup(brake_bias=57, rear_wing=11)), encoding="utf-8")
    save_setup_to_bundle(setup_path, bundle_dir)

    snapshot = analyze_setup_bundle(bundle_dir, issue_tags=["bottoming risk", "entry understeer"])

    assert snapshot.status == "heuristic_scored"
    assert "front_limited" in snapshot.issue_tags
    assert "bottoming_risk" in snapshot.issue_tags
    lever_ids = [candidate.lever_id for candidate in snapshot.candidates]
    assert "brake_bias" in lever_ids
    assert "ride_height" in lever_ids or "rear_wing" in lever_ids


def _acc_setup(*, brake_bias: int, rear_wing: int) -> dict[str, object]:
    return {
        "carName": "ferrari_488_gt3",
        "basicSetup": {
            "strategy": {
                "fuel": 36,
                "tc1": 3,
            }
        },
        "advancedSetup": {
            "mechanicalBalance": {
                "brakeBias": brake_bias,
            },
            "aeroBalance": {
                "rearWing": rear_wing,
            },
        },
    }
