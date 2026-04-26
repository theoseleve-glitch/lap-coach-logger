"""T189: discover, label, and submit Windows minidump (.dmp)
files written when the app crashes.

The capture itself (writing the .dmp on segfault / unhandled
native exception) happens in OS-level code outside Python's
reach — Sentry's native SDK or a custom ``MiniDumpWriteDump``
unhandled-exception filter. This module covers what comes
*after* the dump exists on disk:

- :func:`find_crash_dumps` enumerates ``*.dmp`` files in a
  directory (non-recursive).
- :func:`mark_dump_for_review` writes a sidecar JSON
  preserving ``app_version`` + capture timestamp so the
  upload step has provenance even if the dump is moved.
- :func:`submit_crash_dump` POSTs the dump bytes via an
  injectable ``http_post`` callable. Never raises — returns
  a :class:`SubmitResult`.

Same shape as the auto-update plumbing (T186): frozen
dataclasses + never-raises functions + injectable I/O.
"""
from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)


# ``http_post(url, body, content_type, timeout_s) -> int``
# Returns HTTP status code. Raises on connection errors.
HttpPost = Callable[[str, bytes, str, float], int]

DEFAULT_TIMEOUT_S = 30.0
MINIDUMP_CONTENT_TYPE = "application/x-minidump"


@dataclasses.dataclass(frozen=True)
class CrashDumpEntry:
    """A discovered crash dump with sidecar metadata.

    ``dump_path`` points at the actual .dmp file;
    ``app_version`` is the version that was running when the
    dump was captured (so a dump from v2.0.0 doesn't get
    misattributed after an update); ``captured_at_iso`` is
    an ISO-8601 UTC timestamp.
    """

    dump_path: Path
    app_version: str
    captured_at_iso: str


@dataclasses.dataclass(frozen=True)
class SubmitResult:
    """Outcome of a single upload attempt.

    On success: ``success=True``, ``http_status`` is the 2xx
    code (typically 200/202), ``error=None``. On failure:
    ``success=False``, ``error`` describes what went wrong;
    ``http_status`` is set when the failure was a non-2xx
    response (None for connection errors / missing file).
    """

    success: bool
    error: str | None
    http_status: int | None


def find_crash_dumps(dump_dir: Path) -> list[Path]:
    """Enumerate ``*.dmp`` files in ``dump_dir`` (non-recursive).

    Returns ``[]`` for any failure mode: directory absent, no
    matching files, permission denied. Never raises — the
    crash-dump UI must not itself crash.
    """
    try:
        if not dump_dir.is_dir():
            return []
        return sorted(
            p for p in dump_dir.iterdir()
            if p.is_file() and p.suffix.lower() == ".dmp"
        )
    except OSError:
        return []


def _sidecar_path(dump_path: Path) -> Path:
    """Sidecar JSON lives at ``<dump>.json`` (literal suffix
    append, not replace) so ``LapCoachLogger.exe.42.dmp.json``
    sorts next to the dump and travels with it across moves."""
    return dump_path.with_suffix(dump_path.suffix + ".json")


def mark_dump_for_review(
    dump_path: Path,
    *,
    app_version: str,
    captured_at_iso: str,
) -> None:
    """Write the metadata sidecar at ``<dump>.json``.

    Atomic-ish: writes the JSON in one shot. The dump dir
    (which already contains the .dmp) is assumed to exist.
    """
    payload = {
        "app_version": app_version,
        "captured_at_iso": captured_at_iso,
    }
    _sidecar_path(dump_path).write_text(
        json.dumps(payload), encoding="utf-8",
    )


def read_dump_metadata(dump_path: Path) -> CrashDumpEntry | None:
    """Read the sidecar metadata. Returns ``None`` for any
    failure: sidecar absent, JSON malformed, fields missing
    or wrong type. Never raises."""
    sidecar = _sidecar_path(dump_path)
    if not sidecar.is_file():
        return None
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    app_v = data.get("app_version")
    captured = data.get("captured_at_iso")
    if not isinstance(app_v, str) or not isinstance(captured, str):
        return None
    return CrashDumpEntry(
        dump_path=dump_path,
        app_version=app_v,
        captured_at_iso=captured,
    )


def submit_crash_dump(
    dump_path: Path,
    url: str,
    *,
    http_post: HttpPost,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> SubmitResult:
    """POST the dump bytes to ``url`` via ``http_post``.

    Args:
        dump_path: Path to the .dmp file to upload.
        url: Crash submission endpoint URL.
        http_post: Injectable HTTP POST. Signature
            ``(url, body, content_type, timeout_s) -> int``
            where the return is the HTTP status code.
        timeout_s: Network timeout.

    Returns:
        :class:`SubmitResult` with success / error / status.
        Never raises.
    """
    try:
        body = dump_path.read_bytes()
    except OSError as exc:
        return SubmitResult(
            success=False,
            error=f"could not read dump: {type(exc).__name__}: {exc}",
            http_status=None,
        )

    try:
        status = http_post(url, body, MINIDUMP_CONTENT_TYPE, timeout_s)
    except Exception as exc:  # broad — see "never raises" docstring
        return SubmitResult(
            success=False,
            error=f"upload failed: {type(exc).__name__}: {exc}",
            http_status=None,
        )

    if 200 <= status < 300:
        return SubmitResult(
            success=True, error=None, http_status=status,
        )
    return SubmitResult(
        success=False,
        error=f"upload returned non-2xx status: {status}",
        http_status=status,
    )
