"""Config schema migrations.

  - ``CURRENT_SCHEMA_VERSION`` = the version this codebase writes.
  - ``migrate_to_current(data)`` = pure dict-in / dict-out
    migration. Returns ``(migrated, did_migrate)`` so callers can
    skip the re-save when nothing changed (avoids churning mtime
    on every launch).

Adding a new schema bump (e.g. v2 → v3):
    1. bump ``CURRENT_SCHEMA_VERSION`` to 3
    2. add a ``_migrate_v2_to_v3(data)`` step
    3. extend the chain in ``migrate_to_current``
    4. update the test for ``CURRENT_SCHEMA_VERSION``
"""
from __future__ import annotations

import logging

CURRENT_SCHEMA_VERSION: int = 2

_log = logging.getLogger(__name__)


def _migrate_v1_to_v2(data: dict) -> dict:
    """v1 (pre-T222) had no explicit ``schema_version`` key; the
    schema itself was stable apart from silent additive fields
    that ``AppConfig.from_dict`` already absorbs via defaults
    (telemetry_enabled, auto_update_enabled, accessibility, ...).

    The 1→2 step therefore just stamps the version. Future bumps
    do the real renames here.
    """
    out = dict(data)
    out["schema_version"] = 2
    return out


def migrate_to_current(data: dict) -> tuple[dict, bool]:
    """Apply the migration chain to bring ``data`` to
    ``CURRENT_SCHEMA_VERSION``.

    Returns:
        (migrated_data, did_migrate)

        - ``did_migrate`` is True only when the data was older
          than current and we transformed it. Caller writes back
          to disk in that case.
        - When the data is already current, returns the original
          data unchanged with did_migrate=False (no churn).
        - When the data is from a *newer* schema (older binary
          launched on a newer config), passes through untouched
          with did_migrate=False — best-effort, don't lose user
          state, don't overwrite a newer file.
    """
    version = data.get("schema_version")

    if version is None:
        # v1 → v2
        _log.info("Config: migrating v1 → v2 (stamping schema_version)")
        return _migrate_v1_to_v2(data), True

    if version == CURRENT_SCHEMA_VERSION:
        return data, False

    if version > CURRENT_SCHEMA_VERSION:
        _log.warning(
            "Config schema_version %d is newer than this binary "
            "(%d). Loading best-effort; will not rewrite to disk.",
            version,
            CURRENT_SCHEMA_VERSION,
        )
        return data, False

    # Future: chain v2 → v3, v3 → v4, ...
    # if version == 2:
    #     data = _migrate_v2_to_v3(data)
    #     version = 3
    # ...

    _log.warning(
        "Config schema_version %d has no migration path to %d; "
        "loading best-effort.",
        version,
        CURRENT_SCHEMA_VERSION,
    )
    return data, False
