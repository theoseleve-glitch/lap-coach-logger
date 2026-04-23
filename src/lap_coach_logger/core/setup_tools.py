"""Local setup library, diff, and file-management helpers for lap_pc."""

from __future__ import annotations

import configparser
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


_SIM_ROOTS = {
    "ACC": [
        Path.home() / "Documents" / "Assetto Corsa Competizione" / "Setups",
    ],
    "Assetto Corsa": [
        Path.home() / "Documents" / "Assetto Corsa" / "setups",
    ],
    "iRacing": [
        Path.home() / "Documents" / "iRacing" / "setups",
    ],
    "Le Mans Ultimate": [
        Path.home() / "Documents" / "My Games" / "Le Mans Ultimate" / "Setups",
        Path.home() / "Documents" / "Le Mans Ultimate" / "Setups",
    ],
}

_SIM_EXTENSIONS = {
    "ACC": {".json"},
    "Assetto Corsa": {".ini"},
    "iRacing": {".sto", ""},
    "Le Mans Ultimate": {".json", ".ini", ".svm"},
}

_ARRAY_LABELS = {
    2: ("Front", "Rear"),
    4: ("LF", "RF", "LR", "RR"),
}


@dataclass(slots=True)
class SetupEntry:
    id: str
    sim: str
    path: Path
    name: str
    car: str
    track: str
    format: str
    modified_ts: float
    size_bytes: int
    is_current: bool
    is_favorite: bool
    can_parse: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "sim": self.sim,
            "path": str(self.path),
            "name": self.name,
            "car": self.car,
            "track": self.track,
            "format": self.format,
            "modified_ts": self.modified_ts,
            "size_bytes": self.size_bytes,
            "is_current": self.is_current,
            "is_favorite": self.is_favorite,
            "can_parse": self.can_parse,
        }


def scan_setup_library(
    *,
    sim_preference: str | None = None,
    live: Mapping[str, object] | None = None,
    favorites: Iterable[str] = (),
    docs_root: Path | None = None,
    limit: int = 200,
) -> dict[str, object]:
    favorite_ids = {str(Path(path)) for path in favorites}
    entries_by_sim: dict[str, list[SetupEntry]] = {}

    for sim_name, roots in _candidate_roots(docs_root).items():
        entries = _scan_sim_entries(sim_name, roots, favorite_ids, limit=limit)
        if entries:
            entries_by_sim[sim_name] = entries

    active_sim = str((live or {}).get("sim") or "").strip() or None
    selected_sim = _choose_sim(entries_by_sim, sim_preference=sim_preference, active_sim=active_sim)
    if selected_sim is None:
        return {
            "status": "missing",
            "sim": sim_preference or active_sim or "-",
            "root": None,
            "entries": [],
            "current_setup_id": None,
            "current_setup_name": None,
            "current_setup_rows": [],
            "diff_default_a_id": None,
            "diff_default_b_id": None,
        }

    entries = entries_by_sim[selected_sim]
    current_entry = _find_current_entry(entries, live=live)
    diff_a, diff_b = _default_compare_pair(entries, current_entry)
    root = _first_existing_root(_candidate_roots(docs_root)[selected_sim])
    current_rows: list[dict[str, object]] = []
    if current_entry is not None:
        current_rows = read_setup_rows(current_entry.path, current_entry.format)[:20]

    return {
        "status": "ready",
        "sim": selected_sim,
        "root": str(root) if root is not None else None,
        "entries": [entry.to_dict() for entry in entries],
        "current_setup_id": current_entry.id if current_entry is not None else None,
        "current_setup_name": current_entry.name if current_entry is not None else None,
        "current_setup_rows": current_rows,
        "diff_default_a_id": diff_a.id if diff_a is not None else None,
        "diff_default_b_id": diff_b.id if diff_b is not None else None,
    }


