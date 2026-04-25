"""T186: download update binaries to a temp location, verify
their Ed25519 signature, and stage a "pending update" marker
that the next app launch picks up.

Three independent primitives that compose into the end-to-end
flow but can also be exercised in isolation by tests:

- ``download_update`` — atomic ``.partial`` + rename pattern.
  The target path never holds a half-baked file.
- ``verify_signature`` — Ed25519 public-key verify on the
  downloaded bytes. Never raises.
- ``mark_update_pending`` / ``read_pending_update`` /
  ``clear_pending_update`` — JSON marker plumbing for the
  "apply on next launch" sequence.

The actual swap-and-relaunch (T187) and crash-rollback (T188)
plug into ``read_pending_update`` without re-implementing this
plumbing.
"""
from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path
from typing import Callable, Iterable

log = logging.getLogger(__name__)


HttpGetBytes = Callable[[str, float], Iterable[bytes]]

DEFAULT_TIMEOUT_S = 30.0


# -- atomic download ---------------------------------------------------


def _default_http_get_bytes(url: str, timeout_s: float) -> Iterable[bytes]:
    """Stdlib-only streaming GET — yields chunks. Used when no
    fetcher is injected; tests always inject one."""
    import urllib.request

    with urllib.request.urlopen(url, timeout=timeout_s) as resp:
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                return
            yield chunk


def download_update(
    url: str,
    target_path: Path,
    *,
    http_get_bytes: HttpGetBytes | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> Path:
    """Stream a download to ``target_path`` via a ``.partial``
    file, then atomic rename. Cleans up ``.partial`` on
    failure so retries have a clean slate.

    Returns ``target_path`` on success. Re-raises whatever the
    fetcher raises on failure (caller decides retry policy).
    """
    fetcher: HttpGetBytes = (
        http_get_bytes if http_get_bytes is not None
        else _default_http_get_bytes
    )

    target_path.parent.mkdir(parents=True, exist_ok=True)
    partial = target_path.with_suffix(target_path.suffix + ".partial")

    try:
        with partial.open("wb") as fh:
            for chunk in fetcher(url, timeout_s):
                fh.write(chunk)
    except BaseException:
        # Any failure (network, disk, KeyboardInterrupt) — drop
        # the half-written file so retries don't see stale
        # bytes.
        try:
            partial.unlink()
        except FileNotFoundError:
            pass
        raise

    # Windows: replace() is atomic and overwrites if target exists.
    partial.replace(target_path)
    return target_path


# -- signature verification --------------------------------------------


def verify_signature(
    file_bytes: bytes,
    signature_hex: str,
    public_key_raw: bytes,
) -> bool:
    """Verify an Ed25519 signature on ``file_bytes``.

    Args:
        file_bytes: The signed payload (e.g., installer bytes).
        signature_hex: Hex-encoded 64-byte Ed25519 signature.
        public_key_raw: 32-byte raw Ed25519 public key (the
            publisher's key, bundled with the app).

    Returns:
        ``True`` iff the signature is valid for these bytes
        with this key. ``False`` for any failure mode (bad hex,
        wrong-length signature, malformed key, tampered bytes,
        wrong key). Never raises.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PublicKey,
        )
        pk = Ed25519PublicKey.from_public_bytes(public_key_raw)
        signature = bytes.fromhex(signature_hex)
        pk.verify(signature, file_bytes)
        return True
    except Exception:
        return False


# -- pending-update marker --------------------------------------------


@dataclasses.dataclass(frozen=True)
class PendingUpdate:
    """A staged update waiting to be applied on next launch.

    ``staged_path`` is the verified, downloaded binary;
    ``version`` is the version string the user will see in the
    "an update is ready to install" prompt.
    """

    staged_path: Path
    version: str


def mark_update_pending(
    staged_path: Path,
    version: str,
    *,
    marker_path: Path,
) -> None:
    """Write a JSON marker file pointing at the staged update.

    Atomic-ish: writes the JSON in one shot. The marker dir is
    created if missing.
    """
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "staged_path": str(staged_path),
        "version": version,
    }
    marker_path.write_text(
        json.dumps(payload), encoding="utf-8",
    )


def read_pending_update(marker_path: Path) -> PendingUpdate | None:
    """Read the marker. Returns ``None`` for any failure mode:
    marker absent, JSON malformed, fields missing or wrong
    type, referenced staged file no longer exists.

    Never raises — the launch path can't crash on a malformed
    file the user can't see.
    """
    if not marker_path.is_file():
        return None
    try:
        data = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    raw_staged = data.get("staged_path")
    raw_version = data.get("version")
    if not isinstance(raw_staged, str) or not isinstance(raw_version, str):
        return None
    staged = Path(raw_staged)
    if not staged.is_file():
        return None
    return PendingUpdate(staged_path=staged, version=raw_version)


def clear_pending_update(marker_path: Path) -> None:
    """Remove the marker file. Idempotent — no-op if absent."""
    try:
        marker_path.unlink()
    except FileNotFoundError:
        pass
