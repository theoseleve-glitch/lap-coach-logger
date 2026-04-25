"""T105: Bundle upload includes ``coaching_insights.json`` so the
server can audit which rules fired client-side.

T099 wrote the file into the bundle dir tagged ``source: "client"``
per ADR-009. T105 pins that the ingest client's multipart upload
includes that file alongside everything else — without an
explicit pin, a future "filter only known file extensions"
optimisation could silently drop it.

Why this matters: server-side audit (T105 backend twin) compares
the client-fired rules against the server's reprocessed view to
catch rules that fire client-side but not server-side (or vice
versa). Without the file in the upload, that audit becomes
impossible — a silent capability loss.

The test exercises ``_build_multipart_body`` directly because:
- We control the bundle dir contents (don't need a real
  finalize cycle here).
- We can inspect the multipart body bytes to see which files
  are included without reading the wire response.
"""
from __future__ import annotations

import json
from pathlib import Path

from lap_coach_logger.infra.ingest import _build_multipart_body


def _seed_bundle(tmp_path: Path) -> Path:
    """Plant a minimal bundle with a manifest, telemetry, and the
    T099-shaped coaching_insights.json."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "manifest.json").write_text(
        json.dumps({"session_id": "01900000-0000-7000-8000-00000000a105"}),
        encoding="utf-8",
    )
    (bundle / "telemetry.parquet").write_bytes(b"\x00" * 32)
    (bundle / "coaching_insights.json").write_text(
        json.dumps(
            [
                {
                    "rule_id": "br.late_braking",
                    "payload": {"title": "Brake later"},
                    "source": "client",
                }
            ]
        ),
        encoding="utf-8",
    )
    return bundle


# ---------------------------------------------------------------------------
# Upload includes coaching_insights.json
# ---------------------------------------------------------------------------


def test_multipart_body_includes_coaching_insights_file(tmp_path: Path) -> None:
    """The file must appear in the upload's multipart body — not
    filtered out, not silently dropped. Match by filename in a
    Content-Disposition header to ignore wire-formatting noise."""
    bundle = _seed_bundle(tmp_path)
    manifest_bytes = (bundle / "manifest.json").read_bytes()

    body = _build_multipart_body(
        bundle,
        manifest_bytes=manifest_bytes,
        boundary="test-boundary",
        chunk_size_bytes=8 * 1024 * 1024,
    )

    # The Content-Disposition for each chunk includes filename="…".
    # Searching for ``filename="coaching_insights.json"`` is
    # robust against ordering changes elsewhere in the body.
    assert b'filename="coaching_insights.json"' in body


def test_multipart_body_includes_coaching_insights_payload_bytes(
    tmp_path: Path,
) -> None:
    """It's not enough that the filename is present — the file
    contents must round-trip too. A Windows fluke where iterdir
    listed the file but read_bytes silently failed would still
    leave the filename header."""
    bundle = _seed_bundle(tmp_path)
    manifest_bytes = (bundle / "manifest.json").read_bytes()

    body = _build_multipart_body(
        bundle,
        manifest_bytes=manifest_bytes,
        boundary="test-boundary",
        chunk_size_bytes=8 * 1024 * 1024,
    )

    # The rule_id is unique to coaching_insights — finding it in
    # the body proves the file's bytes made it through.
    assert b"br.late_braking" in body


def test_coaching_insights_carries_client_source_tag_in_upload(
    tmp_path: Path,
) -> None:
    """The ``source: "client"`` tag is the audit signal — server
    distinguishes client-fired insights from its own. Pin that
    the tag survives the upload (i.e., the file isn't transformed
    or stripped during multipart packaging)."""
    bundle = _seed_bundle(tmp_path)
    manifest_bytes = (bundle / "manifest.json").read_bytes()

    body = _build_multipart_body(
        bundle,
        manifest_bytes=manifest_bytes,
        boundary="test-boundary",
        chunk_size_bytes=8 * 1024 * 1024,
    )

    assert b'"source": "client"' in body


# ---------------------------------------------------------------------------
# Bundle without coaching_insights still uploads cleanly
# ---------------------------------------------------------------------------


def test_upload_works_when_coaching_insights_absent(tmp_path: Path) -> None:
    """Bundles from callers that don't use the rules engine
    (legacy paths, demo mode) shouldn't fail the upload — the
    file is optional, not required."""
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "manifest.json").write_text(
        json.dumps({"session_id": "no-coaching"}), encoding="utf-8"
    )
    (bundle / "telemetry.parquet").write_bytes(b"\x00" * 32)
    manifest_bytes = (bundle / "manifest.json").read_bytes()

    # Must not raise
    body = _build_multipart_body(
        bundle,
        manifest_bytes=manifest_bytes,
        boundary="test-boundary",
        chunk_size_bytes=8 * 1024 * 1024,
    )

    # And the file isn't accidentally fabricated
    assert b'filename="coaching_insights.json"' not in body