def build_setup_diff(
    entry_a: Mapping[str, object] | None,
    entry_b: Mapping[str, object] | None,
) -> list[dict[str, object]]:
    if not isinstance(entry_a, Mapping) or not isinstance(entry_b, Mapping):
        return []

    path_a = _path_from_entry(entry_a)
    path_b = _path_from_entry(entry_b)
    format_a = str(entry_a.get("format") or "")
    format_b = str(entry_b.get("format") or "")
    if path_a is None or path_b is None:
        return []

    rows_a = read_setup_rows(path_a, format_a)
    rows_b = read_setup_rows(path_b, format_b)
    values_a = {str(row["key"]): row for row in rows_a if isinstance(row, dict) and "key" in row}
    values_b = {str(row["key"]): row for row in rows_b if isinstance(row, dict) and "key" in row}

    if not values_a or not values_b:
        return [{
            "key": "binary.diff",
            "value_a": f"{path_a.name} ({path_a.stat().st_size} B)",
            "value_b": f"{path_b.name} ({path_b.stat().st_size} B)",
            "effect": "Structured diff is unavailable for this setup format.",
        }]

    changed_rows: list[dict[str, object]] = []
    for key in sorted(set(values_a) | set(values_b)):
        value_a = values_a.get(key, {}).get("display")
        value_b = values_b.get(key, {}).get("display")
        if value_a == value_b:
            continue
        changed_rows.append({
            "key": key,
            "value_a": value_a or "-",
            "value_b": value_b or "-",
            "effect": describe_setup_effect(key),
        })
    return changed_rows


def read_setup_rows(path: Path, format_name: str) -> list[dict[str, object]]:
    suffix = format_name.lower() or path.suffix.lower()
    if suffix == "json" or path.suffix.lower() == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        rows: list[dict[str, object]] = []
        _flatten_json_rows(rows, data)
        return rows

    if suffix == "ini" or path.suffix.lower() in {".ini", ".svm"}:
        parser = configparser.ConfigParser()
        parser.optionxform = str
        try:
            parser.read(path, encoding="utf-8")
        except Exception:
            try:
                parser.read(path, encoding="utf-16")
            except Exception:
                return []
        rows: list[dict[str, object]] = []
        for section in parser.sections():
            items = list(parser.items(section))
            if len(items) == 1 and items[0][0].upper() == "VALUE":
                rows.append(_make_row(section, items[0][1]))
                continue
            for key, value in items:
                if section == "__EXT_PATCH":
                    continue
                rows.append(_make_row(f"{section}.{key}", value))
        return rows

    return []


def install_setup_file(
    source_path: Path,
    destination_dir: Path,
    *,
    new_name: str | None = None,
) -> tuple[Path, dict[str, object]]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    source = source_path.expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(str(source))

    base_name = _sanitize_file_name(new_name or source.stem)
    target = _unique_path(destination_dir / f"{base_name}{source.suffix}")
    return _copy_with_rollback(source, target)


def duplicate_setup_file(source_path: Path, new_name: str) -> tuple[Path, dict[str, object]]:
    source = source_path.expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(str(source))
    if not new_name.strip():
        raise ValueError("A new setup name is required.")

    target = _unique_path(source.with_name(f"{_sanitize_file_name(new_name)}{source.suffix}"))
    return _copy_with_rollback(source, target)


def rollback_setup_operation(operation: Mapping[str, object] | None) -> str:
    if not isinstance(operation, Mapping):
        raise ValueError("No setup operation is available to roll back.")

    target = Path(str(operation.get("target_path") or ""))
    backup = Path(str(operation.get("backup_path") or "")) if operation.get("backup_path") else None
    created_path = Path(str(operation.get("created_path") or "")) if operation.get("created_path") else None

    if backup is not None and backup.exists():
        if target.exists():
            target.unlink()
        backup.replace(target)
        return f"Rolled back {target.name}"

    if created_path is not None and created_path.exists():
        created_path.unlink()
        return f"Removed {created_path.name}"

    raise ValueError("Nothing could be rolled back.")


def save_setup_to_bundle(setup_path: Path, bundle_dir: Path) -> Path:
    setup = setup_path.expanduser().resolve()
    if not setup.exists() or not setup.is_file():
        raise FileNotFoundError(str(setup))
    bundle_dir.mkdir(parents=True, exist_ok=True)
    target = _unique_path(bundle_dir / f"setup__{_sanitize_file_name(setup.stem)}{setup.suffix}")
    shutil.copy2(setup, target)
    return target


