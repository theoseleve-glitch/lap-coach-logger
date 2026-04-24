"""Sprint T024 audit: no duplicate Pydantic models in desktop.

Locks the outcome of the T022/T023 removals and prevents future drift:

* Sprint T022 removed the local ``SessionManifest`` dataclass (renamed
  to ``LegacySessionManifest`` as transitional, shared Pydantic model
  now owns the ``SessionManifest`` name).
* Sprint T023 removed the local ``LapRecord`` dataclass (renamed to
  ``LegacyLapRecord``, shared Pydantic model now owns the name).
* Additionally the stale ``SessionManifest`` import in ``finalizer.py``
  was removed, and every test-side construction of these types was
  migrated to the ``Legacy*`` aliases.

Going forward the desktop tree must not introduce its own
``pydantic.BaseModel`` subclasses — those belong in
``lap_schemas.v1`` (or later) so every consumer shares one shape.
"""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src" / "lap_coach_logger"

# ``class Foo(BaseModel):`` or multi-base-inheritance that includes BaseModel.
_PYDANTIC_CLASS = re.compile(r"^class\s+\w+\s*\([^)]*\bBaseModel\b[^)]*\)\s*:", re.MULTILINE)


def _python_files() -> list[Path]:
    return [p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts]


def test_desktop_has_no_local_pydantic_base_models() -> None:
    offenders: list[tuple[str, int]] = []
    for path in _python_files():
        for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _PYDANTIC_CLASS.match(line):
                offenders.append((str(path.relative_to(REPO_ROOT)), idx))
    assert offenders == [], (
        "Desktop tree must not define local pydantic.BaseModel subclasses. "
        f"Move these to lap_schemas.v1 instead: {offenders}"
    )


def test_bundle_schema_defines_no_local_session_manifest_or_lap_record() -> None:
    source = (SRC / "writers" / "bundle_schema.py").read_text(encoding="utf-8")
    # T022/T023 renamed the local dataclasses to ``Legacy*``. If someone
    # re-introduces the original name as a class def here, it shadows the
    # shared Pydantic re-export at import time.
    assert not re.search(r"^class SessionManifest\b", source, re.MULTILINE), (
        "writers/bundle_schema.py must not redefine SessionManifest locally "
        "(removed in T022 — shared lap_schemas.v1.SessionManifest re-exported)."
    )
    assert not re.search(r"^class LapRecord\b", source, re.MULTILINE), (
        "writers/bundle_schema.py must not redefine LapRecord locally "
        "(removed in T023 — shared lap_schemas.v1.LapRecord re-exported)."
    )


def test_shared_types_still_exported_from_bundle_schema() -> None:
    # Sanity: the re-exports from T022/T023 are still wired.
    from lap_coach_logger.writers.bundle_schema import LapRecord, SessionManifest
    from lap_schemas.v1 import LapRecord as V1LapRecord
    from lap_schemas.v1 import SessionManifest as V1SessionManifest

    assert SessionManifest is V1SessionManifest
    assert LapRecord is V1LapRecord
