"""T191: download and cache the coaching rules bundle for
offline use.

Three primitives:

- :func:`download_rules_bundle` — atomic ``.partial`` + rename
  download from a URL to a cache path. Same shape as T186's
  ``download_update``.
- :func:`validate_rules_bundle` — parse + schema check on the
  downloaded bytes. Returns a :class:`RulesBundleStatus` with
  ``payload`` populated on success, ``error`` populated on
  failure. Never raises.
- :func:`load_cached_rules_bundle` — read + validate from the
  cache path. Returns the parsed dict or ``None`` for any
  failure (missing cache, malformed JSON, wrong shape).

Conceptually separate from auto-update (T186): this is content
delivery (data the app uses), not binary delivery (the app
itself). Callers may fall back to bundled defaults when the
cache is absent.
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
class RulesBundleStatus:
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


def download_rules_bundle(
    url: str,
    target_path: Path,
    *,
    http_get_bytes: HttpGetBytes | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> Path:
    """Stream a rules-bundle JSON download to ``target_path``
    via a ``.partial`` file, then atomic rename.

    Creates the parent directory if missing (first launch).
    Cleans up ``.partial`` on any failure. Re-raises whatever
    the fetcher raises — caller decides retry policy.
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


def validate_rules_bundle(payload_bytes: bytes) -> RulesBundleStatus:
    """Parse and schema-check the downloaded bytes.

    Required schema:

    - Top level is a JSON object.
    - Has a ``version`` field that's a non-empty string.
    - Has a ``rules`` field that's a list (possibly empty).

    Never raises. Errors are captured in the ``error`` field.
    """
    try:
        data = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return RulesBundleStatus(
            payload=None,
            error=f"could not parse JSON: {type(exc).__name__}: {exc}",
        )
    except Exception as exc:
        return RulesBundleStatus(
            payload=None,
            error=f"unexpected parse error: {type(exc).__name__}: {exc}",
        )

    if not isinstance(data, dict):
        return RulesBundleStatus(
            payload=None,
            error=f"top-level must be a JSON object, got {type(data).__name__}",
        )

    version = data.get("version")
    if not isinstance(version, str) or not version:
        return RulesBundleStatus(
            payload=None,
            error="bundle missing 'version' (must be a non-empty string)",
        )

    rules = data.get("rules")
    if not isinstance(rules, list):
        return RulesBundleStatus(
            payload=None,
            error=(
                f"bundle missing 'rules' or wrong type "
                f"(must be a list, got {type(rules).__name__})"
            ),
        )

    return RulesBundleStatus(payload=data, error=None)


# -- load from cache --------------------------------------------------


def load_cached_rules_bundle(
    cache_path: Path,
) -> dict[str, Any] | None:
    """Read + validate the cached bundle in one shot.

    Returns the parsed dict on success, ``None`` for any
    failure (cache absent, unreadable, malformed, wrong
    shape). Never raises — the launch path must keep working
    if the cache is corrupt (we fall back to bundled defaults).
    """
    if not cache_path.is_file():
        return None
    try:
        raw = cache_path.read_bytes()
    except OSError:
        return None
    status = validate_rules_bundle(raw)
    return status.payload