def describe_setup_effect(key: str) -> str:
    normalized = key.lower()
    if "brakebias" in normalized or "front_bias" in normalized or "brake_bias" in normalized:
        return "More front bias adds braking stability but can increase entry understeer. Less front bias helps rotation but risks rear instability."
    if "brake" in normalized and any(token in normalized for token in ("torque", "power", "pad", "duct")):
        return "Brake changes trade stopping confidence, temperature control, and lockup risk."
    if "pressure" in normalized:
        return "Higher pressure supports the tyre more and can sharpen response; lower pressure adds compliance and heat generation."
    if "camber" in normalized:
        return "More negative camber usually helps mid-corner grip but can hurt traction and braking."
    if "toe" in normalized:
        return "Toe changes affect initial response, straight-line stability, and tyre scrub."
    if "arb" in normalized:
        if "front" in normalized:
            return "A stiffer front anti-roll bar generally adds understeer and entry stability."
        if "rear" in normalized:
            return "A stiffer rear anti-roll bar generally adds rotation and oversteer risk."
        return "Anti-roll bar changes move lateral balance between stability and rotation."
    if "spring" in normalized or "wheelrate" in normalized or "bumpstop" in normalized or "packer" in normalized:
        return "Spring and bump-stop changes trade platform control against kerb compliance and traction."
    if "rideheight" in normalized or "rod_length" in normalized or "rodlength" in normalized:
        return "Ride-height changes trade aero efficiency against bottoming margin and platform control."
    if "wing" in normalized or "splitter" in normalized:
        return "Aero changes trade top speed against high-speed stability and balance."
    if "preload" in normalized or "diff" in normalized:
        return "Differential changes affect traction, entry rotation, and throttle stability."
    if "fuel" in normalized:
        return "Fuel changes alter weight, balance, and stint length."
    if "tc" in normalized or "abs" in normalized or "map" in normalized:
        return "Electronics changes alter intervention level, driveability, and tyre management."
    return "This change shifts balance, platform, or tyre load distribution. Verify it against lap behavior."


def entry_map(entries: Iterable[Mapping[str, object]]) -> dict[str, dict[str, object]]:
    mapped: dict[str, dict[str, object]] = {}
    for entry in entries:
        setup_id = str(entry.get("id") or "")
        if setup_id:
            mapped[setup_id] = dict(entry)
    return mapped


def load_json_list(path: Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item) for item in payload if isinstance(item, str)]


