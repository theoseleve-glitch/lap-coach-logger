"""SQLite-backed local metadata index for saved session bundles."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)

_DB_FILE = "session_index.sqlite3"
_SCHEMA_VERSION = 1
_DEFAULT_RECENT_SCAN_LIMIT = 150


class SessionIndex:
    """Durable metadata index with incremental rebuild and corruption recovery."""

    def __init__(self, cache_dir: str | Path) -> None:
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._cache_dir / _DB_FILE
        self._conn = self._open_or_repair()
        self._ensure_schema()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def close(self) -> None:
        self._conn.close()

    def sync_from_output(
        self,
        *,
        output_root: Path,
        parse_entry: Callable[[Path], dict[str, Any]],
        max_dirs: int | None = 150,
        recent_scan_limit: int | None = _DEFAULT_RECENT_SCAN_LIMIT,
    ) -> list[dict[str, Any]]:
        """Incrementally sync index from output directory and return indexed entries.

        The index always preserves older bundles once discovered. Recent bundles are
        rescanned on every refresh, and if the output directory contains bundles
        that have never been indexed, the full archive is scanned until the index
        catches up.
        """
        output_root = Path(output_root)
        if not output_root.exists():
            self.clear()
            return []

        dirs = [p for p in output_root.iterdir() if p.is_dir() and not p.name.startswith("_tmp_")]
        dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        actual_paths = {str(folder) for folder in dirs}
        indexed_paths = self._indexed_paths()

        if recent_scan_limit is None or not actual_paths.issubset(indexed_paths):
            dirs_to_scan = dirs
        else:
            dirs_to_scan = dirs[:recent_scan_limit]

        for folder in dirs_to_scan:
            folder_str = str(folder)
            try:
                bundle_mtime = folder.stat().st_mtime
            except OSError:
                continue

            current = self._get_indexed_mtime(folder_str)
            if isinstance(current, float) and abs(current - bundle_mtime) < 1e-6:
                continue

            try:
                parsed = parse_entry(folder)
                self._upsert_from_entry(parsed, bundle_mtime=bundle_mtime)
            except Exception:
                log.debug("Skipping index update for %s (parse failed)", folder, exc_info=True)

        self._delete_missing_entries(actual_paths=actual_paths)
        return self.list_entries(limit=max_dirs)

    def list_entries(self, *, limit: int | None = 150) -> list[dict[str, Any]]:
        query = """
            SELECT
                session_id,
                path,
                created_at,
                simulator,
                track,
                car,
                session_type,
                duration_s,
                lap_count,
                clean_lap_count,
                best_lap_s,
                quality_classification,
                review_status,
                sync_status,
                bundle_hash,
                schema_version,
                sample_count,
                ended_at_utc,
                bundle_mtime
            FROM sessions
            ORDER BY COALESCE(created_at, ended_at_utc, '') DESC
            """
        params: tuple[object, ...] = ()
        if limit is not None:
            query = f"{query}\nLIMIT ?"
            params = (int(limit),)

        cur = self._conn.execute(query, params)
        rows = cur.fetchall()
        return [self._row_to_entry(row) for row in rows]

    def get_unique_values(self, field: str) -> list[str]:
        field_map = {
            "sim": "simulator",
            "track": "track",
            "car": "car",
            "quality": "quality_classification",
            "sync_status": "sync_status",
            "session_type": "session_type",
        }
        col = field_map.get(field)
        if not col:
            return []

        cur = self._conn.execute(
            f"SELECT DISTINCT {col} FROM sessions WHERE {col} IS NOT NULL AND {col} NOT IN ('', '-') ORDER BY {col} COLLATE NOCASE"
        )
        return [str(r[0]) for r in cur.fetchall() if r and r[0] is not None]

    def remove_entry(self, folder: str | Path) -> None:
        self._conn.execute("DELETE FROM sessions WHERE path = ?", (str(folder),))
        self._conn.commit()

    def clear(self) -> None:
        self._conn.execute("DELETE FROM sessions")
        self._conn.commit()

    def __len__(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM sessions")
        value = cur.fetchone()
        return int(value[0]) if value else 0

    def _upsert_from_entry(self, entry: dict[str, Any], *, bundle_mtime: float) -> None:
        path = str(entry.get("folder") or entry.get("path") or "")
        if not path:
            return

        created_at = self._best_created_at(entry)
        schema_version = str(entry.get("schema_version") or "")

        self._conn.execute(
            """
            INSERT INTO sessions (
                session_id, path, created_at, simulator, track, car, session_type,
                duration_s, lap_count, clean_lap_count, best_lap_s,
                quality_classification, review_status, sync_status,
                bundle_hash, schema_version, sample_count, ended_at_utc, bundle_mtime,
                indexed_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                session_id=excluded.session_id,
                created_at=excluded.created_at,
                simulator=excluded.simulator,
                track=excluded.track,
                car=excluded.car,
                session_type=excluded.session_type,
                duration_s=excluded.duration_s,
                lap_count=excluded.lap_count,
                clean_lap_count=excluded.clean_lap_count,
                best_lap_s=excluded.best_lap_s,
                quality_classification=excluded.quality_classification,
                review_status=excluded.review_status,
                sync_status=excluded.sync_status,
                bundle_hash=excluded.bundle_hash,
                schema_version=excluded.schema_version,
                sample_count=excluded.sample_count,
                ended_at_utc=excluded.ended_at_utc,
                bundle_mtime=excluded.bundle_mtime,
                indexed_at_utc=excluded.indexed_at_utc
            """,
            (
                str(entry.get("session_id") or Path(path).name),
                path,
                created_at,
                str(entry.get("sim") or "-"),
                str(entry.get("track") or "-"),
                str(entry.get("car") or "-"),
                str(entry.get("session_type") or "-"),
                self._as_float(entry.get("duration_s")),
                self._as_int(entry.get("total_laps")),
                self._as_int(entry.get("clean_laps")),
                self._parse_best_lap(entry.get("best_lap")),
                str(entry.get("quality") or "-"),
                str(entry.get("review_status") or "ready"),
                str(entry.get("sync_status") or "not_queued"),
                str(entry.get("bundle_hash") or ""),
                schema_version,
                self._as_int(entry.get("sample_count")),
                str(entry.get("ended_at_utc") or ""),
                float(bundle_mtime),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()

    def _indexed_paths(self) -> set[str]:
        cur = self._conn.execute("SELECT path FROM sessions")
        return {str(r[0]) for r in cur.fetchall() if r and r[0]}

    def _delete_missing_entries(self, *, actual_paths: set[str]) -> None:
        cur = self._conn.execute("SELECT path FROM sessions")
        existing_paths = [str(r[0]) for r in cur.fetchall()]
        to_delete = [p for p in existing_paths if p not in actual_paths]
        if not to_delete:
            return
        self._conn.executemany("DELETE FROM sessions WHERE path = ?", [(p,) for p in to_delete])
        self._conn.commit()

    def _get_indexed_mtime(self, path: str) -> float | None:
        cur = self._conn.execute("SELECT bundle_mtime FROM sessions WHERE path = ?", (path,))
        row = cur.fetchone()
        if not row or row[0] is None:
            return None
        return float(row[0])

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT NOT NULL,
                path TEXT PRIMARY KEY,
                created_at TEXT,
                simulator TEXT,
                track TEXT,
                car TEXT,
                session_type TEXT,
                duration_s REAL,
                lap_count INTEGER,
                clean_lap_count INTEGER,
                best_lap_s REAL,
                quality_classification TEXT,
                review_status TEXT,
                sync_status TEXT,
                bundle_hash TEXT,
                schema_version TEXT,
                sample_count INTEGER,
                ended_at_utc TEXT,
                bundle_mtime REAL,
                indexed_at_utc TEXT
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_sim ON sessions(simulator)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_track ON sessions(track)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_car ON sessions(car)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_quality ON sessions(quality_classification)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_sync_status ON sessions(sync_status)")

        self._conn.execute("CREATE TABLE IF NOT EXISTS index_meta (key TEXT PRIMARY KEY, value TEXT)")
        self._conn.execute(
            "INSERT INTO index_meta(key, value) VALUES('schema_version', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(_SCHEMA_VERSION),),
        )
        self._conn.commit()

    def _open_or_repair(self) -> sqlite3.Connection:
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            quick = conn.execute("PRAGMA quick_check").fetchone()
            if not quick or str(quick[0]).lower() != "ok":
                raise sqlite3.DatabaseError("quick_check failed")
            return conn
        except Exception:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            log.warning("Session index appears corrupted, rebuilding: %s", self._db_path)
            try:
                if self._db_path.exists():
                    backup_name = self._db_path.with_suffix(".corrupt.sqlite3")
                    if backup_name.exists():
                        backup_name.unlink(missing_ok=True)
                    self._db_path.rename(backup_name)
            except Exception:
                self._db_path.unlink(missing_ok=True)

            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

    @staticmethod
    def _parse_best_lap(value: object) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            txt = value.strip().lower().replace("s", "")
            try:
                return float(txt)
            except Exception:
                return None
        return None

    @staticmethod
    def _as_int(value: object) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(float(str(value)))
        except Exception:
            return None

    @staticmethod
    def _as_float(value: object) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(str(value))
        except Exception:
            return None

    @staticmethod
    def _best_created_at(entry: dict[str, Any]) -> str:
        for key in ("created_at", "started_at_utc", "ended_at_utc"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return ""

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> dict[str, Any]:
        best_lap_s = row["best_lap_s"]
        ended_at = row["ended_at_utc"] or ""
        ended_display = ""
        ended_date = ""
        if ended_at:
            try:
                ended_dt = datetime.fromisoformat(str(ended_at).replace("Z", "+00:00"))
                ended_display = ended_dt.strftime("%Y-%m-%d %H:%M")
                ended_date = ended_dt.strftime("%Y-%m-%d")
            except Exception:
                ended_display = str(ended_at)
                ended_date = str(ended_at)[:10]

        return {
            "session_id": row["session_id"],
            "folder": row["path"],
            "path": row["path"],
            "name": Path(str(row["path"])).name,
            "created_at": row["created_at"],
            "sim": row["simulator"] or "-",
            "track": row["track"] or "-",
            "car": row["car"] or "-",
            "session_type": row["session_type"] or "-",
            "duration_s": row["duration_s"] or 0,
            "duration_display": _format_duration_archive(row["duration_s"] or 0),
            "total_laps": row["lap_count"] or 0,
            "clean_laps": row["clean_lap_count"] or 0,
            "best_lap": f"{best_lap_s:.3f}s" if isinstance(best_lap_s, (int, float)) else "-",
            "quality": row["quality_classification"] or "-",
            "review_status": row["review_status"] or "ready",
            "sync_status": row["sync_status"] or "not_queued",
            "bundle_hash": row["bundle_hash"] or "",
            "schema_version": row["schema_version"] or "",
            "sample_count": row["sample_count"] or 0,
            "ended": ended_display,
            "ended_display": ended_display,
            "ended_date": ended_date,
            "ended_at_utc": ended_at,
            "analysis_ready": (row["quality_classification"] or "-") != "-",
            "sync_ready": str(row["sync_status"] or "") in {"sync_ready", "queued", "synced"},
        }


def _format_duration_archive(duration_s: float) -> str:
    if not isinstance(duration_s, (int, float)) or duration_s <= 0:
        return "—"
    total_seconds = int(duration_s)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    return f"{minutes}m {seconds}s"
