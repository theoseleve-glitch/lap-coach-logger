"""Local sync queue manager (offline-first, retry-ready)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lap_coach_logger.core.sync_service import DisabledSyncService, SyncService
from lap_coach_logger.core.sync_status import (
    SYNC_STATUS_BLOCKED,
    SYNC_STATUS_FAILED,
    SYNC_STATUS_NOT_QUEUED,
    SYNC_STATUS_QUEUED,
    SYNC_STATUS_READY,
    SYNC_STATUS_SYNCED,
    derive_sync_status,
)


@dataclass(frozen=True)
class QueueEntry:
    dedupe_key: str
    session_id: str
    bundle_hash: str
    bundle_path: str
    queued_at_utc: str


class SyncQueueManager:
    """Maintains durable queue state and per-session sync metadata."""

    def __init__(
        self,
        *,
        output_root: Path,
        queue_file_name: str = ".sync_queue.json",
        sync_enabled: bool = False,
        sync_service: SyncService | None = None,
    ) -> None:
        self._output_root = output_root
        self._queue_path = output_root / queue_file_name
        self._sync_enabled = sync_enabled
        self._sync_service = sync_service or DisabledSyncService()
        self._entries = self._load_queue()

    @property
    def sync_enabled(self) -> bool:
        return bool(self._sync_enabled and self._sync_service.enabled)

    def queue_depth(self) -> int:
        return len(self._entries)

    @staticmethod
    def dedupe_key(*, session_id: str, bundle_hash: str) -> str:
        return f"{session_id}:{bundle_hash}"

    @staticmethod
    def compute_bundle_hash(*, session_id: str, telemetry_sha256: str | None) -> str:
        source = f"{session_id}:{telemetry_sha256 or ''}".encode("utf-8")
        return hashlib.sha256(source).hexdigest()

    def ensure_sync_metadata(self, bundle_dir: Path) -> dict[str, Any]:
        manifest_path = bundle_dir / "session.json"
        metadata_path = bundle_dir / "metadata.json"
        manifest = self._read_json(manifest_path)
        metadata = self._read_json(metadata_path)

        session_id = str(manifest.get("session_id") or metadata.get("session_uid") or bundle_dir.name)
        telemetry_sha256 = manifest.get("telemetry_sha256") or metadata.get("telemetry_sha256")
        bundle_hash = (
            manifest.get("bundle_hash")
            or metadata.get("bundle_hash")
            or self.compute_bundle_hash(session_id=session_id, telemetry_sha256=telemetry_sha256)
        )

        remote_id = manifest.get("remote_id") or metadata.get("remote_id")
        current_status = manifest.get("sync_status") or metadata.get("sync_status") or SYNC_STATUS_NOT_QUEUED
        derived_status = derive_sync_status(
            current_status=current_status,
            review_status=manifest.get("review_status") or metadata.get("review_status"),
            quality_classification=(
                manifest.get("quality_classification")
                or metadata.get("quality_classification")
            ),
            remote_id=remote_id,
        )

        sync_payload = {
            "sync_status": derived_status,
            "sync_attempt_count": int(manifest.get("sync_attempt_count") or metadata.get("sync_attempt_count") or 0),
            "last_sync_attempt_at": manifest.get("last_sync_attempt_at") or metadata.get("last_sync_attempt_at"),
            "last_sync_error": manifest.get("last_sync_error") or metadata.get("last_sync_error"),
            "bundle_hash": bundle_hash,
            "remote_id": remote_id,
        }

        changed_manifest = any(manifest.get(key) != value for key, value in sync_payload.items())
        changed_metadata = any(metadata.get(key) != value for key, value in sync_payload.items())

        if changed_manifest:
            manifest.update(sync_payload)
            self._write_json(manifest_path, manifest)
        if changed_metadata:
            metadata.update(sync_payload)
            self._write_json(metadata_path, metadata)

        return manifest

    def queue_session(self, bundle_dir: Path) -> tuple[bool, str]:
        manifest = self.ensure_sync_metadata(bundle_dir)
        session_id = str(manifest.get("session_id") or bundle_dir.name)
        bundle_hash = str(manifest.get("bundle_hash") or "")
        dedupe_key = self.dedupe_key(session_id=session_id, bundle_hash=bundle_hash)
        status = str(manifest.get("sync_status") or SYNC_STATUS_NOT_QUEUED)

        if status == SYNC_STATUS_SYNCED:
            return True, "Session already synced"
        if status == SYNC_STATUS_BLOCKED:
            return False, "Session is currently blocked from sync"

        for entry in self._entries:
            if entry.dedupe_key == dedupe_key:
                return True, "Session already queued"

        queued_at = datetime.now(timezone.utc).isoformat()
        self._entries.append(
            QueueEntry(
                dedupe_key=dedupe_key,
                session_id=session_id,
                bundle_hash=bundle_hash,
                bundle_path=str(bundle_dir),
                queued_at_utc=queued_at,
            )
        )
        self._save_queue()

        self._update_bundle_sync_fields(
            bundle_dir,
            sync_status=SYNC_STATUS_QUEUED,
            sync_attempt_count=int(manifest.get("sync_attempt_count") or 0),
            last_sync_error=None,
        )

        return True, "Queued"

    def remove_bundle(self, bundle_dir: Path) -> None:
        target = str(bundle_dir)
        self._entries = [entry for entry in self._entries if entry.bundle_path != target]
        self._save_queue()

    def process_queue(self, *, max_items: int = 5) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if not self.sync_enabled:
            return results

        remaining: list[QueueEntry] = []
        for entry in self._entries[:max_items]:
            bundle_dir = Path(entry.bundle_path)
            if not bundle_dir.exists():
                results.append({"dedupe_key": entry.dedupe_key, "status": "dropped_missing_bundle"})
                continue

            attempt_at = datetime.now(timezone.utc).isoformat()
            manifest = self.ensure_sync_metadata(bundle_dir)
            attempt_count = int(manifest.get("sync_attempt_count") or 0) + 1

            upload = self._sync_service.upload_bundle(
                bundle_dir=bundle_dir,
                session_id=entry.session_id,
                bundle_hash=entry.bundle_hash,
            )

            if upload.success:
                self._update_bundle_sync_fields(
                    bundle_dir,
                    sync_status=SYNC_STATUS_SYNCED,
                    sync_attempt_count=attempt_count,
                    last_sync_attempt_at=attempt_at,
                    last_sync_error=None,
                    remote_id=upload.remote_id,
                )
                results.append({"dedupe_key": entry.dedupe_key, "status": "synced"})
            else:
                self._update_bundle_sync_fields(
                    bundle_dir,
                    sync_status=SYNC_STATUS_FAILED,
                    sync_attempt_count=attempt_count,
                    last_sync_attempt_at=attempt_at,
                    last_sync_error=upload.error or "Unknown sync error",
                )
                results.append({"dedupe_key": entry.dedupe_key, "status": "failed"})
                if upload.retryable:
                    remaining.append(entry)

        remaining.extend(self._entries[max_items:])
        self._entries = remaining
        self._save_queue()
        return results

    def _update_bundle_sync_fields(
        self,
        bundle_dir: Path,
        *,
        sync_status: str,
        sync_attempt_count: int,
        last_sync_attempt_at: str | None = None,
        last_sync_error: str | None = None,
        remote_id: str | None = None,
    ) -> None:
        manifest_path = bundle_dir / "session.json"
        metadata_path = bundle_dir / "metadata.json"
        manifest = self._read_json(manifest_path)
        metadata = self._read_json(metadata_path)

        patch = {
            "sync_status": sync_status,
            "sync_attempt_count": int(sync_attempt_count),
            "last_sync_attempt_at": last_sync_attempt_at,
            "last_sync_error": last_sync_error,
            "remote_id": remote_id or manifest.get("remote_id") or metadata.get("remote_id"),
            "bundle_hash": manifest.get("bundle_hash") or metadata.get("bundle_hash"),
        }
        manifest.update(patch)
        metadata.update(patch)
        self._write_json(manifest_path, manifest)
        self._write_json(metadata_path, metadata)

    def _load_queue(self) -> list[QueueEntry]:
        payload = self._read_json(self._queue_path)
        entries = payload.get("entries")
        if not isinstance(entries, list):
            return []

        loaded: list[QueueEntry] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            try:
                loaded.append(
                    QueueEntry(
                        dedupe_key=str(item.get("dedupe_key") or ""),
                        session_id=str(item.get("session_id") or ""),
                        bundle_hash=str(item.get("bundle_hash") or ""),
                        bundle_path=str(item.get("bundle_path") or ""),
                        queued_at_utc=str(item.get("queued_at_utc") or ""),
                    )
                )
            except Exception:
                continue
        return loaded

    def _save_queue(self) -> None:
        self._output_root.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "entries": [
                {
                    "dedupe_key": entry.dedupe_key,
                    "session_id": entry.session_id,
                    "bundle_hash": entry.bundle_hash,
                    "bundle_path": entry.bundle_path,
                    "queued_at_utc": entry.queued_at_utc,
                }
                for entry in self._entries
            ],
        }
        self._write_json(self._queue_path, payload)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
