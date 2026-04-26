"""T189: discover and surface Windows minidump (.dmp) files
written when the app crashes, mark them with metadata, and
upload via an injectable HTTP POST.

The capture itself (writing the .dmp on segfault / unhandled
native exception) happens in OS-level code outside Python's
reach — Sentry's native SDK or a custom MiniDumpWriteDump
handler. T189 covers the *handling* of already-written dumps:

1. ``find_crash_dumps(dump_dir)`` enumerates ``*.dmp`` files.
2. ``mark_dump_for_review(dump_path, *, app_version,
   marker_dir)`` writes a sidecar JSON with timestamp + app
   version so the dump's provenance is preserved across
   sessions.
3. ``submit_crash_dump(dump_path, url, *, http_post)``
   uploads the bytes. Never raises — returns a result tuple
   with success/error so the upload thread can't crash on a
   network blip.

Same shape as the auto-update plumbing (T186) — frozen
dataclasses, never-raises I/O functions, injectable callables.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# -- module exports ---------------------------------------------------


def test_module_exports_public_api() -> None:
    """All five primitives must be exposed."""
    from lap_coach_logger import crash_dump

    assert hasattr(crash_dump, "CrashDumpEntry")
    assert hasattr(crash_dump, "find_crash_dumps")
    assert hasattr(crash_dump, "mark_dump_for_review")
    assert hasattr(crash_dump, "read_dump_metadata")
    assert hasattr(crash_dump, "submit_crash_dump")
    assert hasattr(crash_dump, "SubmitResult")


def test_entry_and_result_are_immutable() -> None:
    """Dataclasses must be frozen — callers can't mutate the
    bookkeeping mid-flight."""
    from dataclasses import is_dataclass, FrozenInstanceError
    from lap_coach_logger.crash_dump import CrashDumpEntry, SubmitResult

    assert is_dataclass(CrashDumpEntry)
    assert is_dataclass(SubmitResult)

    e = CrashDumpEntry(
        dump_path=Path("x.dmp"),
        app_version="2.0.0",
        captured_at_iso="2026-04-26T00:00:00Z",
    )
    with pytest.raises(FrozenInstanceError):
        e.app_version = "9.9.9"  # type: ignore[misc]

    r = SubmitResult(success=True, error=None, http_status=200)
    with pytest.raises(FrozenInstanceError):
        r.success = False  # type: ignore[misc]


# -- find_crash_dumps -------------------------------------------------


def test_find_crash_dumps_lists_dmp_files(tmp_path: Path) -> None:
    """Any ``*.dmp`` file in the dump directory is enumerated."""
    from lap_coach_logger.crash_dump import find_crash_dumps

    (tmp_path / "LapCoachLogger.exe.1234.dmp").write_bytes(b"MDMP")
    (tmp_path / "LapCoachLogger.exe.5678.dmp").write_bytes(b"MDMP")
    # Non-dmp files must be ignored.
    (tmp_path / "log.txt").write_text("not a dump")
    (tmp_path / "other.dat").write_bytes(b"random")

    result = find_crash_dumps(tmp_path)
    names = {p.name for p in result}
    assert names == {
        "LapCoachLogger.exe.1234.dmp",
        "LapCoachLogger.exe.5678.dmp",
    }


def test_find_crash_dumps_returns_empty_when_dir_absent(
    tmp_path: Path,
) -> None:
    """A missing dump dir is the steady state on every clean
    install — the function must not raise."""
    from lap_coach_logger.crash_dump import find_crash_dumps

    result = find_crash_dumps(tmp_path / "does-not-exist")
    assert result == []


def test_find_crash_dumps_returns_empty_when_no_dmps(
    tmp_path: Path,
) -> None:
    """Empty / non-dmp directory → empty list."""
    from lap_coach_logger.crash_dump import find_crash_dumps

    (tmp_path / "log.txt").write_text("not a dump")
    assert find_crash_dumps(tmp_path) == []


def test_find_crash_dumps_ignores_subdirectories(
    tmp_path: Path,
) -> None:
    """The function must NOT recurse — dump dirs are flat by
    convention; recursing would let a stray archive appear as
    a "fresh" crash."""
    from lap_coach_logger.crash_dump import find_crash_dumps

    sub = tmp_path / "archive"
    sub.mkdir()
    (sub / "LapCoachLogger.exe.9999.dmp").write_bytes(b"MDMP")
    (tmp_path / "LapCoachLogger.exe.1.dmp").write_bytes(b"MDMP")

    result = find_crash_dumps(tmp_path)
    names = {p.name for p in result}
    assert names == {"LapCoachLogger.exe.1.dmp"}


# -- mark_dump_for_review + read_dump_metadata ------------------------


def test_mark_and_read_metadata_round_trip(tmp_path: Path) -> None:
    """Metadata sidecar must round-trip ``app_version`` and
    timestamp so the upload step has provenance even if
    the .dmp is moved or renamed."""
    from lap_coach_logger.crash_dump import (
        mark_dump_for_review, read_dump_metadata,
    )

    dump = tmp_path / "LapCoachLogger.exe.42.dmp"
    dump.write_bytes(b"MDMP fake dump bytes")

    mark_dump_for_review(
        dump,
        app_version="2.1.0",
        captured_at_iso="2026-04-26T12:34:56Z",
    )

    entry = read_dump_metadata(dump)
    assert entry is not None
    assert entry.dump_path == dump
    assert entry.app_version == "2.1.0"
    assert entry.captured_at_iso == "2026-04-26T12:34:56Z"


def test_read_dump_metadata_returns_none_when_sidecar_absent(
    tmp_path: Path,
) -> None:
    """A dump without a sidecar (e.g., user dropped a file in
    manually, or sidecar was deleted) returns None — caller
    decides what to do (skip, prompt with default values)."""
    from lap_coach_logger.crash_dump import read_dump_metadata

    dump = tmp_path / "LapCoachLogger.exe.42.dmp"
    dump.write_bytes(b"MDMP")
    assert read_dump_metadata(dump) is None


def test_read_dump_metadata_returns_none_when_sidecar_malformed(
    tmp_path: Path,
) -> None:
    """Malformed sidecar JSON → None, never raise. The crash
    dump UI mustn't crash because of a corrupt metadata file."""
    from lap_coach_logger.crash_dump import read_dump_metadata

    dump = tmp_path / "LapCoachLogger.exe.42.dmp"
    dump.write_bytes(b"MDMP")
    sidecar = dump.with_suffix(dump.suffix + ".json")
    sidecar.write_text("not valid json {")

    assert read_dump_metadata(dump) is None


