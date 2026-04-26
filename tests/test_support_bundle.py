"""T233: Diagnostic bundle export — pure helpers.

Extracts the privacy-sensitive parts of the support-bundle
export into pure, side-effect-free helpers so we can pin them
in CI without spinning up the full desktop service.

Two helpers:

  - ``redact_config(AppConfig)`` returns a dict suitable for
    bundling: every secret-bearing field (sync.device_token,
    future API keys) is replaced with the literal string
    ``"<redacted>"``. Other fields pass through unchanged.
    The function never mutates its input.
  - ``enumerate_sessions(sessions_root)`` walks the configured
    output directory and returns a list of one-entry-per-
    session metadata records — folder name, started_at,
    sample_count, sim, track. Missing or malformed sessions
    are skipped (not raised) so a single corrupt directory
    can't block the whole support export.

Wiring these into the existing service.export_support_bundle()
is a follow-up — T233 establishes the testable primitives.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lap_coach_logger.config.models import AppConfig
from lap_coach_logger.diagnostics import support_bundle as sb


# ---------------------------------------------------------------------------
# redact_config: strips secrets, preserves everything else
# ---------------------------------------------------------------------------


def test_redact_config_replaces_sync_device_token() -> None:
    """device_token is the most-sensitive field in the config —
    it grants upload access for the user's account. MUST be
    replaced with the literal redaction marker, not blanked
    (an empty string would lose the "yes, you HAD a token"
    signal that's useful for debugging sync issues)."""
    cfg = AppConfig()
    cfg.sync.device_token = "secret-token-abc-123"
    redacted = sb.redact_config(cfg)
    assert redacted["sync"]["device_token"] == "<redacted>"


def test_redact_config_does_not_mutate_input() -> None:
    """Pure function contract: the AppConfig instance the user
    passes in must come back unchanged. Otherwise calling
    redact_config() before saving would zero the user's token
    on disk."""
    cfg = AppConfig()
    cfg.sync.device_token = "preserve-me"
    sb.redact_config(cfg)
    assert cfg.sync.device_token == "preserve-me"


def test_redact_config_preserves_non_secret_fields() -> None:
    """Non-secret fields pass through unchanged so support
    can see the user's actual configuration."""
    cfg = AppConfig()
    cfg.driver_name = "Theo"
    cfg.sample_interval_s = 0.05
    cfg.sync.api_url = "https://api.lap-coach.racing"
    redacted = sb.redact_config(cfg)
    assert redacted["driver_name"] == "Theo"
    assert redacted["sample_interval_s"] == 0.05
    assert redacted["sync"]["api_url"] == "https://api.lap-coach.racing"


def test_redact_config_omits_token_marker_when_token_was_empty() -> None:
    """If the user never set a device_token, don't fake a
    redaction marker — it would mislead support into thinking
    a token was present when it wasn't."""
    cfg = AppConfig()
    # Default: empty string
    assert cfg.sync.device_token == ""
    redacted = sb.redact_config(cfg)
    assert redacted["sync"]["device_token"] == ""


# ---------------------------------------------------------------------------
# enumerate_sessions: lists session folders with metadata
# ---------------------------------------------------------------------------


def _make_session(
    sessions_root: Path,
    folder_name: str,
    *,
    metadata: dict | None = None,
    write_metadata: bool = True,
) -> Path:
    folder = sessions_root / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    if write_metadata:
        payload = metadata or {
            "started_at_utc": "2026-04-25T14:30:00+00:00",
            "sample_count": 5400,
            "sim": "iracing",
            "track": "Spa-Francorchamps",
            "session_uid": folder_name,
        }
        (folder / "metadata.json").write_text(json.dumps(payload), encoding="utf-8")
    return folder


def test_enumerate_sessions_returns_one_entry_per_folder(tmp_path: Path) -> None:
    _make_session(tmp_path, "2026-04-25_session-a")
    _make_session(tmp_path, "2026-04-26_session-b")
    sessions = sb.enumerate_sessions(tmp_path)
    assert len(sessions) == 2


def test_enumerate_sessions_includes_folder_name(tmp_path: Path) -> None:
    """Folder name is the support team's primary handle — it's
    what appears in the file path the user shows in screenshots."""
    _make_session(tmp_path, "2026-04-25_session-a")
    sessions = sb.enumerate_sessions(tmp_path)
    assert sessions[0]["folder"] == "2026-04-25_session-a"


def test_enumerate_sessions_includes_metadata_fields(tmp_path: Path) -> None:
    """Each entry must surface enough metadata to triage without
    needing the actual telemetry: when, how many samples, sim,
    track."""
    _make_session(
        tmp_path,
        "session-spa",
        metadata={
            "started_at_utc": "2026-04-25T14:30:00+00:00",
            "sample_count": 12345,
            "sim": "iracing",
            "track": "Spa",
            "session_uid": "uid-spa",
        },
    )
    sessions = sb.enumerate_sessions(tmp_path)
    entry = sessions[0]
    assert entry["started_at_utc"] == "2026-04-25T14:30:00+00:00"
    assert entry["sample_count"] == 12345
    assert entry["sim"] == "iracing"
    assert entry["track"] == "Spa"


def test_enumerate_sessions_skips_folders_without_metadata(tmp_path: Path) -> None:
    """A folder without metadata.json is half-finished or stale
    — skip rather than crash the whole bundle export."""
    _make_session(tmp_path, "good-session")
    _make_session(tmp_path, "bad-session", write_metadata=False)
    sessions = sb.enumerate_sessions(tmp_path)
    assert len(sessions) == 1
    assert sessions[0]["folder"] == "good-session"


def test_enumerate_sessions_skips_malformed_metadata(tmp_path: Path) -> None:
    """A corrupted metadata.json must not block the whole
    export — log the skip and move on."""
    _make_session(tmp_path, "good-session")
    bad = tmp_path / "bad-session"
    bad.mkdir()
    (bad / "metadata.json").write_text("{not valid json", encoding="utf-8")
    sessions = sb.enumerate_sessions(tmp_path)
    folders = {e["folder"] for e in sessions}
    assert folders == {"good-session"}


def test_enumerate_sessions_returns_empty_list_for_missing_dir(tmp_path: Path) -> None:
    """No output_dir yet (first run, fresh install) — return
    empty list, never raise."""
    missing = tmp_path / "no-such-dir"
    sessions = sb.enumerate_sessions(missing)
    assert sessions == []


def test_enumerate_sessions_ignores_non_directory_entries(tmp_path: Path) -> None:
    """A stray file in the sessions root (e.g. .DS_Store)
    must not be confused for a session."""
    _make_session(tmp_path, "real-session")
    (tmp_path / ".DS_Store").write_text("noise", encoding="utf-8")
    sessions = sb.enumerate_sessions(tmp_path)
    assert len(sessions) == 1
    assert sessions[0]["folder"] == "real-session"


def test_enumerate_sessions_results_sorted_by_folder_name(tmp_path: Path) -> None:
    """Stable order so support can grep the bundle and find
    sessions in the same place every time. Folder names start
    with a date prefix so alphabetical sort = chronological."""
    _make_session(tmp_path, "2026-04-25_a")
    _make_session(tmp_path, "2026-04-23_b")
    _make_session(tmp_path, "2026-04-24_c")
    sessions = sb.enumerate_sessions(tmp_path)
    folders = [s["folder"] for s in sessions]
    assert folders == ["2026-04-23_b", "2026-04-24_c", "2026-04-25_a"]
