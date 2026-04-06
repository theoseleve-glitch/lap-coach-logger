# Evaluation Gate — Coaching Ingestion Readiness Checklist

This document defines the **minimum correctness requirements** the logger must
satisfy before being connected as an ingestion source for automated coaching
evaluation.  Every item in this checklist maps 1-to-1 to a test in
`tests/test_evaluation_gate.py`.

---

## How to run the gate

```powershell
# Full suite (all 112+ tests)
python -m pytest tests -q

# Gate-only (fast, CI-friendly)
python -m pytest tests/test_evaluation_gate.py -v

# Gate-only in strict mode — fail immediately on the first failure
python -m pytest tests/test_evaluation_gate.py -x -v
```

A build is **evaluation-ready** only when all gate tests pass with exit code 0.

---

## Checklist

Symbols: ✅ = checked automatically | ⬛ = manual step outside test scope

### 1 — State Machine Correctness

| ID | Check | Test |
|----|-------|------|
| RG-01 | FSM completes full IDLE → READY_FOR_REVIEW happy path | `test_happy_path_reaches_ready_for_review` |
| RG-02 | Every illegal state transition is rejected (36 invalid pairs) | `test_every_invalid_transition_is_rejected` (parametrized) |
| RG-03 | Abrupt disconnect path FAILED → FINALIZING → READY_FOR_REVIEW succeeds | `test_abrupt_disconnect_failed_path_reaches_ready_for_review` |
| RG-04 | `on_enter` callback crash does not abort or corrupt state | `test_on_enter_exception_does_not_corrupt_state` |
| RG-05 | FSM supports back-to-back sessions via READY_FOR_REVIEW → WAITING | `test_ready_for_review_allows_next_session` |

### 2 — Bundle Integrity

| ID | Check | Test |
|----|-------|------|
| RG-06 | All 7 required bundle files present after finalize | `test_all_seven_required_files_present` |
| RG-07 | `session_id` in `session.json` equals the caller-supplied `session_uid` | `test_session_id_matches_supplied_uid` |
| RG-08 | `session_id` is never silently overwritten by the folder name | `test_session_id_not_derived_from_folder_name` |
| RG-09 | `session_folder_name()` is deterministic for identical inputs | `test_folder_name_is_deterministic_for_fixed_inputs` |
| RG-10 | No `_tmp_` directory survives a successful finalize | `test_no_tmp_directory_left_after_successful_finalize` |
| RG-11 | `session.json` and `metadata.json` are cross-consistent | `test_session_json_and_metadata_json_are_consistent` |
| RG-12 | `telemetry_sha256` in manifest verifies the actual file on disk | `test_telemetry_sha256_in_manifest_verifies_actual_file` |

### 3 — Normalized Schema Generation

| ID | Check | Test |
|----|-------|------|
| RG-13 | All 40+ canonical `TelemetrySample` fields appear as CSV column headers | `test_all_canonical_fields_present_in_csv_header` |
| RG-14 | `None`-valued optional fields serialize as empty CSV cells, not `"None"` strings | `test_none_fields_serialized_as_empty_not_none_string` |
| RG-15 | ACC and iRacing sessions produce identical column sets | `test_acc_and_iracing_sessions_produce_identical_column_sets` |
| RG-16 | `TELEMETRY_SCHEMA_VERSION` constant equals `"2.0.0"` | `test_telemetry_schema_version_constant` |
| — | `channels.json` declares all canonical channels | `test_channels_json_lists_all_canonical_channels` |

### 4 — Quality Gate Behavior

| ID | Check | Test |
|----|-------|------|
| RG-17 | `overall_quality_score` is always within `[0.0, 1.0]` for any input | `test_quality_score_always_in_unit_interval` |
| RG-18 | Exactly `min_samples − 1` samples triggers `too_few_samples` rejection | `test_exactly_min_samples_minus_one_triggers_rejection` |
| RG-19 | Session duration below `min_duration_s` triggers duration rejection | `test_session_under_min_duration_triggers_rejection` |
| RG-20 | A well-formed accepted session has zero `rejection_reasons` | `test_accepted_session_has_zero_rejection_reasons` |
| RG-21 | `quality_classification` in `session.json` matches `quality_report.json` | `test_manifest_quality_classification_matches_quality_report` |

### 5 — Lap Classification Behavior

| ID | Check | Test |
|----|-------|------|
| RG-22 | Out-lap is never counted as a clean lap | `test_out_lap_is_never_counted_as_clean` |
| RG-23 | Pit lap is not `valid_for_analysis` | `test_pit_lap_is_not_valid_for_analysis` |
| RG-24 | `best_clean_lap_time_s` equals the minimum clean lap time | `test_best_clean_lap_time_is_minimum_of_all_clean_times` |
| RG-25 | `representative_lap_number` picks the lap closest to the median clean time | `test_representative_lap_picks_median_clean_time` |
| RG-26 | Off-track excursions and spin/reset events both invalidate their lap | `test_offtrack_and_spin_both_invalidate_their_laps` |

### 6 — Finalize After Abrupt Disconnect

| ID | Check | Test |
|----|-------|------|
| RG-27 | FSM RECORDING → FAILED → FINALIZING → READY_FOR_REVIEW path works | `test_fsm_recording_failed_finalizing_ready_path` |
| RG-28 | `finalize()` with zero samples returns `None` (no partial bundle) | `test_finalize_with_zero_samples_returns_none` |
| RG-29 | A below-threshold sample count still writes a bundle with `quality=rejected` | `test_finalize_with_few_samples_produces_rejected_quality` |
| RG-30 | Calling `finalize()` with `ended_at=None` produces a valid bundle | `test_finalize_with_ended_at_none_still_produces_bundle` |
| RG-31 | No `_tmp_` dir survives any finalize outcome (success or abort) | `test_no_tmp_dir_left_after_any_finalize_outcome` |

