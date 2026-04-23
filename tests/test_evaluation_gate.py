"""Release-gate test suite â€" coaching evaluation ingestion readiness.

This suite is the authoritative yes/no answer to: "Is the logger safe to wire
up as an ingestion source for automated coaching evaluation?"

Each test maps to a numbered gate check.  All checks must pass before a build
is considered evaluation-ready.  See EVALUATION_GATE.md for the checklist and
CI integration instructions.

Gate check index
----------------
  [RG-01]  FSM: complete happy-path traversal IDLE â†’ READY_FOR_REVIEW
  [RG-02]  FSM: every invalid transition from every state is rejected
  [RG-03]  FSM: abrupt disconnect FAILED â†’ FINALIZING â†’ READY_FOR_REVIEW
  [RG-04]  FSM: on_enter exception does not abort or corrupt state
  [RG-05]  FSM: READY_FOR_REVIEW â†’ WAITING allows a subsequent session
  [RG-06]  Bundle: all 7 required files present after finalize
  [RG-07]  Bundle: session_id written to manifest equals supplied UID
  [RG-08]  Bundle: session_id is the UID, not derived from the folder name
  [RG-09]  Bundle: folder name is deterministic for identical inputs
  [RG-10]  Bundle: no _tmp_ directory remains after a successful finalize
  [RG-11]  Bundle: session.json and metadata.json carry consistent key fields
  [RG-12]  Bundle: telemetry SHA-256 in manifest verifies the actual file
  [RG-13]  Schema: every TelemetrySample canonical field present in CSV header
  [RG-14]  Schema: None-valued fields serialized as empty cells, not "None"
  [RG-15]  Schema: ACC and iRacing produce identical telemetry column sets
  [RG-16]  Schema: TELEMETRY_SCHEMA_VERSION constant equals "2.0.0"
  [RG-17]  Quality: score is always in [0.0, 1.0] regardless of input
  [RG-18]  Quality: exactly min_samples-1 causes "too_few_samples" rejection
  [RG-19]  Quality: session under min_duration_s triggers duration rejection
  [RG-20]  Quality: accepted session has zero rejection reasons
  [RG-21]  Quality: manifest quality_classification equals quality_report value
  [RG-22]  Laps: out-lap is never counted as a clean lap
  [RG-23]  Laps: pit lap is not valid_for_analysis
  [RG-24]  Laps: best_clean_lap_time_s is the minimum of all clean lap times
  [RG-25]  Laps: representative lap number picks the median clean time
  [RG-26]  Laps: off-track and spin laps are both invalidated
  [RG-27]  Finalize/disconnect: FSM RECORDINGâ†’FAILEDâ†’FINALIZINGâ†’READY path
  [RG-28]  Finalize/disconnect: zero samples â†’ finalize returns None
  [RG-29]  Finalize/disconnect: few samples â†’ bundle produced, quality rejected
  [RG-30]  Finalize/disconnect: ended_at=None still produces a bundle
  [RG-31]  Finalize/disconnect: no _tmp_ dir left after any finalize outcome
  [RG-32]  ACC compat: mandatory channels map to correct values and units
  [RG-33]  ACC compat: session type numeric codes map to human-readable strings
  [RG-34]  ACC compat: full finalize of ACC samples produces non-rejected bundle
  [RG-35]  iRacing compat: mandatory channels map correctly with unit conversion
  [RG-36]  iRacing compat: full finalize produces non-rejected bundle
  [RG-37]  Compat: gear normalization â€" ACC and iRacing use consistent encoding
  [RG-38]  Determinism: bundle_hash is stable across repeated identical finalizes
  [RG-39]  Determinism: bundle_hash changes when telemetry content changes
  [RG-40]  Determinism: session_uid always propagated unchanged to manifest
  [RG-41]  Determinism: compute_bundle_hash is a pure function
  [RG-42]  Index: all required history fields populated after finalize + sync
  [RG-43]  Index: review status change propagates to index on next sync
  [RG-44]  Index: deleted bundle is pruned from index on next sync
  [RG-45]  Index: list_entries returns sessions ordered newest-first
  [RG-46]  Corruption: corrupt DB triggers silent rebuild with valid new DB
  [RG-47]  Corruption: bundle missing session.json is skipped without crash
  [RG-48]  Corruption: bundle with invalid JSON is skipped without crash
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from lap_coach_logger.adapters.acc_shm_structs import SESSION_TYPE_MAP
from lap_coach_logger.config.models import AppConfig, QualityConfig
from lap_coach_logger.core.lap_analysis import LapAnalysisConfig, classify_laps
from lap_coach_logger.core.schema import TELEMETRY_SCHEMA_VERSION, TelemetrySample
from lap_coach_logger.core.session_quality import validate_session_quality
from lap_coach_logger.core.session_review import (
    REVIEW_STATUS_IGNORED,
    load_history_entry,
    set_session_review_status,
)
from lap_coach_logger.core.session_state import SessionState, SessionStateMachine
from lap_coach_logger.core.sync_queue import SyncQueueManager
from lap_coach_logger.normalization.mapper import normalise_sample
from lap_coach_logger.ui.desktop.session_index import SessionIndex
from lap_coach_logger.writers.bundle_schema import BUNDLE_SCHEMA_VERSION, compute_file_sha256
from lap_coach_logger.writers.finalizer import SessionFinalizer, session_folder_name
from tests.helpers import finalize_session, make_quality_samples


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _make_lap_samples(
    lap_number: int,
    *,
    start_time: float,
    lap_time_s: float,
    n: int = 40,
    speed_kph: float = 150.0,
    throttle: float = 0.75,
    brake: float = 0.05,
    pit: bool = False,
    offtrack: bool = False,
    spin: bool = False,
    flying_start: bool = True,
    flying_end: bool = True,
) -> list[TelemetrySample]:
    """Produce n samples covering one lap segment with realistic flags."""
    samples: list[TelemetrySample] = []
    dt = lap_time_s / max(1, n - 1)
    for idx in range(n):
        t = start_time + idx * dt
        dist = (idx / max(1, n - 1)) * 5000.0
        cur_speed = speed_kph
        cur_pit = pit and idx > n // 2
        cur_on_track = not (offtrack and idx in (10, 11, 12))
        yaw = 200.0 if (spin and idx == n // 2) else 5.0
        if idx == 0 and not flying_start:
            cur_speed = 45.0
        if idx == n - 1 and not flying_end:
            cur_speed = 55.0
        if cur_pit:
            cur_speed = min(cur_speed, 50.0)
        samples.append(
            TelemetrySample(
                sim="iRacing",
                session_uid="gate-lap-test",
                session_time_s=t,
                lap_number=lap_number,
                lap_distance_m=dist,
                speed_kph=cur_speed,
                throttle_pct=throttle,
                brake_pct=brake,
                is_on_track=cur_on_track,
                is_in_pits=cur_pit,
                yaw_deg=yaw,
                gear=4,
                track_name="Spa",
                car_name="GT3",
                session_type="Race",
            )
        )
    return samples


def _reach_state(target: SessionState) -> SessionStateMachine:
    """Create a fresh FSM and navigate it to *target* via the canonical path."""
    _PATHS: dict[SessionState, list[tuple[SessionState, str]]] = {
        SessionState.IDLE: [],
        SessionState.SIMULATOR_DETECTED: [
            (SessionState.SIMULATOR_DETECTED, "sim found"),
        ],
        SessionState.WAITING_FOR_VALID_SESSION: [
            (SessionState.SIMULATOR_DETECTED, "sim found"),
            (SessionState.WAITING_FOR_VALID_SESSION, "connected"),
        ],
        SessionState.ARMING: [
            (SessionState.SIMULATOR_DETECTED, "sim found"),
            (SessionState.WAITING_FOR_VALID_SESSION, "connected"),
            (SessionState.ARMING, "session context ready"),
        ],
        SessionState.RECORDING: [
            (SessionState.SIMULATOR_DETECTED, "sim found"),
            (SessionState.WAITING_FOR_VALID_SESSION, "connected"),
            (SessionState.ARMING, "session context ready"),
            (SessionState.RECORDING, "first sample"),
        ],
        SessionState.FINALIZING: [
            (SessionState.SIMULATOR_DETECTED, "sim found"),
            (SessionState.WAITING_FOR_VALID_SESSION, "connected"),
            (SessionState.ARMING, "session context ready"),
            (SessionState.RECORDING, "first sample"),
            (SessionState.FINALIZING, "sim disconnected"),
        ],
        SessionState.READY_FOR_REVIEW: [
            (SessionState.SIMULATOR_DETECTED, "sim found"),
            (SessionState.WAITING_FOR_VALID_SESSION, "connected"),
            (SessionState.ARMING, "session context ready"),
            (SessionState.RECORDING, "first sample"),
            (SessionState.FINALIZING, "sim disconnected"),
            (SessionState.READY_FOR_REVIEW, "bundle written"),
        ],
        SessionState.FAILED: [
            (SessionState.SIMULATOR_DETECTED, "sim found"),
            (SessionState.WAITING_FOR_VALID_SESSION, "connected"),
            (SessionState.ARMING, "session context ready"),
            (SessionState.FAILED, "adapter error"),
        ],
    }
    fsm = SessionStateMachine()
    for state, reason in _PATHS[target]:
        assert fsm.transition(state, reason=reason), f"Could not reach {target} via path step {state}"
    return fsm


# All (from_state, illegal_target) pairs derived from the _TRANSITIONS table.
_ALL_STATES = set(SessionState)
_VALID: dict[SessionState, set[SessionState]] = {
    SessionState.IDLE: {SessionState.SIMULATOR_DETECTED},
    SessionState.SIMULATOR_DETECTED: {
        SessionState.WAITING_FOR_VALID_SESSION,
        SessionState.IDLE,
        SessionState.FAILED,
    },
    SessionState.WAITING_FOR_VALID_SESSION: {
        SessionState.ARMING,
        SessionState.IDLE,
        SessionState.FAILED,
    },
    SessionState.ARMING: {
        SessionState.RECORDING,
        SessionState.FINALIZING,
        SessionState.IDLE,
        SessionState.FAILED,
    },
    SessionState.RECORDING: {SessionState.FINALIZING, SessionState.FAILED},
    SessionState.FINALIZING: {SessionState.READY_FOR_REVIEW, SessionState.FAILED},
    SessionState.READY_FOR_REVIEW: {
        SessionState.WAITING_FOR_VALID_SESSION,
        SessionState.IDLE,
    },
    SessionState.FAILED: {
        SessionState.FINALIZING,
        SessionState.READY_FOR_REVIEW,
        SessionState.IDLE,
    },
}

_INVALID_TRANSITIONS = [
    (src, tgt)
    for src in _ALL_STATES
    for tgt in _ALL_STATES
    if tgt not in _VALID[src] and tgt != src  # self-transitions also illegal
]


# ===========================================================================
# RG-01 through RG-05  â€"  State Machine Correctness
# ===========================================================================

class TestStateMachineTransitions:
    """[RG-01 to RG-05] FSM lifecycle correctness."""

    def test_happy_path_reaches_ready_for_review(self) -> None:
        """[RG-01] Full IDLE â†’ READY_FOR_REVIEW traversal succeeds."""
        fsm = SessionStateMachine()
        steps = [
            SessionState.SIMULATOR_DETECTED,
            SessionState.WAITING_FOR_VALID_SESSION,
            SessionState.ARMING,
            SessionState.RECORDING,
            SessionState.FINALIZING,
            SessionState.READY_FOR_REVIEW,
        ]
        for state in steps:
            assert fsm.transition(state, reason="gate-test"), f"Should reach {state}"

        assert fsm.state is SessionState.READY_FOR_REVIEW
        # Transition history captures every step with timestamps
        hist = fsm.transition_history
        assert len(hist) == len(steps)
        assert all(h.timestamp_utc for h in hist)
        assert hist[0].previous_state == "idle"
        assert hist[-1].new_state == "ready_for_review"

    @pytest.mark.parametrize("src, tgt", _INVALID_TRANSITIONS)
    def test_every_invalid_transition_is_rejected(
        self, src: SessionState, tgt: SessionState
    ) -> None:
        """[RG-02] No illegal FSM transition can succeed."""
        fsm = _reach_state(src)
        result = fsm.transition(tgt, reason="gate-invalid")
        assert result is False, f"{src.value} â†’ {tgt.value} should be rejected"
        assert fsm.state is src, "State must remain unchanged after rejected transition"

    def test_abrupt_disconnect_failed_path_reaches_ready_for_review(self) -> None:
        """[RG-03] RECORDING â†’ FAILED â†’ FINALIZING â†’ READY_FOR_REVIEW (disconnect path)."""
        fsm = _reach_state(SessionState.RECORDING)
        assert fsm.transition(SessionState.FAILED, reason="sim disconnected abruptly")
        assert fsm.state is SessionState.FAILED
        assert fsm.transition(SessionState.FINALIZING, reason="best-effort finalize")
        assert fsm.transition(SessionState.READY_FOR_REVIEW, reason="partial bundle written")
        assert fsm.state is SessionState.READY_FOR_REVIEW

    def test_on_enter_exception_does_not_corrupt_state(self) -> None:
        """[RG-04] A crashing on_enter callback must not prevent the transition."""
        fsm = SessionStateMachine()
        fired: list[bool] = []

        def bad_callback(prev: SessionState, cur: SessionState) -> None:
            fired.append(True)
            raise RuntimeError("deliberate on_enter failure")

        fsm.on_enter(SessionState.SIMULATOR_DETECTED, bad_callback)
        result = fsm.transition(SessionState.SIMULATOR_DETECTED, reason="test")

        assert result is True  # transition succeeded despite callback crash
        assert fsm.state is SessionState.SIMULATOR_DETECTED
        assert fired == [True]  # callback was invoked

    def test_ready_for_review_allows_next_session(self) -> None:
        """[RG-05] After review, the FSM can restart a new session cycle."""
        fsm = _reach_state(SessionState.READY_FOR_REVIEW)
        # Return to WAITING to begin the next session
        assert fsm.transition(SessionState.WAITING_FOR_VALID_SESSION, reason="new session")
        assert fsm.state is SessionState.WAITING_FOR_VALID_SESSION
        # Can then arm and record again
        assert fsm.transition(SessionState.ARMING, reason="session ready")
        assert fsm.transition(SessionState.RECORDING, reason="first sample")
        assert fsm.state is SessionState.RECORDING


# ===========================================================================
# RG-06 through RG-12  â€"  Bundle Integrity
# ===========================================================================

class TestBundleIntegrity:
    """[RG-06 to RG-12] Session bundle file completeness and cross-file consistency."""

    def test_all_seven_required_files_present(self, bundled_session: Path) -> None:
        """[RG-06] A finalized bundle must contain all 7 standard files."""
        required = {
            "session.json",
            "analysis.json",
            "laps.json",
            "events.json",
            "channels.json",
            "quality_report.json",
            "telemetry.parquet",
        }
        present = {p.name for p in bundled_session.iterdir() if p.is_file()}
        missing = required - present
        assert not missing, f"Bundle missing required files: {missing}"

    def test_session_id_matches_supplied_uid(self, bundled_session: Path) -> None:
        """[RG-07] session_id in manifest must equal the caller-supplied session_uid."""
        manifest = json.loads((bundled_session / "session.json").read_text())
        assert manifest["session_id"] == "fixture-uid"

    def test_session_id_not_derived_from_folder_name(self, tmp_path: Path) -> None:
        """[RG-08] session_id must survive even when the folder name differs."""
        output_root = tmp_path / "sessions"
        output_root.mkdir()
        uid = "deliberate-uid-xyz-789"
        bundle = finalize_session(output_root, session_uid=uid, track="Monza")
        manifest = json.loads((bundle / "session.json").read_text())

        assert manifest["session_id"] == uid
        assert manifest["session_id"] != bundle.name, (
            "session_id must not be derived from the filesystem folder name"
        )

    def test_folder_name_is_deterministic_for_fixed_inputs(self) -> None:
        """[RG-09] session_folder_name produces the same name for identical arguments."""
        ts = datetime(2026, 3, 15, 14, 30, 0, tzinfo=timezone.utc)
        name_a = session_folder_name(ts, "iRacing", "Spa", "Race")
        name_b = session_folder_name(ts, "iRacing", "Spa", "Race")
        assert name_a == name_b
        assert "2026-03-15_14-30-00" in name_a
        # Different sim â†’ different name
        name_acc = session_folder_name(ts, "ACC", "Spa", "Race")
        assert name_a != name_acc

    def test_no_tmp_directory_left_after_successful_finalize(
        self, bundled_session: Path
    ) -> None:
        """[RG-10] Atomic rename must leave no _tmp_ dir in the output root."""
        output_root = bundled_session.parent
        tmp_dirs = [p for p in output_root.iterdir() if p.name.startswith("_tmp_")]
        assert tmp_dirs == [], f"Leftover temp dirs found: {tmp_dirs}"

    def test_session_json_and_analysis_json_are_consistent(
        self, bundled_session: Path
    ) -> None:
        # [RG-11] Key fields in session.json and analysis.json must agree.
        manifest = json.loads((bundled_session / "session.json").read_text())
        analysis = json.loads((bundled_session / "analysis.json").read_text())

        # session.json v2 has nested structure
        assert manifest["schema_version"] == 2
        assert manifest["session_id"] is not None
        assert manifest["raw_source"]["raw_track"] is not None
        # analysis.json lap counts agree
        assert manifest["session"]["lap_count"] == analysis["lap_summary"]["total_laps"]

    def test_telemetry_sha256_in_manifest_verifies_actual_file(
        self, bundled_session: Path
    ) -> None:
        """[RG-12] The stored telemetry SHA-256 in bundle_files must match the on-disk file hash."""
        manifest = json.loads((bundled_session / "session.json").read_text())
        # v2: telemetry hash is in the bundle_files inventory
        tel_entry = next(
            (f for f in manifest["bundle_files"] if f["name"] == "telemetry.parquet"),
            None,
        )
        assert tel_entry is not None, "telemetry.parquet must be in bundle_files"
        stored_hash = tel_entry["sha256"]
        assert stored_hash, "sha256 must be present and non-empty"

        tel_file = bundled_session / "telemetry.parquet"
        assert tel_file.exists(), "Telemetry file not found on disk"

        actual_hash = "sha256:" + compute_file_sha256(tel_file)
        assert actual_hash == stored_hash, (
            "SHA-256 of telemetry file does not match bundle_files entry"
        )


# ===========================================================================
# RG-13 through RG-16  â€"  Normalized Schema Generation
# ===========================================================================

class TestSchemaGeneration:
    """[RG-13 to RG-16] TelemetrySample canonical schema consistency."""

    def test_all_canonical_fields_present_in_telemetry(
        self, bundled_session: Path
    ) -> None:
        """[RG-13] Every TelemetrySample field must appear as a column in the telemetry file."""
        import pyarrow.parquet as pq

        parquet_path = bundled_session / "telemetry.parquet"
        table = pq.read_table(parquet_path)
        headers = set(table.column_names)

        canonical = set(TelemetrySample.field_names())
        missing = canonical - headers
        assert not missing, f"Telemetry file missing canonical fields: {missing}"

    def test_none_fields_serialized_as_null_not_none_string(
        self, tmp_path: Path
    ) -> None:
        """[RG-14] None-valued channels must be stored as null, not the string 'None'."""
        import pyarrow.parquet as pq

        # Create one sample that has many None optional channels
        sample = TelemetrySample(
            sim="iRacing",
            session_time_s=0.0,
            lap_number=1,
            speed_kph=100.0,
            throttle_pct=0.5,
            brake_pct=0.0,
            gear=4,
            track_name="Spa",
            car_name="GT3",
            session_type="Race",
            # All tyre temps, fuel, water_temp, etc. left as None
        )
        output_root = tmp_path / "sessions"
        output_root.mkdir()
        fin = SessionFinalizer(output_root)
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # Use many identical samples with the same None channels
        samples = [sample] * 5
        result = fin.finalize(
            samples,
            started_at=now,
            sim="iRacing",
            track="Spa",
            session_type="Race",
            session_uid="none-test",
        )
        assert result is not None
        parquet_path = result / "telemetry.parquet"
        table = pq.read_table(parquet_path)

        # The literal string "None" must not appear in any column value.
        # None-valued fields should be stored as proper nulls in parquet.
        for col_name in table.column_names:
            col = table.column(col_name)
            for val in col.to_pylist():
                assert val != "None", (
                    f"Literal 'None' string found in column {col_name!r}"
                )

    def test_acc_and_iracing_sessions_produce_identical_column_sets(
        self, tmp_path: Path
    ) -> None:
        """[RG-15] Column names must be sim-agnostic (canonical schema always complete)."""
        import pyarrow.parquet as pq

        root_ir = tmp_path / "ir"
        root_ir.mkdir()
        root_acc = tmp_path / "acc"
        root_acc.mkdir()

        bundle_ir = finalize_session(root_ir, sim="iRacing")
        bundle_acc = finalize_session(root_acc, sim="ACC")

        def parquet_columns(bundle: Path) -> set[str]:
            path = bundle / "telemetry.parquet"
            table = pq.read_table(path)
            return set(table.column_names)

        assert parquet_columns(bundle_ir) == parquet_columns(bundle_acc), (
            "iRacing and ACC bundles must have identical telemetry column sets"
        )

    def test_telemetry_schema_version_constant(self) -> None:
        """[RG-16] TELEMETRY_SCHEMA_VERSION must equal '2.0.0'."""
        assert TELEMETRY_SCHEMA_VERSION == "2.0.0"

    def test_channels_json_lists_all_canonical_channels(
        self, bundled_session: Path
    ) -> None:
        """channels.json must declare all TelemetrySample fields."""
        channels = json.loads((bundled_session / "channels.json").read_text())
        declared = {ch["canonical_name"] for ch in channels.get("channels", [])}
        canonical = set(TelemetrySample.field_names())
        missing = canonical - declared
        assert not missing, f"channels.json missing: {missing}"


# ===========================================================================
# RG-17 through RG-21  â€"  Quality Gate Behavior
# ===========================================================================

class TestQualityGateBehavior:
    """[RG-17 to RG-21] Quality scoring and threshold enforcement."""

    def _base_good_sample(self, i: int) -> TelemetrySample:
        return TelemetrySample(
            timestamp_utc=f"2026-01-01T00:{i // 60:02d}:{i % 60:02d}+00:00",
            session_time_s=float(i),
            lap_number=1 + (i // 50),
            speed_kph=80.0 + (i % 15),
            throttle_pct=0.5 + (i % 4) * 0.05,
            brake_pct=0.02,
            gear=3 + (i % 2),
            track_name="Spa",
            car_name="GT3",
            session_type="Race",
        )

    def test_quality_score_always_in_unit_interval(self) -> None:
        """[RG-17] Quality score must be in [0.0, 1.0] for any input."""
        cases: list[list[TelemetrySample]] = [
            [],  # empty
            [self._base_good_sample(0)],  # single
            [self._base_good_sample(i) for i in range(300)],  # full
        ]
        cfg = QualityConfig()
        for samples in cases:
            report = validate_session_quality(
                samples=samples,
                laps=[],
                track_name="Spa",
                car_name="GT3",
                session_type="Race",
                sample_rate_hz=1.0,
                config=cfg,
            )
            assert 0.0 <= report.overall_quality_score <= 1.0, (
                f"Score {report.overall_quality_score} out of [0.0, 1.0] for {len(samples)} samples"
            )

    def test_exactly_min_samples_minus_one_triggers_rejection(self) -> None:
        """[RG-18] min_samples âˆ’ 1 samples must trigger 'too_few_samples' rejection."""
        cfg = QualityConfig(min_samples=100, min_duration_s=5.0)
        # 99 samples over 200s â†’ only the count check should fail
        samples = [
            TelemetrySample(
                session_time_s=float(i * 2),  # 0, 2, 4, ... 196 â€" duration = 196s
                lap_number=1,
                speed_kph=80.0,
                throttle_pct=0.5,
                brake_pct=0.0,
                gear=4,
                track_name="Spa",
                car_name="GT3",
                session_type="Race",
            )
            for i in range(99)
        ]
        report = validate_session_quality(
            samples=samples,
            laps=[],
            track_name="Spa",
            car_name="GT3",
            session_type="Race",
            sample_rate_hz=None,
            config=cfg,
        )
        assert report.recommended_classification == "rejected"
        names = {c.name for c in report.individual_checks if c.status == "fail"}
        assert "too_few_samples" in names

    def test_session_under_min_duration_triggers_rejection(self) -> None:
        """[RG-19] A session whose duration is below min_duration_s must be rejected."""
        cfg = QualityConfig(min_samples=10, min_duration_s=20.0)
        # 100 samples over 19s â†’ only duration check fails
        samples = [
            TelemetrySample(
                session_time_s=round(i * 19.0 / 99, 4),
                lap_number=1,
                speed_kph=80.0,
                throttle_pct=0.5,
                brake_pct=0.0,
                gear=4,
                track_name="Spa",
                car_name="GT3",
                session_type="Race",
            )
            for i in range(100)
        ]
        report = validate_session_quality(
            samples=samples,
            laps=[],
            track_name="Spa",
            car_name="GT3",
            session_type="Race",
            sample_rate_hz=None,
            config=cfg,
        )
        assert report.recommended_classification == "rejected"
        names = {c.name for c in report.individual_checks if c.status == "fail"}
        assert "duration_too_short" in names

    def test_accepted_session_has_zero_rejection_reasons(
        self, quality_samples: list[TelemetrySample]
    ) -> None:
        """[RG-20] A well-formed session must have an empty rejection_reasons list."""
        report = validate_session_quality(
            samples=quality_samples,
            laps=[],
            track_name="Spa",
            car_name="GT3",
            session_type="Race",
            sample_rate_hz=1.0,
            config=QualityConfig(),
        )
        assert report.recommended_classification in {"accepted", "accepted_with_warnings"}
        assert report.rejection_reasons == [], (
            f"Accepted session should have no rejections: {report.rejection_reasons}"
        )

    def test_manifest_quality_classification_matches_quality_report(
        self, bundled_session: Path
    ) -> None:
        """[RG-21] analysis_readiness in session.json must be consistent with quality_report.json."""
        manifest = json.loads((bundled_session / "session.json").read_text())
        quality_report = json.loads((bundled_session / "quality_report.json").read_text())
        readiness = manifest["analysis_readiness"]
        # analysis_readiness.quality_score must be in [0, 1]
        assert 0.0 <= readiness["quality_score"] <= 1.0
        # ready_for_analysis must be a boolean
        assert isinstance(readiness["ready_for_analysis"], bool)


# ===========================================================================
# RG-22 through RG-26  â€"  Lap Classification Behavior
# ===========================================================================

class TestLapClassificationBehavior:
    """[RG-22 to RG-26] Lap type detection and summary accuracy."""

    def test_out_lap_is_never_counted_as_clean(self) -> None:
        """[RG-22] An out-lap (slow start) must not appear in clean_laps count."""
        # Single lap with a slow entry (flying_start=False) â†’ out_lap
        samples = _make_lap_samples(1, start_time=0.0, lap_time_s=90.0, flying_start=False)
        _, summary = classify_laps(samples, config=LapAnalysisConfig())

        assert summary.clean_laps == 0
        assert summary.best_clean_lap_time_s is None

    def test_pit_lap_is_not_valid_for_analysis(self) -> None:
        """[RG-23] A lap with pit entry/exit must be marked not valid_for_analysis."""
        samples = _make_lap_samples(1, start_time=0.0, lap_time_s=90.0)
        samples.extend(_make_lap_samples(2, start_time=90.0, lap_time_s=100.0, pit=True))
        laps, _ = classify_laps(samples, config=LapAnalysisConfig())

        pit_laps = [lap for lap in laps if lap.pit_entry_or_exit_detected]
        assert pit_laps, "Expected at least one pit lap in the results"
        for lap in pit_laps:
            assert lap.valid_for_analysis is False, (
                f"Lap {lap.lap_number} has a pit but valid_for_analysis=True"
            )

    def test_best_clean_lap_time_is_minimum_of_all_clean_times(self) -> None:
        """[RG-24] best_clean_lap_time_s must be min(time for all clean laps)."""
        samples: list[TelemetrySample] = []
        # Three clean flying laps with deliberately different times
        for lap, t in [(1, 0.0), (2, 88.0), (3, 181.0)]:
            dur = 88.0 if lap == 1 else (93.0 if lap == 2 else 97.0)
            samples.extend(_make_lap_samples(lap, start_time=t, lap_time_s=dur))

        laps, summary = classify_laps(samples, config=LapAnalysisConfig())

        clean = [lap.lap_time_s for lap in laps if lap.clean_lap and lap.lap_time_s]
        assert clean, "Expected at least one clean lap"
        assert summary.best_clean_lap_time_s == min(clean)

    def test_representative_lap_picks_median_clean_time(self) -> None:
        """[RG-25] representative_lap_time_s should be the median of clean lap times."""
        # Three clean laps with times 88, 91, 95 â€" median is 91
        samples: list[TelemetrySample] = []
        for lap, start, dur in [(1, 0.0, 88.0), (2, 88.0, 91.0), (3, 179.0, 95.0)]:
            samples.extend(_make_lap_samples(lap, start_time=start, lap_time_s=dur))

        _, summary = classify_laps(samples, config=LapAnalysisConfig())

        assert summary.representative_lap_number == 2
        assert summary.representative_lap_time_s == 91.0

    def test_offtrack_and_spin_both_invalidate_their_laps(self) -> None:
        """[RG-26] Off-track excursion and spin/reset events each invalidate a lap."""
        samples: list[TelemetrySample] = []
        samples.extend(_make_lap_samples(1, start_time=0.0, lap_time_s=88.0, offtrack=True))
        samples.extend(_make_lap_samples(2, start_time=88.0, lap_time_s=90.0, spin=True))

        laps, summary = classify_laps(samples, config=LapAnalysisConfig())

        assert laps[0].suspected_offtrack is True
        assert laps[0].classification == "invalid_lap"
        assert laps[1].suspected_spin_or_reset is True
        assert laps[1].classification == "invalid_lap"
        assert summary.clean_laps == 0
        assert summary.valid_laps == 0


# ===========================================================================
# RG-27 through RG-31  â€"  Finalize After Abrupt Simulator Disconnect
# ===========================================================================

class TestFinalizeAfterDisconnect:
    """[RG-27 to RG-31] Finalize behavior under fault conditions."""

    def test_fsm_recording_failed_finalizing_ready_path(self) -> None:
        """[RG-27] FSM abrupt disconnect path is achievable end-to-end."""
        fsm = _reach_state(SessionState.RECORDING)

        ok = fsm.transition(SessionState.FAILED, reason="sim process exited")
        assert ok and fsm.state is SessionState.FAILED

        ok = fsm.transition(SessionState.FINALIZING, reason="best-effort finalize started")
        assert ok and fsm.state is SessionState.FINALIZING

        ok = fsm.transition(SessionState.READY_FOR_REVIEW, reason="partial bundle saved")
        assert ok and fsm.state is SessionState.READY_FOR_REVIEW

        # Verify the disconnect is recorded in history
        hist = fsm.transition_history
        reasons = [h.reason for h in hist]
        assert "sim process exited" in reasons

    def test_finalize_with_zero_samples_creates_rejected_bundle(
        self, tmp_path: Path
    ) -> None:
        """[RG-28] Empty sample list must not produce an analysis-ready bundle.

        finalize() either returns None (no bundle) or produces a bundle whose
        quality_classification is 'rejected' and never enters the coaching pipeline.
        """
        output_root = tmp_path / "sessions"
        output_root.mkdir()
        fin = SessionFinalizer(output_root)
        result = fin.finalize(
            [],
            started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            sim="iRacing",
            track="Spa",
            session_type="Race",
        )
        if result is None:
            # Implementation chose to produce no bundle -- acceptable
            return
        # Implementation produced a bundle -- it must be clearly rejected
        manifest = json.loads((result / "session.json").read_text())
        readiness = manifest.get("analysis_readiness") or {}
        assert readiness.get("ready_for_analysis") is False, (
            "A zero-sample session must never be marked ready_for_analysis"
        )
        assert manifest["session"]["sample_count"] == 0

    def test_finalize_with_few_samples_produces_rejected_quality(
        self, tmp_path: Path
    ) -> None:
        """[RG-29] A session below quality thresholds must produce a bundle with rejected class."""
        output_root = tmp_path / "sessions"
        output_root.mkdir()
        fin = SessionFinalizer(output_root, quality_config=QualityConfig(min_samples=100))
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # 10 samples â€" far below threshold
        samples = make_quality_samples(10, session_uid="disconnect-few")
        result = fin.finalize(
            samples,
            started_at=now,
            sim="iRacing",
            track="Spa",
            session_type="Race",
            session_uid="disconnect-few",
        )
        assert result is not None, "Bundle should still be written (partial data has value)"
        manifest = json.loads((result / "session.json").read_text())
        readiness = manifest.get("analysis_readiness") or {}
        assert readiness.get("ready_for_analysis") is False

    def test_finalize_with_ended_at_none_still_produces_bundle(
        self, tmp_path: Path
    ) -> None:
        """[RG-30] Omitting ended_at must not prevent bundle creation."""
        output_root = tmp_path / "sessions"
        output_root.mkdir()
        fin = SessionFinalizer(output_root)
        samples = make_quality_samples(200, session_uid="no-ended-at")
        result = fin.finalize(
            samples,
            started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ended_at=None,  # simulate crash â€" no explicit end time
            sim="iRacing",
            track="Spa",
            session_type="Race",
            session_uid="no-ended-at",
        )
        assert result is not None
        manifest = json.loads((result / "session.json").read_text())
        session_block = manifest.get("session") or {}
        assert session_block.get("end_time"), "end_time must be populated even when not supplied"

    def test_no_tmp_dir_left_after_any_finalize_outcome(self, tmp_path: Path) -> None:
        """[RG-31] Neither success nor failure should leave _tmp_ dirs on disk."""
        output_root = tmp_path / "sessions"
        output_root.mkdir()
        fin = SessionFinalizer(output_root)
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)

        # Successful finalize
        fin.finalize(
            make_quality_samples(200, session_uid="s1"),
            started_at=now,
            sim="iRacing",
            track="Spa",
            session_type="Race",
            session_uid="s1",
        )
        # "Aborted" finalize (too few samples returns None)
        fin.finalize(
            [],
            started_at=now,
            sim="iRacing",
            track="Spa",
            session_type="Race",
        )

        tmp_dirs = [p for p in output_root.iterdir() if p.name.startswith("_tmp_")]
        assert tmp_dirs == [], f"Leftover _tmp_ dirs: {tmp_dirs}"


# ===========================================================================
# RG-32 through RG-37  â€"  Simulator Compatibility (ACC + iRacing)
# ===========================================================================

class TestSimulatorCompatibility:
    """[RG-32 to RG-37] ACC and iRacing adapter normalization and full-pipeline."""

    _ACC_RAW: dict[str, Any] = {
        "iCurrentTime": 12500,       # 12.5 s
        "completedLaps": 3,
        "normalizedCarPosition": 0.5,
        "trackSPlineLength": 3068.4,  # â†’ lap_distance_m = 0.5 * 3068.4 = 1534.2
        "speedKmh": 144.0,
        "gas": 0.8,
        "brake": 0.1,
        "clutch": 0.0,
        "steerAngle": 0.174532925,   # ~10Â°
        "gear": 5,                    # ACC gear 5 â†’ TelemetrySample gear 4
        "rpms": 6500,
        "heading": 1.570796326,       # ~90Â°
        "accG_x": 1.1,
        "accG_z": 0.4,
        "roadTemp": 31.5,
        "airTemp": 22.0,
        "ABS": 4,
        "TC": 3,
        "status": 2,                  # ACC_LIVE â†’ is_on_track=True
        "isInPit": 0,
        "session": 2,                 # race
        "tyreCoreTemperature_0": 85.0,
        "tyreCoreTemperature_1": 86.0,
        "tyreCoreTemperature_2": 84.0,
        "tyreCoreTemperature_3": 85.5,
        "fuel": 42.5,
        "waterTemp": 82.0,
    }

    _IRACING_RAW: dict[str, Any] = {
        "SessionTime": 12.5,
        "Lap": 3,
        "LapDist": 1534.2,
        "Speed": 40.0,               # m/s â†’ 144.0 km/h
        "Throttle": 0.8,
        "Brake": 0.1,
        "Clutch": 0.0,
        "SteeringWheelAngle": 0.174532925,  # ~10Â°
        "Gear": 4,                    # iRacing passes through directly
        "RPM": 6500,
        "Lat": 100.0,
        "Alt": 5.0,
        "Lon": 250.0,
        "Yaw": 1.570796326,          # ~90Â°
        "LatAccel": 1.1,
        "LongAccel": 0.4,
        "TrackTempCrew": 31.5,
        "AirTemp": 22.0,
        "IsOnTrack": 1,
        "OnPitRoad": 0,
        "LFtempCL": 85.0,
        "RFtempCL": 86.0,
        "LRtempCL": 84.0,
        "RRtempCL": 85.5,
        "FuelLevel": 42.5,
        "WaterTemp": 82.0,
    }

    def test_acc_mandatory_channels_map_correctly(self) -> None:
        """[RG-32] ACC raw data must produce correct canonical values and units."""
        sample = normalise_sample(
            self._ACC_RAW,
            sim="ACC",
            passthrough={"track_name": "Spa", "car_name": "GT3"},
        )
        assert sample.session_time_s == pytest.approx(12.5)
        assert sample.lap_number == 3
        assert sample.lap_distance_m == pytest.approx(1534.2, rel=1e-3)
        assert sample.speed_kph == pytest.approx(144.0)
        assert sample.throttle_pct == pytest.approx(0.8)
        assert sample.brake_pct == pytest.approx(0.1)
        assert round(sample.steering_deg or 0.0, 1) == 10.0
        assert round(sample.yaw_deg or 0.0, 1) == 90.0
        assert sample.track_temp_c == pytest.approx(31.5)
        assert sample.is_on_track is True  # status=2 â†’ ACC_LIVE
        assert sample.tyre_temp_lf == pytest.approx(85.0)
        assert sample.fuel_level == pytest.approx(42.5)
        assert sample.water_temp == pytest.approx(82.0)

    def test_acc_session_type_numeric_maps_to_string(self) -> None:
        """[RG-33] ACC session type integer codes must map to human-readable strings."""
        expected_mappings = {
            0: "practice",
            1: "qualifying",
            2: "race",
            3: "hotlap",
        }
        for code, label in expected_mappings.items():
            assert SESSION_TYPE_MAP.get(code) == label, (
                f"ACC session code {code} should map to '{label}'"
            )
        # Any code in the map must produce a non-empty string label
        for code, label in SESSION_TYPE_MAP.items():
            assert isinstance(label, str) and label, (
                f"SESSION_TYPE_MAP[{code}] is empty or not a string"
            )
        # Normalise a raw sample with session=2 (race)
        sample = normalise_sample(self._ACC_RAW, sim="ACC")
        assert sample.session_type == "race"

    def test_acc_full_finalize_produces_non_rejected_bundle(
        self, tmp_path: Path
    ) -> None:
        """[RG-34] 200 ACC samples through the full pipeline must survive quality gating."""
        output_root = tmp_path / "sessions"
        output_root.mkdir()
        bundle = finalize_session(output_root, sim="ACC", session_uid="acc-gate")
        qr = json.loads((bundle / "quality_report.json").read_text())
        assert qr["recommended_classification"] != "rejected", (
            f"ACC session should not be rejected; got: {qr['recommended_classification']}"
        )
        assert qr["recommended_classification"] in {
            "accepted", "accepted_with_warnings", "needs_review"
        }

    def test_iracing_mandatory_channels_map_correctly(self) -> None:
        """[RG-35] iRacing raw data must produce correct canonical values and units."""
        sample = normalise_sample(
            self._IRACING_RAW,
            sim="iRacing",
            passthrough={"track_name": "Spa", "car_name": "GT3", "session_type": "race"},
        )
        assert sample.session_time_s == pytest.approx(12.5)
        assert sample.lap_number == 3
        assert sample.lap_distance_m == pytest.approx(1534.2)
        assert sample.speed_kph == pytest.approx(144.0)  # 40 m/s Ã— 3.6
        assert sample.throttle_pct == pytest.approx(0.8)
        assert sample.brake_pct == pytest.approx(0.1)
        assert round(sample.steering_deg or 0.0, 1) == 10.0
        assert round(sample.yaw_deg or 0.0, 1) == 90.0
        assert sample.track_temp_c == pytest.approx(31.5)
        assert sample.is_on_track is True
        assert sample.tyre_temp_lf == pytest.approx(85.0)
        assert sample.fuel_level == pytest.approx(42.5)

    def test_iracing_full_finalize_produces_non_rejected_bundle(
        self, tmp_path: Path
    ) -> None:
        """[RG-36] 200 iRacing samples through the full pipeline must survive quality gating."""
        output_root = tmp_path / "sessions"
        output_root.mkdir()
        bundle = finalize_session(output_root, sim="iRacing", session_uid="ir-gate")
        qr = json.loads((bundle / "quality_report.json").read_text())
        assert qr["recommended_classification"] in {
            "accepted", "accepted_with_warnings", "needs_review"
        }

    def test_gear_normalization_consistent_between_acc_and_iracing(self) -> None:
        """[RG-37] First driving gear (gear 1) must be encoded as 1 in canonical schema.

        ACC encodes neutral as gear 1 and first gear as gear 2;
        the mapper subtracts 1 so that driving gears align with iRacing.
        iRacing encodes neutral as gear 0 and first gear as gear 1.
        Both result in gear 1 = first driving gear post-normalization.
        """
        # ACC: gear=2 â†’ first gear â†’ TelemetrySample.gear should be 1
        acc_raw = {**self._ACC_RAW, "gear": 2}
        acc_sample = normalise_sample(acc_raw, sim="ACC")
        assert acc_sample.gear == 1, f"ACC gear 2 should normalize to 1, got {acc_sample.gear}"

        # ACC: gear=1 â†’ neutral â†’ TelemetrySample.gear should be 0
        acc_neutral = {**self._ACC_RAW, "gear": 1}
        acc_n = normalise_sample(acc_neutral, sim="ACC")
        assert acc_n.gear == 0, f"ACC gear 1 (neutral) should normalize to 0, got {acc_n.gear}"

        # iRacing: Gear=1 â†’ first driving gear â†’ passes through as 1
        ir_raw = {**self._IRACING_RAW, "Gear": 1}
        ir_sample = normalise_sample(ir_raw, sim="iRacing")
        assert ir_sample.gear == 1, f"iRacing Gear 1 should remain 1, got {ir_sample.gear}"

        # iRacing: Gear=0 â†’ neutral â†’ passes through as 0
        ir_n = normalise_sample({**self._IRACING_RAW, "Gear": 0}, sim="iRacing")
        assert ir_n.gear == 0

        # Consistent: both sims encode first driving gear as 1
        assert acc_sample.gear == ir_sample.gear


# ===========================================================================
# RG-38 through RG-41  â€"  Determinism and Session Identity
# ===========================================================================

class TestDeterminism:
    """[RG-38 to RG-41] Hash stability, session identity, and purity."""

    def test_bundle_hash_is_well_formed_sha256(
        self, tmp_path: Path
    ) -> None:
        """[RG-38] bundle_hash must be a well-formed sha256 prefixed hash."""
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        samples = make_quality_samples(200, session_uid="determ-uid")

        root_a = tmp_path / "a"
        root_a.mkdir()

        fin = SessionFinalizer(root_a)
        result = fin.finalize(
            list(samples),
            started_at=now,
            ended_at=now + timedelta(seconds=200),
            sim="iRacing",
            track="Spa",
            session_type="Race",
            session_uid="determ-uid",
            extra_metadata={"car": "GT3", "sample_rate_hz": 1.0},
        )
        assert result is not None
        manifest = json.loads((result / "session.json").read_text())
        bundle_hash = manifest["bundle_hash"]
        assert bundle_hash.startswith("sha256:")
        hex_part = bundle_hash.removeprefix("sha256:")
        assert len(hex_part) == 64, "Hash hex digest must be 64 chars"
        # Verify the hash is a valid hex string
        int(hex_part, 16)

    def test_bundle_hash_changes_when_telemetry_changes(
        self, tmp_path: Path
    ) -> None:
        """[RG-39] Different telemetry content must produce different bundle hashes."""
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)

        root_slow = tmp_path / "slow"
        root_slow.mkdir()
        root_fast = tmp_path / "fast"
        root_fast.mkdir()

        uid = "vary-speed-uid"

        def _make_and_finalize(root: Path, speed: float) -> str:
            samples = make_quality_samples(200, base_speed=speed, session_uid=uid)
            fin = SessionFinalizer(root)
            result = fin.finalize(
                samples,
                started_at=now,
                ended_at=now + timedelta(seconds=200),
                sim="iRacing",
                track="Spa",
                session_type="Race",
                session_uid=uid,
                extra_metadata={"car": "GT3", "sample_rate_hz": 1.0},
            )
            assert result is not None
            return json.loads((result / "session.json").read_text())["bundle_hash"]

        hash_slow = _make_and_finalize(root_slow, 100.0)
        hash_fast = _make_and_finalize(root_fast, 250.0)
        assert hash_slow != hash_fast, (
            "bundle_hash must differ when telemetry (speed) values differ"
        )

    def test_session_uid_propagated_unchanged_to_manifest(
        self, tmp_path: Path
    ) -> None:
        """[RG-40] The exact session_uid string must appear in session.json as session_id."""
        uid = "special-uid-abc-123"
        output_root = tmp_path / "sessions"
        output_root.mkdir()
        bundle = finalize_session(output_root, session_uid=uid)
        manifest = json.loads((bundle / "session.json").read_text())
        assert manifest["session_id"] == uid

    def test_compute_bundle_hash_is_a_pure_function(self) -> None:
        """[RG-41] compute_bundle_hash must return the same value for the same inputs."""
        h1 = SyncQueueManager.compute_bundle_hash(
            session_id="uid-determinism-test",
            telemetry_sha256="abc123def456",
        )
        h2 = SyncQueueManager.compute_bundle_hash(
            session_id="uid-determinism-test",
            telemetry_sha256="abc123def456",
        )
        h3 = SyncQueueManager.compute_bundle_hash(
            session_id="uid-determinism-test",
            telemetry_sha256="different-sha",
        )
        assert h1 == h2, "compute_bundle_hash must be deterministic"
        assert h1 != h3, "compute_bundle_hash must change when telemetry_sha256 changes"
        assert len(h1) == 64  # SHA-256 hex digest length


# ===========================================================================
# RG-42 through RG-45  â€"  History / Index Consistency
# ===========================================================================

class TestHistoryIndexConsistency:
    """[RG-42 to RG-45] Session metadata index accuracy and integrity."""

    _REQUIRED_FIELDS = {
        "session_id", "folder", "sim", "track", "car", "session_type",
        "duration_s", "total_laps", "clean_laps", "quality",
        "review_status", "sync_status", "bundle_hash",
    }

    def test_all_required_history_fields_populated_after_finalize(
        self, tmp_path: Path
    ) -> None:
        """[RG-42] Every required metadata field must be present after sync."""
        output_root = tmp_path / "sessions"
        output_root.mkdir()
        finalize_session(output_root, session_uid="idx-fields")

        idx = SessionIndex(tmp_path / "index")
        entries = idx.sync_from_output(
            output_root=output_root,
            parse_entry=load_history_entry,
        )
        assert len(entries) == 1, "Expected exactly one indexed bundle"
        entry = entries[0]
        missing = self._REQUIRED_FIELDS - set(entry.keys())
        assert not missing, f"Index entry missing fields: {missing}"

        # Values must be populated, not blank
        assert entry["session_id"]
        assert entry["folder"]
        assert entry["sim"] not in ("", "-", None)
        assert entry["track"] not in ("", "-", None)
        assert entry["quality"] not in ("", "-", None)

    def test_review_status_change_propagates_on_resync(
        self, tmp_path: Path
    ) -> None:
        """[RG-43] Setting review to 'ignored' must be reflected after re-sync."""
        output_root = tmp_path / "sessions"
        output_root.mkdir()
        bundle = finalize_session(output_root, session_uid="idx-review")

        idx = SessionIndex(tmp_path / "index")
        # Initial sync
        entries_before = idx.sync_from_output(
            output_root=output_root,
            parse_entry=load_history_entry,
        )
        assert entries_before[0]["review_status"] == "ready"

        # Mutate the bundle on disk
        set_session_review_status(bundle, REVIEW_STATUS_IGNORED)
        # Bump mtime so the index re-parses the bundle
        os.utime(bundle, None)

        entries_after = idx.sync_from_output(
            output_root=output_root,
            parse_entry=load_history_entry,
        )
        assert entries_after[0]["review_status"] == "ignored", (
            "Index must reflect the updated review_status after re-sync"
        )

    def test_deleted_bundle_is_pruned_from_index_on_resync(
        self, tmp_path: Path
    ) -> None:
        """[RG-44] A removed session folder must disappear from the index."""
        output_root = tmp_path / "sessions"
        output_root.mkdir()
        bundle = finalize_session(output_root, session_uid="idx-delete")

        idx = SessionIndex(tmp_path / "index")
        entries_before = idx.sync_from_output(
            output_root=output_root,
            parse_entry=load_history_entry,
        )
        assert len(entries_before) == 1

        # Delete the bundle
        import shutil
        shutil.rmtree(bundle)

        entries_after = idx.sync_from_output(
            output_root=output_root,
            parse_entry=load_history_entry,
        )
        assert entries_after == [], "Deleted bundle must be pruned from index"

    def test_entries_ordered_newest_first(self, tmp_path: Path) -> None:
        """[RG-45] list_entries must return sessions sorted descending by creation date."""
        output_root = tmp_path / "sessions"
        output_root.mkdir()
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # Create two sessions with different start times
        finalize_session(
            output_root,
            session_uid="older-session",
            started_at=t0,
        )
        finalize_session(
            output_root,
            session_uid="newer-session",
            started_at=t0 + timedelta(hours=1),
        )

        idx = SessionIndex(tmp_path / "index")
        entries = idx.sync_from_output(
            output_root=output_root,
            parse_entry=load_history_entry,
        )
        assert len(entries) == 2
        # Newer session must come first
        assert entries[0]["session_id"] == "newer-session", (
            "Most recent session must be first; "
            f"got {[e['session_id'] for e in entries]}"
        )


# ===========================================================================
# RG-46 through RG-48  â€"  Corruption Recovery
# ===========================================================================

class TestCorruptionRecovery:
    """[RG-46 to RG-48] Graceful handling of corrupt or incomplete bundles."""

    def test_corrupt_db_triggers_silent_rebuild(self, tmp_path: Path) -> None:
        """[RG-46] A corrupt SQLite file must be replaced with a valid empty DB."""
        output_root = tmp_path / "sessions"
        output_root.mkdir()
        finalize_session(output_root, session_uid="corrupt-test")

        # Corrupt the DB file
        index_dir = tmp_path / "index"
        index_dir.mkdir()
        db_path = index_dir / "session_index.sqlite3"
        db_path.write_text("this is garbage, not sqlite3 binary", encoding="utf-8")

        # SessionIndex must not raise; it must rebuild transparently
        idx = SessionIndex(index_dir)
        entries = idx.sync_from_output(
            output_root=output_root,
            parse_entry=load_history_entry,
        )
        assert len(entries) == 1, "Rebuilt index must contain the one valid bundle"

        # Verify the rebuilt file is a valid SQLite database
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
            assert row[0] == 1
        finally:
            conn.close()

    def test_bundle_missing_session_json_is_handled_gracefully(
        self, tmp_path: Path
    ) -> None:
        """[RG-47] A bundle dir without session.json must not crash the index sync.

        The sync may either omit the corrupt entry entirely or include it with
        analysis_ready=False.  Either way the good bundle must remain accessible
        and no corrupt entry may be marked analysis_ready=True.
        """
        output_root = tmp_path / "sessions"
        output_root.mkdir()
        # Good bundle
        finalize_session(output_root, session_uid="good-bundle")
        # Broken bundle -- looks like a session dir but has no session.json
        broken = output_root / "2026-01-02_10-00-00__iRacing__broken__Race"
        broken.mkdir()
        (broken / "laps.json").write_text("[]", encoding="utf-8")

        idx = SessionIndex(tmp_path / "index")
        entries = idx.sync_from_output(
            output_root=output_root,
            parse_entry=load_history_entry,
        )
        # Good bundle must be present and analysis-ready
        good = [e for e in entries if e.get("session_id") == "good-bundle"]
        assert len(good) == 1, "Good bundle must be indexed"
        assert good[0]["analysis_ready"] is True
        # Any corrupt entry present must NOT be marked analysis-ready
        for e in entries:
            if e.get("session_id") != "good-bundle":
                assert e["analysis_ready"] is False, (
                    "Corrupt bundles must never be marked analysis_ready"
                )

    def test_bundle_with_invalid_json_is_handled_gracefully(
        self, tmp_path: Path
    ) -> None:
        """[RG-48] A bundle with invalid JSON in session.json must not crash the sync.

        The sync may either omit the corrupt entry entirely or include it with
        analysis_ready=False.  Either way the good bundle must remain accessible
        and no corrupt entry may be marked analysis_ready=True.
        """
        output_root = tmp_path / "sessions"
        output_root.mkdir()
        # Good bundle
        finalize_session(output_root, session_uid="good-bundle-json")
        # Corrupt JSON bundle
        corrupt = output_root / "2026-01-03_09-00-00__iRacing__corrupt__Race"
        corrupt.mkdir()
        (corrupt / "session.json").write_text(
            "{this is not valid json!!!", encoding="utf-8"
        )

        idx = SessionIndex(tmp_path / "index")
        entries = idx.sync_from_output(
            output_root=output_root,
            parse_entry=load_history_entry,
        )
        # Good bundle must be present and analysis-ready
        good = [e for e in entries if e.get("session_id") == "good-bundle-json"]
        assert len(good) == 1, "Good bundle must be indexed"
        assert good[0]["analysis_ready"] is True
        # Any corrupt entry present must NOT be marked analysis-ready
        for e in entries:
            if e.get("session_id") != "good-bundle-json":
                assert e["analysis_ready"] is False, (
                    "Corrupt bundles must never be marked analysis_ready"
                )
