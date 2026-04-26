"""T192: download and cache the track catalog for offline
sector-split computation.

Three primitives, identical shape to T191's rules bundle but
a separate module since the consumers and content schema
differ:

- :func:`download_track_catalog` — atomic ``.partial`` +
  rename pattern.
- :func:`validate_track_catalog` — parse + check top-level
  shape ``{"version": str, "tracks": list}``. Returns a
  :class:`TrackCatalogStatus`. Never raises.
- :func:`load_cached_track_catalog` — read + validate; returns
  the parsed dict or ``None`` for any failure mode.

Per-track schema (sector boundaries, track length, GPS
coordinates) is the consumer's responsibility — T192 just
guarantees structural integrity at transport time. A
half-cached catalog must never reach the sector-split
computation, otherwise users see ghost deltas at random
sectors.
"""
from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path
from typing import Any, Callable, Iterable

log = logging.getLogger(__name__)


HttpGetBytes = Callable[[str, float], Iterable[bytes]]

DEFAULT_TIMEOUT_S = 30.0


@dataclasses.dataclass(frozen=True)
class TrackCatalogStatus:
    """Outcome of a parse + validate pass.

    On success: ``payload`` is the parsed dict, ``error`` is
    ``None``. On failure: ``payload`` is ``None`` and ``error``
    describes what went wrong.
    """

    payload: dict[str, Any] | None
    error: str | None


# -- atomic download --------------------------------------------------


def _default_http_get_bytes(url: str, timeout_s: float) -> Iterable[bytes]:
    """Stdlib-only streaming GET. Tests always inject."""
    import urllib.request

    with urllib.request.urlopen(url, timeout=timeout_s) as resp:
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                return
            yield chunk


def download_track_catalog(
    url: str,
    target_path: Path,
    *,
    http_get_bytes: HttpGetBytes | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> Path:
    """Stream a track-catalog JSON download to ``target_path``
    via a ``.partial`` file, then atomic rename.

    Creates the parent directory if missing (first launch).
    Cleans up ``.partial`` on any failure. Re-raises whatever
    the fetcher raises.
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
        try:
            partial.unlink()
        except FileNotFoundError:
            pass
        raise

    partial.replace(target_path)
    return target_path


# -- validate ---------------------------------------------------------


def validate_track_catalog(payload_bytes: bytes) -> TrackCatalogStatus:
    """Parse and schema-check the downloaded bytes.

    Required schema:

    - Top level is a JSON object.
    - ``version`` is a non-empty string.
    - ``tracks`` is a list (possibly empty).

    Per-track validation belongs to the consumer; T192 just
    guarantees the bundle is structurally a catalog.

    Never raises.
    """
    try:
        data = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return TrackCatalogStatus(
            payload=None,
            error=f"could not parse JSON: {type(exc).__name__}: {exc}",
        )
    except Exception as exc:
        return TrackCatalogStatus(
            payload=None,
            error=f"unexpected parse error: {type(exc).__name__}: {exc}",
        )

    if not isinstance(data, dict):
        return TrackCatalogStatus(
            payload=None,
            error=f"top-level must be a JSON object, got {type(data).__name__}",
        )

    version = data.get("version")
    if not isinstance(version, str) or not version:
        return TrackCatalogStatus(
            payload=None,
            error="catalog missing 'version' (must be a non-empty string)",
        )

    tracks = data.get("tracks")
    if not isinstance(tracks, list):
        return TrackCatalogStatus(
            payload=None,
            error=(
                f"catalog missing 'tracks' or wrong type "
                f"(must be a list, got {type(tracks).__name__})"
            ),
        )

    return TrackCatalogStatus(payload=data, error=None)


# -- load from cache --------------------------------------------------


def load_cached_track_catalog(
    cache_path: Path,
) -> dict[str, Any] | None:
    """Read + validate the cached catalog in one shot.

    Returns the parsed dict on success, ``None`` for any
    failure (cache absent, unreadable, malformed, wrong
    shape). Never raises.
    """
    if not cache_path.is_file():
        return None
    try:
        raw = cache_path.read_bytes()
    except OSError:
        return None
    status = validate_track_catalog(raw)
    return status.payload
