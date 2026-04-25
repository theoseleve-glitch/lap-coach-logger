"""T186: ``lap_coach_logger.updates.downloader`` plumbs three
independent pieces of auto-update infrastructure:

1. ``download_update(url, target_path, *, http_get_bytes)`` —
   streams bytes from a URL to a ``.partial`` file, then
   atomically renames to the final ``target_path`` on success.
   Cleans up the ``.partial`` on failure so retries have a
   clean slate.

2. ``verify_signature(file_bytes, signature_hex, public_key_raw)``
   — verifies an Ed25519 signature on the file bytes. Never
   raises; returns ``False`` for any failure (tamper, wrong
   key, malformed signature, malformed key).

3. ``mark_update_pending(staged_path, version, *, marker_path)``
   + ``read_pending_update(marker_path)`` +
   ``clear_pending_update(marker_path)`` — the "apply on next
   launch" plumbing. The marker is JSON pointing at the staged
   binary; ``read_pending_update`` returns ``None`` if the
   marker is missing, malformed, or the referenced staged file
   is gone.

T187 (UI surfacing the pending update) and T188 (rollback if
new version crashes) plug into this plumbing without
re-writing it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pytest


# -- module exports ----------------------------------------------------


def test_module_exports_public_api() -> None:
    """All four primitives must be exposed for callers."""
    from lap_coach_logger.updates import downloader

    assert hasattr(downloader, "download_update")
    assert hasattr(downloader, "verify_signature")
    assert hasattr(downloader, "mark_update_pending")
    assert hasattr(downloader, "read_pending_update")
    assert hasattr(downloader, "clear_pending_update")
    assert hasattr(downloader, "PendingUpdate")


# -- download_update ---------------------------------------------------


def _bytes_iter(payload: bytes, chunk: int = 64) -> Iterable[bytes]:
    """Helper: yield payload as fixed-size chunks."""
    for i in range(0, len(payload), chunk):
        yield payload[i : i + chunk]


def test_download_update_writes_bytes_to_target(
    tmp_path: Path,
) -> None:
    """The full payload streamed from ``http_get_bytes`` must
    end up at ``target_path``."""
    from lap_coach_logger.updates.downloader import download_update

    payload = b"hello update world" * 10

    def fake_get(url: str, timeout_s: float):
        return _bytes_iter(payload)

    target = tmp_path / "LapCoachLogger-2.1.0.exe"
    result = download_update(
        "https://example.invalid/x.exe",
        target,
        http_get_bytes=fake_get,
    )

    assert result == target
    assert target.is_file()
    assert target.read_bytes() == payload


def test_download_update_uses_partial_rename(
    tmp_path: Path,
) -> None:
    """The download must write to ``<target>.partial`` first
    and then rename — so an interrupted download leaves no
    half-baked file at the canonical target path."""
    from lap_coach_logger.updates.downloader import download_update

    target = tmp_path / "LapCoachLogger-2.1.0.exe"
    partial = target.with_suffix(target.suffix + ".partial")

    seen_partial = []

    def fake_get(url: str, timeout_s: float):
        # While we're being called, the .partial file should
        # already exist (writer opens it before reading
        # chunks).
        for chunk in _bytes_iter(b"abcdef" * 100):
            seen_partial.append(partial.exists())
            yield chunk

    download_update(
        "https://example.invalid/x.exe",
        target,
        http_get_bytes=fake_get,
    )

    assert any(seen_partial), (
        ".partial file must exist mid-download (writer opens "
        "it before consuming the byte stream)"
    )
    # After completion, .partial must be gone (renamed).
    assert not partial.exists()
    assert target.exists()


def test_download_update_cleans_up_partial_on_failure(
    tmp_path: Path,
) -> None:
    """If the byte stream raises mid-download, the ``.partial``
    file must be removed — otherwise repeated retries leave
    orphan files."""
    from lap_coach_logger.updates.downloader import download_update

    target = tmp_path / "LapCoachLogger-2.1.0.exe"
    partial = target.with_suffix(target.suffix + ".partial")

    def boom(url: str, timeout_s: float):
        yield b"first chunk"
        raise ConnectionError("network died mid-download")

    with pytest.raises(ConnectionError):
        download_update(
            "https://example.invalid/x.exe",
            target,
            http_get_bytes=boom,
        )

    assert not partial.exists(), (
        ".partial must be cleaned up on failure"
    )
    assert not target.exists(), (
        "target must not exist when download failed"
    )


def test_download_update_overwrites_existing_partial(
    tmp_path: Path,
) -> None:
    """A leftover ``.partial`` from a previous failed download
    must not block a retry — it's overwritten."""
    from lap_coach_logger.updates.downloader import download_update

    target = tmp_path / "LapCoachLogger-2.1.0.exe"
    partial = target.with_suffix(target.suffix + ".partial")
    partial.write_bytes(b"stale leftover bytes")

    payload = b"fresh download bytes"

    def fake_get(url: str, timeout_s: float):
        return _bytes_iter(payload)

    download_update(
        "https://example.invalid/x.exe",
        target,
        http_get_bytes=fake_get,
    )

    assert target.read_bytes() == payload, (
        "fresh download must overwrite the stale .partial"
    )


# -- verify_signature --------------------------------------------------


