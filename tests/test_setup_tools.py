from __future__ import annotations

import json
from pathlib import Path

from lap_coach_logger.core.setup_tools import (
    build_setup_diff,
    duplicate_setup_file,
    entry_map,
    install_setup_file,
    rollback_setup_operation,
    save_setup_to_bundle,
    scan_setup_library,
)


def test_scan_setup_library_prefers_active_sim_and_picks_matching_current_setup(tmp_path: Path) -> None:
    docs_root = tmp_path / "Documents"
    acc_root = docs_root / "Assetto Corsa Competizione" / "Setups" / "ferrari_488_gt3" / "Spa"
    acc_root.mkdir(parents=True)
    (acc_root / "stable.json").write_text(json.dumps(_acc_setup(brake_bias=56, rear_wing=8)), encoding="utf-8")
    matching = acc_root / "attack.json"
    matching.write_text(json.dumps(_acc_setup(brake_bias=54, rear_wing=10)), encoding="utf-8")

    ac_root = docs_root / "Assetto Corsa" / "setups" / "ks_ferrari_sf70h" / "generic"
    ac_root.mkdir(parents=True)
    (ac_root / "last.ini").write_text("[WING_1]\nVALUE=12\n", encoding="utf-8")

    snapshot = scan_setup_library(
        sim_preference=None,
        live={"sim": "ACC", "car_name": "ferrari_488_gt3", "track_name": "Spa"},
        docs_root=docs_root,
        favorites=[str(matching.resolve())],
    )

    assert snapshot["status"] == "ready"
    assert snapshot["sim"] == "ACC"
    assert snapshot["current_setup_name"] == "attack.json"
    entries = entry_map(snapshot["entries"])
    assert str(matching.resolve()) in entries
    assert entries[str(matching.resolve())]["is_favorite"] is True


def test_build_setup_diff_returns_changed_values_only_with_effects(tmp_path: Path) -> None:
    setup_a = tmp_path / "setup_a.json"
    setup_b = tmp_path / "setup_b.json"
    setup_a.write_text(json.dumps(_acc_setup(brake_bias=56, rear_wing=8)), encoding="utf-8")
    setup_b.write_text(json.dumps(_acc_setup(brake_bias=54, rear_wing=11)), encoding="utf-8")

    diff_rows = build_setup_diff(
        {"path": str(setup_a), "format": "JSON"},
        {"path": str(setup_b), "format": "JSON"},
    )

    diff_keys = {row["key"] for row in diff_rows}

    assert "advancedSetup.mechanicalBalance.brakeBias" in diff_keys
    assert "advancedSetup.aeroBalance.rearWing" in diff_keys
    assert all(row["effect"] for row in diff_rows)
    assert all(row["value_a"] != row["value_b"] for row in diff_rows)


def test_setup_file_operations_install_duplicate_rollback_and_bundle_save(tmp_path: Path) -> None:
    source = tmp_path / "external.ini"
    source.write_text("[FRONT_BIAS]\nVALUE=54\n", encoding="utf-8")
    destination_dir = tmp_path / "Assetto Corsa" / "setups" / "ks_ferrari_sf70h" / "generic"
    destination_dir.mkdir(parents=True)

    installed_path, install_operation = install_setup_file(source, destination_dir)
    assert installed_path.exists()
    assert installed_path.parent == destination_dir

    duplicated_path, duplicate_operation = duplicate_setup_file(installed_path, "race_trim")
    assert duplicated_path.exists()
    assert duplicated_path.name == "race_trim.ini"

    message = rollback_setup_operation(duplicate_operation)
    assert "race_trim.ini" in message
    assert not duplicated_path.exists()

    bundle_dir = tmp_path / "bundle"
    saved_bundle_path = save_setup_to_bundle(installed_path, bundle_dir)
    assert saved_bundle_path.exists()
    assert saved_bundle_path.parent == bundle_dir

    rollback_message = rollback_setup_operation(install_operation)
    assert installed_path.name in rollback_message
    assert not installed_path.exists()


def _acc_setup(*, brake_bias: int, rear_wing: int) -> dict[str, object]:
    return {
        "carName": "ferrari_488_gt3",
        "basicSetup": {
            "strategy": {
                "fuel": 36,
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
