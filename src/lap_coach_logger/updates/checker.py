"""T185: best-effort version check on app start.

Fetches a small JSON manifest of shape ``{"version": "X.Y.Z",
...}`` from a static URL, compares against the running
``__version__``, and returns an ``UpdateCheckResult`` that
captures *both* success and failure (the function never raises).

Design constraints:

- **Never raises.** A daemon thread invokes this at startup; an
  uncaught exception there would crash silently and we'd lose
  the diagnostic trail. All exceptions are captured as
  ``error`` in the returned result.
- **Pure-ish.** The HTTP fetcher is injected via ``http_get``
  so tests can run offline and instantly. The default fetcher
  uses ``urllib.request`` from stdlib (avoiding a ``requests``
  dependency).
- **Numeric semver compare.** ``"1.10.0" > "1.9.9"`` works the
  way users expect, not lexicographically.
"""
from __future__ import annotations

import dataclasses
import json
import logging
from typing import Callable

log = logging.getLogger(__name__)


# Placeholder URL — real production URL gets configured via env
# var or settings in T186/T187. For T185 the default is only
# used if no override is supplied; the test suite always
# injects a fake fetcher.
DEFAULT_MANIFEST_URL = (
    "https://updates.lapcoach.invalid/manifest.json"
)

DEFAULT_TIMEOUT_S = 5.0


HttpGet = Callable[[str, float], dict]


@dataclasses.dataclass(frozen=True)
class UpdateCheckResult:
    """Outcome of a single update check.

    On success: ``latest_version`` is set and ``error`` is
    ``None``. On any failure (network, malformed manifest,
    parse error): ``latest_version`` is ``None``, ``has_update``
    is ``False``, and ``error`` describes what went wrong.
    """

    current_version: str
    latest_version: str | None
    has_update: bool
    error: str | None


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse ``"2.10.1"`` into ``(2, 10, 1)`` for numeric
    compare. Non-numeric components (e.g. ``"2.0.0-rc1"``) raise
    ``ValueError`` — caller handles."""
    return tuple(int(part) for part in v.split("."))


def _is_newer(latest: str, current: str) -> bool:
    """True iff ``latest`` is strictly greater than ``current``
    in numeric semver order. Falls back to ``False`` on parse
    failure (rather than raising) — an unparseable version
    string is not a valid "newer" claim."""
    try:
        return _parse_version(latest) > _parse_version(current)
    except ValueError:
        return False


def _default_http_get(url: str, timeout_s: float) -> dict:
    """Stdlib-only JSON GET. Returns the parsed object."""
    import urllib.request

    with urllib.request.urlopen(url, timeout=timeout_s) as resp:
        body = resp.read()
    parsed = json.loads(body.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(
            f"manifest must be a JSON object, got {type(parsed).__name__}"
        )
    return parsed


def check_for_updates(
    current_version: str,
    *,
    manifest_url: str = DEFAULT_MANIFEST_URL,
    http_get: HttpGet | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> UpdateCheckResult:
    """Check whether a newer version is published in the
    manifest at ``manifest_url``. Always returns; never raises.

    Args:
        current_version: The running app's ``__version__``.
        manifest_url: URL to the JSON manifest (default points
            to a placeholder; production config overrides).
        http_get: Injectable fetcher ``(url, timeout) -> dict``
            for testing. Default uses stdlib ``urllib``.
        timeout_s: Network timeout in seconds.

    Returns:
        ``UpdateCheckResult`` with all fields populated.
    """
    fetcher: HttpGet = http_get if http_get is not None else _default_http_get

    try:
        manifest = fetcher(manifest_url, timeout_s)
    except Exception as exc:  # broad on purpose — see docstring
        return UpdateCheckResult(
            current_version=current_version,
            latest_version=None,
            has_update=False,
            error=f"{type(exc).__name__}: {exc}",
        )

    if not isinstance(manifest, dict):
        return UpdateCheckResult(
            current_version=current_version,
            latest_version=None,
            has_update=False,
            error=f"manifest is not a JSON object: {type(manifest).__name__}",
        )

    latest_raw = manifest.get("version")
    if not isinstance(latest_raw, str):
        return UpdateCheckResult(
            current_version=current_version,
            latest_version=None,
            has_update=False,
            error=(
                f"manifest 'version' field missing or not a string: "
                f"{latest_raw!r}"
            ),
        )

    return UpdateCheckResult(
        current_version=current_version,
        latest_version=latest_raw,
        has_update=_is_newer(latest_raw, current_version),
        error=None,
    )