### 7 — Simulator Compatibility (ACC + iRacing)

| ID | Check | Test |
|----|-------|------|
| RG-32 | ACC raw packet → correct canonical channel values and units | `test_acc_mandatory_channels_map_correctly` |
| RG-33 | ACC session type integer codes map to human-readable strings | `test_acc_session_type_numeric_maps_to_string` |
| RG-34 | 200 ACC samples through full pipeline produce non-rejected bundle | `test_acc_full_finalize_produces_non_rejected_bundle` |
| RG-35 | iRacing raw packet → correct canonical channel values with unit conversions | `test_iracing_mandatory_channels_map_correctly` |
| RG-36 | 200 iRacing samples through full pipeline produce non-rejected bundle | `test_iracing_full_finalize_produces_non_rejected_bundle` |
| RG-37 | Gear encoding is consistent: first driving gear = 1 in both adapters | `test_gear_normalization_consistent_between_acc_and_iracing` |

### 8 — Determinism

| ID | Check | Test |
|----|-------|------|
| RG-38 | `bundle_hash` is stable: identical inputs always produce the same hash | `test_bundle_hash_stable_for_identical_finalizes` |
| RG-39 | `bundle_hash` changes when telemetry content changes | `test_bundle_hash_changes_when_telemetry_changes` |
| RG-40 | Supplied `session_uid` is propagated unchanged to `session.json` | `test_session_uid_propagated_unchanged_to_manifest` |
| RG-41 | `SyncQueueManager.compute_bundle_hash()` is a pure function | `test_compute_bundle_hash_is_a_pure_function` |

### 9 — History / Index Consistency

| ID | Check | Test |
|----|-------|------|
| RG-42 | All required metadata fields populated in index after finalize + sync | `test_all_required_history_fields_populated_after_finalize` |
| RG-43 | Review status change on disk propagates to index on next sync | `test_review_status_change_propagates_on_resync` |
| RG-44 | Deleted bundle is pruned from index on next sync | `test_deleted_bundle_is_pruned_from_index_on_resync` |
| RG-45 | `list_entries` returns sessions sorted newest-first | `test_entries_ordered_newest_first` |

### 10 — Corruption Recovery

| ID | Check | Test |
|----|-------|------|
| RG-46 | Corrupt SQLite file triggers silent rebuild with a valid new database | `test_corrupt_db_triggers_silent_rebuild` |
| RG-47 | Bundle directory missing `session.json` is skipped without crashing | `test_bundle_missing_session_json_is_skipped` |
| RG-48 | Bundle directory with invalid JSON in `session.json` is skipped without crashing | `test_bundle_with_invalid_json_is_skipped` |

---

## CI Integration

### GitHub Actions (recommended)

Create `.github/workflows/gate.yml`:

```yaml
name: Evaluation Gate

on:
  push:
    branches: [main, release/**]
  pull_request:

jobs:
  gate:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run full test suite
        run: python -m pytest tests -q --tb=short
      - name: Run evaluation gate (strict)
        run: python -m pytest tests/test_evaluation_gate.py -v --tb=long
```

### Local pre-release gate command

```powershell
python -m pytest tests/test_evaluation_gate.py -v --tb=short 2>&1 | Tee-Object gate_results.txt
if ($LASTEXITCODE -ne 0) { Write-Error "GATE FAILED — build is not evaluation-ready" }
```

---

## Release Note Template

```
## Release Gate Status

Date: YYYY-MM-DD
Build: vX.Y.Z

Gate suite: tests/test_evaluation_gate.py
Total gate checks: 48
Passed: NN
Failed: 0

Status: EVALUATION-READY ✅
```

---

## What "evaluation-ready" means

A passing gate means the logger guarantees:

1. **Bundle completeness** — every session on disk has all required files with
   consistent cross-file metadata.
2. **Schema stability** — the canonical `TelemetrySample` schema is complete
   and will not silently drop or corrupt fields during write.
3. **Quality classification accuracy** — the quality gate correctly rejects or
   classifies all sessions before they enter the coaching pipeline.
4. **Lap-level ground truth** — lap classifications (clean, invalid, out, pit)
   are accurate and best-lap timing is mathematically correct.
5. **Simulator interoperability** — ACC and iRacing data reduce to the same
   canonical format so downstream code can be sim-agnostic.
6. **Session identity integrity** — `session_id` and `bundle_hash` are stable
   identifiers that can be safely used as foreign keys in a coaching database.
7. **Resilience** — partial or corrupt data never crashes the indexer or
   leaves stale temporary artifacts on disk.

---

## Known scope exclusions

The following are **not** covered by this gate and require separate validation:

| Area | Reason |
|------|--------|
| Live UI panel correctness | Requires Qt event loop; covered by manual QA |
| Actual SHM adapter reads (ACC/iRacing processes) | Requires live sim; integration environment only |
| `SyncService` upload path | Disabled by default (`DisabledSyncService`); gate when a real backend is wired |
| Parquet write path | CSV is the primary format; Parquet fallback tested by `test_writer_fallback.py` |
| Windows installer behavior | Covered by `RELEASE_CHECKLIST.md` manual steps |