@pytest.fixture(scope="module")
def ed25519_keypair():
    """Generate a one-shot Ed25519 keypair for testing.
    Returns (private_key_obj, public_key_raw_bytes)."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
    from cryptography.hazmat.primitives import serialization

    priv = Ed25519PrivateKey.generate()
    pub_raw = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return priv, pub_raw


def test_verify_signature_accepts_valid_signature(
    ed25519_keypair,
) -> None:
    """A signature produced by the matching private key must
    verify True."""
    from lap_coach_logger.updates.downloader import verify_signature

    priv, pub_raw = ed25519_keypair
    payload = b"the file we're vouching for" * 50
    sig_hex = priv.sign(payload).hex()

    assert verify_signature(payload, sig_hex, pub_raw) is True


def test_verify_signature_rejects_tampered_payload(
    ed25519_keypair,
) -> None:
    """If even one byte of the payload is flipped, the signature
    must reject — that's the whole point of a signature."""
    from lap_coach_logger.updates.downloader import verify_signature

    priv, pub_raw = ed25519_keypair
    payload = b"the original file"
    sig_hex = priv.sign(payload).hex()

    tampered = payload[:-1] + bytes([payload[-1] ^ 0x01])
    assert verify_signature(tampered, sig_hex, pub_raw) is False


def test_verify_signature_rejects_wrong_key(ed25519_keypair) -> None:
    """A signature signed with a different private key must
    fail verification — even if the signature itself is
    well-formed."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
    from cryptography.hazmat.primitives import serialization
    from lap_coach_logger.updates.downloader import verify_signature

    _legit_priv, legit_pub_raw = ed25519_keypair

    attacker_priv = Ed25519PrivateKey.generate()
    payload = b"file claiming to be from publisher"
    forged_sig_hex = attacker_priv.sign(payload).hex()

    assert verify_signature(
        payload, forged_sig_hex, legit_pub_raw,
    ) is False


def test_verify_signature_rejects_malformed_inputs(
    ed25519_keypair,
) -> None:
    """Bad hex, wrong-length signature, garbage key — must
    return False rather than raise."""
    from lap_coach_logger.updates.downloader import verify_signature

    _priv, pub_raw = ed25519_keypair

    # Garbage hex.
    assert verify_signature(b"x", "not-hex-at-all", pub_raw) is False
    # Wrong-length signature (Ed25519 sigs are 64 bytes = 128 hex).
    assert verify_signature(b"x", "ab" * 10, pub_raw) is False
    # Garbage public key.
    assert verify_signature(b"x", "ab" * 64, b"too short") is False


# -- pending update marker --------------------------------------------


def test_pending_update_round_trip(tmp_path: Path) -> None:
    """``mark_update_pending`` writes; ``read_pending_update``
    reads back the same staged path + version."""
    from lap_coach_logger.updates.downloader import (
        mark_update_pending, read_pending_update,
    )

    staged = tmp_path / "staged" / "LapCoachLogger-2.1.0.exe"
    staged.parent.mkdir(parents=True)
    staged.write_bytes(b"staged exe bytes")

    marker = tmp_path / "pending_update.json"
    mark_update_pending(staged, "2.1.0", marker_path=marker)

    pending = read_pending_update(marker)
    assert pending is not None
    assert pending.staged_path == staged
    assert pending.version == "2.1.0"


def test_read_pending_update_returns_none_when_marker_absent(
    tmp_path: Path,
) -> None:
    """No marker = no pending update. The fast-path on every
    cold launch."""
    from lap_coach_logger.updates.downloader import read_pending_update

    marker = tmp_path / "pending_update.json"
    assert read_pending_update(marker) is None


def test_read_pending_update_returns_none_when_staged_file_missing(
    tmp_path: Path,
) -> None:
    """If the marker points at a staged binary that no longer
    exists (user manually deleted, AV quarantined, etc.), the
    pending entry is treated as gone."""
    from lap_coach_logger.updates.downloader import (
        mark_update_pending, read_pending_update,
    )

    staged = tmp_path / "ghost.exe"
    staged.write_bytes(b"will be deleted")
    marker = tmp_path / "pending_update.json"
    mark_update_pending(staged, "2.1.0", marker_path=marker)
    staged.unlink()

    assert read_pending_update(marker) is None


def test_read_pending_update_returns_none_when_marker_malformed(
    tmp_path: Path,
) -> None:
    """A corrupt marker file (bad JSON, missing fields) must
    return ``None`` — never raise. The launch path can't crash
    on a malformed file the user doesn't know about."""
    from lap_coach_logger.updates.downloader import read_pending_update

    marker = tmp_path / "pending_update.json"
    marker.write_text("not valid json at all }}}")

    assert read_pending_update(marker) is None

    marker.write_text(json.dumps({"version": "2.1.0"}))  # missing staged_path
    assert read_pending_update(marker) is None


def test_clear_pending_update_removes_marker(tmp_path: Path) -> None:
    """After applying an update (or aborting), the marker
    must be removable — otherwise every subsequent launch tries
    to re-apply."""
    from lap_coach_logger.updates.downloader import (
        clear_pending_update, mark_update_pending,
        read_pending_update,
    )

    staged = tmp_path / "staged.exe"
    staged.write_bytes(b"x")
    marker = tmp_path / "pending_update.json"
    mark_update_pending(staged, "2.1.0", marker_path=marker)
    assert read_pending_update(marker) is not None

    clear_pending_update(marker)
    assert not marker.exists()
    assert read_pending_update(marker) is None


def test_clear_pending_update_is_idempotent(tmp_path: Path) -> None:
    """Calling clear twice (or against a never-written marker)
    must not raise — idempotent cleanup is safer for shutdown
    paths."""
    from lap_coach_logger.updates.downloader import clear_pending_update

    marker = tmp_path / "never_written.json"
    clear_pending_update(marker)  # must not raise
    clear_pending_update(marker)  # must not raise