def test_mark_dump_for_review_writes_sidecar_alongside_dump(
    tmp_path: Path,
) -> None:
    """Sidecar lives at ``<dump>.json`` so tools that move the
    dump can carry the metadata together."""
    from lap_coach_logger.crash_dump import mark_dump_for_review

    dump = tmp_path / "LapCoachLogger.exe.42.dmp"
    dump.write_bytes(b"MDMP")

    mark_dump_for_review(
        dump,
        app_version="2.1.0",
        captured_at_iso="2026-04-26T12:34:56Z",
    )

    sidecar = dump.with_suffix(dump.suffix + ".json")
    assert sidecar.is_file()
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["app_version"] == "2.1.0"
    assert data["captured_at_iso"] == "2026-04-26T12:34:56Z"


# -- submit_crash_dump ------------------------------------------------


def test_submit_crash_dump_invokes_http_post(tmp_path: Path) -> None:
    """The function must POST the dump bytes to the configured
    URL via the injected ``http_post`` callable."""
    from lap_coach_logger.crash_dump import submit_crash_dump

    dump = tmp_path / "LapCoachLogger.exe.42.dmp"
    dump.write_bytes(b"MDMP fake dump payload")

    captured = []

    def fake_post(url: str, body: bytes, content_type: str, timeout_s: float):
        captured.append({
            "url": url,
            "body": body,
            "content_type": content_type,
            "timeout_s": timeout_s,
        })
        return 200  # http status

    result = submit_crash_dump(
        dump,
        url="https://crashes.example.invalid/submit",
        http_post=fake_post,
    )

    assert result.success is True
    assert result.error is None
    assert result.http_status == 200
    assert len(captured) == 1
    assert captured[0]["url"] == "https://crashes.example.invalid/submit"
    assert captured[0]["body"] == b"MDMP fake dump payload"
    assert "minidump" in captured[0]["content_type"].lower() or (
        "octet-stream" in captured[0]["content_type"].lower()
    )


def test_submit_crash_dump_returns_error_on_post_exception(
    tmp_path: Path,
) -> None:
    """Network failure must be captured as ``error`` rather
    than propagated. Otherwise the upload-thread crashes
    silently."""
    from lap_coach_logger.crash_dump import submit_crash_dump

    dump = tmp_path / "LapCoachLogger.exe.42.dmp"
    dump.write_bytes(b"MDMP")

    def boom(url, body, content_type, timeout_s):
        raise ConnectionError("DNS broken")

    result = submit_crash_dump(
        dump,
        url="https://crashes.example.invalid/submit",
        http_post=boom,
    )

    assert result.success is False
    assert result.error is not None
    assert "DNS broken" in result.error
    assert result.http_status is None


def test_submit_crash_dump_returns_error_when_dump_missing(
    tmp_path: Path,
) -> None:
    """A dump that's been deleted (manually, by AV, etc.)
    between discovery and submission must surface as an error
    rather than a confusing exception."""
    from lap_coach_logger.crash_dump import submit_crash_dump

    def fake_post(*a, **kw):
        return 200

    missing = tmp_path / "ghost.dmp"
    result = submit_crash_dump(
        missing,
        url="https://crashes.example.invalid/submit",
        http_post=fake_post,
    )
    assert result.success is False
    assert result.error is not None


def test_submit_crash_dump_returns_error_on_4xx_5xx(
    tmp_path: Path,
) -> None:
    """A non-2xx HTTP status from the upload must be surfaced
    as an error, not silently treated as success."""
    from lap_coach_logger.crash_dump import submit_crash_dump

    dump = tmp_path / "LapCoachLogger.exe.42.dmp"
    dump.write_bytes(b"MDMP")

    def fake_post(url, body, content_type, timeout_s):
        return 503  # service unavailable

    result = submit_crash_dump(
        dump,
        url="https://crashes.example.invalid/submit",
        http_post=fake_post,
    )
    assert result.success is False
    assert result.http_status == 503
    assert result.error is not None
