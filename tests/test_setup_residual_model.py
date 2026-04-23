from __future__ import annotations

import json
from pathlib import Path

from lap_coach_logger.core.setup_coach import (
    SetupDatasetRow,
    SetupRecommendationCandidate,
    SetupRecommendationSnapshot,
)
from lap_coach_logger.core.setup_residual_model import (
    ResidualExample,
    ResidualModelArtifact,
    load_residual_model,
    refine_recommendation_snapshot,
    train_residual_model,
)
from lap_coach_logger.core.setup_tools import save_setup_to_bundle
from tests.helpers import finalize_session


def test_train_residual_model_exports_json_artifact(tmp_path: Path) -> None:
    output_root = tmp_path / "sessions"
    output_root.mkdir()
    bundle_dir = finalize_session(
        output_root,
        sim="ACC",
        track="Spa",
        car="ferrari_488_gt3",
        session_uid="residual-train",
    )
    setup_path = tmp_path / "aggressive.json"
    setup_path.write_text(json.dumps(_acc_setup(brake_bias=54, rear_wing=10)), encoding="utf-8")
    save_setup_to_bundle(setup_path, bundle_dir)

    model_path = tmp_path / "setup_residual_model.json"
    artifact = train_residual_model(output_root, model_path)
    loaded = load_residual_model(model_path)

    assert artifact.example_count > 0
    assert model_path.exists()
    assert loaded.example_count == artifact.example_count
    assert "speed_mean_kph" in loaded.context_fields


def test_refine_recommendation_snapshot_boosts_supported_direction() -> None:
    current_row = _make_row(brake_bias=57.0, delta=0.42, speed_mean=131.0, steering=24.0)
    rows = [current_row]
    snapshot = SetupRecommendationSnapshot(
        status="heuristic_scored",
        sim="ACC",
        car="ferrari_488_gt3",
        track="Spa",
        issue_tags=["front_limited"],
        candidates=[
            SetupRecommendationCandidate(
                lever_id="brake_bias",
                label="Brake bias",
                feature_key="advancedsetup.mechanicalbalance.brakebias",
                current_value=57.0,
                current_display="57.0%",
                direction="decrease",
                confidence=0.55,
                rationale="Move brake bias rearward if the car is reluctant on entry.",
                likely_effect="Brake changes trade stopping confidence, temperature control, and lockup risk.",
                suggested_value=56.7,
                suggested_display="56.7%",
                diff_hint="-0.3% from current.",
            )
        ],
        notes=[],
    )
    model = ResidualModelArtifact(
        version="1",
        created_at_utc="2026-03-31T00:00:00+00:00",
        output_root="C:\\temp",
        context_fields=["speed_mean_kph", "steering_abs_mean_deg"],
        example_count=4,
        stats={
            "speed_mean_kph": {"mean": 131.0, "std": 2.0},
            "steering_abs_mean_deg": {"mean": 23.0, "std": 2.0},
        },
        examples=[
            ResidualExample(
                sim="ACC",
                car="ferrari_488_gt3",
                track="Spa",
                session_id="a",
                lap_number=2,
                target_delta_s=0.05,
                context={"speed_mean_kph": 130.5, "steering_abs_mean_deg": 23.0},
                setup_features={"advancedsetup.mechanicalbalance.brakebias": 53.0},
            ),
            ResidualExample(
                sim="ACC",
                car="ferrari_488_gt3",
                track="Spa",
                session_id="b",
                lap_number=2,
                target_delta_s=0.08,
                context={"speed_mean_kph": 131.3, "steering_abs_mean_deg": 24.0},
                setup_features={"advancedsetup.mechanicalbalance.brakebias": 54.0},
            ),
            ResidualExample(
                sim="ACC",
                car="ferrari_488_gt3",
                track="Spa",
                session_id="c",
                lap_number=2,
                target_delta_s=0.36,
                context={"speed_mean_kph": 131.2, "steering_abs_mean_deg": 24.2},
                setup_features={"advancedsetup.mechanicalbalance.brakebias": 57.0},
            ),
            ResidualExample(
                sim="ACC",
                car="ferrari_488_gt3",
                track="Spa",
                session_id="d",
                lap_number=2,
                target_delta_s=0.41,
                context={"speed_mean_kph": 130.8, "steering_abs_mean_deg": 24.4},
                setup_features={"advancedsetup.mechanicalbalance.brakebias": 58.0},
            ),
        ],
    )

    refined, adjustments = refine_recommendation_snapshot(snapshot, rows, model)

    assert adjustments
    assert refined.candidates[0].confidence > 0.55
    assert "Residual model" in refined.candidates[0].rationale
    assert any("Residual model refinement is active" in note for note in refined.notes)


def _make_row(*, brake_bias: float, delta: float, speed_mean: float, steering: float) -> SetupDatasetRow:
    return SetupDatasetRow(
        session_id="session",
        bundle_dir="C:\\bundle",
        sim="ACC",
        car="ferrari_488_gt3",
        track="Spa",
        session_type="Race",
        lap_number=2,
        lap_time_s=120.0 + delta,
        classification="push_lap",
        clean_lap=True,
        valid_for_analysis=True,
        delta_to_best_lap_s=delta,
        delta_to_best_clean_lap_s=delta,
        delta_to_representative_lap_s=delta,
        sample_count=200,
        distance_coverage_pct=0.98,
        speed_min_kph=84.0,
        speed_mean_kph=speed_mean,
        speed_max_kph=246.0,
        throttle_mean_pct=0.57,
        brake_mean_pct=0.14,
        brake_peak_pct=0.98,
        coast_ratio=0.12,
        pedal_overlap_ratio=0.04,
        steering_abs_mean_deg=steering,
        steering_peak_deg=31.0,
        rpm_mean=6100.0,
        rpm_max=7600.0,
        long_g_peak=0.48,
        lat_g_peak=0.92,
        fuel_used_l=2.8,
        tyre_temp_mean_c=88.0,
        track_temp_c=27.0,
        air_temp_c=19.0,
        setup_source_path="C:\\setup.json",
        setup_fingerprint="abc",
        setup_feature_count=2,
        setup_numeric_features={"advancedsetup.mechanicalbalance.brakebias": brake_bias},
        setup_categorical_features={},
        recommendation_seed={},
    )


def _acc_setup(*, brake_bias: int, rear_wing: int) -> dict[str, object]:
    return {
        "carName": "ferrari_488_gt3",
        "basicSetup": {"strategy": {"fuel": 36}},
        "advancedSetup": {
            "mechanicalBalance": {"brakeBias": brake_bias},
            "aeroBalance": {"rearWing": rear_wing},
        },
    }