def save_json_list(path: Path, values: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted({str(value) for value in values})
    path.write_text(json.dumps(ordered, indent=2), encoding="utf-8")


def _candidate_roots(docs_root: Path | None) -> dict[str, list[Path]]:
    if docs_root is None:
        return {sim: list(paths) for sim, paths in _SIM_ROOTS.items()}
    docs_root = docs_root.expanduser().resolve()
    return {
        "ACC": [docs_root / "Assetto Corsa Competizione" / "Setups"],
        "Assetto Corsa": [docs_root / "Assetto Corsa" / "setups"],
        "iRacing": [docs_root / "iRacing" / "setups"],
        "Le Mans Ultimate": [
            docs_root / "My Games" / "Le Mans Ultimate" / "Setups",
            docs_root / "Le Mans Ultimate" / "Setups",
        ],
    }


def _scan_sim_entries(
    sim_name: str,
    roots: list[Path],
    favorite_ids: set[str],
    *,
    limit: int,
) -> list[SetupEntry]:
    extensions = _SIM_EXTENSIONS[sim_name]
    entries: list[SetupEntry] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in extensions and not (sim_name == "iRacing" and path.name == "-Current-"):
                continue
            stat = path.stat()
            car, track = _derive_car_track(sim_name, root, path)
            resolved = str(path.resolve())
            entries.append(
                SetupEntry(
                    id=resolved,
                    sim=sim_name,
                    path=path.resolve(),
                    name=path.name,
                    car=car,
                    track=track,
                    format=_format_name_for_path(path),
                    modified_ts=stat.st_mtime,
                    size_bytes=stat.st_size,
                    is_current=path.name.lower() in {"last.ini", "-current-"} or path.stem.lower() == "current",
                    is_favorite=resolved in favorite_ids,
                    can_parse=path.suffix.lower() in {".json", ".ini", ".svm"},
                )
            )
    entries.sort(key=lambda entry: (not entry.is_favorite, not entry.is_current, -entry.modified_ts))
    return entries[:limit]


def _choose_sim(
    entries_by_sim: Mapping[str, list[SetupEntry]],
    *,
    sim_preference: str | None,
    active_sim: str | None,
) -> str | None:
    for candidate in (sim_preference, active_sim):
        if candidate and candidate in entries_by_sim:
            return candidate
    newest: tuple[float, str] | None = None
    for sim_name, entries in entries_by_sim.items():
        latest_ts = max((entry.modified_ts for entry in entries), default=0.0)
        if newest is None or latest_ts > newest[0]:
            newest = (latest_ts, sim_name)
    return newest[1] if newest is not None else None


def _find_current_entry(
    entries: list[SetupEntry],
    *,
    live: Mapping[str, object] | None,
) -> SetupEntry | None:
    for entry in entries:
        if entry.is_current:
            return entry

    live_track = _normalize_name(str((live or {}).get("track_name") or ""))
    live_car = _normalize_name(str((live or {}).get("car_name") or ""))
    if live_track or live_car:
        scored: list[tuple[int, float, SetupEntry]] = []
        for entry in entries:
            score = 0
            if live_track and _normalize_name(entry.track) == live_track:
                score += 2
            if live_car and _normalize_name(entry.car) == live_car:
                score += 2
            if score > 0:
                scored.append((score, entry.modified_ts, entry))
        if scored:
            scored.sort(key=lambda item: (-item[0], -item[1]))
            return scored[0][2]

    return entries[0] if entries else None


def _default_compare_pair(entries: list[SetupEntry], current_entry: SetupEntry | None) -> tuple[SetupEntry | None, SetupEntry | None]:
    if not entries:
        return None, None
    first = current_entry or entries[0]
    second = next((entry for entry in entries if entry.id != first.id), None)
    return first, second or first


def _derive_car_track(sim_name: str, root: Path, path: Path) -> tuple[str, str]:
    rel_parts = path.relative_to(root).parts
    if sim_name == "ACC" and len(rel_parts) >= 3:
        return rel_parts[-3], rel_parts[-2]
    if sim_name == "Assetto Corsa" and len(rel_parts) >= 3:
        return rel_parts[-3], rel_parts[-2]
    if sim_name == "iRacing" and len(rel_parts) >= 2:
        car = rel_parts[0]
        track = rel_parts[-2] if len(rel_parts) >= 3 else "Generic"
        return car, track
    if sim_name == "Le Mans Ultimate" and len(rel_parts) >= 3:
        return rel_parts[-3], rel_parts[-2]
    return "Unknown", "Unknown"


def _flatten_json_rows(rows: list[dict[str, object]], value: object, prefix: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            _flatten_json_rows(rows, child, next_prefix)
        return

    if isinstance(value, list):
        labels = _ARRAY_LABELS.get(len(value))
        for index, child in enumerate(value):
            if labels is not None:
                suffix = labels[index]
            else:
                suffix = str(index)
            next_prefix = f"{prefix}[{suffix}]"
            _flatten_json_rows(rows, child, next_prefix)
        return

    rows.append(_make_row(prefix, value))


def _make_row(key: str, value: object) -> dict[str, object]:
    return {
        "key": key,
        "value": value,
        "display": _display_value(value),
    }


def _copy_with_rollback(source: Path, target: Path) -> tuple[Path, dict[str, object]]:
    target = _unique_path(target) if not target.exists() or source.resolve() == target.resolve() else target
    operation: dict[str, object] = {
        "target_path": str(target),
        "created_path": str(target),
    }

    if target.exists():
        backup = target.with_name(f"{target.name}.lapcoach.bak")
        if backup.exists():
            backup.unlink()
        shutil.copy2(target, backup)
        operation["backup_path"] = str(backup)

    shutil.copy2(source, target)
    return target, operation


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _display_value(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def _sanitize_file_name(value: str) -> str:
    cleaned = re.sub(r"[<>:\"/\\\\|?*]+", "_", value.strip())
    return cleaned or "setup"


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _format_name_for_path(path: Path) -> str:
    if path.suffix:
        return path.suffix.lstrip(".").upper()
    return "BIN"


def _first_existing_root(roots: Iterable[Path]) -> Path | None:
    return next((path for path in roots if path.exists()), None)


def _path_from_entry(entry: Mapping[str, object]) -> Path | None:
    raw = str(entry.get("path") or "")
    if not raw:
        return None
    path = Path(raw)
    return path if path.exists() else None


def file_fingerprint(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
